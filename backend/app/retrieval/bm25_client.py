"""PostgreSQL full-text search (BM25-style) client for chunk retrieval."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Sequence
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import Chunk
from app.models.document import Document

logger = logging.getLogger(__name__)


class BM25Client:
    """BM25 keyword search backed by PostgreSQL full-text search.

    The ``Chunk`` table is expected to have a ``content_tsv`` ``TSVECTOR``
    column (GIN-indexed).  Queries are tokenised with ``plainto_tsquery`` and
    ranked with ``ts_rank_cd``.  The client is fully async and degrades
    gracefully when the schema is not ready or the query is empty.
    """

    def __init__(self, ts_config: str = "simple") -> None:
        self.ts_config = ts_config

    @staticmethod
    def _normalise_query(query: str) -> str:
        """Remove characters that break ``to_tsquery`` syntax."""
        if not query:
            return ""
        # Keep CJK characters, letters, digits and spaces; drop punctuation.
        cleaned = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", query)
        return " ".join(cleaned.split())

    async def search(
        self,
        db: AsyncSession,
        query: str,
        kb_ids: Sequence[UUID | str],
        top_k: int = 20,
        denied_doc_ids: Sequence[str] | None = None,
        denied_tags: Sequence[str] | None = None,
        modalities: Sequence[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """BM25 search over active chunks restricted by knowledge base(s).

        Args:
            db: Async SQLAlchemy session.
            query: Free-text query.
            kb_ids: Knowledge-base IDs to scope the search.
            top_k: Maximum number of hits to return.
            denied_doc_ids: Document IDs the user is explicitly denied.
            denied_tags: Tags the user is explicitly denied.
            modalities: Optional modality filter (e.g. ``["text", "table"]``).

        Returns:
            List of result dicts with ``chunk_id``, ``doc_id``, ``kb_id``,
            ``content``, ``score`` and ``modality``.
        """
        normalised = self._normalise_query(query)
        if not normalised or not kb_ids:
            return []

        try:
            rank_expr = func.ts_rank_cd(
                Chunk.content_tsv,
                func.plainto_tsquery(self.ts_config, normalised),
                32,  # rank normalization: divide by document length
            ).label("score")

            ts_match = Chunk.content_tsv.op("@@")(
                func.plainto_tsquery(self.ts_config, normalised)
            )

            stmt = (
                select(
                    Chunk.id,
                    Chunk.doc_id,
                    Document.kb_id,
                    Chunk.content,
                    Chunk.modality,
                    rank_expr,
                )
                .join(Document, Chunk.doc_id == Document.id)
                .where(ts_match)
                .where(Chunk.status == "active")
                .where(Document.kb_id.in_(list(kb_ids)))
                .order_by(desc(rank_expr))
                .limit(top_k)
            )

            if modalities:
                stmt = stmt.where(Chunk.modality.in_(list(modalities)))

            if denied_doc_ids:
                stmt = stmt.where(Chunk.doc_id.notin_(denied_doc_ids))

            if denied_tags:
                # Tags on the chunk metadata JSONB are stored as a list of strings
                # under the "tags" key.  Exclude chunks whose tag list overlaps.
                tag_values = [str(t).lower() for t in denied_tags]
                for tag in tag_values:
                    stmt = stmt.where(
                        ~Chunk.metadata_.op("@>")({"tags": [tag]})
                    )

            result = await db.execute(stmt)
            rows = result.all()

            hits: List[Dict[str, Any]] = []
            for row in rows:
                hits.append(
                    {
                        "chunk_id": str(row.id),
                        "doc_id": str(row.doc_id),
                        "kb_id": str(row.kb_id) if row.kb_id else None,
                        "content": row.content or "",
                        "modality": row.modality or "text",
                        "score": float(row.score or 0.0),
                    }
                )
            return hits
        except Exception as exc:
            logger.exception("BM25 search failed: %s", exc)
            return []

    async def update_tsv_for_kb(
        self,
        db: AsyncSession,
        kb_ids: Sequence[UUID | str],
    ) -> int:
        """(Re)build ``content_tsv`` for active chunks in given KBs.

        This is useful when ``content_tsv`` is out of sync or needs to be
        regenerated after bulk imports.  Returns the number of rows updated.
        """
        if not kb_ids:
            return 0

        try:
            stmt = (
                Chunk.__table__.update()
                .where(Chunk.doc_id == Document.id)
                .where(Document.kb_id.in_(list(kb_ids)))
                .where(Chunk.status == "active")
                .values(
                    content_tsv=func.to_tsvector(
                        self.ts_config, func.coalesce(Chunk.content, "")
                    )
                )
            )
            result = await db.execute(stmt)
            await db.commit()
            return result.rowcount or 0
        except Exception as exc:
            await db.rollback()
            logger.exception("Failed to update content_tsv: %s", exc)
            return 0


# Module-level singleton for convenience.
bm25_client = BM25Client()
