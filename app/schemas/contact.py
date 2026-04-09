"""Schemas Pydantic para Contact."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ContactCreate(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=20)
    name: str = "Sin nombre"
    notes: str | None = None


class ContactUpdate(BaseModel):
    name: str | None = None
    notes: str | None = None


class ContactResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    tenant_id: uuid.UUID
    phone_number: str
    name: str
    notes: str | None
    created_at: datetime
