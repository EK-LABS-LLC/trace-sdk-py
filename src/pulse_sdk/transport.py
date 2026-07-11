from __future__ import annotations

import json
from typing import Any, Dict, List

import requests

from .types import Span

DEFAULT_TIMEOUT = 10  # seconds


def send_spans(api_url: str, api_key: str, spans: List[Span]) -> None:
    if not spans:
        return

    url = f"{api_url.rstrip('/')}/v1/traces"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        url, headers=headers, data=json.dumps(_to_otlp(spans)), timeout=DEFAULT_TIMEOUT
    )
    if not response.ok:
        raise RuntimeError(
            f"Pulse SDK: failed to send spans ({response.status_code}): {response.text}"
        )


def _attr(key: str, value: str) -> Dict[str, Any]:
    return {"key": key, "value": {"stringValue": value}}


def _to_otlp(spans: List[Span]) -> Dict[str, Any]:
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": [_attr("service.name", "pulse-sdk-py")]},
                "scopeSpans": [
                    {
                        "scope": {"name": "pulse-trace-sdk"},
                        "spans": [_to_otlp_span(span) for span in spans],
                    }
                ],
            }
        ]
    }


def _to_otlp_span(span: Span) -> Dict[str, Any]:
    start_ms = _parse_iso_ms(span["timestamp"])
    start_ns = start_ms * 1_000_000
    end_ns = start_ns + int(span.get("duration_ms", 0)) * 1_000_000
    attrs = [
        _attr("pulse.source", span["source"]),
        _attr("pulse.kind", span["kind"]),
        _attr("pulse.event_type", span["event_type"]),
        _attr("pulse.session_id", span["session_id"]),
        _attr("pulse.trace_id", span["trace_id"]),
    ]
    if span.get("model"):
        attrs.append(_attr("gen_ai.request.model", str(span["model"])))
    if span.get("provider"):
        attrs.append(_attr("gen_ai.provider.name", span["provider"]))
    if span.get("model_used"):
        attrs.append(_attr("gen_ai.response.model", span["model_used"]))
    if span.get("provider_request_id"):
        attrs.append(_attr("gen_ai.response.id", span["provider_request_id"]))
    if span.get("finish_reason"):
        attrs.append(_attr("gen_ai.response.finish_reasons", json.dumps([span["finish_reason"]])))
    if span.get("input_tokens") is not None:
        attrs.append({"key": "gen_ai.usage.input_tokens", "value": {"intValue": str(span["input_tokens"])}})
    if span.get("output_tokens") is not None:
        attrs.append({"key": "gen_ai.usage.output_tokens", "value": {"intValue": str(span["output_tokens"])}})
    if span.get("cost_cents") is not None:
        attrs.append({"key": "pulse.cost_cents", "value": {"doubleValue": float(span["cost_cents"])}})
    if span.get("output_text") is not None:
        attrs.append(_attr("pulse.output_text", span["output_text"]))
    if span.get("tool_use_id"):
        attrs.append(_attr("pulse.tool.id", span["tool_use_id"]))
    if span.get("tool_name"):
        attrs.append(_attr("pulse.tool.name", span["tool_name"]))
        attrs.append(_attr("gen_ai.tool.name", span["tool_name"]))
    if "tool_input" in span:
        attrs.append(_attr("pulse.tool.input", json.dumps(span["tool_input"], default=str)))
    if "tool_response" in span:
        attrs.append(
            _attr("pulse.tool.response", json.dumps(span["tool_response"], default=str))
        )
    if "error" in span:
        attrs.append(_attr("pulse.error", json.dumps(span["error"], default=str)))
    for key, value in span.get("metadata", {}).items():
        attrs.append(_attr(key, value if isinstance(value, str) else json.dumps(value, default=str)))

    status: Dict[str, Any] = {"code": 2 if span["status"] == "error" else 1}
    error = span.get("error")
    if span["status"] == "error" and isinstance(error, dict) and isinstance(error.get("message"), str):
        status["message"] = error["message"]

    result: Dict[str, Any] = {
        "traceId": span["trace_id"],
        "spanId": span["span_id"],
        "name": span.get("tool_name") or span["event_type"],
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": attrs,
        "status": status,
    }
    if span.get("parent_span_id"):
        result["parentSpanId"] = span["parent_span_id"]
    return result


def _parse_iso_ms(value: str) -> int:
    import datetime

    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1000)
