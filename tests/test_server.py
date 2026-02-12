import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from anthropic import Anthropic
from pydantic import BaseModel

from pulse_sdk import Provider, init_pulse, observe

load_dotenv()

PULSE_API_KEY = os.environ.get("PULSE_API_KEY")
if not PULSE_API_KEY:
    raise RuntimeError("PULSE_API_KEY is required for the test server")

init_pulse(
    {
        "api_key": PULSE_API_KEY,
        "api_url": os.environ.get("PULSE_API_URL", "http://localhost:3000"),
        "batch_size": 1,
        "flush_interval": 1000,
    }
)

app = FastAPI()


class RunRequest(BaseModel):
    provider: str
    session_id: Optional[str] = None


@app.get("/health")
def health() -> dict[str, bool]:
    return {
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


@app.post("/run")
def run_endpoint(request: RunRequest):
    try:
        result = run_provider(request.provider, request.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


def _call_openai(session_id: str | None = None):
    client = observe(OpenAI(api_key=os.environ.get("OPENAI_API_KEY")), Provider.OPENAI)
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": "Say 'test'"}],
        max_tokens=32,
        pulse_session_id=session_id,
    )
    return {
        "model": response.model,
        "content": response.choices[0].message.content,
    }


def _call_anthropic(session_id: str | None = None):
    client = observe(
        Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY")), Provider.ANTHROPIC
    )
    response = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022"),
        max_tokens=32,
        messages=[{"role": "user", "content": "Say 'test'"}],
        pulse_session_id=session_id,
    )

    return {
        "model": response.model,
        "content": response.content,
    }


def run_provider(provider_name: str, session_id: str | None = None):
    normalized = provider_name.strip().lower()
    if normalized == "openai":
        response = _call_openai(session_id=session_id)
    elif normalized == "anthropic":
        response = _call_anthropic(session_id=session_id)
    else:
        raise ValueError("provider must be 'openai' or 'anthropic'")
    return response


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("SDK_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("SDK_SERVER_PORT", "8080"))
    uvicorn.run(app, host=host, port=port, reload=False)
