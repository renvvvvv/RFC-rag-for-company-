from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.group_service import GroupService
from app.api.v1.auth import get_current_user, is_admin
from app.core.exceptions import NotFoundException, PermissionDeniedException
from app.models.group import UserGroup
from app.schemas.group import (
    UserGroupCreate, UserGroupUpdate, UserGroupResponse, GroupMemberOperation
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/groups", tags=["用户群"])


def _require_group_admin(group: UserGroup, current_user: UserResponse) -> None:
    """Require system admin, group creator, or group admin."""
    if is_admin(current_user):
        return
    user_id = str(current_user.id)
    if user_id == str(group.created_by):
        return
    if user_id in (group.admin_ids or []):
        return
    raise PermissionDeniedException("需要组管理员或系统管理员权限")


@router.post("", response_model=UserGroupResponse)
async def create_group(
    group_data: UserGroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    service = GroupService(db)
    group = await service.create_group(group_data, current_user.id)
    return UserGroupResponse.model_validate(group)

@router.get("", response_model=List[UserGroupResponse])
async def list_groups(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    service = GroupService(db)
    groups = await service.list_groups(skip, limit)
    return [UserGroupResponse.model_validate(g) for g in groups]

@router.get("/{group_id}", response_model=UserGroupResponse)
async def get_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    service = GroupService(db)
    group = await service.get_group(group_id)
    return UserGroupResponse.model_validate(group)

@router.put("/{group_id}", response_model=UserGroupResponse)
async def update_group(
    group_id: UUID,
    group_data: UserGroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    service = GroupService(db)
    group = await service.get_group(group_id)
    _require_group_admin(group, current_user)
    updated = await service.update_group(group_id, group_data)
    return UserGroupResponse.model_validate(updated)

@router.delete("/{group_id}")
async def delete_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    service = GroupService(db)
    group = await service.get_group(group_id)
    _require_group_admin(group, current_user)
    await service.delete_group(group_id)
    return {"message": "删除成功"}

@router.post("/{group_id}/members")
async def add_members(
    group_id: UUID,
    operation: GroupMemberOperation,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    service = GroupService(db)
    group = await service.get_group(group_id)
    _require_group_admin(group, current_user)
    await service.add_members(group_id, operation)
    return {"message": "成员添加成功"}

@router.delete("/{group_id}/members")
async def remove_members(
    group_id: UUID,
    operation: GroupMemberOperation,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    service = GroupService(db)
    group = await service.get_group(group_id)
    _require_group_admin(group, current_user)
    await service.remove_members(group_id, operation)
    return {"message": "成员移除成功"}
