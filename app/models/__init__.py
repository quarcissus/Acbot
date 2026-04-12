"""
Importa todos los modelos para que SQLAlchemy los detecte automáticamente.
Los imports están protegidos para evitar circular imports.
"""

# Importar en orden de dependencias (sin FK primero, con FK después)
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.models.contact import Contact
from app.models.staff import Staff
from app.models.conversation import Conversation, Message
from app.models.appointment import Appointment

__all__ = ["AdminUser", "Tenant", "Contact", "Staff", "Conversation", "Message", "Appointment"]