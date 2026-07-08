from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SourceItem(BaseModel):
    doc_id: Optional[str]
    chunk_id: Optional[str]
    content: str
    score: float
    rerank_score: Optional[float] = None
    modality: str
    position_info: Optional[Dict[str, Any]] = None
    page: Optional[int] = None
    sheet: Optional[str] = None
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    query: str
    kb_ids: List[UUID]
    conversation_id: Optional[UUID] = None
    modalities: Optional[List[str]] = None
    top_k: Optional[int] = 10
    rerank_top_k: Optional[int] = 5
    max_context_tokens: Optional[int] = 4000
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    answer: str
    intercepted: bool = False
    sources: List[SourceItem] = []
    strategy: Optional[Dict[str, Any]] = None
    conversation_id: Optional[UUID] = None


class ConversationCreate(BaseModel):
    title: Optional[str] = "新会话"
    kb_ids: List[UUID]


class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    kb_ids: List[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    sources: List[SourceItem] = []
    feedback_rating: Optional[int] = None
    feedback_comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatWithHistoryRequest(BaseModel):
    conversation_id: UUID
    query: str
    kb_ids: Optional[List[UUID]] = None
    modalities: Optional[List[str]] = None
    top_k: Optional[int] = 10
    rerank_top_k: Optional[int] = 5
    max_context_tokens: Optional[int] = 4000


class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=-1, le=1)
    comment: Optional[str] = None
