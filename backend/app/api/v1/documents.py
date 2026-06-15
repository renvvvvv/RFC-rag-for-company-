from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, Form, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.v1.auth import get_current_user
from app.schemas.user import UserResponse
from app.schemas.document import DocumentResponse, DocumentListResponse, DocumentLinkCreate
from app.services.document_service import DocumentService
from app.core.exceptions import NotFoundException
from app.workers.ingest_tasks import process_document
from app.core.exceptions import ValidationException

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: UUID = Form(...),
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """上传文档到指定知识库"""
    file_bytes = await file.read()
    metadata = {"tags": tags.split(",") if tags else []}
    
    service = DocumentService(db)
    doc = await service.upload_document(
        kb_id=kb_id,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
        created_by=current_user.id,
        metadata=metadata
    )
    
    # 异步触发摄取任务
    process_document.delay(str(doc.id))
    return doc

@router.post("/link", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_link_document(
    kb_id: UUID,
    link_data: DocumentLinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """创建链接文档"""
    service = DocumentService(db)
    doc = await service.create_link_document(
        kb_id=kb_id,
        link_data=link_data,
        created_by=current_user.id
    )
    process_document.delay(str(doc.id))
    return doc

@router.get("/{kb_id}", response_model=DocumentListResponse)
async def list_documents(
    kb_id: UUID,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """列出知识库下的文档"""
    service = DocumentService(db)
    total, items = await service.list_documents(kb_id, status, skip, limit)
    return DocumentListResponse(total=total, items=list(items))

@router.get("/detail/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """获取文档详情"""
    service = DocumentService(db)
    try:
        return await service.get_document(doc_id)
    except NotFoundException:
        raise HTTPException(status_code=404, detail="Document not found")

@router.delete("/detail/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """删除文档"""
    service = DocumentService(db)
    try:
        await service.delete_document(doc_id)
    except NotFoundException:
        raise HTTPException(status_code=404, detail="Document not found")
    return None


@router.post("/{doc_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """重新运行文档摄取流水线"""
    service = DocumentService(db)
    doc = await service.get_document(doc_id)

    if doc.status == "processing":
        raise ValidationException("文档正在处理中，请稍后再试")

    await service.update_status(
        doc_id,
        status="pending",
        processing_info={"reprocess_requested_by": str(current_user.id)},
    )
    process_document.delay(str(doc_id))
    return doc
