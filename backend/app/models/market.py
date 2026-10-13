"""الدولُ والحدود (SPEC §٧٤-أ/٢–٣، أمرُ المالك ٢٠٢٦-١٠-١٣) — ثلاثةُ جداول، **ولا عمودَ لحال السوق**.

**حالُ السوق (مفتوحة/مغلقة) تبقى في مفتاح `country_visible` القائم** (§٢٤): بيتٌ واحدٌ للحقيقة يقرؤه `/config` منذ ٢٠٢٦-٠٨-١٩،
**وجدولٌ ثانٍ يحمل الحالَ نفسَها يفترق عنه أوّلَ تعديل** (الشكلُ الثامن). والجديدُ أن بابَه صار صفحةَ «الدول» وحدَها (فحصُ الجاهزيّة
والصلاحية)، **ويردّه بابُ المفاتيح العامّ**.

١. **`country_markets`** — صفٌّ لكلِّ دولةٍ **بما ليس في المفتاح**: ظهورُ المغلقة في التسجيل. **وغيابُ الصفِّ «قريباً»** — افتراضُ
   المالك بلفظه، **والسكوتُ لا يُخفي دولةً من التسجيل ولا يجعلها تُختار** (المغلقةُ لا تُختار أبداً).
٢. **`market_borders`** — صفٌّ واحدٌ عالميّ: **«الحدودُ مفروضة»**. **وغيابُه «مفروضة»** — السكوتُ لا يُسقط حدّاً (قاعدةُ
   `DEFAULT_ENABLED_FLAGS` في اتجاهها الآمن)، ورفعُها فعلُ مالكٍ صريحٌ مدقَّق.
٣. **`border_allowances`** — قائمةُ الحسابات المسموح لها بالعمل من خارج الحدود والحدودُ مفروضة. **والنزعُ ختمٌ لا حذف**
   (`revoked_at`): من سُمح له ومتى ومن نزع — يُقرأ بعد شهر؛ **وسماحٌ قائمٌ واحدٌ لكلِّ حساب** (فهرسٌ فريدٌ جزئيّ).

**ولا مالَ هنا**: لا عمودَ مالٍ ولا صلةَ بجداول المال — فبوّابةُ المال لا تعنيها هذه الترحيلة.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, SignupDisplay


class CountryMarket(TimestampMixin, Base):
    """ما يخصّ الدولةَ في صفحة «الدول» سوى حالها — **ظهورُ المغلقة في التسجيل**."""

    __tablename__ = "country_markets"

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), primary_key=True
    )
    signup_display: Mapped[SignupDisplay] = mapped_column(
        pg_enum(SignupDisplay, "signup_display"),
        nullable=False,
        default=SignupDisplay.SOON,
        server_default=SignupDisplay.SOON.value,
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class MarketBorders(UUIDMixin, TimestampMixin, Base):
    """مفتاحُ «العمل خارج حدود الدول» — **صفٌّ واحدٌ عالميّ** يحرسه `singleton` (كسياسة دخول اللوحة).

    **عالميٌّ لا لكلِّ دولة**: نصُّ المالك مفتاحٌ واحد، والحدُّ نفسُه يُقرأ بدولة الحساب. **ورفعُه لا يفتح دولةً مغلقة** — ذلك
    سؤالٌ آخرُ يُسأل في بابه.
    """

    __tablename__ = "market_borders"
    __table_args__ = (
        CheckConstraint("singleton IS TRUE", name="market_borders_singleton"),
    )

    singleton: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True, unique=True
    )
    #: **مفروضةٌ افتراضاً في القاعدة أيضاً** — صفٌّ يُدخَل يدويّاً في عطلٍ ليلاً يخرج بالحدود لا بلاها
    enforced: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true"), default=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class BorderAllowance(UUIDMixin, TimestampMixin, Base):
    """حسابٌ مسموحٌ له بالعمل من خارج حدود الدول **والحدودُ مفروضة** — بسببٍ مكتوب، ونزعُه ختم."""

    __tablename__ = "border_allowances"
    __table_args__ = (
        CheckConstraint("length(btrim(reason)) >= 3", name="border_allowance_reason"),
        # **سماحٌ قائمٌ واحدٌ لكلِّ حساب** — والمنزوعُ يبقى سطراً في التاريخ
        Index(
            "uq_border_allowance_active",
            "user_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
