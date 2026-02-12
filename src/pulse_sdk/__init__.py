from __future__ import annotations

from .config import load_config
from .providers import observe_anthropic, observe_openai
from .state import (
    flush_buffer,
    reset_state,
    set_config,
    start_flush_worker,
    stop_flush_worker,
)
from .types import ObserveOptions, Provider, PulseConfig


def init_pulse(config: PulseConfig) -> None:
    resolved = load_config(config)
    set_config(resolved)
    start_flush_worker()


def shutdown() -> None:
    stop_flush_worker()
    reset_state()


def observe(client, provider: Provider, options: ObserveOptions | None = None):
    if provider in (Provider.OPENAI, Provider.OPENROUTER):
        return observe_openai(client, provider, options)
    if provider == Provider.ANTHROPIC:
        return observe_anthropic(client, options)
    raise ValueError(f"Unsupported provider: {provider}")


__all__ = [
    "init_pulse",
    "shutdown",
    "observe",
    "flush_buffer",
    "Provider",
    "ObserveOptions",
]
