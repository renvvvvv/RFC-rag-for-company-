from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.v1.auth import get_current_user, is_admin
from app.core.exceptions import NotFoundException, PermissionDeniedException, ValidationException
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["用户管理"])


def _require_admin(current_user: UserResponse) -> None:
    if not is_admin(current_user):
        raise PermissionDeniedException("需要管理员权限")


@router.get("", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """列出用户（管理员）"""
    _require_admin(current_user)
    result = await db.execute(select(User).offset(skip).limit(limit))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """获取用户信息（管理员或本人）"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not is_admin(current_user) and str(current_user.id) != str(user_id):
        raise PermissionDeniedException("没有权限查看该用户")
    return UserResponse.model_validate(user)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """创建用户（管理员入口，与 /auth/register 等价）"""
    _require_admin(current_user)
    auth_service = AuthService(db)
    try:
        user = await auth_service.create_user(user_data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """更新用户信息：角色、部门、显示名、激活状态等（管理员）"""
    _require_admin(current_user)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_data.model_dump(exclude_unset=True)

    # 不允许通过此接口修改密码
    update_data.pop("password", None)

    if "is_active" in update_data:
        user.is_active = update_data.pop("is_active")
        # 保持 status 字段与 is_active 同步
        user.status = "active" if user.is_active else "inactive"

    for field, value in update_data.items():
        if hasattr(user, field):
            setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """删除用户（管理员）"""
    _require_admin(current_user)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return None
