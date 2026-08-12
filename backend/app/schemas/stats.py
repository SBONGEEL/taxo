from __future__ import annotations

import uuid
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


class DayRevenueOut(BaseModel):
    day: str
    revenue: Decimal
    rides: int


class TopDriverOut(BaseModel):
    driver_id: uuid.UUID
    name: str
    completed_rides: int
    revenue: Decimal
    rating_avg: Decimal


class PlanSalesOut(BaseModel):
    plan_id: uuid.UUID
    plan_name: str
    sold: int
    revenue: Decimal


class ReportsOut(BaseModel):
    """«التقارير والإحصاءات» (SPEC القسم 13/5) — نِسَبٌ ومتوسطاتٌ محسوبة.

    المتوسطُ والنسبةُ يخرجان من الخلفية جاهزين لا معاملَين تقسمهما الواجهة:
    البسطُ والمقام كلاهما مجموعٌ على الجدول كلِّه، وقسمةُ رقمين مسقوفَين تعطي
    متوسطَ الصفحة لا متوسط الفترة.
    """

    period: str
    from_at: datetime
    to_at: datetime
    currency: str

    revenue_by_day: list[DayRevenueOut]
    avg_ride_fare: Decimal
    # نسبةٌ مئوية بمنزلتين — لا كسرٌ يضربه العرض في مئة
    cancellation_rate: Decimal
    active_drivers: int

    subscriptions_sold: int
    subscription_revenue: Decimal
    sales_by_plan: list[PlanSalesOut]

    top_drivers: list[TopDriverOut]
