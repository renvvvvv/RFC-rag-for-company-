"""Sensitive keyword management endpoints."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.database import get_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.schemas.keyword import (
    SensitiveKeywordCreate,
    SensitiveKeywordResponse,
    SensitiveKeywordUpdate,
    SensitiveScanRequest,
    SensitiveScanResponse,
)
from app.services.keyword_service import KeywordService
from app.services.sensitive_info_service import SensitiveInfoService

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


@router.post("/keywords/scan", response_model=SensitiveScanResponse)
async def scan_text_or_document(
    payload: SensitiveScanRequest,
    db: AsyncSession = Depends(get_db),
):
    """Scan provided text or an existing document for sensitive information."""
    svc = SensitiveInfoService(db)

    if payload.text:
        findings = await svc.scan_text(payload.text)
        masked = svc.mask_text(payload.text, findings)
        return SensitiveScanResponse(
            findings=findings,
            masked_text=masked,
            summary={
                "total": len(findings),
                "by_type": _count_by(findings, "type"),
                "by_label": _count_by(findings, "label"),
            },
        )

    if payload.document_id:
        document = await db.get(Document, payload.document_id)
        if document is None:
            raise NotFoundException(f"Document {payload.document_id} not found")

        result = await db.execute(
            select(Chunk).where(Chunk.doc_id == str(payload.document_id))
        )
        chunks = result.scalars().all()
        chunks_content = [c.content or "" for c in chunks]

        findings = await svc.scan_document_content(payload.document_id, chunks_content)
        summary = {
            "total": len(findings),
            "chunks_scanned": len(chunks_content),
            "chunks_with_findings": len(
                {f.get("chunk_index") for f in findings if f.get("chunk_index") is not None}
            ),
            "by_type": _count_by(findings, "type"),
            "by_label": _count_by(findings, "label"),
        }
        return SensitiveScanResponse(
            document_id=payload.document_id,
            findings=findings,
            summary=summary,
        )

    raise ValidationException("Either text or document_id must be provided")


def _count_by(findings: List[dict], key: str) -> dict:
    counts: dict = {}
    for finding in findings:
        counts[finding.get(key, "unknown")] = counts.get(finding.get(key, "unknown"), 0) + 1
    return counts
