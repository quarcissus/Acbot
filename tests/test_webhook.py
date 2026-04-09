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


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_meta_signature(body: bytes, secret: str = "test_secret") -> str:
    """Genera la firma HMAC-SHA256 como lo haría Meta."""
    return "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()


def make_whatsapp_payload(
    phone_number_id: str = "123456",
    from_number: str = "5213312345678",
    message_body: str = "Hola",
    message_id: str = "wamid.test123",
) -> dict:
    """Construye un payload de webhook de Meta."""
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": phone_number_id},
                    "messages": [{
                        "from": from_number,
                        "id": message_id,
                        "type": "text",
                        "text": {"body": message_body},
                    }],
                },
            }],
        }],
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_verification_success():
    """GET /webhook con token correcto devuelve el challenge."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "my_challenge_123",
                "hub.verify_token": settings.meta_verify_token,
            },
        )
    assert response.status_code == 200
    assert response.text == "my_challenge_123"


@pytest.mark.asyncio
async def test_webhook_verification_wrong_token():
    """GET /webhook con token incorrecto devuelve 403."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "my_challenge",
                "hub.verify_token": "token_incorrecto",
            },
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_webhook_post_echo(monkeypatch):
    """
    POST /webhook con un mensaje de texto devuelve 200 y procesa el mensaje.
    Mockea la DB y el sender para no necesitar infraestructura real.
    """
    payload = make_whatsapp_payload(message_body="Hola bot")
    body = json.dumps(payload).encode()

    # En dev sin secret, la firma se salta automáticamente
    monkeypatch.setattr(settings, "meta_app_secret", "")
    monkeypatch.setattr(settings, "environment", "development")

    with patch("app.gateway.router.route_incoming_message", new_callable=AsyncMock) as mock_route:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/webhook",
                content=body,
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_route.assert_called_once()

    # Verificar que se pasaron los datos correctos
    call_kwargs = mock_route.call_args.kwargs
    assert call_kwargs["phone_number_id"] == "123456"
    assert call_kwargs["from_number"] == "5213312345678"
    assert call_kwargs["message_body"] == "Hola bot"


@pytest.mark.asyncio
async def test_webhook_ignores_non_message_events():
    """POST /webhook con eventos que no son mensajes devuelve 200 sin procesar."""
    payload = {"object": "whatsapp_business_account", "entry": []}
    body = json.dumps(payload).encode()

    with patch("app.gateway.router.route_incoming_message", new_callable=AsyncMock) as mock_route:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/webhook",
                content=body,
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == 200
    mock_route.assert_not_called()


@pytest.mark.asyncio
async def test_health_endpoint():
    """GET /health devuelve estado de la aplicación."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
