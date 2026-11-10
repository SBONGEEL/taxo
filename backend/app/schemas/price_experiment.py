"""مخطّطاتُ تجارب الأسعار (البند ٤، §٩٧/٤)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import CountryCode


class PriceExperimentIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    #: **موجبةٌ زيادةٌ وسالبةٌ خصم** — بين −50 و+50 ولا صفر
    adjust_percent: Decimal = Field(ge=-50, le=50, max_digits=5, decimal_places=2)
    share_percent: int = Field(ge=1, le=100)
    days: int = Field(ge=1, le=60)
    center_lat: float | None = Field(default=None, ge=-90, le=90)
    center_lng: float | None = Field(default=None, ge=-180, le=180)
    radius_km: Decimal | None = Field(default=None, gt=0, le=200, max_digits=6, decimal_places=2)


class ArmStatsOut(BaseModel):
    arm: str
    requests: int
    completed: int
    cancelled: int
    fares: Decimal
    commission: Decimal
    captains: Decimal
    completion_percent: int | None
    cancel_percent: int | None
    average_fare: Decimal | None


class PriceExperimentOut(BaseModel):
    id: uuid.UUID
    country_code: CountryCode
    name: str
    adjust_percent: Decimal
    share_percent: int
    days: int
    center_lat: float | None
    center_lng: float | None
    radius_km: Decimal | None
    status: str
    started_at: datetime | None
    ends_at: datetime | None
    stopped_at: datetime | None
    decided_at: datetime | None
    #: **انتهت مدّتُها** وهي «تعمل» — لا تُسعِّر بعدها، وتنتظر الإيقافَ والقرار
    expired: bool
    #: «تطبيقُ الفائز» للتجربة على الدولة كلِّها وحدَها
    can_apply: bool
    arms: list[ArmStatsOut]
