"""واجهة التحقق من رمز هوية Firebase — العقد الذي يتكلمه كل ما عدا المُحقِّق.

نفس بنية بقية مزودي المرحلة 8: عقدٌ مجرّد، ومزودٌ وهمي يُدار من صفحة العقود،
وملفٌّ واحد يعرف أسلاك Firebase، ونقطةُ قرارٍ تقرأ العقد المشفَّر.

**ما يجري هنا نقلُ ثقةٍ لا إنشاؤها**: Firebase تحققت من أن صاحب الطلب يملك
الهاتف (أرسلت الرمز واستقبلته)، وتقول ذلك في رمزٍ موقَّع. مهمتُنا الوحيدة أن
نتأكد أن الرمز **منها هي**، و**لمشروعنا نحن**، و**لم ينتهِ**، وأنه يحمل
هاتفاً. وما لم يُتحقق من هذه الأربعة صار الرمزُ ورقةً يكتبها أي أحد.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.exceptions import AppError

REQUEST_TIMEOUT_SECONDS = 10.0


class FirebaseAuthUnavailable(AppError):
    """لا عقد Firebase مُدخل أو مفعّل، أو عقدٌ بلا `project_id`."""

    status_code = 503
    code = "firebase_auth_unavailable"
    message = "خدمة التحقق من الهاتف غير مهيأة — راجع عقد Firebase في لوحة الإدارة"


class InvalidIdToken(AppError):
    """رمزُ هويةٍ لا يجتاز التحقق — لأي سبب.

    **401 برسالةٍ واحدة لكل الأسباب**: توقيعٌ لا يطابق، أو مشروعٌ آخر، أو
    انتهاء صلاحية، أو رمزٌ بلا هاتف. تفصيلُ السبب للمهاجم خريطةُ طريق، وهو
    في السجل لمن يملك السجل.
    """

    status_code = 401
    code = "invalid_id_token"
    message = "رمز التحقق غير صالح أو انتهت صلاحيته"


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    """ما نأخذه من الرمز بعد اجتيازه التحقق — ولا شيء غيره.

    `phone` بصيغة E.164 كما تصدرها Firebase، وهي نفس الصيغة التي يخزّنها
    `users.phone` (SPEC القسم 4) — فالمقارنة بينهما مباشرة بلا تطبيع ثانٍ.

    `provider_uid` مُعرّف المستخدم لدى Firebase: لا يُخزَّن اليوم ولا يُبنى
    عليه شيء — هويتُنا هي الهاتف — لكنه يُسجَّل في السجل عند الفشل فيُعرف
    أيُّ حسابٍ لدى المزود حاول.
    """

    phone: str
    provider_uid: str
    # مزودُ الدخول داخل Firebase: يجب أن يكون `phone` لا `google.com` ولا غيره
    sign_in_provider: str


class IdTokenVerifier(Protocol):
    async def verify(self, id_token: str) -> VerifiedIdentity:
        """يتحقق من الرمز ويعيد هويته، أو يرفع `InvalidIdToken`."""
        ...

    async def test_connection(self) -> str:
        """يختبر العقد من بطاقته في اللوحة، أو يرفع `AppError`."""
        ...
