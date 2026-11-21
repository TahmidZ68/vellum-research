from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_NAME: str = "Vellum Research"
    APP_SECRET_KEY: str = "dev-insecure-secret-key-change-in-production"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "sqlite+aiosqlite:///./open_research_agent.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    TASK_QUEUE_MODE: Literal["arq", "inline"] = "inline"

    JWT_SECRET_KEY: str = "dev-insecure-jwt-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    LLM_PROVIDER: Literal["gemini", "openai_compatible", "mock"] = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    SEARCH_PROVIDER: Literal["tavily", "mock"] = "tavily"
    TAVILY_API_KEY: str = ""

    ALLOW_MOCK_PROVIDERS: bool = False

    FRONTEND_URL: str = "http://localhost:5173"
    BACKEND_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    MAX_SEARCH_ITERATIONS: int = 2
    MAX_EXTRACTION_CONCURRENCY: int = 4
    EXTRACTION_TIMEOUT_SECONDS: int = 12
    MAX_EXTRACTION_BYTES: int = 1_500_000
    MAX_REDIRECTS: int = 3

    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RESEARCH_RUNS_PER_USER_PER_DAY: int = 30

    # Configurable research depth limits
    DEPTH_QUICK_SUBQUESTIONS: int = 3
    DEPTH_QUICK_SOURCES: int = 5
    DEPTH_STANDARD_SUBQUESTIONS: int = 5
    DEPTH_STANDARD_SOURCES: int = 12
    DEPTH_DEEP_SUBQUESTIONS: int = 8
    DEPTH_DEEP_SOURCES: int = 25

    @field_validator("GEMINI_MODEL")
    @classmethod
    def validate_gemini_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("GEMINI_MODEL cannot be empty.")
        return cleaned

    @field_validator("OPENAI_MODEL")
    @classmethod
    def validate_openai_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("OPENAI_MODEL cannot be empty.")
        return cleaned

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    def get_depth_limits(self, depth: str) -> tuple[int, int]:
        """Return (max_subquestions, max_sources) for the given depth tier."""
        mapping = {
            "quick": (self.DEPTH_QUICK_SUBQUESTIONS, self.DEPTH_QUICK_SOURCES),
            "standard": (self.DEPTH_STANDARD_SUBQUESTIONS, self.DEPTH_STANDARD_SOURCES),
            "deep": (self.DEPTH_DEEP_SUBQUESTIONS, self.DEPTH_DEEP_SOURCES),
        }
        return mapping.get(depth, mapping["standard"])

    def get_provider_diagnostics(self) -> dict[str, object]:
        """Return non-sensitive provider configuration status for API/UI diagnostics."""
        llm_configured = False
        llm_guidance = ""
        if self.LLM_PROVIDER == "gemini":
            llm_configured = bool(self.GEMINI_API_KEY.strip())
            if not llm_configured:
                llm_guidance = (
                    "GEMINI_API_KEY is not set. Add GEMINI_API_KEY to .env or switch "
                    "LLM_PROVIDER=openai_compatible (or LLM_PROVIDER=mock with "
                    "ALLOW_MOCK_PROVIDERS=true for clearly labeled demo mode)."
                )
        elif self.LLM_PROVIDER == "openai_compatible":
            llm_configured = bool(self.OPENAI_API_KEY.strip())
            if not llm_configured:
                llm_guidance = (
                    "OPENAI_API_KEY is not set. Add OPENAI_API_KEY and OPENAI_BASE_URL "
                    "to .env to use an OpenAI-compatible model."
                )
        elif self.LLM_PROVIDER == "mock":
            llm_configured = self.ALLOW_MOCK_PROVIDERS
            llm_guidance = (
                "Mock LLM provider is active. Outputs are clearly labeled as sample data."
                if llm_configured
                else "Set ALLOW_MOCK_PROVIDERS=true to permit the demo mock LLM provider."
            )

        search_configured = False
        search_guidance = ""
        if self.SEARCH_PROVIDER == "tavily":
            search_configured = bool(self.TAVILY_API_KEY.strip())
            if not search_configured:
                search_guidance = (
                    "TAVILY_API_KEY is not set. Add TAVILY_API_KEY to .env for live web search, "
                    "or set SEARCH_PROVIDER=mock with ALLOW_MOCK_PROVIDERS=true for demo runs."
                )
        elif self.SEARCH_PROVIDER == "mock":
            search_configured = self.ALLOW_MOCK_PROVIDERS
            search_guidance = (
                "Mock search provider is active. Results are clearly labeled as sample sources."
                if search_configured
                else "Set ALLOW_MOCK_PROVIDERS=true to permit the demo mock search provider."
            )

        return {
            "llm_provider": self.LLM_PROVIDER,
            "llm_model": (
                self.GEMINI_MODEL
                if self.LLM_PROVIDER == "gemini"
                else self.OPENAI_MODEL
                if self.LLM_PROVIDER == "openai_compatible"
                else "mock-analyst-v1"
            ),
            "llm_configured": llm_configured,
            "llm_guidance": llm_guidance,
            "search_provider": self.SEARCH_PROVIDER,
            "search_configured": search_configured,
            "search_guidance": search_guidance,
            "allow_mock_providers": self.ALLOW_MOCK_PROVIDERS,
            "is_demo_mode": (
                self.LLM_PROVIDER == "mock" or self.SEARCH_PROVIDER == "mock"
            )
            and self.ALLOW_MOCK_PROVIDERS,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
