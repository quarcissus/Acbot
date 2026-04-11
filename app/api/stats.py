"""
Stats API — estadísticas del negocio por tenant.
"""

import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel

from app.core.database import get_db
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.tenant import Tenant
from app.api.deps import get_current_admin, get_tenant_by_slug
from app.models.admin_user import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{slug}/stats", tags=["stats"])


class StatsOut(BaseModel):
    period_days: int
    total_appointments: int
    confirmed: int
    cancelled: int
    completed: int
    pending: int
    no_show_rate_pct: float        # % canceladas vs total
    total_contacts: int            # clientes únicos
    new_contacts_period: int       # nuevos en el período
    busiest_day: str | None        # día de la semana con más citas
    appointments_by_staff: list[dict]  # [{name, count}]


@router.get("", response_model=StatsOut)
async def get_stats(
    slug: str,
    days: int = Query(30, ge=1, le=365, description="Período en días hacia atrás"),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> StatsOut:
    """
    Estadísticas del tenant para los últimos N días (default: 30).
    """
    mexico_offset = timezone(timedelta(hours=-6))
    now_utc = datetime.now(timezone.utc)
    period_start = now_utc - timedelta(days=days)

    # ── Citas del período ─────────────────────────────────────────────────────
    result = await db.execute(
        select(Appointment).where(
            and_(
                Appointment.tenant_id == tenant.id,
                Appointment.scheduled_at >= period_start,
                Appointment.scheduled_at <= now_utc,
            )
        )
    )
    appointments = list(result.scalars().all())

    total = len(appointments)
    by_status = {"confirmed": 0, "cancelled": 0, "completed": 0, "pending": 0}
    by_weekday: dict[int, int] = {}
    by_staff: dict[str, int] = {}

    for appt in appointments:
        by_status[appt.status] = by_status.get(appt.status, 0) + 1

        # Día de la semana (en hora México)
        local_dt = appt.scheduled_at.replace(tzinfo=timezone.utc).astimezone(mexico_offset)
        wd = local_dt.weekday()
        by_weekday[wd] = by_weekday.get(wd, 0) + 1

    # ── Staff counts ──────────────────────────────────────────────────────────
    from app.models.staff import Staff
    staff_result = await db.execute(
        select(Staff.name, func.count(Appointment.id).label("count"))
        .join(Appointment, Appointment.staff_id == Staff.id, isouter=True)
        .where(
            and_(
                Staff.tenant_id == tenant.id,
                Appointment.scheduled_at >= period_start,
                Appointment.scheduled_at <= now_utc,
            )
        )
        .group_by(Staff.name)
        .order_by(func.count(Appointment.id).desc())
    )
    appointments_by_staff = [
        {"name": row.name, "count": row.count}
        for row in staff_result.all()
    ]

    # ── Contactos ─────────────────────────────────────────────────────────────
    total_contacts_result = await db.execute(
        select(func.count(Contact.id)).where(Contact.tenant_id == tenant.id)
    )
    total_contacts = total_contacts_result.scalar() or 0

    new_contacts_result = await db.execute(
        select(func.count(Contact.id)).where(
            and_(
                Contact.tenant_id == tenant.id,
                Contact.created_at >= period_start,
            )
        )
    )
    new_contacts = new_contacts_result.scalar() or 0

    # ── Día más ocupado ───────────────────────────────────────────────────────
    days_es = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
               4: "Viernes", 5: "Sábado", 6: "Domingo"}
    busiest_day = None
    if by_weekday:
        busiest_wd = max(by_weekday, key=by_weekday.get)
        busiest_day = days_es.get(busiest_wd)

    # ── No-show rate ──────────────────────────────────────────────────────────
    cancelled = by_status.get("cancelled", 0)
    no_show_rate = round((cancelled / total * 100), 1) if total > 0 else 0.0

    return StatsOut(
        period_days=days,
        total_appointments=total,
        confirmed=by_status.get("confirmed", 0),
        cancelled=cancelled,
        completed=by_status.get("completed", 0),
        pending=by_status.get("pending", 0),
        no_show_rate_pct=no_show_rate,
        total_contacts=total_contacts,
        new_contacts_period=new_contacts,
        busiest_day=busiest_day,
        appointments_by_staff=appointments_by_staff,
    )