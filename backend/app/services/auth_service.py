from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, Token
from app.core.exceptions import AuthenticationException
from app.config import settings

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    
    async def create_user(self, user_data: UserCreate) -> User:
        # 检查用户名/邮箱是否已存在
        result = await self.db.execute(
            select(User).where(
                (User.username == user_data.username) | (User.email == user_data.email)
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise AuthenticationException("用户名或邮箱已存在")
        
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=self.hash_password(user_data.password),
            department=user_data.department,
            security_level=user_data.security_level,
            role_id=user_data.role_id,
            status="active"
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def authenticate_user(self, username: str, password: str) -> User:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user or not self.verify_password(password, user.password_hash):
            raise AuthenticationException("用户名或密码错误")
        
        if user.status != "active":
            raise AuthenticationException("用户已被禁用")
        
        return user
    
    def create_access_token(self, user_id: UUID) -> str:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "type": "access"
        }
        secret = settings.SECRET_KEY or settings.JWT_SECRET_KEY
        return jwt.encode(to_encode, secret, algorithm=settings.JWT_ALGORITHM)
    
    async def get_current_user(self, token: str) -> User:
        try:
            secret = settings.SECRET_KEY or settings.JWT_SECRET_KEY
            payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                raise AuthenticationException("无效的认证令牌")
        except JWTError:
            raise AuthenticationException("无效的认证令牌")
        
        result = await self.db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise AuthenticationException("用户不存在")
        
        return user
    
    async def get_user(self, user_id: UUID) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
