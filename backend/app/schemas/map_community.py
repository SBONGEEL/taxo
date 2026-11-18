"""مخطّطاتُ اقتراحات الأماكن وبلاغات الطريق والازدحام (أمرُ المالك ٢٠٢٦-١١-١٨ السابع)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import MapPlaceCategory

SuggestionKind = Literal["add", "fix"]
RoadReportKind = Literal["works", "closed", "accident", "jam"]


class PlaceSuggestionIn(BaseModel):
    kind: SuggestionKind
    name_ar: str = Field(min_length=2, max_length=80)
    name_en: str | None = Field(default=None, max_length=80)
    category: MapPlaceCategory
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    #: الاسمُ كما رآه على الخريطة — للتصحيح
    current_name: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=300)


class PlaceSuggestionOut(BaseModel):
    """**لصاحبه**: أنّه وصل وينتظر المراجعة — لا أكثر."""

    id: uuid.UUID
    status: str


class PlaceSuggestionAdminOut(BaseModel):
    id: uuid.UUID
    country_code: str
    kind: str
    name_ar: str
    name_en: str | None
    category: str
    lat: float
    lng: float
    current_name: str | None
    note: str | None
    status: str
    created_at: datetime
    reviewed_at: datetime | None
    review_note: str | None
    map_place_id: uuid.UUID | None


class SuggestionApproveIn(BaseModel):
    name_ar: str | None = Field(default=None, min_length=2, max_length=80)
    category: MapPlaceCategory | None = None


class SuggestionRejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class RoadReportIn(BaseModel):
    kind: RoadReportKind
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class RoadReportOut(BaseModel):
    """**بلا اسم المبلِّغ** — النوعُ والموضعُ وحدهما، وكم أكّده ومتى ينتهي."""

    id: uuid.UUID
    kind: str
    lat: float
    lng: float
    confirmations: int
    expires_at: datetime


class RoadReportAckOut(RoadReportOut):
    created: bool
    counted: bool
    #: **أيُرى الآن؟** — بتأكيدٍ كافٍ أو بموافقة المشرف
    visible: bool


class RoadReportAdminOut(RoadReportOut):
    country_code: str
    approved: bool
    status: str
    created_at: datetime


class TrafficOut(BaseModel):
    """GeoJSON — خطوطُ مقاطعَ بلونٍ لا برقم (`l`: free · slow · heavy)."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict]
