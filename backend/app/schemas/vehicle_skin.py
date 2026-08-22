"""عقدُ مركبات الكراج والمتجر — **مجمَّدٌ قبل التوزيع** (2026-08-22).

**ولمَ يُجمَّد أولاً**: أربعةُ وكلاءَ يعملون متوازين، فلو تُرك الشكلُ ليُكتشف
لكتب كلٌّ منهم ما يظنّه — وهو **الشكلُ الثامن** (بابان ينشران الشيءَ نفسَه
ويفترقان) قبل أن يُكتب سطرٌ واحد. فالعقدُ هنا مرجعٌ واحد، ومن يحتاج تعديلَه
**يقف عند المنسّق** ولا يعدّله في مكانه.

**والمالُ سلاسلُ نصّ**: `MONEY` يُسلسَل `"3.000"` — و§14 تمنع تمريرَه بـ`Number`
في التطبيقات. **والصفرُ يُكوَّن مُكمَّماً** (`round_money`) وإلا خرج `"0"` لا
`"0.000"` — الشكلُ السابع، وقع ثلاث مرّاتٍ في هذا المشروع.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated

from app.models.enums import CountryCode

Rarity = Literal["common", "premium", "rare", "legendary"]
AcquireSource = Literal["gift", "purchase", "grant"]

#: **سببُ عدمِ إمكان الشراء** — واحدٌ لا أكثر، وأولُ ما ينطبق بترتيب الأسبقية:
#: مملوكةٌ ← نفدت ← مقفولةٌ بالمستوى ← خارج الموسم ← رصيدٌ غيرُ كافٍ.
#: **والترتيبُ جزءٌ من العقد** لأن شاشتين ترتّبانه اختلافاً تقولان لكبتنٍ
#: واحدٍ سببين لرفضٍ واحد.
BlockedReason = Literal[
    "owned", "sold_out", "level_locked", "out_of_season", "insufficient_balance"
]


class SkinOut(BaseModel):
    """مركبةٌ كما يراها الكبتنُ في المتجر أو الكراج."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    rarity: Rarity
    #: مسارُ الرسمة الكبيرة والعلويّة — **نسبيّان**، يبنيهما التطبيقُ على أصله
    store_image_url: str
    map_image_url: str
    map_scale_percent: int
    map_rotates: bool
    #: **أين تُراها** — يُكتب في بطاقة المتجر نصّاً: من يدفع يعرف ما يشتري
    visible_before_accept: bool

    #: `null` غيرُ معروضةٍ للبيع (العادية تُوهب ولا تُباع)
    price: Decimal | None = None
    currency: str | None = None

    #: `null` بلا حدّ — و`0` نفدت
    remaining: int | None = None
    #: **عدّادُ الاقتناء الحيّ** عبر المنصّة
    owners_count: int = 0
    level_required: int | None = None

    valid_until: datetime | None = None

    owned: bool = False
    active: bool = False
    blocked_reason: BlockedReason | None = None


class GarageOut(BaseModel):
    """كراجُ الكبتن — **ومعه ما يحتاجه الكراجُ نفسُه** بنداءٍ واحد."""

    skins: list[SkinOut]
    active_skin_id: uuid.UUID | None = None
    #: **مركبةٌ وُهبت ولم تُعرض ورقتُها بعد** — تُعرض مرةً ثم تُختم
    celebrate: SkinOut | None = None
    #: **لا اشتراكَ له**: الكراجُ يقول ذلك ليُرسم البديلُ الباهتُ ويظهر الزرّ
    has_subscription: bool = True


class StoreOut(BaseModel):
    """المتجرُ مقسوماً بندرته — والترتيبُ عقدٌ لا ذوق."""

    skins: list[SkinOut]
    balance: Decimal
    currency: str
    driver_level: int | None = None


class ActivateSkinIn(BaseModel):
    skin_id: uuid.UUID


class BuySkinOut(BaseModel):
    """ما يُعرض بعد الشراء — **الرصيدُ الجديدُ من الدفتر لا محسوباً في الشاشة**."""

    skin: SkinOut
    balance_after: Decimal
    currency: str


# --------------------------------------------------------------- أبوابُ اللوحة


class SkinPriceIn(BaseModel):
    country_code: CountryCode
    price: Annotated[Decimal, Field(gt=0)]


class SkinCreateIn(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=64)]
    rarity: Rarity
    prices: list[SkinPriceIn] = []
    max_supply: Annotated[int, Field(gt=0)] | None = None
    level_required: Annotated[int, Field(gt=0)] | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    is_gift: bool = False
    is_feminine: bool = False
    feminine_drivers_only: bool = False
    #: **يُصرَّح ولا يُستنتج من الندرة** — التفصيل في `models/vehicle_skin.py`
    visible_before_accept: bool = True
    map_rotates: bool = True
    map_scale_percent: Annotated[int, Field(ge=80, le=120)] = 100
    is_active: bool = True


class SkinUpdateIn(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=64)] | None = None
    prices: list[SkinPriceIn] | None = None
    max_supply: Annotated[int, Field(gt=0)] | None = None
    level_required: Annotated[int, Field(gt=0)] | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    visible_before_accept: bool | None = None
    map_rotates: bool | None = None
    map_scale_percent: Annotated[int, Field(ge=80, le=120)] | None = None
    is_feminine: bool | None = None
    feminine_drivers_only: bool | None = None
    is_active: bool | None = None


class AdminSkinOut(BaseModel):
    """صفُّ الكتالوج كما تراه اللوحة — **بحاله لا مصفّى بسوق**."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    rarity: Rarity
    store_image_url: str
    map_image_url: str
    map_scale_percent: int
    map_rotates: bool
    visible_before_accept: bool
    max_supply: int | None
    level_required: int | None
    valid_from: datetime | None
    valid_until: datetime | None
    is_gift: bool
    is_public_default: bool
    is_feminine: bool
    feminine_drivers_only: bool
    is_active: bool
    prices: list[SkinPriceIn] = []
    owners_count: int = 0
    #: **مبيعاتٌ وإيراد** — مجموعان في الخلفية كقاعدة §14
    sold_count: int = 0
    revenue: dict[str, Decimal] = {}


class SkinStatsOut(BaseModel):
    """إحصاءُ المتجر — **الأكثرُ مبيعاً والإيرادُ الكلي**، مجموعَين في القاعدة."""

    top_selling: list[AdminSkinOut]
    revenue_by_currency: dict[str, Decimal]
    total_owned: int
