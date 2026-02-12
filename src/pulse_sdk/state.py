from __future__ import annotations

import threading
import time
from typing import List

from .config import ResolvedConfig
from .transport import send_traces
from .types import Trace

_config: ResolvedConfig | None = None
_buffer: List[Trace] = []
_buffer_lock = threading.Lock()
_flush_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None


def set_config(config: ResolvedConfig) -> None:
    global _config
    _config = config


def get_config() -> ResolvedConfig:
    if _config is None:
        raise RuntimeError("Pulse SDK: init_pulse() must be called before use")
    return _config


def is_enabled() -> bool:
    return bool(_config and _config.enabled)


def add_to_buffer(trace: Trace) -> None:
    if not is_enabled():
        return

    with _buffer_lock:
        _buffer.append(trace)
        threshold = _config.batch_size if _config else 0
        should_flush = len(_buffer) >= threshold > 0

    if should_flush:
        flush_buffer()


def flush_buffer() -> None:
    if not is_enabled():
        return

    traces: List[Trace]
    with _buffer_lock:
        if not _buffer:
            return
        traces = list(_buffer)
        _buffer.clear()

    cfg = get_config()
    try:
        send_traces(cfg.api_url, cfg.api_key, traces)
    except Exception as exc:
        print(f"Pulse SDK: failed to send traces: {exc}")


def _flush_loop(interval_ms: int, stop_event: threading.Event) -> None:
    interval = max(interval_ms / 1000.0, 1.0)
    while not stop_event.wait(interval):
        flush_buffer()


def start_flush_worker() -> None:
    global _flush_thread, _stop_event

    if not is_enabled():
        return

    stop_flush_worker()
    cfg = get_config()
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_flush_loop,
        args=(cfg.flush_interval, stop_event),
        name="pulse-sdk-flush",
        daemon=True,
    )
    _stop_event = stop_event
    _flush_thread = thread
    thread.start()


def stop_flush_worker() -> None:
    global _flush_thread, _stop_event

    if _stop_event:
        _stop_event.set()
    if _flush_thread and _flush_thread.is_alive():
        _flush_thread.join(timeout=1)
    _stop_event = None
    _flush_thread = None


def reset_state() -> None:
    global _buffer
    stop_flush_worker()
    with _buffer_lock:
        _buffer = []
