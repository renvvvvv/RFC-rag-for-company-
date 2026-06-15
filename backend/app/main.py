"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.core.exceptions import RAGBaseException
from app.core.logging import RequestIDMiddleware, configure_logging
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
