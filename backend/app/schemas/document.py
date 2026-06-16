from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, field_validator

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

    @field_validator("metadata", "processing_info", mode="before")
    @classmethod
    def _convert_json_metadata(cls, v: Any) -> Optional[Dict[str, Any]]:
        # SQLAlchemy JSONB may return a wrapper object (e.g. MetaData) in some drivers;
        # force it to a plain dict so Pydantic can validate it.
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        return dict(v) if hasattr(v, "__iter__") and not isinstance(v, str) else {}

class DocumentListResponse(BaseModel):
    total: int
    items: List[DocumentResponse]
