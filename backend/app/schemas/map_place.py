"""مخطّطاتُ «الأماكن» (SPEC §٧١-د/١٤) — **والتحقّقُ هنا لا في الشاشة**: من أرسل بـ`curl` لا يتجاوزه."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CountryCode, MapPlaceCategory

#: **الفئةُ من التعداد نفسِه** الذي يبني قيدَ القاعدة — فلا مرآتان تفترقان
Category = MapPlaceCategory


def _name(value: str | None) -> str | None:
    """**المسافاتُ تُطوى** — اسمٌ بمسافتين بين كلمتيه يُبحث عنه بمسافةٍ فلا يُوجد."""
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


def _required(value: str | None) -> str | None:
    """**والعربيُّ لا يُفرَّغ** — اسمٌ من مسافاتٍ يمرّ بحدِّ الطول ثمّ يُطوى إلى لا شيء."""
    if value is None:
        return None
    cleaned = _name(value)
    if cleaned is None or len(cleaned) < 2:
        raise ValueError("الاسمُ العربيُّ حرفان على الأقل")
    return cleaned


class MapPlaceIn(BaseModel):
    country_code: CountryCode
    name_ar: str = Field(min_length=2, max_length=80)
    name_en: str | None = Field(default=None, max_length=80)
    category: Category
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    is_hidden: bool = False

    @field_validator("name_ar")
    @classmethod
    def _clean_ar(cls, value: str | None) -> str | None:
        return _required(value)

    @field_validator("name_en")
    @classmethod
    def _clean_en(cls, value: str | None) -> str | None:
        return _name(value)


class MapPlacePatch(BaseModel):
    name_ar: str | None = Field(default=None, min_length=2, max_length=80)
    name_en: str | None = Field(default=None, max_length=80)
    category: Category | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    is_hidden: bool | None = None

    @field_validator("name_ar")
    @classmethod
    def _clean_ar(cls, value: str | None) -> str | None:
        return _required(value)

    @field_validator("name_en")
    @classmethod
    def _clean_en(cls, value: str | None) -> str | None:
        return _name(value)


class MapPlaceAdminOut(BaseModel):
    id: uuid.UUID
    country_code: CountryCode
    name_ar: str
    name_en: str | None
    category: str
    lat: float
    lng: float
    is_hidden: bool
    #: **`owner` أو `osm`** — والمستوردُ يحمل أصلَه (`osm_ref`) ليُراجع
    source: str
    osm_ref: str | None
    created_at: datetime
    updated_at: datetime


class MapPlaceOut(BaseModel):
    """**ما يرسمه التطبيقان ويبحثان فيه** — والمطارُ منه بفئة `airport` يُقرأ من بيته (`facilities`). **ولا إخفاءَ في الحمولة**:
    المخفيُّ لا يخرج أصلاً. و`source` يفرّق «من المالك» عن «مرفقٌ برسم» للعرض وحدَه."""

    id: uuid.UUID
    name_ar: str
    name_en: str | None
    category: str
    lat: float
    lng: float
    source: Literal["place", "facility"]
    #: **بالمتر من نقطة البحث** — في البحث وحدَه، و`None` حين لا نقطة
    distance_m: int | None = None
