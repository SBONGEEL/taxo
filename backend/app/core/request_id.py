"""مُعرِّفُ الطلب — **الخيطُ الذي يصل عطباً في هاتفٍ بسطرٍ في السجل**.

**العلّةُ مقيسةٌ لا محتاطة**: حتى اليوم، حين يقول كبتنٌ «الشاشةُ وقعت أمس»
لا يوجد شيءٌ يُبحث به. السجلُّ يحمل المسارَ والوقتَ، والهاتفُ يحمل رسالةً
عربيةً عامّة، **ولا حرفَ مشتركٌ بينهما**. فمن يُشخِّص يقارن الساعاتِ ويخمّن.

**وهذا المُعرِّفُ هو الحرفُ المشترك**: يُولَّد لكلِّ طلب، يُكتب في رأس الردّ
فيلتقطه التطبيق، ويُكتب في سطر السجل حين يقع خطأ. فيصير سؤالُ «لماذا سقط
طلبُه» بحثاً نصّياً واحداً بدل تخمين.

**ولا يُقبل مُعرِّفٌ وارد** — وهذا قرارٌ لا سهو: قبولُ نصٍّ من العميل يعني
إدخالَ نصٍّ يتحكّم به غيرُنا في **كلِّ سطر سجلٍّ نكتبه**، ولا أحدَ اليومَ
يرسل واحداً أصلاً. فالمنفعةُ صفرٌ والسطحُ ليس صفراً. ويومَ تصير الحافةُ
تُرسل مُعرِّفَ تتبّعٍ يُعاد النظر — **ويُقرأ هذا السطرُ قرارَه لا غفلتَه**.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

#: اسمُ الرأس — **ويُصرَّح في `expose_headers` وإلا لم يقرأه متصفّح**
HEADER = "x-request-id"

#: مفتاحُ المُعرِّف في `scope` — **والنسخةُ الثانيةُ ليست ترفاً** (قِيس
#: 2026-09-20): `ServerErrorMiddleware` الذي يستدعي معالجَ `Exception`
#: **أخرجُ من كلِّ وسيطٍ يُضاف بـ`add_middleware`**، فحين يبلغه الاستثناءُ
#: يكون `finally` هنا قد أعاد الـ`ContextVar` إلى فراغه — **فيخرج ٥٠٠ بلا
#: رقمٍ مرجعيّ وهو الردُّ الذي وُجد الرقمُ لأجله**. و`scope` قاموسٌ واحدٌ
#: يمرّ بالمكدَّس كلِّه صعوداً ونزولاً، فما يُكتب فيه يبقى.
SCOPE_KEY = "taxo_request_id"

_request_id: ContextVar[str] = ContextVar("request_id", default="")


def current_request_id() -> str:
    """مُعرِّفُ الطلب الجاري، أو نصٌّ فارغٌ خارج طلب (مهمّةُ Celery مثلاً)."""
    return _request_id.get()


def request_id_of(scope: Scope) -> str:
    """المُعرِّفُ من `scope` — **يُقرأ هكذا في معالجات الأخطاء**.

    ويسقط إلى `ContextVar` لمن يُنشئ `Request` بلا مرورٍ بالوسيط (اختبارٌ
    يستدعي معالجاً مباشرةً مثلاً).
    """
    value = scope.get(SCOPE_KEY) if isinstance(scope, dict) else None
    return value or _request_id.get()


class RequestIdMiddleware:
    """وسيطٌ خامٌ لا `BaseHTTPMiddleware` — **والفرقُ ليس ذوقاً**.

    `BaseHTTPMiddleware` يشغّل ما تحته في مهمّةٍ أخرى بنسخةٍ من السياق، فيصير
    وضعُ `ContextVar` فيه سؤالاً عن ترتيبِ نسخٍ بدل أن يكون حقيقةً واحدة.
    والوسيطُ الخامُ يضع القيمةَ في سياق الطلب نفسِه الذي تقرأ منه المعالجات.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:16]
        scope[SCOPE_KEY] = request_id
        token = _request_id.set(request_id)

        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            _request_id.reset(token)
