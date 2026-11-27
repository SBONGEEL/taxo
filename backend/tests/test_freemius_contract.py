"""سكربتُ عقد Freemius — **من ملفّ الأسرار إلى العقد المشفَّر، ولا حرفَ من المفاتيح في مخرَجه**.

**والقيمُ مولَّدةٌ لكلِّ تشغيلٍ لا حرفيّة** — قيمةٌ حرفيّةٌ بشكل مفتاحٍ أوقفت ماسحَ الأسرار في رفع (٢٠٢٦-١٠-١١).
"""

from __future__ import annotations

import secrets as rnd
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.crypto import get_cipher
from app.models.enums import CountryCode, FeatureKey, PaymentProviderKind, ProviderKey
from app.models.payment_request import PayMethod
from app.services import settings_service
from app.services.providers import credentials as credentials_service
from scripts import freemius_contract as script

pytestmark = pytest.mark.asyncio

PHONE = "+962790000" + "456"


@pytest.fixture
async def method_row(session_factory) -> None:
    """**كما تضعها `0194`** — والمجموعةُ تفرغ الجداولَ بين الاختبارات فيُعاد صفُّها هنا."""
    async with session_factory() as session:
        session.add(
            PayMethod(
                country_code=CountryCode.JO, kind=PaymentProviderKind.BANK_TRANSFER, code="freemius_card",
                name="الدفع بالبطاقة المصرفية", integration="freemius", enabled=True, for_topup=False,
                for_subscription=True, fee_bearer="taxo", sort_order=1, max_amount=Decimal("100.000"),
            )
        )
        await session.commit()


def _files(
    tmp_path: Path, test_mode: str, *, plans: dict[str, str] | None = None, phone: str | None = PHONE, public: str | None = None
) -> tuple[Path, Path, list[str]]:
    secret_values = ["sk_" + rnd.token_urlsafe(22), rnd.token_hex(16)]
    pub = public if public is not None else "pk_" + rnd.token_hex(15)
    body = [f"test_mode={test_mode}", "product_id=46510", f"public_key={pub}", f"secret_key={secret_values[0]}", f"api_token={secret_values[1]}"]
    for name, value in (plans if plans is not None else {"plan_daily": "81967", "plan_weekly": "81968"}).items():
        body.append(f"{name}={value}")
    env = tmp_path / "freemius.env"
    env.write_text("\n".join(body) + "\n", encoding="utf-8")
    accounts = tmp_path / "test-accounts.env"
    accounts.write_text(f"TAXO_TEST_CAPTAIN_PHONE={phone}\n" if phone else "# none\n", encoding="utf-8")
    return env, accounts, secret_values


async def test_test_mode_contract_is_encrypted_limited_to_the_test_captain_and_never_printed(
    method_row, session_factory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env, accounts, secret_values = _files(tmp_path, "1")

    preview = await script.main_async(secrets_file=env, test_accounts=accounts, write=False, session_factory=session_factory)
    async with session_factory() as session:
        assert await credentials_service.get_credential(session, ProviderKey.FREEMIUS, CountryCode.JO) is None

    plan = await script.main_async(secrets_file=env, test_accounts=accounts, write=True, session_factory=session_factory)
    assert plan.mode == "test" == preview.mode
    async with session_factory() as session:
        credential = await credentials_service.get_credential(session, ProviderKey.FREEMIUS, CountryCode.JO)
        assert credential is not None and credential.is_active
        for value in secret_values:
            assert value not in str(credential.credentials)
        values = get_cipher().decrypt(credential.credentials)
        assert values["secret_key"] == secret_values[0] and values["api_token"] == secret_values[1]
        assert values["product_id"] == "46510"
        assert values["plan_daily"] == "81967" and values["plan_weekly"] == "81968" and "plan_monthly" not in values
        assert credentials_service.is_on(values, "test_mode") and values["allowlist"] == PHONE
        # **ولا يغيّر البوّابة** — المفتاحان كما كانا
        for key in (FeatureKey.DIGISTORE24_CARD_ENABLED, FeatureKey.FREEMIUS_CARD_ENABLED):
            assert not await settings_service.is_feature_enabled(session, CountryCode.JO, key)

    out = " ".join(plan.lines + preview.lines) + capsys.readouterr().out
    for value in secret_values:
        assert value not in out


async def test_test_mode_without_the_test_captain_phone_writes_nothing(session_factory, tmp_path: Path) -> None:
    env, accounts, _values = _files(tmp_path, "1", phone=None)
    with pytest.raises(script.ContractRefused):
        await script.main_async(secrets_file=env, test_accounts=accounts, write=True, session_factory=session_factory)
    async with session_factory() as session:
        assert await credentials_service.get_credential(session, ProviderKey.FREEMIUS, CountryCode.JO) is None


async def test_live_mode_clears_the_allowlist(method_row, session_factory, tmp_path: Path) -> None:
    env, accounts, _values = _files(tmp_path, "1")
    await script.main_async(secrets_file=env, test_accounts=accounts, write=True, session_factory=session_factory)
    live, _accounts, _values2 = _files(tmp_path, "0")
    plan = await script.main_async(secrets_file=live, test_accounts=None, write=True, session_factory=session_factory)
    assert plan.mode == "live"
    async with session_factory() as session:
        credential = await credentials_service.get_credential(session, ProviderKey.FREEMIUS, CountryCode.JO)
        values = get_cipher().decrypt(credential.credentials)
        assert not credentials_service.is_on(values, "test_mode") and values["allowlist"] == ""


@pytest.mark.parametrize(
    ("plans", "public", "why"),
    [({}, None, "no plan"), ({"plan_daily": "abc"}, None, "not digits"), (None, "pub-without-prefix-000000", "bad public key")],
)
async def test_bad_values_refuse(session_factory, tmp_path: Path, plans: dict[str, str] | None, public: str | None, why: str) -> None:
    env, accounts, _values = _files(tmp_path, "1", plans=plans, public=public)
    with pytest.raises(script.ContractRefused):
        await script.main_async(secrets_file=env, test_accounts=accounts, write=False, session_factory=session_factory)


async def test_a_secrets_file_inside_the_repo_is_refused(session_factory) -> None:
    inside = Path(script.__file__).resolve().parents[1] / "freemius.env"
    with pytest.raises(script.ContractRefused):
        await script.main_async(secrets_file=inside, test_accounts=None, write=False, session_factory=session_factory)


async def test_without_the_method_row_nothing_is_written(session_factory, tmp_path: Path) -> None:
    env, accounts, _values = _files(tmp_path, "1")
    with pytest.raises(script.ContractRefused):
        await script.main_async(secrets_file=env, test_accounts=accounts, write=True, session_factory=session_factory)
