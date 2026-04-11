"""
Bot API — activar y desactivar el bot de un tenant.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.models.tenant import Tenant
from app.api.deps import get_current_admin, get_tenant_by_slug
from app.models.admin_user import AdminUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tenants/{slug}/bot", tags=["bot"])


class BotStatusOut(BaseModel):
    slug: str
    bot_enabled: bool
    bot_welcome_message: str | None


class BotUpdate(BaseModel):
    bot_enabled: bool | None = None
    bot_welcome_message: str | None = None


@router.get("", response_model=BotStatusOut)
async def get_bot_status(
    slug: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> BotStatusOut:
    """Retorna el estado actual del bot para un tenant."""
    return BotStatusOut(
        slug=tenant.slug,
        bot_enabled=tenant.bot_enabled,
        bot_welcome_message=tenant.bot_welcome_message,
    )


@router.patch("", response_model=BotStatusOut)
async def update_bot(
    slug: str,
    body: BotUpdate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_tenant_by_slug),
    _: AdminUser = Depends(get_current_admin),
) -> BotStatusOut:
    """Activa/desactiva el bot o actualiza el mensaje de bienvenida."""
    if body.bot_enabled is not None:
        tenant.bot_enabled = body.bot_enabled
        logger.info(f"Bot {'activado' if body.bot_enabled else 'desactivado'} para tenant {slug}")

    if body.bot_welcome_message is not None:
        tenant.bot_welcome_message = body.bot_welcome_message

    await db.flush()

    return BotStatusOut(
        slug=tenant.slug,
        bot_enabled=tenant.bot_enabled,
        bot_welcome_message=tenant.bot_welcome_message,
    )