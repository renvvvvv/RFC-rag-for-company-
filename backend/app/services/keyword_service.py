"""Sensitive keyword business logic and access control."""
import uuid
from dataclasses import dataclass
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.metrics import rag_permission_intercepts_total
from app.models.chunk import Chunk
from app.models.keyword import KeywordMatchLog, SensitiveKeyword
from app.models.user import User
from app.pipelines.keyword_annotator import KeywordAnnotator, LEVEL_ORDER
from app.schemas.keyword import SensitiveKeywordCreate, SensitiveKeywordUpdate


@dataclass
class InterceptResult:
    """Outcome of ``intercept_response``."""

    allowed: bool
    message: Optional[str] = None
    violated_matches: List = None

    def __post_init__(self):
        if self.violated_matches is None:
            self.violated_matches = []


class KeywordService:
    """Service layer for sensitive keyword CRUD and runtime control."""

    # Friendly message; never includes the actual keyword.
    INTERCEPT_MESSAGE = (
        "回答可能包含超出您权限等级的敏感信息，已被拦截。"
        "如需访问，请联系管理员申请提升安全等级。"
    )
    CONTEXT_VIOLATION_MESSAGE = (
        "引用的知识片段包含超出您权限等级的敏感信息，已被拦截。"
    )

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._annotator: Optional[KeywordAnnotator] = None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    async def create_keyword(
        self, data: "SensitiveKeywordCreate"
    ) -> SensitiveKeyword:
        """Create a new sensitive keyword."""
        keyword = SensitiveKeyword(**data.model_dump())
        self.db.add(keyword)
        await self.db.commit()
        await self.db.refresh(keyword)
        self._annotator = None  # invalidate cache
        from app.services.generation_service import GenerationService
        GenerationService.reset_stream_annotator()
        return keyword

    async def update_keyword(
        self, keyword_id: uuid.UUID, data: "SensitiveKeywordUpdate"
    ) -> SensitiveKeyword:
        """Update an existing keyword and re-annotate affected chunks."""
        keyword = await self._get_keyword_or_raise(keyword_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field in ("variants", "apply_to_modalities") and value is None:
                value = []
            setattr(keyword, field, value)

        await self.db.commit()
        await self.db.refresh(keyword)
        self._annotator = None  # invalidate cache
        from app.services.generation_service import GenerationService
        GenerationService.reset_stream_annotator()

        # Re-evaluate chunks that previously referenced this keyword.
        await self.reannotate_chunks_for_keyword(keyword_id)
        return keyword

    async def delete_keyword(self, keyword_id: uuid.UUID) -> None:
        """Delete a sensitive keyword."""
        keyword = await self._get_keyword_or_raise(keyword_id)
        await self.db.delete(keyword)
        await self.db.commit()
        self._annotator = None  # invalidate cache
        from app.services.generation_service import GenerationService
        GenerationService.reset_stream_annotator()

    async def list_keywords(
        self,
        category: Optional[str] = None,
        level: Optional[str] = None,
    ) -> List[SensitiveKeyword]:
        """List sensitive keywords with optional filters."""
        stmt = select(SensitiveKeyword)
        if category:
            stmt = stmt.where(SensitiveKeyword.category == category)
        if level:
            stmt = stmt.where(SensitiveKeyword.level == level)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_keyword_or_raise(self, keyword_id: uuid.UUID) -> SensitiveKeyword:
        keyword = await self.db.get(SensitiveKeyword, keyword_id)
        if keyword is None:
            raise NotFoundException(f"Sensitive keyword {keyword_id} not found")
        return keyword

    # ------------------------------------------------------------------
    # Annotation / access control
    # ------------------------------------------------------------------
    async def _get_annotator(self) -> KeywordAnnotator:
        """Return a ready-to-use ``KeywordAnnotator`` built from DB keywords."""
        if self._annotator is None:
            keywords = await self.list_keywords()
            self._annotator = KeywordAnnotator()
            self._annotator.load_keywords(keywords)
        return self._annotator

    async def annotate_chunk(self, chunk: Chunk) -> Chunk:
        """Annotate a chunk and write match logs."""
        if chunk is None:
            return chunk

        annotator = await self._get_annotator()
        annotator.annotate_chunk(chunk)

        result = annotator.last_annotation_result
        if result and result.matches:
            await self._log_matches("chunk", chunk.id, result.matches)

        await self.db.flush()
        return chunk

    def check_chunk_level(
        self, chunk: Chunk, user_level: str
    ) -> Tuple[bool, Optional[str]]:
        """Return (is_accessible, reason) for a user accessing ``chunk``."""
        if chunk is None:
            return True, None

        metadata = chunk.metadata_ or {}
        chunk_level = metadata.get("max_keyword_level") or "L0"
        user_value = LEVEL_ORDER.get(user_level, -1)
        chunk_value = LEVEL_ORDER.get(chunk_level, -1)

        if chunk_value <= user_value:
            return True, None
        return (
            False,
            f"该片段的敏感等级为 {chunk_level}，高于您的访问等级 {user_level}。",
        )

    async def intercept_response(
        self,
        answer: str,
        context_chunks: Optional[List[Chunk]],
        user_id: uuid.UUID,
    ) -> InterceptResult:
        """Check whether a generated answer is allowed for ``user_id``.

        The check covers both the answer text itself and the retrieved
        context chunks.  Specific keywords are never exposed to the caller.
        """
        annotator = await self._get_annotator()
        answer_result = annotator.annotate(answer or "")
        if answer_result.matches:
            await self._log_matches("response", None, answer_result.matches)

        user_level = await self._get_user_level(user_id)
        user_value = LEVEL_ORDER.get(user_level, -1)

        # 1. Does the answer directly contain higher-level keywords?
        over_level = [
            m
            for m in answer_result.matches
            if LEVEL_ORDER.get(m.level, -1) > user_value
        ]
        if over_level:
            rag_permission_intercepts_total.labels(
                reason="response_keyword_level"
            ).inc()
            return InterceptResult(
                allowed=False,
                message=self.INTERCEPT_MESSAGE,
                violated_matches=over_level,
            )

        # 2. Do any referenced chunks exceed the user's clearance?
        for chunk in context_chunks or []:
            metadata = chunk.metadata_ or {}
            chunk_level = metadata.get("max_keyword_level") or "L0"
            if LEVEL_ORDER.get(chunk_level, -1) > user_value:
                rag_permission_intercepts_total.labels(
                    reason="context_keyword_level"
                ).inc()
                return InterceptResult(
                    allowed=False,
                    message=self.CONTEXT_VIOLATION_MESSAGE,
                    violated_matches=[],
                )

        return InterceptResult(allowed=True)

    async def reannotate_chunks_for_keyword(
        self, keyword_id: uuid.UUID
    ) -> int:
        """Re-annotate chunks previously tagged with ``keyword_id``.

        Returns the number of chunks re-evaluated.
        """
        stmt = select(Chunk).where(
            Chunk.metadata_.op("@>")(
                {"sensitive_keywords": [str(keyword_id)]}
            )
        )
        result = await self.db.execute(stmt)
        chunks = result.scalars().all()

        annotator = await self._get_annotator()
        for chunk in chunks:
            annotator.annotate_chunk(chunk)
            res = annotator.last_annotation_result
            if res and res.matches:
                await self._log_matches("chunk", chunk.id, res.matches)

        await self.db.commit()
        return len(chunks)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_user_level(self, user_id: uuid.UUID) -> str:
        user = await self.db.get(User, user_id)
        if user is None:
            return "L0"
        return user.security_level or "L0"

    async def _log_matches(
        self,
        source_type: str,
        source_id: Optional[uuid.UUID],
        matches: List,
    ) -> None:
        """Persist keyword match audit logs."""
        for m in matches:
            log = KeywordMatchLog(
                keyword_id=m.keyword_id,
                source_type=source_type,
                source_id=source_id,
                matched_text=m.matched_text,
                matched_variant=m.matched_variant,
                confidence=m.confidence,
            )
            self.db.add(log)
        await self.db.flush()
