"""فئاتُ الرحلة (SPEC §٦٧) — **المفتاحُ نوعٌ واحدٌ في كلِّ باب**، والفئةُ كما تُنشر للتطبيقين وكما تُكتب من اللوحة."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode, VehicleBodyType, VehicleFuel

#: **أيقوناتُ الفئة** — **من قائمةٍ لا نصٌّ حرّ**: خطُّ الأيقونات مقتطَعٌ بأسمائه في التطبيقين (`index.html`)، واسمٌ خارجه يُرسم نصّاً
CategoryIcon = Literal["local_taxi", "directions_car", "airport_shuttle", "electric_car", "diamond", "accessible"]

#: **مفتاحُ فئة الرحلة** — `economy` · `comfort` · أو مفتاحُ فئةٍ أضافها المشرف (لاتينيٌّ صغير). **والخدمةُ تفحص أنه مطلوبٌ في السوق**
CategoryKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,31}$", max_length=32)]


class RideCategoryPublic(BaseModel):
    """**ما يراه التطبيقان** في `/config` — الاسمُ والأيقونةُ والوصفُ والمقاعد، بترتيب السوق."""

    key: str
    name: str
    icon: str
    description: str | None = None
    seats: int


class RideCategoryOut(RideCategoryPublic):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    sort_order: int
    is_active: bool
    is_builtin: bool
    allowed_body_types: list[str]
    allowed_fuels: list[str]
    min_year: int | None
    min_seats: int | None


class RideCategoryCreate(BaseModel):
    country_code: CountryCode
    key: CategoryKey
    name: str = Field(min_length=2, max_length=40)
    icon: CategoryIcon = "local_taxi"
    description: str | None = Field(default=None, max_length=120)
    seats: int = Field(default=4, ge=1, le=20)
    #: **بعد المدمجتين افتراضاً** (ترتيبُهما ٠ و١)
    sort_order: int = Field(default=10, ge=0, le=100)
    allowed_body_types: list[VehicleBodyType] = Field(default_factory=list)
    allowed_fuels: list[VehicleFuel] = Field(default_factory=list)
    min_year: int | None = Field(default=None, ge=1990, le=2100)
    min_seats: int | None = Field(default=None, ge=1, le=20)


class RideCategoryUpdate(BaseModel):
    """**كلُّ شيءٍ إلا المفتاحَ والدولة** — المفتاحُ مكتوبٌ على الرحلات والأسعار فلا يتغيّر."""

    name: str | None = Field(default=None, min_length=2, max_length=40)
    icon: CategoryIcon | None = None
    description: str | None = Field(default=None, max_length=120)
    seats: int | None = Field(default=None, ge=1, le=20)
    sort_order: int | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
    allowed_body_types: list[VehicleBodyType] | None = None
    allowed_fuels: list[VehicleFuel] | None = None
    min_year: int | None = Field(default=None, ge=1990, le=2100)
    min_seats: int | None = Field(default=None, ge=1, le=20)


class CategoryAccessIn(BaseModel):
    """**منحٌ أو نزعٌ لكبتن** — `granted = null` يرفع ما قرّره المشرفُ فتعود قاعدةُ الشروط وحدَها."""

    driver_id: uuid.UUID
    granted: bool | None
    reason: str = Field(min_length=4, max_length=280)


class CategoryAccessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver_id: uuid.UUID
    driver_name: str | None = None
    driver_phone: str | None = None
    granted: bool
    reason: str | None


class VehicleAttributesIn(BaseModel):
    """**صفاتُ المركبة** يضعها المشرفُ في مراجعتها (§٦٧-ج/٥) — `null` يمحو الصفة."""

    body_type: VehicleBodyType | None = None
    fuel: VehicleFuel | None = None
    seats: int | None = Field(default=None, ge=1, le=20)
