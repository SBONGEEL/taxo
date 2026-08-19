"""واتساب مُحقِّقاً ثالثاً — WhatsApp Cloud API (المرحلة 12-هـ).

خمسُ قواعد في هذا الملف، وكلٌّ منها تفشل بحذف سطرٍ واحد:

1. **العقدُ وحده لا يفتح القناة** — والمفتاحُ per-country شرطٌ ثانٍ.
2. **والمفتاحُ وحده لا يفتحها** — عقدٌ غائبٌ يعني القناة التالية.
3. **الترتيبُ `whatsapp ← sms ← firebase`** (تبدّل بقرار المالك).
4. **فشلُ الإرسال يحمل مخرجاً** — `fallback_channel` في جسم الخطأ.
5. **والرمزُ يُتحقق منه بلا سؤالٍ عن قناته**: من ارتدّ إلى الرسائل بعد أن فشل
   واتساب يُقبل رمزُه — ولو كان التحققُ مرتبطاً بالقناة لبطل الارتدادُ نفسُه.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import (
    disable_provider,
    enable_sms_provider,
    enable_whatsapp_provider,
    fast_forward_otp_cooldown,
    read_otp,
    read_whatsapp_otp,
)

PHONE = "0791234567"
E164 = "+962791234567"
LIBYAN_PHONE = "0912345678"
LIBYAN_E164 = "+218912345678"

SIGNUP = {
    "phone": PHONE,
    "name": "راكب واتساب",
    "password": "SuperSecret123",
    "country_code": "JO",
    "role": "rider",
}


async def _flip_whatsapp(
    client: AsyncClient, admin_headers: dict, enabled: bool, country: str = "JO"
) -> None:
    """يُشعل المفتاح من نفس الباب الذي يضغطه المشرف — لا بكتابةٍ في القاعدة."""
    response = await client.put(
        "/admin/settings/feature-flags",
        json={
            "country_code": country,
            "feature_key": "whatsapp_otp_enabled",
            "enabled": enabled,
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


async def _method(client: AsyncClient, country: str = "JO") -> dict:
    response = await client.get("/auth/method", params={"country_code": country})
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------- شرطان لا شرطٌ واحد


async def test_the_contract_alone_does_not_open_the_channel(
    client: AsyncClient, session_factory
) -> None:
    """عقدٌ مفعّلٌ ومفتاحٌ مطفأ — فالقناةُ لا تُعرض ولا تُستعمل.

    وهذا ما يجعل «مطفأٌ افتراضاً» قابلاً للتصديق: المفتاحُ ليس تجميلاً في شاشة
    الإعدادات بل شرطٌ يُقرأ في نقطة القرار.
    """
    await enable_whatsapp_provider(session_factory)
    await disable_provider(session_factory, "firebase_auth")

    assert (await _method(client))["verification"] == "none"
    assert "whatsapp_otp" not in (await _method(client))["channels"]


async def test_the_flag_alone_does_not_open_the_channel(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """مفتاحٌ مشتعلٌ بلا عقد — تُنتقل إلى القناة التالية بلا عطل."""
    await _flip_whatsapp(client, admin_headers, True)
    await enable_sms_provider(session_factory)

    body = await _method(client)
    assert body["verification"] == "sms_otp"
    assert "whatsapp_otp" not in body["channels"]


async def test_both_together_make_whatsapp_first(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """الترتيب `whatsapp ← sms ← firebase` — والقنواتُ معلنةٌ كلُّها."""
    await enable_whatsapp_provider(session_factory)
    await enable_sms_provider(session_factory)
    await _flip_whatsapp(client, admin_headers, True)

    body = await _method(client)
    assert body["verification"] == "whatsapp_otp"
    assert body["channels"] == ["whatsapp_otp", "sms_otp", "firebase"]
    # وطولُ الرمز يُعلن للقناتين: كلتاهما تُوصل رمزاً من ست خانات نولّده نحن
    assert body["otp_length"] == 6


async def test_the_flag_is_per_country_while_the_contract_is_global(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """سوقٌ يُشعلها وسوقٌ لا — بعقدٍ واحد.

    وهو سببُ وجود المفتاح per-country: القالبُ يُعتمد بلغةٍ وسوقٍ قبل الآخر،
    وعقدٌ واحد لا يحمل هذا الفرق.
    """
    await enable_whatsapp_provider(session_factory)
    await enable_sms_provider(session_factory)
    await _flip_whatsapp(client, admin_headers, True, country="JO")

    assert (await _method(client, "JO"))["verification"] == "whatsapp_otp"
    assert (await _method(client, "LY"))["verification"] == "sms_otp"


async def test_the_channel_follows_the_phone_not_the_default_country(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """رقمٌ ليبيّ في مسارٍ لا يحمل دولة — الدولةُ تُشتق من الرقم لا تُفترض.

    ولو افتُرضت الدولةُ الافتراضية لأرسل السوقُ الليبي في قناةٍ أُطفئت فيه —
    وهو بعينه عطبُ «ما يُعلن غيرُ ما يقع».
    """
    await enable_whatsapp_provider(session_factory)
    await enable_sms_provider(session_factory)
    await _flip_whatsapp(client, admin_headers, True, country="JO")

    jordanian = await client.post("/auth/challenge", json={"phone": E164})
    assert jordanian.status_code == 200, jordanian.text
    assert jordanian.json()["channel"] == "whatsapp_otp"

    libyan = await client.post("/auth/challenge", json={"phone": LIBYAN_E164})
    assert libyan.status_code == 200, libyan.text
    assert libyan.json()["channel"] == "sms_otp"


# ------------------------------------------------------ الإرسال والتحقق


async def test_a_code_sent_over_whatsapp_completes_signup(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """التدفّق كاملاً على المزود الوهمي: رمزٌ في واتساب ثم حسابٌ محقق."""
    from app.core.redis_client import get_redis_client
    from app.services.whatsapp import last_message

    await enable_whatsapp_provider(session_factory)
    await _flip_whatsapp(client, admin_headers, True)

    challenge = await client.post(
        "/auth/challenge", json={"phone": PHONE, "country_code": "JO"}
    )
    assert challenge.status_code == 200, challenge.text
    assert challenge.json()["sent"] is True
    assert challenge.json()["channel"] == "whatsapp_otp"

    # الرسالةُ «وصلت» في قناة واتساب لا في قناة الرسائل — مفتاحان منفصلان
    assert await last_message(get_redis_client(), E164) is not None

    created = await client.post(
        "/auth/register",
        json=SIGNUP | {"verification_token": await read_whatsapp_otp(E164)},
    )
    assert created.status_code == 201, created.text
    assert created.json()["user"]["phone_verified"] is True


async def test_an_explicit_channel_is_honoured_and_an_unavailable_one_refused(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """زرُّ «أرسله برسالة نصية» — ومنعُ استبدالٍ صامت."""
    await enable_whatsapp_provider(session_factory)
    await enable_sms_provider(session_factory)
    await _flip_whatsapp(client, admin_headers, True)

    chosen = await client.post(
        "/auth/challenge",
        json={"phone": PHONE, "country_code": "JO", "channel": "sms_otp"},
    )
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["channel"] == "sms_otp"

    await _flip_whatsapp(client, admin_headers, False)
    await fast_forward_otp_cooldown(E164)

    refused = await client.post(
        "/auth/challenge",
        json={"phone": PHONE, "country_code": "JO", "channel": "whatsapp_otp"},
    )
    assert refused.status_code == 400
    assert refused.json()["code"] == "verification_channel_unavailable"


async def test_a_failed_send_carries_the_next_channel(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    monkeypatch,
) -> None:
    """**رفضٌ بلا مخرجٍ ليس رفضاً**: الخطأ يحمل القناةَ التالية المتاحة.

    والقناةُ لا تُبدَّل في صمت: الرمزُ ربما وصل فعلاً، وتبديلٌ صامتٌ يجعل صاحبَه
    يقرأ رمزاً من قناةٍ ويكتب رمزاً من أخرى فيُحرق الرمزان.
    """
    from app.services.whatsapp import MockWhatsAppProvider
    from app.services.whatsapp.base import WhatsAppError

    await enable_whatsapp_provider(session_factory)
    await enable_sms_provider(session_factory)
    await _flip_whatsapp(client, admin_headers, True)

    async def _boom(self, to: str, code: str, **_: object) -> str:
        raise WhatsAppError("واتساب: القالب «taxo_otp» غير معتمد بعد")

    monkeypatch.setattr(MockWhatsAppProvider, "send_code", _boom)

    failed = await client.post(
        "/auth/challenge", json={"phone": PHONE, "country_code": "JO"}
    )
    assert failed.status_code == 502
    body = failed.json()
    assert body["code"] == "verification_send_failed"
    assert body["channel"] == "whatsapp_otp"
    assert body["fallback_channel"] == "sms_otp"
    # ونصُّ المزود يصل كما هو: «القالب غير معتمد» يوفّر على المشرف ساعةَ تخمين
    assert "القالب" in body["message"]

    # والمخرجُ يعمل فعلاً: القناةُ التالية تُرسل، والرمزُ يُقبل بلا سؤالٍ عن قناته
    await fast_forward_otp_cooldown(E164)
    fallback = await client.post(
        "/auth/challenge",
        json={"phone": PHONE, "country_code": "JO", "channel": "sms_otp"},
    )
    assert fallback.status_code == 200, fallback.text
    created = await client.post(
        "/auth/register", json=SIGNUP | {"verification_token": await read_otp(E164)}
    )
    assert created.status_code == 201, created.text


async def test_a_failed_send_with_no_other_channel_says_so(
    client: AsyncClient, admin_headers: dict, session_factory, monkeypatch
) -> None:
    """لا قناةَ أخرى — و`null` جوابٌ صادق لا حقلٌ ناقص.

    فالواجهةُ لا ترسم زرَّ ارتدادٍ لا يعمل، ومكانُ الإصلاح صفحةُ العقود.
    """
    from app.services.whatsapp import MockWhatsAppProvider
    from app.services.whatsapp.base import WhatsAppError

    await enable_whatsapp_provider(session_factory)
    await _flip_whatsapp(client, admin_headers, True)

    async def _boom(self, to: str, code: str, **_: object) -> str:
        raise WhatsAppError()

    monkeypatch.setattr(MockWhatsAppProvider, "send_code", _boom)

    failed = await client.post(
        "/auth/challenge", json={"phone": PHONE, "country_code": "JO"}
    )
    assert failed.status_code == 502
    assert failed.json()["fallback_channel"] is None


async def test_a_failed_send_leaves_no_live_code(
    client: AsyncClient, admin_headers: dict, session_factory, monkeypatch
) -> None:
    """قاعدةُ `otp.issue` تبقى: إرسالٌ فاشل يمحو الرمز.

    فلا يبقى رمزٌ حيٌّ لم يصل صاحبَه — ولو بقي لكان تخميناً مفتوحاً خمسَ دقائق.
    """
    from app.services.whatsapp import MockWhatsAppProvider
    from app.services.whatsapp.base import WhatsAppError

    await enable_whatsapp_provider(session_factory)
    await _flip_whatsapp(client, admin_headers, True)

    async def _boom(self, to: str, code: str, **_: object) -> str:
        raise WhatsAppError()

    monkeypatch.setattr(MockWhatsAppProvider, "send_code", _boom)
    await client.post("/auth/challenge", json={"phone": PHONE, "country_code": "JO"})

    created = await client.post(
        "/auth/register", json=SIGNUP | {"verification_token": "123456"}
    )
    assert created.status_code == 401
    assert created.json()["code"] == "invalid_otp"


# ------------------------------------------------------- زرُّ الاختبار


async def test_the_connection_test_leaves_no_trace_and_checks_the_template(
    client: AsyncClient, admin_headers: dict
) -> None:
    """زرُّ الاختبار في صفحة العقود — على المزود الوهمي بلا شبكة."""
    saved = await client.put(
        "/admin/providers/whatsapp",
        json={
            "values": {
                "phone_number_id": "111222333",
                "access_token": "wa-secret",
                "template_name": "taxo_otp",
                "waba_id": "999888777",
                "use_mock": True,
            },
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert saved.status_code == 200, saved.text
    # والسرُّ مقنَّعٌ في الجواب كبقية العقود
    assert saved.json()["values"]["access_token"] == "****"

    tested = await client.post(
        f"/admin/providers/{saved.json()['id']}/test",
        json={},
        headers=admin_headers,
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["ok"] is True
