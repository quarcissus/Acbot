"""
BaseHandler — clase base para todos los handlers de vertical.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant import Tenant
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.services.ai_service import get_conversation_history, generate_response, parse_action
from app.services.security_service import validate_and_sanitize

logger = logging.getLogger(__name__)


class BaseHandler(ABC):

    @abstractmethod
    def get_system_prompt(self, tenant: Tenant, contact: Contact) -> str:
        ...

    async def handle_message(
        self,
        tenant: Tenant,
        contact: Contact,
        conversation: Conversation,
        message: str,
        db: AsyncSession,
    ) -> str:
        # 1. Seguridad
        is_valid, processed_message = validate_and_sanitize(message)
        if not is_valid:
            logger.warning(f"Mensaje rechazado por seguridad para tenant {tenant.slug}")
            return processed_message

        # 2. Historial
        history = await get_conversation_history(db, conversation.id)

        # 3. System prompt
        system_prompt = await self._build_system_prompt(tenant, contact, db)

        # 4. Llamar a IA
        raw_response = await generate_response(system_prompt, history, processed_message)

        # 5. Parsear acción
        clean_response, action = parse_action(raw_response)

        # 6. Ejecutar acción si existe
        if action:
            action_result = await self.execute_action(action, tenant, contact, conversation, db)
            if action_result:
                return action_result
            return "¡Tu cita ha sido agendada! Te enviaremos un recordatorio antes de tu cita."

        return clean_response

    async def _build_system_prompt(
        self, tenant: Tenant, contact: Contact, db: AsyncSession
    ) -> str:
        return self.get_system_prompt(tenant, contact)

    def staff_label_singular(self) -> str:
        return "persona"

    def staff_label_plural(self) -> str:
        return "personas disponibles"

    async def execute_action(
        self,
        action: dict,
        tenant: Tenant,
        contact: Contact,
        conversation: Conversation,
        db: AsyncSession,
    ) -> str | None:
        action_type = action.get("action")
        logger.info(f"Acción detectada: {action_type} para tenant {tenant.slug}")

        if action_type == "create_appointment":
            return await self._handle_create_appointment(action, tenant, contact, db)
        if action_type == "cancel_appointment":
            return await self._handle_cancel_appointment(action, tenant, contact, db)
        if action_type == "reschedule_appointment":
            return await self._handle_reschedule_appointment(action, tenant, contact, db)
        if action_type == "get_available_slots":
            return await self._handle_get_slots(action, tenant, contact, db)
        if action_type == "human_handoff":
            return await self._handle_human_handoff(action, tenant, contact, conversation, db)

        return None

    # ── CREATE APPOINTMENT ────────────────────────────────────────────────────

    async def _handle_create_appointment(
        self,
        action: dict,
        tenant: Tenant,
        contact: Contact,
        db: AsyncSession,
    ) -> str | None:
        from app.services.appointment_service import create_appointment
        from app.services.staff_service import (
            get_staff_by_name, is_staff_available, get_available_staff
        )
        from app.services.contact_service import update_contact_name

        try:
            service = action.get("service", "Consulta")
            date_str = action.get("date")
            time_str = action.get("time")
            staff_name = action.get("staff_name")
            client_name = action.get("client_name", "")

            if not date_str or not time_str:
                logger.warning(f"Acción sin fecha/hora: {action}")
                return None

            # Guardar nombre del cliente si aún no lo tiene (#4)
            if client_name:
                await update_contact_name(db, contact, client_name)

            scheduled_at = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            mexico_offset = timezone(timedelta(hours=-6))
            scheduled_at = scheduled_at.replace(tzinfo=mexico_offset).astimezone(timezone.utc)

            staff_id = None
            staff_member = None

            if staff_name:
                staff_member = await get_staff_by_name(db, tenant.id, staff_name)

                if staff_member:
                    available = await is_staff_available(
                        db, staff_member.id, scheduled_at, staff_member.appointment_duration
                    )
                    if not available:
                        other_staff = await get_available_staff(db, tenant.id, scheduled_at)
                        if other_staff:
                            other_names = [s.name for s in other_staff]
                            names_str = (
                                ", ".join(other_names[:-1]) + f" o {other_names[-1]}"
                                if len(other_names) > 1 else other_names[0]
                            )
                            label = self.staff_label_plural() if len(other_names) > 1 else self.staff_label_singular()
                            prefix = "Estos" if len(other_names) > 1 else "Este"
                            return (
                                f"Lo siento, {staff_member.name} no está disponible a esa hora. "
                                f"{prefix} {label} sí {'están' if len(other_names) > 1 else 'está'} "
                                f"disponible{'s' if len(other_names) > 1 else ''}: {names_str}. "
                                f"¿Con cuál prefieres?"
                            )
                        else:
                            return (
                                f"Lo siento, no hay {self.staff_label_plural()} disponibles "
                                f"el {date_str} a las {time_str}. ¿Quieres intentar con otro horario?"
                            )
                    staff_id = staff_member.id

            appointment = await create_appointment(
                db=db,
                tenant_id=tenant.id,
                contact_id=contact.id,
                title=service,
                scheduled_at=scheduled_at,
                staff_id=staff_id,
                source="chatbot",
            )

            staff_info = f" con {staff_member.name}" if staff_member else ""
            mexico_offset = timezone(timedelta(hours=-6))
            local_time = scheduled_at.astimezone(mexico_offset)
            fecha_legible = local_time.strftime("%d/%m/%Y a las %H:%M")

            logger.info(f"Cita agendada: {appointment.id} — {service}{staff_info}")
            return (
                f"✅ ¡Cita confirmada! Tu cita de {service}{staff_info} quedó agendada "
                f"para el {fecha_legible}. Te enviaremos un recordatorio antes de tu cita."
            )

        except ValueError as e:
            logger.error(f"Error parseando fecha: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creando cita: {e}")
            return None

    # ── CANCEL APPOINTMENT ────────────────────────────────────────────────────

    async def _handle_cancel_appointment(
        self,
        action: dict,
        tenant: Tenant,
        contact: Contact,
        db: AsyncSession,
    ) -> str | None:
        from app.models.appointment import Appointment
        from sqlalchemy import and_

        try:
            # Buscar cita próxima activa del contacto
            result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.contact_id == contact.id,
                        Appointment.tenant_id == tenant.id,
                        Appointment.status.in_(["confirmed", "pending"]),
                        Appointment.scheduled_at > datetime.now(timezone.utc),
                    )
                ).order_by(Appointment.scheduled_at)
            )
            appointment = result.scalar_one_or_none()

            if not appointment:
                return "No encontré citas próximas activas a tu nombre. ¿Quieres agendar una nueva?"

            mexico_offset = timezone(timedelta(hours=-6))
            local_time = appointment.scheduled_at.replace(tzinfo=timezone.utc).astimezone(mexico_offset)
            fecha_legible = local_time.strftime("%d/%m/%Y a las %H:%M")

            appointment.status = "cancelled"
            await db.flush()

            logger.info(f"Cita cancelada: {appointment.id} para contact {contact.id}")
            return (
                f"✅ Tu cita de {appointment.title} del {fecha_legible} ha sido cancelada. "
                f"Cuando quieras agendar de nuevo, con gusto te ayudo."
            )

        except Exception as e:
            logger.error(f"Error cancelando cita: {e}")
            return "Tuve un problema cancelando tu cita. Por favor intenta de nuevo."

    # ── RESCHEDULE APPOINTMENT ────────────────────────────────────────────────

    async def _handle_reschedule_appointment(
        self,
        action: dict,
        tenant: Tenant,
        contact: Contact,
        db: AsyncSession,
    ) -> str | None:
        from app.models.appointment import Appointment
        from app.services.staff_service import is_staff_available
        from sqlalchemy import and_

        try:
            date_str = action.get("date")
            time_str = action.get("time")

            if not date_str or not time_str:
                return None

            new_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            mexico_offset = timezone(timedelta(hours=-6))
            new_dt_utc = new_dt.replace(tzinfo=mexico_offset).astimezone(timezone.utc)

            # Buscar cita próxima activa
            result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.contact_id == contact.id,
                        Appointment.tenant_id == tenant.id,
                        Appointment.status.in_(["confirmed", "pending"]),
                        Appointment.scheduled_at > datetime.now(timezone.utc),
                    )
                ).order_by(Appointment.scheduled_at)
            )
            appointment = result.scalar_one_or_none()

            if not appointment:
                return "No encontré citas próximas a reagendar. ¿Quieres agendar una nueva?"

            # Verificar disponibilidad del mismo staff en el nuevo horario
            if appointment.staff_id:
                available = await is_staff_available(
                    db, appointment.staff_id, new_dt_utc, appointment.duration_minutes
                )
                if not available:
                    return (
                        f"Lo siento, ese horario no está disponible. "
                        f"¿Quieres que te muestre los próximos horarios libres?"
                    )

            appointment.scheduled_at = new_dt_utc
            appointment.reminder_sent = False  # Resetear recordatorio
            await db.flush()

            local_time = new_dt_utc.astimezone(mexico_offset)
            fecha_legible = local_time.strftime("%d/%m/%Y a las %H:%M")

            logger.info(f"Cita reagendada: {appointment.id} → {new_dt_utc}")
            return (
                f"✅ ¡Listo! Tu cita de {appointment.title} fue reagendada "
                f"para el {fecha_legible}. Te recordaremos antes de tu cita."
            )

        except Exception as e:
            logger.error(f"Error reagendando cita: {e}")
            return "Tuve un problema reagendando tu cita. Por favor intenta de nuevo."

    # ── GET AVAILABLE SLOTS ───────────────────────────────────────────────────

    async def _handle_get_slots(
        self,
        action: dict,
        tenant: Tenant,
        contact: Contact,
        db: AsyncSession,
    ) -> str | None:
        from app.services.staff_service import (
            get_staff_by_name, get_next_available_slots, format_slots_for_whatsapp
        )

        try:
            staff_name = action.get("staff_name")
            staff_id = None
            staff_label = ""

            if staff_name:
                staff = await get_staff_by_name(db, tenant.id, staff_name)
                if staff:
                    staff_id = staff.id
                    staff_label = f" con {staff.name}"

            slots = await get_next_available_slots(
                db=db,
                tenant_id=tenant.id,
                staff_id=staff_id,
                slots_needed=3,
            )

            if not slots:
                return f"No encontré horarios disponibles{staff_label} en los próximos 14 días."

            slots_str = format_slots_for_whatsapp(slots)
            return (
                f"Estos son los próximos horarios disponibles{staff_label}:\n\n"
                f"{slots_str}\n\n¿Cuál te viene mejor?"
            )

        except Exception as e:
            logger.error(f"Error obteniendo slots: {e}")
            return None

    # ── HUMAN HANDOFF ─────────────────────────────────────────────────────────

    async def _handle_human_handoff(
        self,
        action: dict,
        tenant: Tenant,
        contact: Contact,
        conversation: Conversation,
        db: AsyncSession,
    ) -> str | None:
        from app.services.contact_service import set_bot_enabled

        try:
            await set_bot_enabled(db, contact, enabled=False)
            logger.info(
                f"Handoff activado para contact {contact.id} "
                f"({contact.phone_number}) en tenant {tenant.slug}"
            )
            return (
                "Entendido, voy a conectarte con alguien de nuestro equipo. "
                "En breve te contactarán. 🙏"
            )
        except Exception as e:
            logger.error(f"Error en handoff: {e}")
            return None