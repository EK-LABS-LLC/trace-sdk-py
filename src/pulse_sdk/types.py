from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, TypedDict


class Provider(str, Enum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"


class TraceStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class Trace(TypedDict, total=False):
    trace_id: str
    timestamp: str
    provider: str
    model_requested: str
    model_used: Optional[str]
    provider_request_id: Optional[str]
    request_body: Dict[str, Any]
    response_body: Dict[str, Any]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    output_text: Optional[str]
    finish_reason: Optional[str]
    status: str
    error: Dict[str, Any]
    cost_cents: Optional[float]
    latency_ms: int
    session_id: Optional[str]
    metadata: Dict[str, Any]


class PulseConfig(TypedDict, total=False):
    api_key: str
    api_url: str
    batch_size: int
    flush_interval: int
    enabled: bool


@dataclass
class ObserveOptions:
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class NormalizedResponse:
    model: str
    content: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    finish_reason: Optional[str]
    cost_cents: Optional[float] = None
    provider_request_id: Optional[str] = None
