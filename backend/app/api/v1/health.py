"""Health check endpoint for the RAG backend."""
import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.storage import get_file_storage

router = APIRouter(tags=["health"])

logger = logging.getLogger(__name__)


async def _check_postgres() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        logging.warning("Postgres health check failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


async def _check_redis() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        from redis.asyncio import from_url as redis_from_url

        redis = redis_from_url(settings.redis_url)
        await redis.ping()
        await redis.close()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        logging.warning("Redis health check failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


async def _check_broker() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        if settings.CELERY_BROKER_TYPE.lower() == "redis":
            from redis.asyncio import from_url as redis_from_url

            redis = redis_from_url(settings.celery_broker_url)
            await redis.ping()
            await redis.close()
        else:
            import aio_pika

            connection = await aio_pika.connect_robust(settings.celery_broker_url)
            await connection.close()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        logging.warning("Broker health check failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


async def _check_vector_store() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        from app.retrieval.vector_store import get_vector_store

        store = get_vector_store()
        if not store.is_available:
            return {"status": "unavailable", "error": "vector store is not available"}
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        logging.warning("Vector store health check failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


async def _check_storage() -> Dict[str, Any]:
    """Check the configured file storage backend (S3/MinIO or local filesystem)."""
    start = time.perf_counter()
    storage = get_file_storage()
    try:
        if settings.FILE_STORAGE_BACKEND.lower() == "s3":
            # For S3-compatible backends, verify the bucket is reachable.
            await asyncio.to_thread(
                storage._client.head_bucket, Bucket=settings.MINIO_BUCKET
            )
        else:
            # For local storage, verify the base directory exists and is writable.
            base_path = Path(settings.LOCAL_STORAGE_PATH)
            await asyncio.to_thread(base_path.mkdir, parents=True, exist_ok=True)
            marker = base_path / f".health-check-{uuid.uuid4().hex}"
            await asyncio.to_thread(marker.write_text, "")
            await asyncio.to_thread(marker.unlink)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        logging.warning("Storage health check failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


@router.get("/health")
async def health_check():
    services = {
        "postgres": await _check_postgres(),
        "redis": await _check_redis(),
        "broker": await _check_broker(),
        "vector_store": await _check_vector_store(),
        "storage": await _check_storage(),
    }
    healthy = all(s["status"] == "ok" for s in services.values())
    body = {"status": "ok" if healthy else "degraded", "services": services}
    if healthy:
        return body
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body)
