"""Seed a demo user and sample research investigation for local exploration."""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.project import ResearchProject  # noqa: E402
from app.models.research import ResearchRun  # noqa: E402
from app.models.user import User  # noqa: E402
from app.providers.llm_mock import MockLLMProvider  # noqa: E402
from app.providers.search_mock import MockSearchProvider  # noqa: E402
from app.services.research_runner import execute_research_run  # noqa: E402


async def main() -> None:
    settings = get_settings()
    if settings.DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.email == "demo@openresearch.local"))
        user = res.scalar_one_or_none()
        if user is None:
            user = User(
                email="demo@openresearch.local",
                full_name="Demo Researcher",
                password_hash=hash_password("DemoPassword123!"),
            )
            db.add(user)
            await db.flush()

        project = ResearchProject(
            user_id=user.id,
            title="AI Agent Frameworks Comparison (Sample)",
            description="Seeded sample investigation using clearly labeled mock providers.",
        )
        db.add(project)
        await db.flush()

        run = ResearchRun(
            project_id=project.id,
            user_id=user.id,
            query=(
                "Compare the leading open-source AI agent frameworks. Evaluate their "
                "architecture, developer experience, deployment options, and limitations."
            ),
            context="Focus on production reliability and primary documentation.",
            depth="quick",
            date_range="any",
            source_preferences=["primary", "academic"],
            language="en",
            status="queued",
            current_stage="queued",
            is_demo_mode=True,
        )
        db.add(run)
        await db.commit()
        run_id = run.id

    await execute_research_run(
        run_id,
        AsyncSessionLocal,
        llm=MockLLMProvider(),
        search_provider=MockSearchProvider(),
        resolve_dns_on_fetch=False,
    )
    print("Seeded demo user: demo@openresearch.local / DemoPassword123!")
    print(f"Seeded sample research run ID: {run_id}")


if __name__ == "__main__":
    asyncio.run(main())
