"""
Tests unitarios para el router de mensajes.

Prueba la lógica de:
- Encontrar tenant por phone_number_id
- Crear/encontrar contactos
- Crear/encontrar conversaciones
- Deduplicación de mensajes
- Generación de respuesta echo
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.gateway.router import (
    _generate_echo_response,
    _get_or_create_contact,
    _get_or_create_conversation,
    _message_exists,
)
from app.models.tenant import Tenant
from app.models.contact import Contact
from app.models.conversation import Conversation, Message


# ── Tests de echo response ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_echo_response_format():
    """La respuesta echo incluye el nombre del tenant y el mensaje original."""
    tenant = MagicMock(spec=Tenant)
    tenant.name = "Barbería Don Pepe"

    response = await _generate_echo_response(tenant, "Hola, ¿cómo están?")

    assert "Barbería Don Pepe" in response
    assert "Hola, ¿cómo están?" in response


@pytest.mark.asyncio
async def test_echo_response_different_tenants():
    """Cada tenant tiene su propia respuesta echo."""
    tenant1 = MagicMock(spec=Tenant)
    tenant1.name = "Barbería Alpha"

    tenant2 = MagicMock(spec=Tenant)
    tenant2.name = "Consultorio Beta"

    msg = "Test"
    r1 = await _generate_echo_response(tenant1, msg)
    r2 = await _generate_echo_response(tenant2, msg)

    assert "Alpha" in r1
    assert "Beta" in r2
    assert r1 != r2


# ── Tests de normalización de números ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_contact_phone_normalized_with_plus():
    """El número del contacto se guarda siempre con '+' al inicio."""
    db = AsyncMock()

    # Simular que no existe el contacto
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    db.add = MagicMock()
    db.flush = AsyncMock()

    contact = await _get_or_create_contact(db, uuid.uuid4(), "5213398765432")

    # Verificar que se creó con el '+' prefijado
    db.add.assert_called_once()
    created_contact = db.add.call_args[0][0]
    assert created_contact.phone_number.startswith("+")


@pytest.mark.asyncio
async def test_contact_phone_already_has_plus():
    """Si el número ya tiene '+', no se duplica."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    db.add = MagicMock()
    db.flush = AsyncMock()

    await _get_or_create_contact(db, uuid.uuid4(), "+5213398765432")

    created_contact = db.add.call_args[0][0]
    assert created_contact.phone_number == "+5213398765432"
    assert not created_contact.phone_number.startswith("++")


# ── Tests de deduplicación ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_message_exists_true():
    """Devuelve True si el wa_message_id ya existe en la DB."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = uuid.uuid4()  # Existe
    db.execute = AsyncMock(return_value=mock_result)

    result = await _message_exists(db, "wamid.existing123")
    assert result is True


@pytest.mark.asyncio
async def test_message_exists_false():
    """Devuelve False si el wa_message_id no existe en la DB."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # No existe
    db.execute = AsyncMock(return_value=mock_result)

    result = await _message_exists(db, "wamid.new123")
    assert result is False


@pytest.mark.asyncio
async def test_message_exists_empty_id():
    """Con wa_message_id vacío, devuelve False sin consultar la DB."""
    db = AsyncMock()

    result = await _message_exists(db, "")
    assert result is False
    db.execute.assert_not_called()
