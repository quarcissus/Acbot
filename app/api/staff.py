"""
Staff API — gestionar empleados de un tenant.
"""

import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from app.core.database import get_db
from app.models.staff import Staff
from app.models.tenant import Tenant
from app.api.deps import get_current_admin, get_tenant_by_slug
from app.models.admin_user import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{slug}/staff", tags=["staff"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class StaffOut(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    is_active: bool
    appointment_duration: int

    model_config = {"from_attributes": True}


class StaffCreate(BaseModel):
    name: str
    role: str = "barbero"
    appointment_duration: int = 30


class StaffUpdate(BaseModel):
    is_active: bool | None = None
    appointment_duration: int | None = None
    role: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[StaffOut])
async def list_staff(
    slug: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> list[StaffOut]:
    """Lista todo el staff de un tenant (activos e inactivos)."""
    result = await db.execute(
        select(Staff)
        .where(Staff.tenant_id == tenant.id)
        .order_by(Staff.name)
    )
    return list(result.scalars().all())


@router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
async def create_staff(
    slug: str,
    body: StaffCreate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> StaffOut:
    """Agrega un nuevo empleado al tenant."""
    staff = Staff(
        tenant_id=tenant.id,
        name=body.name.strip().title(),
        role=body.role,
        appointment_duration=body.appointment_duration,
    )
    db.add(staff)
    await db.flush()
    await db.refresh(staff)
    logger.info(f"Staff creado: {staff.name} para tenant {slug}")
    return staff


@router.patch("/{staff_id}", response_model=StaffOut)
async def update_staff(
    slug: str,
    staff_id: uuid.UUID,
    body: StaffUpdate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> StaffOut:
    """Actualiza datos de un empleado (activar, desactivar, cambiar duración)."""
    result = await db.execute(
        select(Staff).where(
            and_(Staff.id == staff_id, Staff.tenant_id == tenant.id)
        )
    )
    staff = result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    if body.is_active is not None:
        staff.is_active = body.is_active
    if body.appointment_duration is not None:
        staff.appointment_duration = body.appointment_duration
    if body.role is not None:
        staff.role = body.role

    await db.flush()
    logger.info(f"Staff {staff.name} actualizado en tenant {slug}")
    return staff