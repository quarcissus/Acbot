"""
ContactService — CRUD de contactos (clientes finales).
"""

import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.contact import Contact

logger = logging.getLogger(__name__)


async def get_or_create_contact(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    phone_number: str,
    name: str = "Sin nombre",
) -> tuple[Contact, bool]:
    """
    Busca un contacto existente o crea uno nuevo.
    Returns: (contact, created) — created=True si se acaba de crear.
    """
    result = await db.execute(
        select(Contact).where(
            and_(
                Contact.tenant_id == tenant_id,
                Contact.phone_number == phone_number,
            )
        )
    )
    contact = result.scalar_one_or_none()

    if contact:
        return contact, False

    contact = Contact(tenant_id=tenant_id, phone_number=phone_number, name=name)
    db.add(contact)
    await db.flush()
    logger.info(f"Contacto creado: {phone_number} para tenant {tenant_id}")
    return contact, True


async def get_contact_by_id(
    db: AsyncSession,
    contact_id: uuid.UUID,
) -> Contact | None:
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    return result.scalar_one_or_none()


async def get_contact_by_phone(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    phone_number: str,
) -> Contact | None:
    result = await db.execute(
        select(Contact).where(
            and_(
                Contact.tenant_id == tenant_id,
                Contact.phone_number == phone_number,
            )
        )
    )
    return result.scalar_one_or_none()


async def update_contact_name(
    db: AsyncSession,
    contact: Contact,
    name: str,
) -> Contact:
    """Actualiza el nombre de un contacto si aún no tiene uno real."""
    if name and name.strip() and contact.name in ("Sin nombre", "", None):
        contact.name = name.strip().title()
        await db.flush()
        logger.info(f"Nombre guardado para contacto {contact.id}: {contact.name}")
    return contact


async def set_bot_enabled(
    db: AsyncSession,
    contact: Contact,
    enabled: bool,
) -> Contact:
    """Activa o desactiva el bot para un contacto específico (handoff)."""
    contact.bot_enabled = enabled
    await db.flush()
    logger.info(f"bot_enabled={enabled} para contacto {contact.id} ({contact.phone_number})")
    return contact


async def list_contacts(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[Contact]:
    result = await db.execute(
        select(Contact)
        .where(Contact.tenant_id == tenant_id)
        .order_by(Contact.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())