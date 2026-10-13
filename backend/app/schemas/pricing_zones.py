"""«مناطق التسعير» في اللوحة (SPEC §٧٤-أ/٥)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode
from app.schemas.settings import Money


class ZoneRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vehicle_category: str
    base_fare: Decimal
    price_per_km: Decimal
    price_per_min: Decimal
    minimum_fare: Decimal


class PricingZoneOut(BaseModel):
    id: uuid.UUID
    country_code: CountryCode
    code: str
    name_ar: str
    name_fr: str | None
    note: str | None
    rugged: bool
    adjustment_mode: Literal["percent", "table"]
    adjustment_percent: Decimal
    rules: list[ZoneRuleOut]


class PricingZonesOut(BaseModel):
    zones: list[PricingZoneOut]
    #: **مصدرُ الحدود** — يُعرض تحت الخريطة (ODbL يشترط الإسناد)
    attribution: str | None = None


class PricingZoneUpdate(BaseModel):
    rugged: bool | None = None
    adjustment_mode: Literal["percent", "table"] | None = None
    #: **زيادةٌ لا خصم، ولها سقف** — ٠ إلى ٢٠٠
    adjustment_percent: Decimal | None = Field(default=None, ge=0, le=200, max_digits=5, decimal_places=2)


class ZoneRuleIn(BaseModel):
    base_fare: Decimal = Money
    price_per_km: Decimal = Money
    price_per_min: Decimal = Money
    minimum_fare: Decimal = Money
