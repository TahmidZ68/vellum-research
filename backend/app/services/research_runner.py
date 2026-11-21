import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.graph import build_research_graph
from app.agents.state import ResearchState
from app.core.config import Settings, get_settings
from app.models.research import (
    Evidence,
    Report,
    ReportCitation,
    ResearchPlan,
    ResearchRun,
    Source,
)
from app.providers.base import BaseLLMProvider, BaseSearchProvider
from app.providers.factory import get_llm_provider, get_search_provider
from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)


async def execute_research_run(
    run_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    llm: BaseLLMProvider | None = None,
    search_provider: BaseSearchProvider | None = None,
    settings: Settings | None = None,
    resolve_dns_on_fetch: bool = True,
) -> None:
    """Execute a research run end-to-end, persisting plan, sources, evidence, report, and citations."""
    cfg = settings or get_settings()

    async with session_factory() as db:
        result = await db.execute(select(ResearchRun).where(ResearchRun.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            logger.error("Research run %s not found.", run_id)
            return

        if run.cancel_requested:
            run.status = "cancelled"
            run.current_stage = "cancelled"
            run.completed_at = datetime.now(UTC)
            await db.commit()
            await event_bus.publish(run_id, "run_cancelled", "cancelled", "Research run cancelled.")
            return

        run.status = "running"
        run.current_stage = "initializing"
        run.started_at = datetime.now(UTC)
        run.error_message = None
        await db.commit()

        initial_state: ResearchState = {
            "user_id": str(run.user_id),
            "project_id": str(run.project_id),
            "run_id": str(run.id),
            "original_question": run.query,
            "research_context": run.context,
            "research_depth": run.depth,
            "date_range": run.date_range,
            "source_preferences": list(run.source_preferences or []),
            "language": run.language,
            "is_demo_mode": run.is_demo_mode,
            "search_results": [],
            "executed_queries": [],
            "errors": [],
            "retry_count": 0,
            "max_iterations": cfg.MAX_SEARCH_ITERATIONS,
            "citation_fix_attempts": 0,
            "cancel_requested": False,
        }

    async def emit_event(
        event_type: str, stage: str, message: str, data: dict[str, Any] | None = None
    ) -> None:
        async with session_factory() as stage_db:
            res = await stage_db.execute(select(ResearchRun).where(ResearchRun.id == run_id))
            current_run = res.scalar_one_or_none()
            if current_run is not None and current_run.status == "running":
                current_run.current_stage = stage
                await stage_db.commit()
        await event_bus.publish(run_id, event_type, stage, message, data)

    async def is_cancelled(target_run_id: str) -> bool:
        async with session_factory() as check_db:
            res = await check_db.execute(
                select(ResearchRun.cancel_requested).where(ResearchRun.id == UUID(target_run_id))
            )
            flag = res.scalar_one_or_none()
            return bool(flag)

    try:
        active_llm = llm or get_llm_provider(cfg)
        active_search = search_provider or get_search_provider(cfg)

        is_demo = (
            active_llm.provider_name == "mock" or active_search.provider_name == "mock"
        )

        graph = build_research_graph(
            llm=active_llm,
            search_provider=active_search,
            emit_event=emit_event,
            is_cancelled=is_cancelled,
            settings=cfg,
            resolve_dns_on_fetch=resolve_dns_on_fetch,
        )
        final_state = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": str(run_id)}},
        )

        async with session_factory() as db:
            res = await db.execute(select(ResearchRun).where(ResearchRun.id == run_id))
            run = res.scalar_one_or_none()
            if run is None:
                return

            run.is_demo_mode = is_demo
            run.retry_count = int(final_state.get("retry_count", 0))

            if final_state.get("cancel_requested") or run.cancel_requested:
                run.status = "cancelled"
                run.current_stage = "cancelled"
                run.completed_at = datetime.now(UTC)
                await db.commit()
                await event_bus.publish(
                    run_id, "run_cancelled", "cancelled", "Research run cancelled by user."
                )
                return

            # Clear previous artifacts if run was retried
            await db.execute(delete(ResearchPlan).where(ResearchPlan.run_id == run_id))
            await db.execute(delete(Evidence).where(Evidence.run_id == run_id))
            await db.execute(delete(Source).where(Source.run_id == run_id))
            await db.flush()

            analysis = final_state.get("question_analysis", {})
            plan_data = final_state.get("research_plan", {})
            plan = ResearchPlan(
                run_id=run_id,
                objective=str(analysis.get("objective") or run.query),
                scope=str(analysis.get("scope") or ""),
                subquestions=list(final_state.get("subquestions", [])),
                search_strategy=dict(plan_data.get("search_strategy", {})),
            )
            db.add(plan)

            source_map: dict[int, Source] = {}
            for doc in final_state.get("extracted_documents", []):
                cit_num = int(doc["citation_number"])
                src = Source(
                    run_id=run_id,
                    url=str(doc["url"]),
                    canonical_url=str(doc.get("canonical_url") or doc["url"]),
                    title=str(doc.get("title") or "Untitled Source")[:500],
                    publisher=str(doc.get("publisher") or "Unknown")[:255],
                    author=str(doc["author"])[:255] if doc.get("author") else None,
                    published_at=str(doc["published_at"])[:64] if doc.get("published_at") else None,
                    source_type=str(doc.get("source_type") or "company")[:64],
                    extraction_status=str(doc.get("extraction_status") or "extracted")[:32],
                    relevance_score=float(doc.get("relevance_score") or 0.5),
                    relevance_note=str(doc.get("relevance_note") or ""),
                    limitations=str(doc.get("limitations") or ""),
                    raw_excerpt=str(doc.get("raw_excerpt") or ""),
                    content_text=str(doc.get("content_text") or ""),
                    content_hash=doc.get("content_hash") or None,
                    error_detail=doc.get("error_detail"),
                )
                db.add(src)
                source_map[cit_num] = src

            await db.flush()

            evidence_by_source: dict[int, Evidence] = {}
            for ev in final_state.get("evidence_records", []):
                ref_num = int(ev.get("source_ref", 0))
                src_obj = source_map.get(ref_num)
                if src_obj is None:
                    continue
                ev_obj = Evidence(
                    run_id=run_id,
                    source_id=src_obj.id,
                    claim=str(ev["claim"]),
                    excerpt=str(ev.get("excerpt") or ""),
                    evidence_type=str(ev.get("evidence_type") or "company")[:64],
                    claim_category=str(ev.get("claim_category") or "source_reported_claim")[:64],
                    relevance=str(ev.get("relevance") or "medium")[:32],
                    date_context=str(ev.get("date_context") or "")[:120],
                    limitations=str(ev.get("limitations") or ""),
                    corroboration_status=str(ev.get("corroboration_status") or "single_source")[:32],
                )
                db.add(ev_obj)
                if ref_num not in evidence_by_source:
                    evidence_by_source[ref_num] = ev_obj

            await db.flush()

            # Create versioned report snapshot
            existing_versions = await db.execute(
                select(Report.version).where(Report.run_id == run_id)
            )
            max_ver = max((v for v in existing_versions.scalars().all()), default=0)

            report_data = final_state.get("generated_report", {})
            validation_data = final_state.get("citation_validation", {})
            report_status = "validated" if validation_data.get("is_valid") else "warning"

            report = Report(
                run_id=run_id,
                version=max_ver + 1,
                title=str(report_data.get("title") or f"Research Report: {run.query[:80]}")[:400],
                summary=str(report_data.get("summary") or ""),
                content=str(report_data.get("content") or ""),
                structured_data=dict(report_data.get("structured_data") or {}),
                citation_validation=dict(validation_data),
                status=report_status,
            )
            db.add(report)
            await db.flush()

            for cit_num in validation_data.get("cited_numbers", []):
                src_obj = source_map.get(int(cit_num))
                if src_obj is None:
                    continue
                ev_obj = evidence_by_source.get(int(cit_num))
                db.add(
                    ReportCitation(
                        report_id=report.id,
                        source_id=src_obj.id,
                        evidence_id=ev_obj.id if ev_obj else None,
                        citation_number=int(cit_num),
                        cited_claim=ev_obj.claim if ev_obj else src_obj.raw_excerpt[:240],
                    )
                )

            run.status = "completed"
            run.current_stage = "completed"
            run.completed_at = datetime.now(UTC)
            await db.commit()

            await event_bus.publish(
                run_id,
                "run_completed",
                "completed",
                "Research report completed and verified.",
                {"report_id": str(report.id), "status": report_status},
            )
    except Exception as exc:
        logger.exception("Research run %s failed: %s", run_id, exc)
        async with session_factory() as err_db:
            res = await err_db.execute(select(ResearchRun).where(ResearchRun.id == run_id))
            run = res.scalar_one_or_none()
            if run is not None:
                run.status = "failed"
                run.current_stage = "failed"
                run.error_message = str(exc)
                run.completed_at = datetime.now(UTC)
                await err_db.commit()
        await event_bus.publish(
            run_id,
            "run_failed",
            "failed",
            f"Research run failed: {exc}",
            {"error": str(exc)},
        )
