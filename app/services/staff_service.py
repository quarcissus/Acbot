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

    Detecta traslapes reales: dos citas se traslapan si el inicio de una
    cae dentro del rango [inicio, fin) de la otra.

    Cita A: [scheduled_at_A, scheduled_at_A + duration_A)
    Cita B: [scheduled_at_B, scheduled_at_B + duration_B)
    Traslape cuando: A.start < B.end  AND  B.start < A.end
    """
    scheduled_at_utc = scheduled_at.replace(tzinfo=timezone.utc) if scheduled_at.tzinfo is None else scheduled_at
    new_end = scheduled_at_utc + timedelta(minutes=duration_minutes)

    # Buscar citas del staff que se traslapen con el nuevo rango
    # existing.start < new_end  AND  new_start < existing.start + existing.duration
    # Como no guardamos duration en UTC calculamos: existing.start + existing.duration
    # via columna duration_minutes del appointment
    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.staff_id == staff_id,
                Appointment.status.in_(["confirmed", "pending"]),
                # La cita existente empieza antes de que termine la nueva
                Appointment.scheduled_at < new_end,
                # La nueva cita empieza antes de que termine la existente
                # (scheduled_at_utc < existing.scheduled_at + existing.duration_minutes)
                # Equivalente: existing.scheduled_at > scheduled_at_utc - existing.duration
                # Lo manejamos filtrando en Python tras traer candidatos cercanos
                Appointment.scheduled_at > scheduled_at_utc - timedelta(hours=4),  # ventana máxima
            )
        )
    )
    candidates = list(result.scalars().all())

    for appt in candidates:
        appt_start = appt.scheduled_at.replace(tzinfo=timezone.utc) if appt.scheduled_at.tzinfo is None else appt.scheduled_at
        appt_end = appt_start + timedelta(minutes=appt.duration_minutes)
        # Traslape real: new_start < appt_end AND appt_start < new_end
        if scheduled_at_utc < appt_end and appt_start < new_end:
            logger.info(
                f"Disponibilidad staff_id={staff_id} en {scheduled_at_utc}: "
                f"ocupado (traslapa con cita {appt.id} [{appt_start}–{appt_end}])"
            )
            return False

    logger.info(f"Disponibilidad staff_id={staff_id} en {scheduled_at_utc}: libre")
    return True


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

async def get_next_available_slots(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID | None,
    duration_minutes: int = 30,
    slots_needed: int = 3,
    business_hours: dict | None = None,
) -> list[datetime]:
    """
    Retorna los próximos N slots disponibles para un staff (o cualquiera del tenant).

    business_hours define los rangos válidos por día de semana (0=lunes, 6=domingo).
    Si no se pasa, usa el horario estándar de barbería.
    """
    from datetime import date

    # Horario estándar de barbería (hora México UTC-6)
    DEFAULT_HOURS = {
        0: (8, 20),   # Lunes
        1: (8, 20),   # Martes
        2: (8, 20),   # Miércoles
        3: (8, 20),   # Jueves
        4: (8, 20),   # Viernes
        5: (8, 18),   # Sábado
        6: (10, 15),  # Domingo
    }
    hours = business_hours or DEFAULT_HOURS

    mexico_offset = timezone(timedelta(hours=-6))
    now_mexico = datetime.now(timezone.utc).astimezone(mexico_offset)

    slots: list[datetime] = []
    check_date = now_mexico.date()
    max_days = 14  # Buscar hasta 2 semanas hacia adelante

    for _ in range(max_days):
        weekday = check_date.weekday()
        if weekday not in hours:
            check_date += timedelta(days=1)
            continue

        open_h, close_h = hours[weekday]

        # Empezar desde la hora actual si es hoy, si no desde apertura
        if check_date == now_mexico.date():
            start_h = max(open_h, now_mexico.hour + 1)  # siguiente hora completa
        else:
            start_h = open_h

        for hour in range(start_h, close_h):
            candidate_local = datetime(
                check_date.year, check_date.month, check_date.day,
                hour, 0, tzinfo=mexico_offset
            )
            candidate_utc = candidate_local.astimezone(timezone.utc)

            # Verificar disponibilidad
            if staff_id:
                available = await is_staff_available(db, staff_id, candidate_utc, duration_minutes)
            else:
                # Cualquier staff disponible alcanza
                any_available = await get_available_staff(db, tenant_id, candidate_utc, duration_minutes)
                available = len(any_available) > 0

            if available:
                slots.append(candidate_local)
                if len(slots) >= slots_needed:
                    return slots

        check_date += timedelta(days=1)

    return slots


def format_slots_for_whatsapp(slots: list[datetime]) -> str:
    """Formatea lista de slots para mostrar al cliente en WhatsApp."""
    if not slots:
        return "No encontré disponibilidad en los próximos 14 días."

    days_es = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
               4: "Viernes", 5: "Sábado", 6: "Domingo"}
    lines = []
    for i, slot in enumerate(slots, 1):
        day_name = days_es[slot.weekday()]
        lines.append(f"  {i}. {day_name} {slot.strftime('%d/%m')} a las {slot.strftime('%H:%M')}")
    return "\n".join(lines)