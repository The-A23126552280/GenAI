"""Thin wrapper around Groq's OpenAI-compatible chat API."""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from openai import OpenAI

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# Groq retires models regularly (llama-3.3-70b-versatile shut down on 2026-08-16).
# Check https://console.groq.com/docs/deprecations and change this, or set GROQ_MODEL in .env.
DEFAULT_MODEL = "openai/gpt-oss-120b"


def get_client(api_key: str) -> "OpenAI":
    from openai import OpenAI  # imported lazily so the pure-logic modules stay testable without it

    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)


def model_options(model: str) -> dict:
    """Extra request params for reasoning models.

    GPT-OSS spends hidden "reasoning" tokens before it writes the answer. "low" effort keeps
    replies fast and leaves the token budget for the answer itself (otherwise short calls such
    as the JSON profile extraction can come back empty).
    """
    if "gpt-oss" in model.lower():
        return {"extra_body": {"reasoning_effort": "low"}}
    return {}


def chat_stream(
    client: "OpenAI", model: str, messages: list[dict], temperature: float = 0.4, max_tokens: int = 1500
) -> Iterator[str]:
    """Yield the reply token-by-token (for st.write_stream)."""
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        **model_options(model),
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def chat_once(
    client: "OpenAI", model: str, messages: list[dict], temperature: float = 0.0, max_tokens: int = 600
) -> str:
    """Single non-streaming call, used for the profile-extraction step."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **model_options(model),
    )
    return response.choices[0].message.content or ""
