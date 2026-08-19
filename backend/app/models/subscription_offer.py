"""عروضُ اشتراكات الكباتن (`design/SUBSCRIPTION-OFFERS.md`، البند ٥٤).

**والخصمُ مالٌ لا وقت** (قرارُ المالك 2026-08-19، الفرع أ): النسبةُ لغةُ البطاقة،
والخصمُ الزمنيُّ يمسّ تاريخَ الانتهاء والتجديدَ والاسترداد — وهي مساراتٌ تعمل.

**ولا يُعاد استعمالُ `promo_codes`**: تلك قناةُ دفعِ **رحلة** تتحمّلها الشركةُ عن
الراكب فتُقاس بجمع صفوف `promo`؛ وهذا **إيرادٌ لم يُقبض** — لا رحلةَ ولا صفَّ
دفعات. والأولُ مصروفٌ والثاني تنازل، ولا يُجمعان في تقريرٍ واحد.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

# **نوعُ الخصم نصٌّ لا تعدادُ Postgres** (شرطُ المالك): إضافةُ نوعٍ زمنيٍّ أو
# خصمٍ بمبلغٍ ثابت تصير **كوداً بلا ترحيلة**، وهو استثناءُ
# `feature_flags.feature_key` نفسُه ولنفس سببه. والقيمُ يحرسها مخطط Pydantic.
DISCOUNT_MONEY_PERCENT = "money_percent"
DISCOUNT_TYPES = (DISCOUNT_MONEY_PERCENT,)

# جمهورُ العرض — **ثلاثةٌ منها مقارنةٌ حيّةٌ لحظةَ الشراء** لا عمودٌ يُختم
# (درسُ `qualified_at`): خفضُ `lapsed_days` يشمل من كان ينتظره بلا لمس صفّ.
AUDIENCE_ALL = "all"
AUDIENCE_NEW_DRIVER = "new_driver"
AUDIENCE_LAPSED = "lapsed"
AUDIENCE_MANUAL = "manual"
AUDIENCES = (AUDIENCE_ALL, AUDIENCE_NEW_DRIVER, AUDIENCE_LAPSED, AUDIENCE_MANUAL)


class SubscriptionOffer(UUIDMixin, TimestampMixin, Base):
    """عرضٌ يخصم من سعر خطةٍ (أو كلِّ الخطط) في دولةٍ واحدة."""

    __tablename__ = "subscription_offers"
    __table_args__ = (
        UniqueConstraint("country_code", "name", name="uq_subscription_offers_name"),
        # نسبةٌ بين صفرٍ ومئة — والحدُّ في القاعدة لا في الخدمة وحدَها: قيمةٌ
        # فوق المئة تجعل `amount_paid` سالباً، وهو مالٌ من عدم
        CheckConstraint(
            "discount_value > 0 AND discount_value <= 100",
            name="subscription_offer_percent_range",
        ),
        CheckConstraint(
            "max_uses_per_driver >= 0", name="subscription_offer_uses_non_negative"
        ),
        CheckConstraint(
            "lapsed_days IS NULL OR lapsed_days > 0",
            name="subscription_offer_lapsed_days_positive",
        ),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="subscription_offer_window_positive",
        ),
        Index("ix_subscription_offers_country_active", "country_code", "is_active"),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    discount_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DISCOUNT_MONEY_PERCENT
    )
    discount_value: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # سقفُ النسبة بالمال — كـ`promo_codes.max_discount`. و`NULL` = بلا سقف
    max_discount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    # خطةٌ بعينها، و`NULL` = كلُّ خطط الدولة
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    audience: Mapped[str] = mapped_column(
        String(24), nullable=False, default=AUDIENCE_ALL
    )
    # لجمهور `lapsed` وحدَه: انقطعت تغطيتُه منذ كذا يوماً
    lapsed_days: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # **حدٌّ لكل عرضٍ لا لكل شهر** (الفرع ب): العدُّ صفوفُ الاشتراكات الحاملةُ
    # `offer_id` لهذا الكبتن — فالعرضُ نفسُه هو النافذة، بلا حسابِ شهرٍ تقويميٍّ
    # وبلا حدٍّ يقع على حافّته. و«عرضٌ شهريٌّ متكرر» صفُّ عرضٍ جديدٌ كلَّ شهر.
    # وصفرٌ = بلا حدّ، **مكتوبٌ صراحةً** كأصفار `wallet_settings`.
    max_uses_per_driver: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1
    )
    # سقفُ التنازل الكلّي — و`NULL` = بلا سقف
    total_budget: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<SubscriptionOffer {self.country_code}/{self.name}>"


class SubscriptionOfferGrant(UUIDMixin, TimestampMixin, Base):
    """منحُ عرضٍ لكبتنٍ بعينه — **لجمهور `manual` وحدَه**، وبسببٍ مكتوب."""

    __tablename__ = "subscription_offer_grants"
    __table_args__ = (
        UniqueConstraint(
            "offer_id", "driver_id", name="uq_subscription_offer_grant_driver"
        ),
    )

    offer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("subscription_offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    offer: Mapped["SubscriptionOffer"] = relationship("SubscriptionOffer")
