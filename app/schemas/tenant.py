"""
Schemas Pydantic para Tenant.
Separa lo que entra (Create/Update) de lo que sale (Response).
"""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    business_type: str = Field(..., pattern=r"^(barberia|doctor|academia)$")
    phone_number: str = Field(..., min_length=10, max_length=20)
    whatsapp_phone_id: str
    whatsapp_waba_id: str
    timezone: str = "America/Mexico_City"
    bot_system_prompt: str | None = None
    bot_welcome_message: str | None = None
    bot_enabled: bool = True
    reminder_hours_before: int = Field(default=24, ge=1, le=72)


class TenantUpdate(BaseModel):
    name: str | None = None
    bot_system_prompt: str | None = None
    bot_welcome_message: str | None = None
    bot_enabled: bool | None = None
    reminder_hours_before: int | None = None


class TenantResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    slug: str
    business_type: str
    phone_number: str
    whatsapp_phone_id: str
    timezone: str
    bot_enabled: bool
    reminder_hours_before: int
    created_at: datetime
    updated_at: datetime
