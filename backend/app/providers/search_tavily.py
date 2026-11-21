from typing import Any
from urllib.parse import urlparse

import httpx

from app.providers.base import (
    BaseSearchProvider,
    ProviderConfigurationError,
    ProviderExecutionError,
    SearchOptions,
    SearchResultItem,
)


class TavilySearchProvider(BaseSearchProvider):
    """Tavily web search provider adapter."""

    provider_name = "tavily"
    ENDPOINT = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: int = 20,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        if not self.api_key:
            raise ProviderConfigurationError(
                "TAVILY_API_KEY is missing. Configure TAVILY_API_KEY in your .env file "
                "or enable mock mode (SEARCH_PROVIDER=mock, ALLOW_MOCK_PROVIDERS=true) for demo runs."
            )
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @staticmethod
    def _map_days(date_range: str) -> int | None:
        mapping = {
            "last_week": 7,
            "last_month": 30,
            "last_year": 365,
            "last_5_years": 1825,
        }
        return mapping.get(date_range)

    async def search(
        self, query: str, options: SearchOptions | None = None
    ) -> list[SearchResultItem]:
        opts = options or SearchOptions()
        payload: dict[str, Any] = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced" if opts.search_depth == "advanced" else "basic",
            "max_results": max(1, min(opts.max_results, 20)),
            "include_answer": False,
            "include_raw_content": opts.include_raw_content,
        }
        days = self._map_days(opts.date_range)
        if days is not None:
            payload["days"] = days

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                transport=self.transport,
            ) as client:
                response = await client.post(self.ENDPOINT, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderExecutionError(
                f"Tavily search returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderExecutionError(f"Tavily search request failed: {exc}") from exc

        raw_results = data.get("results", [])
        if not isinstance(raw_results, list):
            return []
        return self.normalize_results(raw_results, query=query)

    def normalize_results(
        self, raw_results: list[dict[str, Any]], query: str = ""
    ) -> list[SearchResultItem]:
        normalized: list[SearchResultItem] = []
        for item in raw_results:
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            hostname = (urlparse(url).hostname or "unknown").lower()
            if hostname.startswith("www."):
                hostname = hostname[4:]
            title = str(item.get("title") or hostname).strip()
            snippet = str(item.get("content") or item.get("snippet") or "").strip()
            published_at = item.get("published_date") or item.get("published_at")
            raw_content = item.get("raw_content")
            try:
                score = float(item.get("score") or 0.5)
            except (TypeError, ValueError):
                score = 0.5

            normalized.append(
                SearchResultItem(
                    url=url,
                    title=title,
                    snippet=snippet,
                    publisher=hostname,
                    published_at=str(published_at) if published_at else None,
                    score=max(0.0, min(score, 1.0)),
                    raw_content=str(raw_content) if raw_content else None,
                    query=query,
                    metadata={"provider": self.provider_name},
                )
            )
        return normalized
