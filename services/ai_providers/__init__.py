"""
Provider factory: maps a provider name string ("anthropic", "gemini",
"openai", "grok") to a constructed AIProvider, using that provider's own
sensible default model for the given role ("main" or "fast") unless the
person overrode it with AI_MODEL_MAIN / AI_MODEL_FAST.

This is the only file that needs to change to add a fifth provider later:
add the implementation module, then one branch here.
"""
import config
from services.ai_providers.base import AIProvider
from services.ai_providers.anthropic_provider import (
    AnthropicProvider,
    DEFAULT_MAIN_MODEL as _ANTHROPIC_MAIN,
    DEFAULT_FAST_MODEL as _ANTHROPIC_FAST,
)
from services.ai_providers.gemini_provider import (
    GeminiProvider,
    DEFAULT_MAIN_MODEL as _GEMINI_MAIN,
    DEFAULT_FAST_MODEL as _GEMINI_FAST,
)
from services.ai_providers.openai_compatible_provider import (
    OpenAICompatibleProvider,
    OPENAI_DEFAULT_MAIN_MODEL,
    OPENAI_DEFAULT_FAST_MODEL,
    GROK_DEFAULT_MAIN_MODEL,
    GROK_DEFAULT_FAST_MODEL,
    GROK_BASE_URL,
)

SUPPORTED_PROVIDERS = ("anthropic", "gemini", "openai", "grok")

# Which env var each provider reads its API key from -- used both here and
# by config.validate_config() so only the key(s) for providers actually in
# use are required.
PROVIDER_API_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "grok": "XAI_API_KEY",
}


def build_provider(provider_name: str, role: str) -> AIProvider:
    """role is "main" or "fast" -- selects which of a provider's two default
    models applies when AI_MODEL_MAIN / AI_MODEL_FAST isn't set."""
    name = (provider_name or "anthropic").strip().lower()
    is_main = role == "main"
    override = config.AI_MODEL_MAIN if is_main else config.AI_MODEL_FAST

    if name == "anthropic":
        model = override or (_ANTHROPIC_MAIN if is_main else _ANTHROPIC_FAST)
        return AnthropicProvider(api_key=config.ANTHROPIC_API_KEY, model=model)

    if name == "gemini":
        model = override or (_GEMINI_MAIN if is_main else _GEMINI_FAST)
        return GeminiProvider(api_key=config.GOOGLE_API_KEY, model=model)

    if name == "openai":
        model = override or (OPENAI_DEFAULT_MAIN_MODEL if is_main else OPENAI_DEFAULT_FAST_MODEL)
        return OpenAICompatibleProvider(api_key=config.OPENAI_API_KEY, model=model, display_name="openai")

    if name == "grok":
        model = override or (GROK_DEFAULT_MAIN_MODEL if is_main else GROK_DEFAULT_FAST_MODEL)
        return OpenAICompatibleProvider(
            api_key=config.XAI_API_KEY, model=model, base_url=GROK_BASE_URL, display_name="grok"
        )

    raise ValueError(f"Unknown AI provider {provider_name!r}. Supported: {', '.join(SUPPORTED_PROVIDERS)}")
