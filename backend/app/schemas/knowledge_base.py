from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel


class KnowledgeBaseBase(BaseModel):
    name: str
    description: Optional[str] = None


class KnowledgeBaseCreate(KnowledgeBaseBase):
    config: Optional[Dict[str, Any]] = {}


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class KnowledgeBaseResponse(KnowledgeBaseBase):
    id: UUID
    owner_id: Optional[UUID] = None
    config: Dict[str, Any]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeBaseStats(BaseModel):
    kb_id: UUID
    document_count: int
    chunk_count: int
    status_breakdown: Dict[str, int]
    last_upload_at: Optional[datetime] = None
