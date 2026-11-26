"""حمولاتُ سجلِّ الإصدارات — **البند ٨ (§39٫٨، §43)**.

**والقرارُ يُحسب في الخلفية لا في التطبيقات**: `state` تخرج محسوبةً
(`ok`/`optional`/`forced`) — **وثلاثةُ تطبيقاتٍ تقارن رقمين بأنفسها ثلاثةُ
نسخٍ من قاعدةٍ واحدة**، تفترق أوّلَ ما تتغيّر. وهي قاعدةُ §14 مطبَّقةً على
حكمٍ لا على مبلغ، كما طُبِّقت على `SettlementState` و`LiveDriverOut.state`.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.app_release import MAX_REMINDER_HOURS
from app.models.enums import ClientApp, ReleasePlatform, ReleaseSource


class AppReleaseIn(BaseModel):
    """إنشاءُ إصدارٍ أو تعديلُه — **ومعه إقرارُ الحجب حين يرتفع الحدّ**."""

    app: ClientApp
    #: **أندرويد افتراضاً** — وكلُّ صفٍّ قبل 2026-10-12 أندرويد. ولا يُعدَّل في
    #: صفٍّ قائم كما لا يُعدَّل رقمُه: هو هويةُ الحزمة معه
    platform: ReleasePlatform = ReleasePlatform.ANDROID
    #: **المتجر** (٢٠٢٦-١١-٢٠) — `default` افتراضاً: Google Play والموقع، وهو كلُّ صفٍّ قبله. ولا يُعدَّل في صفٍّ قائم
    source: ReleaseSource = ReleaseSource.DEFAULT
    build: int = Field(ge=1)
    min_supported_build: int = Field(ge=1)
    #: **يُفحص قبل الحفظ** — `HttpUrl` تحرس الشكل، والخدمةُ تطرق الباب
    download_url: HttpUrl
    release_notes: str = Field(min_length=1, max_length=4000)
    #: **0 = «في كلِّ فتح»** (٢٠٢٦-١١-٢٦) — «لاحقاً» يكتم التنبيهَ في الفتح نفسِه ويعود في الإقلاع التالي
    reminder_hours: int = Field(default=24, ge=0, le=MAX_REMINDER_HOURS)
    #: **حدٌّ أدنى لكلِّ دولة** يحلّ محلَّ العامِّ فيها — `{"JO": 1573}`؛ فارغٌ = العامُّ في كلِّ الدول
    country_min_builds: dict[str, int] = Field(default_factory=dict)
    #: **إقرارُ رفعِ حدِّ دولة** — كالعامّ: رقمُها مكتوباً ثانيةً لكلِّ دولةٍ يرتفع حدُّها
    confirm_country_min_builds: dict[str, int] | None = None
    #: **أدنى غلافٍ تُرسم فيه الخريطةُ المفتوحة** — فارغٌ = لا غلافَ (SPEC §١٠٥/٥)
    open_map_min_build: int | None = Field(default=None, ge=1)
    #: **الإذنُ الثاني، مبنيٌّ في العقد لا في الشاشة** (§39٫٨: «يستأذن
    #: مرّتين»): حين يرتفع الحدُّ عمّا هو قائم **يُطلب رقمُه مكتوباً ثانيةً**.
    #: وإخفاءُ ورقةٍ في الواجهة راحةٌ، **وحقلٌ يجب أن يساوي الرقمَ شرط**.
    confirm_min_supported_build: int | None = None

    @field_validator("country_min_builds")
    @classmethod
    def _country_codes(cls, value: dict[str, int]) -> dict[str, int]:
        out: dict[str, int] = {}
        for code, build in value.items():
            key = code.strip().upper()
            if not re.fullmatch(r"[A-Z]{2}", key):
                raise ValueError("رمزُ الدولة حرفان لاتينيّان (JO · LY · DZ)")
            if build < 1:
                raise ValueError("حدُّ الدولة رقمٌ موجب")
            out[key] = build
        return out


class AppReleaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    app: ClientApp
    platform: ReleasePlatform
    source: ReleaseSource
    build: int
    min_supported_build: int
    download_url: str
    release_notes: str
    reminder_hours: int
    open_map_min_build: int | None = None
    country_min_builds: dict[str, int] = Field(default_factory=dict)
    #: **أهذا هو الصفُّ الحاكم؟** — أعلى رقمٍ للتطبيق. **ويُحسب في الخلفية**:
    #: لوحةٌ تحسبه بفرزها هي تخالف الخادمَ أوّلَ صفحةٍ مقصوصة
    is_current: bool
    created_at: datetime
    updated_at: datetime


class AppVersionOut(BaseModel):
    """جوابُ التطبيق عند الإقلاع — **والحكمُ محسوبٌ هنا**.

    **و`ok` مع حقولٍ فارغةٍ تعني «لا سجلَّ لهذا التطبيق»** — لا «كلُّ النسخ
    مقبولة» ولا «مرفوضة». **وغيابُ السجلِّ لا يقفل أحداً.**
    """

    state: Literal["ok", "optional", "forced"]
    latest_build: int | None = None
    min_supported_build: int | None = None
    download_url: str | None = None
    release_notes: str | None = None
    reminder_hours: int | None = None
    #: **أيُرسم MapLibre في هذا الغلاف؟** — محسوبٌ هنا من رقم الحزمة وحدِّ الصفِّ الحاكم (SPEC §١٠٥/٥).
    #: **ولا يُشعل الخريطةَ وحدَه**: مفتاحُ `open_map_display` للسوق شرطٌ ثانٍ في التطبيق.
    open_map: bool = False
