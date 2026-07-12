from types import SimpleNamespace
from uuid import uuid4

from pulse_sdk.config import ResolvedConfig
from pulse_sdk.providers.openai import observe_openai
from pulse_sdk.spans import (
    MAX_PAYLOAD_BYTES,
    build_tool_request_spans,
    compact_payload,
    correlate_tool_results,
)
from pulse_sdk.state import set_config
from pulse_sdk.types import Provider


def test_compact_payload_caps_utf8_preview_by_bytes() -> None:
    payload = "\N{GRINNING FACE}" * MAX_PAYLOAD_BYTES

    compacted = compact_payload(payload)

    assert compacted["truncated"] is True
    assert compacted["originalBytes"] == MAX_PAYLOAD_BYTES * 4
    assert len(compacted["preview"].encode("utf-8")) <= MAX_PAYLOAD_BYTES


def test_tool_results_are_correlated_only_once() -> None:
    client_id = str(uuid4())
    session_id = str(uuid4())
    tool_id = str(uuid4())
    build_tool_request_spans(
        provider=Provider.OPENAI,
        client_id=client_id,
        trace_id="1" * 32,
        session_id=session_id,
        parent_span_id="2" * 16,
        tool_calls=[{"id": tool_id}],
    )
    result = [{"id": tool_id, "response": "sunny"}]

    trace_id, first_matches = correlate_tool_results(
        Provider.OPENAI, client_id, session_id, result
    )
    duplicate_trace_id, duplicate_matches = correlate_tool_results(
        Provider.OPENAI, client_id, session_id, result
    )

    assert trace_id == "1" * 32
    assert first_matches[0]["status"] == "matched"
    assert duplicate_trace_id is None
    assert duplicate_matches == []


def test_chat_telemetry_failure_does_not_hide_successful_response(monkeypatch) -> None:
    response = object()
    create = lambda **kwargs: response
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    set_config(
        ResolvedConfig(
            api_key="pulse_sk_test",
            api_url="http://localhost:3000",
            batch_size=100,
            flush_interval=5000,
            enabled=True,
        )
    )
    monkeypatch.setattr(
        "pulse_sdk.providers.openai.normalize_openai_response",
        lambda value: (_ for _ in ()).throw(ValueError("bad telemetry")),
    )
    observe_openai(client, Provider.OPENAI)

    assert client.chat.completions.create(model="test") is response


def test_responses_telemetry_failure_does_not_hide_successful_response(
    monkeypatch,
) -> None:
    response = object()
    create = lambda **kwargs: response
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        responses=SimpleNamespace(create=create),
    )
    set_config(
        ResolvedConfig(
            api_key="pulse_sk_test",
            api_url="http://localhost:3000",
            batch_size=100,
            flush_interval=5000,
            enabled=True,
        )
    )
    monkeypatch.setattr(
        "pulse_sdk.providers.openai._normalize_responses_response",
        lambda value, request: (_ for _ in ()).throw(ValueError("bad telemetry")),
    )
    observe_openai(client, Provider.OPENAI)

    assert client.responses.create(model="test") is response
