from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResearchCreateRequest(BaseModel):
    project_id: UUID | None = None
    project_title: str | None = Field(default=None, max_length=200)
    query: str = Field(min_length=5, max_length=2000)
    context: str = Field(default="", max_length=4000)
    depth: Literal["quick", "standard", "deep"] = "standard"
    date_range: Literal["any", "last_week", "last_month", "last_year", "last_5_years"] = "any"
    source_preferences: list[str] = Field(default_factory=list, max_length=10)
    language: Literal["en", "bn"] = "en"


class ResearchPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    objective: str
    scope: str
    subquestions: list[dict[str, Any]]
    search_strategy: dict[str, Any]
    created_at: datetime


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    url: str
    canonical_url: str
    title: str
    publisher: str
    author: str | None
    published_at: str | None
    retrieved_at: datetime
    source_type: str
    extraction_status: str
    relevance_score: float
    relevance_note: str
    limitations: str
    raw_excerpt: str
    error_detail: str | None


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    source_id: UUID
    claim: str
    excerpt: str
    evidence_type: str
    claim_category: str
    relevance: str
    date_context: str
    limitations: str
    corroboration_status: str
    created_at: datetime


class ReportCitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    citation_number: int
    source_id: UUID
    evidence_id: UUID | None
    cited_claim: str
    source: SourceResponse | None = None
    evidence: EvidenceResponse | None = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    version: int
    title: str
    summary: str
    content: str
    structured_data: dict[str, Any]
    citation_validation: dict[str, Any]
    status: str
    created_at: datetime
    citations: list[ReportCitationResponse] = Field(default_factory=list)


class ResearchMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    role: str
    content: str
    citations: list[dict[str, Any]]
    created_at: datetime


class ResearchRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    user_id: UUID
    query: str
    context: str
    depth: str
    date_range: str
    source_preferences: list[str]
    language: str
    status: str
    current_stage: str
    retry_count: int
    cancel_requested: bool
    is_demo_mode: bool
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    plan: ResearchPlanResponse | None = None
    source_count: int = 0
    extracted_source_count: int = 0
    evidence_count: int = 0
    has_report: bool = False


class FollowUpRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


class FollowUpResponse(BaseModel):
    user_message: ResearchMessageResponse
    assistant_message: ResearchMessageResponse
