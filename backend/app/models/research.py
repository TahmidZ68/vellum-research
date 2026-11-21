import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ResearchRun(Base):
    __tablename__ = "research_runs"
    __table_args__ = (
        Index("ix_research_runs_user_created", "user_id", "created_at"),
        Index("ix_research_runs_project_created", "project_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    depth: Mapped[str] = mapped_column(String(24), nullable=False, default="standard")
    date_range: Mapped[str] = mapped_column(String(64), nullable=False, default="any")
    source_preferences: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", index=True)
    current_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_demo_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user = relationship("User", back_populates="research_runs")
    project = relationship("ResearchProject", back_populates="runs")
    plan = relationship(
        "ResearchPlan", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )
    sources = relationship(
        "Source", back_populates="run", cascade="all, delete-orphan"
    )
    evidence_items = relationship(
        "Evidence", back_populates="run", cascade="all, delete-orphan"
    )
    reports = relationship(
        "Report", back_populates="run", cascade="all, delete-orphan"
    )
    messages = relationship(
        "ResearchMessage", back_populates="run", cascade="all, delete-orphan"
    )


class ResearchPlan(Base):
    __tablename__ = "research_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_runs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="")
    subquestions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    search_strategy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run = relationship("ResearchRun", back_populates="plan")


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        Index("ix_sources_run_canonical", "run_id", "canonical_url"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="Untitled Source")
    publisher: Mapped[str] = mapped_column(String(255), nullable=False, default="Unknown")
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="company")
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    relevance_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    limitations: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    run = relationship("ResearchRun", back_populates="sources")
    evidence_items = relationship(
        "Evidence", back_populates="source", cascade="all, delete-orphan"
    )
    citations = relationship(
        "ReportCitation", back_populates="source", cascade="all, delete-orphan"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False, default="company")
    claim_category: Mapped[str] = mapped_column(
        String(64), nullable=False, default="source_reported_claim"
    )
    relevance: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    date_context: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    limitations: Mapped[str] = mapped_column(Text, nullable=False, default="")
    corroboration_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="single_source"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run = relationship("ResearchRun", back_populates="evidence_items")
    source = relationship("Source", back_populates="evidence_items")
    citations = relationship(
        "ReportCitation", back_populates="evidence", cascade="all, delete-orphan"
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    citation_validation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="validated")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run = relationship("ResearchRun", back_populates="reports")
    citations = relationship(
        "ReportCitation", back_populates="report", cascade="all, delete-orphan"
    )


class ReportCitation(Base):
    __tablename__ = "report_citations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    citation_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cited_claim: Mapped[str] = mapped_column(Text, nullable=False, default="")

    report = relationship("Report", back_populates="citations")
    evidence = relationship("Evidence", back_populates="citations")
    source = relationship("Source", back_populates="citations")


class ResearchMessage(Base):
    __tablename__ = "research_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run = relationship("ResearchRun", back_populates="messages")
