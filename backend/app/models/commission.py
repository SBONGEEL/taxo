from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CommissionAppliesTo, CountryCode


class CommissionSetting(UUIDMixin, TimestampMixin, Base):
    """إعداد العمولة لكل دولة — معطّلة افتراضياً (SPEC القسم 8).

    تفعيلها لا يمس الرحلات القائمة: كل رحلة تحمل
    `commission_percent_at_ride` مجمّدة لحظة إنشائها (المرحلة 3).
    """

    __tablename__ = "commission_settings"
    __table_args__ = (
        CheckConstraint(
            "commission_percent >= 0 AND commission_percent <= 100",
            name="commission_percent_range",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, unique=True, index=True
    )
    commission_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    commission_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0")
    )
    applies_to: Mapped[CommissionAppliesTo] = mapped_column(
        pg_enum(CommissionAppliesTo, "commission_applies_to"),
        nullable=False,
        default=CommissionAppliesTo.ALL_RIDES,
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<CommissionSetting {self.country_code} {self.commission_percent}%>"
