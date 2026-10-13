"""سكربتُ حسابات التجربة في كلِّ سوق (SPEC §٧٤-ز) — **يُقاس على ما يَعِد به رأسُه، وكلُّ وعدٍ يسقط بحذف ما يحرسه**.

١) **العائلاتُ الأربع** بأسواقها الثلاثة، والجزائريّان — موسومةً، مُثبتةَ الأرقام، **والتوائمُ مربوطةٌ بأصلها** فيراها المُختار.
٢) **كلُّ كبتنٍ معتمدٌ مغطّى الآن في سوقه** — والجزائرُ على خطّةٍ **موقوفةٍ بعد الالتزام**: لا يراها كبتنٌ ولا يشتريها.
٣) **رصيدُ التجربة بمبلغ كلِّ سوق** لكلِّ فرد، **وقائمةُ السماح لأفراد الأربع لا للجزائريَّين**.
٤) **ولا كلمةَ مرورٍ على الشاشة**، والملفُّ بإذن 600 وكلماتُه تدخل — **ولا رسالةَ إلى رقمٍ بحال**.
٥) **وإعادةُ التشغيل لا تغيّر شيئاً**، **وبلا أصلَي §٦٥-ج يقف قبل أن يكتب**.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.driver import Driver
from app.models.enums import CountryCode, DriverStatus, UserRole
from app.models.market import BorderAllowance
from app.models.subscription import SubscriptionPlan
from app.models.user import User
from app.services import subscriptions, test_markets, wallet
from scripts import provision_market_test_accounts as script
from scripts import provision_test_accounts
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
    """`tmp_path` تحت `/tmp` الذي يردّه السكربت — **فيُرفع من المردود هنا وحدَه** (الردُّ نفسُه مقيسٌ في `test_test_accounts.py`)."""
    monkeypatch.setattr(provision_test_accounts, "_EPHEMERAL_ROOTS", ())
    return tmp_path


def _values(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith("#"))


async def test_the_script_builds_every_market_family_once(
    client: AsyncClient,
    jordan_settings: None,
    session_factory,
    _secrets_dir: Path,
    capsys: pytest.CaptureFixture[str],
    _no_messages: None,
) -> None:
    await ensure_plan(session_factory)
    await ensure_plan(session_factory, country="LY", name="خطة ليبيا الشهرية", price="100.000")
    await provision_test_accounts.provision(secrets_file=_secrets_dir / "test-accounts.env", session_factory=session_factory)
    capsys.readouterr()

    secrets_file = _secrets_dir / "aldeeb-accounts.env"
    first = await script.provision(secrets_file=secrets_file, session_factory=session_factory)
    printed = capsys.readouterr().out
    planned = script.planned_accounts()
    assert first.created is True and len(first.ids) == len(planned) == 12

    # ── الملف: 600، ولا كلمةَ على الشاشة، والكلماتُ تدخل ولو كان السوقُ مغلقاً ──
    assert stat.S_IMODE(os.stat(secrets_file).st_mode) == 0o600
    values = _values(secrets_file)
    assert len(values) == 24
    for item in planned:
        assert item.phone in printed and values[f"{item.label}_PASSWORD"] not in printed
    for label in ("ALDEEB_RIDER_DZ", "ALDEEB_CAPTAIN_LY"):
        login = await client.post(
            "/auth/login", json={"phone": values[f"{label}_PHONE"], "password": values[f"{label}_PASSWORD"]}
        )
        assert login.status_code == 200, login.text
        assert login.json()["user"]["is_test"] is True

    # ── المُختار: أصلُ Aldeeb وأصلُ §٦٥-ج يريان أسواقَهما الثلاثة ──
    for label in ("ALDEEB_RIDER_JO",):
        login = await client.post(
            "/auth/login", json={"phone": values[f"{label}_PHONE"], "password": values[f"{label}_PASSWORD"]}
        )
        markets = (
            await client.get("/auth/test-markets", headers={"Authorization": f"Bearer {login.json()['tokens']['access_token']}"})
        ).json()["markets"]
        assert {row["country_code"] for row in markets} == {"JO", "LY", "DZ"}

    async with session_factory() as session:
        users = {user.phone: user for user in await session.scalars(select(User).where(User.is_test.is_(True)))}
        jo_rider = users[provision_test_accounts.RIDER_PHONE]
        assert {member.country_code for member in await test_markets.family(session, jo_rider)} == {
            CountryCode.JO, CountryCode.LY, CountryCode.DZ,
        }
        assert all(user.phone_verified_at is not None for user in users.values())

        # ── الكباتن: معتمدون مغطَّون الآن في أسواقهم ──
        captains = [user for user in users.values() if user.role is UserRole.DRIVER]
        # Aldeeb ×3 · كبتنُ §٦٥-ج وتوأماه · الجزائريّ
        assert len(captains) == 7
        for user in captains:
            driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
            assert driver.status is DriverStatus.APPROVED
            assert await subscriptions.current_subscription(session, driver.id) is not None, user.phone

        # ── خطّةُ الجزائر موقوفةٌ بعد الالتزام: لا يراها كبتنٌ ولا يشتريها ──
        held = await session.scalar(select(SubscriptionPlan).where(SubscriptionPlan.country_code == CountryCode.DZ))
        assert held is not None and held.is_active is False
        assert list(await subscriptions.available_plans(session, CountryCode.DZ)) == []

        # ── رصيدُ التجربة بمبلغ سوقه لكلِّ فرد ──
        for user in users.values():
            balance = await wallet.balance(session, user.id, wallet.owner_type_for(user))
            assert balance == test_markets.TEST_FUNDS[CountryCode(user.country_code)], user.phone

        # ── قائمةُ السماح: أفرادُ الأربع (١٢) لا الجزائريّان ──
        allowed = set(await session.scalars(select(BorderAllowance.user_id).where(BorderAllowance.revoked_at.is_(None))))
        assert len(allowed) == 12
        assert users["+213599000671"].id not in allowed and users["+213599000672"].id not in allowed
        before = await session.scalar(select(func.count()).select_from(User))

    # ── إعادةُ التشغيل: «موجود» ولا شيءَ يتغيّر ──
    written = secrets_file.read_bytes()
    elsewhere = _secrets_dir / "again.env"
    second = await script.provision(secrets_file=elsewhere, session_factory=session_factory)
    assert second.created is False and second.ids == first.ids
    assert capsys.readouterr().out.count(provision_test_accounts.PRESENT) == 12
    assert not elsewhere.exists() and secrets_file.read_bytes() == written
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == before


async def test_without_the_section_65_accounts_it_stops_before_writing(
    jordan_settings: None, session_factory, _secrets_dir: Path, _no_messages: None
) -> None:
    await ensure_plan(session_factory)
    with pytest.raises(provision_test_accounts.ProvisionRefused, match="provision_test_accounts"):
        await script.provision(secrets_file=_secrets_dir / "aldeeb-accounts.env", session_factory=session_factory)
    assert not (_secrets_dir / "aldeeb-accounts.env").exists()
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User).where(User.is_test.is_(True))) == 0
