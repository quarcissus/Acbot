"""
Importa todos los modelos para que Alembic los detecte automáticamente.
Este archivo es crítico: sin estos imports, Alembic no genera las migraciones.
"""

from app.models.tenant import Tenant
from app.models.contact import Contact
from app.models.conversation import Conversation, Message
from app.models.appointment import Appointment

__all__ = ["Tenant", "Contact", "Conversation", "Message", "Appointment"]
