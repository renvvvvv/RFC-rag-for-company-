from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    username: str
    email: EmailStr
    department: Optional[str] = None
    security_level: str = "L0"

class UserCreate(UserBase):
    password: str
    role_id: Optional[UUID] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    department: Optional[str] = None
    security_level: Optional[str] = None
    status: Optional[str] = None

class UserResponse(UserBase):
    id: UUID
    role_id: Optional[UUID]
    status: str
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
