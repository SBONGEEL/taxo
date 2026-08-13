"""مخطّطاتُ مشاركة الرحلة (SPEC §5.12، المرحلة 12-ي)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import CountryCode


class RideSharingSettingsIn(BaseModel):
    """ما يعدّله المشرف per-country — و`None` تعني «لا تمسّ هذا الحقل».

    **والصفرُ في النسبة قرارٌ صريحٌ لا فراغ**: يُقرأ «لم تُقرَّر بعد» فيُخفي
    الميزةَ كلَّها ولو كان مفتاحُها مشتعلاً — كما يفعل صفرُ مبلغ البقشيش وصفرُ
    مكافأة الإحالة. فهو الطريقُ الصحيحُ لإطفائها بلا نقاشٍ في المفتاح.
    """

    discount_percent: Decimal | None = Field(default=None, ge=0, le=100)
    # الحدودُ العليا عمليةٌ لا شكلية: ممرٌّ بخمسين كيلومتراً يجعل المطابقةَ
    # تسأل Mapbox عن رحلاتٍ في مدينةٍ أخرى، وسقفُ التفافٍ بساعةٍ يجعل من قَبِل
    # أولاً يدفع ثمنَ خصمِ غيره من وقته
    corridor_km: Decimal | None = Field(default=None, ge=0, le=50)
    max_detour_minutes: int | None = Field(default=None, ge=0, le=60)
    partner_wait_seconds: int | None = Field(default=None, ge=0, le=900)


class RideSharingSettingsOut(BaseModel):
    country_code: CountryCode
    discount_percent: Decimal
    corridor_km: Decimal
    max_detour_minutes: int
    partner_wait_seconds: int
