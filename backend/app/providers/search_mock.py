from typing import Any

from app.providers.base import BaseSearchProvider, SearchOptions, SearchResultItem


class MockSearchProvider(BaseSearchProvider):
    """
    Deterministic mock search provider for offline testing and clearly-labeled demo mode.
    Never impersonates live web search results.
    """

    provider_name = "mock"

    def __init__(self, custom_results: list[dict[str, Any]] | None = None) -> None:
        self.custom_results = custom_results

    async def search(
        self, query: str, options: SearchOptions | None = None
    ) -> list[SearchResultItem]:
        opts = options or SearchOptions()
        if self.custom_results is not None:
            return self.normalize_results(self.custom_results[: opts.max_results], query=query)

        sample_catalog = [
            {
                "url": "https://docs.example.org/research-overview",
                "title": f"[SAMPLE DATA] Industry Overview & Adoption Trends: {query[:60]}",
                "content": (
                    "Sample documentation report indicating 42% enterprise workflow automation "
                    "adoption in 2025, while noting limited survey coverage among small businesses. "
                    "Primary drivers include customer support triage, document processing, and "
                    "internal knowledge retrieval pipelines deployed across mid-to-large teams."
                ),
                "published_date": "2025-11-10",
                "score": 0.92,
                "publisher": "docs.example.org",
                "source_type": "primary",
            },
            {
                "url": "https://journal.example.com/market-analysis-2026",
                "title": f"[SAMPLE DATA] Market Pricing & Competitor Landscape for {query[:50]}",
                "content": (
                    "Sample journalism analysis observing tiered subscription pricing ($49-$499/mo) "
                    "alongside custom enterprise retainers, and highlighting slower SMB uptake due to integration cost. "
                    "Buyers increasingly request transparent usage limits, human-in-the-loop checkpoints, "
                    "and verifiable source attribution before committing to annual contracts."
                ),
                "published_date": "2026-02-14",
                "score": 0.88,
                "publisher": "journal.example.com",
                "source_type": "journalism",
            },
            {
                "url": "https://research.example.edu/benchmarks-study",
                "title": f"[SAMPLE DATA] Empirical Evaluation & Limitations Study: {query[:50]}",
                "content": (
                    "Sample academic benchmark showing 28% efficiency gains in controlled pilots, "
                    "contradicting vendor claims of 70% immediate cost reduction. "
                    "Authors note that maintenance overhead, edge-case handling, and QA review "
                    "account for the gap between laboratory benchmarks and production rollouts."
                ),
                "published_date": "2026-01-20",
                "score": 0.85,
                "publisher": "research.example.edu",
                "source_type": "academic",
            },
            {
                "url": "https://vendor.example.io/automation-suite",
                "title": f"[SAMPLE DATA] Commercial Vendor Platform Benchmarks: {query[:50]}",
                "content": (
                    "Sample promotional case study claiming up to 70% cost reduction for mid-market clients; "
                    "methodology and sample size are not disclosed. The vendor offers turnkey onboarding "
                    "and managed integrations, though independent verification of baseline metrics is absent."
                ),
                "published_date": "2025-08-03",
                "score": 0.74,
                "publisher": "vendor.example.io",
                "source_type": "promotional",
            },
            {
                "url": "https://policy.example.gov/digital-economy-brief",
                "title": f"[SAMPLE DATA] Public Sector Digital Readiness Brief: {query[:50]}",
                "content": (
                    "Sample institutional brief highlighting regulatory compliance, data localization, "
                    "and talent availability as decisive factors for regional adoption. "
                    "Public agencies recommend clear audit trails and open standards for procurement."
                ),
                "published_date": "2026-03-01",
                "score": 0.81,
                "publisher": "policy.example.gov",
                "source_type": "government",
            },
        ]
        return self.normalize_results(sample_catalog[: opts.max_results], query=query)

    def normalize_results(
        self, raw_results: list[dict[str, Any]], query: str = ""
    ) -> list[SearchResultItem]:
        items: list[SearchResultItem] = []
        for entry in raw_results:
            items.append(
                SearchResultItem(
                    url=str(entry["url"]),
                    title=str(entry.get("title", "Sample Source")),
                    snippet=str(entry.get("content", "")),
                    publisher=str(entry.get("publisher", "example.org")),
                    published_at=entry.get("published_date"),
                    score=float(entry.get("score", 0.75)),
                    raw_content=str(entry.get("raw_content") or entry.get("content", "")),
                    query=query,
                    metadata={
                        "provider": self.provider_name,
                        "is_mock": True,
                        "source_type": entry.get("source_type", "company"),
                    },
                )
            )
        return items
