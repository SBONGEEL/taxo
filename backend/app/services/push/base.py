"""واجهة مزود إشعارات Push — العقد الذي يتكلمه كل ما عدا المزود نفسه.

نفس نهج `services/card_gateway/`: `services/notifications.py` و
`services/campaigns.py` لا يعرفان FCM من غيره، وتبديلُ المزود أو تشغيلُ
الوهمي **إدخالُ عقدٍ من صفحة العقود لا تعديلُ كود** (SPEC القسم 15/أ).

القاعدة التي تحكم الواجهة: **الإرسال لا يفشل الطلبَ الذي أطلقه.** إشعارٌ لم
يصل خسارةٌ أهون من رحلةٍ لم تبدأ لأن مزوداً بعيداً تأخر — فالمستدعي يبتلع
الخطأ ويسجّله. ولهذا يعيد `send` نتيجةً تُقرأ لا يرفع استثناءً لكل رمزٍ ميت:
الرمز الميت **بيانٌ يُنظَّف** لا خطأٌ يُبلَّغ عنه.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.exceptions import AppError

REQUEST_TIMEOUT_SECONDS = 15.0


class PushUnavailable(AppError):
    """لا عقد FCM مُدخل أو مفعّل — أو عقدٌ ناقص الحقول."""

    status_code = 503
    code = "push_unavailable"
    message = "خدمة الإشعارات غير مهيأة — راجع عقد FCM في لوحة الإدارة"


class PushError(AppError):
    """المزود ردّ بخطأ أو تعذّر الوصول إليه."""

    status_code = 502
    code = "push_failed"
    message = "تعذّر إرسال الإشعار"


@dataclass(frozen=True, slots=True)
class PushMessage:
    """إشعارٌ واحد كما يراه المرسِل — بلا أثرٍ لأي مزود بعينه.

    `data` حمولةٌ نصّيّة تفتح الشاشة الصحيحة عند الضغط (نوع الحدث ومُعرّف
    الرحلة مثلاً). لا يُوضع فيها مالٌ ولا سرّ: تمر بخوادم المزود.

    `high_priority` لطلبات الرحلة وحدها (SPEC القسم 10): مهلة القبول عشرون
    ثانية، وDoze mode يؤجّل الإشعار العادي دقائقَ — فتصل البطاقة بعد أن
    انتقل الطلب لكبتنٍ آخر.
    """

    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)
    high_priority: bool = False
    #: **قناةُ أندرويد التي يُعرض فيها** — و`None` تعني القناةَ الافتراضية.
    #:
    #: **وأهميّةُ القناة تُضبط مرّةً عند إنشائها ولا يملك التطبيقُ رفعَها**
    #: (يملكها المستخدم) — فقناةٌ واحدةٌ لكلِّ شيءٍ تختار أحدَ السلوكين للأبد.
    #: **وطلبُ الرحلة يجب أن يصيح ولو كان الهاتفُ صامتاً**، فله قناتُه
    #: (`taxo.offer`) بصوتٍ على **مجرى المنبّه** — وهو ما ينجو من الصامت.
    #:
    #: **ولا يُبنى لها مسارٌ ثانٍ في التطبيق**: أندرويد نفسُه يوجّه الإشعارَ
    #: إلى قناته حين يصل التطبيقُ في الخلفية، فالحقلُ هنا يكفي.
    android_channel_id: str | None = None


@dataclass(frozen=True, slots=True)
class PushResult:
    """ما جرى فعلاً — يُقرأ لتنظيف الرموز الميتة لا ليُبلَّغ به المستخدم."""

    delivered: int = 0
    failed: int = 0
    # رموزٌ ردّ عليها المزود بـ unregistered/invalid: تُعطَّل ولا يُعاد إليها
    invalid_tokens: tuple[str, ...] = ()


class PushProvider(Protocol):
    provider_name: str

    async def send(
        self, tokens: list[str], message: PushMessage
    ) -> PushResult:
        """يرسل الإشعار إلى رموز أجهزةٍ ويعيد ما جرى."""
        ...

    async def test_connection(self) -> str:
        """يختبر بيانات الاعتماد بلا إرسال شيء — أو يرفع `PushError`."""
        ...
