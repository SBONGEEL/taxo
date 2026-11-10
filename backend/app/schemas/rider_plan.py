"""مخطّطاتُ اشتراكات الركّاب (البند ١٣، §٩٧/١٣)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import CountryCode


class RiderPlanIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    days: int = Field(ge=7, le=365)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    discount_percent: Decimal = Field(gt=0, le=50, max_digits=5, decimal_places=2)
    per_ride_cap: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    monthly_cap: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    terms: str | None = Field(default=None, max_length=2000)
    bearer: Literal["taxo", "captain"]


class RiderPlanPatch(BaseModel):
    is_active: bool


class RiderPlanOut(BaseModel):
    id: uuid.UUID
    country_code: CountryCode
    name: str
    days: int
    price: Decimal
    discount_percent: Decimal
    per_ride_cap: Decimal
    monthly_cap: Decimal
    terms: str | None
    bearer: str
    is_active: bool


class RiderPlanAdminOut(RiderPlanOut):
    #: **من الخلفية**: المشتركون الآن، وما دُفع ثمناً، وما خُصم
    active_subscribers: int
    revenue: Decimal
    discounts: Decimal


class MyPlanOut(BaseModel):
    plan_name: str
    starts_at: datetime
    ends_at: datetime
    discount_percent: Decimal
    per_ride_cap: Decimal
    monthly_cap: Decimal
    #: **ما وفّره الراكبُ** في هذا الاشتراك، وما بقي من حدِّ الشهر — محسوبان هنا لا في التطبيق
    saved: Decimal
    month_left: Decimal
    #: يُجدَّد الآن (الأيامُ الثلاثةُ الأخيرة)
    can_renew: bool


class MyPlansOut(BaseModel):
    enabled: bool
    currency: str
    plans: list[RiderPlanOut]
    current: MyPlanOut | None
