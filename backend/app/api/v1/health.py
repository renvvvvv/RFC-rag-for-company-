"""Health check endpoint for the RAG backend."""
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, status
from sqlalchemy import text

from app.config import settings
from app.database import engine

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


async def _check_rabbitmq() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        import aio_pika

        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        await connection.close()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        logging.warning("RabbitMQ health check failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


async def _check_milvus() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        from pymilvus import connections, utility

        connections.connect(
            alias="health",
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
        )
        _ = utility.get_server_version(using="health")
        connections.disconnect("health")
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        logging.warning("Milvus health check failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


async def _check_minio() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import ClientError

        protocol = "https" if settings.MINIO_SECURE else "http"
        s3 = boto3.client(
            "s3",
            endpoint_url=f"{protocol}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        s3.head_bucket(Bucket=settings.MINIO_BUCKET)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except ClientError as exc:
        logging.warning("MinIO health check failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logging.warning("MinIO health check failed: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    services = {
        "postgres": await _check_postgres(),
        "redis": await _check_redis(),
        "rabbitmq": await _check_rabbitmq(),
        "milvus": await _check_milvus(),
        "minio": await _check_minio(),
    }
    overall = "ok" if all(s["status"] == "ok" for s in services.values()) else "degraded"
    return {
        "status": overall,
        "services": services,
    }
