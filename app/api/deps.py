"""
Dependencias compartidas de la API REST.
Provee: autenticación JWT y obtención de tenant por slug.
"""

import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError, jwt

from app.config.settings import settings
from app.core.database import get_db
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Algoritmo y configuración JWT
ALGORITHM = "HS256"
bearer_scheme = HTTPBearer()


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """
    Dependencia que valida el JWT y retorna el AdminUser autenticado.
    Usar con: admin: AdminUser = Depends(get_current_admin)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(
        select(AdminUser).where(AdminUser.id == user_id, AdminUser.is_active == True)  # noqa: E712
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise credentials_exception

    return admin


async def get_tenant_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> Tenant:
    """
    Dependencia que obtiene un tenant por slug.
    Requiere autenticación. Retorna 404 si no existe.
    """
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{slug}' no encontrado",
        )
    return tenant