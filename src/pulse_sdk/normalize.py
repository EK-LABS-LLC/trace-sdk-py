from __future__ import annotations

from typing import Optional

from .types import NormalizedResponse

try:
    from openai.types.chat import ChatCompletion
except Exception:
    ChatCompletion = object  # type: ignore

try:
    from anthropic.types import Message
except Exception:
    Message = object  # type: ignore


ANTHROPIC_STOP_REASON_MAP = {
    "end_turn": "stop",
    "max_tokens": "length",
    "stop_sequence": "stop",
    "tool_use": "tool_calls",
}


def normalize_openai_response(response: "ChatCompletion") -> NormalizedResponse:
    choice = response.choices[0] if response.choices else None
    content = getattr(choice.message, "content", None) if choice else None
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", None)
    output_tokens = getattr(usage, "completion_tokens", None)
    finish_reason = getattr(choice, "finish_reason", None)
    model = getattr(response, "model", "unknown")
    provider_id = getattr(response, "id", None)

    cost_cents = None
    cost_value = getattr(response, "cost", None)
    if isinstance(cost_value, (int, float)):
        cost_cents = cost_value * 100

    return NormalizedResponse(
        model=model,
        content=content if isinstance(content, str) else None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        finish_reason=finish_reason,
        cost_cents=cost_cents,
        provider_request_id=provider_id,
    )


def normalize_anthropic_response(response: "Message") -> NormalizedResponse:
    content_parts = []
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            text_value = getattr(block, "text", None)
            if text_value:
                content_parts.append(text_value)
    content = "".join(content_parts) if content_parts else None

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)

    stop_reason = getattr(response, "stop_reason", None)
    finish_reason = ANTHROPIC_STOP_REASON_MAP.get(stop_reason, stop_reason)
    model = getattr(response, "model", "unknown")

    return NormalizedResponse(
        model=model,
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        finish_reason=finish_reason,
    )
