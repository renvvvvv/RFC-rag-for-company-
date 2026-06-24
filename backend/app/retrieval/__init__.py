"""Retrieval layer: vector stores and full-text indexes."""
from app.retrieval.bm25_client import BM25Client
from app.retrieval.milvus_client import MilvusVectorStore
from app.retrieval.vector_store import BaseVectorStore, get_vector_store

__all__ = ["BaseVectorStore", "get_vector_store", "MilvusVectorStore", "BM25Client"]

try:
    from app.retrieval.pgvector_client import PGVectorStore

    __all__.append("PGVectorStore")
except Exception:  # pragma: no cover
    pass

try:
    from app.retrieval.meilisearch_client import MeilisearchFulltextStore

    __all__.append("MeilisearchFulltextStore")
except Exception:  # pragma: no cover
    pass
