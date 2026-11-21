import pytest

from app.agents.nodes.pipeline import ResearchNodes
from app.core.config import Settings
from app.providers.base import ProviderConfigurationError
from app.providers.llm_gemini import GeminiProvider
from app.providers.llm_mock import MockLLMProvider
from app.providers.search_mock import MockSearchProvider
from app.providers.search_tavily import TavilySearchProvider
from app.services.citation_validator import validate_report_citations


def test_provider_configuration_errors_for_missing_keys() -> None:
    with pytest.raises(ProviderConfigurationError) as exc1:
        TavilySearchProvider(api_key="")
    assert "TAVILY_API_KEY" in str(exc1.value)

    with pytest.raises(ProviderConfigurationError) as exc2:
        GeminiProvider(api_key="", model_name="gemini-2.5-flash")
    assert "GEMINI_API_KEY" in str(exc2.value)


def test_tavily_result_normalization() -> None:
    provider = TavilySearchProvider(api_key="tvly-test-key")
    raw = [
        {
            "url": "https://www.reuters.com/tech/ai-automation-2026",
            "title": "AI Automation Spending Grows",
            "content": "Spending increased 30% year-over-year.",
            "published_date": "2026-01-12",
            "score": 0.91,
        }
    ]
    items = provider.normalize_results(raw, query="ai spending")
    assert len(items) == 1
    assert items[0].publisher == "reuters.com"
    assert items[0].score == 0.91
    assert items[0].published_at == "2026-01-12"


@pytest.mark.asyncio
async def test_deduplicate_and_rank_sources_nodes() -> None:
    nodes = ResearchNodes(
        llm=MockLLMProvider(),
        search_provider=MockSearchProvider(),
        settings=Settings(ALLOW_MOCK_PROVIDERS=True),
        resolve_dns_on_fetch=False,
    )
    state = {
        "research_depth": "quick",
        "source_preferences": ["academic"],
        "search_results": [
            {
                "url": "https://example.edu/paper?utm_source=x",
                "title": "Study A",
                "snippet": "Academic findings",
                "publisher": "example.edu",
                "score": 0.7,
                "metadata": {"source_type": "academic"},
            },
            {
                "url": "https://example.edu/paper/",
                "title": "Study A Duplicate",
                "snippet": "Academic findings",
                "publisher": "example.edu",
                "score": 0.85,
                "metadata": {"source_type": "academic"},
            },
            {
                "url": "http://127.0.0.1/local-trap",
                "title": "SSRF Trap",
                "snippet": "Should be dropped",
                "publisher": "127.0.0.1",
                "score": 0.99,
            },
        ],
    }
    dedup_update = await nodes.deduplicate_sources(state)
    deduped = dedup_update["deduplicated_sources"]
    assert len(deduped) == 1
    assert deduped[0]["score"] == 0.85

    rank_update = await nodes.rank_sources({**state, **dedup_update})
    selected = rank_update["selected_sources"]
    assert len(selected) == 1
    assert selected[0]["citation_number"] == 1
    assert selected[0]["source_type"] == "academic"


def test_citation_validator_detects_invented_citations_and_urls() -> None:
    sources = {
        1: {
            "title": "Primary Docs",
            "publisher": "docs.example.org",
            "url": "https://docs.example.org/overview",
            "canonical_url": "https://docs.example.org/overview",
            "source_type": "primary",
            "raw_excerpt": "42% adoption in 2025.",
        }
    }
    valid_md = "## Key Findings\nEnterprise adoption reached 42% [1].\n"
    res_ok, final_ok = validate_report_citations(valid_md, sources)
    assert res_ok.is_valid is True
    assert res_ok.cited_numbers == [1]
    assert "## References" in final_ok
    assert "https://docs.example.org/overview" in final_ok

    bad_md = "## Key Findings\nFake stat [99] from https://invented.example.net/fake.\n"
    res_bad, _ = validate_report_citations(bad_md, sources)
    assert res_bad.is_valid is False
    assert 99 in res_bad.invalid_numbers
    assert "https://invented.example.net/fake" in res_bad.ungrounded_urls


@pytest.mark.asyncio
async def test_langgraph_citation_auto_repair_pass() -> None:
    from app.agents.graph import build_research_graph

    class RepairingLLM(MockLLMProvider):
        def __init__(self) -> None:
            self.report_calls = 0

        async def generate_json(self, system_prompt: str, user_prompt: str, **kwargs):
            if "TASK:generate_report" in user_prompt:
                self.report_calls += 1
                if self.report_calls == 1:
                    return {
                        "title": "Draft With Invalid Citation",
                        "summary": "Initial draft",
                        "markdown_report": "## Key Findings\nUnsupported claim [999].",
                        "key_findings": [],
                    }
                return {
                    "title": "Repaired Report",
                    "summary": "Fixed draft",
                    "markdown_report": "## Key Findings\nSupported claim [1].",
                    "key_findings": ["Supported claim [1]."],
                }
            return await super().generate_json(system_prompt, user_prompt, **kwargs)

    llm = RepairingLLM()
    graph = build_research_graph(
        llm=llm,
        search_provider=MockSearchProvider(),
        settings=Settings(ALLOW_MOCK_PROVIDERS=True),
        resolve_dns_on_fetch=False,
    )
    final_state = await graph.ainvoke(
        {
            "user_id": "u1",
            "project_id": "p1",
            "run_id": "r1",
            "original_question": "Test citation repair",
            "research_context": "",
            "research_depth": "quick",
            "date_range": "any",
            "source_preferences": [],
            "language": "en",
            "search_results": [],
            "executed_queries": [],
            "errors": [],
            "retry_count": 0,
            "max_iterations": 1,
            "citation_fix_attempts": 0,
            "cancel_requested": False,
        },
        config={"configurable": {"thread_id": "repair-test"}},
    )
    assert llm.report_calls == 2
    assert final_state["citation_validation"]["is_valid"] is True
    assert final_state["final_status"] == "completed"

