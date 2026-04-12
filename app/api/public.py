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
    date: str
    time: str


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


class StaffHoursPublicOut(BaseModel):
    weekday: int
    weekday_name: str
    is_working: bool
    start_time: str
    end_time: str


WEEKDAY_NAMES_PUBLIC = {
    0: "Lunes", 1: "Martes", 2: "Miercoles", 3: "Jueves",
    4: "Viernes", 5: "Sabado", 6: "Domingo"
}


async def _send_web_booking_confirmation(tenant, contact, appointment, staff_name, local_dt_str):
    """
    Envía confirmación WhatsApp al cliente.
    Intenta usar el template oficial de Meta primero.
    Si falla (template aún en revisión), usa mensaje de texto libre como fallback.
    """
    # Separar fecha y hora del string "18/04/2026 14:00"
    try:
        parts_dt = local_dt_str.split(" ")
        date_part = parts_dt[0] if len(parts_dt) > 0 else local_dt_str
        time_part = parts_dt[1] if len(parts_dt) > 1 else ""
        # Convertir "18/04/2026" a "18 de abril de 2026"
        from datetime import datetime
        dt_obj = datetime.strptime(date_part, "%d/%m/%Y")
        months = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
                  7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}
        date_str = str(dt_obj.day) + " de " + months[dt_obj.month] + " de " + str(dt_obj.year)
    except Exception:
        date_str = local_dt_str
        time_part = ""

    # 1. Intentar template oficial
    try:
        from app.gateway.template_sender import send_appointment_confirmation
        await send_appointment_confirmation(
            phone_number_id=tenant.whatsapp_phone_id,
            to=contact.phone_number,
            client_name=contact.name,
            business_name=tenant.name,
            date_str=date_str,
            time_str=time_part,
            barber_name=staff_name,
        )
        logger.info("Confirmacion via template enviada a " + contact.phone_number)
        return
    except Exception as e:
        logger.warning("Template no disponible, usando texto libre: " + str(e))

    # 2. Fallback — texto libre (ventana de 24h o template aún en revisión)
    try:
        from app.gateway.sender import send_text_message
        lines = [
            "Cita confirmada!",
            "",
            "Hola " + contact.name + ", tu cita en " + tenant.name + " fue agendada:",
            "",
            "Servicio: " + appointment.title,
            "Fecha y hora: " + local_dt_str,
        ]
        if staff_name:
            lines.append("Barbero: " + staff_name)
        lines += ["", "Si necesitas cancelar o cambiar, escribenos por WhatsApp."]
        await send_text_message(
            phone_number_id=tenant.whatsapp_phone_id,
            to=contact.phone_number,
            body="\n".join(lines),
        )
        logger.info("Confirmacion via texto libre enviada a " + contact.phone_number)
    except Exception as e:
        logger.warning("No se pudo enviar confirmacion WhatsApp: " + str(e))


@public_router.get("/staff", response_model=list[StaffOut])
async def get_public_staff(slug: str, db: AsyncSession = Depends(get_db)):
    from app.models.tenant import Tenant
    from app.models.staff import Staff
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    result = await db.execute(
        select(Staff).where(and_(Staff.tenant_id == tenant.id, Staff.is_active == True)).order_by(Staff.name)  # noqa: E712
    )
    return list(result.scalars().all())


@public_router.get("/appointments", response_model=list[SlotOut])
async def get_public_appointments(
    slug: str,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
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
        .where(and_(Appointment.tenant_id == tenant.id, Appointment.status.in_(["confirmed", "pending"])))
    )
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query = query.where(Appointment.scheduled_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            query = query.where(Appointment.scheduled_at <= dt)
        except ValueError:
            pass
    result = await db.execute(query.order_by(Appointment.scheduled_at))
    rows = result.all()
    return [SlotOut(scheduled_at_local=to_local_str(a.scheduled_at), staff_name=s.name if s else None, status=a.status) for a, s in rows]


@public_router.post("/appointments", response_model=PublicAppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_public_appointment(slug: str, body: PublicAppointmentIn, db: AsyncSession = Depends(get_db)):
    from app.models.tenant import Tenant
    from app.models.appointment import Appointment
    from app.services.staff_service import get_staff_by_name, is_staff_available
    from app.services.contact_service import get_or_create_contact

    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    if not tenant.bot_enabled:
        raise HTTPException(status_code=403, detail="El sistema de citas no esta disponible")

    try:
        naive_dt = datetime.strptime(body.date + " " + body.time, "%Y-%m-%d %H:%M")
        scheduled_at = naive_dt.replace(tzinfo=timezone(MEXICO_OFFSET)).astimezone(timezone.utc)
    except ValueError:
        raise HTTPException(status_code=422, detail="Formato invalido. Use YYYY-MM-DD y HH:MM")

    if scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="La fecha debe ser futura")

    contact, _ = await get_or_create_contact(
        db=db, tenant_id=tenant.id,
        phone_number=body.client_phone.strip(),
        name=body.client_name.strip().title(),
    )
    if contact.name == "Sin nombre" and body.client_name.strip():
        contact.name = body.client_name.strip().title()
        await db.flush()

    staff_id = None
    staff_member = None
    if body.staff_name:
        staff_member = await get_staff_by_name(db, tenant.id, body.staff_name)
        if staff_member:
            available = await is_staff_available(db, staff_member.id, scheduled_at, staff_member.appointment_duration)
            if not available:
                raise HTTPException(status_code=409, detail=body.staff_name + " no esta disponible en ese horario.")
            staff_id = staff_member.id

    appointment = Appointment(
        tenant_id=tenant.id, contact_id=contact.id,
        title=body.service, scheduled_at=scheduled_at,
        duration_minutes=staff_member.appointment_duration if staff_member else 30,
        status="confirmed", source="web", staff_id=staff_id,
    )
    db.add(appointment)
    await db.flush()
    await db.refresh(appointment)

    logger.info("Cita web creada: " + str(appointment.id) + " para " + body.client_name)

    await _send_web_booking_confirmation(
        tenant=tenant, contact=contact, appointment=appointment,
        staff_name=staff_member.name if staff_member else None,
        local_dt_str=to_local_str(appointment.scheduled_at),
    )

    return PublicAppointmentOut(
        id=appointment.id, title=appointment.title,
        scheduled_at_local=to_local_str(appointment.scheduled_at),
        contact_name=contact.name,
        staff_name=staff_member.name if staff_member else None,
    )


@public_router.get("/staff/{staff_id}/hours", response_model=list[StaffHoursPublicOut])
async def get_public_staff_hours(slug: str, staff_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.models.tenant import Tenant
    from app.models.staff import Staff
    from app.services.staff_hours_service import get_staff_hours

    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    result = await db.execute(select(Staff).where(and_(Staff.id == staff_id, Staff.tenant_id == tenant.id)))
    staff = result.scalar_one_or_none()
    if not staff:
        raise HTTPException(status_code=404, detail="Barbero no encontrado")

    hours = await get_staff_hours(db, staff_id, tenant.id)
    return [
        StaffHoursPublicOut(
            weekday=h.weekday,
            weekday_name=WEEKDAY_NAMES_PUBLIC.get(h.weekday, "Dia " + str(h.weekday)),
            is_working=h.is_working,
            start_time=h.start_time,
            end_time=h.end_time,
        )
        for h in hours
    ]