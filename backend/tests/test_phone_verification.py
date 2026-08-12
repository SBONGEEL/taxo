"""إثبات ملكية الرقم: تسجيلٌ واستعادةٌ ومفتاح الطوارئ (المرحلة 8-ب).

OTP لم يعد طريقةَ دخول: الدخول كلمةُ مرور دائماً، والتحقق يقع في حدثين —
التسجيل والاستعادة. وهذا الملف يختبر الحدثين على المُحقِّقين معاً (Firebase
ومزود SMS التقليدي)، ويختبر مفتاح `otp_verification_enabled` وحدوده.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User
from app.services.firebase_auth import mock_token
from tests.helpers import (
    disable_provider,
    enable_sms_provider,
    fast_forward_otp_cooldown,
    read_otp,
)

PHONE = "0791234567"
E164 = "+962791234567"
PASSWORD = "SuperSecret123"
NEW_PASSWORD = "BrandNewSecret456"

SIGNUP = {
    "phone": PHONE,
    "name": "راكب التحقق",
    "password": PASSWORD,
    "country_code": "JO",
    "role": "rider",
}


async def _disable_firebase(session_factory) -> None:
    """يُطفئ عقد التحقق الذي يثبّته conftest — لاختبار المُحقِّق الثاني أو غيابه."""
    from sqlalchemy import update

    from app.models.enums import ProviderKey
    from app.models.provider_credential import ProviderCredential

    async with session_factory() as session:
        await session.execute(
            update(ProviderCredential)
            .where(ProviderCredential.provider_key == ProviderKey.FIREBASE_AUTH)
            .values(is_active=False)
        )
        await session.commit()


async def _set_verification_flag(
    client: AsyncClient, admin_headers: dict, enabled: bool, **extra
) -> None:
    response = await client.put(
        "/admin/settings/feature-flags",
        json={
            "country_code": "JO",
            "feature_key": "otp_verification_enabled",
            "enabled": enabled,
        }
        | extra,
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


async def _user(session_factory, phone: str = E164) -> User:
    async with session_factory() as session:
        return await session.scalar(select(User).where(User.phone == phone))


# ------------------------------------------------------------- التسجيل


async def test_signup_requires_proof_and_marks_the_account_verified(
    client: AsyncClient, session_factory
) -> None:
    denied = await client.post("/auth/register", json=SIGNUP)
    assert denied.status_code == 422
    assert denied.json()["code"] == "invalid_input"

    created = await client.post(
        "/auth/register", json=SIGNUP | {"verification_token": mock_token(E164)}
    )
    assert created.status_code == 201, created.text
    assert created.json()["user"]["phone_verified"] is True
    assert (await _user(session_factory)).phone_verified_at is not None


async def test_signup_proof_must_match_the_phone(client: AsyncClient) -> None:
    """رمزٌ صحيح لرقمٍ آخر لا يُنشئ حساباً بهذا الرقم."""
    response = await client.post(
        "/auth/register",
        json=SIGNUP | {"verification_token": mock_token("+962799999999")},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_id_token"


async def test_no_account_is_left_behind_by_a_rejected_proof(
    client: AsyncClient, session_factory
) -> None:
    """التحقق يسبق الإنشاء — فلا صفَّ نصفَ مُنشأ لرمزٍ لم يُقبل."""
    await client.post(
        "/auth/register", json=SIGNUP | {"verification_token": "garbage"}
    )
    assert await _user(session_factory) is None


async def test_login_after_signup_uses_the_password_not_a_token(
    client: AsyncClient,
) -> None:
    await client.post(
        "/auth/register", json=SIGNUP | {"verification_token": mock_token(E164)}
    )

    with_password = await client.post(
        "/auth/login",
        json={"phone": PHONE, "password": PASSWORD, "country_code": "JO"},
    )
    assert with_password.status_code == 200

    with_token = await client.post(
        "/auth/login",
        json={"phone": PHONE, "password": mock_token(E164), "country_code": "JO"},
    )
    assert with_token.status_code == 401


# --------------------------------------------- المُحقِّق الثاني (SMS)


async def test_sms_provider_serves_as_the_second_verifier(
    client: AsyncClient, session_factory
) -> None:
    """عقد SMS لم يمت بزوال OTP-as-login — صار المُحقِّق الثاني."""
    await _disable_firebase(session_factory)
    await enable_sms_provider(session_factory)

    assert (await client.get("/auth/method")).json() == {
        "login": "password",
        "verification": "sms_otp",
        "otp_length": 6,
        "channels": ["sms_otp"],
    }

    challenge = await client.post(
        "/auth/challenge", json={"phone": PHONE, "country_code": "JO"}
    )
    assert challenge.json()["sent"] is True

    created = await client.post(
        "/auth/register", json=SIGNUP | {"verification_token": await read_otp(E164)}
    )
    assert created.status_code == 201, created.text
    assert created.json()["user"]["phone_verified"] is True


async def test_the_sms_contract_now_wins_over_firebase(
    client: AsyncClient, session_factory
) -> None:
    """**تبدّلت الأولوية بقرار المالك في 12-هـ**: كان Firebase أولاً.

    والترتيبُ الآن `whatsapp_otp ← sms_otp ← firebase`، وتبعتُه صريحة: عقدُ
    Firebase مفعّلاً **لا يُستعمل** ما دام عقدُ رسائلٍ مفعّلاً — فمن أراده
    يُطفئ ما قبله. وهذا الاختبارُ هو ما يمنع «تصحيحاً» لاحقاً يعيد القديم.
    """
    await enable_sms_provider(session_factory)
    body = (await client.get("/auth/method")).json()
    assert body["verification"] == "sms_otp"
    # والقناتان معلنتان بترتيبهما: الثانيةُ مخرجٌ لا سرّ
    assert body["channels"] == ["sms_otp", "firebase"]

    await disable_provider(session_factory, "sms")
    assert (await client.get("/auth/method")).json()["verification"] == "firebase"


async def test_no_verifier_blocks_signup_loudly(
    client: AsyncClient, session_factory
) -> None:
    """«لا حساب يُنشأ برقم غير محقق» لا تُخرق لأن العقد غائب."""
    await _disable_firebase(session_factory)

    assert (await client.get("/auth/method")).json()["verification"] == "none"
    response = await client.post(
        "/auth/register", json=SIGNUP | {"verification_token": "anything"}
    )
    assert response.status_code == 503
    assert response.json()["code"] == "verification_unavailable"


# ------------------------------------------------- مفتاح الطوارئ


async def test_disabling_the_flag_allows_unverified_signup(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _set_verification_flag(
        client, admin_headers, False, reason="عطل عند مزود التحقق"
    )

    created = await client.post("/auth/register", json=SIGNUP)
    assert created.status_code == 201, created.text
    assert created.json()["user"]["phone_verified"] is False
    assert (await _user(session_factory)).phone_verified_at is None


async def test_disabling_the_flag_needs_a_written_reason(
    client: AsyncClient, admin_headers: dict
) -> None:
    """إجراءُ طوارئٍ يُسأل عنه — وسجلٌّ يقول «أُطفئ» بلا «لماذا» نصفُ سجل."""
    response = await client.put(
        "/admin/settings/feature-flags",
        json={
            "country_code": "JO",
            "feature_key": "otp_verification_enabled",
            "enabled": False,
        },
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert "سبب" in response.json()["detail"]


async def test_the_reason_is_recorded_in_the_audit_log(
    client: AsyncClient, admin_headers: dict
) -> None:
    await _set_verification_flag(
        client, admin_headers, False, reason="مزود التحقق متوقف منذ الصباح"
    )

    logs = (
        await client.get(
            "/admin/settings/audit-logs?entity_type=feature_flag",
            headers=admin_headers,
        )
    ).json()
    assert logs[0]["details"]["reason"] == "مزود التحقق متوقف منذ الصباح"
    assert logs[0]["details"]["enabled"] is False


async def test_the_flag_is_admin_only(
    client: AsyncClient, support_headers: dict
) -> None:
    response = await client.put(
        "/admin/settings/feature-flags",
        json={
            "country_code": "JO",
            "feature_key": "otp_verification_enabled",
            "enabled": False,
            "reason": "محاولة من دعم فني",
        },
        headers=support_headers,
    )
    assert response.status_code == 403


async def test_the_flag_defaults_to_enabled_without_a_row(
    client: AsyncClient, admin_headers: dict
) -> None:
    """الاستثناء الوحيد لقاعدة «غياب الصف = معطّل»: هذا حارسٌ لا ميزة."""
    flags = (
        await client.get("/admin/settings/feature-flags", headers=admin_headers)
    ).json()
    by_country = {row["country_code"]: row["flags"] for row in flags}
    assert by_country["JO"]["otp_verification_enabled"] is True
    assert by_country["LY"]["otp_verification_enabled"] is True
    # وبقية المفاتيح على القاعدة الأصلية
    assert by_country["LY"]["card_enabled"] is False


async def test_an_unverified_account_can_verify_later(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """ما يفعله التطبيق عند أول فرصة بعد إعادة تفعيل المفتاح."""
    await _set_verification_flag(client, admin_headers, False, reason="عطل مؤقت")
    created = await client.post("/auth/register", json=SIGNUP)
    headers = {"Authorization": f"Bearer {created.json()['tokens']['access_token']}"}

    await _set_verification_flag(client, admin_headers, True)

    verified = await client.post(
        "/auth/me/verify-phone",
        json={"verification_token": mock_token(E164)},
        headers=headers,
    )
    assert verified.status_code == 200
    assert verified.json()["phone_verified"] is True
    assert (await _user(session_factory)).phone_verified_at is not None


# ------------------------------------------- استعادة كلمة المرور


async def _signup(client: AsyncClient) -> dict:
    response = await client.post(
        "/auth/register", json=SIGNUP | {"verification_token": mock_token(E164)}
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_reset_requires_proof_then_sets_the_password(
    client: AsyncClient,
) -> None:
    await _signup(client)

    reset = await client.post(
        "/auth/password-reset",
        json={
            "phone": PHONE,
            "country_code": "JO",
            "verification_token": mock_token(E164),
            "new_password": NEW_PASSWORD,
        },
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["tokens"]["access_token"]

    old = await client.post(
        "/auth/login",
        json={"phone": PHONE, "password": PASSWORD, "country_code": "JO"},
    )
    assert old.status_code == 401

    new = await client.post(
        "/auth/login",
        json={"phone": PHONE, "password": NEW_PASSWORD, "country_code": "JO"},
    )
    assert new.status_code == 200


async def test_reset_without_proof_is_rejected(client: AsyncClient) -> None:
    await _signup(client)

    response = await client.post(
        "/auth/password-reset",
        json={
            "phone": PHONE,
            "country_code": "JO",
            "verification_token": mock_token("+962799999999"),
            "new_password": NEW_PASSWORD,
        },
    )
    assert response.status_code == 401


async def test_reset_still_requires_proof_when_the_flag_is_off(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**أخطر قاعدة في هذا الملف**: إطفاء المفتاح لا يعفي الاستعادة.

    لو أعفاها لصار إطفاءُ المفتاح طريقاً للاستيلاء على أي حساب بمعرفة رقمه.
    """
    await _signup(client)
    await _set_verification_flag(client, admin_headers, False, reason="عطل مؤقت")

    response = await client.post(
        "/auth/password-reset",
        json={
            "phone": PHONE,
            "country_code": "JO",
            "verification_token": "no-real-proof",
            "new_password": NEW_PASSWORD,
        },
    )
    assert response.status_code == 401

    # وكلمةُ المرور القديمة ما زالت تعمل
    assert (
        await client.post(
            "/auth/login",
            json={"phone": PHONE, "password": PASSWORD, "country_code": "JO"},
        )
    ).status_code == 200


