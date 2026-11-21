import asyncio
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from app.agents.prompts.research_prompts import SYSTEM_ANALYST_PROMPT, build_follow_up_prompt
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.rate_limit import enforce_rate_limit
from app.core.security import get_current_user
from app.models.project import ResearchProject
from app.models.research import (
    Evidence,
    Report,
    ReportCitation,
    ResearchMessage,
    ResearchPlan,
    ResearchRun,
    Source,
)
from app.models.user import User
from app.providers.base import ProviderConfigurationError
from app.providers.factory import get_llm_provider, get_search_provider
from app.schemas.research import (
    EvidenceResponse,
    FollowUpRequest,
    FollowUpResponse,
    ReportCitationResponse,
    ReportResponse,
    ResearchCreateRequest,
    ResearchMessageResponse,
    ResearchPlanResponse,
    ResearchRunResponse,
    SourceResponse,
)
from app.services.event_bus import event_bus
from app.services.exporters import export_report_markdown, export_report_pdf
from app.services.research_runner import execute_research_run

router = APIRouter(prefix="/research", tags=["Research"])

_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


async def _get_owned_run(
    db: AsyncSession, run_id: UUID, user_id: UUID
) -> ResearchRun:
    result = await db.execute(
        select(ResearchRun).where(
            ResearchRun.id == run_id,
            ResearchRun.user_id == user_id,
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research run not found.",
        )
    return run


async def _serialize_run(db: AsyncSession, run: ResearchRun) -> ResearchRunResponse:
    plan_res = await db.execute(select(ResearchPlan).where(ResearchPlan.run_id == run.id))
    plan = plan_res.scalar_one_or_none()

    source_count = await db.scalar(select(func.count(Source.id)).where(Source.run_id == run.id))
    extracted_count = await db.scalar(
        select(func.count(Source.id)).where(
            Source.run_id == run.id, Source.extraction_status == "extracted"
        )
    )
    evidence_count = await db.scalar(
        select(func.count(Evidence.id)).where(Evidence.run_id == run.id)
    )
    report_count = await db.scalar(select(func.count(Report.id)).where(Report.run_id == run.id))

    return ResearchRunResponse(
        id=run.id,
        project_id=run.project_id,
        user_id=run.user_id,
        query=run.query,
        context=run.context,
        depth=run.depth,
        date_range=run.date_range,
        source_preferences=list(run.source_preferences or []),
        language=run.language,
        status=run.status,
        current_stage=run.current_stage,
        retry_count=run.retry_count,
        cancel_requested=run.cancel_requested,
        is_demo_mode=run.is_demo_mode,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        plan=ResearchPlanResponse.model_validate(plan) if plan else None,
        source_count=int(source_count or 0),
        extracted_source_count=int(extracted_count or 0),
        evidence_count=int(evidence_count or 0),
        has_report=bool(report_count and report_count > 0),
    )


@router.get("", response_model=list[ResearchRunResponse])
async def list_research_runs(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResearchRunResponse]:
    result = await db.execute(
        select(ResearchRun)
        .where(ResearchRun.user_id == current_user.id)
        .order_by(ResearchRun.created_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return [await _serialize_run(db, r) for r in runs]


@router.post(
    "",
    response_model=ResearchRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
async def start_research(
    payload: ResearchCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResearchRunResponse:
    cfg = get_settings()

    # Validate provider credentials before enqueueing work
    try:
        llm = get_llm_provider(cfg)
        search = get_search_provider(cfg)
    except ProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    # Enforce per-user daily research quota
    day_ago = datetime.now(UTC) - timedelta(hours=24)
    runs_today = await db.scalar(
        select(func.count(ResearchRun.id)).where(
            ResearchRun.user_id == current_user.id,
            ResearchRun.created_at >= day_ago,
        )
    )
    if int(runs_today or 0) >= cfg.RESEARCH_RUNS_PER_USER_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily research quota reached ({cfg.RESEARCH_RUNS_PER_USER_PER_DAY} runs/24h).",
        )

    # Resolve or create project owned by user
    if payload.project_id is not None:
        proj_res = await db.execute(
            select(ResearchProject).where(
                ResearchProject.id == payload.project_id,
                ResearchProject.user_id == current_user.id,
            )
        )
        project = proj_res.scalar_one_or_none()
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target research project not found.",
            )
    else:
        title = (payload.project_title or payload.query[:80]).strip()
        project = ResearchProject(
            user_id=current_user.id,
            title=title,
            description=f"Investigation: {payload.query[:200]}",
        )
        db.add(project)
        await db.flush()

    is_demo = llm.provider_name == "mock" or search.provider_name == "mock"
    run = ResearchRun(
        project_id=project.id,
        user_id=current_user.id,
        query=payload.query.strip(),
        context=payload.context.strip(),
        depth=payload.depth,
        date_range=payload.date_range,
        source_preferences=payload.source_preferences,
        language=payload.language,
        status="queued",
        current_stage="queued",
        is_demo_mode=is_demo,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    await event_bus.publish(
        run.id,
        "run_queued",
        "queued",
        "Research run queued for execution",
        {"depth": run.depth, "is_demo_mode": run.is_demo_mode},
    )

    if cfg.TASK_QUEUE_MODE == "arq":
        try:
            pool = await create_pool(RedisSettings.from_dsn(cfg.REDIS_URL))
            await pool.enqueue_job("run_research_job", str(run.id))
            await pool.aclose()
        except Exception:
            # Graceful fallback to inline execution if Redis/ARQ isn't running locally
            task = asyncio.create_task(execute_research_run(run.id, AsyncSessionLocal))
            _BACKGROUND_TASKS.add(task)
            task.add_done_callback(_BACKGROUND_TASKS.discard)
    else:
        task = asyncio.create_task(execute_research_run(run.id, AsyncSessionLocal))
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)

    return await _serialize_run(db, run)


@router.get("/{run_id}", response_model=ResearchRunResponse)
async def get_research_status(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResearchRunResponse:
    run = await _get_owned_run(db, run_id, current_user.id)
    return await _serialize_run(db, run)


@router.post("/{run_id}/cancel", response_model=ResearchRunResponse)
async def cancel_research(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResearchRunResponse:
    run = await _get_owned_run(db, run_id, current_user.id)
    if run.status in {"completed", "failed", "cancelled"}:
        return await _serialize_run(db, run)

    run.cancel_requested = True
    if run.status == "queued":
        run.status = "cancelled"
        run.current_stage = "cancelled"
        run.completed_at = datetime.now(UTC)
        await event_bus.publish(run.id, "run_cancelled", "cancelled", "Research run cancelled.")
    await db.commit()
    await db.refresh(run)
    return await _serialize_run(db, run)


@router.get("/{run_id}/events")
async def stream_research_events(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await _get_owned_run(db, run_id, current_user.id)

    async def event_generator():
        # If run already finished before client connected and no history remains, emit snapshot
        if run.status in {"completed", "failed", "cancelled"} and not event_bus._history.get(str(run.id)):
            terminal_event = (
                "run_completed"
                if run.status == "completed"
                else "run_cancelled"
                if run.status == "cancelled"
                else "run_failed"
            )
            yield {
                "event": terminal_event,
                "data": json.dumps(
                    {
                        "run_id": str(run.id),
                        "event": terminal_event,
                        "stage": run.current_stage,
                        "message": f"Research run {run.status}.",
                        "data": {"error": run.error_message} if run.error_message else {},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
            }
            return

        async for payload in event_bus.subscribe(run.id):
            yield {
                "event": payload.get("event", "progress"),
                "data": json.dumps(payload),
            }

    return EventSourceResponse(event_generator())


@router.get("/{run_id}/sources", response_model=list[SourceResponse])
async def get_research_sources(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SourceResponse]:
    await _get_owned_run(db, run_id, current_user.id)
    result = await db.execute(
        select(Source).where(Source.run_id == run_id).order_by(Source.relevance_score.desc())
    )
    return [SourceResponse.model_validate(s) for s in result.scalars().all()]


@router.get("/{run_id}/evidence", response_model=list[EvidenceResponse])
async def get_research_evidence(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EvidenceResponse]:
    await _get_owned_run(db, run_id, current_user.id)
    result = await db.execute(
        select(Evidence).where(Evidence.run_id == run_id).order_by(Evidence.created_at.asc())
    )
    return [EvidenceResponse.model_validate(e) for e in result.scalars().all()]


@router.get("/{run_id}/report", response_model=ReportResponse)
async def get_research_report(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportResponse:
    await _get_owned_run(db, run_id, current_user.id)
    result = await db.execute(
        select(Report)
        .where(Report.run_id == run_id)
        .options(
            selectinload(Report.citations).selectinload(ReportCitation.source),
            selectinload(Report.citations).selectinload(ReportCitation.evidence),
        )
        .order_by(Report.version.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report is not ready yet for this research run.",
        )

    sorted_citations = sorted(report.citations, key=lambda c: c.citation_number)
    return ReportResponse(
        id=report.id,
        run_id=report.run_id,
        version=report.version,
        title=report.title,
        summary=report.summary,
        content=report.content,
        structured_data=report.structured_data,
        citation_validation=report.citation_validation,
        status=report.status,
        created_at=report.created_at,
        citations=[ReportCitationResponse.model_validate(c) for c in sorted_citations],
    )


@router.get("/{run_id}/messages", response_model=list[ResearchMessageResponse])
async def get_follow_up_messages(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResearchMessageResponse]:
    await _get_owned_run(db, run_id, current_user.id)
    result = await db.execute(
        select(ResearchMessage)
        .where(ResearchMessage.run_id == run_id)
        .order_by(ResearchMessage.created_at.asc())
    )
    return [ResearchMessageResponse.model_validate(m) for m in result.scalars().all()]


@router.post("/{run_id}/follow-up", response_model=FollowUpResponse)
async def ask_follow_up(
    run_id: UUID,
    payload: FollowUpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowUpResponse:
    run = await _get_owned_run(db, run_id, current_user.id)
    if run.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Follow-up questions can only be asked after the research run completes.",
        )

    report_res = await db.execute(
        select(Report)
        .where(Report.run_id == run_id)
        .options(selectinload(Report.citations).selectinload(ReportCitation.source))
        .order_by(Report.version.desc())
        .limit(1)
    )
    report = report_res.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    evidence_res = await db.execute(select(Evidence).where(Evidence.run_id == run_id))
    evidence_items = evidence_res.scalars().all()

    sources_catalog = [
        {
            "citation_number": c.citation_number,
            "title": c.source.title if c.source else "Source",
            "url": c.source.url if c.source else "",
            "source_id": str(c.source_id),
        }
        for c in sorted(report.citations, key=lambda x: x.citation_number)
    ]
    if not sources_catalog:
        src_res = await db.execute(select(Source).where(Source.run_id == run_id))
        sources_catalog = [
            {"citation_number": i, "title": s.title, "url": s.url, "source_id": str(s.id)}
            for i, s in enumerate(src_res.scalars().all(), start=1)
        ]

    source_num_by_id = {s["source_id"]: s["citation_number"] for s in sources_catalog}
    ev_records = [
        {
            "source_ref": source_num_by_id.get(str(e.source_id), 1),
            "claim": e.claim,
            "excerpt": e.excerpt,
            "claim_category": e.claim_category,
        }
        for e in evidence_items
    ]

    try:
        llm = get_llm_provider()
    except ProviderConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    prompt = build_follow_up_prompt(
        original_question=run.query,
        follow_up_question=payload.question.strip(),
        report_summary=report.summary,
        sources_catalog=sources_catalog,
        evidence_records=ev_records,
    )
    answer = await llm.generate_text(SYSTEM_ANALYST_PROMPT, prompt)

    cited_nums = sorted({int(m) for m in re.findall(r"\[(\d+)\](?!\()", answer)})
    catalog_by_num = {s["citation_number"]: s for s in sources_catalog}
    referenced_citations = [
        catalog_by_num[n] for n in cited_nums if n in catalog_by_num
    ]

    user_msg = ResearchMessage(
        run_id=run_id, role="user", content=payload.question.strip(), citations=[]
    )
    assistant_msg = ResearchMessage(
        run_id=run_id, role="assistant", content=answer.strip(), citations=referenced_citations
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    return FollowUpResponse(
        user_message=ResearchMessageResponse.model_validate(user_msg),
        assistant_message=ResearchMessageResponse.model_validate(assistant_msg),
    )


@router.get("/{run_id}/export")
async def export_research_report(
    run_id: UUID,
    format: Literal["markdown", "pdf"] = Query(default="markdown"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await _get_owned_run(db, run_id, current_user.id)
    result = await db.execute(
        select(Report)
        .where(Report.run_id == run_id)
        .order_by(Report.version.desc())
        .limit(1)
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No report available to export for this research run.",
        )

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", report.title.lower()).strip("-")[:50] or "research-report"
    if format == "markdown":
        md = export_report_markdown(
            title=report.title,
            query=run.query,
            summary=report.summary,
            content=report.content,
            is_demo_mode=run.is_demo_mode,
            validation_status=report.status,
            created_at=report.created_at,
        )
        return Response(
            content=md,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{slug}.md"'},
        )

    pdf_bytes = export_report_pdf(
        title=report.title,
        query=run.query,
        content=report.content,
        is_demo_mode=run.is_demo_mode,
        validation_status=report.status,
        created_at=report.created_at,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{slug}.pdf"'},
    )
