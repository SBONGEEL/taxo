"""أسعارُ صرفٍ تضعها الإدارة — **للمجموع التقريبيّ في «المالية العامة» وحدَه** (SPEC §٧٤-أ/٩).

**لا مالَ هنا ولا تحويل**: سعرٌ يُضرب فيه مجموعٌ للعرض، **موسوماً «تقريبي — بسعر صرف تضعه الإدارة»** ومعه السعرُ وتاريخُه. **ولا يُجمع دينارٌ
إلى دينارٍ إلا عبره**، ولا يُكتب بسببه صفٌّ في أيِّ جدولِ مال.

**والتاريخُ يُحفظ لا يُستبدل**: كلُّ ضبطٍ صفٌّ جديد، والساري أحدثُ صفٍّ لكلِّ (عملةٍ مرجعيّة × عملة) — **فيُقرأ بعد شهرٍ بأيِّ سعرٍ قُرئ رقمُ يومٍ
ما**. **والعملةُ المرجعيّةُ رمزٌ من ثلاثة أحرف** (USD · EUR …) لا عضوٌ في `Currency`: هي عملةُ عرضٍ لا عملةُ سوق.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import Currency


class ExchangeRate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        CheckConstraint("rate > 0", name="exchange_rate_positive"),
        CheckConstraint("reference ~ '^[A-Z]{3}$'", name="exchange_rate_reference_code"),
        Index("ix_exchange_rates_current", "reference", "currency", "created_at"),
    )

    #: **العملةُ المرجعيّة** — ما يُعرض به المجموعُ التقريبيّ
    reference: Mapped[str] = mapped_column(String(3), nullable=False)
    currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    #: **كم وحدةً من المرجعيّة لوحدةٍ واحدةٍ من العملة** — 1 د.أ = 1.41 دولاراً
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    set_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
