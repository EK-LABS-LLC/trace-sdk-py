from __future__ import annotations

import copy
import time
from typing import Any, Dict

from ..normalize import normalize_anthropic_response
from ..state import add_to_buffer, is_enabled
from ..trace import (
    build_error_trace,
    build_trace,
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

        start = time.perf_counter()
        try:
            response = original_create(**clean_payload)
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            trace = build_error_trace(
                request_payload,
                exc,
                Provider.ANTHROPIC,
                latency,
                session_id,
                metadata,
            )
            add_to_buffer(trace)
            raise

        latency = (time.perf_counter() - start) * 1000
        normalized = normalize_anthropic_response(response)
        trace = build_trace(
            request_payload,
            normalized,
            Provider.ANTHROPIC,
            latency,
            session_id,
            metadata,
        )
        add_to_buffer(trace)
        return response

    messages.create = wrapped_create  # type: ignore[assignment]
    return client
