"""
StaffService — CRUD de staff y validación de disponibilidad.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.staff import Staff
from app.models.appointment import Appointment

logger = logging.getLogger(__name__)


async def get_active_staff(db: AsyncSession, tenant_id: uuid.UUID) -> list[Staff]:
    """Retorna todos los empleados activos de un tenant."""
    result = await db.execute(
        select(Staff)
        .where(and_(Staff.tenant_id == tenant_id, Staff.is_active == True))  # noqa: E712
        .order_by(Staff.name)
    )
    return list(result.scalars().all())


async def get_staff_by_name(
    db: AsyncSession, tenant_id: uuid.UUID, name: str
) -> Staff | None:
    """Busca un empleado por nombre (case-insensitive)."""
    result = await db.execute(
        select(Staff).where(
            and_(
                Staff.tenant_id == tenant_id,
                Staff.is_active == True,  # noqa: E712
                Staff.name.ilike(f"%{name}%"),
            )
        )
    )
    return result.scalar_one_or_none()


async def is_staff_available(
    db: AsyncSession,
    staff_id: uuid.UUID,
    scheduled_at: datetime,
    duration_minutes: int = 30,
) -> bool:
    """
    Verifica si un empleado está disponible en el horario solicitado.
    Bloquea si hay una cita exactamente a la misma hora.
    """
    scheduled_at_utc = scheduled_at.replace(tzinfo=timezone.utc) if scheduled_at.tzinfo is None else scheduled_at

    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.staff_id == staff_id,
                Appointment.status.in_(["confirmed", "pending"]),
                Appointment.scheduled_at == scheduled_at_utc,
            )
        )
    )
    existing = result.scalar_one_or_none()
    logger.info(f"Disponibilidad staff_id={staff_id} en {scheduled_at_utc}: {'ocupado' if existing else 'libre'}")
    return existing is None


async def get_available_staff(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    scheduled_at: datetime,
    duration_minutes: int = 30,
) -> list[Staff]:
    """Retorna la lista de empleados disponibles en un horario dado."""
    all_staff = await get_active_staff(db, tenant_id)
    available = []
    for staff in all_staff:
        if await is_staff_available(db, staff.id, scheduled_at, duration_minutes):
            available.append(staff)
    return available


async def create_staff(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    role: str = "barbero",
    appointment_duration: int = 30,
) -> Staff:
    """Crea un nuevo empleado."""
    staff = Staff(
        tenant_id=tenant_id,
        name=name,
        role=role,
        appointment_duration=appointment_duration,
    )
    db.add(staff)
    await db.commit()
    await db.refresh(staff)
    logger.info(f"Staff creado: {name} para tenant {tenant_id}")
    return staff


async def format_staff_list(staff_list: list[Staff]) -> str:
    """Formatea la lista de barberos para mostrar en WhatsApp."""
    if not staff_list:
        return "No hay barberos disponibles en este momento."
    names = [s.name for s in staff_list]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" o {names[-1]}"