from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.services.auth_service import AuthService
from app.services.api_key_service import ApiKeyService
from app.models.api_key import ApiKey
from app.schemas.user import UserCreate, UserResponse, UserLogin, Token
from app.core.exceptions import AuthenticationException, AuthorizationException

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
    # Public registration is always limited to the lowest security level.
    # Higher levels must be assigned by an administrator via /users.
    user_data.security_level = "L0"
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


# --------------------------------------------------------------------------- #
# API Key authentication (used by external /api/v1/external/* endpoints)
# --------------------------------------------------------------------------- #

def _extract_api_key(request: Request) -> str:
    """Read an API key from the ``X-API-Key`` header or ``Authorization: Bearer``."""
    if key := request.headers.get("x-api-key"):
        return key.strip()

    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token.strip()

    raise AuthenticationException("API key required")


async def get_current_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """Authenticate the request using an API key.

    Returns the ``ApiKey`` record after validating the key, rate limits, and
    expiration. Raises ``HTTPException(401)`` on failure.
    """
    service = ApiKeyService(db)
    try:
        plain_key = _extract_api_key(request)
        return await service.authenticate_key(plain_key)
    except AuthenticationException as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


async def get_current_api_key_user(
    api_key: ApiKey = Depends(get_current_api_key),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Return the API key owner as a ``UserResponse``.

    Business endpoints should use this dependency so they can reuse existing
    permission services that expect a ``user_id``.
    """
    service = ApiKeyService(db)
    try:
        owner = await service.load_owner(api_key)
        return UserResponse.model_validate(owner)
    except AuthenticationException as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


def require_api_scope(scope: str):
    """Dependency factory that ensures the API key includes ``scope``."""

    async def _check_scope(api_key: ApiKey = Depends(get_current_api_key)) -> ApiKey:
        if not ApiKeyService.key_has_scope(api_key, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {scope}",
            )
        return api_key

    return _check_scope
