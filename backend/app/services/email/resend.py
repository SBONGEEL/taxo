"""مُرسِلُ بريدٍ عبر Resend — **الملفُّ الوحيد الذي يعرف أسلاكَ Resend**.

نفسُ دور `sms/http_sms.py` و`card_gateway/telr.py`: عنوانُ الواجهة وموضعُ
المفتاح وشكلُ الجواب هنا وحدَها، **وما عداه يتكلّم `base.EmailProvider`**.

**أُذن به ٢٠٢٦-١١-٢٢** (أمرُ المالك الثاني، البند ٢ — `design/OWNER-2026-11-22-SECOND.md`):
خدمةٌ **مجّانيّةٌ بلا بطاقة**، ومفتاحُها في عقد `provider_credentials` المشفَّر
لا في `.env`، **ونطاقُ المُرسِل محقَّقٌ بسجلّات SPF وDKIM** — فبريدٌ من نطاقٍ
غيرِ محقَّقٍ يقع في مجلَّد السخام فيُقرأ «لم يصل الرمز» وهو أُرسل.

**والمفتاحُ مفتاحُ إرسالٍ وحدَه** (`sending_access`) لا مفتاحٌ كامل: من سرقه
يرسل باسمنا ولا يقرأ ولا يحذف ولا يغيّر نطاقاً. **فاختبارُ الاتصال بلا عنوانٍ
لا يستطيع أن يسأل «ما نطاقاتي؟»** — يسأل، فتردّ Resend بـ`restricted_api_key`،
**وهذا الردُّ نفسُه شاهدُ أن المفتاحَ معروفٌ وصالح**: المفتاحُ الباطلُ يُردّ بغيره.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.email.base import REQUEST_TIMEOUT_SECONDS, EmailError

API_BASE = "https://api.resend.com"
SEND_PATH = "/emails"
#: يُسأل بلا إرسال — مفتاحُ الإرسال يُردّ عليه بـ`restricted_api_key` وهو جوابُ «صالح»
PROBE_PATH = "/domains"
RESTRICTED_KEY_NAME = "restricted_api_key"


class ResendEmailProvider:
    """عقدٌ واحد — يُبنى من قيم العقد المفكوكة لا من `.env`."""

    provider_name = "resend"

    def __init__(self, *, api_key: str, from_address: str, from_name: str = "") -> None:
        self._api_key = api_key
        self._from = f"{from_name} <{from_address}>" if from_name else from_address

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        """نداءُ الإرسال — **نقطةُ الحقن الوحيدة في الاختبارات**."""
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
            return await http.post(API_BASE + SEND_PATH, json=payload, headers=self._headers())

    async def _get(self, path: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
            return await http.get(API_BASE + path, headers=self._headers())

    @staticmethod
    def _error_text(response: httpx.Response) -> str:
        """رسالةُ Resend بلا أن يُطبع مفتاحٌ أو نصُّ الرسالة — **فالنصُّ فيه الرمز**."""
        try:
            body = response.json()
        except ValueError:
            return f"HTTP {response.status_code}"
        if isinstance(body, dict):
            name = str(body.get("name") or "")
            message = str(body.get("message") or "")[:160]
            return f"HTTP {response.status_code} {name}: {message}".strip()
        return f"HTTP {response.status_code}"

    async def send(self, to: str, *, subject: str, body: str) -> str:
        payload = {"from": self._from, "to": [to], "subject": subject, "text": body}
        try:
            response = await self._post(payload)
        except httpx.HTTPError as exc:
            raise EmailError("تعذّر الوصول إلى مُرسِل البريد") from exc
        if response.status_code >= 400:
            raise EmailError(f"مُرسِلُ البريد رفض الرسالة — {self._error_text(response)}")
        try:
            data = response.json()
        except ValueError:
            data = {}
        # جوابٌ مقبولٌ بلا مرجعٍ ليس فشلاً: الرسالةُ قُبلت والمرجعُ تفصيلٌ تشخيصيّ
        return str((data or {}).get("id") or "resend-accepted")

    async def test_connection(self, test_email: str | None = None) -> str:
        if test_email:
            reference = await self.send(
                test_email, subject="TAXO: اختبار اتصال", body="اختبارُ اتصالِ مُرسِل البريد."
            )
            return f"أُرسلت رسالةُ اختبار — مرجعُ Resend {reference}"
        try:
            response = await self._get(PROBE_PATH)
        except httpx.HTTPError as exc:
            raise EmailError("تعذّر الوصول إلى Resend") from exc
        if response.status_code < 400:
            return "المفتاحُ صالح (مفتاحٌ كامل) — لم تُرسل رسالة. أضف عنواناً لتجربة إرسالٍ فعليّ"
        try:
            name = str((response.json() or {}).get("name") or "")
        except ValueError:
            name = ""
        if name == RESTRICTED_KEY_NAME:
            return "المفتاحُ صالح (مفتاحُ إرسالٍ وحدَه) — لم تُرسل رسالة. أضف عنواناً لتجربة إرسالٍ فعليّ"
        raise EmailError(f"Resend رفض المفتاح — {self._error_text(response)}")
