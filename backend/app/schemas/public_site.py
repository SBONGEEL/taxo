"""حمولةُ الصفحة التعريفية — **ولا حقلَ فيها يخصّ شخصاً**."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import Currency


class LandingOfferOut(BaseModel):
    """عرضٌ عامٌّ قائم — بمبلغه محسوباً في الخلفية (§14)."""

    name: str
    plan_name: str
    price: Decimal
    price_after: Decimal
    currency: Currency
    #: مجاناً تماماً — تُقال بكلمةٍ لا برقمٍ صفر.
    free: bool


class LandingOut(BaseModel):
    """**و`None` تعني لا سطرَ عرضٍ على الصفحة** — حالٌ صحيحةٌ لا خطأ."""

    offer: LandingOfferOut | None = None
