"""Schemas Pydantic para Conversation y Message."""

import uuid
from datetime import datetime
from pydantic import BaseModel


class MessageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    message_type: str
    wa_message_id: str | None
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    tenant_id: uuid.UUID
    contact_id: uuid.UUID
    status: str
    created_at: datetime
    last_message_at: datetime
