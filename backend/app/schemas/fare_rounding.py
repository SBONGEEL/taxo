"""مخطّطاتُ «تقريب الأسعار وعرضها» (أمرُ المالك ٢٠٢٦-١١-١٩) — `services/fare_rounding.py`."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import CountryCode, RoundingMode


class FareRoundingIn(BaseModel):
    """**القيمُ كاملةً** — لا حقلَ ناقص: صفحةٌ واحدةٌ تحفظ ما تراه كلَّه."""

    decimals: int = Field(ge=0, le=3)
    #: `null` = بلا تقريب (دقيق)
    step: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    mode: RoundingMode = RoundingMode.NEAREST
    on_estimate: bool
    on_final: bool
    on_negotiation: bool
    on_cancellation: bool


class FareRoundingOut(FareRoundingIn):
    country_code: CountryCode
    currency: str
    currency_decimals: int


class FareRoundingPreviewIn(FareRoundingIn):
    #: مبلغٌ يكتبه المشرفُ ليرى ناتجَه
    amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)


class FareRoundingAmountOut(BaseModel):
    amount: Decimal
    after: Decimal
    after_text: str


class FareRoundingSampleOut(BaseModel):
    distance_km: Decimal
    duration_min: Decimal
    precise: Decimal
    before: Decimal
    after: Decimal
    before_text: str
    after_text: str


class FareRoundingPreviewOut(BaseModel):
    #: جملةُ منع الحفظ إن لم تلائم الخاناتُ الخطوة — و`null` إن لاءمت
    fit_error: str | None
    vehicle_category: str | None
    amount: FareRoundingAmountOut | None
    samples: list[FareRoundingSampleOut]
