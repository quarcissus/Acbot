"""
Router del Gateway — orquesta el flujo completo de un mensaje entrante.
"""

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.gateway.sender import send_text_message, mark_as_read

logger = logging.getLogger(__name__)

CONVERSATION_TIMEOUT_HOURS = 4


async def route_incoming_message(
    db: AsyncSession,
    phone_number_id: str,
    from_number: str,
    message_body: str,
    wa_message_id: str,
) -> None:
    from app.models.tenant import Tenant
    from app.models.contact import Contact
    from app.models.conversation import Conversation, Message

    tenant = await _get_tenant_by_phone_id(db, phone_number_id)
    if not tenant:
        logger.warning(f"No se encontró tenant para phone_number_id={phone_number_id}")
        return

    if not tenant.bot_enabled:
        logger.info(f"Bot deshabilitado para tenant {tenant.slug}")
        return

    contact = await _get_or_create_contact(db, tenant.id, from_number)

    if not contact.bot_enabled:
        logger.info(f"Handoff activo para contacto {contact.phone_number} — bot silenciado")
        await mark_as_read(phone_number_id, wa_message_id)
        return

    is_new_contact = contact.name == "Sin nombre" and not await _contact_has_history(db, contact.id)

    conversation = await _get_or_create_conversation(db, tenant.id, contact.id)

    if await _message_already_processed(db, wa_message_id):
        logger.info(f"Mensaje {wa_message_id} ya procesado, ignorando")
        return

    incoming_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=message_body,
        message_type="text",
        wa_message_id=wa_message_id,
    )
    db.add(incoming_msg)
    conversation.last_message_at = datetime.now(timezone.utc)
    await db.flush()

    await mark_as_read(phone_number_id, wa_message_id)

    if is_new_contact and tenant.bot_welcome_message:
        welcome = tenant.bot_welcome_message
        await send_text_message(phone_number_id=phone_number_id, to=from_number, body=welcome)
        welcome_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=welcome,
            message_type="text",
        )
        db.add(welcome_msg)
        await db.flush()

    response_text = await _generate_response(tenant, contact, conversation, message_body, db)

    outgoing_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_text,
        message_type="text",
    )
    db.add(outgoing_msg)
    await db.flush()

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


async def _get_tenant_by_phone_id(db: AsyncSession, phone_number_id: str):
    from app.models.tenant import Tenant
    result = await db.execute(
        select(Tenant).where(Tenant.whatsapp_phone_id == phone_number_id)
    )
    return result.scalar_one_or_none()


async def _get_or_create_contact(db: AsyncSession, tenant_id, phone_number: str):
    from app.models.contact import Contact
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


async def _get_or_create_conversation(db: AsyncSession, tenant_id, contact_id):
    from app.models.conversation import Conversation
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
        last_activity = conversation.last_message_at or conversation.created_at
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
            conversation = None

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
    from app.models.conversation import Message
    result = await db.execute(
        select(Message.id).where(Message.wa_message_id == wa_message_id)
    )
    return result.scalar_one_or_none() is not None


async def _generate_response(tenant, contact, conversation, message_body: str, db: AsyncSession) -> str:
    from app.handlers import get_handler
    handler = get_handler(tenant.business_type)
    return await handler.handle_message(tenant, contact, conversation, message_body, db)


async def _contact_has_history(db: AsyncSession, contact_id) -> bool:
    from app.models.conversation import Conversation
    result = await db.execute(
        select(Conversation.id).where(Conversation.contact_id == contact_id).limit(1)
    )
    return result.scalar_one_or_none() is not None