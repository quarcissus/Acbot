"""
Webhook — endpoints que Meta llama para verificación y mensajes entrantes.

GET  /webhook  → Verificación inicial (Meta confirma que el endpoint existe)
POST /webhook  → Mensajes entrantes en tiempo real
"""

import logging
import json
from fastapi import APIRouter, Request, Response, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.database import get_db
from app.core.security import verify_meta_signature, skip_signature_in_dev
from app.gateway.router import route_incoming_message

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhook"])


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
) -> Response:
    """
    Meta llama este endpoint una sola vez para verificar que el webhook es tuyo.
    Debes responder con hub.challenge si el verify_token coincide.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        logger.info("Webhook verificado por Meta")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning(
        f"Verificación de webhook fallida. "
        f"mode={hub_mode}, token_match={hub_verify_token == settings.meta_verify_token}"
    )
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Meta envía aquí todos los eventos: mensajes entrantes, cambios de estado, etc.
    
    Estructura del payload de Meta:
    {
      "object": "whatsapp_business_account",
      "entry": [{
        "id": "WABA_ID",
        "changes": [{
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": "..."},
            "messages": [{"from": "...", "id": "...", "text": {"body": "..."}}]
          }
        }]
      }]
    }
    """
    # Verificar firma de Meta (seguridad)
    if skip_signature_in_dev():
        logger.warning("⚠️  Verificación de firma deshabilitada (modo desarrollo)")
        body = await request.body()
    else:
        body = await verify_meta_signature(request)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Payload del webhook no es JSON válido")
        raise HTTPException(status_code=400, detail="JSON inválido")

    # Meta espera siempre HTTP 200, incluso si hubo error interno
    # Si respondemos != 200, Meta reintenta y duplica mensajes
    try:
        await _process_webhook_payload(payload, db)
    except Exception as e:
        logger.exception(f"Error procesando webhook: {e}")
        # Aún retornamos 200 para que Meta no reintente
    
    return {"status": "ok"}


async def _process_webhook_payload(payload: dict, db: AsyncSession) -> None:
    """
    Parsea el payload de Meta y extrae los mensajes de texto.
    Ignora eventos que no sean mensajes (delivery receipts, read receipts, etc.)
    """
    if payload.get("object") != "whatsapp_business_account":
        return

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # Solo procesar cambios de tipo "messages"
            if change.get("field") != "messages":
                continue

            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            if not phone_number_id:
                logger.warning("Webhook sin phone_number_id en metadata")
                continue

            # Procesar cada mensaje en el batch (Meta puede enviar varios)
            for message in value.get("messages", []):
                await _handle_single_message(message, phone_number_id, db)


async def _handle_single_message(
    message: dict,
    phone_number_id: str,
    db: AsyncSession,
) -> None:
    """Extrae datos de un mensaje individual y lo enruta."""
    msg_type = message.get("type")
    from_number = message.get("from")
    wa_message_id = message.get("id")

    if not all([msg_type, from_number, wa_message_id]):
        logger.warning(f"Mensaje con campos faltantes: {message}")
        return

    # Fase 1: solo procesamos mensajes de texto
    # Fase futura: agregar "image", "audio", "location", etc.
    if msg_type == "text":
        body = message.get("text", {}).get("body", "").strip()
        if not body:
            return

        await route_incoming_message(
            db=db,
            phone_number_id=phone_number_id,
            from_number=from_number,
            message_body=body,
            wa_message_id=wa_message_id,
        )
    else:
        logger.info(f"Tipo de mensaje no soportado en Fase 1: {msg_type}")
