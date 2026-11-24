"""**عروضُ الركاب** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، الجزء د؛ SPEC §١١٤-د) — الترحيلة `0190`.

* **«ادعُ صديقك»** (`rider_offer_entitlements`): استحقاقُ خصمِ رحلةٍ واحدةٍ للصديق المدعوّ وللداعي — **يُستهلك برحلةٍ واحدة**.
* **قسائمُ المتاجر الشريكة** (`partner_coupons`): خصمٌ على بضائع المتجر نفسِه **لا على TAXO** — نصٌّ يُعرض لا مالٌ يتحرّك.
* **مزايا غيرُ نقديّة** (`rider_perks`): إلغاءٌ مجّانيٌّ خلال ثوانٍ يضعها المالك، وشارةُ «راكب مميز» بعد عددِ رحلاتٍ يضعه. **فارغةٌ = مطفأة.**
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

ENTITLEMENT_FRIEND = "invite_friend"
ENTITLEMENT_INVITER = "invite_inviter"


class RiderOfferEntitlement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rider_offer_entitlements"
    __table_args__ = (
        UniqueConstraint("rider_id", "promo_code_id", "source", name="uq_rider_offer_entitlement"),
        CheckConstraint("source IN ('invite_friend', 'invite_inviter')", name="rider_offer_entitlement_source"),
    )

    rider_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    promo_code_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("promo_codes.id", ondelete="RESTRICT"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    referral_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    used_ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("rides.id", ondelete="RESTRICT"), nullable=True, unique=True
    )


class PartnerCoupon(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "partner_coupons"

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False, index=True)
    shop_name: Mapped[str] = mapped_column(String(120), nullable=False)
    shop_area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class RiderPerks(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rider_perks"
    __table_args__ = (
        UniqueConstraint("country_code", name="uq_rider_perks_country"),
        CheckConstraint(
            "(free_cancel_seconds IS NULL OR free_cancel_seconds BETWEEN 30 AND 900) "
            "AND (premium_after_rides IS NULL OR premium_after_rides BETWEEN 1 AND 1000)",
            name="rider_perks_values",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(pg_enum(CountryCode, "country_code"), nullable=False)
    #: **إلغاءٌ مجّانيٌّ خلال هذه الثواني من قبول الكبتن** — فارغٌ = مطفأ
    free_cancel_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: **«راكب مميز» بعد هذا العدد من الرحلات المكتملة** — فارغٌ = مطفأ
    premium_after_rides: Mapped[int | None] = mapped_column(Integer, nullable=True)
    premium_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
