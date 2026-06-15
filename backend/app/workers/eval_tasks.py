"""Celery tasks for running evaluation jobs."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.evaluation import EvaluationTask
from app.services.evaluation_service import evaluation_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async_engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    future=True,
)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def run_evaluation_task(self, task_id: str, user_id: str | None = None) -> Dict[str, Any]:
    """Run an evaluation task asynchronously."""
    logger.info("Running evaluation task %s", task_id)
    try:
        result = asyncio.run(_run_evaluation_async(task_id, user_id))
        return result
    except Exception as exc:
        logger.exception("Evaluation task %s failed", task_id)
        raise self.retry(exc=exc) from exc


async def _run_evaluation_async(task_id: str, user_id: str | None = None) -> Dict[str, Any]:
    """Load the task from the DB and execute the evaluation."""
    eval_user_id = UUID(user_id) if user_id else None

    async with AsyncSessionLocal() as session:
        task = await session.get(EvaluationTask, UUID(task_id))
        if task is None:
            raise ValueError(f"Evaluation task {task_id} not found")

        try:
            results = await evaluation_service.run_evaluation(
                db=session,
                task=task,
                user_id=eval_user_id,
            )
            return results
        except Exception as exc:
            await evaluation_service.update_task_status(
                session,
                task,
                "failed",
                {"error": str(exc)},
            )
            raise
