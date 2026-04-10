"""
Router del Gateway — orquesta el flujo completo de un mensaje entrante.

Responsabilidades:
1. Identificar el tenant por phone_number_id
2. Buscar/crear el contacto
3. Buscar/crear la conversación activa
4. Persistir el mensaje entrante
5. Enrutar al handler correcto según business_type
6. Enviar la respuesta

En Fase 1: responde con "Echo: {mensaje}" sin IA.
En Fase 2: se conecta con los handlers reales.
"""

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.tenant import Tenant
from app.models.contact import Contact
from app.models.conversation import Conversation, Message
from app.gateway.sender import send_text_message, mark_as_read

logger = logging.getLogger(__name__)


async def route_incoming_message(
    db: AsyncSession,
    phone_number_id: str,
    from_number: str,
    message_body: str,
    wa_message_id: str,
) -> None:
    """
    Punto de entrada principal para cada mensaje de WhatsApp entrante.

    Args:
        db: Sesión de base de datos.
        phone_number_id: ID del número de WhatsApp que recibió el mensaje (identifica al tenant).
        from_number: Número del cliente final que escribió.
        message_body: Texto del mensaje.
        wa_message_id: ID del mensaje en WhatsApp (para deduplicación y read receipts).
    """
    # 1. Buscar tenant por phone_number_id
    tenant = await _get_tenant_by_phone_id(db, phone_number_id)
    if not tenant:
        logger.warning(f"No se encontró tenant para phone_number_id={phone_number_id}")
        return

    if not tenant.bot_enabled:
        logger.info(f"Bot deshabilitado para tenant {tenant.slug}")
        return

    # 2. Buscar o crear contacto
    contact = await _get_or_create_contact(db, tenant.id, from_number)

    # 3. Buscar o crear conversación activa
    conversation = await _get_or_create_conversation(db, tenant.id, contact.id)

    # 4. Verificar si el mensaje ya fue procesado (deduplicación)
    if await _message_already_processed(db, wa_message_id):
        logger.info(f"Mensaje {wa_message_id} ya procesado, ignorando")
        return

    # 5. Guardar mensaje entrante
    incoming_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=message_body,
        message_type="text",
        wa_message_id=wa_message_id,
    )
    db.add(incoming_msg)

    # Actualizar last_message_at de la conversación
    conversation.last_message_at = datetime.now(timezone.utc)

    await db.flush()  # Persiste sin commitear (el commit lo hace el middleware de FastAPI)

    # 6. Marcar como leído (palomitas azules)
    await mark_as_read(phone_number_id, wa_message_id)

    # 7. Generar respuesta
    # FASE 1: Echo simple. En Fase 2 esto llamará al handler correspondiente.
    response_text = await _generate_response(tenant, contact, conversation, message_body, db)

    # 8. Guardar respuesta del bot
    outgoing_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        message_type="text",
    )
    db.add(outgoing_msg)
    await db.flush()

    # 9. Enviar respuesta via Meta Cloud API
    await send_text_message(
        phone_number_id=phone_number_id,
        to=from_number,
        body=response_text,
    )

    logger.info(
        f"Mensaje procesado para tenant={tenant.slug}, "
        f"contact={from_number}, "
        f"wa_id={wa_message_id}"
    )


async def _get_tenant_by_phone_id(
    db: AsyncSession, phone_number_id: str
) -> Tenant | None:
    """Busca un tenant por su whatsapp_phone_id."""
    result = await db.execute(
        select(Tenant).where(Tenant.whatsapp_phone_id == phone_number_id)
    )
    return result.scalar_one_or_none()


async def _get_or_create_contact(
    db: AsyncSession, tenant_id, phone_number: str
) -> Contact:
    """Busca un contacto existente o crea uno nuevo."""
    result = await db.execute(
        select(Contact).where(
            and_(
                Contact.tenant_id == tenant_id,
                Contact.phone_number == phone_number,
            )
        )
    )
    contact = result.scalar_one_or_none()

    if not contact:
        contact = Contact(tenant_id=tenant_id, phone_number=phone_number)
        db.add(contact)
        await db.flush()
        logger.info(f"Nuevo contacto creado: {phone_number} para tenant {tenant_id}")

    return contact


CONVERSATION_TIMEOUT_HOURS = 4  # Horas de inactividad para cerrar conversación


async def _get_or_create_conversation(
    db: AsyncSession, tenant_id, contact_id
) -> Conversation:
    """
    Busca una conversación activa o crea una nueva.

    Si la conversación activa tiene más de CONVERSATION_TIMEOUT_HOURS horas
    sin actividad, se cierra y se abre una nueva — así el cliente siempre
    empieza con contexto limpio después de una pausa larga.
    """
    result = await db.execute(
        select(Conversation).where(
            and_(
                Conversation.tenant_id == tenant_id,
                Conversation.contact_id == contact_id,
                Conversation.status == "active",
            )
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        # Verificar si la conversación expiró por inactividad
        last_activity = conversation.last_message_at or conversation.created_at
        # Asegurar que last_activity tenga timezone para comparar
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        inactivity = datetime.now(timezone.utc) - last_activity

        if inactivity > timedelta(hours=CONVERSATION_TIMEOUT_HOURS):
            logger.info(
                f"Conversación {conversation.id} expirada tras "
                f"{inactivity.total_seconds()/3600:.1f}h de inactividad — cerrando"
            )
            conversation.status = "closed"
            await db.flush()
            conversation = None  # Forzar creación de nueva conversación

    if not conversation:
        conversation = Conversation(
            tenant_id=tenant_id,
            contact_id=contact_id,
            status="active",
        )
        db.add(conversation)
        await db.flush()
        logger.info(f"Nueva conversación creada para contact_id={contact_id}")

    return conversation


async def _message_already_processed(db: AsyncSession, wa_message_id: str) -> bool:
    """Verifica si un mensaje ya fue procesado (evita duplicados de Meta)."""
    result = await db.execute(
        select(Message.id).where(Message.wa_message_id == wa_message_id)
    )
    return result.scalar_one_or_none() is not None


async def _generate_response(
    tenant: Tenant,
    contact: Contact,
    conversation: Conversation,
    message_body: str,
    db: AsyncSession,
) -> str:
    """
    FASE 2: Llama al handler correcto según el business_type del tenant.
    """
    from app.handlers import get_handler
    handler = get_handler(tenant.business_type)
    return await handler.handle_message(tenant, contact, conversation, message_body, db)