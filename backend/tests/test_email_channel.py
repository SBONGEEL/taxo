"""البريدُ قناةً بديلة — **والحسابُ المحدود** (قرارُ المالك 2026-08-31).

## ما يُقاس هنا، وكلُّه نقضُه لا يصيح

* **البريدُ يُثبت البريدَ لا الهاتف** — فلا يدخل سلسلةَ إثبات الرقم. **ونقضُ
  هذه وحدَها يفتح البابَ الذي بُني `otp_verification_enabled` ليغلقه**: حسابٌ
  كاملُ الصلاحية برقمٍ لم يملكه أحد.
* **والمفتاحُ لا يُشعَل بلا عقدٍ فعّال** — وإلا رُسم في التطبيق بابٌ يسقط عند
  أوّل ضغطة.
* **والحسابُ المحدود لا رحلةَ له ولا محفظة** — **والتحويلُ يُسأل من طرفيه**،
  فحارسٌ على المرسِل وحدَه يُلتفّ عليه بأن يستقبل بدل أن يرسل.
* **والرقمُ يُملَك من بابِ إثباتِ الرقم نفسِه** — لا من بابٍ ثالثٍ يُكتب له.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User
from tests.helpers import (
    email_code_of,
    fast_forward_email_cooldown,
    enable_email_provider,
    enable_features,
    register,
    rider_session,
)

EMAIL = "Sameer.Q@Example.COM"
PHONE = "0791239876"


def _signup(**overrides) -> dict:
    return {
        "phone": PHONE,
        "email": EMAIL,
        "name": "سمير الراكب",
        "password": "TaxoTest123",
        "country_code": "JO",
        "role": "rider",
    } | overrides


async def _open_channel(client: AsyncClient, session_factory) -> None:
    await enable_email_provider(session_factory)
    await enable_features(session_factory, "email_otp_enabled")


async def _challenge(client: AsyncClient, email: str = EMAIL) -> None:
    response = await client.post(
        "/auth/email/challenge", json={"email": email, "country_code": "JO"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["channel"] == "email_otp"


# ═════════════════════════════ ١) العقدُ والمفتاحُ معاً


async def test_channel_is_closed_by_default(
    client: AsyncClient, session_factory
) -> None:
    """**غيابُ الصفِّ إطفاء** — ولا يُضاف هذا المفتاحُ إلى المفعَّلة بالسكوت."""
    refused = await client.post(
        "/auth/email/challenge", json={"email": EMAIL, "country_code": "JO"}
    )
    assert refused.status_code == 400
    assert refused.json()["code"] == "verification_channel_unavailable"


async def test_contract_without_flag_keeps_it_closed(
    client: AsyncClient, session_factory
) -> None:
    """**العقدُ يقول «نستطيع»، والمفتاحُ «نفعل هنا»** — وواحدٌ لا يكفي."""
    await enable_email_provider(session_factory)
    refused = await client.post(
        "/auth/email/challenge", json={"email": EMAIL, "country_code": "JO"}
    )
    assert refused.status_code == 400


async def test_flag_without_contract_keeps_it_closed(
    client: AsyncClient, session_factory
) -> None:
    await enable_features(session_factory, "email_otp_enabled")
    refused = await client.post(
        "/auth/email/challenge", json={"email": EMAIL, "country_code": "JO"}
    )
    assert refused.status_code == 400


async def test_admin_cannot_light_the_flag_without_a_sender(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**زرٌّ بلا باب مقلوباً**: مفتاحٌ مشتعلٌ بلا مُرسِلٍ يرسم «سجّل ببريدك»
    في التطبيق **ثم يسقط عند أوّل ضغطة** — ومن يراه يجرّب ويظنّ العطبَ في
    بريده.
    """
    refused = await client.put(
        "/admin/settings/feature-flags",
        json={
            "country_code": "JO",
            "feature_key": "email_otp_enabled",
            "enabled": True,
        },
        headers=admin_headers,
    )
    assert refused.status_code == 422
    assert "عقدِ مُرسِلٍ فعّال" in refused.json()["message"]


