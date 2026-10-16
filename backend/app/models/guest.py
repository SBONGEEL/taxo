"""وضعُ الضيف (SPEC §٧٦-ن/أ، أمرُ المالك ٢٠٢٦-١٠-١٥) — **جلسةُ عرضٍ موسومةٌ لا حساب**.

**ولمَ لا صفٌّ في `users`؟** الضيفُ لا يُعدّ في أيِّ مقياسٍ ولا تقريرٍ ماليّ — وكلُّ مقياسٍ في المشروع يعدّ `users`. صفٌّ هناك بعلامةٍ
يحتاج أن يتذكّر كلُّ عدّادٍ اليومَ وغداً أن يطرحه؛ **وجدولٌ منفصلٌ لا يدخل عدّاداً أصلاً**. **ولا رحلةَ ولا قيدَ ولا محفظةَ للضيف** —
كلُّ ما يراه محاكاةٌ في التطبيق نفسِه، والخادمُ لا يعرف منه إلا أنه بدأ وما كتبه في «أرسل ملاحظة».

**ولا هويّةَ فيه**: الجهازُ والعنوانُ مُجزَّآن بمفتاح الخادم (`guest.fingerprint`) — للحدّ وحدَه لا للتعرّف. **ويُمحى بعد ٣٠ يوماً**
ومعه ملاحظاتُه (`guest.expired`).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class GuestSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "guest_sessions"
    __table_args__ = (CheckConstraint("app IN ('rider', 'driver')", name="guest_sessions_app"),)

    #: `rider` أو `driver` — التطبيقُ الذي بدأ منه
    app: Mapped[str] = mapped_column(String(8), nullable=False)
    #: **مُجزَّأٌ لا خام** — للحدِّ لكلِّ جهاز
    device_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    #: دولةُ الشبكة كما تقولها حافّةُ Cloudflare (`CF-IPCountry`) — **لتُعرف الأسواقُ التي يأتي منها المختبِرون**، لا أكثر
    network_region: Mapped[str | None] = mapped_column(String(2), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GuestModeSetting(UUIDMixin, TimestampMixin, Base):
    """**مفتاحُ وضع الضيف لكلِّ تطبيق** — صفٌّ واحدٌ عالميٌّ كسياسة الدخول: العرضُ ليس سوقاً.

    **والافتراضُ مطفأٌ في القاعدة**: صفٌّ مفقودٌ لا يفتح باباً لم يقرّره أحد.
    """

    __tablename__ = "guest_mode_settings"
    __table_args__ = (CheckConstraint("singleton IS TRUE", name="guest_mode_settings_singleton"),)

    singleton: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True, unique=True
    )
    rider_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    driver_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
