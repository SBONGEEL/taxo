from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.models.driver import Driver
from app.models.user import User


async def test_login_is_always_password_and_verification_is_firebase(
    client: AsyncClient,
) -> None:
    """الدخول ثابتٌ والمُحقِّق متغيّر (المرحلة 8-ب).

    عقد التحقق الوهمي مثبَّت في كل اختبار، فالمُحقِّق `firebase`.
    """
    response = await client.get("/auth/method")
    assert response.status_code == 200
    assert response.json() == {
        "login": "password",
        "verification": "firebase",
        "otp_length": None,
    }


async def test_register_returns_user_and_tokens(
    client: AsyncClient, rider_payload: dict
) -> None:
    response = await client.post("/auth/register", json=rider_payload)
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["user"]["phone"] == "+962791234567"  # مطبّع لصيغة E.164
    assert body["user"]["role"] == "rider"
    assert body["user"]["country_code"] == "JO"
    assert body["user"]["is_blocked"] is False
    assert "password" not in str(body["user"])
    assert body["tokens"]["access_token"] and body["tokens"]["refresh_token"]


async def test_password_hash_never_leaves_the_backend(
    client: AsyncClient, rider_payload: dict, session_factory
) -> None:
    await client.post("/auth/register", json=rider_payload)
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.phone == "+962791234567"))
    assert user is not None
    assert user.password_hash and user.password_hash.startswith("$2b$")
    assert rider_payload["password"] not in user.password_hash


async def test_register_rejects_duplicate_phone(
    client: AsyncClient, rider_payload: dict
) -> None:
    assert (await client.post("/auth/register", json=rider_payload)).status_code == 201

    # صيغة محلية مختلفة لنفس الرقم — يجب أن تُرفض بعد التطبيع
    duplicate = rider_payload | {"phone": "+962 79 123 4567"}
    response = await client.post("/auth/register", json=duplicate)
    assert response.status_code == 409
    assert response.json()["code"] == "phone_already_registered"


async def test_register_rejects_invalid_phone(
    client: AsyncClient, rider_payload: dict
) -> None:
    response = await client.post("/auth/register", json=rider_payload | {"phone": "0612345678"})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_register_rejects_admin_role(
    client: AsyncClient, rider_payload: dict
) -> None:
    """حسابات admin/support لا تُنشأ عبر التسجيل الذاتي."""
    response = await client.post("/auth/register", json=rider_payload | {"role": "admin"})
    assert response.status_code == 422


async def test_register_driver_creates_pending_driver_profile(
    client: AsyncClient, driver_payload: dict, session_factory
) -> None:
    response = await client.post("/auth/register", json=driver_payload)
    assert response.status_code == 201
    user_id = response.json()["user"]["id"]

    async with session_factory() as session:
        driver = await session.scalar(select(Driver).where(Driver.user_id == user_id))
    assert driver is not None
    assert driver.status.value == "pending"
    assert driver.is_online is False


async def test_login_success(client: AsyncClient, rider_payload: dict) -> None:
    await client.post("/auth/register", json=rider_payload)

    response = await client.post(
        "/auth/login",
        json={"phone": "0791234567", "password": rider_payload["password"], "country_code": "JO"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["phone"] == "+962791234567"


async def test_login_works_with_international_format_without_country(
    client: AsyncClient, rider_payload: dict
) -> None:
    await client.post("/auth/register", json=rider_payload)
    response = await client.post(
        "/auth/login",
        json={"phone": "+962791234567", "password": rider_payload["password"]},
    )
    assert response.status_code == 200


async def test_login_with_wrong_password(client: AsyncClient, rider_payload: dict) -> None:
    await client.post("/auth/register", json=rider_payload)
    response = await client.post(
        "/auth/login",
        json={"phone": "+962791234567", "password": "not-the-password"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_login_unknown_phone_gives_same_error_as_wrong_password(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/auth/login", json={"phone": "+962799999999", "password": "whatever123"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_blocked_user_cannot_login(
    client: AsyncClient, rider_payload: dict, session_factory
) -> None:
    await client.post("/auth/register", json=rider_payload)
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.phone == "+962791234567"))
        user.is_blocked = True
        await session.commit()

    response = await client.post(
        "/auth/login",
        json={"phone": "+962791234567", "password": rider_payload["password"]},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "account_blocked"


async def test_login_rate_limit_kicks_in(client: AsyncClient, rider_payload: dict) -> None:
    await client.post("/auth/register", json=rider_payload)

    codes = []
    for _ in range(7):
        response = await client.post(
            "/auth/login", json={"phone": "+962791234567", "password": "wrong-pass"}
        )
        codes.append(response.status_code)

    assert 429 in codes, codes
    # لا يُحظر إلا بعد استنفاد المحاولات المسموحة
    assert codes[0] == 401


async def test_me_requires_token(client: AsyncClient) -> None:
    assert (await client.get("/auth/me")).status_code == 401


async def test_me_returns_current_user(client: AsyncClient, rider_payload: dict) -> None:
    tokens = (await client.post("/auth/register", json=rider_payload)).json()["tokens"]
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "+962791234567"


async def test_me_rejects_refresh_token_used_as_access(
    client: AsyncClient, rider_payload: dict
) -> None:
    tokens = (await client.post("/auth/register", json=rider_payload)).json()["tokens"]
    response = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert response.status_code == 401


async def test_refresh_rotates_and_invalidates_old_token(
    client: AsyncClient, rider_payload: dict
) -> None:
    tokens = (await client.post("/auth/register", json=rider_payload)).json()["tokens"]

    first = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    new_tokens = first.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # إعادة استخدام التوكن القديم مرفوضة
    replay = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401

    # الجديد يعمل
    assert (
        await client.post("/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    ).status_code == 200


async def test_logout_revokes_refresh_token(
    client: AsyncClient, rider_payload: dict
) -> None:
    tokens = (await client.post("/auth/register", json=rider_payload)).json()["tokens"]

    logout = await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout.status_code == 204

    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401


async def test_blocked_user_cannot_refresh(
    client: AsyncClient, rider_payload: dict, session_factory
) -> None:
    tokens = (await client.post("/auth/register", json=rider_payload)).json()["tokens"]
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.phone == "+962791234567"))
        user.is_blocked = True
        await session.commit()

    response = await client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401
