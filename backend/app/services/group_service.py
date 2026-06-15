from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.group import UserGroup
from app.schemas.group import UserGroupCreate, UserGroupUpdate, GroupMemberOperation
from app.core.exceptions import NotFoundException, ValidationException

class GroupService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_group(self, group_data: UserGroupCreate, created_by: UUID) -> UserGroup:
        group = UserGroup(
            name=group_data.name,
            description=group_data.description,
            group_type=group_data.group_type,
            parent_group_id=group_data.parent_group_id,
            member_ids=[str(mid) for mid in group_data.member_ids],
            admin_ids=[str(aid) for aid in group_data.admin_ids],
            max_security_level=group_data.max_security_level,
            created_by=str(created_by)
        )
        self.db.add(group)
        await self.db.commit()
        await self.db.refresh(group)
        return group
    
    async def get_group(self, group_id: UUID) -> UserGroup:
        result = await self.db.execute(
            select(UserGroup).where(UserGroup.id == group_id)
        )
        group = result.scalar_one_or_none()
        if not group:
            raise NotFoundException(f"用户群 {group_id} 不存在")
        return group
    
    async def list_groups(self, skip: int = 0, limit: int = 100) -> List[UserGroup]:
        result = await self.db.execute(
            select(UserGroup).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def update_group(self, group_id: UUID, group_data: UserGroupUpdate) -> UserGroup:
        group = await self.get_group(group_id)
        
        update_data = group_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field in ["member_ids", "admin_ids"] and value is not None:
                value = [str(v) for v in value]
            setattr(group, field, value)
        
        await self.db.commit()
        await self.db.refresh(group)
        return group
    
    async def delete_group(self, group_id: UUID):
        group = await self.get_group(group_id)
        await self.db.delete(group)
        await self.db.commit()
    
    async def add_members(self, group_id: UUID, operation: GroupMemberOperation):
        group = await self.get_group(group_id)
        current_members = set(group.member_ids or [])
        new_members = {str(uid) for uid in operation.user_ids}
        group.member_ids = list(current_members | new_members)
        await self.db.commit()
    
    async def remove_members(self, group_id: UUID, operation: GroupMemberOperation):
        group = await self.get_group(group_id)
        current_members = set(group.member_ids or [])
        remove_members = {str(uid) for uid in operation.user_ids}
        group.member_ids = list(current_members - remove_members)
        await self.db.commit()
    
    async def get_user_groups(self, user_id: UUID) -> List[UserGroup]:
        """获取用户所属的所有群（包含继承的父群）"""
        user_id_str = str(user_id)
        result = await self.db.execute(select(UserGroup))
        all_groups = result.scalars().all()
        
        user_groups = []
        for group in all_groups:
            if user_id_str in (group.member_ids or []):
                user_groups.append(group)
                # 添加父群
                parent = await self._get_parent_groups(group)
                user_groups.extend(parent)
        
        # 去重
        seen = set()
        unique_groups = []
        for g in user_groups:
            if str(g.id) not in seen:
                seen.add(str(g.id))
                unique_groups.append(g)
        
        return unique_groups
    
    async def _get_parent_groups(self, group: UserGroup) -> List[UserGroup]:
        """递归获取父群"""
        parents = []
        current_parent_id = group.parent_group_id
        while current_parent_id:
            result = await self.db.execute(
                select(UserGroup).where(UserGroup.id == UUID(current_parent_id))
            )
            parent = result.scalar_one_or_none()
            if parent:
                parents.append(parent)
                current_parent_id = parent.parent_group_id
            else:
                break
        return parents
