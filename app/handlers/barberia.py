"""
Handler para barberías.
El bot pregunta con qué barbero quiere el cliente y valida disponibilidad.
Los horarios del negocio se leen dinámicamente desde la DB.
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
        """Inyecta lista de barberos activos Y horarios desde la DB."""
        from app.services.staff_service import get_active_staff
        from app.services.business_hours_service import get_business_hours, format_hours_for_prompt

        # Cargar horarios del negocio
        try:
            hours_list = await get_business_hours(db, tenant.id)
            hours_text = format_hours_for_prompt(hours_list)
        except Exception as e:
            logger.warning(f"No se pudo cargar horarios: {e}")
            hours_list = []
            hours_text = "• Lunes a viernes: 8:00 - 20:00\n• Sábados: 8:00 - 18:00\n• Domingos: cerrado"

        # Horario de hoy específicamente
        mexico_offset = timezone(timedelta(hours=-6))
        now_mexico = datetime.now(timezone.utc).astimezone(mexico_offset)
        current_weekday = now_mexico.weekday()

        today_hours = "cerrado"
        open_days = []
        for h in hours_list:
            if h.is_open:
                open_days.append(h.weekday_name)
                if h.weekday == current_weekday:
                    today_hours = f"{h.open_time} - {h.close_time}"

        open_days_str = ", ".join(open_days) if open_days else "ningún día configurado"

        logger.info(f"Horarios cargados para tenant {tenant.slug}: {open_days_str}")
        logger.info(f"hours_text: {hours_text}")

        base_prompt = self.get_system_prompt(tenant, contact, hours_text, today_hours, open_days_str)

        # Cargar staff activo
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

    def get_system_prompt(
        self,
        tenant: Tenant,
        contact: Contact,
        hours_text: str = "",
        today_hours: str = "ver horario",
        open_days_str: str = "lunes a sábado",
    ) -> str:
        custom_prompt = tenant.bot_system_prompt or ""
        client_name = contact.name if contact.name != "Sin nombre" else "cliente"

        mexico_offset = timezone(timedelta(hours=-6))
        now_mexico = datetime.now(timezone.utc).astimezone(mexico_offset)
        today = now_mexico.strftime("%A %d de %B de %Y")

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
{hours_text}
• Horario de hoy: {today_hours}

REGLAS PARA AGENDAR CITAS:
1. Antes de agendar SIEMPRE reúne estos 5 datos: nombre, servicio, fecha, hora y barbero.
2. IMPORTANTE — Interpretar horas del cliente:
   - Horas claramente de tarde (1, 2, 3, 4, 5, 6, 7): interprétalas como PM. Nunca como madrugada.
   - Horas de mañana (9, 10, 11, 12): interprétalas como AM.
   - El 8 es ambiguo (puede ser 8am o 8pm). Si el cliente dice "las 8" sin aclarar, PREGUNTA: "¿Las 8 de la mañana o las 8 de la noche?"
   - Ejemplos: "las 3" = 15:00, "las 11" = 11:00, "las 7" = 19:00.
3. IMPORTANTE — Validar día y hora:
   - Días válidos para agendar: {open_days_str}
   - Si el cliente pide un día cerrado, dile amablemente que ese día no trabajamos y sugiere el día hábil más cercano.
   - Si el cliente pide una hora fuera del horario de ese día, dile el horario correcto y sugiere una hora válida.
   - NUNCA rechaces un día válido por error — verifica siempre contra la lista de días abiertos.
4. Cuando tengas todos los datos Y el día/hora sean válidos, responde ÚNICAMENTE con la acción:
   ###ACTION###
   {{"action": "create_appointment", "service": "servicio", "date": "YYYY-MM-DD", "time": "HH:MM", "client_name": "nombre", "staff_name": "nombre del barbero"}}
   ###END_ACTION###
5. El sistema confirma la cita automáticamente. NO agregues texto antes ni después de la acción.
6. Si el sistema avisa que el barbero no está disponible, pregunta si prefiere otro barbero u otro horario.

CANCELACIONES Y REAGENDAMIENTOS:
- Si el cliente quiere CANCELAR su cita, genera:
  ###ACTION###
  {{"action": "cancel_appointment"}}
  ###END_ACTION###
- Si el cliente quiere REAGENDAR, pide la nueva fecha y hora, valida el día y horario, luego genera:
  ###ACTION###
  {{"action": "reschedule_appointment", "date": "YYYY-MM-DD", "time": "HH:MM"}}
  ###END_ACTION###

MOSTRAR HORARIOS DISPONIBLES:
- Si el cliente pregunta qué horarios hay disponibles, genera:
  ###ACTION###
  {{"action": "get_available_slots", "staff_name": "nombre del barbero o null si no importa"}}
  ###END_ACTION###

ESCALAR A HUMANO:
- Si el cliente tiene una queja o pide hablar con una persona, genera:
  ###ACTION###
  {{"action": "human_handoff"}}
  ###END_ACTION###

OTRAS REGLAS:
1. Responde SIEMPRE en español, sé amigable e informal.
2. Máximo 3-4 oraciones por respuesta.
3. Al primer mensaje de agendar, lista servicios con precios y menciona los barberos disponibles.
4. Si no sabes algo, di que pueden llamar directamente al negocio.
5. NUNCA inventes precios o servicios que no estén en tu contexto."""