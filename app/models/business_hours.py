"""
Modelo BusinessHours — horario de atención por día de la semana de un tenant.
Cada tenant tiene hasta 7 registros (uno por día).
"""

import uuid
from sqlalchemy import String, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

WEEKDAY_NAMES = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


class BusinessHours(Base):
    __tablename__ = "business_hours"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Lunes, 6=Domingo
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    open_time: Mapped[str] = mapped_column(String(5), default="08:00")   # "HH:MM"
    close_time: Mapped[str] = mapped_column(String(5), default="20:00")  # "HH:MM"

    # Relación
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="business_hours")  # noqa: F821

    @property
    def weekday_name(self) -> str:
        return WEEKDAY_NAMES.get(self.weekday, f"Día {self.weekday}")

    def __repr__(self) -> str:
        status = f"{self.open_time}-{self.close_time}" if self.is_open else "cerrado"
        return f"<BusinessHours {self.weekday_name}: {status}>"