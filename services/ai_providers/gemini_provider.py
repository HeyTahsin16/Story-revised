"""Google Gemini provider, via the current (GA) google-genai SDK."""
import asyncio

from services.ai_providers.base import AIProvider

# Current as of the models available when this was written -- override via
# AI_MODEL_MAIN / AI_MODEL_FAST if Google ships something newer by the time
# you're reading this.
DEFAULT_MAIN_MODEL = "gemini-3.6-flash"
DEFAULT_FAST_MODEL = "gemini-3.5-flash-lite"


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        try:
            from google import genai
            from google.genai import errors as genai_errors
        except ImportError as exc:
            raise RuntimeError(
                "AI_PROVIDER is set to 'gemini' but the google-genai package isn't "
                "installed. Run: pip install google-genai"
            ) from exc
        self._retry_error = genai_errors.APIError  # covers both ServerError and ClientError
        self._client = genai.Client(api_key=api_key)
        self._model = model
        # Learned once per process: does this model/account accept
        # thinking_budget=0? If rejected, stop asking -- see
        # _generate_with_thinking_fallback for why re-trying an unsupported
        # param on every call wastes a request each time, which matters a
        # lot against a small quota.
        self._thinking_disable_supported = True

    @staticmethod
    def _is_quota_error(exc) -> bool:
        return getattr(exc, "status", None) == "RESOURCE_EXHAUSTED"

    async def complete(self, system: str, user: str, max_tokens: int) -> str:
        """
        Retries transient failures with backoff, same as any other provider
        -- EXCEPT quota/rate-limit errors (RESOURCE_EXHAUSTED), which are
        deliberately NOT retried here at all. This isn't a hypothetical
        concern: a free-tier quota of 20 requests/day was measured being
        exhausted within minutes, driven by this exact call retrying a
        doomed request. A quota error -- especially a small daily cap --
        will not resolve itself in the couple of seconds a backoff would
        wait, and retrying anyway just spends more of an already-exhausted
        quota for zero benefit. The scheduler is responsible for a much
        longer cooldown before attempting a failing guild again at all;
        see cogs/scheduler_cog.py's consecutive-failure backoff.
        """
        last_exc = None
        for attempt in range(3):
            try:
                text = await self._generate_with_thinking_fallback(system, user, max_tokens)
                if text:
                    return text
                last_exc = RuntimeError("Gemini returned an empty response after retries")
            except self._retry_error as exc:
                if self._is_quota_error(exc):
                    print(f"[gemini_provider] quota/rate limit hit ({exc!r}) -- not retrying, a short wait won't fix this")
                    raise
                last_exc = exc
                print(f"[gemini_provider] API error on attempt {attempt + 1}/3: {exc!r}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
        raise last_exc

    async def _generate_with_thinking_fallback(self, system: str, user: str, max_tokens: int) -> str:
        """
        Tries with thinking disabled first, to maximize the budget available
        for actual visible prose (see the README's Gemini "thinking" models
        note for why that matters). Falls back to the model's own default
        thinking behavior if that's rejected or comes back empty -- but only
        until we've learned, once, whether thinking_budget=0 is even
        supported by this model; after that we stop spending an extra
        request re-discovering the same answer on every single call, which
        -- again -- matters a lot against a small quota. A quota error
        specifically skips the fallback attempt entirely, since it would
        hit the exact same quota wall regardless of thinking config.
        """
        if self._thinking_disable_supported:
            try:
                text = await self._try_generate(system, user, max_tokens, disable_thinking=True)
                if text:
                    return text
            except self._retry_error as exc:
                if self._is_quota_error(exc):
                    raise
                self._thinking_disable_supported = False
                print(f"[gemini_provider] thinking_budget=0 rejected ({exc!r}), disabling that override for the rest of this process")

        return await self._try_generate(system, user, max_tokens, disable_thinking=False)

    async def _try_generate(self, system: str, user: str, max_tokens: int, disable_thinking: bool) -> str:
        config = {"system_instruction": system, "max_output_tokens": max_tokens}
        if disable_thinking:
            config["thinking_config"] = {"thinking_budget": 0}
        response = await self._client.aio.models.generate_content(
            model=self._model, contents=user, config=config
        )
        return response.text or ""
