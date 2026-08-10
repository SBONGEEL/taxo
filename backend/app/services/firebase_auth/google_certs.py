"""مُحقِّق رموز Firebase — **الملف الوحيد الذي يعرف شكل رمز هوية Firebase**.

عنوانُ مفاتيح Google العامة، وقواعدُ `iss`/`aud`، وأسماءُ المطالبات: كلها هنا.
وما عداه يتكلم `base.IdTokenVerifier`.

> **لماذا لا `firebase-admin`؟** الطلب كان «التحقق بـ Admin SDK»، وهذا الملف
> يفعل **ما تفعله الحزمة حرفاً بحرف** في `verify_id_token`: يجلب شهادات
> `securetoken@system.gserviceaccount.com`، ويختار الشهادة بـ `kid`، ويتحقق
> من توقيع RS256 ومن `aud` و`iss` و`exp` و`iat` و`sub`. والسببان في تركها:
>
> 1. **اتساقٌ مع ما قبله**: `services/push/fcm.py` في هذه المرحلة نفسها يوقّع
>    JWT ويبادل توكن OAuth بيده بـ PyJWT — فإدخالُ الحزمة الآن يعني طريقتين
>    لقراءة نفس مشروع Firebase في مستودعٍ واحد.
> 2. **الكلفة**: `firebase-admin` يجرّ `google-cloud-*` و`grpcio` (عشرات
>    الميغابايتات وبناءً أطول) مقابل نحو مئة سطرٍ نكتبها هنا ونختبرها.
>
> وما **لا** يفعله هذا الملف ولا تفعله الحزمة افتراضياً: فحصُ إبطال الجلسة
> (`check_revoked`) — نداءٌ إضافي لكل دخول. وما دام الرمز عمره ساعة والدخول
> يُصدر توكناتنا نحن، فالإبطال عندنا لا عند Firebase.

**الشهادات تُخزَّن بعمرٍ يقوله Google نفسه** في `Cache-Control: max-age`:
جلبُها لكل دخول يجعل تسجيل الدخول رهينةَ شبكةٍ ثالثة، وتثبيتُها إلى الأبد
يكسر الدخول يوم تُدوَّر المفاتيح.
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx
import jwt
from cryptography.x509 import load_pem_x509_certificate

from app.services.firebase_auth.base import (
    REQUEST_TIMEOUT_SECONDS,
    InvalidIdToken,
    VerifiedIdentity,
)

CERTS_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)
ISSUER_TEMPLATE = "https://securetoken.google.com/{project_id}"
ALGORITHM = "RS256"

# مزود الدخول المقبول داخل Firebase — الهاتف وحده. حسابٌ دخل بـ Google أو
# بمجهولٍ (anonymous) ليس إثباتاً لملكية رقم
PHONE_PROVIDER = "phone"

# هامشُ انحراف الساعات المقبول بين خادمنا وGoogle
LEEWAY_SECONDS = 30
# سقفٌ احتياطي لعمر الشهادات إن غاب `Cache-Control`
FALLBACK_CACHE_SECONDS = 3600

_E164 = re.compile(r"^\+[1-9]\d{6,14}$")


class _CertCache:
    """شهاداتُ Google مشتركةٌ بين كل العقود: مفاتيحُ توقيعٍ واحدة للعالم كله."""

    def __init__(self) -> None:
        self._certs: dict[str, str] = {}
        self._expires_at: float = 0.0

    async def get(self) -> dict[str, str]:
        if self._certs and time.time() < self._expires_at:
            return self._certs

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.get(CERTS_URL)
                response.raise_for_status()
                certs = response.json()
        except httpx.HTTPError as exc:
            raise InvalidIdToken("تعذّر جلب مفاتيح التحقق من Google") from exc
        except ValueError as exc:
            raise InvalidIdToken("مفاتيح التحقق غير مقروءة") from exc

        if not isinstance(certs, dict) or not certs:
            raise InvalidIdToken("مفاتيح التحقق غير مقروءة")

        self._certs = {str(k): str(v) for k, v in certs.items()}
        self._expires_at = time.time() + _max_age(
            response.headers.get("cache-control", "")
        )
        return self._certs

    def clear(self) -> None:
        self._certs = {}
        self._expires_at = 0.0


def _max_age(header: str) -> int:
    match = re.search(r"max-age=(\d+)", header)
    return int(match.group(1)) if match else FALLBACK_CACHE_SECONDS


_cache = _CertCache()


def _public_key(cert_pem: str):
    """Google تنشر شهادات X.509 لا مفاتيح JWK — فالمفتاح يُستخرج منها."""
    return load_pem_x509_certificate(cert_pem.encode("utf-8")).public_key()


class FirebaseIdTokenVerifier:
    """يتحقق من رموز مشروعٍ واحد — يُبنى من قيم العقد لا من `.env`."""

    def __init__(self, *, project_id: str) -> None:
        self._project_id = project_id

    @property
    def issuer(self) -> str:
        return ISSUER_TEMPLATE.format(project_id=self._project_id)

    async def verify(self, id_token: str) -> VerifiedIdentity:
        token = (id_token or "").strip()
        if not token:
            raise InvalidIdToken()

        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidIdToken() from exc

        if header.get("alg") != ALGORITHM:
            # `alg: none` أو HS256 بمفتاحٍ يخمّنه المهاجم — يُرفض قبل أي شيء
            raise InvalidIdToken()

        key_id = header.get("kid")
        if not key_id:
            raise InvalidIdToken()

        claims = await self._decode(token, key_id)
        return self._identity(claims)

    async def _decode(self, token: str, key_id: str) -> dict[str, Any]:
        certs = await _cache.get()
        cert = certs.get(key_id)
        if cert is None:
            # مفتاحٌ لا نعرفه: قد تكون Google دوّرت مفاتيحها للتوّ — نعيد
            # الجلب مرةً واحدة قبل الرفض
            _cache.clear()
            cert = (await _cache.get()).get(key_id)
        if cert is None:
            raise InvalidIdToken()

        try:
            return jwt.decode(
                token,
                _public_key(cert),
                algorithms=[ALGORITHM],
                # الجمهور والمُصدِر يُفحصان هنا لا بعد فك التشفير: رمزٌ صحيح
                # التوقيع لمشروعٍ آخر رمزٌ **صالح** — والقبولُ به يعني أن أي
                # مشروع Firebase في العالم يستطيع إصدار دخولٍ لتطبيقنا
                audience=self._project_id,
                issuer=self.issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "aud", "iss", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidIdToken() from exc

    def _identity(self, claims: dict[str, Any]) -> VerifiedIdentity:
        firebase = claims.get("firebase") or {}
        provider = str(firebase.get("sign_in_provider") or "")
        if provider != PHONE_PROVIDER:
            raise InvalidIdToken("هذا الرمز ليس تحققاً من رقم هاتف")

        phone = str(claims.get("phone_number") or "").strip()
        if not _E164.match(phone):
            # Firebase تُصدر E.164 دائماً؛ ورمزٌ بلا هاتف مقروء لا هوية له عندنا
            raise InvalidIdToken("رمز التحقق بلا رقم هاتف صالح")

        subject = str(claims.get("sub") or "").strip()
        if not subject:
            raise InvalidIdToken()

        return VerifiedIdentity(
            phone=phone, provider_uid=subject, sign_in_provider=provider
        )

    async def test_connection(self) -> str:
        """يجلب مفاتيح Google ويؤكد أن العقد يحمل مشروعاً.

        لا يمكن أن يكون الاختبار أقطع من هذا بلا رمزٍ حقيقي: صحةُ
        `project_id` لا تظهر إلا في `aud` رمزٍ يُصدره تطبيقٌ فعلي.
        """
        certs = await _cache.get()
        return (
            f"مفاتيح Google متاحة ({len(certs)} مفتاحاً) — "
            f"المُصدِر المتوقع {self.issuer}"
        )
