"""
Seguridad del webhook de Meta.
Meta firma cada request con HMAC-SHA256 usando el app secret.
NUNCA procesar mensajes sin verificar la firma.
"""

import hashlib
import hmac
import logging
from fastapi import HTTPException, Request

from app.config.settings import settings

logger = logging.getLogger(__name__)


async def verify_meta_signature(request: Request) -> bytes:
    """
    Verifica la firma X-Hub-Signature-256 de Meta en cada POST al webhook.
    
    Meta calcula: HMAC-SHA256(body, APP_SECRET) y lo envía en el header.
    Nosotros recalculamos y comparamos con hmac.compare_digest (tiempo constante).
    
    Returns:
        El body raw como bytes si la firma es válida.
    
    Raises:
        HTTPException 403 si la firma es inválida o falta el header.
    """
    signature_header = request.headers.get("X-Hub-Signature-256", "")

    if not signature_header:
        logger.warning("Webhook recibido sin header X-Hub-Signature-256")
        raise HTTPException(status_code=403, detail="Falta firma de Meta")

    body = await request.body()

    # Calcular firma esperada
    expected_signature = (
        "sha256="
        + hmac.new(
            settings.meta_app_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
    )

    # Comparar en tiempo constante para evitar timing attacks
    if not hmac.compare_digest(expected_signature, signature_header):
        logger.warning(
            "Firma de Meta inválida. "
            f"Esperada: {expected_signature[:20]}... "
            f"Recibida: {signature_header[:20]}..."
        )
        raise HTTPException(status_code=403, detail="Firma inválida")

    return body


def skip_signature_in_dev() -> bool:
    """
    En desarrollo, permite saltar la verificación de firma
    cuando META_APP_SECRET no está configurado.
    
    NUNCA debe retornar True en producción.
    """
    return (
        settings.environment == "development"
        and not settings.meta_app_secret
    )
