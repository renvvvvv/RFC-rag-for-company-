from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str
    kb_ids: List[UUID]
    modalities: Optional[List[str]] = None
    top_k: Optional[int] = 10
    rerank_top_k: Optional[int] = 5
    max_context_tokens: Optional[int] = 4000
    stream: Optional[bool] = False

class SourceItem(BaseModel):
    doc_id: Optional[str]
    chunk_id: Optional[str]
    content: str
    score: float
    modality: str

class ChatResponse(BaseModel):
    answer: str
    intercepted: bool = False
    sources: List[SourceItem] = []
    strategy: Optional[Dict[str, Any]] = None