async def test_admin_lights_it_once_a_sender_is_active(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    await enable_email_provider(session_factory)
    allowed = await client.put(
        "/admin/settings/feature-flags",
        json={
            "country_code": "JO",
            "feature_key": "email_otp_enabled",
            "enabled": True,
        },
        headers=admin_headers,
    )
    assert allowed.status_code == 200
    assert allowed.json()["flags"]["email_otp_enabled"] is True


async def test_config_publishes_the_channel_per_market(
    client: AsyncClient, session_factory
) -> None:
    """**بانٍ واحدٌ لبابين** — والتطبيقُ يقرأ الجوابَ لسوقه لا للافتراضيّ."""
    before = (await client.get("/config")).json()
    jordan = next(c for c in before["countries"] if c["country_code"] == "JO")
    assert jordan["email_signup"] is False

    await _open_channel(client, session_factory)
    after = (await client.get("/config")).json()
    jordan = next(c for c in after["countries"] if c["country_code"] == "JO")
    libya = next(c for c in after["countries"] if c["country_code"] == "LY")
    assert jordan["email_signup"] is True
    # **المفتاحُ per-country والعقدُ عامّ** — فليبيا مغلقةٌ والعقدُ نفسُه
    assert libya["email_signup"] is False


# ═════════════════════════ ٢) البريدُ لا يدخل سلسلةَ إثبات الرقم


async def test_email_is_never_a_phone_verifier(
    client: AsyncClient, session_factory
) -> None:
    """**وهذا هو أخطرُ ما في هذا الملفّ**: لو دخل `verification_channels`
    لَرسمت شاشةُ التسجيل بريداً **بديلاً عن إثبات الرقم**، فيُنشأ حسابٌ
    كاملُ الصلاحية برقمٍ لم يملكه أحد.
    """
    await _open_channel(client, session_factory)
    body = (await client.get("/config")).json()
    jordan = next(c for c in body["countries"] if c["country_code"] == "JO")

    assert "email_otp" not in jordan["verification_channels"]
    assert jordan["verification"] != "email_otp"
    # **وهو منشورٌ في حقله وحدَه** — فالتطبيقُ يعرفه ولا يخلطه
    assert jordan["email_signup"] is True


# ═══════════════════════════ ٣) الرمزُ والحسابُ المحدود


async def test_signup_by_email_opens_a_limited_account(
    client: AsyncClient, session_factory
) -> None:
    await _open_channel(client, session_factory)
    await _challenge(client)
    code = await email_code_of(EMAIL)

    created = await client.post(
        "/auth/register/email", json=_signup(email_code=code)
    )
    assert created.status_code == 201, created.text
    user = created.json()["user"]

    assert user["phone_pending"] is True
    assert user["phone_verified"] is False
    # **والعنوانُ يُخزَّن مطبَّعاً** — فبحثٌ بالنصِّ الخام لا يفوته
    assert user["email"] == EMAIL.lower()


async def test_a_limited_account_may_not_request_a_ride(
    client: AsyncClient, session_factory
) -> None:
    """**الرحلةُ تضع إنساناً في سيارةِ إنسان، والرقمُ هو ما يُتّصل به.**"""
    await _open_channel(client, session_factory)
    await _challenge(client)
    body = (
        await client.post(
            "/auth/register/email",
            json=_signup(email_code=await email_code_of(EMAIL)),
        )
    ).json()
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}

    refused = await client.post(
        "/rides",
        json={
            "pickup": {"lat": 31.95, "lng": 35.91},
            "dropoff": {"lat": 31.97, "lng": 35.86},
            "vehicle_category": "economy",
        },
        headers=headers,
    )
    assert refused.status_code == 403
    assert refused.json()["code"] == "phone_pending"


async def test_a_limited_account_may_not_top_up(
    client: AsyncClient, session_factory
) -> None:
    await _open_channel(client, session_factory)
    await enable_features(session_factory, "wallet_enabled")
    await _challenge(client)
    body = (
        await client.post(
            "/auth/register/email",
            json=_signup(email_code=await email_code_of(EMAIL)),
        )
    ).json()
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}

    refused = await client.post(
        "/wallet/me/topups",
        json={"method": "cliq", "amount": "10.000", "reference": "REF123"},
        headers=headers,
    )
    assert refused.status_code == 403
    assert refused.json()["code"] == "phone_pending"


