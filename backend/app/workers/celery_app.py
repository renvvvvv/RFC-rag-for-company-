"""Celery application for background task workers."""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "rag_worker",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Import task modules so Celery auto-discovers them.
import app.workers.ingest_tasks  # noqa: E402,F401
import app.workers.embed_tasks  # noqa: E402,F401


@celery_app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
