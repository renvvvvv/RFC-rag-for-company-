"""Health check endpoint for the RAG backend."""
import logging

from fastapi import APIRouter, status
from sqlalchemy import text

from app.config import settings
from app.database import engine

router = APIRouter(tags=["health"])


async def _check_postgres() -> str:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logging.warning("Postgres health check failed: %s", exc)
        return "unavailable"


async def _check_redis() -> str:
    try:
        from redis.asyncio import from_url as redis_from_url

        redis = redis_from_url(settings.redis_url)
        await redis.ping()
        await redis.close()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logging.warning("Redis health check failed: %s", exc)
        return "unavailable"


async def _check_milvus() -> str:
    try:
        from pymilvus import connections, utility

        connections.connect(
            alias="health",
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
        )
        _ = utility.get_server_version(using="health")
        connections.disconnect("health")
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logging.warning("Milvus health check failed: %s", exc)
        return "unavailable"


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {
        "status": "ok",
        "services": {
            "postgres": await _check_postgres(),
            "redis": await _check_redis(),
            "milvus": await _check_milvus(),
        },
    }
