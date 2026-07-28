"""Anthropic (Claude) provider -- the original/default provider."""
import asyncio

from services.ai_providers.base import AIProvider

DEFAULT_MAIN_MODEL = "claude-sonnet-5"
DEFAULT_FAST_MODEL = "claude-haiku-4-5-20251001"


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        try:
            from anthropic import AsyncAnthropic, APIConnectionError, APIStatusError
        except ImportError as exc:
            raise RuntimeError(
                "AI_PROVIDER is set to 'anthropic' but the anthropic package isn't "
                "installed. Run: pip install anthropic"
            ) from exc
        self._retry_errors = (APIConnectionError, APIStatusError)
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        last_exc = None
        for attempt in range(3):
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                return "".join(block.text for block in response.content if block.type == "text")
            except self._retry_errors as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        raise last_exc
