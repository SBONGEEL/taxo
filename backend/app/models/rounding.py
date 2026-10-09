"""سجلُّ التقريب (SPEC §٧٠-ج/٣، الترحيلة `0104`) — **القيدُ الصريحُ لكلِّ فلس**.

**لمَ جدولٌ لا قيدٌ في الدفتر**: النقدُ وكليك للرحلة **لا قيدَ لهما في الدفتر** (يقبضهما الكبتنُ بيده)، والبطاقةُ لا قيدَ للراكب
فيها — **فقيدُ دفترٍ لفرق التقريب لا يرى الطرقَ كلَّها**، والسجلُّ يراها. لكلِّ تقريبٍ صفٌّ واحد: الدولة · المصدرُ ومعرّفُه ·
الشخص · **الدقيقُ والمقرَّبُ والفرق** · الوحدةُ والاتجاه.

**ويُضاف إليه ولا يُعدَّل ولا يُحذف** — مشغّلٌ في القاعدة كمشغّل الدفتر (`0006`)، فالتصحيحُ صفٌّ جديدٌ لا محوٌ لتاريخ.
**وبمفتاحٍ فريدٍ على المصدر** فلا يُكتب تقريبُ معاملةٍ مرّتين. **ولا صفَّ لفرقٍ صفريّ** (`rounding.record` يقول لمَ).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class MoneyRounding(UUIDMixin, Base):
    """تقريبُ مبلغٍ واحدٍ يدفعه شخصٌ أو يقبضه — يُكتب ولا يُعدَّل ولا يُحذف."""

    __tablename__ = "money_roundings"
    __table_args__ = (
        # **مصدرٌ واحدٌ ⇐ تقريبٌ واحد**: إنهاءٌ يُعاد أو نداءٌ يتكرّر لا يكتب فرقاً ثانياً
        UniqueConstraint("source_kind", "source_id"),
        # **الفرقُ هو المقرَّبُ ناقصَ الدقيق حرفاً، ولا يكون صفراً** — صفٌّ يقول غيرَ ما بين عمودَيه لا يُكتب
        CheckConstraint(
            "difference = rounded - precise AND difference <> 0",
            name="money_rounding_difference",
        ),
        CheckConstraint(
            "unit > 0 AND mode IN ('nearest', 'up', 'down')",
            name="money_rounding_policy",
        ),
        Index("ix_money_roundings_country_created", "country_code", "created_at"),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    #: `RoundingSource` — **نصٌّ بلا قيدٍ في القاعدة** فيُضاف مصدرٌ بلا ترحيلة، والتعدادُ يحرس الكتابة
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    #: **الشخصُ الذي دفع أو قبض** — `users.id` كمالك الدفتر. **RESTRICT**: من له مالٌ مسجَّلٌ لا يُحذف صفُّه
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    #: **المبلغُ بدقّته** (`0.001`) قبل التقريب
    precise: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: **ما دُفع أو قُبض فعلاً** — مضاعفٌ للوحدة
    rounded: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: **المقرَّبُ − الدقيق** — موجبٌ إن زاد ما يدفعه الشخص، سالبٌ إن نقص
    difference: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    #: **الإعدادُ الذي قُرِّب به** — مجمَّدٌ على الصفّ، فتعديلُ اللوحة غداً لا يغيّر ما يقوله صفُّ اليوم
    unit: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<MoneyRounding {self.source_kind}:{self.source_id} {self.difference}>"
