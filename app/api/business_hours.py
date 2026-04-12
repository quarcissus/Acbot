"""
Business Hours API — gestionar horarios de atención por tenant.
Accesible tanto por el admin de Acvex como por el cliente (con su propio JWT futuro).
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

router = APIRouter(prefix="/api/tenants/{slug}/hours", tags=["hours"])

WEEKDAY_NAMES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class BusinessHoursOut(BaseModel):
    id: uuid.UUID
    weekday: int
    weekday_name: str
    is_open: bool
    open_time: str
    close_time: str

    model_config = {"from_attributes": True}


class BusinessHoursUpdate(BaseModel):
    is_open: bool
    open_time: str   # "HH:MM"
    close_time: str  # "HH:MM"


class BusinessHoursBulkUpdate(BaseModel):
    hours: list[BusinessHoursUpdate]  # 7 items, índice = weekday (0=Lunes)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[BusinessHoursOut])
async def get_hours(
    slug: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> list[BusinessHoursOut]:
    """Retorna los 7 días con sus horarios. Crea defaults si no existen."""
    from app.services.business_hours_service import get_business_hours
    hours = await get_business_hours(db, tenant.id)
    return [
        BusinessHoursOut(
            id=h.id,
            weekday=h.weekday,
            weekday_name=WEEKDAY_NAMES.get(h.weekday, f"Día {h.weekday}"),
            is_open=h.is_open,
            open_time=h.open_time,
            close_time=h.close_time,
        )
        for h in hours
    ]


@router.patch("/{weekday}", response_model=BusinessHoursOut)
async def update_day(
    slug: str,
    weekday: int,
    body: BusinessHoursUpdate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> BusinessHoursOut:
    """Actualiza el horario de un día específico (0=Lunes, 6=Domingo)."""
    if weekday not in range(7):
        raise HTTPException(status_code=422, detail="weekday debe ser 0-6")

    from app.services.business_hours_service import update_day_hours
    h = await update_day_hours(
        db=db,
        tenant_id=tenant.id,
        weekday=weekday,
        is_open=body.is_open,
        open_time=body.open_time,
        close_time=body.close_time,
    )
    await db.commit()

    logger.info(f"Horario {WEEKDAY_NAMES[weekday]} actualizado para tenant {slug}")

    return BusinessHoursOut(
        id=h.id,
        weekday=h.weekday,
        weekday_name=WEEKDAY_NAMES.get(h.weekday, f"Día {h.weekday}"),
        is_open=h.is_open,
        open_time=h.open_time,
        close_time=h.close_time,
    )


@router.put("", response_model=list[BusinessHoursOut])
async def update_all_hours(
    slug: str,
    body: BusinessHoursBulkUpdate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> list[BusinessHoursOut]:
    """Actualiza todos los días de una vez (bulk update)."""
    if len(body.hours) != 7:
        raise HTTPException(status_code=422, detail="Se requieren exactamente 7 días")

    from app.services.business_hours_service import update_day_hours
    result = []
    for weekday, day_data in enumerate(body.hours):
        h = await update_day_hours(
            db=db,
            tenant_id=tenant.id,
            weekday=weekday,
            is_open=day_data.is_open,
            open_time=day_data.open_time,
            close_time=day_data.close_time,
        )
        result.append(BusinessHoursOut(
            id=h.id,
            weekday=h.weekday,
            weekday_name=WEEKDAY_NAMES.get(h.weekday, f"Día {h.weekday}"),
            is_open=h.is_open,
            open_time=h.open_time,
            close_time=h.close_time,
        ))

    await db.commit()
    logger.info(f"Horarios bulk actualizados para tenant {slug}")
    return result