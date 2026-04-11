"""
Tenants API — listar y ver detalle de los negocios cliente.
"""

import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.tenant import Tenant
from app.api.deps import get_current_admin, get_tenant_by_slug
from app.models.admin_user import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    business_type: str
    phone_number: str
    bot_enabled: bool
    reminder_hours_before: int
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[TenantOut])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin),
) -> list[TenantOut]:
    """Lista todos los tenants (negocios cliente)."""
    result = await db.execute(select(Tenant).order_by(Tenant.name))
    return list(result.scalars().all())


@router.get("/{slug}", response_model=TenantOut)
async def get_tenant(
    slug: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> TenantOut:
    """Detalle de un tenant por slug."""
    return tenant