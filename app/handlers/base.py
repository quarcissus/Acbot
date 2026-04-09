"""
BaseHandler — clase base para todos los handlers de vertical.
Implementa la lógica común: cargar historial, llamar a IA, parsear acciones.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.services.ai_service import (
    get_conversation_history,
    generate_response,
    parse_action,
)
from app.services.security_service import validate_and_sanitize

logger = logging.getLogger(__name__)


class BaseHandler(ABC):

    @abstractmethod
    def get_system_prompt(self, tenant: Tenant, contact: Contact) -> str:
        """Construye el system prompt para este tenant y vertical."""
        ...

    async def handle_message(
        self,
        tenant: Tenant,
        contact: Contact,
        conversation: Conversation,
        message: str,
        db: AsyncSession,
    ) -> str:
        """
        Flujo principal:
        1. Valida y sanitiza el mensaje (seguridad)
        2. Carga historial de conversación
        3. Construye system prompt
        4. Llama a OpenAI
        5. Parsea acciones (si las hay)
        6. Ejecuta la acción
        7. Retorna la respuesta limpia
        """
        # 1. Seguridad — validar y sanitizar
        is_valid, processed_message = validate_and_sanitize(message)
        if not is_valid:
            logger.warning(f"Mensaje rechazado por seguridad para tenant {tenant.slug}")
            return processed_message

        # 2. Cargar historial
        history = await get_conversation_history(db, conversation.id)

        # 3. System prompt
        system_prompt = self.get_system_prompt(tenant, contact)

        # 4. Llamar a IA
        raw_response = await generate_response(system_prompt, history, processed_message)

        # 5. Parsear acción
        clean_response, action = parse_action(raw_response)

        # 6. Ejecutar acción si existe
        if action:
            action_result = await self.execute_action(action, tenant, contact, db)
            if action_result:
                clean_response = action_result

        return clean_response

    async def execute_action(
        self,
        action: dict,
        tenant: Tenant,
        contact: Contact,
        db: AsyncSession,
    ) -> str | None:
        """
        Ejecuta acciones detectadas en la respuesta del bot.
        Soporta: create_appointment
        """
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
        """Crea una cita a partir de la acción detectada por la IA."""
        from app.services.appointment_service import create_appointment

        try:
            service = action.get("service", "Consulta")
            date_str = action.get("date")
            time_str = action.get("time")

            if not date_str or not time_str:
                logger.warning(f"Acción create_appointment sin fecha/hora: {action}")
                return None

            # Parsear fecha y hora
            scheduled_at = datetime.strptime(
                f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
            )

            appointment = await create_appointment(
                db=db,
                tenant_id=tenant.id,
                contact_id=contact.id,
                title=service,
                scheduled_at=scheduled_at,
                source="chatbot",
            )

            logger.info(f"Cita agendada: {appointment.id} — {service} el {date_str}")
            return None  # La IA ya generó el mensaje de confirmación

        except ValueError as e:
            logger.error(f"Error parseando fecha de la acción: {e} — {action}")
            return None
        except Exception as e:
            logger.error(f"Error creando cita: {e}")
            return None