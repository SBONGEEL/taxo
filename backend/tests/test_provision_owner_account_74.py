"""حسابُ المالك الحقيقيّ في الجزائر (SPEC §٧٤-ك/٢) — **عاديٌّ لا تجربة، بلا رصيد، في قائمة السماح، وكلمتُه في ملفّ الأسرار وحدَه**."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models.enums import CountryCode
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import markets, test_accounts
from scripts import provision_owner_account_74 as script
from scripts import provision_test_accounts

pytestmark = pytest.mark.asyncio

#: **رقمٌ للاختبار وحدَه** — والرقمُ الحقيقيُّ يُعطيه المالكُ ولا يُكتب في الشيفرة
PHONE = "+213555000999"


@pytest.fixture
def secrets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(provision_test_accounts, "_EPHEMERAL_ROOTS", ())
    return tmp_path


async def test_a_real_algeria_rider_for_the_owner(session_factory, secrets_dir: Path, capsys) -> None:
    preview, _ = await script.main_async(
        phone=PHONE, name=script.DEFAULT_NAME, secrets_file=secrets_dir / "p.env", write=False, session_factory=session_factory
    )
    assert preview and not (secrets_dir / "p.env").exists()
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User).where(User.phone == PHONE)) == 0

    path = secrets_dir / "owner-dz.env"
    await script.main_async(phone=PHONE, name=script.DEFAULT_NAME, secrets_file=path, write=True, session_factory=session_factory)
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.phone == PHONE))
        assert user is not None and user.country_code is CountryCode.DZ and user.name == "Mohammed Aldeeb"
        assert not user.is_test and user.test_twin_of is None
        test_accounts.require_real_money(user)  # **مالٌ حقيقيٌّ يمرّ له** — لا وسمَ يردّه
        assert await markets.active_allowance(session, user.id) is not None
        assert await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(WalletTransaction.owner_id == user.id)
        ) == 0
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    content = path.read_text(encoding="utf-8").splitlines()
    password = next(line.split("=", 1)[1] for line in content if line.startswith("OWNER_DZ_PASSWORD="))
    assert len(password) >= 24 and password not in capsys.readouterr().out

    with pytest.raises(provision_test_accounts.ProvisionRefused):
        await script.main_async(
            phone=PHONE, name=script.DEFAULT_NAME, secrets_file=secrets_dir / "again.env", write=True,
            session_factory=session_factory,
        )


async def test_a_libyan_number_is_accepted_for_the_algeria_account_and_a_local_one_is_refused(
    session_factory, secrets_dir: Path
) -> None:
    """**المالكُ يستعمله من ليبيا** — فرقمٌ ليبيٌّ دوليٌّ يُقبل وسوقُ الحساب الجزائر؛ **والرقمُ المحلّيُّ بلا رمز دولةٍ يُردّ**: لا يُخمَّن بلدُه."""
    with pytest.raises(provision_test_accounts.ProvisionRefused):
        await script.main_async(phone="0912345678", name=script.DEFAULT_NAME, secrets_file=secrets_dir / "x.env",
                                write=False, session_factory=session_factory)
    await script.main_async(phone="+218 91 234 5678", name=script.DEFAULT_NAME, secrets_file=secrets_dir / "ly.env",
                            write=True, session_factory=session_factory)
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.phone == "+218912345678"))
        assert user is not None and user.country_code is CountryCode.DZ and not user.is_test
