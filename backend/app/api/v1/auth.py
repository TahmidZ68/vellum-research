from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.project import ResearchProject
from app.models.research import ResearchRun
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    SettingsOverviewResponse,
    UserResponse,
    UserSettingsUpdate,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    normalized_email = payload.email.strip().lower()
    existing = await db.execute(select(User).where(User.email == normalized_email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=normalized_email,
        full_name=payload.full_name.strip() or normalized_email.split("@")[0],
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    normalized_email = payload.email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(user.id)
    return AuthResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


settings_router = APIRouter(prefix="/settings", tags=["Settings"])


@settings_router.get("", response_model=SettingsOverviewResponse)
async def get_settings_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SettingsOverviewResponse:
    cfg = get_settings()
    day_ago = datetime.now(UTC) - timedelta(hours=24)

    total_projects = await db.scalar(
        select(func.count(ResearchProject.id)).where(ResearchProject.user_id == current_user.id)
    )
    total_runs = await db.scalar(
        select(func.count(ResearchRun.id)).where(ResearchRun.user_id == current_user.id)
    )
    runs_last_24h = await db.scalar(
        select(func.count(ResearchRun.id)).where(
            ResearchRun.user_id == current_user.id,
            ResearchRun.created_at >= day_ago,
        )
    )

    return SettingsOverviewResponse(
        user=UserResponse.model_validate(current_user),
        providers=cfg.get_provider_diagnostics(),
        usage={
            "total_projects": int(total_projects or 0),
            "total_runs": int(total_runs or 0),
            "runs_last_24h": int(runs_last_24h or 0),
            "daily_limit": cfg.RESEARCH_RUNS_PER_USER_PER_DAY,
        },
    )


@settings_router.patch("", response_model=UserResponse)
async def update_user_settings(
    payload: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.preferred_language is not None:
        current_user.preferred_language = payload.preferred_language
    if payload.preferred_theme is not None:
        current_user.preferred_theme = payload.preferred_theme
    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)
