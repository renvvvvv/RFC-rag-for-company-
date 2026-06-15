from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

class UserGroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    group_type: str = "custom"
    max_security_level: str = "L0"

class UserGroupCreate(UserGroupBase):
    parent_group_id: Optional[UUID] = None
    member_ids: List[UUID] = []
    admin_ids: List[UUID] = []

class UserGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_security_level: Optional[str] = None
    parent_group_id: Optional[UUID] = None
    member_ids: Optional[List[UUID]] = None
    admin_ids: Optional[List[UUID]] = None

class UserGroupResponse(UserGroupBase):
    id: UUID
    parent_group_id: Optional[UUID]
    member_count: int
    admin_count: int
    created_by: UUID
    
    class Config:
        from_attributes = True

class GroupMemberOperation(BaseModel):
    user_ids: List[UUID]
