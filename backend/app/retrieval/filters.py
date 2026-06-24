"""Backend-neutral permission filter for vector stores.

``VectorFilter`` captures the same ACL rules as the legacy Milvus expression
builder but can be translated into either a Milvus boolean expression or a list
of SQLAlchemy WHERE clauses for pgvector.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import ARRAY


@dataclass
class VectorFilter:
    """Permission-aware filter shared across vector store backends."""

    kb_ids: List[str]
    modalities: List[str]
    denied_doc_ids: List[str] = field(default_factory=list)
    denied_tags: List[str] = field(default_factory=list)
    status: str = "active"

    def to_milvus_expr(self) -> str:
        """Translate the filter into a Milvus boolean expression string."""
        conditions: List[str] = []

        if self.status:
            conditions.append(f"status == '{self.status}'")

        if self.kb_ids:
            kb_list = ", ".join(f'"{str(k)}"' for k in self.kb_ids)
            conditions.append(f"kb_id in [{kb_list}]")

        if self.modalities:
            type_list = ", ".join(f'"{t}"' for t in self.modalities)
            conditions.append(f"modality in [{type_list}]")

        if self.denied_doc_ids:
            doc_list = ", ".join(f'"{d}"' for d in self.denied_doc_ids)
            conditions.append(f"doc_id not in [{doc_list}]")

        for tag in self.denied_tags:
            conditions.append(f"array_not_contains(tags, '{tag}')")

        if not conditions:
            return ""

        return " and ".join(f"({c})" for c in conditions)

    def to_sqlalchemy(self, table: Any) -> List[Any]:
        """Return a list of SQLAlchemy WHERE clauses for the given table/model.

        *table* is expected to expose the columns used by the filter:
        ``status``, ``kb_id``, ``modality``, ``doc_id`` and ``tags``.
        Callers can combine the returned clauses with ``and_(*clauses)``.
        """
        clauses: List[Any] = []

        if self.status:
            clauses.append(table.status == self.status)

        if self.kb_ids:
            clauses.append(table.kb_id.in_(self.kb_ids))

        if self.modalities:
            clauses.append(table.modality.in_(self.modalities))

        if self.denied_doc_ids:
            clauses.append(~table.doc_id.in_(self.denied_doc_ids))

        if self.denied_tags and hasattr(table, "tags"):
            # tags is a PostgreSQL ARRAY(String). Reject rows whose tags array
            # contains any of the denied tag IDs: tags @> ARRAY[tag] is false.
            for tag in self.denied_tags:
                if isinstance(table.tags.type, ARRAY):
                    clauses.append(~table.tags.contains([tag]))
                else:
                    clauses.append(table.tags != tag)

        return clauses

    def apply_to_query(self, query: Any, table: Any) -> Any:
        """Convenience helper: apply ``to_sqlalchemy`` clauses to a query."""
        clauses = self.to_sqlalchemy(table)
        if clauses:
            return query.where(and_(*clauses))
        return query
