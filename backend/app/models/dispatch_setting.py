"""إعداداتُ التوزيع لكلِّ سوق — الترحيلة `0062`.

**والغيابُ لا يُفترض تفعيلاً**: صفٌّ غائبٌ يعني القيمَ الافتراضيّةَ المكتوبة في
`services/dispatch_settings.py` — **وهي التي تُقرأ في التطبيق**، لا التي تكتبها
القاعدة، لأن سوقاً بلا صفٍّ يجب أن يوزّع كسوقٍ بصفٍّ افتراضيّ.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, DispatchMode


class DispatchSetting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "dispatch_settings"

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    #: **تسلسليٌّ افتراضاً** — فتشغيلُ الجدول لا يغيّر سلوكاً قائماً
    mode: Mapped[DispatchMode] = mapped_column(
        pg_enum(DispatchMode, "dispatch_mode"),
        nullable=False,
        server_default=text("'sequential'"),
    )
    offer_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("7")
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("5")
    )
    total_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("120")
    )
    #: **تبريدٌ لا استبعادٌ دائم** — والصفرُ ممنوعٌ في القاعدة
    cooldown_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("30")
    )
    broadcast_batch_size: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("4")
    )
    #: **«وجهتي»** (البند ١٥، الترحيلة `0148`) — كم مرّةً في اليوم يضع الكبتنُ وجهة، **و`0` يطفئها في السوق**
    destination_daily_uses: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("2")
    )
    #: والانحرافُ المقبولُ عن طريقه المباشر إليها، بالمئة من طوله
    destination_detour_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("30")
    )

    __table_args__ = (
        UniqueConstraint("country_code", name="dispatch_settings_country"),
        CheckConstraint(
            "offer_timeout_seconds BETWEEN 3 AND 120",
            name="dispatch_offer_timeout_range",
        ),
        CheckConstraint(
            "max_attempts BETWEEN 1 AND 50", name="dispatch_max_attempts_range"
        ),
        CheckConstraint(
            "total_timeout_seconds BETWEEN 10 AND 900",
            name="dispatch_total_timeout_range",
        ),
        CheckConstraint(
            "cooldown_seconds BETWEEN 1 AND 600", name="dispatch_cooldown_range"
        ),
        CheckConstraint(
            "broadcast_batch_size BETWEEN 1 AND 20",
            name="dispatch_batch_size_range",
        ),
        CheckConstraint(
            "destination_daily_uses BETWEEN 0 AND 10",
            name="dispatch_destination_uses_range",
        ),
        CheckConstraint(
            "destination_detour_percent BETWEEN 5 AND 100",
            name="dispatch_destination_detour_range",
        ),
    )
