from __future__ import annotations

import copy
import time
from typing import Any, Dict

from ..normalize import normalize_openai_response
from ..state import add_to_buffer, is_enabled
from ..trace import build_error_trace, build_trace, extract_pulse_params, resolve_trace_metadata
from ..types import ObserveOptions, Provider


class OpenAIIntegrationError(RuntimeError):
    pass


def observe_openai(client: Any, provider: Provider, options: ObserveOptions | None = None) -> Any:
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

        start = time.perf_counter()
        try:
            response = original_create(**clean_payload)
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            trace = build_error_trace(
                request_payload,
                exc,
                provider,
                latency,
                session_id,
                metadata,
            )
            add_to_buffer(trace)
            raise

        latency = (time.perf_counter() - start) * 1000
        normalized = normalize_openai_response(response)
        trace = build_trace(
            request_payload,
            normalized,
            provider,
            latency,
            session_id,
            metadata,
        )
        add_to_buffer(trace)
        return response

    completions.create = wrapped_create  # type: ignore[assignment]
    return client