async def test_transfer_is_refused_from_both_sides(
    client: AsyncClient, session_factory, rider_payload: dict
) -> None:
    """**حارسٌ على المرسِل وحدَه يُلتفّ عليه بأن يستقبل بدل أن يرسل.**"""
    from app.core.exceptions import AppError
    from app.services import wallet

    await _open_channel(client, session_factory)
    await _challenge(client)
    limited = (
        await client.post(
            "/auth/register/email",
            json=_signup(email_code=await email_code_of(EMAIL)),
        )
    ).json()
    full = await rider_session(client, rider_payload)

    async with session_factory() as session:
        limited_user = await session.get(User, limited["user"]["id"])
        full_user = await session.get(User, full["user"]["id"])

        for sender, recipient in (
            (limited_user, full_user),
            (full_user, limited_user),
        ):
            try:
                await wallet.transfer(
                    session,
                    sender=sender,
                    recipient=recipient,
                    amount=1,
                    idempotency_key="k",
                )
            except AppError as exc:
                assert exc.code == "phone_pending"
            else:  # pragma: no cover - الفشلُ هو الخبر
                raise AssertionError("مرّ تحويلٌ على حسابٍ محدود")


# ═══════════════════════ ٤) الرقمُ يُملَك من بابِ إثباتِ الرقم


async def test_verifying_the_phone_lifts_the_limit(
    client: AsyncClient, session_factory
) -> None:
    """**ولا بابَ ثالثٌ يُكتب له** — سؤالُه سؤالُ هذا الباب حرفاً."""
    from app.services.firebase_auth import mock_token
    from tests.helpers import enable_firebase_auth

    await _open_channel(client, session_factory)
    await enable_firebase_auth(session_factory)
    await _challenge(client)
    body = (
        await client.post(
            "/auth/register/email",
            json=_signup(email_code=await email_code_of(EMAIL)),
        )
    ).json()
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}

    lifted = await client.post(
        "/auth/me/verify-phone",
        json={"verification_token": mock_token("+962791239876")},
        headers=headers,
    )
    assert lifted.status_code == 200, lifted.text
    assert lifted.json()["phone_pending"] is False
    assert lifted.json()["phone_verified"] is True


# ═══════════════════════════════ ٥) العنوانُ نفسُه


async def test_a_verified_email_is_taken_case_insensitively(
    client: AsyncClient, session_factory
) -> None:
    """`Ali@X.com` و`ali@x.com` **صندوقٌ واحد** — وحسابان عليه ازدواج."""
    await _open_channel(client, session_factory)
    await _challenge(client)
    first = await client.post(
        "/auth/register/email", json=_signup(email_code=await email_code_of(EMAIL))
    )
    assert first.status_code == 201

    other = EMAIL.lower()
    # **العنوانُ واحدٌ فمهلتُه واحدة** — والمقيسُ هنا الفهرسُ لا المهلة
    await fast_forward_email_cooldown(other)
    await _challenge(client, other)
    second = await client.post(
        "/auth/register/email",
        json=_signup(
            phone="0791239877",
            email=other,
            email_code=await email_code_of(other),
        ),
    )
    assert second.status_code == 409


async def test_a_malformed_address_is_refused_before_anything_is_sent(
    client: AsyncClient, session_factory
) -> None:
    await _open_channel(client, session_factory)
    refused = await client.post(
        "/auth/email/challenge",
        json={"email": "لا-بريد-هنا", "country_code": "JO"},
    )
    assert refused.status_code == 422
    assert refused.json()["code"] == "invalid_input"


async def test_a_stale_code_does_not_survive_the_flag_being_switched_off(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**مفتاحٌ يُطفأ بين الإرسال والتسجيل** يترك رمزاً حيّاً يفتح باباً أُغلق."""
    await _open_channel(client, session_factory)
    await _challenge(client)
    code = await email_code_of(EMAIL)

    await client.put(
        "/admin/settings/feature-flags",
        json={
            "country_code": "JO",
            "feature_key": "email_otp_enabled",
            "enabled": False,
        },
        headers=admin_headers,
    )

    refused = await client.post(
        "/auth/register/email", json=_signup(email_code=code)
    )
    assert refused.status_code == 422
