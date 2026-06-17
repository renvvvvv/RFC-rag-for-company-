from typing import Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.runtime_config import get_model_config, update_runtime_config
from app.database import get_db
from app.schemas.user import UserResponse

router = APIRouter(prefix="/config", tags=["系统配置"])


class ModelConfigOut(BaseModel):
    embedding_api_url: str | None
    embedding_model: str
    rerank_api_url: str | None
    rerank_model: str
    llm_api_url: str | None
    llm_model: str
    llm_base_url: str


class ModelConfigUpdate(BaseModel):
    embedding_api_url: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    rerank_api_url: str | None = None
    rerank_model: str | None = None
    rerank_api_key: str | None = None
    llm_api_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    minimax_api_key: str | None = None


@router.get("/models", response_model=ModelConfigOut)
async def get_model_config_api(
    current_user: UserResponse = Depends(get_current_user),
):
    """获取模型服务配置（不包含 API Key）"""
    cfg = get_model_config()
    return ModelConfigOut(
        embedding_api_url=cfg.get("EMBEDDING_API_URL"),
        embedding_model=cfg.get("EMBEDDING_MODEL"),
        rerank_api_url=cfg.get("RERANK_API_URL"),
        rerank_model=cfg.get("RERANK_MODEL"),
        llm_api_url=cfg.get("LLM_API_URL"),
        llm_model=cfg.get("LLM_MODEL"),
        llm_base_url=cfg.get("MINIMAX_BASE_URL"),
    )


@router.put("/models")
async def update_model_config_api(
    data: ModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """更新模型服务配置，保存后立即生效"""
    updates: Dict[str, Any] = {}
    if data.embedding_api_url is not None:
        updates["EMBEDDING_API_URL"] = data.embedding_api_url
    if data.embedding_model is not None:
        updates["EMBEDDING_MODEL"] = data.embedding_model
    # API keys: treat empty strings as "no change" so the frontend can keep the
    # password fields blank without accidentally clearing stored credentials.
    if data.embedding_api_key:
        updates["EMBEDDING_API_KEY"] = data.embedding_api_key
    if data.rerank_api_url is not None:
        updates["RERANK_API_URL"] = data.rerank_api_url
    if data.rerank_model is not None:
        updates["RERANK_MODEL"] = data.rerank_model
    if data.rerank_api_key:
        updates["RERANK_API_KEY"] = data.rerank_api_key
    if data.llm_api_url is not None:
        updates["LLM_API_URL"] = data.llm_api_url
    if data.llm_model is not None:
        updates["LLM_MODEL"] = data.llm_model
    if data.llm_api_key:
        updates["LLM_API_KEY"] = data.llm_api_key
    if data.minimax_api_key:
        updates["MINIMAX_API_KEY"] = data.minimax_api_key

    await update_runtime_config(db, updates)
    return {"message": "配置已保存并生效"}
