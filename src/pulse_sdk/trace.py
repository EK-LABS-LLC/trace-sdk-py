from __future__ import annotations

import copy
import datetime
import time
import uuid
from typing import Any, Dict, Optional

from .pricing import calculate_cost
from .types import NormalizedResponse, Provider, Trace, TraceStatus


def generate_trace_id() -> str:
    return str(uuid.uuid4())


def current_timestamp() -> str:
    return datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()


def extract_pulse_params(
    payload: Dict[str, Any],
) -> tuple[Dict[str, Any], Optional[str], Optional[Dict[str, Any]]]:
    clean = copy.deepcopy(payload)
    session = None
    metadata = None

    for key in ("pulse_session_id", "pulseSessionId"):
        if key in clean:
            session = clean.pop(key)
            break

    for key in ("pulse_metadata", "pulseMetadata"):
        if key in clean:
            metadata = clean.pop(key)
            break

    return clean, session, metadata  # type: ignore[return-value]


def resolve_trace_metadata(
    observe_session: Optional[str],
    observe_metadata: Optional[Dict[str, Any]],
    pulse_session: Optional[str],
    pulse_metadata: Optional[Dict[str, Any]],
) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    session_id = pulse_session or observe_session
    metadata = observe_metadata.copy() if observe_metadata else None
    if pulse_metadata:
        metadata = {**(metadata or {}), **pulse_metadata}
    return session_id, metadata


def build_trace(
    request: Dict[str, Any],
    response: Optional[NormalizedResponse],
    provider: Provider,
    latency_ms: float,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Trace:
    trace: Trace = {
        "trace_id": generate_trace_id(),
        "timestamp": current_timestamp(),
        "provider": provider.value,
        "model_requested": str(request.get("model", "unknown")),
        "request_body": request,
        "latency_ms": int(round(latency_ms)),
        "status": TraceStatus.SUCCESS.value if response else TraceStatus.ERROR.value,
    }

    if response:
        trace["model_used"] = response.model
        trace["response_body"] = {
            "content": response.content,
            "inputTokens": response.input_tokens,
            "outputTokens": response.output_tokens,
            "finishReason": response.finish_reason,
            "model": response.model,
        }
        trace["input_tokens"] = response.input_tokens
        trace["output_tokens"] = response.output_tokens
        trace["output_text"] = response.content
        trace["finish_reason"] = response.finish_reason
        if response.provider_request_id:
            trace["provider_request_id"] = response.provider_request_id

        if response.cost_cents is not None:
            trace["cost_cents"] = response.cost_cents
        elif response.input_tokens is not None and response.output_tokens is not None:
            calculated = calculate_cost(
                response.model, response.input_tokens, response.output_tokens
            )
            if calculated is not None:
                trace["cost_cents"] = calculated
    else:
        trace["status"] = TraceStatus.ERROR.value

    if session_id:
        trace["session_id"] = session_id
    if metadata:
        trace["metadata"] = metadata

    return trace


def build_error_trace(
    request: Dict[str, Any],
    error: Exception,
    provider: Provider,
    latency_ms: float,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Trace:
    trace = build_trace(request, None, provider, latency_ms, session_id, metadata)
    trace["status"] = TraceStatus.ERROR.value
    trace["error"] = {
        "name": error.__class__.__name__,
        "message": str(error),
    }
    return trace
