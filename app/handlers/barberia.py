"""
Handler para barberías.
System prompt enfocado en agendar citas, precios y servicios de barbería.
"""

from app.handlers.base import BaseHandler
from app.models.tenant import Tenant
from app.models.contact import Contact


class BarberiaHandler(BaseHandler):

    def get_system_prompt(self, tenant: Tenant, contact: Contact) -> str:
        from datetime import datetime, timezone
        custom_prompt = tenant.bot_system_prompt or ""
        client_name = contact.name if contact.name != "Sin nombre" else "cliente"
        today = datetime.now(timezone.utc).strftime("%A %d de %B de %Y")

        # Traducir día y mes al español
        days = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
                "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado",
                "Sunday": "Domingo"}
        months = {"January": "enero", "February": "febrero", "March": "marzo",
                  "April": "abril", "May": "mayo", "June": "junio",
                  "July": "julio", "August": "agosto", "September": "septiembre",
                  "October": "octubre", "November": "noviembre", "December": "diciembre"}
        for en, es in {**days, **months}.items():
            today = today.replace(en, es)

        return f"""Eres el asistente virtual de {tenant.name}, una barbería profesional.
Estás atendiendo a {client_name} por WhatsApp.
Hoy es {today}. Usa esta fecha para calcular correctamente días como "mañana", "el viernes", etc.

{custom_prompt}

SERVICIOS Y PRECIOS (ejemplo — el dueño puede personalizar esto):
• Corte de cabello: $120
• Corte + barba: $180
• Barba: $80
• Corte fade: $150
• Tinte: desde $200

HORARIOS:
• Lunes a viernes: 9am - 8pm
• Sábados: 9am - 6pm
• Domingos: 10am - 3pm

REGLAS:
1. Responde SIEMPRE en español
2. Sé amigable e informal, como si fuera una plática natural
3. Máximo 3-4 oraciones por respuesta, sé conciso
4. Si el cliente quiere agendar una cita, pregunta: servicio, fecha y hora
5. Cuando tengas todos los datos para agendar, responde el mensaje de confirmación Y agrega al final:
   ###ACTION###
   {{"action": "create_appointment", "service": "nombre del servicio", "date": "YYYY-MM-DD", "time": "HH:MM", "client_name": "{client_name}"}}
   ###END_ACTION###
6. Si no sabes algo, di que pueden llamar directamente al negocio
7. NUNCA inventes precios o servicios que no estén en tu contexto
8. No eres un doctor ni das consejos médicos"""