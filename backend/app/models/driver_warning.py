"""إنذاراتُ الكبتن (SPEC §٦٣-ج/٣) — **اعتذارُه عن حجزٍ مضمونٍ بعد أن أكّده**، من المرّة الأولى بنصِّ المالك.

**صفٌّ لكلِّ اعتذار لا عدّادٌ على الكبتن**: «اعتذاران في شهر» نافذةٌ تتدحرج، وعدّادٌ يُصفَّر بيدٍ يفترق عن الواقع أوّلَ شهر.
**ومعه الغرامةُ وما لم يغطّه رصيدُه** (`penalty_shortfall`) — والباقي سؤالٌ للمالك (`APPROVALS-62` §٥-١/١٣) لا يُحصَّل بتخمين.
**ولا حذف** — سجلُّ جودةٍ لا يُمحى.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin

WARNING_GUARANTEE_WITHDRAWAL = "guarantee_withdrawal"


class DriverWarning(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "driver_warnings"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('guarantee_withdrawal') AND penalty_amount >= 0 AND penalty_shortfall >= 0",
            name="driver_warning_valid",
        ),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ride_bookings.id", ondelete="SET NULL"), nullable=True
    )
    #: ما انتقل فعلاً من محفظته إلى الراكب
    penalty_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default=text("0")
    )
    #: ما لم يغطّه رصيدُه — **يُسجَّل ولا يُحصَّل** حتى يقرّر المالك
    penalty_shortfall: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default=text("0")
    )
