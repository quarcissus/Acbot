"""
BaseHandler — interfaz común para todos los handlers de vertical.
Implementado en Fase 2.
"""

from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tenant import Tenant
from app.models.contact import Contact
from app.models.conversation import Conversation


class BaseHandler(ABC):
    """
    Clase base que todos los handlers de vertical deben implementar.
    En Fase 2 se agregan: ai_service, historial de conversación, parse de acciones.
    """

    @abstractmethod
    async def handle_message(
        self,
        tenant: Tenant,
        contact: Contact,
        conversation: Conversation,
        message: str,
        db: AsyncSession,
    ) -> str:
        """Procesa un mensaje y retorna la respuesta del bot."""
        ...

    @abstractmethod
    def get_system_prompt(self, tenant: Tenant) -> str:
        """Construye el system prompt para OpenAI según el tenant."""
        ...
