from __future__ import annotations

from typing import Dict, Optional

ModelPricing = Dict[str, float]

MODEL_PRICING: Dict[str, ModelPricing] = {
    "gpt-5.1": {"input": 125, "output": 1000},
    "gpt-5": {"input": 150, "output": 1000},
    "gpt-5-mini": {"input": 90, "output": 400},
    "gpt-5-nano": {"input": 20, "output": 100},
    "gpt-5.1-chat-latest": {"input": 125, "output": 1000},
    "gpt-5-chat-latest": {"input": 150, "output": 1000},
    "gpt-5.1-codex-max": {"input": 250, "output": 1250},
    "gpt-5.1-codex": {"input": 125, "output": 600},
    "gpt-5-codex": {"input": 145, "output": 600},
    "gpt-5.1-codex-mini": {"input": 40, "output": 160},
    "codex-mini-latest": {"input": 40, "output": 160},
    "gpt-5-pro": {"input": 250, "output": 1200},
    "gpt-5-search-api": {"input": 400, "output": 1600},
    "gpt-4.1": {"input": 250, "output": 1000},
    "gpt-4.1-mini": {"input": 100, "output": 400},
    "gpt-4.1-nano": {"input": 15, "output": 60},
    "gpt-4o": {"input": 250, "output": 1000},
    "gpt-4o-2024-05-13": {"input": 250, "output": 1000},
    "gpt-4o-mini": {"input": 15, "output": 60},
    "gpt-4o-mini-search-preview": {"input": 500, "output": 2000},
    "gpt-4o-search-preview": {"input": 1000, "output": 4000},
    "gpt-realtime": {"input": 500, "output": 2000},
    "gpt-realtime-mini": {"input": 250, "output": 1000},
    "gpt-4o-realtime-preview": {"input": 500, "output": 2000},
    "gpt-4o-mini-realtime-preview": {"input": 15, "output": 60},
    "gpt-audio": {"input": 250, "output": 1000},
    "gpt-audio-mini": {"input": 60, "output": 250},
    "gpt-4o-audio-preview": {"input": 250, "output": 1000},
    "gpt-4o-mini-audio-preview": {"input": 15, "output": 60},
    "o1": {"input": 1500, "output": 6000},
    "o1-pro": {"input": 1800, "output": 7200},
    "o1-mini": {"input": 350, "output": 1400},
    "o3-pro": {"input": 1500, "output": 6000},
    "o3": {"input": 600, "output": 2400},
    "o3-mini": {"input": 200, "output": 800},
    "o3-deep-research": {"input": 2500, "output": 10000},
    "o4-mini": {"input": 300, "output": 1200},
    "o4-mini-deep-research": {"input": 500, "output": 2000},
    "computer-use-preview": {"input": 500, "output": 0},
    "gpt-image-1": {"input": 5000, "output": 0},
    "gpt-image-1-mini": {"input": 2000, "output": 0},
    "gpt-4-turbo": {"input": 1000, "output": 3000},
    "gpt-3.5-turbo": {"input": 50, "output": 150},
    "claude-opus-4-5-20251101": {"input": 500, "output": 2500},
    "claude-opus-4-1-20250805": {"input": 1500, "output": 7500},
    "claude-opus-4-20250514": {"input": 1500, "output": 7500},
    "claude-sonnet-4-5-20250929": {"input": 300, "output": 1500},
    "claude-sonnet-4-20250514": {"input": 300, "output": 1500},
    "claude-3-7-sonnet-20250219": {"input": 300, "output": 1500},
    "claude-3-sonnet-20240229": {"input": 300, "output": 1500},
    "claude-3-5-sonnet-20241022": {"input": 300, "output": 1500},
    "claude-haiku-4-5-20251001": {"input": 100, "output": 500},
    "claude-3-5-haiku-20241022": {"input": 80, "output": 400},
    "claude-3-haiku-20240307": {"input": 25, "output": 125},
    "claude-3-opus-20240229": {"input": 1500, "output": 7500},
}

MODEL_ALIASES: Dict[str, str] = {
    "gpt-5.1-latest": "gpt-5.1",
    "gpt-5-latest": "gpt-5",
    "gpt-5-mini-latest": "gpt-5-mini",
    "gpt-5-nano-latest": "gpt-5-nano",
    "gpt-5.1-codex-latest": "gpt-5.1-codex",
    "gpt-5-codex-latest": "gpt-5-codex",
    "gpt-5.1-codex-mini-latest": "gpt-5.1-codex-mini",
    "gpt-4.1-latest": "gpt-4.1",
    "gpt-4.1-mini-latest": "gpt-4.1-mini",
    "gpt-4.1-nano-latest": "gpt-4.1-nano",
    "gpt-4o-2024-11-20": "gpt-4o",
    "gpt-4o-2024-08-06": "gpt-4o",
    "gpt-4o-mini-2024-07-18": "gpt-4o-mini",
    "gpt-4-turbo-2024-04-09": "gpt-4-turbo",
    "gpt-4-turbo-preview": "gpt-4-turbo",
    "gpt-3.5-turbo-0125": "gpt-3.5-turbo",
    "gpt-3.5-turbo-1106": "gpt-3.5-turbo",
    "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
    "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
    "claude-3-sonnet": "claude-3-sonnet-20240229",
    "claude-3.0-sonnet": "claude-3-sonnet-20240229",
    "claude-3-5-haiku": "claude-3-5-haiku-20241022",
    "claude-3.5-haiku": "claude-3-5-haiku-20241022",
    "claude-3-opus": "claude-3-opus-20240229",
    "claude-opus-4-5": "claude-opus-4-5-20251101",
    "claude-opus-4.5": "claude-opus-4-5-20251101",
    "claude-opus-4-1": "claude-opus-4-1-20250805",
    "claude-opus-4.1": "claude-opus-4-1-20250805",
    "claude sonnet": "claude-3-sonnet-20240229",
}


def _resolve_model(model: str) -> Optional[ModelPricing]:
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    alias = MODEL_ALIASES.get(model)
    if alias and alias in MODEL_PRICING:
        return MODEL_PRICING[alias]
    return None


def calculate_cost(
    model: str, input_tokens: int, output_tokens: int
) -> Optional[float]:
    pricing = _resolve_model(model)
    if not pricing:
        return None

    cost = 0.0
    cost += (input_tokens * pricing["input"]) / 1_000_000
    cost += (output_tokens * pricing["output"]) / 1_000_000
    return round(cost, 6)
