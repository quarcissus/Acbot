"""
BusinessHoursService — CRUD de horarios de atención por tenant.
"""

import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.business_hours import BusinessHours

logger = logging.getLogger(__name__)

DEFAULT_HOURS = [
    {"weekday": 0, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},  # Lunes
    {"weekday": 1, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},  # Martes
    {"weekday": 2, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},  # Miércoles
    {"weekday": 3, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},  # Jueves
    {"weekday": 4, "is_open": True,  "open_time": "08:00", "close_time": "20:00"},  # Viernes
    {"weekday": 5, "is_open": True,  "open_time": "08:00", "close_time": "18:00"},  # Sábado
    {"weekday": 6, "is_open": False, "open_time": "10:00", "close_time": "15:00"},  # Domingo
]


async def get_business_hours(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[BusinessHours]:
    """Retorna los horarios del tenant ordenados por día. Crea defaults si no existen."""
    result = await db.execute(
        select(BusinessHours)
        .where(BusinessHours.tenant_id == tenant_id)
        .order_by(BusinessHours.weekday)
    )
    hours = list(result.scalars().all())

    # Si no tiene horarios configurados, crear los defaults
    if not hours:
        hours = await create_default_hours(db, tenant_id)

    return hours


async def create_default_hours(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[BusinessHours]:
    """Crea los horarios por defecto para un tenant nuevo."""
    hours = []
    for h in DEFAULT_HOURS:
        bh = BusinessHours(
            tenant_id=tenant_id,
            weekday=h["weekday"],
            is_open=h["is_open"],
            open_time=h["open_time"],
            close_time=h["close_time"],
        )
        db.add(bh)
        hours.append(bh)
    await db.flush()
    logger.info(f"Horarios por defecto creados para tenant {tenant_id}")
    return hours


async def update_day_hours(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    weekday: int,
    is_open: bool,
    open_time: str,
    close_time: str,
) -> BusinessHours:
    """Actualiza el horario de un día específico."""
    result = await db.execute(
        select(BusinessHours).where(
            and_(
                BusinessHours.tenant_id == tenant_id,
                BusinessHours.weekday == weekday,
            )
        )
    )
    bh = result.scalar_one_or_none()

    if not bh:
        bh = BusinessHours(tenant_id=tenant_id, weekday=weekday)
        db.add(bh)

    bh.is_open = is_open
    bh.open_time = open_time
    bh.close_time = close_time
    await db.flush()

    logger.info(f"Horario actualizado: {bh}")
    return bh


def format_hours_for_prompt(hours: list[BusinessHours]) -> str:
    """
    Formatea los horarios para incluir en el system prompt del bot.
    Ejemplo de salida:
        • Lunes: 8:00 - 20:00
        • Martes: 8:00 - 20:00
        • Miércoles: cerrado
    """
    lines = []
    for h in sorted(hours, key=lambda x: x.weekday):
        if h.is_open:
            lines.append(f"• {h.weekday_name}: {h.open_time} - {h.close_time}")
        else:
            lines.append(f"• {h.weekday_name}: cerrado")
    return "\n".join(lines)


def build_hours_dict(hours: list[BusinessHours]) -> dict:
    """
    Construye un dict {weekday: (open_hour, close_hour)} para el calculador de slots.
    Solo incluye días abiertos.
    """
    result = {}
    for h in hours:
        if h.is_open:
            open_h = int(h.open_time.split(":")[0])
            close_h = int(h.close_time.split(":")[0])
            result[h.weekday] = (open_h, close_h)
    return result