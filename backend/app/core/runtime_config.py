"""Runtime model configuration.

Model configuration is persisted in PostgreSQL (system_config table) and kept in
a process-global dictionary so that clients can read it without a database
session.  The dictionary is refreshed once at startup and updated on every
configuration change.
"""
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.system_config import SystemConfig

# In-memory snapshot of the model configuration.  Keys match environment
# variable names so that clients can fall back to settings easily.
RUNTIME_MODEL_CONFIG: Dict[str, Optional[str]] = {
    "EMBEDDING_API_URL": settings.EMBEDDING_API_URL or settings.EMBEDDING_SERVICE_URL,
    "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
    "EMBEDDING_API_KEY": settings.EMBEDDING_API_KEY,
    "RERANK_API_URL": settings.RERANK_API_URL or settings.RERANK_SERVICE_URL,
    "RERANK_MODEL": settings.RERANK_MODEL,
    "RERANK_API_KEY": settings.RERANK_API_KEY,
    "LLM_API_URL": settings.LLM_API_URL,
    "LLM_MODEL": settings.LLM_MODEL,
    "LLM_API_KEY": settings.LLM_API_KEY or settings.MINIMAX_API_KEY,
    "MINIMAX_API_KEY": settings.MINIMAX_API_KEY,
    "MINIMAX_BASE_URL": settings.MINIMAX_BASE_URL,
}

# Mapping from database keys to the canonical config keys.
_DB_KEYS = {
    "EMBEDDING_API_URL": "EMBEDDING_API_URL",
    "EMBEDDING_MODEL": "EMBEDDING_MODEL",
    "EMBEDDING_API_KEY": "EMBEDDING_API_KEY",
    "RERANK_API_URL": "RERANK_API_URL",
    "RERANK_MODEL": "RERANK_MODEL",
    "RERANK_API_KEY": "RERANK_API_KEY",
    "LLM_API_URL": "LLM_API_URL",
    "LLM_MODEL": "LLM_MODEL",
    "LLM_API_KEY": "LLM_API_KEY",
    "MINIMAX_API_KEY": "MINIMAX_API_KEY",
}


def get_model_config() -> Dict[str, Optional[str]]:
    """Return the current in-memory model configuration."""
    return RUNTIME_MODEL_CONFIG.copy()


async def load_runtime_config(db: AsyncSession) -> Dict[str, Optional[str]]:
    """Load configuration from database into the in-memory snapshot."""
    global RUNTIME_MODEL_CONFIG

    result = await db.execute(select(SystemConfig).where(SystemConfig.key.in_(_DB_KEYS.keys())))
    rows = {row.key: row.value for row in result.scalars().all()}

    for db_key, cfg_key in _DB_KEYS.items():
        if rows.get(db_key) is not None:
            RUNTIME_MODEL_CONFIG[cfg_key] = rows[db_key]

    return RUNTIME_MODEL_CONFIG.copy()


async def update_runtime_config(db: AsyncSession, updates: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Persist updates to database and refresh the in-memory snapshot."""
    global RUNTIME_MODEL_CONFIG

    for db_key, cfg_key in _DB_KEYS.items():
        if cfg_key not in updates:
            continue

        value = updates[cfg_key]
        if value is None:
            continue

        result = await db.execute(select(SystemConfig).where(SystemConfig.key == db_key))
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            db.add(SystemConfig(key=db_key, value=value))

        RUNTIME_MODEL_CONFIG[cfg_key] = value

    await db.commit()
    return RUNTIME_MODEL_CONFIG.copy()
