import re
from typing import Any, Dict, List

from pulse_sdk.otlp import traces_to_otlp_json
from pulse_sdk.trace import build_trace, extract_pulse_params
from pulse_sdk.transport import send_traces
from pulse_sdk.types import NormalizedResponse, Provider


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


def test_traces_to_otlp_json_emits_one_provider_span() -> None:
    trace = build_trace(
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Summarize OTLP JSON."}],
        },
        NormalizedResponse(
            model="gpt-4o-mini-2024-07-18",
            content="OTLP JSON carries telemetry as resourceSpans.",
            input_tokens=12,
            output_tokens=7,
            finish_reason="stop",
            cost_cents=0.04,
            provider_request_id="chatcmpl_123",
        ),
        Provider.OPENAI,
        latency_ms=125.4,
        session_id="session-123",
        metadata={
            "pulse.session.name": "SDK Tests",
            "pulse.trace.name": "OTLP conversion",
        },
    )

    body = traces_to_otlp_json([trace])

    resource_span = body["resourceSpans"][0]
    resource_attrs = _attr_map(resource_span["resource"]["attributes"])
    assert resource_attrs["service.name"] == "pulse-sdk-python"
    assert resource_attrs["telemetry.sdk.language"] == "python"

    scope_span = resource_span["scopeSpans"][0]
    assert scope_span["scope"]["name"] == "pulse-trace-sdk"
    assert len(scope_span["spans"]) == 1

    span = scope_span["spans"][0]
    assert re.fullmatch(r"[0-9a-f]{32}", span["traceId"])
    assert re.fullmatch(r"[0-9a-f]{16}", span["spanId"])
    assert span["traceId"] == trace["trace_id"]
    assert span["spanId"] == trace["span_id"]
    assert span["kind"] == 3
    assert int(span["startTimeUnixNano"]) <= int(span["endTimeUnixNano"])
    assert span["status"]["code"] == 1

    attrs = _attr_map(span["attributes"])
    assert attrs["pulse.source"] == "sdk"
    assert attrs["pulse.kind"] == "llm_call"
    assert attrs["pulse.event_type"] == "provider_request"
    assert attrs["pulse.session_id"] == "session-123"
    assert attrs["pulse.session.name"] == "SDK Tests"
    assert attrs["pulse.trace.name"] == "OTLP conversion"
    assert attrs["pulse.prompt.preview"] == "Summarize OTLP JSON."
    assert attrs["pulse.provider_request_id"] == "chatcmpl_123"
    assert attrs["pulse.cost_cents"] == 0.04
    assert attrs["gen_ai.provider.name"] == "openai"
    assert attrs["gen_ai.request.model"] == "gpt-4o-mini"
    assert attrs["gen_ai.response.model"] == "gpt-4o-mini-2024-07-18"
    assert attrs["gen_ai.usage.input_tokens"] == 12
    assert attrs["gen_ai.usage.output_tokens"] == 7


def test_traces_to_otlp_json_marks_error_spans() -> None:
    trace = build_trace(
        {"model": "claude-3-5-haiku-20241022", "messages": []},
        None,
        Provider.ANTHROPIC,
        latency_ms=25,
    )
    trace["error"] = {"name": "RuntimeError", "message": "provider failed"}

    span = traces_to_otlp_json([trace])["resourceSpans"][0]["scopeSpans"][0][
        "spans"
    ][0]

    assert span["status"]["code"] == 2
    assert span["status"]["message"] == "provider failed"
    assert span["events"][0]["name"] == "exception"
    event_attrs = _attr_map(span["events"][0]["attributes"])
    assert event_attrs["exception.type"] == "RuntimeError"
    assert event_attrs["exception.message"] == "provider failed"


def test_send_traces_posts_otlp_json_to_v1_traces(monkeypatch) -> None:
    trace = build_trace(
        {"model": "gpt-4o-mini", "prompt": "hello"},
        None,
        Provider.OPENAI,
        latency_ms=1,
    )
    calls: Dict[str, Any] = {}

    class Response:
        ok = True
        status_code = 202
        text = ""

    def post(url: str, **kwargs: Any) -> Response:
        calls["url"] = url
        calls["kwargs"] = kwargs
        return Response()

    monkeypatch.setattr("pulse_sdk.transport.requests.post", post)

    send_traces("https://pulse.example/", "pulse_sk_test", [trace])

    assert calls["url"] == "https://pulse.example/v1/traces"
    assert calls["kwargs"]["headers"]["Authorization"] == "Bearer pulse_sk_test"
    assert "resourceSpans" in calls["kwargs"]["json"]
    assert calls["kwargs"]["json"]["resourceSpans"][0]["scopeSpans"][0]["spans"][0][
        "traceId"
    ] == trace["trace_id"]


def test_extract_pulse_params_strips_display_name_kwargs() -> None:
    clean, session_id, metadata = extract_pulse_params(
        {
            "model": "gpt-4o-mini",
            "pulse_session_id": "session-abc",
            "pulse_session_name": "Support",
            "pulse_trace_name": "Refund answer",
            "pulse_metadata": {"custom": "value"},
        }
    )

    assert clean == {"model": "gpt-4o-mini"}
    assert session_id == "session-abc"
    assert metadata == {
        "pulse.session.name": "Support",
        "pulse.trace.name": "Refund answer",
        "custom": "value",
    }
