"""مخطّطاتُ نقاط الولاء (البند ١٤، §٩٧/١٤)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LoyaltyRuleIn(BaseModel):
    points_per_ride: int = Field(ge=1, le=10000)
    expiry_days: int = Field(ge=30, le=1095)
    silver_threshold: int = Field(ge=1)
    gold_threshold: int = Field(ge=2)
    silver_bonus_percent: int = Field(ge=0, le=100)
    gold_bonus_percent: int = Field(ge=0, le=100)
    redeem_points: int = Field(ge=1)
    redeem_value: Decimal = Field(gt=0, max_digits=12, decimal_places=3)


class LoyaltyRuleOut(LoyaltyRuleIn):
    country_code: str
    #: **من الخلفية**: ركّابٌ لهم نقاطٌ سارية، ومجموعُ ما بقي، وما استُبدل رصيداً
    holders: int
    open_points: int
    redeemed_value: Decimal


class LoyaltyOut(BaseModel):
    enabled: bool
    currency: str
    points: int
    tier: str
    year_points: int
    next_tier: str | None
    to_next: int | None
    bonus_percent: int
    redeem_points: int | None
    redeem_value: Decimal | None
    redeemable_value: Decimal
    expiry_days: int | None
    expiring_points: int
    expiring_at: datetime | None


class RedeemIn(BaseModel):
    blocks: int = Field(ge=1, le=1000)
