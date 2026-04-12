"""
Staff Hours API — gestionar horarios de trabajo por barbero.
"""

import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_admin, get_tenant_by_slug
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{slug}/staff/{staff_id}/hours", tags=["staff-hours"])

WEEKDAY_NAMES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class StaffHoursOut(BaseModel):
    id: uuid.UUID
    weekday: int
    weekday_name: str
    is_working: bool
    start_time: str
    end_time: str
    clamped: bool = False  # True si el horario fue ajustado por business_hours
    model_config = {"from_attributes": True}


class StaffHoursUpdate(BaseModel):
    is_working: bool
    start_time: str  # "HH:MM"
    end_time: str    # "HH:MM"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_staff_or_404(db, tenant_id, staff_id):
    from sqlalchemy import select, and_
    from app.models.staff import Staff
    result = await db.execute(
        select(Staff).where(and_(Staff.id == staff_id, Staff.tenant_id == tenant_id))
    )
    staff = result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Barbero no encontrado")
    return staff


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[StaffHoursOut])
async def get_staff_hours(
    slug: str,
    staff_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> list[StaffHoursOut]:
    """Retorna los 7 días con el horario del barbero."""
    from app.services.staff_hours_service import get_staff_hours as _get
    await _get_staff_or_404(db, tenant.id, staff_id)
    hours = await _get(db, staff_id, tenant.id)
    return [
        StaffHoursOut(
            id=h.id,
            weekday=h.weekday,
            weekday_name=WEEKDAY_NAMES.get(h.weekday, f"Día {h.weekday}"),
            is_working=h.is_working,
            start_time=h.start_time,
            end_time=h.end_time,
        )
        for h in hours
    ]


@router.patch("/{weekday}", response_model=StaffHoursOut)
async def update_staff_day(
    slug: str,
    staff_id: uuid.UUID,
    weekday: int,
    body: StaffHoursUpdate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> StaffHoursOut:
    """
    Actualiza el horario de un día para un barbero.
    Ajusta automáticamente si excede el horario del negocio.
    """
    if weekday not in range(7):
        raise HTTPException(status_code=422, detail="weekday debe ser 0-6")

    from app.services.staff_hours_service import update_staff_day as _update

    await _get_staff_or_404(db, tenant.id, staff_id)

    original_start = body.start_time
    original_end = body.end_time

    h = await _update(
        db=db,
        staff_id=staff_id,
        tenant_id=tenant.id,
        weekday=weekday,
        is_working=body.is_working,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    await db.commit()

    # Detectar si el horario fue ajustado
    clamped = (h.start_time != original_start or h.end_time != original_end)
    if clamped:
        logger.info(f"Horario ajustado por business_hours: {original_start}-{original_end} → {h.start_time}-{h.end_time}")

    return StaffHoursOut(
        id=h.id,
        weekday=h.weekday,
        weekday_name=WEEKDAY_NAMES.get(h.weekday, f"Día {h.weekday}"),
        is_working=h.is_working,
        start_time=h.start_time,
        end_time=h.end_time,
        clamped=clamped,
    )