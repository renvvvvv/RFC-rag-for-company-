from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.permission_service import PermissionService
from app.services.auth_service import AuthService
from app.core.cache import CacheManager
from app.schemas.permission import (
    FileTypePermissionCreate, DocumentPermissionCreate,
    FieldPermissionCreate, TagPermissionCreate, PermissionCheckResponse
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/permissions", tags=["权限管理"])

async def get_permission_service(db: AsyncSession = Depends(get_db)):
    cache = CacheManager()
    return PermissionService(db, cache)

@router.post("/file-type")
async def set_file_type_permission(
    perm_data: FileTypePermissionCreate,
    db: AsyncSession = Depends(get_db)
):
    # 简化实现：直接创建记录
    from app.models.permission import FileTypePermission
    perm = FileTypePermission(**perm_data.model_dump())
    db.add(perm)
    await db.commit()
    return {"message": "文件类型权限设置成功"}

@router.post("/document")
async def set_document_permission(
    perm_data: DocumentPermissionCreate,
    db: AsyncSession = Depends(get_db)
):
    from app.models.permission import DocumentPermission
    perm = DocumentPermission(**perm_data.model_dump())
    db.add(perm)
    await db.commit()
    return {"message": "文档权限设置成功"}

@router.post("/field")
async def set_field_permission(
    perm_data: FieldPermissionCreate,
    db: AsyncSession = Depends(get_db)
):
    from app.models.permission import FieldPermission
    perm = FieldPermission(**perm_data.model_dump())
    db.add(perm)
    await db.commit()
    return {"message": "字段权限设置成功"}

@router.post("/tag")
async def set_tag_permission(
    perm_data: TagPermissionCreate,
    db: AsyncSession = Depends(get_db)
):
    from app.models.permission import TagPermission
    perm = TagPermission(**perm_data.model_dump())
    db.add(perm)
    await db.commit()
    return {"message": "标签权限设置成功"}

@router.get("/check/{doc_id}", response_model=PermissionCheckResponse)
async def check_permission(
    doc_id: UUID,
    service: PermissionService = Depends(get_permission_service),
    current_user: UserResponse = Depends(AuthService.get_current_user)
):
    perm = await service.check_document_permission(current_user.id, doc_id)
    level = await service.get_user_security_level(current_user.id)
    return PermissionCheckResponse(
        doc_id=doc_id,
        permission=perm,
        security_level=level
    )
