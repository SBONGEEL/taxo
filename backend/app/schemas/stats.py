from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class OverviewOut(BaseModel):
    """أرقام «نظرة عامة» — جاهزةً للعرض بلا جمعٍ في الواجهة (القسم 13/1)."""

    period: str
    from_at: datetime
    to_at: datetime

    completed_rides: int
    cancelled_rides: int
    # `NUMERIC(12,3)` يخرج نصّاً إلى الواجهة كبقية المال
    revenue: Decimal

    online_drivers: int
    active_rides: int
    active_subscriptions: int
    open_disputes: int

    # بطاقاتُ الإجراء في التصميم: ما ينتظر قراراً بشرياً الآن
    pending_documents: int
    pending_withdrawals: int

    # أربعٌ وعشرون خانة بترتيب ساعات **يوم الدولة**
    rides_by_hour: list[int]
    payment_mix: dict[str, int]
