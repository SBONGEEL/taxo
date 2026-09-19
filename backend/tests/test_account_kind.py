"""نوعُ الحساب — المفتاحُ المركّب `(phone, account_kind)` (1-أ/3، §D9.1).

**ما يُقاس هنا صحّةُ البنية لا بقاءُ كلِّ صفّ** (قرارُ المالك: الصفوفُ بياناتُ
اختبار ما دام الاختبارُ مغلقاً): القيدُ يقبل الرقمَ بنوعين، ويرفض الرقمَ مكرَّراً
في النوع نفسِه، والبريدُ المُثبَتُ كذلك — وكلُّ حسابٍ يُنشأ من الأبواب القائمة
نوعُه `taxo` بلا أن يذكره أحد.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.enums import AccountKind, CountryCode, UserRole
from app.models.user import User
from tests.helpers import rider_session

PHONE = "+962790009001"


def _user(kind: AccountKind, *, phone: str | None = PHONE, email: str | None = None) -> User:
    return User(
        phone=phone,
        name="حساب نوع",
        role=UserRole.RIDER,
        country_code=CountryCode.JO,
        account_kind=kind,
        email=email,
        email_verified_at=datetime.now(UTC) if email else None,
    )


async def test_one_number_holds_one_account_of_each_kind(session_factory) -> None:
    """الرقمُ نفسُه بثلاثة أنواع: ثلاثةُ صفوفٍ يقبلها القيد."""
    async with session_factory() as session:
        session.add_all([_user(kind) for kind in AccountKind])
        await session.commit()
        kinds = (
            await session.scalars(select(User.account_kind).where(User.phone == PHONE))
        ).all()
    assert sorted(kinds) == sorted(AccountKind)


async def test_a_number_cannot_hold_two_accounts_of_the_same_kind(
    session_factory,
) -> None:
    async with session_factory() as session:
        session.add(_user(AccountKind.MARKET))
        await session.commit()
    async with session_factory() as session:
        session.add(_user(AccountKind.MARKET))
        with pytest.raises(IntegrityError, match="uq_users_phone_account_kind"):
            await session.commit()


async def test_a_verified_email_is_unique_per_kind_not_globally(
    session_factory,
) -> None:
    """`uq_users_email_verified` صار على `(lower(email), account_kind)`."""
    async with session_factory() as session:
        session.add(_user(AccountKind.TAXO, phone="+962790009002", email="Kind@X.com"))
        session.add(_user(AccountKind.MARKET, phone="+962790009003", email="kind@x.com"))
        await session.commit()
    async with session_factory() as session:
        session.add(_user(AccountKind.MARKET, phone="+962790009004", email="KIND@x.com"))
        with pytest.raises(IntegrityError, match="uq_users_email_verified"):
            await session.commit()


async def test_panel_accounts_without_a_phone_still_coexist(session_factory) -> None:
    """حساباتُ اللوحة بلا رقم — `NULL` لا يُعدّ مكرَّراً في القيد المركّب."""
    async with session_factory() as session:
        session.add_all([_user(AccountKind.TAXO, phone=None) for _ in range(2)])
        await session.commit()


async def test_every_existing_door_creates_a_taxo_account(
    client: AsyncClient, session_factory
) -> None:
    """التسجيلُ القائم لا يذكر النوع — فيقع `taxo` بالافتراض لا بالتخمين."""
    rider = await rider_session(client)
    async with session_factory() as session:
        kind = await session.scalar(
            select(User.account_kind).where(User.id == rider["user"]["id"])
        )
    assert kind is AccountKind.TAXO
