"""مخطّطاتُ البلاطات واللافتات — الترحيلة `0063`."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BannerLinkKind, CampaignAudience, CountryCode, ServiceTileStatus


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


class StorefrontOut(BaseModel):
    """**نداءٌ واحدٌ لشاشةٍ واحدة** — البلاطاتُ واللافتاتُ معاً.

    **وندءان يعنيان شاشةً تُرسم على مرحلتين**: البلاطاتُ تظهر ثم تقفز
    اللافتةُ فوقها، **وهو ارتجافٌ يراه المستخدمُ عطباً**.
    """

    tiles: list[ServiceTileOut]
    banners: list[PromoBannerOut]


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
