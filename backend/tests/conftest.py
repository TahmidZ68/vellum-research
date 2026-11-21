import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.rate_limit import rate_limiter
from app.main import create_app


@pytest_asyncio.fixture
async def test_engine(tmp_path: Path):
    db_file = tmp_path / "test_ora.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def client(
    monkeypatch: pytest.MonkeyPatch,
    test_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    rate_limiter.reset()
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TASK_QUEUE_MODE", "inline")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_MOCK_PROVIDERS", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-at-least-32-chars")
    get_settings.cache_clear()

    # Patch AsyncSessionLocal used by inline background runner
    import app.api.v1.research as research_api

    monkeypatch.setattr(research_api, "AsyncSessionLocal", test_session_factory)

    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

    # Allow background tasks spawned during tests to settle cleanly
    await asyncio.sleep(0.05)
    get_settings.cache_clear()
