# Pulse Python SDK

Python client helpers for Pulse trace ingestion. Wrap your LLM provider SDK (OpenAI, Anthropic) and Pulse automatically captures trace metadata and ships it to your trace-service instance.

## Installation

From the repo root:

```bash
cd sdk-py
pip install -e .
```

## Usage

```python
from openai import OpenAI
from pulse_sdk import init_pulse, observe, Provider

init_pulse({
    "api_key": "pulse_sk_...",
    "api_url": "http://localhost:3000",
})

client = OpenAI(api_key="your-openai-key")
observed = observe(client, Provider.OPENAI)

response = observed.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello Pulse"}],
    pulse_session_id="session-123",
    pulse_metadata={"feature": "chat"},
)
```

To instrument Anthropic:

```python
from anthropic import Anthropic
from pulse_sdk import observe, Provider

anthropic_client = Anthropic(api_key="anthropic-key")
observe(anthropic_client, Provider.ANTHROPIC)

anthropic_client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=300,
    messages=[{"role": "user", "content": "Summarize"}],
)
```

## API

- `init_pulse(config)` – configure API URL, key, batch size, and flush interval. Starts a background worker that periodically flushes traces.
- `observe(client, provider, options=None)` – wraps the provider SDK and returns the same client instance instrumented with tracing.
- `flush_buffer()` – (optional) force-send buffered traces, useful before process shutdown.
- `shutdown()` – stop the background worker and clear buffers.

### Config options

```python
init_pulse({
    "api_key": "pulse_sk_...",     # required
    "api_url": "https://api.example.com",  # default http://localhost:3000
    "batch_size": 10,               # flush when buffer hits this size
    "flush_interval": 5000,         # milliseconds between automatic flushes
    "enabled": True,                # set False to disable tracing
})
```

### Pulse specific metadata

All `chat.completions.create` / `messages.create` calls support:

- `pulse_session_id` – associate traces with a session.
- `pulse_metadata` – arbitrary dictionary merged into trace metadata.

## Requirements

- Python 3.10+
- `requests`
- Corresponding provider SDK (`openai`, `anthropic`) for the helpers you use.

## Tests

```bash
uv run pytest
```

### Live integration check

To manually exercise the SDK against real providers, run:

```bash
uv run python tests/test_server.py openai
uv run python tests/test_server.py anthropic
```

Set `PULSE_API_KEY` and the relevant provider key (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`) before running. The script makes a single completion request and relies on `observe()` to push traces to your trace-service instance.
