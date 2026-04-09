"""
Sender — envía mensajes de texto libre a través de Meta Cloud API.
Solo para mensajes dentro de la ventana de 24h.
"""

import logging
import httpx
from app.config.settings import settings

logger = logging.getLogger(__name__)


async def send_text_message(
    phone_number_id: str,
    to: str,
    body: str,
) -> dict:
    """
    Envía un mensaje de texto al número `to` usando el `phone_number_id` del tenant.

    Args:
        phone_number_id: El Phone Number ID de Meta del tenant (no el número visible).
        to: Número del destinatario en formato internacional sin '+' (ej: "5213312345678").
        body: Texto del mensaje (máx ~4096 chars).

    Returns:
        Respuesta JSON de Meta con el message_id si fue exitoso.

    Raises:
        httpx.HTTPStatusError: Si Meta rechaza el request.
    """
    url = f"{settings.meta_graph_url}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to.lstrip("+"),  # Meta no acepta el + en este campo
        "type": "text",
        "text": {"body": body, "preview_url": False},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            logger.error(
                f"Error enviando mensaje a {to}: "
                f"HTTP {response.status_code} — {response.text}"
            )
            response.raise_for_status()

        result = response.json()
        logger.info(
            f"Mensaje enviado a {to} | "
            f"wa_id: {result.get('messages', [{}])[0].get('id', 'N/A')}"
        )
        return result


async def mark_as_read(phone_number_id: str, wa_message_id: str) -> None:
    """
    Marca un mensaje entrante como leído (muestra las palomitas azules).
    Buena práctica para UX: hacerlo justo antes de enviar la respuesta.

    Args:
        phone_number_id: Phone Number ID del tenant.
        wa_message_id: El ID del mensaje del usuario (viene en el webhook).
    """
    url = f"{settings.meta_graph_url}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": wa_message_id,
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(url, json=payload, headers=headers)
        except Exception as e:
            # No es crítico si falla el "read", no interrumpir el flujo
            logger.warning(f"No se pudo marcar como leído {wa_message_id}: {e}")
