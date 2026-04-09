"""Schemas Pydantic para Appointment."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    contact_id: uuid.UUID
    title: str = Field(..., min_length=2, max_length=200)
    description: str | None = None
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=480)
    notes: str | None = None
    source: str = "manual"


class AppointmentUpdate(BaseModel):
    title: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = None
    status: str | None = None
    notes: str | None = None


class AppointmentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    tenant_id: uuid.UUID
    contact_id: uuid.UUID
    title: str
    description: str | None
    scheduled_at: datetime
    duration_minutes: int
    status: str
    reminder_sent: bool
    source: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
