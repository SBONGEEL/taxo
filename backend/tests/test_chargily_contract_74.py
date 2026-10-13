"""سكربتُ عقد Chargily (SPEC §٧٤-ي/١) — **من ملفّ الأسرار إلى العقد المشفَّر، ولا حرفَ من المفتاح في مخرَجه**.

**والمفتاحُ مولَّدٌ لكلِّ تشغيلٍ لا حرفيّ** — قيمةٌ حرفيّةٌ بشكل مفتاحٍ أوقفت ماسحَ الأسرار في رفع (٢٠٢٦-١٠-١١).
"""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.crypto import get_cipher
from app.models.enums import CountryCode, ProviderKey
from app.models.payment_request import PayMethod
from app.services.providers import credentials as credentials_service
from scripts import chargily_contract_74 as script

pytestmark = pytest.mark.asyncio


def _env(tmp_path: Path, mode: str, key: str, name: str | None = None) -> Path:
    path = tmp_path / "chargily.env"
    path.write_text(f"CHARGILY_MODE={mode}\n{name or script.KEY_NAME[mode]}={key}\n", encoding="utf-8")
    return path


async def test_the_contract_is_written_encrypted_and_the_key_never_printed(
    session_factory, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    key = "test_sk_" + secrets.token_hex(16)
    path = _env(tmp_path, "test", key)

    preview = await script.main_async(secrets_file=path, write=False, session_factory=session_factory)
    async with session_factory() as session:
        assert await credentials_service.get_credential(session, ProviderKey.CHARGILY, CountryCode.DZ) is None

    plan = await script.main_async(secrets_file=path, write=True, session_factory=session_factory)
    assert plan.mode == "test" == preview.mode
    async with session_factory() as session:
        credential = await credentials_service.get_credential(session, ProviderKey.CHARGILY, CountryCode.DZ)
        assert credential is not None and credential.is_active
        assert key not in str(credential.credentials)
        values = get_cipher().decrypt(credential.credentials)
        assert values["secret_key"] == key and credentials_service.is_on(values, "test_mode")
        method = await session.scalar(select(PayMethod).where(PayMethod.integration == "chargily"))
        assert method is not None and method.enabled and method.for_topup and method.for_subscription
        assert method.country_code is CountryCode.DZ and method.fee_bearer == "taxo"

    # **وإعادتُه لا تُنشئ ثانية**
    again = await script.main_async(secrets_file=path, write=True, session_factory=session_factory)
    async with session_factory() as session:
        assert len((await session.scalars(select(PayMethod).where(PayMethod.integration == "chargily"))).all()) == 1
    assert key not in " ".join(plan.lines + again.lines + preview.lines)
    assert key not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("mode", "key_prefix", "name"),
    [("test", "live_sk_", None), ("demo", "test_sk_", "CHARGILY_TEST_SECRET_KEY"), ("live", "live_sk_", "OTHER_NAME")],
)
async def test_a_wrong_or_missing_key_stops_before_writing(
    session_factory, tmp_path: Path, mode: str, key_prefix: str, name: str | None
) -> None:
    key = key_prefix + secrets.token_hex(16)
    path = _env(tmp_path, mode, key, name or (script.KEY_NAME[mode] if mode in script.KEY_NAME else None))
    with pytest.raises(script.ContractRefused) as refused:
        await script.main_async(secrets_file=path, write=True, session_factory=session_factory)
    assert key not in str(refused.value)
    async with session_factory() as session:
        assert await credentials_service.get_credential(session, ProviderKey.CHARGILY, CountryCode.DZ) is None
