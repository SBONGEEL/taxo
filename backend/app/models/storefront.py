"""بلاطاتُ الخدمات ولافتاتُ المحتوى — الترحيلة `0063`.

**جدولان لا جدولٌ بنوعٍ مصرَّح** (قرارُ المالك 2026-08-30): البلاطةُ **دائمةٌ
بلا نافذة**، واللافتةُ **مؤقّتةٌ بنافذةٍ إلزاميّة** — **وعمودٌ إلزاميٌّ لصنفٍ
واختياريٌّ لآخر يُقرأ «إلزاميٌّ أحياناً» ولا يحرسه شيء**.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    BannerLinkKind,
    CampaignAudience,
    CountryCode,
    ServiceTileStatus,
)


class ServiceTile(UUIDMixin, TimestampMixin, Base):
    """بلاطةُ خدمةٍ في الشاشة الرئيسة — للراكب أو الكبتن أو لهما."""

    __tablename__ = "service_tiles"

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    #: **مفتاحٌ ثابتٌ يعرفه التطبيق** — والعنوانُ يتغيّر ولا يتغيّر هو
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(60), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(80), nullable=True)
    #: اسمُ أيقونةِ lucide — والتطبيقان يستعملانها أصلاً
    icon: Mapped[str] = mapped_column(String(40), nullable=False)
    #: **`by_country` تعني الاثنين** — مقروءةً من `campaigns.py` لا مخترَعة
    audience: Mapped[CampaignAudience] = mapped_column(
        pg_enum(CampaignAudience, "campaign_audience"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    destination: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[ServiceTileStatus] = mapped_column(
        pg_enum(ServiceTileStatus, "service_tile_status"),
        nullable=False,
        server_default=text("'hidden'"),
    )
    #: **شارةُ «جديد» بمدّتها** — تختفي بانقضائها **بلا نشر**
    new_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint("country_code", "key", name="service_tile_key_per_market"),
        CheckConstraint(
            "status <> 'active' OR destination IS NOT NULL",
            name="service_tile_active_needs_destination",
        ),
    )

    def is_new_on(self, today: date) -> bool:
        """أتُعرض شارةُ «جديد»؟ — **حسابٌ واحدٌ لا تكرارٌ في كلِّ قارئ**."""
        return self.new_until is not None and today <= self.new_until


class PromoBanner(UUIDMixin, TimestampMixin, Base):
    """لافتةُ محتوى — **بنافذةٍ إلزاميّة**، يملؤها المشرف."""

    __tablename__ = "promo_banners"

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    body: Mapped[str | None] = mapped_column(String(160), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(40), nullable=True)
    audience: Mapped[CampaignAudience] = mapped_column(
        pg_enum(CampaignAudience, "campaign_audience"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    #: **إلزاميّةٌ بقرار المالك**: «لافتةٌ بلا مدّةِ انتهاءٍ لا تُقبل» —
    #: **وعمودٌ اختياريٌّ يجعل لافتةَ عيدٍ تبقى إلى العيد القادم**
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    link_kind: Mapped[BannerLinkKind] = mapped_column(
        pg_enum(BannerLinkKind, "banner_link_kind"),
        nullable=False,
        server_default=text("'none'"),
    )
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="promo_banner_window_forward"),
        CheckConstraint(
            "link_kind = 'none' OR link IS NOT NULL",
            name="promo_banner_link_matches_kind",
        ),
        Index("promo_banner_live", "country_code", "starts_at", "ends_at"),
    )
