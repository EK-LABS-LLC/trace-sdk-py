from __future__ import annotations

import copy
import time
import uuid
from typing import Any, Dict

from ..ids import generate_trace_id
from ..normalize import normalize_openai_response
from ..spans import (
    build_provider_span,
    build_tool_request_spans,
    build_tool_result_spans,
    correlate_tool_results,
    parse_jsonish,
    resolve_session_id,
)
from ..state import add_to_buffer, is_enabled
from ..trace import (
    current_timestamp,
    extract_pulse_params,
    resolve_trace_metadata,
)
from ..types import ObserveOptions, Provider


class OpenAIIntegrationError(RuntimeError):
    pass


def observe_openai(
    client: Any, provider: Provider, options: ObserveOptions | None = None
) -> Any:
    if provider not in (Provider.OPENAI, Provider.OPENROUTER):
        raise ValueError("Provider must be openai or openrouter for observe_openai")

    try:
        import openai  # noqa: F401  # ensure dependency is available
    except ImportError as exc:
        raise OpenAIIntegrationError(
            "openai package is required to observe OpenAI clients"
        ) from exc

    chat = getattr(client, "chat", None)
    completions = getattr(chat, "completions", None)
    if completions is None or not hasattr(completions, "create"):
        raise OpenAIIntegrationError("Client is missing chat.completions.create")

    client_id = str(uuid.uuid4())
    original_create = completions.create

    def wrapped_create(*args: Any, **kwargs: Any):
        if not is_enabled():
            return original_create(*args, **kwargs)

        if args:
            # openai-python uses keyword-only API. Fall back if user passed args.
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
            provider, client_id, session_id, _extract_chat_tool_results(request_payload)
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
                    provider=provider,
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
        normalized = normalize_openai_response(response)
        provider_span = build_provider_span(
            trace_id=trace_id,
            session_id=session_id,
            provider=provider,
            request=request_payload,
            response=normalized,
            started_at=started_at,
            latency_ms=latency,
            status="success",
            metadata=metadata,
        )
        add_to_buffer(provider_span)
        for span in build_tool_request_spans(
            provider=provider,
            client_id=client_id,
            trace_id=trace_id,
            session_id=session_id,
            parent_span_id=provider_span["span_id"],
            tool_calls=_extract_chat_tool_calls(response),
        ):
            add_to_buffer(span)
        return response

    completions.create = wrapped_create  # type: ignore[assignment]

    responses = getattr(client, "responses", None)
    if responses is not None and hasattr(responses, "create"):
        original_responses_create = responses.create

        def wrapped_responses_create(*args: Any, **kwargs: Any):
            if not is_enabled() or args:
                return original_responses_create(*args, **kwargs)

            clean_payload, pulse_session_id, pulse_metadata = extract_pulse_params(kwargs)
            request_payload = copy.deepcopy(clean_payload)
            observe_session = options.session_id if options else None
            observe_metadata = options.metadata if options else None
            session_id, metadata = resolve_trace_metadata(
                observe_session, observe_metadata, pulse_session_id, pulse_metadata
            )
            session_id = resolve_session_id(session_id, client_id)
            result_trace_id, result_matches = correlate_tool_results(
                provider, client_id, session_id, _extract_responses_tool_results(request_payload)
            )
            trace_id = result_trace_id or generate_trace_id()
            # Tool results were produced before this request, so record them
            # up front rather than after the provider responds.
            for span in build_tool_result_spans(trace_id, session_id, result_matches):
                add_to_buffer(span)

            started_at = current_timestamp()
            start = time.perf_counter()
            try:
                response = original_responses_create(**clean_payload)
            except Exception as exc:
                latency = (time.perf_counter() - start) * 1000
                add_to_buffer(
                    build_provider_span(
                        trace_id=trace_id,
                        session_id=session_id,
                        provider=provider,
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
            normalized = _normalize_responses_response(response, request_payload)
            provider_span = build_provider_span(
                trace_id=trace_id,
                session_id=session_id,
                provider=provider,
                request=request_payload,
                response=normalized,
                started_at=started_at,
                latency_ms=latency,
                status="success",
                metadata=metadata,
            )
            add_to_buffer(provider_span)
            for span in build_tool_request_spans(
                provider=provider,
                client_id=client_id,
                trace_id=trace_id,
                session_id=session_id,
                parent_span_id=provider_span["span_id"],
                tool_calls=_extract_responses_tool_calls(response),
            ):
                add_to_buffer(span)
            return response

        responses.create = wrapped_responses_create  # type: ignore[assignment]
    return client


def _extract_chat_tool_calls(response: Any) -> list[dict[str, Any]]:
    calls = []
    for choice in getattr(response, "choices", []) or []:
        message = getattr(choice, "message", None)
        for call in getattr(message, "tool_calls", []) or []:
            function = getattr(call, "function", None)
            calls.append(
                {
                    "id": getattr(call, "id"),
                    "name": getattr(function, "name", None),
                    "input": parse_jsonish(getattr(function, "arguments", None)),
                }
            )
    return [call for call in calls if call.get("id")]


def _extract_chat_tool_results(request: Dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for message in request.get("messages", []) or []:
        if isinstance(message, dict) and message.get("role") == "tool" and message.get("tool_call_id"):
            results.append({"id": message["tool_call_id"], "response": message.get("content")})
    return results


def _extract_responses_tool_calls(response: Any) -> list[dict[str, Any]]:
    calls = []
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", None)
        if item_type == "function_call" and getattr(item, "call_id", None):
            calls.append(
                {
                    "id": getattr(item, "call_id"),
                    "name": getattr(item, "name", None),
                    "input": parse_jsonish(getattr(item, "arguments", None)),
                }
            )
        elif isinstance(item_type, str) and item_type.endswith("_call") and getattr(item, "id", None):
            calls.append({"id": getattr(item, "id"), "name": item_type, "input": item})
    return calls


def _extract_responses_tool_results(request: Dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": item["call_id"], "response": item.get("output")}
        for item in request.get("input", []) or []
        if isinstance(item, dict)
        and item.get("type") == "function_call_output"
        and item.get("call_id")
    ]


def _normalize_responses_response(response: Any, request: Dict[str, Any]):
    from ..types import NormalizedResponse

    usage = getattr(response, "usage", None)
    status = getattr(response, "status", None)
    incomplete = getattr(response, "incomplete_details", None)
    finish_reason = None
    if status == "incomplete" and isinstance(getattr(incomplete, "reason", None), str):
        finish_reason = incomplete.reason
    elif isinstance(status, str):
        finish_reason = status
    return NormalizedResponse(
        model=str(getattr(response, "model", request.get("model", "unknown"))),
        content=getattr(response, "output_text", None),
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        finish_reason=finish_reason,
        provider_request_id=getattr(response, "id", None),
    )
