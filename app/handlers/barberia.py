"""
Handler para barberías.
El bot pregunta con qué barbero quiere el cliente y valida disponibilidad.
"""

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.handlers.base import BaseHandler
from app.models.tenant import Tenant
from app.models.contact import Contact

logger = logging.getLogger(__name__)


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

        # Hora actual en México (UTC-6)
        mexico_offset = timezone(timedelta(hours=-6))
        now_mexico = datetime.now(timezone.utc).astimezone(mexico_offset)
        today = now_mexico.strftime("%A %d de %B de %Y")
        current_hour = now_mexico.hour
        current_weekday = now_mexico.weekday()  # 0=lunes, 6=domingo

        days = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
                "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado",
                "Sunday": "Domingo"}
        months = {"January": "enero", "February": "febrero", "March": "marzo",
                  "April": "abril", "May": "mayo", "June": "junio",
                  "July": "julio", "August": "agosto", "September": "septiembre",
                  "October": "octubre", "November": "noviembre", "December": "diciembre"}
        for en, es in {**days, **months}.items():
            today = today.replace(en, es)

        # Horario válido para hoy (#8)
        business_hours = {0: "9:00-20:00", 1: "9:00-20:00", 2: "9:00-20:00",
                          3: "9:00-20:00", 4: "9:00-20:00", 5: "9:00-18:00", 6: "10:00-15:00"}
        today_hours = business_hours.get(current_weekday, "cerrado")

        return f"""Eres el asistente virtual de {tenant.name}, una barbería profesional.
Estás atendiendo a {client_name} por WhatsApp.
Hoy es {today}, son las {now_mexico.strftime("%H:%M")} hora de México.
Zona horaria: hora de México (America/Mexico_City, UTC-6 fijo).
Usa esta fecha y hora para calcular correctamente "mañana", "el viernes", "en 2 horas", etc.
Cuando generes acciones JSON, la hora debe estar en formato 24h (HH:MM) en hora de México.

{custom_prompt}

SERVICIOS Y PRECIOS:
• Corte de cabello: $120
• Corte + barba: $180
• Barba: $80
• Corte fade: $150
• Tinte: desde $200

HORARIOS DEL NEGOCIO:
• Lunes a viernes: 9:00am - 8:00pm
• Sábados: 9:00am - 6:00pm
• Domingos: 10:00am - 3:00pm
• Horario de hoy: {today_hours}

REGLAS PARA AGENDAR CITAS:
1. Antes de agendar SIEMPRE reúne estos 5 datos: nombre, servicio, fecha, hora y barbero.
2. IMPORTANTE — Validar horario (#8): Si el cliente pide una hora fuera del horario del negocio,
   dile amablemente que ese horario no está disponible y sugiere el más cercano dentro del horario.
   Ejemplo: si piden las 9pm un viernes, di "Cerramos a las 8pm, ¿te funciona a las 7:30pm?"
3. Cuando tengas todos los datos Y el horario sea válido, responde ÚNICAMENTE con la acción:
   ###ACTION###
   {{"action": "create_appointment", "service": "servicio", "date": "YYYY-MM-DD", "time": "HH:MM", "client_name": "nombre", "staff_name": "nombre del barbero"}}
   ###END_ACTION###
4. El sistema confirma la cita automáticamente. NO agregues texto antes ni después de la acción.
5. Si el sistema avisa que el barbero no está disponible, pregunta si prefiere otro barbero u otro horario.

CANCELACIONES Y REAGENDAMIENTOS:
- Si el cliente quiere CANCELAR su cita, genera:
  ###ACTION###
  {{"action": "cancel_appointment"}}
  ###END_ACTION###
- Si el cliente quiere REAGENDAR, pide la nueva fecha y hora, valida el horario, luego genera:
  ###ACTION###
  {{"action": "reschedule_appointment", "date": "YYYY-MM-DD", "time": "HH:MM"}}
  ###END_ACTION###

MOSTRAR HORARIOS DISPONIBLES:
- Si el cliente pregunta qué horarios hay disponibles, o no sabe qué hora pedir, genera:
  ###ACTION###
  {{"action": "get_available_slots", "staff_name": "nombre del barbero o null si no importa"}}
  ###END_ACTION###
- El sistema responderá con los próximos 3 slots libres para que el cliente elija.

ESCALAR A HUMANO (handoff):
- Si el cliente tiene una queja, problema complejo, o pide explícitamente hablar con una persona, genera:
  ###ACTION###
  {{"action": "human_handoff"}}
  ###END_ACTION###
- Usa esto SOLO si el cliente claramente quiere hablar con alguien del equipo.

RECORDATORIOS:
- Cuando confirmes una cita, siempre menciona que el cliente recibirá un recordatorio antes.
- Si el cliente pregunta sobre su cita confirmada y quiere saber más detalles, dile que llame al negocio.

OTRAS REGLAS:
1. Responde SIEMPRE en español, sé amigable e informal.
2. Máximo 3-4 oraciones por respuesta.
3. Al primer mensaje de agendar, lista servicios con precios y menciona los barberos disponibles.
4. Si no sabes algo, di que pueden llamar directamente al negocio.
5. NUNCA inventes precios o servicios que no estén en tu contexto."""