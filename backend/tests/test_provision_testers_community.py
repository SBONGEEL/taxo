"""حسابا Testers Community (SPEC §٧٨) — **يُقاس على ما وعد به المالك، وكلُّ وعدٍ يسقط بحذف ما يحرسه**.

١) **عائلتان باسم «Testers Community»** بأسواقها الثلاثة — موسومةً، مُثبتةَ الأرقام، **والدخولُ بكلمةٍ بلا رسالة**؛ والكبتنُ معتمدٌ مغطّى.
٢) **رصيدُ التجربة** لكلِّ فرد، **وقائمةُ السماح لكلِّ فرد** (يعملان من أيِّ دولة)، **ولا دورَ إداريّاً**.
٣) **كلمةُ المرور لا تُغيَّر من التطبيق، ولا يُطلب الحذف** — `LockedOnTestAccount` في الخدمتين.
٤) **ولا تحويلَ ولا شحنَ حقيقيّاً** — البابان القائمان يردّانهما.
٥) **وإعادةُ الضبط**: كلمةٌ جديدةٌ تعمل، والقديمةُ لا، **وجلساتُ العائلة كلُّها أُبطلت**.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import LockedOnTestAccount, NoRealMoneyOnTestAccount
from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.enums import CountryCode, DriverStatus, UserRole
from app.models.market import BorderAllowance
from app.models.user import User
from app.services import subscriptions, test_markets, wallet
from app.services.auth.password import set_password
from scripts import provision_test_accounts
from scripts import provision_testers_community as script
from tests.helpers import ensure_plan

pytestmark = pytest.mark.asyncio


@pytest.fixture
def _no_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import sms, whatsapp

    async def _forbidden(*_args, **_kwargs):
        raise AssertionError("السكربتُ نادى مزوّدَ رسائل — والأرقامُ لا تُراسَل")

    monkeypatch.setattr(sms, "get_sms_provider", _forbidden)
    monkeypatch.setattr(whatsapp, "get_whatsapp_provider", _forbidden)
    monkeypatch.setattr(whatsapp, "get_provider_or_none", _forbidden)


@pytest.fixture
def _secrets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(provision_test_accounts, "_EPHEMERAL_ROOTS", ())
    return tmp_path


def _values(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith("#"))


async def _login(client: AsyncClient, phone: str, password: str):
    return await client.post("/auth/login", json={"phone": phone, "password": password})


def _bearer(response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['tokens']['access_token']}"}


async def _provision(session_factory, secrets_dir: Path) -> dict[str, str]:
    await ensure_plan(session_factory)
    await ensure_plan(session_factory, country="LY", name="خطة ليبيا الشهرية", price="100.000")
    secrets_file = secrets_dir / "testers-community.env"
    outcome = await script.create(secrets_file=secrets_file, session_factory=session_factory)
    assert outcome.created is True and len(outcome.ids) == 6
    return _values(secrets_file)


async def test_two_testers_community_families_are_isolated_test_accounts(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    _secrets_dir: Path,
    capsys: pytest.CaptureFixture[str],
    _no_messages: None,
) -> None:
    values = await _provision(session_factory, _secrets_dir)
    printed = capsys.readouterr().out
    assert len(values) == 12
    assert all(value not in printed for key, value in values.items() if key.endswith("_PASSWORD"))

    # ── الدخولُ بكلمةٍ بلا رسالة، موسوماً، والمُختارُ يرى الأسواقَ الثلاثة ──
    for label in ("TC_RIDER_JO", "TC_CAPTAIN_JO"):
        login = await _login(client, values[f"{label}_PHONE"], values[f"{label}_PASSWORD"])
        assert login.status_code == 200, login.text
        assert login.json()["user"]["is_test"] is True
        markets = (await client.get("/auth/test-markets", headers=_bearer(login))).json()["markets"]
        assert {row["country_code"] for row in markets} == {"JO", "LY", "DZ"}

    async with session_factory() as session:
        users = list(await session.scalars(select(User).where(User.name == script.NAME)))
        assert len(users) == 6 and all(user.is_test for user in users)
        # **لا دورَ إداريّاً** — راكبٌ أو كبتنٌ وحدَه
        assert {user.role for user in users} == {UserRole.RIDER, UserRole.DRIVER}
        assert not any(user.has_role(UserRole.ADMIN) for user in users)

        allowed = set(await session.scalars(select(BorderAllowance.user_id).where(BorderAllowance.revoked_at.is_(None))))
        for user in users:
            assert user.id in allowed, user.phone
            balance = await wallet.balance(session, user.id, wallet.owner_type_for(user))
            assert balance == test_markets.TEST_FUNDS[CountryCode(user.country_code)], user.phone
            if user.role is UserRole.DRIVER:
                driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
                assert driver.status is DriverStatus.APPROVED
                assert await subscriptions.current_subscription(session, driver.id) is not None

    # ── لا تحويل: الرصيدُ التجريبيُّ لا يغادر — **بالخدمة نفسِها**: بابُ التطبيق يبحث عن المستلم بين الركّاب قبل أن يسأل عن التجربة ──
    async with session_factory() as session:
        sender = await session.scalar(select(User).where(User.phone == values["TC_RIDER_JO_PHONE"]))
        recipient = await session.scalar(select(User).where(User.phone == values["TC_RIDER_LY_PHONE"]))
        with pytest.raises(NoRealMoneyOnTestAccount):
            await wallet.transfer(
                session, sender=sender, recipient=recipient, amount=Decimal("1.000"), idempotency_key="tc-transfer-0001"
            )
        await session.rollback()

    rider = await _login(client, values["TC_RIDER_JO_PHONE"], values["TC_RIDER_JO_PASSWORD"])
    # ── ولا حذف من التطبيق ──
    deletion = await client.post("/account/deletion", json={"forfeit_amount": None}, headers=_bearer(rider))
    assert deletion.status_code == 403, deletion.text
    assert deletion.json()["code"] == "test_account_locked"


async def test_the_password_of_a_test_account_cannot_be_changed_from_the_app(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    _secrets_dir: Path,
    _no_messages: None,
) -> None:
    values = await _provision(session_factory, _secrets_dir)
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.phone == values["TC_RIDER_JO_PHONE"]))
        with pytest.raises(LockedOnTestAccount):
            await set_password(session, get_redis_client(), user=user, new_password="Another-strong-pass-91")
        await session.rollback()

    # **والكلمةُ القديمةُ ما زالت تعمل** — الردُّ قبل الكتابة
    login = await _login(client, values["TC_RIDER_JO_PHONE"], values["TC_RIDER_JO_PASSWORD"])
    assert login.status_code == 200, login.text


async def test_reset_gives_a_new_password_and_signs_the_whole_family_out(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    _secrets_dir: Path,
    capsys: pytest.CaptureFixture[str],
    _no_messages: None,
) -> None:
    values = await _provision(session_factory, _secrets_dir)
    phone, old = values["TC_CAPTAIN_JO_PHONE"], values["TC_CAPTAIN_JO_PASSWORD"]
    before = await _login(client, phone, old)
    assert before.status_code == 200
    capsys.readouterr()

    fresh = _secrets_dir / "testers-community-reset.env"
    await script.reset(
        "TC_CAPTAIN", secrets_file=fresh, redis=get_redis_client(), session_factory=session_factory
    )
    new = _values(fresh)["TC_CAPTAIN_JO_PASSWORD"]
    assert new != old and new not in capsys.readouterr().out

    assert (await _login(client, phone, old)).status_code == 401
    assert (await _login(client, phone, new)).status_code == 200
    # **الجلسةُ القديمةُ أُبطلت**
    assert (await client.get("/auth/me", headers=_bearer(before))).status_code == 401
