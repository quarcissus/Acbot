"""
BaseHandler — clase base para todos los handlers de vertical.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

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

        # 3. System prompt con lista de barberos disponibles (si aplica)
        system_prompt = await self._build_system_prompt(tenant, contact, db)

        # 4. Llamar a IA
        raw_response = await generate_response(system_prompt, history, processed_message)

        # 5. Parsear acción
        clean_response, action = parse_action(raw_response)

        # 6. Ejecutar acción
        if action:
            action_result = await self.execute_action(action, tenant, contact, db)
            # Siempre usar el resultado del código, nunca el texto de la IA
            # Esto evita que lleguen 2 mensajes
            if action_result:
                return action_result
            return "¡Tu cita ha sido agendada! Te enviaremos un recordatorio antes de tu cita."

        return clean_response

    async def _build_system_prompt(
        self, tenant: Tenant, contact: Contact, db: AsyncSession
    ) -> str:
        """
        Construye el system prompt base.
        Subclases pueden sobreescribir para agregar contexto específico (staff, etc.)
        """
        return self.get_system_prompt(tenant, contact)

    def staff_label_singular(self) -> str:
        """Término para un empleado. Sobreescribir en cada handler."""
        return "persona"

    def staff_label_plural(self) -> str:
        """Término para varios empleados. Sobreescribir en cada handler."""
        return "personas disponibles"

    async def execute_action(
        self,
        action: dict,
        tenant: Tenant,
        contact: Contact,
        db: AsyncSession,
    ) -> str | None:
        action_type = action.get("action")
        logger.info(f"Acción detectada: {action_type} para tenant {tenant.slug}")

        if action_type == "create_appointment":
            return await self._handle_create_appointment(action, tenant, contact, db)

        return None

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

        try:
            service = action.get("service", "Consulta")
            date_str = action.get("date")
            time_str = action.get("time")
            staff_name = action.get("staff_name")

            if not date_str or not time_str:
                logger.warning(f"Acción sin fecha/hora: {action}")
                return None

            scheduled_at = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

            # México es UTC-6 fijo (eliminó horario de verano en 2023)
            mexico_offset = timezone(timedelta(hours=-6))
            scheduled_at = scheduled_at.replace(tzinfo=mexico_offset).astimezone(timezone.utc)

            staff_id = None
            staff_member = None

            # Buscar el barbero solicitado
            if staff_name:
                staff_member = await get_staff_by_name(db, tenant.id, staff_name)

                if staff_member:
                    # Verificar disponibilidad
                    available = await is_staff_available(
                        db, staff_member.id, scheduled_at, staff_member.appointment_duration
                    )
                    if not available:
                        # Staff no disponible — buscar otros
                        other_staff = await get_available_staff(db, tenant.id, scheduled_at)
                        if other_staff:
                            other_names = [s.name for s in other_staff]
                            names_str = ", ".join(other_names[:-1]) + f" o {other_names[-1]}" if len(other_names) > 1 else other_names[0]
                            if len(other_names) > 1:
                                label = self.staff_label_plural()
                                return (
                                    f"Lo siento, {staff_member.name} no está disponible a esa hora. "
                                    f"Estos {label} sí están disponibles: {names_str}. ¿Con cuál prefieres?"
                                )
                            else:
                                label = self.staff_label_singular()
                                return (
                                    f"Lo siento, {staff_member.name} no está disponible a esa hora. "
                                    f"Este {label} sí está disponible: {names_str}. ¿Quieres que te agende con él?"
                                )
                        else:
                            return (
                                f"Lo siento, no hay {self.staff_label_plural()} disponibles el {date_str} a las {time_str}. "
                                f"¿Quieres intentar con otro horario?"
                            )
                    staff_id = staff_member.id

            # Crear la cita
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
            # Formatear hora en México para mostrar al cliente
            mexico_offset = timezone(timedelta(hours=-6))
            local_time = scheduled_at.astimezone(mexico_offset)
            fecha_legible = local_time.strftime("%d/%m/%Y a las %H:%M")

            logger.info(f"Cita agendada: {appointment.id} — {service}{staff_info} el {date_str}")
            return f"✅ ¡Cita confirmada! Tu cita de {service}{staff_info} quedó agendada para el {fecha_legible}. Te enviaremos un recordatorio antes de tu cita."

        except ValueError as e:
            logger.error(f"Error parseando fecha: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creando cita: {e}")
            return None