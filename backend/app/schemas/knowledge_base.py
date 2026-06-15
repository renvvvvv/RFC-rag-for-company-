from datetime import datetime
from typing import Optional, Dict, Any
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
