"""Optional full-text/BM25 store backed by Meilisearch.

This module is intentionally decoupled from the core vector store flow: it is
loaded lazily and will not break application startup if the ``meilisearch``
package or server is unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from app.config import Settings, settings

try:
    import meilisearch

    _MEILI_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    meilisearch = None  # type: ignore
    _MEILI_AVAILABLE = False
    logging.getLogger(__name__).warning("meilisearch package is not installed: %s", exc)

logger = logging.getLogger(__name__)


class MeilisearchFulltextStore:
    """BM25 full-text index for chunk text using Meilisearch.

    Configuration is read from environment variables (with sensible defaults) or
    from an explicit ``Settings`` object so that it can later be migrated into
    ``app.config.Settings`` without changing this file.

    Environment variables:
        * ``MEILISEARCH_HOST`` (default: ``http://localhost:7700``)
        * ``MEILISEARCH_API_KEY`` (default: ``None``)
        * ``MEILISEARCH_INDEX_NAME`` (default: ``{MILVUS_COLLECTION_PREFIX}_chunks_text``)
    """

    DEFAULT_HOST = "http://localhost:7700"

    def __init__(
        self,
        host: str | None = None,
        api_key: str | None = None,
        index_name: str | None = None,
        store_settings: Settings | None = None,
    ) -> None:
        self._settings = store_settings or settings
        self.host = host or os.getenv("MEILISEARCH_HOST", self.DEFAULT_HOST)
        self.api_key = api_key or os.getenv("MEILISEARCH_API_KEY") or None
        self.index_name = index_name or os.getenv(
            "MEILISEARCH_INDEX_NAME",
            f"{self._settings.MILVUS_COLLECTION_PREFIX}_chunks_text",
        )

        self._client: Any | None = None
        self._available = False
        self._connect()

        if self._available:
            self._ensure_index()

    # ------------------------------------------------------------------
    # Connection / availability
    # ------------------------------------------------------------------
    def _connect(self) -> None:
        if not _MEILI_AVAILABLE:
            logger.warning("meilisearch package not installed; MeilisearchFulltextStore unavailable")
            return

        try:
            self._client = meilisearch.Client(self.host, self.api_key)
            self._client.health()
            self._available = True
            logger.info("Connected to Meilisearch at %s", self.host)
        except Exception as exc:
            self._available = False
            logger.warning("Failed to connect to Meilisearch at %s: %s", self.host, exc)

    @property
    def is_available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------
    def _ensure_index(self) -> None:
        if not self._available or self._client is None:
            return

        try:
            indexes_resp = self._client.get_indexes()
            if isinstance(indexes_resp, dict):
                existing = {idx.get("uid") for idx in indexes_resp.get("results", [])}
            else:
                existing = {idx.uid for idx in indexes_resp if hasattr(idx, "uid")}

            if self.index_name not in existing:
                self._client.create_index(self.index_name, {"primaryKey": "id"})
                logger.info("Created Meilisearch index %s", self.index_name)

            index = self._client.index(self.index_name)
            index.update_searchable_attributes(["text", "title", "tags"])
            index.update_ranking_rules(
                ["words", "typo", "proximity", "attribute", "sort", "exactness"]
            )
        except Exception as exc:
            logger.warning("Failed to ensure Meilisearch index %s: %s", self.index_name, exc)

    # ------------------------------------------------------------------
    # Document operations
    # ------------------------------------------------------------------
    def index_chunks(self, chunks: List[Any]) -> Dict[str, Any]:
        """Index a list of chunk objects for BM25 retrieval.

        Each chunk is expected to expose at least ``id``, ``chunk_id``,
        ``doc_id``, ``kb_id``, ``text``, ``modality`` and ``status``.
        Optional attributes ``title`` and ``tags`` are also indexed when present.
        """
        if not self._available or self._client is None:
            logger.warning("Meilisearch unavailable; skipping index_chunks")
            return {"indexed": 0, "errors": []}

        documents: List[Dict[str, Any]] = []
        for chunk in chunks:
            doc: Dict[str, Any] = {
                "id": str(chunk.id),
                "chunk_id": getattr(chunk, "chunk_id", str(chunk.id)),
                "doc_id": getattr(chunk, "doc_id", ""),
                "kb_id": getattr(chunk, "kb_id", ""),
                "text": getattr(chunk, "text", "") or "",
                "modality": getattr(chunk, "modality", "text"),
                "status": getattr(chunk, "status", "active"),
            }
            if hasattr(chunk, "title"):
                doc["title"] = chunk.title
            if hasattr(chunk, "tags"):
                doc["tags"] = list(chunk.tags) if chunk.tags else []
            documents.append(doc)

        if not documents:
            return {"indexed": 0, "errors": []}

        try:
            task = self._client.index(self.index_name).add_documents(documents)
            logger.debug("Indexed %s chunks in Meilisearch", len(documents))
            return {"indexed": len(documents), "task": task}
        except Exception as exc:
            logger.exception("Meilisearch index_chunks failed: %s", exc)
            return {"indexed": 0, "errors": [str(exc)]}

    def search(
        self,
        query: str,
        filter_str: str | None = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """BM25 search over the indexed chunk text.

        Args:
            query: Free-text query.
            filter_str: Meilisearch filter expression, e.g. ``doc_id = "abc123"``.
            limit: Maximum number of hits.
        """
        if not self._available or self._client is None:
            logger.warning("Meilisearch unavailable; returning empty search results")
            return []

        try:
            params: Dict[str, Any] = {
                "limit": limit,
                "attributesToHighlight": ["text"],
            }
            if filter_str:
                params["filter"] = filter_str

            results = self._client.index(self.index_name).search(query, params)
            hits = results.get("hits", [])
            for hit in hits:
                hit["score"] = hit.get("_rankingScore")
            return hits
        except Exception as exc:
            logger.exception("Meilisearch search failed: %s", exc)
            return []

    def delete_by_doc_id(self, doc_id: str) -> bool:
        """Delete all indexed chunks belonging to *doc_id*."""
        if not self._available or self._client is None:
            logger.warning("Meilisearch unavailable; skipping delete_by_doc_id")
            return False

        escaped = str(doc_id).replace('"', '\\"')
        filter_expr = f'doc_id = "{escaped}"'

        try:
            index = self._client.index(self.index_name)
            # Prefer the filter-aware API when available.
            if hasattr(index, "delete_documents_by_filter"):
                index.delete_documents_by_filter(filter_expr)
            else:
                index.delete_documents({"filter": filter_expr})
            logger.info("Deleted Meilisearch records for doc_id=%s", doc_id)
            return True
        except Exception as exc:
            logger.exception("Meilisearch delete_by_doc_id failed: %s", exc)
            return False
