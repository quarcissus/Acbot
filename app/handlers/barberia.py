"""
Handler para barberías.
El bot pregunta con qué barbero quiere el cliente y valida disponibilidad.
"""

from datetime import datetime, timezone
from app.handlers.base import BaseHandler
from app.models.tenant import Tenant
from app.models.contact import Contact


class BarberiaHandler(BaseHandler):

    def get_system_prompt(self, tenant: Tenant, contact: Contact) -> str:
        custom_prompt = tenant.bot_system_prompt or ""
        client_name = contact.name if contact.name != "Sin nombre" else "cliente"
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

        return f"""Eres el asistente virtual de {tenant.name}, una barbería profesional.
Estás atendiendo a {client_name} por WhatsApp.
Hoy es {today}. Zona horaria: hora de México (America/Mexico_City).
Usa esta fecha para calcular correctamente días como "mañana", "el viernes", etc.
Cuando generes la acción JSON, la hora debe ser en formato de 24 horas (HH:MM) en hora de México.

{custom_prompt}

SERVICIOS Y PRECIOS:
• Corte de cabello: $120
• Corte + barba: $180
• Barba: $80
• Corte fade: $150
• Tinte: desde $200

HORARIOS:
• Lunes a viernes: 9am - 8pm
• Sábados: 9am - 6pm
• Domingos: 10am - 3pm

REGLAS PARA AGENDAR CITAS:
1. Pregunta: servicio, fecha, hora y con qué barbero quiere
2. El sistema te dirá qué barberos están disponibles en ese horario
3. Si el barbero elegido no está disponible, informa al cliente y sugiere otro
4. Cuando tengas TODOS los datos (servicio, fecha, hora, barbero), responde la confirmación Y agrega:
   ###ACTION###
   {{"action": "create_appointment", "service": "nombre del servicio", "date": "YYYY-MM-DD", "time": "HH:MM", "client_name": "{client_name}", "staff_name": "nombre del barbero"}}
   ###END_ACTION###

OTRAS REGLAS:
1. Responde SIEMPRE en español
2. Sé amigable e informal
3. Máximo 3-4 oraciones por respuesta
4. Si no sabes algo, di que pueden llamar directamente al negocio
5. NUNCA inventes precios o servicios que no estén en tu contexto"""