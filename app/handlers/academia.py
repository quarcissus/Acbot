"""Handler para academias de baile."""

from app.handlers.base import BaseHandler
from app.models.tenant import Tenant
from app.models.contact import Contact


class AcademiaHandler(BaseHandler):

    def get_system_prompt(self, tenant: Tenant, contact: Contact) -> str:
        from datetime import datetime, timezone
        custom_prompt = tenant.bot_system_prompt or ""
        client_name = contact.name if contact.name != "Sin nombre" else "alumno"
        today = datetime.now(timezone.utc).strftime("%A %d de %B de %Y")
        days = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
                "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado",
                "Sunday": "Domingo"}
        months = {"January": "enero", "February": "febrero", "March": "marzo",
                  "April": "abril", "May": "mayo", "June": "junio",
                  "July": "julio", "August": "agosto", "September": "septiembre",
                  "October": "octubre", "November": "noviembre", "December": "diciembre"}
        for en, es in {**days, **months}.items():
            today = today.replace(en, es)

        return f"""Eres el asistente virtual de {tenant.name}, una academia de baile.
Estás atendiendo a {client_name} por WhatsApp.
Hoy es {today}. Usa esta fecha para calcular correctamente días como "mañana", "el viernes", etc.

{custom_prompt}

REGLAS:
1. Responde SIEMPRE en español
2. Sé entusiasta y motivador
3. Máximo 3-4 oraciones por respuesta
4. Comparte información sobre clases, horarios y precios cuando te pregunten
5. Invita a las personas a inscribirse o tomar una clase de prueba"""