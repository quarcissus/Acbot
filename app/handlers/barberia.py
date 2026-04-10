"""
Handler para barberías.
El bot pregunta con qué barbero quiere el cliente y valida disponibilidad.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.handlers.base import BaseHandler
from app.models.tenant import Tenant
from app.models.contact import Contact


class BarberiaHandler(BaseHandler):

    def staff_label_singular(self) -> str:
        return "barbero"

    def staff_label_plural(self) -> str:
        return "barberos"

    async def _build_system_prompt(
        self, tenant: Tenant, contact: Contact, db: AsyncSession
    ) -> str:
        """Sobreescribe base para inyectar lista de barberos activos."""
        from app.services.staff_service import get_active_staff
        base_prompt = self.get_system_prompt(tenant, contact)
        try:
            staff_list = await get_active_staff(db, tenant.id)
            if staff_list:
                names = [s.name for s in staff_list]
                staff_names = ", ".join(names[:-1]) + f" o {names[-1]}" if len(names) > 1 else names[0]
                base_prompt += f"\n\nBARBEROS DISPONIBLES EN EL NEGOCIO: {staff_names}\nSiempre pregunta al cliente con cuál de estos barberos quiere su cita."
                logger.info(f"System prompt incluye barberos: {staff_names}")
        except Exception as e:
            logger.warning(f"No se pudo cargar staff: {e}")
        return base_prompt

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
1. Pregunta SIEMPRE estos 5 datos antes de agendar: nombre de quien va a la cita, servicio, fecha, hora y barbero
2. Si el cliente no proporciona alguno de estos datos, pregúntalo antes de continuar
3. Cuando tengas TODOS los datos, responde ÚNICAMENTE con la acción, sin texto adicional:
   ###ACTION###
   {{"action": "create_appointment", "service": "nombre del servicio", "date": "YYYY-MM-DD", "time": "HH:MM", "client_name": "nombre de quien va a la cita", "staff_name": "nombre del barbero"}}
   ###END_ACTION###
4. El sistema enviará automáticamente el mensaje de confirmación al cliente
5. Si el sistema te informa que el barbero no está disponible, informa al cliente y pregunta si quiere otro barbero u otro horario
6. NO agregues texto antes ni después de la acción cuando vayas a agendar

OTRAS REGLAS:
1. Responde SIEMPRE en español
2. Sé amigable e informal
3. Máximo 3-4 oraciones por respuesta
4. Cuando el cliente quiera agendar, SIEMPRE lista los servicios con precios en tu primera respuesta, y menciona los barberos disponibles que están listados arriba en BARBEROS DISPONIBLES EN EL NEGOCIO. Ejemplo: "¡Claro! Ofrecemos: corte de cabello ($120), corte + barba ($180), barba ($80), corte fade ($150) y tinte (desde $200). Nuestros barberos son [lista de barberos]. ¿Cuál servicio prefieres, para qué día y hora, y con cuál barbero?"
5. Si no sabes algo, di que pueden llamar directamente al negocio
6. NUNCA inventes precios o servicios que no estén en tu contexto"""