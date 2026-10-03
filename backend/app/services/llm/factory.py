from app.core.config import Settings
from app.services.llm.base import LLMProvider
from app.services.llm.mock import MockProvider
from app.services.llm.openai_compatible import OpenAICompatibleProvider


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockProvider(token_delay=0.01 if settings.app_env != "test" else 0.0)
    if settings.llm_api_key is None:
        raise RuntimeError("LLM_API_KEY is required when LLM_PROVIDER=openai_compatible")
    return OpenAICompatibleProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        timeout=settings.llm_timeout_seconds,
    )
