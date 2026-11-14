"""زرّ «اختبار الاتصال» في بطاقة كل عقد (SPEC القسم 13/7 — المرحلة 8).

مكانٌ واحد يعرف **أيَّ نداءٍ يختبر أيَّ مزود**، وكلُّ مزودٍ يجيب من ملفه هو:
`TelrGateway.test_connection`، `SmsProvider.test_connection`، وهكذا. فما هنا
توجيهٌ لا أسلاك.

ثلاث قواعد:

- **الاختبار لا يترك أثراً.** لا طلب دفعٍ يُفتح، ولا حوالةٌ تُرسل، ولا رسالةٌ
  مدفوعة إلا إن كتب المشرف رقماً صراحةً. اختبارٌ يكلّف مالاً أو يفتح صفاً
  ليس اختباراً.
- **الفشل جوابٌ لا انهيار.** خطأُ المزود يعود 200 بـ `ok=false` ونصِّ السبب:
  الغرضُ أن يقرأ المشرف ما جرى، لا أن تبتلعه شاشةُ خطأ عامة.
- **`last_tested_at` يُكتب في الحالتين.** السؤال «متى آخر مرة اختُبر؟» لا
  «متى آخر مرة نجح؟» — والنتيجةُ نفسها تدخل سجل التدقيق.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import get_cipher
from app.core.exceptions import AppError
from app.models.enums import AuditAction, ProviderKey
from app.models.provider_credential import ProviderCredential
from app.models.user import User
from app.services import audit

# نقطتان في عمّان — مسافةٌ حقيقية قصيرة يقبلها Mapbox، ولا تُنشئ شيئاً
_TEST_PICKUP = (31.9539, 35.9106)
_TEST_DROPOFF = (31.9700, 35.9300)


@dataclass(frozen=True, slots=True)
class TestResult:
    ok: bool
    detail: str


async def _test_mapbox(values: dict[str, Any]) -> str:
    from app.services.directions import Coordinates, fetch_route

    token = str(values.get("secret_token") or "").strip()
    if not token:
        raise AppError("لا توكن سري في العقد")

    route = await fetch_route(
        token, Coordinates(*_TEST_PICKUP), Coordinates(*_TEST_DROPOFF)
    )
    return f"المسارات تعمل — مسافة الاختبار {route.distance_km} كم"


async def _test_telr(values: dict[str, Any]) -> str:
    from app.services.card_gateway import build_gateway

    return await build_gateway(values).test_connection()


async def _test_sms(values: dict[str, Any], test_phone: str | None) -> str:
    from app.services.sms import build_provider

    return await build_provider(values).test_connection(test_phone)


async def _test_whatsapp(values: dict[str, Any], test_phone: str | None) -> str:
    from app.services.whatsapp import build_provider

    return await build_provider(values).test_connection(test_phone)


async def _test_fcm(values: dict[str, Any]) -> str:
    from app.services.push import build_provider

    return await build_provider(values).test_connection()


async def _test_firebase_auth(values: dict[str, Any]) -> str:
    from app.services.firebase_auth import build_verifier

    return await build_verifier(values).test_connection()


async def _test_cliq(values: dict[str, Any]) -> str:
    from app.services.cliq import build_provider

    return await build_provider(values).test_connection()


async def _test_payout(values: dict[str, Any]) -> str:
    from app.services.payout import build_provider

    return await build_provider(values).test_connection()


async def _test_facebook(values: dict[str, Any]) -> str:
    """**يقرأ الصفحةَ نفسَها ويقول اسمَها** — ويرفض معرّفاً لا يطابق ما يعيده فيسبوك.

    فيسبوك يقبل اسمَ المستخدم (`taxoapp`) في المسار ويعيد المعرّفَ الرقميّ؛ **والقناةُ تحتاج الرقميّ**: معرّفُ كلِّ منشورٍ
    `{رقم الصفحة}_{رقم المنشور}`، و`Page.owns` يقارنه ببداية `page_id` — فاسمُ مستخدمٍ في العقد يجعل كلَّ منشورٍ «ليس للصفحة».
    """
    from app.services.facebook import graph

    page_id = str(values.get("page_id") or "").strip()
    token = str(values.get("page_token") or "").strip()
    if not page_id or not token:
        raise AppError("عقد فيسبوك ناقص معرّف الصفحة أو الرمز")
    page = graph.Page(page_id=page_id, token=token)
    try:
        info = await graph.summary(page)
    except graph.FacebookError as exc:
        # **نصُّ فيسبوك منظَّفٌ من الرمز** في `_send` — فيُقرأ كما هو
        raise AppError(f"فيسبوك رفض: {exc}") from None
    real_id = str(info.get("id") or "")
    if real_id != page_id:
        raise AppError(f"المعرّفُ في العقد ليس رقمَ الصفحة — اكتب {real_id or 'المعرّفَ الرقميّ'} بدل {page_id}")
    followers = info.get("followers_count")
    tail = f" · {followers} متابع" if followers is not None else ""
    return f"صفحة «{info.get('name') or page_id}» ({real_id}){tail}"


async def _run(
    provider_key: ProviderKey, values: dict[str, Any], test_phone: str | None
) -> str:
    if provider_key is ProviderKey.MAPBOX:
        return await _test_mapbox(values)
    if provider_key is ProviderKey.TELR:
        return await _test_telr(values)
    if provider_key is ProviderKey.SMS:
        return await _test_sms(values, test_phone)
    if provider_key is ProviderKey.WHATSAPP:
        return await _test_whatsapp(values, test_phone)
    if provider_key is ProviderKey.FCM:
        return await _test_fcm(values)
    if provider_key is ProviderKey.FIREBASE_AUTH:
        return await _test_firebase_auth(values)
    if provider_key is ProviderKey.CLIQ_ACQUIRER:
        return await _test_cliq(values)
    if provider_key in (ProviderKey.CHARGILY, ProviderKey.SOFIZPAY, ProviderKey.NOWPAY, ProviderKey.WHOP, ProviderKey.MOONPAY):
        # **وسيطا الجزائر** (§٧٣-هـ المرحلة ٣) — `Chargily` يسأل رصيدَه، و`SofizPay` يقول إن لا بابَ له يختبر بلا أثر
        from app.services import payment_gateways

        return await payment_gateways.build(provider_key.value, values).test_connection()
    if provider_key is ProviderKey.FACEBOOK_PAGE:
        return await _test_facebook(values)
    if provider_key is ProviderKey.PAYOUT:
        return await _test_payout(values)
    # **لا سقوطَ إلى اختبار عقدٍ آخر** (عطبٌ مقيسٌ ٢٠٢٦-١١-٠٥): كان كلُّ مفتاحٍ بلا فرعٍ يُختبر بعقد التحويلات، فقالت بطاقةُ
    # فيسبوك «عقد التحويلات الآلية ناقص العنوان» — جوابٌ عن عقدٍ آخر يُقرأ جواباً عن هذا
    raise AppError("لا اختبارَ مبنيٌّ لهذا العقد بعد")


async def test_credential(
    session: AsyncSession,
    credential: ProviderCredential,
    *,
    actor: User | None = None,
    test_phone: str | None = None,
) -> TestResult:
    """يختبر عقداً ويسجّل زمن الاختبار ونتيجته. الـ commit مسؤولية الراوتر."""
    values = get_cipher().decrypt(credential.credentials)

    try:
        result = TestResult(
            True, await _run(ProviderKey(credential.provider_key), values, test_phone)
        )
    except AppError as exc:
        result = TestResult(False, exc.message)
    except Exception as exc:  # pragma: no cover - عطلٌ غير متوقع من مكتبة
        result = TestResult(False, f"خطأ غير متوقع: {exc.__class__.__name__}")

    credential.last_tested_at = datetime.now(UTC)
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="provider_credential",
        entity_id=credential.id,
        # لا قيم — اسم الإجراء ونتيجته فقط (SPEC القسم 4)
        details={
            "action": "test_connection",
            "provider_key": ProviderKey(credential.provider_key).value,
            "ok": result.ok,
        },
    )
    return result
