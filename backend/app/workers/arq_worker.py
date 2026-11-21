import logging
from uuid import UUID

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.logging import configure_logging
from app.services.research_runner import execute_research_run

logger = logging.getLogger(__name__)


async def run_research_job(ctx: dict, run_id_str: str) -> None:
    """ARQ background job entrypoint for executing a research run."""
    logger.info("Starting ARQ research job for run_id=%s", run_id_str)
    await execute_research_run(UUID(run_id_str), AsyncSessionLocal)


async def startup(ctx: dict) -> None:
    configure_logging()
    logger.info("ARQ research worker started.")


async def shutdown(ctx: dict) -> None:
    logger.info("ARQ research worker shutting down.")


class WorkerSettings:
    functions = [run_research_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().REDIS_URL)
    max_jobs = 4
    job_timeout = 900
