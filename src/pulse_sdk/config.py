from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .types import PulseConfig


@dataclass(frozen=True)
class ResolvedConfig:
    api_key: str
    api_url: str
    batch_size: int
    flush_interval: int
    enabled: bool


DEFAULT_API_URL = "http://localhost:3000"
DEFAULT_BATCH_SIZE = 10
DEFAULT_FLUSH_INTERVAL = 5000  # ms
DEFAULT_ENABLED = True


class ConfigError(ValueError):
    """Raised when the user passes invalid configuration."""


def load_config(config: PulseConfig) -> ResolvedConfig:
    api_key = config.get("api_key")
    if not api_key:
        raise ConfigError("Pulse SDK: api_key is required")

    if not api_key.startswith("pulse_sk_"):
        raise ConfigError("Pulse SDK: api_key must start with 'pulse_sk_'")

    batch_size = int(config.get("batch_size", DEFAULT_BATCH_SIZE))
    if batch_size < 1 or batch_size > 100:
        raise ConfigError("Pulse SDK: batch_size must be between 1 and 100")

    flush_interval = int(config.get("flush_interval", DEFAULT_FLUSH_INTERVAL))
    if flush_interval < 1000:
        raise ConfigError("Pulse SDK: flush_interval must be at least 1000ms")

    api_url = config.get("api_url", DEFAULT_API_URL)
    enabled = bool(config.get("enabled", DEFAULT_ENABLED))

    return ResolvedConfig(
        api_key=api_key,
        api_url=api_url,
        batch_size=batch_size,
        flush_interval=flush_interval,
        enabled=enabled,
    )
