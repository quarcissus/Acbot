"""
ReminderService — APScheduler que corre cada 15 minutos y envía recordatorios.
Se inicializa en main.py durante el startup de la app.
"""

import logging
from datetime import timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.database import AsyncSessionLocal
from app.services.appointment_service import (
    get_upcoming_appointments_for_reminder,
    mark_reminder_sent,
)
from app.gateway.template_sender import send_appointment_reminder

logger = logging.getLogger(__name__)

# Instancia global del scheduler
scheduler = AsyncIOScheduler(timezone="UTC")


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
                    # Convertir a hora de México (UTC-6 fijo)
                    from datetime import timedelta
                    mexico_offset = timezone(timedelta(hours=-6))
                    scheduled_local = appointment.scheduled_at.replace(
                        tzinfo=timezone.utc
                    ).astimezone(mexico_offset)
                    datetime_str = scheduled_local.strftime("%d/%m/%Y a las %H:%M")

                    await send_appointment_reminder(
                        phone_number_id=tenant.whatsapp_phone_id,
                        to=contact.phone_number,
                        client_name=contact.name,
                        service=appointment.title,
                        datetime_str=datetime_str,
                        business_name=tenant.name,
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
                    # Continuar con los demás recordatorios aunque uno falle
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
        max_instances=1,  # Evita que se ejecute en paralelo
    )
    scheduler.start()
    logger.info("Scheduler iniciado — recordatorios cada 15 minutos")


def stop_scheduler() -> None:
    """Detiene el scheduler limpiamente."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido")