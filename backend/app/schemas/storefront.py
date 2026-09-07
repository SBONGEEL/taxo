"""مخطّطاتُ البلاطات واللافتات — الترحيلة `0063`."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    BannerLinkKind,
    CampaignAudience,
    CountryCode,
    Currency,
    ServiceTileStatus,
)


class ServiceTileOut(BaseModel):
    """ما يقرؤه التطبيق — **و`is_new` محسوبةٌ في الخلفية لا في الشاشة**.

    **وساعةُ الجهاز يملكها صاحبُه**: شارةٌ تُحسب في التطبيق تبقى لمن أخّر
    ساعتَه — فالخلفيةُ هي الساعة.
    """

    id: uuid.UUID
    key: str
    title: str
    subtitle: str | None = None
    icon: str
    status: ServiceTileStatus
    #: `null` مع `soon` — و«قريباً» **تُقرأ ولا تُنقر**
    destination: str | None = None
    is_new: bool


class PromoBannerOut(BaseModel):
    """لافتةٌ حيّةٌ الآن — **والنافذةُ قيست في الخلفية قبل الإرسال**."""

    id: uuid.UUID
    title: str
    body: str | None = None
    icon: str | None = None
    link_kind: BannerLinkKind
    link: str | None = None


class StorefrontOfferOut(BaseModel):
    """عرضُ اشتراكٍ لبطاقة الرئيسة — **بالرقم، وهو الفرقُ عن الصفحة**.

    ## ولمَ ليست `LandingOfferOut` وسؤالُهما واحد

    **الشكلان يجيبان «أيُّ عرضٍ قائم» ويفترقان في من يسأل**، و§52٫3 حسمت
    الصفحة: **«لا يخرج سعرٌ ولا سعرٌ مشطوبٌ من أيِّ بابٍ تقرأه الصفحة»** —
    فنُزعت `price` و`price_after` و`currency` من حمولة الصفحة **نزعاً من
    الباب لا من الرسم**.

    **وهذا بابٌ آخرُ لسائلٍ آخر**: كبتنٌ داخلٌ بجلسته يسأل عن **اشتراكه هو**،
    **وشاشةُ `/subscription` تعرض له الرقمَ نفسَه والسعرَ المشطوبَ منذ البند
    ٥٤** — فبطاقةٌ تقول «عرض» بلا رقمٍ **تدفعه ليضغط ليعرف**، وهي إعلانٌ لا
    خبر.

    **فتوحيدُ الشكلين يُسقط أحدَ الشرطين حتماً**: إمّا يخرج السعرُ إلى الصفحة
    العامة، أو يُحجب عن صاحبه. **وشكلان بعلّتين ليسا نسختين** — والنسخةُ ما
    كان لها سببٌ واحد.
    """

    #: **اسمُ العرض كما كتبه المشرف** — لا جملةٌ مؤلَّفةٌ في الشيفرة.
    name: str
    plan_name: str
    price: Decimal
    #: **بعد الخصم — محسوباً في الخلفية** (§14)، والشاشةُ تعرض ولا تطرح.
    price_after: Decimal
    currency: Currency
    #: **مجاناً تماماً — تُقال بكلمةٍ لا برقمٍ صفر**: «0.000» تُقرأ عطباً في
    #: السعر لا هديّة.
    free: bool


class StorefrontOut(BaseModel):
    """**نداءٌ واحدٌ لشاشةٍ واحدة** — البلاطاتُ واللافتاتُ والعرضُ معاً.

    **وندءان يعنيان شاشةً تُرسم على مرحلتين**: البلاطاتُ تظهر ثم تقفز
    اللافتةُ فوقها، **وهو ارتجافٌ يراه المستخدمُ عطباً**.
    """

    tiles: list[ServiceTileOut]
    banners: list[PromoBannerOut]
    #: **عرضُ اشتراكِ هذا الكبتن — في الصندوق نفسِه لا في كيانٍ ثانٍ**
    #: (قرارُ المالك 2026-09-07).
    #:
    #: **ولمَ حقلٌ مستقلٌّ لا صفُّ لافتةٍ مصنوع**: اللافتةُ صفٌّ يملكه المشرف
    #: — يُنشئه ويُطفئه ويكتب نصَّه؛ **والعرضُ يُحسب لكلِّ كبتنٍ على حدة**
    #: بجمهوره وحدِّه وميزانيته. **وصفٌّ مصنوعٌ آلياً في `promo_banners`**
    #: يعني جدولاً نصفُه بيدٍ ونصفُه بآلة، **يراه المشرفُ فيحرّره فيُمحى في
    #: الدورة التالية** — وهو «بيتان لحقيقةٍ واحدة» بعينه.
    #:
    #: **و`null` للراكب دائماً**: الاشتراكُ للكبتن وحدَه — والحقلُ مُصرَّحٌ في
    #: التطبيقين لأن الصندوقَ مكوّنٌ واحدٌ متطابقٌ بايتاً، **ونسختان تفترقان
    #: أوّلَ تعديل**.
    offer: StorefrontOfferOut | None = None


class ServiceTileIn(BaseModel):
    """**والمقصدُ يُتحقَّق من بنائه في الخدمة لا هنا** — القائمةُ بيتُها واحد."""

    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    key: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=1, max_length=60)
    subtitle: str | None = Field(default=None, max_length=80)
    icon: str = Field(min_length=1, max_length=40)
    audience: CampaignAudience
    sort_order: int = Field(default=0, ge=0, le=999)
    destination: str | None = Field(default=None, max_length=60)
    status: ServiceTileStatus = ServiceTileStatus.HIDDEN
    #: **مدّةُ شارة «جديد»** — و`null` تعني بلا شارة
    new_until: date | None = None


class ServiceTilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=60)
    subtitle: str | None = Field(default=None, max_length=80)
    icon: str | None = Field(default=None, min_length=1, max_length=40)
    audience: CampaignAudience | None = None
    sort_order: int | None = Field(default=None, ge=0, le=999)
    destination: str | None = Field(default=None, max_length=60)
    status: ServiceTileStatus | None = None
    new_until: date | None = None


class AdminServiceTileOut(BaseModel):
    """**وفيها `first_shown_at`** — واللوحةُ تقرؤها لتعرف ما يُحذف وما يُخفى.

    **وليست بيتاً ثانياً للحقيقة**: هي العمودُ نفسُه يُنشر، لا حقلٌ محسوبٌ
    يقول ما يقوله غيرُه. **ولمَ تُنشر أصلاً**: زرٌّ يعمل ثم يرتدّ **يعلّم
    المشرفَ أن يعيد المحاولة**، وزرٌّ معطَّلٌ يقول لمَ يعلّمه أن يُخفي بدلَه.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    key: str
    title: str
    subtitle: str | None = None
    icon: str
    audience: CampaignAudience
    sort_order: int
    destination: str | None = None
    status: ServiceTileStatus
    new_until: date | None = None
    #: **فارغةٌ تعني مسوّدةً لم يرَها إنسان** — وهي وحدَها ما يُحذف
    first_shown_at: datetime | None = None


