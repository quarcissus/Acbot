"""
API pública — endpoints sin autenticación para el sitio web de la barbería.
Todos los imports de modelos son lazy (dentro de las funciones) para evitar
circular imports con el gateway.
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from app.core.database import get_db

logger = logging.getLogger(__name__)

public_router = APIRouter(prefix="/api/public/tenants/{slug}", tags=["public"])

MEXICO_OFFSET = timedelta(hours=-6)


def to_local_str(dt: datetime) -> str:
    local = dt.replace(tzinfo=timezone.utc).astimezone(timezone(MEXICO_OFFSET))
    return local.strftime("%d/%m/%Y %H:%M")


# ── Schemas ───────────────────────────────────────────────────────────────────

class StaffOut(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    is_active: bool
    appointment_duration: int
    model_config = {"from_attributes": True}


class PublicAppointmentIn(BaseModel):
    client_name: str
    client_phone: str
    service: str
    staff_name: str | None = None
    date: str   # YYYY-MM-DD
    time: str   # HH:MM


class PublicAppointmentOut(BaseModel):
    id: uuid.UUID
    title: str
    scheduled_at_local: str
    contact_name: str
    staff_name: str | None


class SlotOut(BaseModel):
    scheduled_at_local: str
    staff_name: str | None
    status: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@public_router.get("/staff", response_model=list[StaffOut])
async def get_public_staff(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> list[StaffOut]:
    """Lista los barberos activos de un negocio."""
    from app.models.tenant import Tenant
    from app.models.staff import Staff

    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    result = await db.execute(
        select(Staff)
        .where(and_(Staff.tenant_id == tenant.id, Staff.is_active == True))  # noqa: E712
        .order_by(Staff.name)
    )
    return list(result.scalars().all())


@public_router.get("/appointments", response_model=list[SlotOut])
async def get_public_appointments(
    slug: str,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[SlotOut]:
    """
    Citas ocupadas para mostrar en el calendario de disponibilidad.
    Oculta datos sensibles del cliente.
    """
    from app.models.tenant import Tenant
    from app.models.appointment import Appointment
    from app.models.staff import Staff

    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    query = (
        select(Appointment, Staff)
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
            dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query = query.where(Appointment.scheduled_at >= dt)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            query = query.where(Appointment.scheduled_at <= dt)
        except ValueError:
            pass

    result = await db.execute(query.order_by(Appointment.scheduled_at))
    rows = result.all()

    return [
        SlotOut(
            scheduled_at_local=to_local_str(appt.scheduled_at),
            staff_name=staff.name if staff else None,
            status=appt.status,
        )
        for appt, staff in rows
    ]


@public_router.post("/appointments", response_model=PublicAppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_public_appointment(
    slug: str,
    body: PublicAppointmentIn,
    db: AsyncSession = Depends(get_db),
) -> PublicAppointmentOut:
    """Agenda una cita desde el sitio web público. No requiere autenticación."""
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

    # Parsear fecha/hora en México (UTC-6)
    try:
        naive_dt = datetime.strptime(f"{body.date} {body.time}", "%Y-%m-%d %H:%M")
        mexico_tz = timezone(MEXICO_OFFSET)
        scheduled_at = naive_dt.replace(tzinfo=mexico_tz).astimezone(timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato inválido. Use YYYY-MM-DD y HH:MM")

    if scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="La fecha debe ser futura")

    # Buscar o crear contacto
    contact, _ = await get_or_create_contact(
        db=db,
        tenant_id=tenant.id,
        phone_number=body.client_phone.strip(),
        name=body.client_name.strip().title(),
    )
    if contact.name == "Sin nombre" and body.client_name.strip():
        contact.name = body.client_name.strip().title()
        await db.flush()

    # Buscar staff
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
                    detail=f"{body.staff_name} no está disponible en ese horario."
                )
            staff_id = staff_member.id

    # Crear cita
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
        f"Cita web: {appointment.id} — {body.service} "
        f"para {body.client_name} el {body.date} {body.time} (tenant={slug})"
    )

    return PublicAppointmentOut(
        id=appointment.id,
        title=appointment.title,
        scheduled_at_local=to_local_str(appointment.scheduled_at),
        contact_name=contact.name,
        staff_name=staff_member.name if staff_member else None,
    )