from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes.pipeline import CancelChecker, EventEmitter, ResearchNodes
from app.agents.state import ResearchState
from app.core.config import Settings
from app.providers.base import BaseLLMProvider, BaseSearchProvider


def build_research_graph(
    *,
    llm: BaseLLMProvider,
    search_provider: BaseSearchProvider,
    emit_event: EventEmitter | None = None,
    is_cancelled: CancelChecker | None = None,
    settings: Settings | None = None,
    resolve_dns_on_fetch: bool = True,
    checkpointer: Any | None = None,
):
    """Build and compile the controlled LangGraph research workflow."""
    nodes = ResearchNodes(
        llm=llm,
        search_provider=search_provider,
        emit_event=emit_event,
        is_cancelled=is_cancelled,
        settings=settings,
        resolve_dns_on_fetch=resolve_dns_on_fetch,
    )

    # Track repair attempts cleanly in generate_report
    async def generate_report_node(state: ResearchState) -> dict[str, Any]:
        validation = state.get("citation_validation", {})
        is_repair = bool(validation and not validation.get("is_valid", True))
        updates = await nodes.generate_report(state)
        if is_repair:
            updates["citation_fix_attempts"] = int(state.get("citation_fix_attempts", 0)) + 1
        return updates

    def route_after_cancel_check(next_node: str):
        def _router(state: ResearchState) -> str:
            if state.get("cancel_requested"):
                return "save_research_results"
            return next_node

        return _router

    def route_after_gaps(state: ResearchState) -> str:
        if state.get("cancel_requested"):
            return "save_research_results"
        if state.get("follow_up_queries"):
            return "generate_search_queries"
        return "generate_report"

    def route_after_validation(state: ResearchState) -> str:
        validation = state.get("citation_validation", {})
        attempts = int(state.get("citation_fix_attempts", 0))
        if not validation.get("is_valid", True) and attempts < 1:
            return "generate_report"
        return "save_research_results"

    builder = StateGraph(ResearchState)

    builder.add_node("understand_question", nodes.understand_question)
    builder.add_node("create_research_plan", nodes.create_research_plan)
    builder.add_node("generate_search_queries", nodes.generate_search_queries)
    builder.add_node("search_web", nodes.search_web)
    builder.add_node("deduplicate_sources", nodes.deduplicate_sources)
    builder.add_node("rank_sources", nodes.rank_sources)
    builder.add_node("extract_source_content", nodes.extract_source_content)
    builder.add_node("extract_evidence", nodes.extract_evidence)
    builder.add_node("evaluate_evidence", nodes.evaluate_evidence)
    builder.add_node("cross_check_claims", nodes.cross_check_claims)
    builder.add_node("identify_research_gaps", nodes.identify_research_gaps)
    builder.add_node("generate_report", generate_report_node)
    builder.add_node("validate_citations", nodes.validate_citations)
    builder.add_node("save_research_results", nodes.save_research_results)

    builder.add_edge(START, "understand_question")
    builder.add_conditional_edges(
        "understand_question",
        route_after_cancel_check("create_research_plan"),
        {
            "create_research_plan": "create_research_plan",
            "save_research_results": "save_research_results",
        },
    )
    builder.add_conditional_edges(
        "create_research_plan",
        route_after_cancel_check("generate_search_queries"),
        {
            "generate_search_queries": "generate_search_queries",
            "save_research_results": "save_research_results",
        },
    )
    builder.add_conditional_edges(
        "generate_search_queries",
        route_after_cancel_check("search_web"),
        {
            "search_web": "search_web",
            "save_research_results": "save_research_results",
        },
    )
    builder.add_conditional_edges(
        "search_web",
        route_after_cancel_check("deduplicate_sources"),
        {
            "deduplicate_sources": "deduplicate_sources",
            "save_research_results": "save_research_results",
        },
    )
    builder.add_edge("deduplicate_sources", "rank_sources")
    builder.add_edge("rank_sources", "extract_source_content")
    builder.add_conditional_edges(
        "extract_source_content",
        route_after_cancel_check("extract_evidence"),
        {
            "extract_evidence": "extract_evidence",
            "save_research_results": "save_research_results",
        },
    )
    builder.add_conditional_edges(
        "extract_evidence",
        route_after_cancel_check("evaluate_evidence"),
        {
            "evaluate_evidence": "evaluate_evidence",
            "save_research_results": "save_research_results",
        },
    )
    builder.add_edge("evaluate_evidence", "cross_check_claims")
    builder.add_conditional_edges(
        "cross_check_claims",
        route_after_cancel_check("identify_research_gaps"),
        {
            "identify_research_gaps": "identify_research_gaps",
            "save_research_results": "save_research_results",
        },
    )
    builder.add_conditional_edges(
        "identify_research_gaps",
        route_after_gaps,
        {
            "generate_search_queries": "generate_search_queries",
            "generate_report": "generate_report",
            "save_research_results": "save_research_results",
        },
    )
    builder.add_conditional_edges(
        "generate_report",
        route_after_cancel_check("validate_citations"),
        {
            "validate_citations": "validate_citations",
            "save_research_results": "save_research_results",
        },
    )
    builder.add_conditional_edges(
        "validate_citations",
        route_after_validation,
        {
            "generate_report": "generate_report",
            "save_research_results": "save_research_results",
        },
    )
    builder.add_edge("save_research_results", END)

    active_checkpointer = checkpointer if checkpointer is not None else MemorySaver()
    return builder.compile(checkpointer=active_checkpointer)
