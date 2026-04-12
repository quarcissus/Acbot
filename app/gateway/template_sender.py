"""
Template Sender — envía mensajes usando templates aprobados por Meta.
Necesario para iniciar conversaciones o contactar después de 24h.
"""

import logging
import httpx
from app.config.settings import settings

logger = logging.getLogger(__name__)


async def send_template_message(
    phone_number_id: str,
    to: str,
    template_name: str,
    language_code: str,
    body_parameters: list[str],
) -> dict:
    """
    Envía un template aprobado por Meta.

    Args:
        phone_number_id: Phone Number ID del tenant.
        to: Número del destinatario sin '+'.
        template_name: Nombre exacto del template en Meta.
        language_code: Código de idioma (ej: "es_MX").
        body_parameters: Lista de strings que reemplazan {{1}}, {{2}}, etc.
    """
    url = f"{settings.meta_graph_url}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_access_token}",
        "Content-Type": "application/json",
    }

    components = []
    if body_parameters:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": param} for param in body_parameters],
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": to.lstrip("+"),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": components,
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            logger.error(
                f"Error enviando template '{template_name}' a {to}: "
                f"HTTP {response.status_code} — {response.text}"
            )
            response.raise_for_status()

        result = response.json()
        logger.info(f"Template '{template_name}' enviado a {to}")
        return result


async def send_appointment_reminder(
    phone_number_id: str,
    to: str,
    client_name: str,
    business_name: str,
    date_str: str,
    time_str: str,
) -> dict:
    """
    Envía el template 'appointment_reminder'.

    Template: "Hola {{1}}, te recordamos tu cita en {{2}} el {{3}} a las {{4}}.
    Si necesitas cancelar o cambiar, responde este mensaje."

    Variables:
        {{1}} = nombre del cliente
        {{2}} = nombre del negocio
        {{3}} = fecha (ej: "lunes 14 de abril")
        {{4}} = hora (ej: "10:00")
    """
    return await send_template_message(
        phone_number_id=phone_number_id,
        to=to,
        template_name="appointment_reminder",
        language_code="es_MX",
        body_parameters=[client_name, business_name, date_str, time_str],
    )


async def send_appointment_confirmation(
    phone_number_id: str,
    to: str,
    client_name: str,
    business_name: str,
    date_str: str,
    time_str: str,
    barber_name: str | None = None,
) -> dict:
    """
    Envía el template 'appointment_confirmation'.

    Template: "Hola {{1}}, tu cita en {{2}} fue confirmada para el {{3}}
    a las {{4}} con {{5}}. Te esperamos!"

    Variables:
        {{1}} = nombre del cliente
        {{2}} = nombre del negocio
        {{3}} = fecha
        {{4}} = hora
        {{5}} = nombre del barbero (o "nuestro equipo" si no hay)
    """
    return await send_template_message(
        phone_number_id=phone_number_id,
        to=to,
        template_name="appointment_confirm",
        language_code="es_MX",
        body_parameters=[
            client_name,
            business_name,
            date_str,
            time_str,
            barber_name or "nuestro equipo",
        ],
    )