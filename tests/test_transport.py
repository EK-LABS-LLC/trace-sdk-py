import json
import re
from typing import Any, Dict, List

from pulse_sdk.ids import generate_span_id, generate_trace_id
from pulse_sdk.transport import _to_otlp, send_spans
from pulse_sdk.types import Span


def _sample_span(**overrides: Any) -> Span:
    span: Span = {
        "span_id": "2222222222222222",
        "trace_id": "11111111111111111111111111111111",
        "session_id": "session-123",
        "timestamp": "2026-07-07T12:00:00.250+00:00",
        "duration_ms": 250,
        "source": "sdk",
        "kind": "llm_call",
        "event_type": "provider_call",
        "status": "success",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "model_used": "gpt-4o-mini-2024-07-18",
        "provider_request_id": "chatcmpl_123",
        "input_tokens": 10,
        "output_tokens": 20,
        "cost_cents": 0.002,
        "finish_reason": "stop",
        "output_text": "Hello",
        "metadata": {"tenant": "acme"},
    }
    span.update(overrides)  # type: ignore[typeddict-item]
    return span


def _attr_map(attributes: List[Dict[str, Any]]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    for attribute in attributes:
        value = attribute["value"]
        if "stringValue" in value:
            values[attribute["key"]] = value["stringValue"]
        elif "intValue" in value:
            values[attribute["key"]] = int(value["intValue"])
        elif "doubleValue" in value:
            values[attribute["key"]] = value["doubleValue"]
        elif "boolValue" in value:
            values[attribute["key"]] = value["boolValue"]
    return values


def test_ids_are_otel_compatible_hex() -> None:
    for _ in range(20):
        assert re.fullmatch(r"[0-9a-f]{32}", generate_trace_id())
        assert re.fullmatch(r"[0-9a-f]{16}", generate_span_id())


def test_to_otlp_serializes_llm_call_span() -> None:
    body = _to_otlp([_sample_span()])

    resource_span = body["resourceSpans"][0]
    resource_attrs = _attr_map(resource_span["resource"]["attributes"])
    assert resource_attrs["service.name"] == "pulse-sdk-py"

    scope_span = resource_span["scopeSpans"][0]
    assert scope_span["scope"]["name"] == "pulse-trace-sdk"
    assert len(scope_span["spans"]) == 1

    span = scope_span["spans"][0]
    assert span["traceId"] == "11111111111111111111111111111111"
    assert span["spanId"] == "2222222222222222"
    assert span["name"] == "provider_call"
    assert span["status"] == {"code": 1}
    start_ns = int(span["startTimeUnixNano"])
    end_ns = int(span["endTimeUnixNano"])
    assert end_ns - start_ns == 250 * 1_000_000

    attrs = _attr_map(span["attributes"])
    assert attrs["pulse.source"] == "sdk"
    assert attrs["pulse.kind"] == "llm_call"
    assert attrs["pulse.session_id"] == "session-123"
    assert attrs["gen_ai.provider.name"] == "openai"
    assert attrs["gen_ai.request.model"] == "gpt-4o-mini"
    assert attrs["gen_ai.response.model"] == "gpt-4o-mini-2024-07-18"
    assert attrs["gen_ai.response.id"] == "chatcmpl_123"
    assert attrs["gen_ai.response.finish_reasons"] == json.dumps(["stop"])
    assert attrs["gen_ai.usage.input_tokens"] == 10
    assert attrs["gen_ai.usage.output_tokens"] == 20
    assert attrs["pulse.cost_cents"] == 0.002
    assert attrs["pulse.output_text"] == "Hello"
    assert attrs["tenant"] == "acme"


def test_to_otlp_serializes_tool_span_with_parent() -> None:
    body = _to_otlp(
        [
            _sample_span(
                kind="tool_use",
                event_type="tool_request",
                parent_span_id="3333333333333333",
                tool_use_id="call_abc",
                tool_name="get_weather",
                tool_input={"city": "Berlin"},
            )
        ]
    )
    span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]

    assert span["name"] == "get_weather"
    assert span["parentSpanId"] == "3333333333333333"
    attrs = _attr_map(span["attributes"])
    assert attrs["pulse.tool.id"] == "call_abc"
    assert attrs["gen_ai.tool.name"] == "get_weather"
    assert attrs["pulse.tool.input"] == json.dumps({"city": "Berlin"})


def test_to_otlp_marks_error_spans_with_status_message() -> None:
    body = _to_otlp(
        [
            _sample_span(
                status="error",
                error={"name": "APIError", "message": "provider unavailable"},
            )
        ]
    )
    span = body["resourceSpans"][0]["scopeSpans"][0]["spans"][0]

    assert span["status"] == {"code": 2, "message": "provider unavailable"}
    attrs = _attr_map(span["attributes"])
    assert json.loads(attrs["pulse.error"]) == {
        "name": "APIError",
        "message": "provider unavailable",
    }


def test_send_spans_posts_otlp_json_to_v1_traces(monkeypatch) -> None:
    calls: Dict[str, Any] = {}

    class Response:
        ok = True
        status_code = 200
        text = "{}"

    def post(url: str, **kwargs: Any) -> Response:
        calls["url"] = url
        calls["kwargs"] = kwargs
        return Response()

    monkeypatch.setattr("pulse_sdk.transport.requests.post", post)

    send_spans("https://pulse.example/", "pulse_sk_test", [_sample_span()])

    assert calls["url"] == "https://pulse.example/v1/traces"
    assert calls["kwargs"]["headers"]["Authorization"] == "Bearer pulse_sk_test"
    body = json.loads(calls["kwargs"]["data"])
    assert len(body["resourceSpans"][0]["scopeSpans"][0]["spans"]) == 1


def test_send_spans_skips_empty_batches(monkeypatch) -> None:
    def post(url: str, **kwargs: Any) -> None:
        raise AssertionError("requests.post should not be called for empty batches")

    monkeypatch.setattr("pulse_sdk.transport.requests.post", post)

    send_spans("https://pulse.example", "pulse_sk_test", [])
