"""
Auth — login y generación de JWT para el panel de control.
"""

import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from app.config.settings import settings
from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.api.deps import ALGORITHM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TOKEN_EXPIRE_HOURS = 8


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = TOKEN_EXPIRE_HOURS * 3600


# ── Helpers ───────────────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """
    Login con email y password. Retorna JWT válido por 8 horas.
    """
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == body.email, AdminUser.is_active == True)  # noqa: E712
    )
    admin = result.scalar_one_or_none()

    if not admin or not verify_password(body.password, admin.hashed_password):
        logger.warning(f"Login fallido para email: {body.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    token = create_access_token(str(admin.id))
    logger.info(f"Login exitoso: {admin.email}")
    return TokenResponse(access_token=token)


@router.post("/verify", tags=["auth"])
async def verify_token(
    db: AsyncSession = Depends(get_db),
    credentials = Depends(__import__("app.api.deps", fromlist=["bearer_scheme"]).bearer_scheme),
) -> dict:
    """Verifica si el token actual es válido. Útil para el frontend."""
    from app.api.deps import get_current_admin
    admin = await get_current_admin(credentials, db)
    return {"valid": True, "email": admin.email}