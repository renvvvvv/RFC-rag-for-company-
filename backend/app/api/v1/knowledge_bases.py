"""Knowledge base management endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.core.exceptions import NotFoundException, PermissionDeniedException
from app.database import get_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    KnowledgeBaseStats,
)
from app.schemas.user import UserResponse

router = APIRouter(tags=["knowledge-bases"])


def _require_kb_access(kb: KnowledgeBase, current_user: UserResponse) -> None:
    """Require that the current user owns the knowledge base.

    This is a simple ownership check; shared/member access can be layered on top
    via the permission service later.
    """
    if kb.owner_id and str(kb.owner_id) != str(current_user.id):
        raise PermissionDeniedException("没有权限访问该知识库")


@router.post(
    "/knowledge-bases",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Create a new knowledge base."""
    kb = KnowledgeBase(
        name=payload.name,
        description=payload.description,
        config=payload.config,
        owner_id=current_user.id,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """List knowledge bases the current user has access to."""
    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.owner_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a knowledge base by ID."""
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundException(f"Knowledge base {kb_id} not found")
    _require_kb_access(kb, current_user)
    return kb


@router.patch("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: UUID,
    payload: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Update a knowledge base."""
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundException(f"Knowledge base {kb_id} not found")
    _require_kb_access(kb, current_user)

    if payload.name is not None:
        kb.name = payload.name
    if payload.description is not None:
        kb.description = payload.description
    if payload.config is not None:
        kb.config = payload.config
    if payload.status is not None:
        kb.status = payload.status

    await db.commit()
    await db.refresh(kb)
    return kb


@router.delete("/knowledge-bases/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete a knowledge base (documents are cascaded)."""
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundException(f"Knowledge base {kb_id} not found")
    _require_kb_access(kb, current_user)
    await db.delete(kb)
    await db.commit()
    return None


@router.get("/knowledge-bases/{kb_id}/stats", response_model=KnowledgeBaseStats)
async def get_knowledge_base_stats(
    kb_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Return statistics for a knowledge base."""
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise NotFoundException(f"Knowledge base {kb_id} not found")
    _require_kb_access(kb, current_user)

    kb_id_str = str(kb_id)

    # Document count and status breakdown.
    doc_count_result = await db.execute(
        select(func.count(Document.id)).where(Document.kb_id == kb_id_str)
    )
    document_count = doc_count_result.scalar() or 0

    status_result = await db.execute(
        select(Document.status, func.count(Document.id))
        .where(Document.kb_id == kb_id_str)
        .group_by(Document.status)
    )
    status_breakdown = {status: count for status, count in status_result.all()}

    # Total chunk count.
    chunk_count_result = await db.execute(
        select(func.count(Chunk.id)).where(Chunk.doc_id.in_(
            select(Document.id).where(Document.kb_id == kb_id_str)
        ))
    )
    chunk_count = chunk_count_result.scalar() or 0

    # Last upload time.
    last_upload_result = await db.execute(
        select(func.max(Document.created_at)).where(Document.kb_id == kb_id_str)
    )
    last_upload_at = last_upload_result.scalar()

    return KnowledgeBaseStats(
        kb_id=kb_id,
        document_count=document_count,
        chunk_count=chunk_count,
        status_breakdown=status_breakdown,
        last_upload_at=last_upload_at,
    )
