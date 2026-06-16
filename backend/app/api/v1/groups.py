from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.group_service import GroupService
from app.api.v1.auth import get_current_user
from app.schemas.group import (
    UserGroupCreate, UserGroupUpdate, UserGroupResponse, GroupMemberOperation
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/groups", tags=["用户群"])

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
    db: AsyncSession = Depends(get_db)
):
    service = GroupService(db)
    groups = await service.list_groups(skip, limit)
    return [UserGroupResponse.model_validate(g) for g in groups]

@router.get("/{group_id}", response_model=UserGroupResponse)
async def get_group(group_id: UUID, db: AsyncSession = Depends(get_db)):
    service = GroupService(db)
    group = await service.get_group(group_id)
    return UserGroupResponse.model_validate(group)

@router.put("/{group_id}", response_model=UserGroupResponse)
async def update_group(
    group_id: UUID,
    group_data: UserGroupUpdate,
    db: AsyncSession = Depends(get_db)
):
    service = GroupService(db)
    group = await service.update_group(group_id, group_data)
    return UserGroupResponse.model_validate(group)

@router.delete("/{group_id}")
async def delete_group(group_id: UUID, db: AsyncSession = Depends(get_db)):
    service = GroupService(db)
    await service.delete_group(group_id)
    return {"message": "删除成功"}

@router.post("/{group_id}/members")
async def add_members(
    group_id: UUID,
    operation: GroupMemberOperation,
    db: AsyncSession = Depends(get_db)
):
    service = GroupService(db)
    await service.add_members(group_id, operation)
    return {"message": "成员添加成功"}

@router.delete("/{group_id}/members")
async def remove_members(
    group_id: UUID,
    operation: GroupMemberOperation,
    db: AsyncSession = Depends(get_db)
):
    service = GroupService(db)
    await service.remove_members(group_id, operation)
    return {"message": "成员移除成功"}
