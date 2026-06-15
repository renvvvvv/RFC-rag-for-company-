from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    username: str
    email: EmailStr
    display_name: Optional[str] = None
    department: Optional[str] = None
    security_level: str = "L0"


class UserCreate(UserBase):
    password: str
    role_id: Optional[UUID] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    department: Optional[str] = None
    security_level: Optional[str] = Field(default=None, pattern=r"^L[0-4]$")
    role_id: Optional[UUID] = None
    status: Optional[str] = Field(default=None, pattern=r"^(active|inactive|locked)$")
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: UUID
    role_id: Optional[UUID] = None
    status: str
    is_active: bool

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
