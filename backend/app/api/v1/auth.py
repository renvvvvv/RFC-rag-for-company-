from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate, UserResponse, UserLogin, Token
from app.core.exceptions import AuthenticationException

router = APIRouter(prefix="/auth", tags=["认证"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def is_admin(user: UserResponse) -> bool:
    """Return True if the user is considered an administrator.

    The built-in admin username is always treated as admin; additional usernames
    can be configured via the ADMIN_USERNAMES environment variable (comma-separated).
    """
    admin_names = {
        name.strip()
        for name in (settings.ADMIN_USERNAMES or "admin").split(",")
        if name.strip()
    }
    return user.username in admin_names


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    auth_service = AuthService(db)
    try:
        user = await auth_service.get_current_user(token)
        return UserResponse.model_validate(user)
    except AuthenticationException as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)
    try:
        user = await auth_service.create_user(user_data)
        return UserResponse.model_validate(user)
    except AuthenticationException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    auth_service = AuthService(db)
    try:
        user = await auth_service.authenticate_user(form_data.username, form_data.password)
        access_token = auth_service.create_access_token(user.id)
        return Token(
            access_token=access_token,
            user=UserResponse.model_validate(user)
        )
    except AuthenticationException as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/me", response_model=UserResponse)
async def me(current_user: UserResponse = Depends(get_current_user)):
    return current_user
