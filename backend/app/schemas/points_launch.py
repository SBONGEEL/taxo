"""**مخطّطاتُ نقاط الالتزام وحملة الإطلاق وعروض الركاب** (§١١٤ — أمرُ المالك ٢٠٢٦-١١-٢٤ السادس)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode


# ===================================================================== نقاطُ الالتزام


class CommitmentRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_code: CountryCode
    is_enabled: bool
    window_start: time
    window_end: time
    span_minutes: int
    max_break_minutes: int
    max_total_break_minutes: int
    points_per_day: int | None
    points_per_credit_unit: int | None
    credit_unit_value: Decimal | None
    daily_points_cap: int | None
    monthly_points_cap: int | None
    points_expiry_days: int | None
    credit_expiry_days: int | None
    require_service_area: bool
    max_accounts_per_device: int


class CommitmentRulePatch(BaseModel):
    """**كلُّ حقلٍ اختياريّ** — وما لم يُرسل لا يُمسّ. والقيمُ الماليّةُ يضعها المالكُ وحدَه."""

    model_config = ConfigDict(extra="forbid")

    is_enabled: bool | None = None
    window_start: time | None = None
    window_end: time | None = None
    span_minutes: int | None = Field(default=None, ge=60, le=1020)
    max_break_minutes: int | None = Field(default=None, ge=1, le=600)
    max_total_break_minutes: int | None = Field(default=None, ge=1, le=900)
    points_per_day: int | None = Field(default=None, ge=1, le=100000)
    points_per_credit_unit: int | None = Field(default=None, ge=1, le=1000000)
    credit_unit_value: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    daily_points_cap: int | None = Field(default=None, ge=1)
    monthly_points_cap: int | None = Field(default=None, ge=1)
    points_expiry_days: int | None = Field(default=None, ge=1, le=3650)
    credit_expiry_days: int | None = Field(default=None, ge=1, le=3650)
    require_service_area: bool | None = None
    max_accounts_per_device: int | None = Field(default=None, ge=1, le=10)
    #: **حقولٌ تُفرَّغ صراحةً** (السقفُ والصلاحيّةُ «بلا حدّ») — لأن `None` أعلاه تعني «لا تمسّ»
    clear: list[str] = Field(default_factory=list)


class CommitmentTodayOut(BaseModel):
    state: str
    elapsed_minutes: int
    online_minutes: int
    breaks_used_minutes: int
    break_count: int
    current_break_minutes: int
    remaining_minutes: int
    can_restart: bool
    reason: str | None


class CommitmentDayOut(BaseModel):
    day: date
    status: str
    reason: str | None
    online_minutes: int
    total_break_minutes: int


class MyCommitmentOut(BaseModel):
    enabled: bool
    window_start: str
    window_end: str
    span_minutes: int
    max_break_minutes: int
    max_total_break_minutes: int
    points_per_day: int | None
    points_per_credit_unit: int | None
    credit_unit_value: str | None
    currency: str
    points_balance: int
    credit_balance: str
    credit_value_of_points: str | None
    convertible_points: int
    today: CommitmentTodayOut
    recent: list[CommitmentDayOut]


class ConvertIn(BaseModel):
    points: int = Field(ge=1)


class ConvertOut(BaseModel):
    points: int
    amount: Decimal
    currency: str
    credit_balance: Decimal


class CreditPurchaseIn(BaseModel):
    plan_id: uuid.UUID
    idempotency_key: str = Field(min_length=8, max_length=80)


class CommitmentReportRow(BaseModel):
    driver_id: uuid.UUID
    driver_name: str | None
    met: int
    disqualified: int
    not_met: int
    flagged: int
    points_balance: int
    credit_balance: str


class DutyDayAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_id: uuid.UUID
    day: date
    status: str
    online_minutes: int
    break_count: int
    longest_break_minutes: int
    total_break_minutes: int
    span_start: datetime | None
    span_end: datetime | None
    reason: str | None
    flags: list[str]
    rides_completed: int


# ===================================================================== حملةُ الإطلاق


class LaunchCampaignOut(BaseModel):
    enabled: bool
    show_banner: bool
    launch_date: str
    launch_at: str
    pre_launch_free_days: int
    post_launch_free_days: int
    zero_commission: bool
    banner: str
    partner_notice: str
    status: str | None = None
    grant_starts_at: str | None = None
    grant_ends_at: str | None = None
    ack_required: bool = False


class LaunchCampaignPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_enabled: bool | None = None
    launch_date: date | None = None
    pre_launch_free_days: int | None = Field(default=None, ge=0, le=365)
    post_launch_free_days: int | None = Field(default=None, ge=0, le=365)
    zero_commission: bool | None = None
    show_banner: bool | None = None


class LaunchGrantRow(BaseModel):
    driver_id: uuid.UUID
    driver_name: str | None
    kind: str
    starts_at: str
    ends_at: str
    has_subscription: bool


class AckOut(BaseModel):
    acknowledged_at: datetime


# ===================================================================== عروضُ الركاب


class RiderPerksOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_code: CountryCode
    free_cancel_seconds: int | None
    premium_after_rides: int | None
    premium_priority: bool


class RiderPerksPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    free_cancel_seconds: int | None = Field(default=None, ge=30, le=900)
    premium_after_rides: int | None = Field(default=None, ge=1, le=1000)
    premium_priority: bool | None = None
    clear: list[str] = Field(default_factory=list)


class PartnerCouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    shop_name: str
    shop_area: str | None
    title: str
    details: str | None
    coupon_code: str | None
    valid_from: datetime | None
    valid_until: datetime | None
    is_active: bool
    sort_order: int


class PartnerCouponIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shop_name: str | None = Field(default=None, max_length=120)
    shop_area: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=120)
    details: str | None = Field(default=None, max_length=1000)
    coupon_code: str | None = Field(default=None, max_length=40)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)


class RiderOfferItem(BaseModel):
    kind: str
    label: str
    discount_type: str
    discount_value: str
    max_discount: str | None


class RiderCouponItem(BaseModel):
    id: uuid.UUID
    shop_name: str
    shop_area: str | None
    title: str
    details: str | None
    coupon_code: str | None
    valid_until: str | None


class RiderOffersOut(BaseModel):
    premium: bool
    premium_after_rides: int | None
    completed_rides: int
    free_cancel_seconds: int | None
    offers: list[RiderOfferItem]
    coupons: list[RiderCouponItem]


class CaptainDiscountRow(BaseModel):
    ride_id: uuid.UUID
    completed_at: str | None
    label: str
    discount: str
    fare: str | None
    currency: str


class CaptainDiscountsOut(BaseModel):
    month: str
    rides: list[CaptainDiscountRow]
    total: str
    count: int
