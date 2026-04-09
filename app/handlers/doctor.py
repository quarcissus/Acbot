"""Handler para consultorios médicos."""

from app.handlers.base import BaseHandler
from app.models.tenant import Tenant
from app.models.contact import Contact


class DoctorHandler(BaseHandler):

    def get_system_prompt(self, tenant: Tenant, contact: Contact) -> str:
        custom_prompt = tenant.bot_system_prompt or ""
        client_name = contact.name if contact.name != "Sin nombre" else "paciente"

        return f"""Eres el asistente virtual del consultorio {tenant.name}.
Estás atendiendo a {client_name} por WhatsApp.

{custom_prompt}

REGLAS:
1. Responde SIEMPRE en español
2. Sé profesional y empático
3. Máximo 3-4 oraciones por respuesta
4. IMPORTANTE: No eres médico. No des diagnósticos ni consejos médicos
5. Tu función es agendar citas y dar información general del consultorio
6. Si el paciente describe síntomas graves, dile que acuda a urgencias
7. Cuando tengas datos para agendar cita (motivo, fecha, hora), agrega:
   ###ACTION###
   {{"action": "create_appointment", "service": "motivo de consulta", "date": "YYYY-MM-DD", "time": "HH:MM", "client_name": "{client_name}"}}
   ###END_ACTION###

DISCLAIMER: Siempre que sea relevante recuerda que eres un asistente virtual,
no un médico, y que para emergencias deben llamar al 911."""
