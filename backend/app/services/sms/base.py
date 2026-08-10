"""واجهة مزود الرسائل القصيرة — العقد الذي يتكلمه كل ما عدا المزود نفسه.

نفس نهج `services/card_gateway/` و`services/auth/`: `services/otp.py` وطبقةُ
المصادقة لا تعرفان أيَّ مزودٍ يرسل، وتبديلُ المزود **إدخالُ عقدٍ من صفحة
العقود لا تعديلُ كود** (SPEC القسم 15/أ).

عمليتان لا أكثر: إرسالُ رسالة، واختبارُ الاتصال الذي يضغطه المشرف من بطاقة
العقد قبل أن يفتح الباب لتحوّل الدخول كله إلى OTP.
"""

from __future__ import annotations

from typing import Protocol

from app.core.exceptions import AppError

# مهلة نداء المزود. أقصر من صبر المستخدم على شاشة «أرسل الرمز»
REQUEST_TIMEOUT_SECONDS = 15.0


class SmsUnavailable(AppError):
    """لا عقد مزود رسائل مُدخل أو مفعّل — أو عقدٌ ناقص الحقول.

    503 لا 501: الميزة مبنية والعقد غائب، نفس منطق `CardGatewayUnavailable`.
    """

    status_code = 503
    code = "sms_unavailable"
    message = "خدمة الرسائل غير مهيأة — راجع عقد مزود SMS في لوحة الإدارة"


class SmsError(AppError):
    """المزود ردّ بخطأ أو تعذّر الوصول إليه."""

    status_code = 502
    code = "sms_send_failed"
    message = "تعذّر إرسال الرسالة القصيرة"


class SmsProvider(Protocol):
    """ما تحتاجه المرحلة 8 من أي مزود رسائل."""

    provider_name: str

    async def send(self, to: str, body: str) -> str:
        """يرسل رسالة إلى رقم E.164 ويعيد مرجعها لدى المزود."""
        ...

    async def test_connection(self, test_phone: str | None = None) -> str:
        """يختبر العقد ويعيد وصفاً لما جرى — أو يرفع `SmsError`.

        `test_phone` اختياري عمداً: بوجوده تُرسل رسالة حقيقية فيكون الاختبار
        قاطعاً، وبغيابه يُكتفى بالوصول إلى الخدمة — فزرُّ اختبارٍ يرسل رسالةً
        مدفوعةً إلى رقمٍ لم يطلبه أحد ليس اختباراً بريئاً.
        """
        ...
