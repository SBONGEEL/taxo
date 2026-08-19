"""WhatsApp Cloud API — **الملف الوحيد الذي يعرف أسلاك ميتا**.

نفس دور `card_gateway/telr.py` و`sms/http_sms.py`: أسماءُ الحقول وشكلُ القالب
وموضعُ المرجع في الجواب هنا وحدها، وما عداه يتكلم `base.WhatsAppOtpProvider`.

**وهذا الملفُّ هو القناةُ الرسمية من ميتا** (Graph API على
`graph.facebook.com`)، **وهي إحدى قناتين منذ 2026-08-16**: الثانيةُ بوابةٌ
ذاتيةٌ على Baileys (`baileys.py`)، ويختار بينهما حقلُ `transport` في العقد.

**وكان هنا نصٌّ يمنع المكتباتِ غيرَ الرسمية منعاً**، ونقضه المالكُ بقرارٍ صريح
لأن الرسميةَ كانت تنتظر عقداً لم يصل بينما **لا أحدَ يستطيع التسجيل**. وحجّةُ
النصِّ القديم تبقى صحيحةً ويجب أن تُقرأ: أتمتةُ حسابٍ بمكتبةٍ غير رسمية مخالفةٌ
لشروط واتساب، وعقوبتُها حظرُ الرقم **بلا إنذار**. ولذلك بقي هذا الملفُّ حيّاً
لا محذوفاً: **العودةُ إليه تعديلُ حقلٍ في صفحة العقود لا كتابةُ كود** — وهو
بعينه ما يجعل الحظرَ حادثاً يُعالَج في دقيقتين لا كارثةً تُوقف المنصّة.
وخطةُ الطوارئ بمددها في `CLAUDE.md`.

**وقالبُ المصادقة (Authentication template) لا يقبل نصّاً حرّاً**: القالبُ
معتمدٌ عند ميتا مسبقاً، ونحن نرسل اسمَه ولغتَه ومُعامِلاً واحداً هو الرمز. فلا
`MESSAGE_TEMPLATE` هنا كما في مزود الرسائل — نصُّ الرسالة يسكن عند ميتا.

> **ملاحظتان تنفيذيتان صريحتان، كالتي في `telr.py`.** لا حسابَ WhatsApp Business
> مُسلَّماً في هذه الجلسة ولا رقمَ اختبار، فتفصيلان أدناه **يحتاجان مطابقةً
> بالتوثيق وبأول تشغيل حقيقي**، وهما مجموعان في ثوابت مسمّاة كي تُطابَق في
> دقائق:
>
> 1. `GRAPH_VERSION` — إصدارُ Graph API. القديمُ يعمل سنتين ثم يُتقاعد؛ رقمٌ
>    واحد يُحدَّث هنا.
> 2. `BUTTON_SUB_TYPE` — نوعُ زرِّ القالب. قوالبُ المصادقة تأتي بزرِّ «نسخ
>    الرمز» أو بزرِّ ملءٍ تلقائي، وشكلُ مُعامِله يختلف بينهما. و`SEND_BUTTON`
>    يجعله **اختيارياً**: قالبٌ بلا زرٍّ يُرسل بجسمٍ وحده ويصل الرمز، وقالبٌ
>    بزرٍّ ناقصِ المُعامِل يرتدّ من ميتا بخطأٍ صريح — فالخطأُ مرئيٌّ لا صامت.
>
> وخطؤها لا يفتح باباً: إرسالٌ فاشل يرتدّ `WhatsAppError` فيُعرض مخرجٌ بالقناة
> التالية، ولا يُنشئ حساباً ولا يفتح جلسة — والرمزُ لا يصل صاحبَه فلا يُقبل منه
> شيء. والمزودُ الوهمي هو ما بُني عليه التدفق واختُبر (SPEC القسم 15/أ).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.whatsapp.base import REQUEST_TIMEOUT_SECONDS, WhatsAppError

# (1) إصدار Graph API — يُتقاعد الإصدارُ القديم بعد سنتين، فالرقمُ في مكانٍ واحد
GRAPH_VERSION = "v21.0"
GRAPH_BASE = "https://graph.facebook.com"

# (2) زرُّ القالب: نوعُه وموضعُه. `SEND_BUTTON=False` يُرسل بالجسم وحده
SEND_BUTTON = True
BUTTON_SUB_TYPE = "url"
BUTTON_INDEX = "0"

# حالةُ القالب التي تسمح بالإرسال — ما دونها يُرفض عند ميتا لا عندنا
TEMPLATE_APPROVED = "APPROVED"


class WhatsAppCloudProvider:
    """عقدُ واتساب واحد — يُبنى من قيم العقد المشفّرة لا من `.env`."""

    provider_name = "whatsapp_cloud"

    def __init__(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        template_name: str,
        template_language: str = "ar",
        waba_id: str = "",
    ) -> None:
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._template_name = template_name
        self._template_language = template_language or "ar"
        self._waba_id = waba_id

    # ------------------------------------------------------------ الأسلاك

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _template_payload(self, to: str, code: str) -> dict[str, Any]:
        """حمولةُ قالب المصادقة — الرمزُ مُعامِلٌ لا نصُّ رسالة.

        و`to` بلا «+»: ميتا تقبل الصيغتين والتوثيق يكتبها بلا علامة، فنطبّع
        على ما يكتبه التوثيق بدل أن نعتمد على تسامحٍ قد يتغيّر.
        """
        components: list[dict[str, Any]] = [
            {"type": "body", "parameters": [{"type": "text", "text": code}]}
        ]
        if SEND_BUTTON:
            components.append(
                {
                    "type": "button",
                    "sub_type": BUTTON_SUB_TYPE,
                    "index": BUTTON_INDEX,
                    "parameters": [{"type": "text", "text": code}],
                }
            )

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to.lstrip("+"),
            "type": "template",
            "template": {
                "name": self._template_name,
                "language": {"code": self._template_language},
                "components": components,
            },
        }

    async def _call(
        self, method: str, path: str, *, json: dict[str, Any] | None = None, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """نداءٌ واحد لميتا — نقطةُ الحقن الوحيدة في الاختبارات.

        وخطأُ ميتا يُقرأ من `error.message` ويُعاد كما هو في تفصيل الخطأ: هو
        نصٌّ للمشرف لا للمستخدم، ويوفّر عليه ساعةً من التخمين («القالبُ غير
        معتمد» ليس «تعذّر الإرسال»).
        """
        url = f"{GRAPH_BASE}/{GRAPH_VERSION}/{path}"
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.request(
                    method, url, headers=self._headers, json=json, params=params
                )
                body = response.json() if response.content else {}
        except httpx.HTTPError as exc:
            raise WhatsAppError("تعذّر الوصول إلى خدمة واتساب") from exc
        except ValueError as exc:
            raise WhatsAppError("جواب واتساب غير مقروء") from exc

        if not isinstance(body, dict):
            raise WhatsAppError("جواب واتساب غير مقروء")

        if response.is_error:
            detail = str(
                (body.get("error") or {}).get("message") or f"HTTP {response.status_code}"
            )
            raise WhatsAppError(f"واتساب: {detail}")

        return body

    # ------------------------------------------------------------ العقد

    async def send_code(
        self,
        to: str,
        code: str,
        *,
        ttl_minutes: int,
        purpose: str = "registration",
        body: str = "",
    ) -> str:
        """يرسل الرمز في قالب المصادقة ويعيد `wamid` الرسالة.

        و`ttl_minutes` لا يُرسل: مدةُ صلاحية الرمز في قوالب المصادقة تُضبط
        **في القالب عند ميتا**، لا في كل رسالة. وهو في الواجهة لأن العقد واحدٌ
        لكل القنوات — ومزودُ الرسائل يكتبها في نصّه.

        **و`body` لا يُرسل هنا ولا يمكن أن يُرسل**: قوالبُ المصادقة عند ميتا
        **لا تقبل نصّاً حرّاً** — تُعتمد هناك ونمرّر إليها معاملاً واحداً هو
        الرمز. فقالبُ اللوحة يحكم سلكَ `baileys` وحدَه، وهذا مكتوبٌ في الشاشة
        نفسِها كي لا يحرّر المشرفُ حقلاً لا أثرَ له على هذا الناقل.
        """
        body = await self._call(
            "POST", f"{self._phone_number_id}/messages", json=self._template_payload(to, code)
        )
        messages = body.get("messages")
        if isinstance(messages, list) and messages:
            reference = (messages[0] or {}).get("id")
            if reference:
                return str(reference)
        # جوابٌ بلا مرجع ليس فشلاً: الرسالة قُبلت والمرجع تفصيلٌ تشخيصي
        return f"{self.provider_name}-accepted"

    async def test_connection(self, test_phone: str | None = None) -> str:
        """اختبارٌ **لا يترك أثراً** — ويتحقق من القالب لا من الوصول وحده.

        ثلاث خطوات، وكلٌّ منها تُجيب عن سؤالٍ يُخطئ فيه الإعداد فعلاً:
        رقمُ الأعمال والتوكن (هل العقد صحيح؟)، ثم القالب (هل اسمُه صحيحٌ
        ومعتمد؟ وهو أكثرُ ما يُخطئ)، ثم — إن كتب المشرف رقماً — رسالةٌ حقيقية.
        """
        info = await self._call(
            "GET",
            self._phone_number_id,
            params={"fields": "display_phone_number,verified_name"},
        )
        number = str(info.get("display_phone_number") or "?")
        name = str(info.get("verified_name") or "?")
        lines = [f"رقم الأعمال {number} ({name})"]

        if self._waba_id:
            templates = await self._call(
                "GET",
                f"{self._waba_id}/message_templates",
                params={"name": self._template_name, "limit": "5"},
            )
            entries = [
                entry
                for entry in (templates.get("data") or [])
                if isinstance(entry, dict) and entry.get("name") == self._template_name
            ]
            if not entries:
                raise WhatsAppError(
                    f"لا قالب باسم «{self._template_name}» في هذا الحساب"
                )
            statuses = {str(entry.get("status") or "?") for entry in entries}
            if TEMPLATE_APPROVED not in statuses:
                raise WhatsAppError(
                    f"القالب «{self._template_name}» غير معتمد بعد ({', '.join(statuses)})"
                )
            lines.append(f"القالب «{self._template_name}» معتمد")
        else:
            lines.append("لم يُتحقق من القالب — أضف WABA ID للتحقق منه")

        if test_phone:
            reference = await self.send_code(test_phone, "000000", ttl_minutes=5)
            lines.append(f"أُرسلت رسالة اختبار — مرجع {reference}")
        else:
            lines.append("لم تُرسل رسالة — أضف رقم اختبار لتجربة إرسال فعلي")

        return " · ".join(lines)
