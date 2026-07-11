"""W3C/OTel-compatible trace and span ID generation.

OTLP requires trace IDs of 16 bytes and span IDs of 8 bytes, serialized as
lowercase hex (32 and 16 characters). All-zero IDs are invalid.
"""

from __future__ import annotations

import secrets


def _random_hex(byte_length: int) -> str:
    value = secrets.token_hex(byte_length)
    while value == "0" * byte_length * 2:
        value = secrets.token_hex(byte_length)
    return value


def generate_trace_id() -> str:
    """Generates a 32-character hex OTel trace ID."""
    return _random_hex(16)


def generate_span_id() -> str:
    """Generates a 16-character hex OTel span ID."""
    return _random_hex(8)
