"""
Appointments API — ver y gestionar citas por tenant.
"""

import uuid
import logging
from datetime import datetime, timezone, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.staff import Staff
from app.models.tenant import Tenant
from app.api.deps import get_current_admin, get_tenant_by_slug
from app.models.admin_user import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{slug}/appointments", tags=["appointments"])

MEXICO_OFFSET_HOURS = -6


# ── Schemas ───────────────────────────────────────────────────────────────────

class AppointmentOut(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    scheduled_at: datetime
    scheduled_at_local: str      # Hora en México formateada
    duration_minutes: int
    source: str
    reminder_sent: bool
    contact_phone: str
    contact_name: str
    staff_name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentStatusUpdate(BaseModel):
    status: str  # "confirmed" | "cancelled" | "completed" | "pending"


# ── Helpers ───────────────────────────────────────────────────────────────────

def to_local_str(dt: datetime) -> str:
    from datetime import timedelta
    mexico_tz = timezone(timedelta(hours=MEXICO_OFFSET_HOURS))
    local = dt.replace(tzinfo=timezone.utc).astimezone(mexico_tz)
    return local.strftime("%d/%m/%Y %H:%M")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AppointmentOut])
async def list_appointments(
    slug: str,
    date_from: Optional[date] = Query(None, description="Filtrar desde esta fecha (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Filtrar hasta esta fecha (YYYY-MM-DD)"),
    appt_status: Optional[str] = Query(None, alias="status", description="confirmed|pending|cancelled|completed"),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> list[AppointmentOut]:
    """
    Lista citas de un tenant. Sin filtros retorna las de los próximos 7 días.
    """
    from datetime import timedelta

    query = (
        select(Appointment, Contact, Staff)
        .join(Contact, Appointment.contact_id == Contact.id)
        .outerjoin(Staff, Appointment.staff_id == Staff.id)
        .where(Appointment.tenant_id == tenant.id)
    )

    if appt_status:
        query = query.where(Appointment.status == appt_status)

    if date_from:
        dt_from = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
        query = query.where(Appointment.scheduled_at >= dt_from)
    else:
        query = query.where(Appointment.scheduled_at >= datetime.now(timezone.utc))

    if date_to:
        dt_to = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc)
        query = query.where(Appointment.scheduled_at <= dt_to)
    else:
        query = query.where(
            Appointment.scheduled_at <= datetime.now(timezone.utc) + timedelta(days=7)
        )

    query = query.order_by(Appointment.scheduled_at)
    result = await db.execute(query)
    rows = result.all()

    return [
        AppointmentOut(
            id=appt.id,
            title=appt.title,
            status=appt.status,
            scheduled_at=appt.scheduled_at,
            scheduled_at_local=to_local_str(appt.scheduled_at),
            duration_minutes=appt.duration_minutes,
            source=appt.source,
            reminder_sent=appt.reminder_sent,
            contact_phone=contact.phone_number,
            contact_name=contact.name,
            staff_name=staff.name if staff else None,
            created_at=appt.created_at,
        )
        for appt, contact, staff in rows
    ]


@router.patch("/{appointment_id}", response_model=AppointmentOut)
async def update_appointment_status(
    slug: str,
    appointment_id: uuid.UUID,
    body: AppointmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> AppointmentOut:
    """
    Actualiza el status de una cita (confirmar, cancelar, completar).
    """
    valid_statuses = {"confirmed", "pending", "cancelled", "completed"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Status inválido. Opciones: {valid_statuses}",
        )

    result = await db.execute(
        select(Appointment, Contact, Staff)
        .join(Contact, Appointment.contact_id == Contact.id)
        .outerjoin(Staff, Appointment.staff_id == Staff.id)
        .where(
            and_(
                Appointment.id == appointment_id,
                Appointment.tenant_id == tenant.id,
            )
        )
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    appt, contact, staff = row
    appt.status = body.status
    await db.flush()

    logger.info(f"Cita {appointment_id} → status={body.status} (tenant={slug})")

    return AppointmentOut(
        id=appt.id,
        title=appt.title,
        status=appt.status,
        scheduled_at=appt.scheduled_at,
        scheduled_at_local=to_local_str(appt.scheduled_at),
        duration_minutes=appt.duration_minutes,
        source=appt.source,
        reminder_sent=appt.reminder_sent,
        contact_phone=contact.phone_number,
        contact_name=contact.name,
        staff_name=staff.name if staff else None,
        created_at=appt.created_at,
    )