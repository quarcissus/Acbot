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
        template_name: Nombre exacto del template en Meta (ej: "appointment_reminder").
        language_code: Código de idioma (ej: "es_MX").
        body_parameters: Lista de strings que reemplazan {{1}}, {{2}}, etc. en el template.

    Returns:
        Respuesta JSON de Meta.
    """
    url = f"{settings.meta_graph_url}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_access_token}",
        "Content-Type": "application/json",
    }

    components = []
    if body_parameters:
        components.append(
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": param} for param in body_parameters
                ],
            }
        )

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
    service: str,
    datetime_str: str,
    business_name: str,
) -> dict:
    """
    Shortcut para enviar el template 'appointment_reminder'.
    Template: "Hola {{1}}, te recordamos que tienes una cita de {{2}} para {{3}} en {{4}}."
    """
    return await send_template_message(
        phone_number_id=phone_number_id,
        to=to,
        template_name="appointment_reminder",
        language_code="es_MX",
        body_parameters=[client_name, service, datetime_str, business_name],
    )
