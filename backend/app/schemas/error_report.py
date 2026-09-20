"""حمولةُ تقرير العطب — **هذا الصنفُ هو القائمةُ البيضاء** (§D10).

**ولا قائمةَ ثانيةٌ في مكانٍ آخر.** ما ليس حقلاً هنا **لا يصل الخدمةَ أصلاً**:
Pydantic يُسقط الزائدَ قبل أن يراه سطرٌ من كودنا، فحقلٌ يضيفه تطبيقٌ غداً —
عمداً أو سهواً — لا يُخزَّن ولا يُسجَّل. **وهذا هو الفرقُ بين بياضٍ وسواد**:
السوادُ يحتاج أن يعرف كاتبُه بالحقل الجديد، والبياضُ لا يحتاج.

**والمقاساتُ حرّاسٌ لا زينة**: `max_length` يجعل الزائدَ **٤٢٢ يُقرأ**، لا
قصّاً صامتاً يُخزِّن نصفَ أثرٍ ويُقرأ كاملاً.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ClientApp, ErrorKind, ErrorPlatform, ErrorStatus


class ErrorReportIn(BaseModel):
    """ما يُقبل من جهاز — **ولا شيءَ سواه**.

    **ولا `user_id` ولا `phone` ولا إحداثيّة**: غيابُها ليس سهواً يُسدّ لاحقاً،
    **بل هو العقد**. ومن أراد إضافةَ حقلٍ يمسّ شخصاً يمرّ بهذا الملفّ أولاً،
    وهو موضعٌ يُقرأ في المراجعة.
    """

    app: ClientApp
    kind: ErrorKind
    platform: ErrorPlatform

    #: **الإصدارُ والقناة** — «أفي النسخة الجديدة وحدها؟» أولُ سؤالٍ يُسأل
    release: str | None = Field(default=None, max_length=40)
    channel: str | None = Field(default=None, max_length=20)
    os_version: str | None = Field(default=None, max_length=60)

    #: `sha256` لمُعرِّف الجهاز — **مُعمّىً في الجهاز، ويُملَّح في الخادم ثانيةً**
    device_hash: str = Field(min_length=16, max_length=64, pattern=r"^[0-9a-f]+$")

    #: **قالبُ المسار** — والخادمُ يعيد تقليبَه ولو أرسله العميلُ خاماً
    route: str | None = Field(default=None, max_length=200)

    name: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2_000)
    stack: str | None = Field(default=None, max_length=8_000)
    component_stack: str | None = Field(default=None, max_length=8_000)

    #: يُعاد بناؤه من مفاتيحَ مسمّاةٍ في `core/scrub.py` — لا يُخزَّن كما وصل
    breadcrumbs: list[dict[str, Any]] | None = None

    occurred_at: datetime
    online: bool = True
    #: تكرارُ الحدث نفسِه في الجلسة — **صفٌّ واحدٌ يحمل العدد**، لا أربعون صفّاً
    repeat: int = Field(default=1, ge=1, le=10_000)

    #: **الخيطُ إلى الخلفية** — آخرُ `X-Request-Id` رآه العميلُ في ردٍّ فاشل
    request_id: str | None = Field(default=None, max_length=32)

    #: جملةُ صاحبِ الجهاز — لتقارير الزرّ وحدَها، **وتُنظَّف في الخادم**
    note: str | None = Field(default=None, max_length=500)


class ErrorReportAccepted(BaseModel):
    """**لا يُعاد إلى الجهاز شيءٌ يُبنى عليه**.

    لا مُعرِّفَ مجموعةٍ ولا عدّادات: تطبيقٌ يعرف «هذا العطبُ وقع ٤٠ مرّة» لا
    يفعل بها شيئاً، **ورقمٌ يخرج هو رقمٌ يُقرأ من خارجنا**.
    """

    accepted: bool = True


# ------------------------------------------------ ما يُقرأ في اللوحة (§D10)


class ErrorGroupOut(BaseModel):
    """صفٌّ في القائمة — **ولا حدثَ فيه**: القائمةُ تُجيب «ما هو وكم»."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    app: ClientApp
    kind: ErrorKind
    name: str
    title: str
    status: ErrorStatus
    event_count: int
    user_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    first_seen_release: str | None
    last_seen_release: str | None


class ErrorEventOut(BaseModel):
    """حدثٌ بعينه — **وما فيه مرّ بالمِصفاة قبل أن يُخزَّن**."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: ErrorPlatform
    os_version: str | None
    release: str | None
    channel: str | None
    route: str | None
    name: str
    message: str
    stack: str | None
    component_stack: str | None
    breadcrumbs: list[dict[str, Any]] | None
    device_hash: str
    online: bool
    repeat: int
    request_id: str | None
    user_reported: bool
    note: str | None
    occurred_at: datetime
    received_at: datetime


class ErrorGroupDetailOut(ErrorGroupOut):
    """المجموعةُ ومعها آخرُ حدثٍ — **وهو ما يُقرأ فعلاً عند التشخيص**."""

    latest: ErrorEventOut | None = None
