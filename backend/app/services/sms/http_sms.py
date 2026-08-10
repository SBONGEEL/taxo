"""مزود رسائل عبر HTTP — **الملف الوحيد الذي يعرف شكل أسلاك مزود الرسائل**.

نفس دور `card_gateway/telr.py`: أسماء الحقول وموضع المفتاح وشكل الجواب هنا
وحدها، وما عداه يتكلم `base.SmsProvider`.

> **ملاحظة تنفيذية صريحة، كالتي في `telr.py`.** لا عقد مزود رسائل مُسلَّم في
> هذه الجلسة ولا توثيق واجهته، فما دون **مبنيٌّ على الشكل الشائع لمزودي
> الرسائل الإقليميين ويحتاج مطابقةً بالتوثيق قبل أول تشغيل حقيقي**، وهو مجموع
> في ثوابت مسمّاة أعلى الملف كي تُطابَق في دقائق:
>
> 1. `FIELD_*` — أسماء حقول الحمولة.
> 2. `AUTH_HEADER` / `AUTH_SCHEME` — موضع المفتاح.
> 3. `_reference_from` — موضع مرجع الرسالة في الجواب.
>
> وخطؤها لا يفتح باباً: إرسالٌ فاشل يرتدّ `SmsError` ولا يُنشئ حساباً ولا
> يفتح جلسة — والرمز لا يصل صاحبَه فلا يُقبل منه شيء. والمزود الوهمي هو ما
> بُني عليه التدفق واختُبر (SPEC القسم 15/أ).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.sms.base import REQUEST_TIMEOUT_SECONDS, SmsError

# (1) أسماء حقول الحمولة
FIELD_TO = "to"
FIELD_BODY = "message"
FIELD_SENDER = "sender"

# (2) موضع المفتاح
AUTH_HEADER = "Authorization"
AUTH_SCHEME = "Bearer"

# (3) مفاتيح مرجع الرسالة في الجواب، بالترتيب
REFERENCE_KEYS: tuple[str, ...] = ("message_id", "id", "reference")


class HttpSmsProvider:
    """عقدُ مزودٍ واحد — يُبنى من قيم العقد المشفّرة لا من `.env`."""

    def __init__(
        self, *, provider_name: str, endpoint: str, api_key: str, sender_id: str
    ) -> None:
        self.provider_name = provider_name
        self._endpoint = endpoint
        self._api_key = api_key
        self._sender_id = sender_id

    async def _post(self, payload: dict[str, str]) -> dict[str, Any]:
        """نداء واحد للمزود — نقطة الحقن الوحيدة في الاختبارات."""
        headers = {AUTH_HEADER: f"{AUTH_SCHEME} {self._api_key}"}
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.post(
                    self._endpoint, json=payload, headers=headers
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise SmsError() from exc
        except ValueError as exc:  # جواب ليس JSON
            raise SmsError("جواب مزود الرسائل غير مقروء") from exc

        return body if isinstance(body, dict) else {}

    def _reference_from(self, body: dict[str, Any]) -> str:
        for key in REFERENCE_KEYS:
            value = body.get(key)
            if value:
                return str(value)
        # جوابٌ بلا مرجع ليس فشلاً: الرسالة قُبلت والمرجع تفصيلٌ تشخيصي
        return f"{self.provider_name}-accepted"

    async def send(self, to: str, body: str) -> str:
        return self._reference_from(
            await self._post(
                {FIELD_TO: to, FIELD_BODY: body, FIELD_SENDER: self._sender_id}
            )
        )

    async def test_connection(self, test_phone: str | None = None) -> str:
        if test_phone:
            reference = await self.send(test_phone, "TAXO: اختبار اتصال")
            return f"أُرسلت رسالة اختبار — مرجع المزود {reference}"

        # بلا رقمٍ لا تُرسل رسالة مدفوعة: يُتحقق من أن الخدمة تُجيب وحسب.
        # أيُّ جوابٍ HTTP دليلُ وصول؛ الفشل وحده انقطاعُ الشبكة أو العنوان الخطأ
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.get(self._endpoint)
        except httpx.HTTPError as exc:
            raise SmsError("تعذّر الوصول إلى عنوان مزود الرسائل") from exc

        return (
            f"الخدمة تستجيب (HTTP {response.status_code}) — لم تُرسل رسالة. "
            "أضف رقم اختبار لتجربة إرسال فعلي"
        )
