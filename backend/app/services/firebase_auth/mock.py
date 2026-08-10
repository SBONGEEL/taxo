"""مُحقِّق رموز وهمي — ما تُختبر عليه استراتيجيةُ Firebase (القسم 15/أ).

لا سبيل لإصدار رمز هوية Firebase حقيقي في اختبار: توقيعُه بمفتاح Google.
فالمزود الوهمي يقبل رمزاً بصيغةٍ معلومة ويعيد هويتها — فيُختبر **كل ما بعد
التحقق** (مطابقة الهاتف، إنشاء الحساب، إصدار توكناتنا) على مسارٍ حقيقي.

أما التحقق نفسه — التوقيع و`aud` و`iss` والانتهاء — فيختبره
`tests/test_firebase_auth.py` على `FirebaseIdTokenVerifier` الحقيقي بمفتاح
RSA يولّده الاختبار، فلا يبقى فرعٌ حرجٌ بلا اختبار.

**ممنوع في الإنتاج** (`__init__.build_verifier`): مُحقِّقٌ يقبل «أنا صاحب هذا
الرقم» بلا إثبات هو بابُ دخولٍ إلى أي حساب.
"""

from __future__ import annotations

from app.services.firebase_auth.base import InvalidIdToken, VerifiedIdentity

# الصيغة المقبولة: `mock-firebase:+962790000000`
PREFIX = "mock-firebase:"


def mock_token(phone: str) -> str:
    """ما يرسله الاختبار (أو تطبيقُ تطويرٍ بلا Firebase) بدل رمزٍ حقيقي."""
    return f"{PREFIX}{phone}"


class MockIdTokenVerifier:
    def __init__(self, *, project_id: str) -> None:
        self._project_id = project_id

    async def verify(self, id_token: str) -> VerifiedIdentity:
        token = (id_token or "").strip()
        if not token.startswith(PREFIX):
            raise InvalidIdToken()

        phone = token[len(PREFIX) :].strip()
        if not phone.startswith("+") or not phone[1:].isdigit():
            # نفس صرامة المُحقِّق الحقيقي: E.164 أو لا هوية
            raise InvalidIdToken("رمز التحقق بلا رقم هاتف صالح")

        return VerifiedIdentity(
            phone=phone, provider_uid=f"mock-uid-{phone}", sign_in_provider="phone"
        )

    async def test_connection(self) -> str:
        return f"المُحقِّق الوهمي جاهز — مشروع {self._project_id} (بلا شبكة)"
