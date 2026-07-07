from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional

from .types import Trace

SCOPE_NAME = "pulse-trace-sdk"
SCOPE_VERSION = "0.2.8"
SERVICE_NAME = "pulse-sdk-python"
OTEL_SPAN_KIND_CLIENT = 3
OTEL_STATUS_CODE_OK = 1
OTEL_STATUS_CODE_ERROR = 2


def _truncate_text(value: str, max_length: int = 140) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip()


def _string_value(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _message_content(message: Any) -> Optional[str]:
    if not isinstance(message, dict):
        return None

    content = message.get("content")
    if isinstance(content, str):
        return _string_value(content)

    if isinstance(content, list):
        parts: List[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = _string_value(part.get("text")) or _string_value(
                    part.get("content")
                )
                if text:
                    parts.append(text)
        if parts:
            return " ".join(parts)

    return None


def prompt_preview_from_request(request: Dict[str, Any]) -> Optional[str]:
    messages = request.get("messages")
    if isinstance(messages, list) and messages:
        user_messages = [
            message
            for message in messages
            if isinstance(message, dict) and message.get("role") == "user"
        ]
        content = _message_content((user_messages or messages)[-1])
        if content:
            return _truncate_text(content)

    for key in ("prompt", "input"):
        prompt = _string_value(request.get(key))
        if prompt:
            return _truncate_text(prompt)

    return None


def _json_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)
    except TypeError:
        return str(value)


def _otlp_value(value: Any) -> Dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": str(value)}


def _attribute(key: str, value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, str) and not value:
        return None
    return {"key": key, "value": _otlp_value(value)}


def _attributes(values: Dict[str, Any]) -> List[Dict[str, Any]]:
    attributes = [_attribute(key, value) for key, value in values.items()]
    return [attribute for attribute in attributes if attribute is not None]


def _metadata_string(metadata: Dict[str, Any], keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        value = _string_value(metadata.get(key))
        if value:
            return value
    return None


def _trace_attributes(trace: Trace) -> List[Dict[str, Any]]:
    request_body = trace.get("request_body", {})
    metadata = trace.get("metadata") or {}
    prompt_preview = (
        _metadata_string(metadata, ("pulse.prompt.preview", "prompt"))
        or prompt_preview_from_request(request_body)
    )
    session_name = _metadata_string(
        metadata, ("pulse.session.name", "session.name", "thread.name")
    )
    trace_name = _metadata_string(
        metadata, ("pulse.trace.name", "trace.name", "operation.name")
    )

    base_attributes: Dict[str, Any] = {
        "pulse.source": "sdk",
        "pulse.kind": "llm_call",
        "pulse.event_type": "provider_request",
        "pulse.trace_id": trace.get("trace_id"),
        "pulse.span_id": trace.get("span_id"),
        "pulse.session_id": trace.get("session_id"),
        "pulse.session.name": session_name,
        "pulse.trace.name": trace_name,
        "pulse.prompt.preview": prompt_preview,
        "pulse.provider_request_id": trace.get("provider_request_id"),
        "pulse.cost_cents": trace.get("cost_cents"),
        "pulse.latency_ms": trace.get("latency_ms"),
        "pulse.status": trace.get("status"),
        "pulse.finish_reason": trace.get("finish_reason"),
        "pulse.request.body": _json_string(request_body),
        "pulse.response.body": _json_string(trace.get("response_body")),
        "pulse.output_text": trace.get("output_text"),
        "session.id": trace.get("session_id"),
        "session.name": session_name,
        "trace.name": trace_name,
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": trace.get("provider"),
        "gen_ai.request.model": trace.get("model_requested"),
        "gen_ai.response.model": trace.get("model_used"),
        "gen_ai.usage.input_tokens": trace.get("input_tokens"),
        "gen_ai.usage.output_tokens": trace.get("output_tokens"),
    }

    return _attributes(base_attributes)


def _span_name(trace: Trace) -> str:
    metadata = trace.get("metadata") or {}
    trace_name = _metadata_string(metadata, ("pulse.trace.name", "trace.name"))
    if trace_name:
        return trace_name
    provider = trace.get("provider") or "provider"
    model = trace.get("model_requested") or "unknown"
    return f"{provider}.{model}"


def _span_events(trace: Trace) -> Optional[List[Dict[str, Any]]]:
    error = trace.get("error")
    if not error:
        return None

    return [
        {
            "name": "exception",
            "timeUnixNano": trace.get("end_time_unix_nano"),
            "attributes": _attributes(
                {
                    "exception.type": error.get("name"),
                    "exception.message": error.get("message"),
                }
            ),
        }
    ]


def trace_to_otlp_span(trace: Trace) -> Dict[str, Any]:
    status_code = (
        OTEL_STATUS_CODE_ERROR
        if str(trace.get("status")).lower() == "error"
        else OTEL_STATUS_CODE_OK
    )
    status: Dict[str, Any] = {"code": status_code}
    error = trace.get("error")
    if error and error.get("message"):
        status["message"] = error["message"]

    span: Dict[str, Any] = {
        "traceId": trace["trace_id"],
        "spanId": trace["span_id"],
        "name": _span_name(trace),
        "kind": OTEL_SPAN_KIND_CLIENT,
        "startTimeUnixNano": trace["start_time_unix_nano"],
        "endTimeUnixNano": trace["end_time_unix_nano"],
        "attributes": _trace_attributes(trace),
        "status": status,
    }
    events = _span_events(trace)
    if events:
        span["events"] = events
    return span


def traces_to_otlp_json(traces: List[Trace]) -> Dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": _attributes(
                        {
                            "service.name": SERVICE_NAME,
                            "telemetry.sdk.language": "python",
                            "telemetry.sdk.name": SCOPE_NAME,
                            "pulse.source": "sdk",
                        }
                    )
                },
                "scopeSpans": [
                    {
                        "scope": {
                            "name": SCOPE_NAME,
                            "version": SCOPE_VERSION,
                        },
                        "spans": [trace_to_otlp_span(trace) for trace in traces],
                    }
                ],
            }
        ]
    }
