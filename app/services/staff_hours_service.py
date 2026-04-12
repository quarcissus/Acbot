"""
StaffHoursService — horarios de trabajo por barbero.
Regla principal: horario del barbero ⊆ horario del negocio.
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.staff_hours import StaffHours, WEEKDAY_NAMES
from app.models.business_hours import BusinessHours

logger = logging.getLogger(__name__)


def _time_to_minutes(t: str) -> int:
    """Convierte 'HH:MM' a minutos desde medianoche."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _clamp_to_business(
    staff_start: str,
    staff_end: str,
    biz_open: str,
    biz_close: str,
) -> tuple[str, str]:
    """
    Ajusta el horario del barbero para que no exceda el del negocio.
    Si el barbero empieza antes que el negocio, se ajusta al negocio.
    Si termina después, se ajusta al cierre del negocio.
    """
    s_start = max(_time_to_minutes(staff_start), _time_to_minutes(biz_open))
    s_end   = min(_time_to_minutes(staff_end),   _time_to_minutes(biz_close))

    # Si después del ajuste el horario queda invertido, usar el del negocio
    if s_start >= s_end:
        s_start = _time_to_minutes(biz_open)
        s_end   = _time_to_minutes(biz_close)

    def mins_to_str(m: int) -> str:
        return f"{m // 60:02d}:{m % 60:02d}"

    return mins_to_str(s_start), mins_to_str(s_end)


