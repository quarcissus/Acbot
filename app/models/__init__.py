"""
Importa todos los modelos para que Alembic los detecte automáticamente.
Este archivo es crítico: sin estos imports, Alembic no genera las migraciones.
"""

from app.models.tenant import Tenant
from app.models.contact import Contact
from app.models.conversation import Conversation, Message
from app.models.appointment import Appointment
from app.models.staff import Staff
from app.models.admin_user import AdminUser

__all__ = ["Tenant", "Contact", "Conversation", "Message", "Appointment", "Staff", "AdminUser"]