"""مخطّطاتُ المهامِّ والمستوياتِ والشارات (البند ٥٣)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import CountryCode
from app.models.mission import normalize_metric


class MissionOut(BaseModel):
    """مهمّةٌ كما تُعرض — **والهدفُ بمقياس معياره**.

    العمودُ `NUMERIC(12,3)` يُسلسَل «40.000»، فيقرأ المشرفُ «٤٠٫٠٠٠ رحلة» وكأنها
    أربعون ألفاً بفاصلة. **وموضعُ التطبيع هنا لا في كل شاشة**: ثلاثةُ قرّاء
    (اللوحة، شاشةُ الكبتن، وأيُّ ثالثٍ لاحقاً) ينسخون التنسيقَ ثلاثَ مرات
    ويفترق أحدُها — وهو الشكلُ نفسُه الذي أخرج «٠ د.أ» بجانب «٥٫٠٠٠ د.أ».
    """

    id: uuid.UUID
    country_code: CountryCode
    month: date
    title: str
    description: str | None = None
    metric: str
    target: Decimal
    is_active: bool

    @model_validator(mode="after")
    def _scale_target(self) -> "MissionOut":
        object.__setattr__(
            self, "target", normalize_metric(self.metric, self.target)
        )
        return self


class MissionIn(BaseModel):
    month: date
    title: str = Field(min_length=2, max_length=120)
    description: str | None = None
    metric: str
    target: Decimal = Field(gt=0)


class MissionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = None
    target: Decimal | None = Field(default=None, gt=0)
    is_active: bool | None = None


class MissionProgressOut(BaseModel):
    """**حقائقُ لا جملةُ حالة** — «أكملتَ ٢٧ من ٤٠» تبنيها الشاشة."""

    mission: MissionOut
    value: Decimal
    target: Decimal
    done: bool


class BadgeOut(BaseModel):
    id: uuid.UUID
    key: str
    label: str
    description: str | None = None
    icon: str | None = None
    is_active: bool


class GrantedBadgeOut(BaseModel):
    badge: BadgeOut
    granted_at: datetime
    # **ولا يصل `note` الكبتنَ**: سببُ المنح كلامُ مشرفٍ لمشرف، وتحويلُه رسالةً
    # لصاحبه يجعل حكماً إدارياً خطاباً — قاعدةُ سبب سحب الوضع النسائي نفسُها


class MyProgressOut(BaseModel):
    """شاشةُ الكبتن: مهامُّه ومستواه وشاراتُه.

    **و`level_effect_meters` يُقال بصدق أو لا يُقال**: «يقرّبك من الطلبات القريبة
    قليلاً» — لا «أولويةٌ في الطلبات» التي يقرؤها وعداً بطلباتٍ أكثر ثم يعدّها
    ولا يجدها. فالرقمُ يُنشر ليكون النصُّ مقيساً لا موعوداً.
    """

    enabled: bool
    level: int
    max_level: int
    level_computed_at: datetime | None = None
    level_effect_meters: int
    # كم مهمّةً أنجز من كم — وهو ما يُبنى منه «ما يلزم للمستوى التالي»
    missions_done: int
    missions_total: int
    missions: list[MissionProgressOut]
    badges: list[GrantedBadgeOut]


class LevelSettingOut(BaseModel):
    country_code: CountryCode
    level: int
    discount_meters: int


class LevelSettingIn(BaseModel):
    # **الحدُّ هنا وفي الخدمة وفي القاعدة**: قرارُ المالك «١٠٠م» يُحرس في
    # الطبقات الثلاث، فطبقةٌ تُتخطّى لا تفتح الباب
    discount_meters: int = Field(ge=0, le=100)


class LevelOverviewOut(BaseModel):
    """جدولُ اللوحة: كم كبتناً في كل مستوى، ومتى حُسب."""

    country_code: CountryCode
    enabled: bool
    counts: dict[int, int]
    settings: list[LevelSettingOut]
    last_computed_at: datetime | None = None


class BadgeIn(BaseModel):
    key: str = Field(min_length=2, max_length=48)
    label: str = Field(min_length=2, max_length=120)
    description: str | None = None
    icon: str | None = None


class BadgeGrantIn(BaseModel):
    badge_id: uuid.UUID
    # **سببٌ مكتوبٌ شرطٌ لا حقلٌ اختياري** — وهو القيمةُ الوحيدة التي يحملها
    # قيدُ التدقيق هنا، فبغيرها يسجّل القيدُ أن شيئاً حدث ولا يقول ماذا
    note: str = Field(min_length=3, max_length=500)


class BadgeRevokeIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
