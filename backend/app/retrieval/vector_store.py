"""Abstract vector store interface for the RAG retrieval layer.

The concrete ``Chunk`` model is expected to be created later in
``app.models.chunk``. This module only defines a lightweight protocol so that
future models can be used via duck-typing without creating a hard import
dependency today.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Protocol, TypeVar

logger = logging.getLogger(__name__)


class ChunkLike(Protocol):
    """Minimal shape required from chunk models passed to vector stores."""

    id: str
    chunk_id: str
    doc_id: str
    kb_id: str
    modality: str
    doc_acl_version: str
    max_keyword_level: int
    tags: List[str] | None
    created_by: str
    status: str


ChunkT = TypeVar("ChunkT", bound=ChunkLike)


class BaseVectorStore(ABC):
    """Abstract vector store used by text/image multimodal retrieval.

    Implementations are expected to gracefully degrade (log and return empty
    results) when the underlying engine is unavailable.
    """

    @abstractmethod
    def create_collection(self, collection_name: str, **kwargs: Any) -> bool:
        """Create a vector collection if it does not already exist."""
        ...

    @abstractmethod
    def insert(self, collection_name: str, records: List[Dict[str, Any]]) -> List[str]:
        """Insert raw records into *collection_name* and return primary keys."""
        ...

    @abstractmethod
    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        filter_expr: str = "",
        top_k: int = 10,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Vector ANN search in *collection_name*.

        Returns a list of hit dictionaries. Each hit must contain at least the
        stored entity fields plus a ``score`` key.
        """
        ...

    @abstractmethod
    def delete_by_doc_id(
        self,
        doc_id: str,
        collection_name: str | None = None,
    ) -> bool:
        """Delete all vectors belonging to *doc_id*.

        When *collection_name* is omitted the implementation should delete from
        every relevant collection.
        """
        ...

    @abstractmethod
    def update(
        self,
        collection_name: str,
        pk: str,
        data: Dict[str, Any],
    ) -> bool:
        """Update/upsert a single entity identified by its primary key."""
        ...

    @abstractmethod
    def drop_collection(self, collection_name: str) -> bool:
        """Permanently drop a vector collection."""
        ...
