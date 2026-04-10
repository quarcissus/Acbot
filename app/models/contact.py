"""
Modelo Contact — cliente final del negocio (el que escribe al WhatsApp).
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone_number", name="uq_contact_tenant_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), default="Sin nombre")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    bot_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # False = handoff activo

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relaciones
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="contacts")  # noqa: F821
    conversations: Mapped[list["Conversation"]] = relationship(  # noqa: F821
        "Conversation", back_populates="contact", lazy="noload"
    )
    appointments: Mapped[list["Appointment"]] = relationship(  # noqa: F821
        "Appointment", back_populates="contact", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Contact {self.phone_number} (tenant: {self.tenant_id})>"