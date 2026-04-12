"""
Importa todos los modelos para que SQLAlchemy los detecte automáticamente.
"""

from app.models.admin_user import AdminUser
from app.models.tenant import Tenant
from app.models.contact import Contact
from app.models.staff import Staff
from app.models.conversation import Conversation, Message
from app.models.appointment import Appointment
from app.models.business_hours import BusinessHours
from app.models.staff_hours import StaffHours

__all__ = ["AdminUser", "Tenant", "Contact", "Staff", "Conversation", "Message", "Appointment", "BusinessHours", "StaffHours"]