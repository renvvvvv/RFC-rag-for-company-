"""Mock embedding service for local integration testing.

Returns deterministic 768-dimension zero vectors for every request.
"""
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Embedding Service")

EMBEDDING_DIM = 768


class EmbedItem(BaseModel):
    id: str
    content: str
    modality: str = "text"
    image_path: str | None = None


class EmbedRequest(BaseModel):
    items: List[EmbedItem]


@app.post("/")
async def embed_root(req: EmbedRequest) -> Dict[str, Any]:
    embeddings = [[0.0] * EMBEDDING_DIM for _ in req.items]
    return {"embeddings": embeddings}


@app.post("/embed")
async def embed_path(req: EmbedRequest) -> Dict[str, Any]:
    embeddings = [[0.0] * EMBEDDING_DIM for _ in req.items]
    return {"embeddings": embeddings}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}
