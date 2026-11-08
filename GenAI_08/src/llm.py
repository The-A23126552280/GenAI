import os
import time
import logging
from typing import Any

from litellm import completion
from litellm.exceptions import RateLimitError

logger = logging.getLogger(__name__)


def get_llm_response(
    messages: list[dict[str, str]],
    max_retries: int = 5,
    **kwargs: Any,
) -> str:
    """Call the configured LLM via LiteLLM with robust rate-limit handling.

    Default model (Nov 2026): qwen/qwen3.8-27b on Groq free tier.
    Override with LLM_PROVIDER / LLM_MODEL_NAME env vars.
    """
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    # qwen-2.5-32b was deprecated Apr 2025. Use a currently available model.
    model = os.getenv("LLM_MODEL_NAME", "qwen/qwen3.8-27b")
    full_model = f"{provider}/{model}"
    api_key = os.getenv(f"{provider.upper()}_API_KEY")

    for attempt in range(max_retries):
        try:
            response = completion(
                model=full_model,
                messages=messages,
                api_key=api_key,
                **kwargs,
            )
            return response.choices[0].message.content
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            # Prefer Retry-After header when present
            wait_time = 15.0
            headers = getattr(e, "headers", None) or {}
            retry_after = headers.get("Retry-After") or headers.get("retry-after")
            if retry_after is not None:
                try:
                    wait_time = float(retry_after)
                except (TypeError, ValueError):
                    pass
            else:
                # Exponential backoff with light jitter, capped at 60s
                wait_time = min(90.0, (2**attempt) * 10) + (attempt * 1.0)

            logger.warning(
                "Rate limit hit (attempt %d/%d). Waiting %.1fs. Error: %s",
                attempt + 1,
                max_retries,
                wait_time,
                str(e)[:200],
            )
            time.sleep(wait_time)

    # Unreachable, but satisfies type checkers
    raise RuntimeError("Exhausted retries without raising")
