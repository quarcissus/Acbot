"""
Modelo Tenant — representa un negocio cliente (barbería, doctor, academia, etc.)
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    business_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "barberia" | "doctor" | "academia"

    # Credenciales de WhatsApp (específicas por tenant)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    whatsapp_phone_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    whatsapp_waba_id: Mapped[str] = mapped_column(String(50), nullable=False)

    # Configuración del bot
    timezone: Mapped[str] = mapped_column(String(50), default="America/Mexico_City")
    bot_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder_hours_before: Mapped[int] = mapped_column(Integer, default=24)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relaciones (se usan en fases posteriores)
    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        "Contact", back_populates="tenant", lazy="noload"
    )
    appointments: Mapped[list["Appointment"]] = relationship(  # noqa: F821
        "Appointment", back_populates="tenant", lazy="noload"
    )
    business_hours: Mapped[list["BusinessHours"]] = relationship(  # noqa: F821
        "BusinessHours", back_populates="tenant", lazy="noload",
        order_by="BusinessHours.weekday"
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.slug} ({self.business_type})>"