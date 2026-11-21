from app.core.config import Settings, get_settings
from app.providers.base import BaseLLMProvider, BaseSearchProvider, ProviderConfigurationError
from app.providers.llm_gemini import GeminiProvider
from app.providers.llm_mock import MockLLMProvider
from app.providers.llm_openai import OpenAICompatibleProvider
from app.providers.search_mock import MockSearchProvider
from app.providers.search_tavily import TavilySearchProvider


def get_search_provider(settings: Settings | None = None) -> BaseSearchProvider:
    cfg = settings or get_settings()
    if cfg.SEARCH_PROVIDER == "tavily":
        return TavilySearchProvider(api_key=cfg.TAVILY_API_KEY)
    if cfg.SEARCH_PROVIDER == "mock":
        if not cfg.ALLOW_MOCK_PROVIDERS:
            raise ProviderConfigurationError(
                "SEARCH_PROVIDER=mock requires ALLOW_MOCK_PROVIDERS=true. "
                "Mock results are never silently substituted for live search."
            )
        return MockSearchProvider()
    raise ProviderConfigurationError(f"Unsupported SEARCH_PROVIDER: {cfg.SEARCH_PROVIDER}")


def get_llm_provider(settings: Settings | None = None) -> BaseLLMProvider:
    cfg = settings or get_settings()
    if cfg.LLM_PROVIDER == "gemini":
        return GeminiProvider(api_key=cfg.GEMINI_API_KEY, model_name=cfg.GEMINI_MODEL)
    if cfg.LLM_PROVIDER == "openai_compatible":
        return OpenAICompatibleProvider(
            api_key=cfg.OPENAI_API_KEY,
            model_name=cfg.OPENAI_MODEL,
            base_url=cfg.OPENAI_BASE_URL,
        )
    if cfg.LLM_PROVIDER == "mock":
        if not cfg.ALLOW_MOCK_PROVIDERS:
            raise ProviderConfigurationError(
                "LLM_PROVIDER=mock requires ALLOW_MOCK_PROVIDERS=true."
            )
        return MockLLMProvider()
    raise ProviderConfigurationError(f"Unsupported LLM_PROVIDER: {cfg.LLM_PROVIDER}")
