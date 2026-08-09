from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import VehicleCategory

if TYPE_CHECKING:
    from app.models.driver import Driver


class Vehicle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("year >= 1990 AND year <= 2100", name="vehicle_year_range"),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    make: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(40), nullable=False)
    plate_number: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    category: Mapped[VehicleCategory] = mapped_column(
        pg_enum(VehicleCategory, "vehicle_category"),
        nullable=False,
        default=VehicleCategory.ECONOMY,
    )

    driver: Mapped["Driver"] = relationship(back_populates="vehicles")
