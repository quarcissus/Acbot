"""
BaseHandler — clase base para todos los handlers de vertical.
Implementa la lógica común: cargar historial, llamar a IA, parsear acciones.
"""

import logging
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.services.ai_service import (
    get_conversation_history,
    generate_response,
    parse_action,
)

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
        1. Carga historial de conversación
        2. Construye system prompt
        3. Llama a OpenAI
        4. Parsea acciones (si las hay)
        5. Ejecuta la acción
        6. Retorna la respuesta limpia
        """
        # 1. Cargar historial
        history = await get_conversation_history(db, conversation.id)

        # 2. System prompt
        system_prompt = self.get_system_prompt(tenant, contact)

        # 3. Llamar a IA
        raw_response = await generate_response(system_prompt, history, message)

        # 4. Parsear acción
        clean_response, action = parse_action(raw_response)

        # 5. Ejecutar acción si existe
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
        Ejecuta una acción detectada en la respuesta del bot.
        Subclases pueden sobreescribir para agregar acciones específicas.
        Fase 3: aquí se conectará appointment_service.
        """
        action_type = action.get("action")
        logger.info(f"Acción detectada: {action_type} para tenant {tenant.slug}")
        return None
