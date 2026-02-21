# pulse-trace-sdk

Python SDK for sending OpenAI/Anthropic traces to Pulse.

## Install

```bash
pip install pulse-trace-sdk
```

## Quick Start

```python
from openai import OpenAI
from pulse_sdk import init_pulse, observe, Provider

init_pulse({
    "api_key": "pulse_sk_...",
    "api_url": "http://localhost:3000",  # optional, defaults to localhost
})

client = observe(OpenAI(api_key="your-openai-key"), Provider.OPENAI)

client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
```

## Supported Providers

- OpenAI
- Anthropic

## Config

```python
init_pulse({
    "api_key": "pulse_sk_...",   # required
    "api_url": "http://localhost:3000",
    "batch_size": 10,
    "flush_interval": 5000,
    "enabled": True,
})
```

## Per-request Metadata

```python
client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hi"}],
    pulse_session_id="session-123",
    pulse_metadata={"feature": "chat"},
)
```

## API

- `init_pulse(config)`
- `observe(client, provider, options=None)`
- `flush_buffer()`
- `shutdown()`

The SDK batches traces and flushes automatically on shutdown.
