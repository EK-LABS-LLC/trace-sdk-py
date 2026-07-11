from __future__ import annotations

import copy
import time
import uuid
from typing import Any, Dict

from ..ids import generate_trace_id
from ..normalize import normalize_anthropic_response
from ..spans import (
    build_provider_span,
    build_tool_request_spans,
    build_tool_result_spans,
    correlate_tool_results,
    resolve_session_id,
)
from ..state import add_to_buffer, is_enabled
from ..trace import (
    current_timestamp,
    extract_pulse_params,
    resolve_trace_metadata,
)
from ..types import ObserveOptions, Provider


class AnthropicIntegrationError(RuntimeError):
    pass


def observe_anthropic(client: Any, options: ObserveOptions | None = None) -> Any:
    try:
        import anthropic  # noqa: F401
    except ImportError as exc:
        raise AnthropicIntegrationError(
            "anthropic package is required to observe Anthropic clients"
        ) from exc

    messages = getattr(client, "messages", None)
    if messages is None or not hasattr(messages, "create"):
        raise AnthropicIntegrationError("Client is missing messages.create")

    client_id = str(uuid.uuid4())
    original_create = messages.create

    def wrapped_create(*args: Any, **kwargs: Any):
        if not is_enabled():
            return original_create(*args, **kwargs)

        if args:
            return original_create(*args, **kwargs)

        clean_payload, pulse_session_id, pulse_metadata = extract_pulse_params(kwargs)
        request_payload: Dict[str, Any] = copy.deepcopy(clean_payload)

        observe_session = options.session_id if options else None
        observe_metadata = options.metadata if options else None
        session_id, metadata = resolve_trace_metadata(
            observe_session,
            observe_metadata,
            pulse_session_id,
            pulse_metadata,
        )
        session_id = resolve_session_id(session_id, client_id)
        result_trace_id, result_matches = correlate_tool_results(
            Provider.ANTHROPIC,
            client_id,
            session_id,
            _extract_tool_results(request_payload),
        )
        trace_id = result_trace_id or generate_trace_id()
        # Tool results were produced before this request, so record them up
        # front rather than after the provider responds.
        for span in build_tool_result_spans(trace_id, session_id, result_matches):
            add_to_buffer(span)

        started_at = current_timestamp()
        start = time.perf_counter()
        try:
            response = original_create(**clean_payload)
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            add_to_buffer(
                build_provider_span(
                    trace_id=trace_id,
                    session_id=session_id,
                    provider=Provider.ANTHROPIC,
                    request=request_payload,
                    response=None,
                    started_at=started_at,
                    latency_ms=latency,
                    status="error",
                    error={"name": exc.__class__.__name__, "message": str(exc)},
                    metadata=metadata,
                )
            )
            raise

        latency = (time.perf_counter() - start) * 1000
        normalized = normalize_anthropic_response(response)
        provider_span = build_provider_span(
            trace_id=trace_id,
            session_id=session_id,
            provider=Provider.ANTHROPIC,
            request=request_payload,
            response=normalized,
            started_at=started_at,
            latency_ms=latency,
            status="success",
            metadata=metadata,
        )
        add_to_buffer(provider_span)
        for span in build_tool_request_spans(
            provider=Provider.ANTHROPIC,
            client_id=client_id,
            trace_id=trace_id,
            session_id=session_id,
            parent_span_id=provider_span["span_id"],
            tool_calls=_extract_tool_calls(response),
        ):
            add_to_buffer(span)
        return response

    messages.create = wrapped_create  # type: ignore[assignment]
    return client


def _extract_tool_calls(response: Any) -> list[dict[str, Any]]:
    calls = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "id", None):
            calls.append(
                {
                    "id": getattr(block, "id"),
                    "name": getattr(block, "name", None),
                    "input": getattr(block, "input", None),
                }
            )
    return calls


def _extract_tool_results(request: Dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for message in request.get("messages", []) or []:
        if not isinstance(message, dict):
            continue
        for block in message.get("content", []) or []:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and block.get("tool_use_id")
            ):
                results.append({"id": block["tool_use_id"], "response": block.get("content")})
    return results
