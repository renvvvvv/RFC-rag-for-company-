from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel

class DocumentUpload(BaseModel):
    metadata: Optional[Dict[str, Any]] = {}
    tags: Optional[List[str]] = []

class DocumentLinkCreate(BaseModel):
    url: str
    metadata: Optional[Dict[str, Any]] = {}
    tags: Optional[List[str]] = []

class DocumentResponse(BaseModel):
    id: UUID
    kb_id: UUID
    filename: str
    file_type: str
    file_size: Optional[int]
    mime_type: Optional[str]
    storage_key: Optional[str]
    status: str
    processing_info: Optional[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]]
    created_by: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    total: int
    items: List[DocumentResponse]
