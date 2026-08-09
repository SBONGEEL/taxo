from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, VehicleCategory


class PricingRule(UUIDMixin, TimestampMixin, Base):
    """تسعيرة فئة مركبة في دولة.

    التسعير كله يُحسب في الخلفية من هذه القيم (SPEC القسم 5) — الواجهة تعرض فقط.
    """

    __tablename__ = "pricing_rules"
    __table_args__ = (
        UniqueConstraint("country_code", "vehicle_category"),
        CheckConstraint(
            "base_fare >= 0 AND price_per_km >= 0 AND price_per_min >= 0 "
            "AND minimum_fare >= 0 AND cancellation_fee >= 0",
            name="pricing_amounts_non_negative",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    vehicle_category: Mapped[VehicleCategory] = mapped_column(
        pg_enum(VehicleCategory, "vehicle_category"), nullable=False
    )

    base_fare: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    price_per_km: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    price_per_min: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    minimum_fare: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    cancellation_fee: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<PricingRule {self.country_code}/{self.vehicle_category}>"
