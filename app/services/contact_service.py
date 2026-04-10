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

    Returns:
        (contact, created) — created=True si se acaba de crear.
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

    contact = Contact(
        tenant_id=tenant_id,
        phone_number=phone_number,
        name=name,
    )
    db.add(contact)
    await db.flush()
    logger.info(f"Contacto creado: {phone_number} para tenant {tenant_id}")
    return contact, True


async def get_contact_by_id(
    db: AsyncSession,
    contact_id: uuid.UUID,
) -> Contact | None:
    """Busca un contacto por ID."""
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    return result.scalar_one_or_none()


async def get_contact_by_phone(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    phone_number: str,
) -> Contact | None:
    """Busca un contacto por número de teléfono dentro de un tenant."""
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
    contact_id: uuid.UUID,
    name: str,
) -> Contact | None:
    """Actualiza el nombre de un contacto."""
    contact = await get_contact_by_id(db, contact_id)
    if not contact:
        return None
    contact.name = name
    await db.flush()
    logger.info(f"Nombre actualizado para contacto {contact_id}: {name}")
    return contact


async def update_contact_notes(
    db: AsyncSession,
    contact_id: uuid.UUID,
    notes: str,
) -> Contact | None:
    """Actualiza las notas de un contacto."""
    contact = await get_contact_by_id(db, contact_id)
    if not contact:
        return None
    contact.notes = notes
    await db.flush()
    return contact


async def list_contacts(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> list[Contact]:
    """Lista todos los contactos de un tenant con paginación."""
    result = await db.execute(
        select(Contact)
        .where(Contact.tenant_id == tenant_id)
        .order_by(Contact.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())