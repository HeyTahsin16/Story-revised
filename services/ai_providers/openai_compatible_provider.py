"""
Shared implementation for any OpenAI-compatible chat completions API.
Covers both OpenAI itself and xAI's Grok, which is intentionally
OpenAI-API-compatible (same request/response shape at a different
base_url) -- so one class serves both, differing only in base_url,
api_key, and default model.
"""
import asyncio

from services.ai_providers.base import AIProvider

OPENAI_DEFAULT_MAIN_MODEL = "gpt-5.5"
OPENAI_DEFAULT_FAST_MODEL = "gpt-5-mini"

GROK_DEFAULT_MAIN_MODEL = "grok-4.5"
GROK_DEFAULT_FAST_MODEL = "grok-4-1-fast-non-reasoning"
GROK_BASE_URL = "https://api.x.ai/v1"


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, api_key: str, model: str, base_url: str = None, display_name: str = "openai"):
        try:
            from openai import AsyncOpenAI, APIConnectionError, APIStatusError
        except ImportError as exc:
            raise RuntimeError(
                f"AI_PROVIDER is set to '{display_name}' but the openai package isn't "
                "installed. Run: pip install openai"
            ) from exc
        self._retry_errors = (APIConnectionError, APIStatusError)
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self._model = model

    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        last_exc = None
        for attempt in range(3):
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return response.choices[0].message.content or ""
            except self._retry_errors as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        raise last_exc
