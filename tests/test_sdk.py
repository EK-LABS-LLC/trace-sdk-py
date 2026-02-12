import os
import time
import uuid
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

import requests
import pytest

TEST_SERVER_URL = os.environ.get("TEST_SERVER_URL", "http://localhost:3001").rstrip("/")
TRACE_SERVICE_URL = os.environ.get("TRACE_SERVICE_URL", "http://localhost:3000").rstrip("/")
PULSE_API_KEY = os.environ.get("PULSE_API_KEY")


def _trace_field(trace: Dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in trace:
            return trace[name]
    return None


def wait_for_traces(delay_ms: int = 2000) -> None:
    time.sleep(max(delay_ms, 0) / 1000)


def get_traces(
    limit: Optional[int] = None,
    provider: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if limit:
        params["limit"] = limit
    if provider:
        params["provider"] = provider
    if session_id:
        params["session_id"] = session_id

    response = requests.get(
        f"{TRACE_SERVICE_URL}/v1/traces",
        params=params,
        headers={"Authorization": f"Bearer {PULSE_API_KEY}"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def get_test_server_health() -> Dict[str, bool]:
    response = requests.get(f"{TEST_SERVER_URL}/health", timeout=10)
    response.raise_for_status()
    data = response.json()
    return {
        "openai": bool(data.get("openai")),
        "anthropic": bool(data.get("anthropic")),
    }


def trigger_run(provider: str, *, session_id: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"provider": provider}
    if session_id:
        payload["session_id"] = session_id

    response = requests.post(
        f"{TEST_SERVER_URL}/run",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise AssertionError(f"Test server returned error: {data['error']}")
    return data


def find_trace(provider: str, session_id: str) -> Dict[str, Any]:
    traces_response = get_traces(provider=provider, session_id=session_id, limit=10)
    for trace in traces_response.get("traces", []):
        trace_provider = str(_trace_field(trace, "provider") or "").lower()
        trace_session = _trace_field(trace, "sessionId", "session_id")
        if trace_provider == provider and trace_session == session_id:
            return trace
    raise AssertionError(
        f"Did not find trace for provider={provider} session_id={session_id} "
        "in trace-service response"
    )


@pytest.fixture(scope="module")
def available_providers() -> Dict[str, bool]:
    try:
        return get_test_server_health()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Test server not reachable at {TEST_SERVER_URL}. Make sure it's running."
        ) from exc


def test_openai_completion_records_trace(available_providers: Dict[str, bool]) -> None:
    if not available_providers.get("openai"):
        pytest.skip("OpenAI not configured on test server")

    session_id = str(uuid.uuid4())
    trigger_run("openai", session_id=session_id)
    wait_for_traces()

    trace = find_trace("openai", session_id)
    assert _trace_field(trace, "sessionId", "session_id") == session_id
    assert str(_trace_field(trace, "provider")).lower() == "openai"


def test_anthropic_completion_records_trace(available_providers: Dict[str, bool]) -> None:
    if not available_providers.get("anthropic"):
        pytest.skip("Anthropic not configured on test server")

    session_id = str(uuid.uuid4())
    trigger_run("anthropic", session_id=session_id)
    wait_for_traces()

    trace = find_trace("anthropic", session_id)
    assert _trace_field(trace, "sessionId", "session_id") == session_id
    assert str(_trace_field(trace, "provider")).lower() == "anthropic"


def test_session_correlation_across_providers(available_providers: Dict[str, bool]) -> None:
    if not (available_providers.get("openai") and available_providers.get("anthropic")):
        pytest.skip("Both OpenAI and Anthropic must be configured for session test")

    session_id = str(uuid.uuid4())

    trigger_run("openai", session_id=session_id)
    trigger_run("anthropic", session_id=session_id)
    wait_for_traces()

    openai_trace = find_trace("openai", session_id)
    anthropic_trace = find_trace("anthropic", session_id)
    assert _trace_field(openai_trace, "sessionId", "session_id") == session_id
    assert _trace_field(anthropic_trace, "sessionId", "session_id") == session_id
