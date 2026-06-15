"""FastAPI application entry point."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.core.exceptions import RAGBaseException
from app.core.logging import RequestIDMiddleware, configure_logging
from app.core.metrics import rag_api_request_duration_seconds, rag_api_requests_total
from app.database import AsyncSessionLocal, engine

# Router imports
from app.api.v1 import auth, health

# Placeholder routers for upcoming modules
from app.api.v1 import (
    chat,
    config,
    documents,
    eval,
    groups,
    keywords,
    knowledge_bases,
    permissions,
    search,
    users,
)

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage external connection lifecycle."""
    # Startup
    try:
        from pymilvus import connections
        from redis.asyncio import from_url as redis_from_url
        from sqlalchemy import text

        # Verify PostgreSQL connectivity
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        # Establish Redis connection
        app.state.redis = redis_from_url(settings.redis_url)
        await app.state.redis.ping()

        # Establish Milvus connection
        connections.connect(
            alias="default",
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
        )

        # Load runtime model configuration from database
        from app.core.runtime_config import load_runtime_config

        async with AsyncSessionLocal() as db:
            await load_runtime_config(db)
            await db.close()

        logging.info("Application startup completed")
    except Exception as exc:  # noqa: BLE001
        logging.warning("Some external connections failed during startup: %s", exc)

    yield

    # Shutdown
    try:
        await engine.dispose()
        if hasattr(app.state, "redis"):
            await app.state.redis.close()
        from pymilvus import connections

        connections.disconnect("default")
        logging.info("Application shutdown completed")
    except Exception as exc:  # noqa: BLE001
        logging.warning("Error during shutdown: %s", exc)


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Emit request count and duration metrics for every non-metrics request."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        method = request.method
        status = 500
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        except Exception:
            status = 500
            raise
        finally:
            duration = time.perf_counter() - start
            route = request.scope.get("route")
            endpoint = getattr(route, "path_format", request.url.path)
            if endpoint != "/metrics":
                rag_api_request_duration_seconds.labels(
                    method=method, endpoint=endpoint
                ).observe(duration)
                rag_api_requests_total.labels(
                    method=method, endpoint=endpoint, status=str(status)
                ).inc()


# Prometheus metrics endpoint
app.mount("/metrics", make_asgi_app())

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID tracking
app.add_middleware(RequestIDMiddleware)

# Prometheus request metrics
app.add_middleware(PrometheusMiddleware)

# Register API routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(knowledge_bases.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(permissions.router, prefix="/api/v1")
app.include_router(keywords.router, prefix="/api/v1")
app.include_router(groups.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(eval.router, prefix="/api/v1")


@app.exception_handler(RAGBaseException)
async def rag_exception_handler(request: Request, exc: RAGBaseException):
    logging.warning("RAG exception at %s: %s", request.url.path, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled exception at %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/")
async def root():
    return {"message": settings.APP_NAME}
