"""الدخول والتسجيل برمز OTP بعد تفعيل عقد الرسائل (SPEC القسم 15/أ)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import (
    enable_sms_provider,
    fast_forward_otp_cooldown,
    read_otp,
)

PHONE = "0791234567"
E164 = "+962791234567"

REGISTER = {
    "phone": PHONE,
    "name": "راكب الرمز",
    "country_code": "JO",
    "role": "rider",
}


async def _challenge(client: AsyncClient, phone: str = PHONE) -> dict:
    await fast_forward_otp_cooldown(E164)
    response = await client.post(
        "/auth/challenge", json={"phone": phone, "country_code": "JO"}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _register_with_otp(client: AsyncClient, **overrides) -> dict:
    await _challenge(client, overrides.get("phone", PHONE))
    code = await read_otp(overrides.get("e164", E164))
    payload = REGISTER | {
        key: value for key, value in overrides.items() if key not in {"e164"}
    }
    response = await client.post("/auth/register", json=payload | {"password": code})
    assert response.status_code == 201, response.text
    return response.json()


# ------------------------------------------------------- وضع كلمة المرور


async def test_challenge_in_password_mode_sends_nothing(client: AsyncClient) -> None:
    """المسار قائمٌ دائماً — الواجهة تسأل قبل أن تعرف الاستراتيجية."""
    body = await _challenge(client)
    assert body == {"sent": False, "expires_in": None, "resend_after": None}


async def test_password_policy_lives_in_the_strategy_not_the_schema(
    client: AsyncClient,
) -> None:
    """المخطط يقبل ستة أرقام (رمز OTP)، والسياسة ترفضها كلمةَ مرور."""
    response = await client.post(
        "/auth/register", json=REGISTER | {"password": "123456"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


# ------------------------------------------------------------- وضع OTP


async def test_register_and_login_with_otp(
    client: AsyncClient, session_factory
) -> None:
    await enable_sms_provider(session_factory)
    assert (await client.get("/auth/method")).json() == {
        "method": "otp",
        "otp_length": 6,
    }

    body = await _register_with_otp(client)
    assert body["user"]["phone"] == E164
    assert body["tokens"]["access_token"]

    # الحساب بلا كلمة مرور — العمود nullable لهذا بالضبط
    from sqlalchemy import select

    from app.models.user import User

    async with session_factory() as session:
        stored = await session.scalar(select(User).where(User.phone == E164))
    assert stored.password_hash is None

    await _challenge(client)
    login = await client.post(
        "/auth/login",
        json={"phone": PHONE, "password": await read_otp(E164), "country_code": "JO"},
    )
    assert login.status_code == 200, login.text
    assert login.json()["user"]["id"] == body["user"]["id"]


async def test_wrong_code_is_rejected_and_right_one_still_works(
    client: AsyncClient, session_factory
) -> None:
    await enable_sms_provider(session_factory)
    await _register_with_otp(client)

    await _challenge(client)
    code = await read_otp(E164)
    wrong = "".join("0" if digit != "0" else "1" for digit in code)

    denied = await client.post(
        "/auth/login",
        json={"phone": PHONE, "password": wrong, "country_code": "JO"},
    )
    assert denied.status_code == 401
    assert denied.json()["code"] == "invalid_otp"

    accepted = await client.post(
        "/auth/login", json={"phone": PHONE, "password": code, "country_code": "JO"}
    )
    assert accepted.status_code == 200


async def test_code_is_consumed_after_use(
    client: AsyncClient, session_factory
) -> None:
    """رمزٌ يُقبل مرتين رمزٌ يُعاد استعماله بعد أن رآه غير صاحبه."""
    await enable_sms_provider(session_factory)
    await _register_with_otp(client)

    await _challenge(client)
    code = await read_otp(E164)
    first = await client.post(
        "/auth/login", json={"phone": PHONE, "password": code, "country_code": "JO"}
    )
    assert first.status_code == 200

    replay = await client.post(
        "/auth/login", json={"phone": PHONE, "password": code, "country_code": "JO"}
    )
    assert replay.status_code == 401


async def test_attempts_burn_the_code(
    client: AsyncClient, session_factory
) -> None:
    from app.services import otp

    await enable_sms_provider(session_factory)
    await _register_with_otp(client)

    await _challenge(client)
    code = await read_otp(E164)

    for _ in range(otp.MAX_ATTEMPTS):
        denied = await client.post(
            "/auth/login",
            json={"phone": PHONE, "password": "000000", "country_code": "JO"},
        )
        assert denied.status_code in (401, 429)

    # الرمز الصحيح نفسه لم يعد يعمل: العدّاد يحرق الرمز لا المحاولة وحدها
    burned = await client.post(
        "/auth/login", json={"phone": PHONE, "password": code, "country_code": "JO"}
    )
    assert burned.status_code in (401, 429)


async def test_resend_has_a_cooldown(
    client: AsyncClient, session_factory
) -> None:
    await enable_sms_provider(session_factory)
    await _challenge(client)

    # بلا تقديمٍ للساعة هذه المرة: الحارس نفسه هو المُختبَر
    again = await client.post(
        "/auth/challenge", json={"phone": PHONE, "country_code": "JO"}
    )
    assert again.status_code == 429
    assert again.json()["code"] == "rate_limited"
    assert int(again.headers["Retry-After"]) > 0


async def test_valid_code_for_unregistered_phone_does_not_create_an_account(
    client: AsyncClient, session_factory
) -> None:
    await enable_sms_provider(session_factory)
    await _challenge(client)

    response = await client.post(
        "/auth/login",
        json={"phone": PHONE, "password": await read_otp(E164), "country_code": "JO"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "account_not_registered"


async def test_registering_twice_is_rejected(
    client: AsyncClient, session_factory
) -> None:
    await enable_sms_provider(session_factory)
    await _register_with_otp(client)

    await _challenge(client)
    response = await client.post(
        "/auth/register",
        json=REGISTER | {"password": await read_otp(E164)},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "phone_already_registered"


async def test_otp_account_cannot_log_in_with_a_password_after_sms_is_disabled(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """حسابٌ بلا كلمة مرور لا يُفتح بواحدةٍ يخترعها المهاجم."""
    await enable_sms_provider(session_factory)
    await _register_with_otp(client)

    catalog = (await client.get("/admin/providers", headers=admin_headers)).json()
    credential = next(
        row for row in catalog["credentials"] if row["provider_key"] == "sms"
    )
    await client.post(
        f"/admin/providers/{credential['id']}/deactivate", headers=admin_headers
    )
    assert (await client.get("/auth/method")).json()["method"] == "password"

    denied = await client.post(
        "/auth/login",
        json={"phone": PHONE, "password": "AnyPassword123", "country_code": "JO"},
    )
    assert denied.status_code == 401
    assert denied.json()["code"] == "invalid_credentials"


async def test_challenge_without_sms_contract_after_activation_is_503(
    client: AsyncClient, session_factory
) -> None:
    """عقدٌ مفعّل بلا حقول كافية: 503 لا انهيار."""
    await enable_sms_provider(session_factory, use_mock=False, endpoint="")

    response = await client.post(
        "/auth/challenge", json={"phone": PHONE, "country_code": "JO"}
    )
    assert response.status_code == 503
    assert response.json()["code"] == "sms_unavailable"
