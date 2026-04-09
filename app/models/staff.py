"""
Modelo Staff — empleados/barberos de un negocio.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, func, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="barbero")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    appointment_duration: Mapped[int] = mapped_column(Integer, default=30)  # minutos por cita

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relaciones
    appointments: Mapped[list["Appointment"]] = relationship(  # noqa: F821
        "Appointment", back_populates="staff", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Staff {self.name} (tenant: {self.tenant_id})>"