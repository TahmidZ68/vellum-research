from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.project import ResearchProject
from app.models.research import ResearchRun
from app.models.user import User
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.schemas.research import ResearchRunResponse

router = APIRouter(prefix="/projects", tags=["Projects"])


async def _enrich_project(db: AsyncSession, project: ResearchProject) -> ProjectResponse:
    run_count = await db.scalar(
        select(func.count(ResearchRun.id)).where(ResearchRun.project_id == project.id)
    )
    latest_res = await db.execute(
        select(ResearchRun)
        .where(ResearchRun.project_id == project.id)
        .order_by(ResearchRun.created_at.desc())
        .limit(1)
    )
    latest_run = latest_res.scalar_one_or_none()
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        title=project.title,
        description=project.description,
        is_archived=project.is_archived,
        created_at=project.created_at,
        updated_at=project.updated_at,
        run_count=int(run_count or 0),
        latest_run_status=latest_run.status if latest_run else None,
        latest_run_id=latest_run.id if latest_run else None,
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    include_archived: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    stmt = select(ResearchProject).where(ResearchProject.user_id == current_user.id)
    if not include_archived:
        stmt = stmt.where(ResearchProject.is_archived.is_(False))
    stmt = stmt.order_by(ResearchProject.updated_at.desc())

    result = await db.execute(stmt)
    projects = result.scalars().all()
    return [await _enrich_project(db, p) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = ResearchProject(
        user_id=current_user.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _enrich_project(db, project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    result = await db.execute(
        select(ResearchProject).where(
            ResearchProject.id == project_id,
            ResearchProject.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return await _enrich_project(db, project)


@router.get("/{project_id}/runs", response_model=list[ResearchRunResponse])
async def list_project_runs(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResearchRunResponse]:
    proj_res = await db.execute(
        select(ResearchProject.id).where(
            ResearchProject.id == project_id,
            ResearchProject.user_id == current_user.id,
        )
    )
    if proj_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    runs_res = await db.execute(
        select(ResearchRun)
        .where(ResearchRun.project_id == project_id, ResearchRun.user_id == current_user.id)
        .order_by(ResearchRun.created_at.desc())
    )
    runs = runs_res.scalars().all()
    return [ResearchRunResponse.model_validate(r) for r in runs]


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    result = await db.execute(
        select(ResearchProject).where(
            ResearchProject.id == project_id,
            ResearchProject.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    if payload.title is not None:
        project.title = payload.title.strip()
    if payload.description is not None:
        project.description = payload.description.strip()
    if payload.is_archived is not None:
        project.is_archived = payload.is_archived

    await db.commit()
    await db.refresh(project)
    return await _enrich_project(db, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(ResearchProject).where(
            ResearchProject.id == project_id,
            ResearchProject.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    await db.delete(project)
    await db.commit()
