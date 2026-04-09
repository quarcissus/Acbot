"""
TenantService — CRUD de tenants.
Usado por el script CLI create_tenant.py y la API REST futura.
"""

import logging
import re
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantUpdate

logger = logging.getLogger(__name__)


class TenantNotFoundError(Exception):
    pass


class TenantAlreadyExistsError(Exception):
    pass


async def create_tenant(db: AsyncSession, data: TenantCreate) -> Tenant:
    """
    Crea un nuevo tenant (negocio cliente).
    
    Raises:
        TenantAlreadyExistsError: Si ya existe un tenant con el mismo slug o phone_number.
    """
    # Verificar duplicados
    existing = await db.execute(
        select(Tenant).where(
            (Tenant.slug == data.slug) | (Tenant.phone_number == data.phone_number)
        )
    )
    if existing.scalar_one_or_none():
        raise TenantAlreadyExistsError(
            f"Ya existe un tenant con slug='{data.slug}' o phone='{data.phone_number}'"
        )

    tenant = Tenant(**data.model_dump())
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    logger.info(f"Tenant creado: {tenant.slug} ({tenant.business_type})")
    return tenant


async def get_tenant_by_id(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    """
    Raises:
        TenantNotFoundError: Si no existe.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise TenantNotFoundError(f"Tenant {tenant_id} no encontrado")
    return tenant


async def get_tenant_by_slug(db: AsyncSession, slug: str) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise TenantNotFoundError(f"Tenant '{slug}' no encontrado")
    return tenant


async def list_tenants(db: AsyncSession) -> list[Tenant]:
    result = await db.execute(select(Tenant).order_by(Tenant.created_at))
    return list(result.scalars().all())


async def update_tenant(
    db: AsyncSession, tenant_id: uuid.UUID, data: TenantUpdate
) -> Tenant:
    tenant = await get_tenant_by_id(db, tenant_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(tenant, field, value)
    await db.commit()
    await db.refresh(tenant)
    return tenant


def slugify(name: str) -> str:
    """Convierte 'Barbería Don Pepe' → 'barberia-don-pepe'."""
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}
    result = name.lower()
    for char, replacement in replacements.items():
        result = result.replace(char, replacement)
    result = re.sub(r"[^a-z0-9\s-]", "", result)
    result = re.sub(r"[\s]+", "-", result.strip())
    return result
