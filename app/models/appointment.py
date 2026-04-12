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

# ── PUBLIC ENDPOINT — sin autenticación ──────────────────────────────────────

class PublicAppointmentIn(BaseModel):
    client_name: str
    client_phone: str
    service: str
    staff_name: str | None = None
    date: str        # YYYY-MM-DD
    time: str        # HH:MM


class PublicAppointmentOut(BaseModel):
    id: uuid.UUID
    title: str
    scheduled_at_local: str
    contact_name: str
    staff_name: str | None


# Router separado para endpoints públicos (sin auth)
public_router = APIRouter(prefix="/api/public/tenants/{slug}", tags=["public"])


@public_router.post("/appointments", response_model=PublicAppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_public_appointment(
    slug: str,
    body: PublicAppointmentIn,
    db: AsyncSession = Depends(get_db),
) -> PublicAppointmentOut:
    """
    Endpoint público para agendar citas desde la web.
    No requiere autenticación — cualquier visitante puede usarlo.
    """
    from datetime import timedelta
    from sqlalchemy import select, and_
    from app.models.tenant import Tenant
    from app.models.contact import Contact
    from app.models.staff import Staff
    from app.models.appointment import Appointment
    from app.services.staff_service import get_staff_by_name, is_staff_available
    from app.services.contact_service import get_or_create_contact

    # Buscar tenant
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Negocio '{slug}' no encontrado")

    if not tenant.bot_enabled:
        raise HTTPException(status_code=403, detail="El sistema de citas no está disponible")

    # Parsear fecha y hora en México (UTC-6)
    try:
        naive_dt = datetime.strptime(f"{body.date} {body.time}", "%Y-%m-%d %H:%M")
        mexico_offset = timezone(timedelta(hours=-6))
        scheduled_at = naive_dt.replace(tzinfo=mexico_offset).astimezone(timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato de fecha/hora inválido. Use YYYY-MM-DD y HH:MM")

    # Verificar que la fecha sea futura
    if scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="La fecha debe ser futura")

    # Buscar o crear contacto
    contact, _ = await get_or_create_contact(
        db=db,
        tenant_id=tenant.id,
        phone_number=body.client_phone.strip(),
        name=body.client_name.strip().title(),
    )
    # Actualizar nombre si ya existía con "Sin nombre"
    if contact.name == "Sin nombre" and body.client_name.strip():
        contact.name = body.client_name.strip().title()
        await db.flush()

    # Buscar staff si se especificó
    staff_id = None
    staff_member = None
    if body.staff_name:
        staff_member = await get_staff_by_name(db, tenant.id, body.staff_name)
        if staff_member:
            available = await is_staff_available(
                db, staff_member.id, scheduled_at, staff_member.appointment_duration
            )
            if not available:
                raise HTTPException(
                    status_code=409,
                    detail=f"{body.staff_name} no está disponible en ese horario. Elige otro horario."
                )
            staff_id = staff_member.id

    # Crear la cita
    appointment = Appointment(
        tenant_id=tenant.id,
        contact_id=contact.id,
        title=body.service,
        scheduled_at=scheduled_at,
        duration_minutes=staff_member.appointment_duration if staff_member else 30,
        status="confirmed",
        source="web",
        staff_id=staff_id,
    )
    db.add(appointment)
    await db.flush()
    await db.refresh(appointment)

    logger.info(
        f"Cita web creada: {appointment.id} — {body.service} "
        f"para {body.client_name} el {body.date} {body.time} "
        f"(tenant={slug})"
    )

    return PublicAppointmentOut(
        id=appointment.id,
        title=appointment.title,
        scheduled_at_local=to_local_str(appointment.scheduled_at),
        contact_name=contact.name,
        staff_name=staff_member.name if staff_member else None,
    )


@public_router.get("/appointments", response_model=list[AppointmentOut])
async def get_public_appointments(
    slug: str,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[AppointmentOut]:
    """
    Endpoint público para ver citas ocupadas (para el calendario de disponibilidad).
    Solo retorna campos no sensibles.
    """
    from datetime import timedelta
    from app.models.tenant import Tenant

    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    query = (
        select(Appointment, Contact, Staff)
        .join(Contact, Appointment.contact_id == Contact.id)
        .outerjoin(Staff, Appointment.staff_id == Staff.id)
        .where(
            and_(
                Appointment.tenant_id == tenant.id,
                Appointment.status.in_(["confirmed", "pending"]),
            )
        )
    )

    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query = query.where(Appointment.scheduled_at >= dt_from)
        except ValueError:
            pass

    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            query = query.where(Appointment.scheduled_at <= dt_to)
        except ValueError:
            pass

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
            contact_phone="***",  # ocultar datos sensibles en endpoint público
            contact_name="***",
            staff_name=staff.name if staff else None,
            created_at=appt.created_at,
        )
        for appt, contact, staff in rows
    ]