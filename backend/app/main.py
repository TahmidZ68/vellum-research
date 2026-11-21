from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.api.v1.auth import router as auth_router
from app.api.v1.auth import settings_router
from app.api.v1.projects import router as projects_router
from app.api.v1.research import router as research_router
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    # Ensure schema exists for local SQLite development; PostgreSQL uses Alembic migrations
    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description=(
            "Vellum Research API — structured web investigation, evidence evaluation, "
            "contradiction detection, and citation-validated research reports."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, object]:
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "environment": settings.APP_ENV,
            "providers": settings.get_provider_diagnostics(),
        }

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")
    app.include_router(research_router, prefix="/api/v1")

    return app


app = create_app()
