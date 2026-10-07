"""اشتراكُ الراكب — المشوارُ الثابت (SPEC §٦٣-ج/٦)."""

from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import Currency
from app.schemas.ride import CoordinatesIn


class CommutePlanIn(BaseModel):
    pickup: CoordinatesIn
    dropoff: CoordinatesIn
    pickup_address: str | None = Field(default=None, max_length=255)
    dropoff_address: str | None = Field(default=None, max_length=255)
    #: **قناعُ بتات** بترتيب `weekday()`: الإثنين ١ · الثلاثاء ٢ · … · الأحد ٦٤
    weekdays: int = Field(ge=1, le=127)
    go_time: time
    return_time: time | None = None
    starts_on: date


class CommuteQuoteOut(BaseModel):
    """**كلُّ رقمٍ محسوبٌ في الخلفية** — سعرُ الرحلة المجمَّد وعددُها والمجموع، والخصمُ نسبةٌ تُقرأ «وفّرتَ ١٠٪»."""

    discount_percent: Decimal
    price_per_ride: Decimal
    rides_total: int
    total: Decimal
    ends_on: date
    currency: Currency


class CommuteOut(BaseModel):
    id: uuid.UUID
    status: str
    pickup_address: str | None
    dropoff_address: str | None
    weekdays: int
    go_time: time
    return_time: time | None
    starts_on: date
    ends_on: date
    discount_percent: Decimal
    price_per_ride: Decimal
    rides_total: int
    #: ما اكتمل حتى الآن — **وما بقي يعود رصيداً** عند النهاية
    rides_done: int
    amount_paid: Decimal
    currency: Currency
    suspended_days: list[date]
    #: اسمُ الكبتن المعتمد كما يراه الراكب — و`null` بلا كبتن
    captain_name: str | None


class CommuteSuspendIn(BaseModel):
    day: date


class CommuteOfferOut(BaseModel):
    """عرضُ الاشتراك كما يراه الكبتن — **بلا اسم الراكب ولا رقمه**، والدخلُ المتوقَّعُ محسوبٌ هنا."""

    id: uuid.UUID
    pickup_address: str | None
    dropoff_address: str | None
    weekdays: int
    go_time: time
    return_time: time | None
    starts_on: date
    ends_on: date
    price_per_ride: Decimal
    rides_total: int
    currency: Currency
    approved: bool
