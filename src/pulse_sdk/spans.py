from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from .ids import generate_span_id
from .pricing import calculate_cost
from .trace import current_timestamp
from .types import NormalizedResponse, Provider, Span

MAX_PAYLOAD_BYTES = 64 * 1024
PENDING_TTL_SECONDS = 10 * 60

_pending: Dict[str, Dict[str, Any]] = {}


def _key(provider: Provider, client_id: str, session_id: str, tool_id: str) -> str:
    return f"{provider.value}:{client_id}:{session_id}:{tool_id}"


def _expire() -> None:
    now = time.time()
    for key, value in list(_pending.items()):
        if now - float(value["created_at"]) > PENDING_TTL_SECONDS:
            _pending.pop(key, None)


def resolve_session_id(session_id: Optional[str], fallback: str) -> str:
    return session_id or fallback


def compact_payload(value: Any) -> Any:
    if value is None:
        return value
    try:
        serialized = value if isinstance(value, str) else json.dumps(value, default=str)
    except Exception:
        serialized = str(value)
    size = len(serialized.encode("utf-8"))
    if size <= MAX_PAYLOAD_BYTES:
        return value
    return {
        "truncated": True,
        "originalBytes": size,
        "preview": serialized[:MAX_PAYLOAD_BYTES],
    }


def correlate_tool_results(
    provider: Provider,
    client_id: str,
    session_id: str,
    results: List[Dict[str, Any]],
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    _expire()
    matches = []
    for result in results:
        pending = _pending.pop(_key(provider, client_id, session_id, result["id"]), None)
        if pending:
            matches.append(
                {
                    "result": result,
                    "trace_id": pending["trace_id"],
                    "parent_span_id": pending["tool_request_span_id"],
                    "status": "matched",
                }
            )
        else:
            matches.append({"result": result, "status": "orphan"})

    trace_ids = {match.get("trace_id") for match in matches if match.get("trace_id")}
    trace_id = next(iter(trace_ids)) if matches and len(trace_ids) == 1 and all(
        match["status"] == "matched" for match in matches
    ) else None
    return trace_id, matches


def truncate_string(value: str) -> str:
    """Byte-caps a string payload, keeping it a string (unlike compact_payload)."""
    encoded = value.encode("utf-8")
    if len(encoded) <= MAX_PAYLOAD_BYTES:
        return value
    return encoded[:MAX_PAYLOAD_BYTES].decode("utf-8", errors="ignore")


def _response_cost_cents(response: NormalizedResponse) -> Optional[float]:
    # Prefer provider-supplied cost (e.g. OpenRouter includes it directly).
    if response.cost_cents is not None:
        return response.cost_cents
    if response.input_tokens is None or response.output_tokens is None:
        return None
    return calculate_cost(response.model, response.input_tokens, response.output_tokens)


def build_provider_span(
    *,
    trace_id: str,
    session_id: str,
    provider: Provider,
    request: Dict[str, Any],
    response: Optional[NormalizedResponse],
    started_at: str,
    latency_ms: float,
    status: str,
    error: Any = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Span:
    span: Span = {
        "span_id": generate_span_id(),
        "trace_id": trace_id,
        "session_id": session_id,
        "timestamp": started_at,
        "duration_ms": int(round(latency_ms)),
        "source": "sdk",
        "kind": "llm_call",
        "event_type": "provider_call",
        "status": status,
        "model": str(request.get("model")) if request.get("model") else (response.model if response else "unknown"),
        "provider": provider.value,
        "metadata": {
            **(metadata or {}),
            "pulse.provider": provider.value,
            "pulse.request": compact_payload(request),
            "pulse.response": compact_payload(response.__dict__ if response else None),
        },
    }
    if response is not None:
        span["model_used"] = response.model
        if response.input_tokens is not None:
            span["input_tokens"] = response.input_tokens
        if response.output_tokens is not None:
            span["output_tokens"] = response.output_tokens
        cost_cents = _response_cost_cents(response)
        if cost_cents is not None:
            span["cost_cents"] = cost_cents
        if response.finish_reason:
            span["finish_reason"] = response.finish_reason
        if response.content is not None:
            span["output_text"] = truncate_string(response.content)
        if response.provider_request_id:
            span["provider_request_id"] = response.provider_request_id
    if error is not None:
        span["error"] = compact_payload(error)
    return span


def build_tool_result_spans(
    trace_id: str, session_id: str, matches: List[Dict[str, Any]]
) -> List[Span]:
    spans = []
    for match in matches:
        result = match["result"]
        span: Span = {
            "span_id": generate_span_id(),
            "trace_id": match.get("trace_id") or trace_id,
            "session_id": session_id,
            "timestamp": current_timestamp(),
            "source": "sdk",
            "kind": "tool_use",
            "event_type": "tool_result",
            "status": "success",
            "tool_use_id": result["id"],
            "tool_response": compact_payload(result.get("response")),
            "metadata": {"pulse.correlation.status": match["status"]},
        }
        if match.get("parent_span_id"):
            span["parent_span_id"] = match["parent_span_id"]
        if result.get("name"):
            span["tool_name"] = result["name"]
        spans.append(span)
    return spans


def build_tool_request_spans(
    *,
    provider: Provider,
    client_id: str,
    trace_id: str,
    session_id: str,
    parent_span_id: str,
    tool_calls: List[Dict[str, Any]],
) -> List[Span]:
    _expire()
    spans = []
    for call in tool_calls:
        span_id = generate_span_id()
        _pending[_key(provider, client_id, session_id, call["id"])] = {
            "trace_id": trace_id,
            "tool_request_span_id": span_id,
            "created_at": time.time(),
        }
        span: Span = {
            "span_id": span_id,
            "trace_id": trace_id,
            "session_id": session_id,
            "parent_span_id": parent_span_id,
            "timestamp": current_timestamp(),
            "source": "sdk",
            "kind": "tool_use",
            "event_type": "tool_request",
            "status": "success",
            "tool_use_id": call["id"],
            "tool_input": compact_payload(call.get("input")),
        }
        if call.get("name"):
            span["tool_name"] = call["name"]
        spans.append(span)
    return spans


def parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value
