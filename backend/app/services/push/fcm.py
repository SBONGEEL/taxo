"""مُحوِّل FCM — **الملف الوحيد في المشروع الذي يعرف شكل أسلاك Firebase**.

عنوان الخدمة، شكل الحمولة، مواضع الأولوية في المنصات الثلاث، ورموز الأخطاء
التي تعني «رمزٌ ميت»: كلها هنا. ما عداه يتكلم `base.PushProvider`.

بيانات الاعتماد ملفُّ حساب خدمة Firebase، مصدره `provider_credentials`
مشفّراً من صفحة العقود — لا `.env` ولا ملفٌّ على القرص (SPEC القسم 14).

**آليّة الدخول:** FCM HTTP v1 لا يقبل مفتاحاً ثابتاً بل توكن OAuth2 قصير
العمر، يُستخرج بتوقيع JWT بمفتاح حساب الخدمة (RS256) ومبادلته عند
`token_uri`. التوكن يُخزَّن في الذاكرة حتى قبيل انتهائه: مبادلةٌ لكل إشعار
تضاعف زمن الإرسال وتصطدم بحدود جوجل.

**الأولوية العالية لطلبات الرحلة** (SPEC القسم 10) تُكتب بحقلٍ مختلف لكل
منصة، ولذلك تُرسل الثلاثة معاً في كل رسالة: الحمولة واحدة والجهاز يقرأ ما
يخصه.

> **حالة التحقق (المرحلة 8).** بخلاف بقية مزودي هذه المرحلة، وصل عقد FCM
> حقيقي فجُرِّبت عليه السلسلة كاملةً على مشروع `taxo-84a5f`: توقيعُ JWT
> بمفتاح حساب الخدمة، ومبادلةُ توكن OAuth، ونداءُ `messages:send` المُصادَق
> عليه، **ووصولُ إشعارين إلى جهازٍ حقيقي** — عاديَّ الأولوية وعاليَها. ورمزُ
> جهازٍ غير صالح يعود بـ `INVALID_ARGUMENT` فيُصنَّف رمزاً ميتاً ويُعطَّل.
>
> ما لم يُرصد بعينه: عرضُ الإشعار من عامل الخدمة والتطبيقُ مغلق — في التجربة
> كانت الصفحة مفتوحة فذهب الإشعار إلى `onMessage`، وهو نفسُه ما تحرسه قاعدة
> «لا Push لجهازٍ سوكته نشط». يُرصد أول ما يُبنى تطبيق الراكب (المرحلة 9).
>
> وخطأٌ هنا لا يكسر شيئاً ماليّاً على أي حال: الإرسال يُبتلع ويُسجَّل، والحدث
> وصل صاحبَه على WebSocket أصلاً. واختباراتُ السويت تجري على المزود الوهمي
> (SPEC القسم 15/أ) — لا شبكةَ في اختبار.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
import jwt

from app.services.push.base import (
    REQUEST_TIMEOUT_SECONDS,
    PushError,
    PushMessage,
    PushResult,
    PushUnavailable,
)

SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TOKEN_LIFETIME_SECONDS = 3600
# هامشٌ يُجدَّد قبله التوكن — لا يُنتظر انتهاؤه على رسالةٍ مستعجلة
TOKEN_REFRESH_MARGIN_SECONDS = 120

# ردود تعني «الرمز لم يعد يخص جهازاً»: تُعطَّل صفوفها ولا يُعاد الإرسال إليها
UNREGISTERED_STATUSES = frozenset({"UNREGISTERED", "NOT_FOUND", "INVALID_ARGUMENT"})

logger = logging.getLogger(__name__)


class FcmPushProvider:
    provider_name = "fcm"

    def __init__(self, *, project_id: str, service_account: dict[str, Any]) -> None:
        self._project_id = project_id
        self._client_email = str(service_account.get("client_email") or "").strip()
        self._private_key = str(service_account.get("private_key") or "")
        self._token_uri = str(
            service_account.get("token_uri") or "https://oauth2.googleapis.com/token"
        )
        if not self._client_email or not self._private_key:
            raise PushUnavailable("ملف حساب الخدمة ناقص client_email أو private_key")

        self._access_token: str | None = None
        self._expires_at: float = 0.0

    # -------------------------------------------------------------- الدخول

    async def _token(self) -> str:
        now = time.time()
        if self._access_token and now < self._expires_at:
            return self._access_token

        assertion = jwt.encode(
            {
                "iss": self._client_email,
                "scope": SCOPE,
                "aud": self._token_uri,
                "iat": int(now),
                "exp": int(now + TOKEN_LIFETIME_SECONDS),
            },
            self._private_key,
            algorithm="RS256",
        )

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.post(
                    self._token_uri,
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": assertion,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise PushError("تعذّر الحصول على توكن FCM") from exc
        except ValueError as exc:
            raise PushError("جواب خدمة التوكن غير مقروء") from exc

        token = payload.get("access_token")
        if not token:
            raise PushError("خدمة التوكن لم تعد بتوكن")

        self._access_token = str(token)
        self._expires_at = now + float(
            payload.get("expires_in") or TOKEN_LIFETIME_SECONDS
        ) - TOKEN_REFRESH_MARGIN_SECONDS
        return self._access_token

    # -------------------------------------------------------------- الإرسال

    def _payload(self, token: str, message: PushMessage) -> dict[str, Any]:
        priority = "high" if message.high_priority else "normal"
        return {
            "message": {
                "token": token,
                "notification": {"title": message.title, "body": message.body},
                "data": {k: str(v) for k, v in message.data.items()},
                "android": {"priority": priority},
                "apns": {
                    "headers": {
                        "apns-priority": "10" if message.high_priority else "5"
                    }
                },
                "webpush": {
                    "headers": {"Urgency": "high" if message.high_priority else "normal"}
                },
            }
        }

    async def send(self, tokens: list[str], message: PushMessage) -> PushResult:
        """رسالةٌ لكل رمز: HTTP v1 لا يعرف الإرسال الجماعي بمعرِّفاتٍ متعددة.

        فشلُ رمزٍ لا يوقف البقية — إشعارُ راكبٍ لا يُحبس على جهازٍ ميت لكبتن.
        """
        if not tokens:
            return PushResult()

        access_token = await self._token()
        url = SEND_URL.format(project_id=self._project_id)
        headers = {"Authorization": f"Bearer {access_token}"}

        delivered = 0
        failed = 0
        invalid: list[str] = []

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
            for token in tokens:
                try:
                    response = await http.post(
                        url, json=self._payload(token, message), headers=headers
                    )
                except httpx.HTTPError:
                    failed += 1
                    continue

                if response.status_code < 300:
                    delivered += 1
                    continue

                failed += 1
                # نصُّ رفض المزود يُسجَّل ولا يُعرض: بغيره يصير كل فشلٍ
                # «لم يصل» بلا سببٍ يُقرأ. ومقطوعٌ عمداً — الجواب قد يطول
                logger.warning(
                    "رفض FCM الإرسال (HTTP %s): %s",
                    response.status_code,
                    response.text[:400],
                )
                if self._is_unregistered(response):
                    invalid.append(token)

        return PushResult(
            delivered=delivered, failed=failed, invalid_tokens=tuple(invalid)
        )

    @staticmethod
    def _is_unregistered(response: httpx.Response) -> bool:
        if response.status_code == 404:
            return True
        try:
            error = (response.json() or {}).get("error") or {}
        except ValueError:
            return False
        return str(error.get("status") or "") in UNREGISTERED_STATUSES

    # -------------------------------------------------------------- الاختبار

    async def test_connection(self) -> str:
        """مبادلةُ التوكن وحدها اختبارٌ قاطع لبيانات الاعتماد بلا إرسال شيء."""
        await self._token()
        return f"بيانات حساب الخدمة صالحة — مشروع {self._project_id}"


def parse_service_account(raw: str) -> dict[str, Any]:
    """ملفُّ حساب الخدمة كما يُلصق في صفحة العقود.

    يُقرأ هنا لا في `credentials.py`: ذاك يحفظ نصوصاً مشفّرة ولا يفهم مزوداً.
    """
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise PushUnavailable("ملف حساب الخدمة ليس JSON صالحاً") from exc
    if not isinstance(parsed, dict):
        raise PushUnavailable("ملف حساب الخدمة ليس JSON صالحاً")
    return parsed
