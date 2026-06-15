"""Sensitive keyword management endpoints."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.database import get_db
from app.schemas.keyword import (
    SensitiveKeywordCreate,
    SensitiveKeywordResponse,
    SensitiveKeywordUpdate,
)
from app.services.keyword_service import KeywordService

router = APIRouter(tags=["keywords"])


async def get_keyword_service(
    db: AsyncSession = Depends(get_db),
) -> KeywordService:
    return KeywordService(db)


@router.get("/keywords", response_model=List[SensitiveKeywordResponse])
async def list_keywords(
    category: Optional[str] = Query(None, description="按分类过滤"),
    level: Optional[str] = Query(None, description="按敏感等级过滤，如 L1"),
    service: KeywordService = Depends(get_keyword_service),
):
    """List sensitive keywords with optional filters."""
    if level and level not in {"L0", "L1", "L2", "L3", "L4"}:
        raise ValidationException("level must be one of L0-L4")
    return await service.list_keywords(category=category, level=level)


@router.post(
    "/keywords",
    response_model=SensitiveKeywordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_keyword(
    data: SensitiveKeywordCreate,
    service: KeywordService = Depends(get_keyword_service),
):
    """Create a new sensitive keyword."""
    return await service.create_keyword(data)


@router.put("/keywords/{keyword_id}", response_model=SensitiveKeywordResponse)
async def update_keyword(
    keyword_id: UUID,
    data: SensitiveKeywordUpdate,
    service: KeywordService = Depends(get_keyword_service),
):
    """Update an existing sensitive keyword."""
    try:
        return await service.update_keyword(keyword_id, data)
    except NotFoundException:
        raise


@router.delete("/keywords/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    keyword_id: UUID,
    service: KeywordService = Depends(get_keyword_service),
):
    """Delete a sensitive keyword."""
    await service.delete_keyword(keyword_id)
    return None


@router.post(
    "/keywords/batch-import",
    response_model=List[SensitiveKeywordResponse],
    status_code=status.HTTP_201_CREATED,
)
async def batch_import_keywords(
    items: List[SensitiveKeywordCreate],
    service: KeywordService = Depends(get_keyword_service),
):
    """Batch import sensitive keywords."""
    created = []
    for item in items:
        created.append(await service.create_keyword(item))
    return created
