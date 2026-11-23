"""سكربتُ عقد Digistore24 — **من ملفّ الأسرار إلى العقد المشفَّر، ولا حرفَ من المفتاح ولا العبارة في مخرَجه**.

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
from scripts import digistore24_contract as script

pytestmark = pytest.mark.asyncio

PHONE = "+962790000" + "123"


@pytest.fixture
async def method_row(session_factory) -> None:
    """**كما تضعها `0188`** — والمجموعةُ تفرغ الجداولَ بين الاختبارات فيُعاد صفُّها هنا."""
    async with session_factory() as session:
        session.add(
            PayMethod(
                country_code=CountryCode.JO, kind=PaymentProviderKind.BANK_TRANSFER, code="digistore24_card",
                name="الدفع بالبطاقة المصرفية", integration="digistore24", enabled=True, for_topup=False,
                for_subscription=True, fee_bearer="taxo", sort_order=1, max_amount=Decimal("100.000"),
            )
        )
        await session.commit()


def _files(tmp_path: Path, mode: str, *, products: dict[str, str] | None = None, phone: str | None = PHONE) -> tuple[Path, Path, str, str]:
    api = rnd.token_hex(24)
    phrase = rnd.token_urlsafe(30)
    body = [f"DS24_MODE={mode}", f"DS24_API_KEY={api}", f"DS24_IPN_PASSPHRASE={phrase}"]
    for name, value in (products if products is not None else {"DS24_PRODUCT_DAILY": "700001", "DS24_PRODUCT_WEEKLY": "700002"}).items():
        body.append(f"{name}={value}")
    env = tmp_path / "ds24.env"
    env.write_text("\n".join(body) + "\n", encoding="utf-8")
    accounts = tmp_path / "test-accounts.env"
    accounts.write_text(f"TAXO_TEST_CAPTAIN_PHONE={phone}\n" if phone else "# none\n", encoding="utf-8")
    return env, accounts, api, phrase


async def test_test_mode_contract_is_encrypted_limited_to_the_test_captain_and_never_printed(
    method_row, session_factory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env, accounts, api, phrase = _files(tmp_path, "test")

    preview = await script.main_async(secrets_file=env, test_accounts=accounts, write=False, session_factory=session_factory)
    async with session_factory() as session:
        assert await credentials_service.get_credential(session, ProviderKey.DIGISTORE24, CountryCode.JO) is None

    plan = await script.main_async(secrets_file=env, test_accounts=accounts, write=True, session_factory=session_factory)
    assert plan.mode == "test" == preview.mode
    async with session_factory() as session:
        credential = await credentials_service.get_credential(session, ProviderKey.DIGISTORE24, CountryCode.JO)
        assert credential is not None and credential.is_active
        assert api not in str(credential.credentials) and phrase not in str(credential.credentials)
        values = get_cipher().decrypt(credential.credentials)
        assert values["api_key"] == api and values["ipn_passphrase"] == phrase
        assert values["product_daily"] == "700001" and values["product_weekly"] == "700002" and "product_monthly" not in values
        assert credentials_service.is_on(values, "test_mode") and values["allowlist"] == PHONE
        # **ولا يشعل مفتاحاً** — المفتاحان كما كانا
        for key in (FeatureKey.DIGISTORE24_CARD_ENABLED, FeatureKey.DIGISTORE24_CARD_PLAY_ENABLED):
            assert not await settings_service.is_feature_enabled(session, CountryCode.JO, key)

    out = " ".join(plan.lines + preview.lines) + capsys.readouterr().out
    assert api not in out and phrase not in out


async def test_test_mode_without_the_test_captain_phone_writes_nothing(session_factory, tmp_path: Path) -> None:
    env, accounts, _api, _phrase = _files(tmp_path, "test", phone=None)
    with pytest.raises(script.ContractRefused):
        await script.main_async(secrets_file=env, test_accounts=accounts, write=True, session_factory=session_factory)
    async with session_factory() as session:
        assert await credentials_service.get_credential(session, ProviderKey.DIGISTORE24, CountryCode.JO) is None


async def test_live_mode_clears_the_allowlist(method_row, session_factory, tmp_path: Path) -> None:
    env, accounts, _api, _phrase = _files(tmp_path, "test")
    await script.main_async(secrets_file=env, test_accounts=accounts, write=True, session_factory=session_factory)
    live, _accounts, _api2, _phrase2 = _files(tmp_path, "live")
    plan = await script.main_async(secrets_file=live, test_accounts=None, write=True, session_factory=session_factory)
    assert plan.mode == "live"
    async with session_factory() as session:
        credential = await credentials_service.get_credential(session, ProviderKey.DIGISTORE24, CountryCode.JO)
        values = get_cipher().decrypt(credential.credentials)
        assert not credentials_service.is_on(values, "test_mode") and values["allowlist"] == ""


@pytest.mark.parametrize(
    ("products", "why"),
    [({}, "no product"), ({"DS24_PRODUCT_DAILY": "abc"}, "not digits")],
)
async def test_bad_products_refuse(session_factory, tmp_path: Path, products: dict[str, str], why: str) -> None:
    env, accounts, _api, _phrase = _files(tmp_path, "test", products=products)
    with pytest.raises(script.ContractRefused):
        await script.main_async(secrets_file=env, test_accounts=accounts, write=False, session_factory=session_factory)


async def test_a_secrets_file_inside_the_repo_is_refused(session_factory) -> None:
    inside = Path(script.__file__).resolve().parents[1] / "ds24.env"
    with pytest.raises(script.ContractRefused):
        await script.main_async(secrets_file=inside, test_accounts=None, write=False, session_factory=session_factory)


async def test_without_the_method_row_nothing_is_written(session_factory, tmp_path: Path) -> None:
    env, accounts, _api, _phrase = _files(tmp_path, "test")
    with pytest.raises(script.ContractRefused):
        await script.main_async(secrets_file=env, test_accounts=accounts, write=True, session_factory=session_factory)
