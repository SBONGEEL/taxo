"""صفحةُ «الدول» ومفتاحُ الحدود في اللوحة (SPEC §٧٤-أ/٢–٣)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CountryCode, MarketStatus, SignupDisplay, UserRole


class MarketRow(BaseModel):
    country_code: CountryCode
    name: str
    status: MarketStatus
    #: **ظهورُ المغلقة في التسجيل** كما اختاره المالك — والمفتوحةُ تحمله أيضاً لأنه يحكم يومَ تُغلق
    signup_display: SignupDisplay
    #: **ما ينقص للفتح** — فارغةٌ = جاهزة. تُحسب عند كلِّ قراءةٍ ولا تُخزَّن
    readiness: list[str]
    #: **رحلاتٌ جارية الآن** — تكتمل إن أُغلق السوق؛ والعددُ يُرى قبل الضغط
    active_rides: int
    currency: str
    currency_label: str


class AllowanceRow(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str | None
    phone: str | None
    role: UserRole
    country_code: CountryCode
    is_test: bool
    reason: str
    granted_at: datetime
    granted_by_name: str | None


class MarketsOut(BaseModel):
    countries: list[MarketRow]
    borders_enforced: bool
    allowances: list[AllowanceRow]


class MarketStatusIn(BaseModel):
    open: bool
    #: **الفتحُ رغم النقص**: `force` ومعه سببٌ مكتوب — ويُرفض بلاه
    force: bool = False
    reason: str | None = Field(default=None, max_length=300)


class SignupDisplayIn(BaseModel):
    display: SignupDisplay


class BordersIn(BaseModel):
    enforced: bool
    #: **إلزاميٌّ للرفع** (8 أحرف) — إسقاطُ حدٍّ بقرارٍ يُسأل عنه بعد شهر
    reason: str | None = Field(default=None, max_length=300)


class AllowanceIn(BaseModel):
    """**بالمعرّف أو بالهاتف** — اللوحةُ تختار الحسابَ من بحثها، أو يُكتب رقمُه بدولته."""

    user_id: uuid.UUID | None = None
    phone: str | None = Field(default=None, max_length=32)
    country_code: CountryCode | None = None
    reason: str = Field(min_length=3, max_length=200)