class PromoBannerIn(BaseModel):
    """**والنافذةُ إلزاميّةٌ في العقد كما هي في القاعدة** — طبقتان لا واحدة."""

    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    title: str = Field(min_length=1, max_length=80)
    body: str | None = Field(default=None, max_length=160)
    icon: str | None = Field(default=None, max_length=40)
    audience: CampaignAudience
    sort_order: int = Field(default=0, ge=0, le=999)
    starts_at: datetime
    #: **بلا افتراضٍ ولا `None`**: «لافتةٌ بلا مدّةِ انتهاءٍ لا تُقبل»
    ends_at: datetime
    link_kind: BannerLinkKind = BannerLinkKind.NONE
    link: str | None = Field(default=None, max_length=300)
    is_active: bool = True


class PromoBannerPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=80)
    body: str | None = Field(default=None, max_length=160)
    icon: str | None = Field(default=None, max_length=40)
    audience: CampaignAudience | None = None
    sort_order: int | None = Field(default=None, ge=0, le=999)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    link_kind: BannerLinkKind | None = None
    link: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None


class AdminPromoBannerOut(BaseModel):
    """**ولا حقلَ `has_image`** — الطلبُ نفسُه هو الجواب (بايتاتٌ أو ٤٠٤).

    **وحقلٌ يقول «لها صورة» بيتٌ ثانٍ للحقيقة** يفترق عن الملفّ أوّلَ رفعٍ
    أو نزع — وهي قاعدةُ `DriverAvatar` نفسُها.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    country_code: CountryCode
    title: str
    body: str | None = None
    icon: str | None = None
    audience: CampaignAudience
    sort_order: int
    starts_at: datetime
    ends_at: datetime
    link_kind: BannerLinkKind
    link: str | None = None
    is_active: bool
    #: **أوّلُ إشعالٍ داخل نافذتها** — و`null` مسوّدةٌ تُحذف
    first_shown_at: datetime | None = None