async def get_staff_hours(
    db: AsyncSession,
    staff_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[StaffHours]:
    """
    Retorna los horarios del barbero.
    Si no tiene configurados, crea defaults basados en los horarios del negocio.
    """
    result = await db.execute(
        select(StaffHours)
        .where(StaffHours.staff_id == staff_id)
        .order_by(StaffHours.weekday)
    )
    hours = list(result.scalars().all())

    if not hours:
        hours = await create_default_staff_hours(db, staff_id, tenant_id)

    return hours


async def create_default_staff_hours(
    db: AsyncSession,
    staff_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[StaffHours]:
    """
    Crea horarios por defecto para un barbero basados en el horario del negocio.
    Por defecto el barbero trabaja todos los días que el negocio está abierto,
    con el mismo horario del negocio.
    """
    # Obtener horarios del negocio
    result = await db.execute(
        select(BusinessHours)
        .where(BusinessHours.tenant_id == tenant_id)
        .order_by(BusinessHours.weekday)
    )
    biz_hours = list(result.scalars().all())

    # Si no hay horarios del negocio, usar defaults hardcodeados
    if not biz_hours:
        biz_defaults = {
            0: ("08:00", "20:00"), 1: ("08:00", "20:00"), 2: ("08:00", "20:00"),
            3: ("08:00", "20:00"), 4: ("08:00", "20:00"), 5: ("08:00", "18:00"),
        }
        biz_hours_dict = biz_defaults
        open_days = set(biz_defaults.keys())
    else:
        biz_hours_dict = {h.weekday: (h.open_time, h.close_time) for h in biz_hours if h.is_open}
        open_days = set(biz_hours_dict.keys())

    hours = []
    for weekday in range(7):
        if weekday in open_days:
            if isinstance(biz_hours_dict[weekday], tuple):
                open_t, close_t = biz_hours_dict[weekday]
            else:
                open_t = biz_hours_dict[weekday].open_time
                close_t = biz_hours_dict[weekday].close_time
            sh = StaffHours(
                staff_id=staff_id,
                tenant_id=tenant_id,
                weekday=weekday,
                is_working=True,
                start_time=open_t,
                end_time=close_t,
            )
        else:
            sh = StaffHours(
                staff_id=staff_id,
                tenant_id=tenant_id,
                weekday=weekday,
                is_working=False,
                start_time="08:00",
                end_time="20:00",
            )
        db.add(sh)
        hours.append(sh)

    await db.flush()
    logger.info(f"Horarios por defecto creados para staff {staff_id}")
    return hours


async def update_staff_day(
    db: AsyncSession,
    staff_id: uuid.UUID,
    tenant_id: uuid.UUID,
    weekday: int,
    is_working: bool,
    start_time: str,
    end_time: str,
) -> StaffHours:
    """
    Actualiza el horario de un día para un barbero.
    Aplica la restricción de business_hours automáticamente.
    """
    # Obtener horario del negocio para ese día
    result = await db.execute(
        select(BusinessHours).where(
            and_(
                BusinessHours.tenant_id == tenant_id,
                BusinessHours.weekday == weekday,
            )
        )
    )
    biz = result.scalar_one_or_none()

    # Validar contra business hours
    if is_working and biz:
        if not biz.is_open:
            # El negocio está cerrado ese día — el barbero tampoco puede trabajar
            is_working = False
            logger.info(f"Barbero {staff_id} no puede trabajar el {WEEKDAY_NAMES[weekday]} — negocio cerrado")
        else:
            # Ajustar horario para que no exceda el del negocio
            start_time, end_time = _clamp_to_business(
                start_time, end_time, biz.open_time, biz.close_time
            )

    # Buscar registro existente
    result = await db.execute(
        select(StaffHours).where(
            and_(
                StaffHours.staff_id == staff_id,
                StaffHours.weekday == weekday,
            )
        )
    )
    sh = result.scalar_one_or_none()

    if not sh:
        sh = StaffHours(staff_id=staff_id, tenant_id=tenant_id, weekday=weekday)
        db.add(sh)

    sh.is_working = is_working
    sh.start_time = start_time
    sh.end_time = end_time
    await db.flush()

    logger.info(f"Horario actualizado: staff={staff_id}, {WEEKDAY_NAMES[weekday]} → {sh}")
    return sh


async def is_staff_working_at(
    db: AsyncSession,
    staff_id: uuid.UUID,
    tenant_id: uuid.UUID,
    scheduled_at: datetime,
) -> tuple[bool, str]:
    """
    Verifica si un barbero trabaja en el datetime dado.
    Retorna (True, "") si trabaja, (False, motivo) si no.
    Aplica validación doble: business_hours + staff_hours.
    """
    # Convertir a hora México (UTC-6)
    mexico_tz = timezone(timedelta(hours=-6))
    local_dt = scheduled_at.astimezone(mexico_tz)
    weekday = local_dt.weekday()  # 0=Lunes
    time_str = local_dt.strftime("%H:%M")
    time_mins = _time_to_minutes(time_str)

    # 1. Verificar business hours del negocio
    result = await db.execute(
        select(BusinessHours).where(
            and_(
                BusinessHours.tenant_id == tenant_id,
                BusinessHours.weekday == weekday,
            )
        )
    )
    biz = result.scalar_one_or_none()
    if biz:
        if not biz.is_open:
            return False, f"El negocio está cerrado los {WEEKDAY_NAMES[weekday]}"
        biz_open  = _time_to_minutes(biz.open_time)
        biz_close = _time_to_minutes(biz.close_time)
        if time_mins < biz_open or time_mins >= biz_close:
            return False, f"El negocio está cerrado a las {time_str} los {WEEKDAY_NAMES[weekday]}"

    # 2. Verificar staff hours del barbero
    result = await db.execute(
        select(StaffHours).where(
            and_(
                StaffHours.staff_id == staff_id,
                StaffHours.weekday == weekday,
            )
        )
    )
    sh = result.scalar_one_or_none()
    if sh:
        if not sh.is_working:
            return False, f"El barbero no trabaja los {WEEKDAY_NAMES[weekday]}"
        staff_start = _time_to_minutes(sh.start_time)
        staff_end   = _time_to_minutes(sh.end_time)
        if time_mins < staff_start or time_mins >= staff_end:
            return False, f"El barbero no trabaja a las {time_str} los {WEEKDAY_NAMES[weekday]}"

    return True, ""


def format_staff_hours_for_prompt(hours: list[StaffHours]) -> str:
    """Formatea los horarios del barbero para el system prompt."""
    lines = []
    for h in sorted(hours, key=lambda x: x.weekday):
        if h.is_working:
            lines.append(f"  {h.weekday_name}: {h.start_time} - {h.end_time}")
        else:
            lines.append(f"  {h.weekday_name}: no trabaja")
    return "\n".join(lines)