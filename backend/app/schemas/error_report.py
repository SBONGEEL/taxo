"""حمولةُ تقرير العطب — **هذا الصنفُ هو القائمةُ البيضاء** (§D10).

**ولا قائمةَ ثانيةٌ في مكانٍ آخر.** ما ليس حقلاً هنا **لا يصل الخدمةَ أصلاً**:
Pydantic يُسقط الزائدَ قبل أن يراه سطرٌ من كودنا، فحقلٌ يضيفه تطبيقٌ غداً —
عمداً أو سهواً — لا يُخزَّن ولا يُسجَّل. **وهذا هو الفرقُ بين بياضٍ وسواد**:
السوادُ يحتاج أن يعرف كاتبُه بالحقل الجديد، والبياضُ لا يحتاج.

**والمقاساتُ حرّاسٌ لا زينة**: `max_length` يجعل الزائدَ **٤٢٢ يُقرأ**، لا
قصّاً صامتاً يُخزِّن نصفَ أثرٍ ويُقرأ كاملاً.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import ClientApp, ErrorKind, ErrorPlatform


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
