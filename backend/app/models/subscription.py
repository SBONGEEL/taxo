from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, Currency, SubscriptionDurationType


class SubscriptionPlan(UUIDMixin, TimestampMixin, Base):
    """خطة اشتراك الكبتن (يومي/أسبوعي/شهري) لكل دولة.

    الاشتراك الفعلي للكبتن (`driver_subscriptions`) من المرحلة 7.
    """

    __tablename__ = "subscription_plans"
    __table_args__ = (
        UniqueConstraint("country_code", "name"),
        CheckConstraint("price >= 0", name="subscription_price_non_negative"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_type: Mapped[SubscriptionDurationType] = mapped_column(
        pg_enum(SubscriptionDurationType, "subscription_duration_type"), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<SubscriptionPlan {self.country_code}/{self.name}>"
