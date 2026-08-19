"""مخططاتُ عروض الاشتراكات (البند ٥٤).

**والنوعُ يُحرس هنا لا في القاعدة**: العمودُ `VARCHAR(16)` عمداً ليصير إضافةُ
نوعٍ زمنيٍّ كوداً بلا ترحيلة، وهذا هو الموضعُ الذي يمنع قيمةً مخترعة — نفسُ
قسمة `feature_flags.feature_key`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import CountryCode

DiscountType = Literal["money_percent"]
Audience = Literal["all", "new_driver", "lapsed", "manual"]


class OfferIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    discount_type: DiscountType = "money_percent"
    # نسبةٌ بين صفرٍ ومئة — والحدُّ هنا وفي القاعدة معاً
    discount_value: Decimal = Field(gt=0, le=100)
    max_discount: Decimal | None = Field(default=None, ge=0)
    plan_id: uuid.UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    audience: Audience = "all"
    lapsed_days: int | None = Field(default=None, gt=0, le=3650)
    # **صفرٌ يعني بلا حدّ، ويُكتب صراحةً** — كأصفار `wallet_settings`
    max_uses_per_driver: int = Field(default=1, ge=0, le=100)
    total_budget: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check(self) -> "OfferIn":
        if self.audience == "lapsed" and self.lapsed_days is None:
            raise ValueError("جمهور «المنقطعون» يحتاج عددَ أيام الانقطاع")
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("نهاية العرض قبل بدايته")
        return self


class OfferUpdate(BaseModel):
    """تعديلٌ جزئي — **والإطفاءُ تعديلٌ لا حذف**: عرضٌ يُحذف بعد أن اشترى به
    عشرون كبتناً يمحو سببَ خصومهم فيبقى المبلغُ رقماً بلا اسم."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    discount_value: Decimal | None = Field(default=None, gt=0, le=100)
    max_discount: Decimal | None = Field(default=None, ge=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    max_uses_per_driver: int | None = Field(default=None, ge=0, le=100)
    total_budget: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class OfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    name: str
    discount_type: str
    discount_value: Decimal
    max_discount: Decimal | None
    plan_id: uuid.UUID | None
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    audience: str
    lapsed_days: int | None
    max_uses_per_driver: int
    total_budget: Decimal | None
    created_at: datetime

    # ------------------------------------------------ جدولُ التنازل
    # **يُحسب في الخلفية** (§14): مجموعٌ على كل الصفوف، وقسمتُه في المتصفح
    # تعطي «متوسطَ الصفحة» تحت عنوانٍ يقول «الكلّ»
    subscriptions_sold: int = 0
    total_list_price: Decimal = Decimal("0.000")
    total_given_up: Decimal = Decimal("0.000")
    # **عددُ ما خالف فيه المشرفُ المبلغَ المعبَّأ** — مقارنةٌ حيّةٌ بين رقمين
    # مجمَّدين، لا عمودٌ يُخزَّن
    manual_adjustments: int = 0


class GrantIn(BaseModel):
    driver_id: uuid.UUID
    note: str | None = Field(default=None, max_length=500)


class GrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    offer_id: uuid.UUID
    driver_id: uuid.UUID
    driver_name: str | None = None
    note: str | None
    created_at: datetime
