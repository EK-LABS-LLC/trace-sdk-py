from __future__ import annotations

import json
from typing import List

import requests

from .types import Trace

DEFAULT_TIMEOUT = 10  # seconds


def send_traces(api_url: str, api_key: str, traces: List[Trace]) -> None:
    if not traces:
        return

    url = f"{api_url.rstrip('/')}/v1/traces/async"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        url, headers=headers, data=json.dumps(traces), timeout=DEFAULT_TIMEOUT
    )
    if not response.ok:
        raise RuntimeError(
            f"Pulse SDK: failed to send traces ({response.status_code}): {response.text}"
        )
