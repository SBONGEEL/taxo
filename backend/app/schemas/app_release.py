"""حمولاتُ سجلِّ الإصدارات — **البند ٨ (§39٫٨، §43)**.

**والقرارُ يُحسب في الخلفية لا في التطبيقات**: `state` تخرج محسوبةً
(`ok`/`optional`/`forced`) — **وثلاثةُ تطبيقاتٍ تقارن رقمين بأنفسها ثلاثةُ
نسخٍ من قاعدةٍ واحدة**، تفترق أوّلَ ما تتغيّر. وهي قاعدةُ §14 مطبَّقةً على
حكمٍ لا على مبلغ، كما طُبِّقت على `SettlementState` و`LiveDriverOut.state`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.app_release import MAX_REMINDER_HOURS
from app.models.enums import ClientApp


class AppReleaseIn(BaseModel):
    """إنشاءُ إصدارٍ أو تعديلُه — **ومعه إقرارُ الحجب حين يرتفع الحدّ**."""

    app: ClientApp
    build: int = Field(ge=1)
    min_supported_build: int = Field(ge=1)
    #: **يُفحص قبل الحفظ** — `HttpUrl` تحرس الشكل، والخدمةُ تطرق الباب
    download_url: HttpUrl
    release_notes: str = Field(min_length=1, max_length=4000)
    reminder_hours: int = Field(default=24, ge=1, le=MAX_REMINDER_HOURS)
    #: **الإذنُ الثاني، مبنيٌّ في العقد لا في الشاشة** (§39٫٨: «يستأذن
    #: مرّتين»): حين يرتفع الحدُّ عمّا هو قائم **يُطلب رقمُه مكتوباً ثانيةً**.
    #: وإخفاءُ ورقةٍ في الواجهة راحةٌ، **وحقلٌ يجب أن يساوي الرقمَ شرط**.
    confirm_min_supported_build: int | None = None


class AppReleaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    app: ClientApp
    build: int
    min_supported_build: int
    download_url: str
    release_notes: str
    reminder_hours: int
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
