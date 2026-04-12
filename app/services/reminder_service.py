"""
ReminderService — APScheduler que corre cada 15 minutos y envía recordatorios.
Se inicializa en main.py durante el startup de la app.
"""

import logging
from datetime import timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.database import AsyncSessionLocal
from app.services.appointment_service import (
    get_upcoming_appointments_for_reminder,
    mark_reminder_sent,
)
from app.gateway.template_sender import send_appointment_reminder

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

DAYS_ES = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo"
}
MONTHS_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


def format_date_es(dt) -> str:
    """Formatea fecha como 'lunes 14 de abril'"""
    day_name = DAYS_ES[dt.weekday()]
    month_name = MONTHS_ES[dt.month]
    return f"{day_name} {dt.day} de {month_name}"


async def send_pending_reminders() -> None:
    """
    Job principal que se ejecuta cada 15 minutos.
    Busca citas próximas y envía recordatorios via WhatsApp template.
    """
    logger.info("Revisando citas para recordatorios...")

    async with AsyncSessionLocal() as db:
        try:
            rows = await get_upcoming_appointments_for_reminder(db)

            if not rows:
                logger.info("Sin citas para recordar en este ciclo")
                return

            logger.info(f"Enviando {len(rows)} recordatorio(s)")

            for appointment, contact, tenant in rows:
                try:
                    # Convertir a hora México (UTC-6)
                    mexico_tz = timezone(timedelta(hours=-6))
                    scheduled_local = appointment.scheduled_at.replace(
                        tzinfo=timezone.utc
                    ).astimezone(mexico_tz)

                    date_str = format_date_es(scheduled_local)
                    time_str = scheduled_local.strftime("%H:%M")

                    await send_appointment_reminder(
                        phone_number_id=tenant.whatsapp_phone_id,
                        to=contact.phone_number,
                        client_name=contact.name,
                        business_name=tenant.name,
                        date_str=date_str,
                        time_str=time_str,
                    )

                    await mark_reminder_sent(db, appointment.id)
                    await db.commit()

                    logger.info(
                        f"Recordatorio enviado: cita={appointment.id} "
                        f"contact={contact.phone_number}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error enviando recordatorio para cita {appointment.id}: {e}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Error en job de recordatorios: {e}")
            await db.rollback()


def start_scheduler() -> None:
    """Inicia el scheduler con el job de recordatorios cada 15 minutos."""
    scheduler.add_job(
        send_pending_reminders,
        trigger=IntervalTrigger(minutes=15),
        id="send_reminders",
        name="Enviar recordatorios de citas",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler iniciado — recordatorios cada 15 minutos")


def stop_scheduler() -> None:
    """Detiene el scheduler limpiamente."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido")