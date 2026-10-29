"""الرقمُ نفسُه راكباً وكبتناً (أمرُ المالك ٢٠٢٦-١٠-٢٩، SPEC §21.6).

ما يُقاس: التسجيلُ برقمٍ له الدورُ الآخر يُدلّ على الدخول لا يُنشئ حساباً · الدخولُ يعرض إضافةَ الملفّ برمزٍ مرّةً واحدةً
ولتطبيقه · الإضافةُ صفُّ دورٍ وكبتنٌ `pending` ولا شيءَ غيرهما · المحفظتان منفصلتان · لا يُطابَق الشخصُ مع نفسه · لا مكافأةَ لإحالة
النفس · حظرُ الراكب لا يحظر الكبتن · وحسابٌ بعاملٍ ثانٍ لا يُعرض عليه البابُ بكلمة المرور وحدَها.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.driver import Driver
from app.models.enums import DriverStatus, UserRole, WalletOwnerType, WalletTransactionType
from app.models.user import User
from tests.helpers import DRIVER, RIDER, approved_driver, auth, register

pytestmark = pytest.mark.asyncio


def _login(payload: dict, app: str) -> dict:
    return {"phone": payload["phone"], "password": payload["password"], "country_code": payload["country_code"], "app": app}


async def _enroll(client: AsyncClient, payload: dict, app: str) -> dict:
    offered = await client.post("/auth/login", json=_login(payload, app))
    assert offered.status_code == 403, offered.text
    assert offered.json()["code"] == "role_can_be_added", offered.text
    token = offered.json()["enroll_token"]
    added = await client.post("/auth/enroll", json={"token": token, "app": app})
    assert added.status_code == 200, added.text
    return added.json()


def _register_body(payload: dict) -> dict:
    from app.core.phone import normalize_phone
    from app.services.firebase_auth import mock_token

    return payload | {"verification_token": mock_token(normalize_phone(payload["phone"], payload["country_code"]))}


async def _users_with_phone(session_factory, phone_fragment: str) -> int:
    async with session_factory() as session:
        return int(await session.scalar(select(func.count()).select_from(User).where(User.phone.like(f"%{phone_fragment}"))) or 0)


async def test_a_rider_becomes_a_captain_with_the_same_number(client: AsyncClient, session_factory) -> None:
    rider = await register(client, RIDER)
    # **التسجيلُ في تطبيق الكبتن بالرقم نفسِه لا يُنشئ حساباً** — يُدلّ على الدخول
    again = await client.post("/auth/register", json=_register_body(DRIVER | {"phone": RIDER["phone"], "app": "driver"}))
    assert again.status_code == 409 and again.json()["code"] == "phone_has_other_role", again.text
    assert await _users_with_phone(session_factory, RIDER["phone"][1:]) == 1

    body = await _enroll(client, RIDER, "driver")
    assert body["user"]["id"] == rider["user"]["id"]
    assert set(body["user"]["roles"]) == {"rider", "driver"}
    async with session_factory() as session:
        driver = await session.scalar(select(Driver).where(Driver.user_id == uuid.UUID(rider["user"]["id"])))
        # **كبتنٌ ينتظر مستنداتِه ومركبتَه وموافقةَ الإدارة** — الإضافةُ لا تمنح موافقة
        assert driver is not None and driver.status is DriverStatus.PENDING
    me = await client.get("/drivers/me", headers=auth(body))
    assert me.status_code == 200, me.text
    # **وتطبيقُ الراكب يفتح ملفَّ الراكب كما كان** — الحسابُ نفسُه
    rider_login = await client.post("/auth/login", json=_login(RIDER, "rider"))
    assert rider_login.status_code == 200 and rider_login.json()["user"]["id"] == rider["user"]["id"]
    assert await _users_with_phone(session_factory, RIDER["phone"][1:]) == 1


async def test_a_captain_becomes_a_rider_with_the_same_number(client: AsyncClient, session_factory) -> None:
    captain = await register(client, DRIVER)
    again = await client.post("/auth/register", json=_register_body(RIDER | {"phone": DRIVER["phone"], "app": "rider"}))
    assert again.status_code == 409 and again.json()["code"] == "phone_has_other_role", again.text
    body = await _enroll(client, DRIVER, "rider")
    assert body["user"]["id"] == captain["user"]["id"] and set(body["user"]["roles"]) == {"rider", "driver"}
    assert (await client.post("/auth/login", json=_login(DRIVER, "driver"))).status_code == 200
    assert (await client.get("/wallet/me?wallet=rider", headers=auth(body))).status_code == 200


async def test_the_enroll_token_is_single_use_and_for_its_app(client: AsyncClient) -> None:
    await register(client, RIDER)
    token = (await client.post("/auth/login", json=_login(RIDER, "driver"))).json()["enroll_token"]
    wrong = await client.post("/auth/enroll", json={"token": token, "app": "rider"})
    assert wrong.status_code == 401, wrong.text
    token = (await client.post("/auth/login", json=_login(RIDER, "driver"))).json()["enroll_token"]
    assert (await client.post("/auth/enroll", json={"token": token, "app": "driver"})).status_code == 200
    assert (await client.post("/auth/enroll", json={"token": token, "app": "driver"})).status_code == 401
    # **ولا يُعرض ثانيةً**: الحسابُ صار كبتناً فيدخل مباشرةً
    assert (await client.post("/auth/login", json=_login(RIDER, "driver"))).status_code == 200


async def test_the_two_wallets_stay_separate(client: AsyncClient, session_factory) -> None:
    """**لا تحويلَ بين المحفظتين** — رصيدُ الراكب لا يظهر في محفظة الكبتن، ومحفظةُ الكبتن الجديدة صفر."""
    from app.services import wallet

    rider = await register(client, RIDER)
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(rider["user"]["id"]))
        await wallet.record(session, owner=user, owner_type=WalletOwnerType.RIDER, tx_type=WalletTransactionType.TOPUP,
                            amount=Decimal("7.000"), reference="اختبار", idempotency_key="dual-role-test-topup")
        await session.commit()
    body = await _enroll(client, RIDER, "driver")
    headers = auth(body)
    rider_wallet = (await client.get("/wallet/me?wallet=rider", headers=headers)).json()
    driver_wallet = (await client.get("/wallet/me?wallet=driver", headers=headers)).json()
    assert Decimal(rider_wallet["balance"]) == Decimal("7")
    assert Decimal(driver_wallet["balance"]) == Decimal("0")


async def test_a_person_is_never_matched_with_himself(client: AsyncClient, session_factory) -> None:
    from app.services import dispatch

    captain = await approved_driver(client, session_factory)
    await _enroll(client, DRIVER, "rider")
    driver_id = uuid.UUID(str(captain["driver_id"]))
    async with session_factory() as session:
        row = await session.get(Driver, driver_id)
        row.is_online = True
        await session.commit()
    async with session_factory() as session:
        anyone = await dispatch._eligible_levels(session, [driver_id], "economy")
        himself = await dispatch._eligible_levels(session, [driver_id], "economy", rider_user_id=uuid.UUID(captain["user_id"]))
        other = await dispatch._eligible_levels(session, [driver_id], "economy", rider_user_id=uuid.uuid4())
    assert driver_id in anyone, "الكبتنُ غيرُ مؤهَّلٍ أصلاً — الاختبارُ لا يقيس شيئاً"
    assert driver_id not in himself
    assert driver_id in other


async def test_a_self_referral_cannot_exist_across_roles(session_factory, client: AsyncClient) -> None:
    """**الشخصُ حسابٌ واحدٌ بدورين** — فإحالةُ نفسه عبر الدورين صفٌّ واحدُ الطرفين، **والقاعدةُ ترفضه بقيدها** (وتحته `attach` يرفض،
    وفوقه `pay` لا يدفع). والدورُ الثاني لا يُسنَد له رمزٌ أصلاً (`role_enrollment` لا يمرّ بـ`attach`)."""
    from sqlalchemy.exc import IntegrityError

    from app.models.referral import Referral

    rider = await register(client, RIDER)
    await _enroll(client, RIDER, "driver")
    async with session_factory() as session:
        session.add(Referral(referrer_user_id=uuid.UUID(rider["user"]["id"]), referred_user_id=uuid.UUID(rider["user"]["id"]),
                             code_used="SELFTEST"))
        with pytest.raises(IntegrityError):
            await session.commit()
    async with session_factory() as session:
        assert int(await session.scalar(select(func.count()).select_from(Referral)) or 0) == 0


async def test_blocking_the_rider_role_keeps_the_captain_working(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    rider = await register(client, RIDER)
    await _enroll(client, RIDER, "driver")
    blocked = await client.post(f"/admin/users/{rider['user']['id']}/rider-block", json={"reason": "اختبار"}, headers=admin_headers)
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["is_blocked"] is False and blocked.json()["rider_blocked_at"] is not None
    assert (await client.post("/auth/login", json=_login(RIDER, "rider"))).status_code == 403
    driver_login = await client.post("/auth/login", json=_login(RIDER, "driver"))
    assert driver_login.status_code == 200, driver_login.text
    assert (await client.get("/drivers/me", headers=auth(driver_login.json()))).status_code == 200
    # **ورفعُه يعيده** — وحظرُ الشخص كلِّه يغلق التطبيقين
    await client.post(f"/admin/users/{rider['user']['id']}/rider-unblock", json={}, headers=admin_headers)
    assert (await client.post("/auth/login", json=_login(RIDER, "rider"))).status_code == 200
    await client.post(f"/admin/users/{rider['user']['id']}/block", json={"reason": "اختبار"}, headers=admin_headers)
    assert (await client.post("/auth/login", json=_login(RIDER, "rider"))).status_code != 200
    assert (await client.post("/auth/login", json=_login(RIDER, "driver"))).status_code != 200


async def test_an_account_with_a_second_factor_is_not_offered_by_password_alone(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import totp

    await register(client, RIDER)

    async def confirmed(session, user_id) -> bool:
        return True

    monkeypatch.setattr(totp, "has_confirmed_factor", confirmed)
    refused = await client.post("/auth/login", json=_login(RIDER, "driver"))
    assert refused.status_code == 403 and refused.json()["code"] == "wrong_app_for_role", refused.text
