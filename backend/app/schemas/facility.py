"""مخطّطاتُ «المرافق الحيوية» (SPEC §٦٣-ج/٢) — المضلّعُ `[[lng, lat], …]` بترتيب GeoJSON بلا النقطة المكرَّرة في آخره."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import CountryCode

Point = list[float]


class FacilityIn(BaseModel):
    country_code: CountryCode
    name: str = Field(min_length=2, max_length=80)
    area: list[Point] = Field(min_length=3, max_length=200)
    #: **رسمُ الكبتن بعملة السوق** — وصفرٌ لا يُطبَّق
    fee: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    is_active: bool = True


class FacilityPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    area: list[Point] | None = Field(default=None, min_length=3, max_length=200)
    fee: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    is_active: bool | None = None


class FacilityOut(BaseModel):
    id: uuid.UUID
    country_code: CountryCode
    kind: str
    name: str
    area: list[Point]
    fee: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AirportOut(BaseModel):
    """مطارٌ يختاره الراكبُ وجهةً — اسمُه ونقطةٌ داخل مضلّعه، **لا الرسمُ ولا الحدود** (§٦٣-ج/٢)."""

    id: uuid.UUID
    name: str
    lat: float
    lng: float
