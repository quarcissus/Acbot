"""
Tests para el webhook de Meta.
Corre con: pytest tests/test_webhook.py -v
"""

import hashlib
import hmac
import json
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock

from app.main import app
from app.config.settings import settings


# Payload de ejemplo que Meta envía al webhook
SAMPLE_WEBHOOK_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "WABA_ID_123",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "5213312345678",
                            "phone_number_id": "PHONE_ID_123",
                        },
                        "messages": [
                            {
                                "from": "5213398765432",
                                "id": "wamid.test123",
                                "timestamp": "1700000000",
                                "text": {"body": "Hola, quiero una cita"},
                                "type": "text",
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


def make_meta_signature(body: bytes, secret: str) -> str:
    """Genera la firma que Meta enviaría en el header."""
    return "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()


@pytest.mark.asyncio
async def test_webhook_verification_success():
    """GET /webhook con token correcto debe devolver hub.challenge."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": settings.meta_verify_token,
                "hub.challenge": "123456",
            },
        )
    assert response.status_code == 200
    assert response.text == "123456"


@pytest.mark.asyncio
async def test_webhook_verification_wrong_token():
    """GET /webhook con token incorrecto debe devolver 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "token_incorrecto",
                "hub.challenge": "123456",
            },
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_post_echo(monkeypatch):
    """
    POST /webhook con mensaje de texto debe procesarlo y responder 200.
    Mockea route_incoming_message para no necesitar DB real.
    """
    # Saltamos validación de firma en test
    monkeypatch.setattr(
        "app.gateway.webhook.skip_signature_in_dev", lambda: True
    )

    mock_route = AsyncMock()
    monkeypatch.setattr(
        "app.gateway.webhook.route_incoming_message", mock_route
    )

    payload = json.dumps(SAMPLE_WEBHOOK_PAYLOAD).encode()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            content=payload,
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    mock_route.assert_called_once()

    # Verificar que se llamó con los parámetros correctos
    call_kwargs = mock_route.call_args.kwargs
    assert call_kwargs["phone_number_id"] == "PHONE_ID_123"
    assert call_kwargs["from_number"] == "5213398765432"
    assert call_kwargs["message_body"] == "Hola, quiero una cita"
    assert call_kwargs["wa_message_id"] == "wamid.test123"


@pytest.mark.asyncio
async def test_webhook_ignores_non_text_messages(monkeypatch):
    """Mensajes de tipo imagen/audio deben ser ignorados en Fase 1."""
    monkeypatch.setattr(
        "app.gateway.webhook.skip_signature_in_dev", lambda: True
    )
    mock_route = AsyncMock()
    monkeypatch.setattr(
        "app.gateway.webhook.route_incoming_message", mock_route
    )

    payload_image = {
        **SAMPLE_WEBHOOK_PAYLOAD,
        "entry": [
            {
                **SAMPLE_WEBHOOK_PAYLOAD["entry"][0],
                "changes": [
                    {
                        "value": {
                            **SAMPLE_WEBHOOK_PAYLOAD["entry"][0]["changes"][0]["value"],
                            "messages": [
                                {
                                    "from": "5213398765432",
                                    "id": "wamid.img123",
                                    "type": "image",  # <- tipo imagen
                                    "image": {"id": "img_id"},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/webhook",
            json=payload_image,
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 200
    mock_route.assert_not_called()  # No debe procesar mensajes de imagen


@pytest.mark.asyncio
async def test_health_check():
    """El endpoint /health siempre debe responder 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
