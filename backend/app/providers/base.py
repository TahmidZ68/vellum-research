from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ProviderConfigurationError(RuntimeError):
    """Raised when a required search or LLM provider credential/setting is missing."""


class ProviderExecutionError(RuntimeError):
    """Raised when an external search or LLM provider request fails."""


@dataclass
class SearchResultItem:
    url: str
    title: str
    snippet: str
    publisher: str = "Unknown"
    published_at: str | None = None
    score: float = 0.0
    raw_content: str | None = None
    query: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchOptions:
    max_results: int = 8
    search_depth: str = "basic"
    date_range: str = "any"
    include_raw_content: bool = False


class BaseSearchProvider(ABC):
    """Abstract interface for web search providers."""

    provider_name: str = "base"

    @abstractmethod
    async def search(self, query: str, options: SearchOptions | None = None) -> list[SearchResultItem]:
        """Execute a web search and return normalized results."""

    @abstractmethod
    def normalize_results(self, raw_results: list[dict[str, Any]], query: str = "") -> list[SearchResultItem]:
        """Normalize provider-specific search payloads into SearchResultItem objects."""


class BaseLLMProvider(ABC):
    """Abstract interface for LLM text and structured JSON generation."""

    provider_name: str = "base"
    model_name: str = ""

    @abstractmethod
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a text completion."""

    @abstractmethod
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Generate a structured JSON object."""