async def test_reset_revokes_every_existing_session(
    client: AsyncClient,
) -> None:
    """كلمةٌ تُغيَّر لأن القديمة تسرّبت لا تُغيّر شيئاً إن بقيت جلسةُ من سرّبها."""
    body = await _signup(client)
    old_refresh = body["tokens"]["refresh_token"]

    await client.post(
        "/auth/password-reset",
        json={
            "phone": PHONE,
            "country_code": "JO",
            "verification_token": mock_token(E164),
            "new_password": NEW_PASSWORD,
        },
    )

    replay = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401
    assert replay.json()["code"] == "invalid_token"


async def test_reset_has_a_daily_cap_per_phone(client: AsyncClient) -> None:
    from app.routers.auth import PASSWORD_RESET_DAILY_LIMIT

    await _signup(client)

    for _ in range(PASSWORD_RESET_DAILY_LIMIT):
        await client.post(
            "/auth/password-reset/challenge",
            json={"phone": PHONE, "country_code": "JO"},
        )

    blocked = await client.post(
        "/auth/password-reset/challenge",
        json={"phone": PHONE, "country_code": "JO"},
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 3600  # نافذةٌ يومية لا ساعية


async def test_reset_challenge_does_not_reveal_whether_the_phone_exists(
    client: AsyncClient,
) -> None:
    known = await client.post(
        "/auth/password-reset/challenge", json={"phone": PHONE, "country_code": "JO"}
    )
    unknown = await client.post(
        "/auth/password-reset/challenge",
        json={"phone": "0799999999", "country_code": "JO"},
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


async def test_reset_over_the_sms_verifier(
    client: AsyncClient, session_factory
) -> None:
    """نفس المسار بالمُحقِّق الثاني — الرمزُ من رسالةٍ لا من Firebase."""
    await _signup(client)
    await _disable_firebase(session_factory)
    await enable_sms_provider(session_factory)

    await fast_forward_otp_cooldown(E164)
    challenge = await client.post(
        "/auth/password-reset/challenge", json={"phone": PHONE, "country_code": "JO"}
    )
    assert challenge.json()["sent"] is True

    reset = await client.post(
        "/auth/password-reset",
        json={
            "phone": PHONE,
            "country_code": "JO",
            "verification_token": await read_otp(E164),
            "new_password": NEW_PASSWORD,
        },
    )
    assert reset.status_code == 200, reset.text
