# pulse-trace-sdk

Official Python SDK for Pulse trace ingestion.

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
