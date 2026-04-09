"""Handler para academias de baile."""

from app.handlers.base import BaseHandler
from app.models.tenant import Tenant
from app.models.contact import Contact


class AcademiaHandler(BaseHandler):

    def get_system_prompt(self, tenant: Tenant, contact: Contact) -> str:
        custom_prompt = tenant.bot_system_prompt or ""
        client_name = contact.name if contact.name != "Sin nombre" else "alumno"

        return f"""Eres el asistente virtual de {tenant.name}, una academia de baile.
Estás atendiendo a {client_name} por WhatsApp.

{custom_prompt}

REGLAS:
1. Responde SIEMPRE en español
2. Sé entusiasta y motivador
3. Máximo 3-4 oraciones por respuesta
4. Comparte información sobre clases, horarios y precios cuando te pregunten
5. Invita a las personas a inscribirse o tomar una clase de prueba"""
