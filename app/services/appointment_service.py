"""
AppointmentService — CRUD de citas y lógica de disponibilidad.
"""

import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


class AppointmentNotFoundError(Exception):
    pass


async def create_appointment(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contact_id: uuid.UUID,
    title: str,
    scheduled_at: datetime,
    duration_minutes: int = 30,
    description: str | None = None,
    notes: str | None = None,
    source: str = "chatbot",
) -> Appointment:
    """
    Crea una nueva cita en la base de datos.
    """
    appointment = Appointment(
        tenant_id=tenant_id,
        contact_id=contact_id,
        title=title,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        description=description,
        notes=notes,
        source=source,
        status="confirmed",
    )
    db.add(appointment)
    await db.flush()
    await db.refresh(appointment)
    logger.info(
        f"Cita creada: '{title}' para contact={contact_id} "
        f"en tenant={tenant_id} a las {scheduled_at}"
    )
    return appointment


async def get_upcoming_appointments_for_reminder(
    db: AsyncSession,
) -> list[tuple[Appointment, Contact, Tenant]]:
    """
    Busca citas que necesitan recordatorio:
    - status = confirmed o pending
    - scheduled_at dentro de las próximas N horas (según tenant.reminder_hours_before)
    - reminder_sent = False
    """
    from app.models.tenant import Tenant
    from sqlalchemy import func
    from datetime import timedelta

    now = datetime.now(timezone.utc)

    # Traer todas las citas pendientes de recordatorio
    result = await db.execute(
        select(Appointment, Contact, Tenant)
        .join(Contact, Appointment.contact_id == Contact.id)
        .join(Tenant, Appointment.tenant_id == Tenant.id)
        .where(
            and_(
                Appointment.status.in_(["confirmed", "pending"]),
                Appointment.reminder_sent == False,  # noqa: E712
                Appointment.scheduled_at > now,
            )
        )
    )
    rows = result.all()

    # Filtrar por reminder_hours_before de cada tenant
    to_remind = []
    for appointment, contact, tenant in rows:
        reminder_delta = timedelta(hours=tenant.reminder_hours_before)
        time_until = appointment.scheduled_at.replace(tzinfo=timezone.utc) - now
        if time_until <= reminder_delta:
            to_remind.append((appointment, contact, tenant))

    return to_remind


async def mark_reminder_sent(db: AsyncSession, appointment_id: uuid.UUID) -> None:
    """Marca una cita como recordatorio enviado."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if appointment:
        appointment.reminder_sent = True
        await db.flush()


async def update_appointment_status(
    db: AsyncSession,
    appointment_id: uuid.UUID,
    status: str,
) -> Appointment:
    """Actualiza el status de una cita."""
    result = await db.execute(
        select(Appointment).where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise AppointmentNotFoundError(f"Cita {appointment_id} no encontrada")
    appointment.status = status
    await db.flush()
    return appointment


async def get_appointments_by_tenant(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    status: str | None = None,
) -> list[Appointment]:
    """Lista citas de un tenant, opcionalmente filtradas por status."""
    query = select(Appointment).where(Appointment.tenant_id == tenant_id)
    if status:
        query = query.where(Appointment.status == status)
    query = query.order_by(Appointment.scheduled_at)
    result = await db.execute(query)
    return list(result.scalars().all())