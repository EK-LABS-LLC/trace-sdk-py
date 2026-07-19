# pulse-trace-sdk

Official Python SDK for Pulse trace ingestion. The public `observe()` API records
supported LLM calls and sends them to Pulse as OTLP HTTP JSON at `POST /v1/traces` —
one `llm_call` span per provider request plus `tool_use` spans for tool calls, carrying
provider, model, token, cost, and session attributes.

## Install

```bash
pip install pulse-trace-sdk
```

## Quick Start

```python
from openai import OpenAI
from pulse_sdk import init_pulse, observe, Provider

init_pulse({"api_key": "pulse_sk_..."})

client = observe(OpenAI(api_key="your-openai-key"), Provider.OPENAI)

client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
)
```

## Docs

Full docs: https://www.usepulse.dev/docs/
