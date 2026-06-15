"""Request/response schemas for search endpoints."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Hybrid / semantic / keyword search request."""

    query: str = Field(..., min_length=1, description="搜索查询文本")
    kb_ids: List[UUID] = Field(..., min_length=1, description="知识库ID列表")
    mode: str = Field(
        default="hybrid",
        pattern="^(hybrid|semantic|keyword)$",
        description="检索模式：hybrid/semantic/keyword",
    )
    modalities: Optional[List[str]] = Field(
        default=None,
        description="模态过滤：text/image/table/link 等",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="每路召回数量")
    rerank_top_k: int = Field(default=5, ge=1, le=100, description="重排序后返回数量")


class SearchResultItem(BaseModel):
    """单个搜索结果。"""

    chunk_id: str
    doc_id: str
    content: str
    modality: str = "text"
    score: float
    rerank_score: Optional[float] = None
    max_keyword_level: str = "L0"
    filtered: bool = False
    position_info: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class SearchResponse(BaseModel):
    """搜索接口响应。"""

    query: str
    mode: str
    total: int
    results: List[SearchResultItem]


class SearchHistoryItem(BaseModel):
    """搜索历史记录。"""

    id: UUID
    query: str
    mode: str
    kb_ids: List[UUID]
    result_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class SearchHistoryResponse(BaseModel):
    """搜索历史列表响应。"""

    total: int
    items: List[SearchHistoryItem]
