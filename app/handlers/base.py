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
            if action_result:
                clean_response = action_result

        return clean_response

    async def _build_system_prompt(
        self, tenant: Tenant, contact: Contact, db: AsyncSession
    ) -> str:
        """Construye el system prompt e inyecta la lista de barberos activos."""
        base_prompt = self.get_system_prompt(tenant, contact)

        # Inyectar lista de staff si el tenant tiene barberos configurados
        try:
            from app.services.staff_service import get_active_staff
            staff_list = await get_active_staff(db, tenant.id)
            logger.info(f"Staff cargado: {[s.name for s in staff_list]}")
            if staff_list:
                names = [s.name for s in staff_list]
                staff_names = ", ".join(names[:-1]) + f" o {names[-1]}" if len(names) > 1 else names[0]
                base_prompt += f"\n\nBARBEROS DISPONIBLES EN EL NEGOCIO: {staff_names}\nSiempre pregunta al cliente con cuál de estos barberos quiere su cita."
                logger.info(f"System prompt incluye barberos: {staff_names}")
        except Exception as e:
            logger.warning(f"No se pudo cargar staff: {e}")

        return base_prompt

    def get_system_prompt(self, tenant: Tenant, contact: Contact) -> str:
        return ""

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
            get_staff_by_name, is_staff_available, get_available_staff, format_staff_list
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
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

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
                        # Barbero no disponible — buscar otros
                        other_staff = await get_available_staff(db, tenant.id, scheduled_at)
                        if other_staff:
                            names = format_staff_list(other_staff)
                            return (
                                f"Lo siento, {staff_member.name} no está disponible a esa hora. "
                                f"Estos barberos sí están disponibles: {names}. ¿Con cuál prefieres?"
                            )
                        else:
                            return (
                                f"Lo siento, no hay barberos disponibles el {date_str} a las {time_str}. "
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
            logger.info(f"Cita agendada: {appointment.id} — {service}{staff_info} el {date_str}")
            return None  # La IA ya generó el mensaje de confirmación

        except ValueError as e:
            logger.error(f"Error parseando fecha: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creando cita: {e}")
            return None