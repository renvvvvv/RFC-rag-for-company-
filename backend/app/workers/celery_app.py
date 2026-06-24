"""Celery application for background task workers."""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "rag_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_default_queue="ingest",
    task_routes={
        "app.workers.ingest_tasks.*": {"queue": "ingest"},
        "app.workers.embed_tasks.*": {"queue": "embed"},
        "app.workers.eval_tasks.*": {"queue": "ingest"},
    },
)

# Import task modules so Celery auto-discovers them.
import app.workers.ingest_tasks  # noqa: E402,F401
import app.workers.embed_tasks  # noqa: E402,F401
import app.workers.eval_tasks  # noqa: E402,F401


@celery_app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
