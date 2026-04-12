"""
Modelo StaffHours — horario de trabajo específico por barbero/empleado.
Debe respetar siempre el BusinessHours del tenant.
"""

import uuid
from sqlalchemy import String, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

WEEKDAY_NAMES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}


class StaffHours(Base):
    __tablename__ = "staff_hours"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staff.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Lunes, 6=Domingo
    is_working: Mapped[bool] = mapped_column(Boolean, default=True)
    start_time: Mapped[str] = mapped_column(String(5), default="08:00")  # "HH:MM"
    end_time: Mapped[str] = mapped_column(String(5), default="20:00")    # "HH:MM"

    # Relaciones
    staff: Mapped["Staff"] = relationship("Staff", back_populates="staff_hours")  # noqa: F821

    @property
    def weekday_name(self) -> str:
        return WEEKDAY_NAMES.get(self.weekday, f"Día {self.weekday}")

    def __repr__(self) -> str:
        status = f"{self.start_time}-{self.end_time}" if self.is_working else "no trabaja"
        return f"<StaffHours {self.weekday_name}: {status}>"