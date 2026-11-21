from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    # Identifiers & input config
    user_id: str
    project_id: str
    run_id: str
    original_question: str
    research_context: str
    research_depth: str
    date_range: str
    source_preferences: list[str]
    language: str
    is_demo_mode: bool

    # Planning & discovery
    question_analysis: dict[str, Any]
    research_plan: dict[str, Any]
    subquestions: list[dict[str, Any]]
    search_queries: list[str]
    executed_queries: list[str]
    search_results: list[dict[str, Any]]

    # Sources & extraction
    deduplicated_sources: list[dict[str, Any]]
    selected_sources: list[dict[str, Any]]
    extracted_documents: list[dict[str, Any]]

    # Evidence & cross-checking
    evidence_records: list[dict[str, Any]]
    identified_contradictions: list[dict[str, Any]]
    corroborated_claims: list[str]
    research_gaps: list[str]
    follow_up_queries: list[str]

    # Synthesis & validation
    generated_report: dict[str, Any]
    citation_validation: dict[str, Any]
    citation_fix_attempts: int

    # Execution control
    current_stage: str
    errors: list[str]
    retry_count: int
    max_iterations: int
    cancel_requested: bool
    final_status: str
