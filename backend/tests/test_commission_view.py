"""ما يراه الكبتنُ عن عمولة TAXO — النسبةُ المجمَّدة والمجموعُ الشهريّ (§25.11)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import (
    CountryCode,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.ride import Ride
from app.models.wallet import WalletTransaction
from app.services import commission_view
from tests.helpers import (
    RIDER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    register,
)


async def _seed_balance(session_factory, *, user_id: uuid.UUID, amount: str) -> None:
    """رصيدٌ موجبٌ أولاً — `balance_after >= 0` قيدُ فحصٍ في القاعدة نفسِها."""
    async with session_factory() as session:
        session.add(
            WalletTransaction(
                owner_id=user_id,
                owner_type=WalletOwnerType.DRIVER,
                type=WalletTransactionType.RIDE_EARNING,
                amount=Decimal(amount),
                balance_after=Decimal(amount),
                idempotency_key=f"test:{uuid.uuid4()}",
            )
        )
        await session.commit()


async def _commission_entry(
    session_factory,
    *,
    user_id: uuid.UUID,
    ride_id: uuid.UUID | None,
    amount: str,
    when: datetime | None = None,
) -> None:
    """قيدُ عمولةٍ يُكتب مباشرة — الاختبارُ عن **العرض** لا عن مسار الدفع."""
    async with session_factory() as session:
        last = await session.scalar(
            select(WalletTransaction.balance_after)
            .where(
                WalletTransaction.owner_id == user_id,
                WalletTransaction.owner_type == WalletOwnerType.DRIVER,
            )
            .order_by(WalletTransaction.created_at.desc())
            .limit(1)
        )
        # **التاريخُ يُكتب عند الإدراج لا بتحديثٍ بعده**: الدفترُ يرفض كلَّ
        # `UPDATE` بمُشغِّلٍ في القاعدة (ترحيلة `0006`) — والتصحيحُ قيدٌ مقابل
        # لا تعديل. فالاختبارُ يحترم القاعدةَ نفسَها التي يحرسها الإنتاج
        entry = WalletTransaction(
            owner_id=user_id,
            owner_type=WalletOwnerType.DRIVER,
            type=WalletTransactionType.COMMISSION,
            amount=Decimal(amount),
            balance_after=Decimal(last or 0) + Decimal(amount),
            ride_id=ride_id,
            idempotency_key=f"test:{uuid.uuid4()}",
        )
        if when is not None:
            entry.created_at = when
        session.add(entry)
        await session.commit()


async def test_the_percent_published_is_the_one_frozen_on_the_ride(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**النسبةُ من الرحلة لا من الإعدادات** — وهي علّةُ التجميد نفسُها.

    **والرحلةُ تُصنع بمسارها الحقيقيّ** لا بصفٍّ مكتوبٍ بيد: صفٌّ يدويٌّ يوافق
    افتراضاتي هو ما مرّر `awaiting_confirmation` من مراجعةٍ كاملة — والحقلُ
    الذي يضيفه الأصلُ ولا يضيفه المساعدُ يجعل الاختبارَ يقيس عالماً لا وجودَ له.
    """
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))
    ride = await completed_ride(client, rider, driver)

    async with session_factory() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        frozen = row.commission_percent_at_ride

    user_id = uuid.UUID(driver["user_id"])
    await _seed_balance(session_factory, user_id=user_id, amount="50.000")
    await _commission_entry(
        session_factory,
        user_id=user_id,
        ride_id=uuid.UUID(ride["id"]),
        amount="-0.500",
    )

    body = (
        await client.get(
            "/wallet/me/transactions?wallet=driver", headers=driver["headers"]
        )
    ).json()
    published = next(
        r for r in body if r["type"] == "commission" and r["ride_id"] == ride["id"]
    )
    assert published["commission_percent"] == str(frozen), published


async def test_a_non_commission_entry_carries_no_percent(
    client: AsyncClient, session_factory, jordan_wallet: None
) -> None:
    """**الغيابُ ليس صفراً**: قيدُ شحنٍ لا نسبةَ له أصلاً، ولا يُقال عنه «صفر٪»."""
    driver = await approved_driver(client, session_factory)
    async with session_factory() as session:
        user_id = uuid.UUID(driver["user_id"])
        session.add(
            WalletTransaction(
                owner_id=user_id,
                owner_type=WalletOwnerType.DRIVER,
                type=WalletTransactionType.TOPUP,
                amount=Decimal("10.000"),
                balance_after=Decimal("10.000"),
                idempotency_key=f"test:{uuid.uuid4()}",
            )
        )
        await session.commit()

    body = (
        await client.get(
            "/wallet/me/transactions?wallet=driver", headers=driver["headers"]
        )
    ).json()
    row = next(r for r in body if r["type"] == "topup")
    assert row["commission_percent"] is None


async def test_the_month_is_calendar_not_a_rolling_thirty_days(
    client: AsyncClient, session_factory, jordan_wallet: None
) -> None:
    """**«هذا الشهر» يُعدّ من أوّله.**

    قيدٌ قبل أوّل الشهر بيومٍ **لا يدخل**، ونافذةٌ متدحرجةٌ بثلاثين يوماً كانت
    ستبتلعه — فيقرأ الكبتنُ رقماً لا يطابق ما يحسبه بيده.
    """
    driver = await approved_driver(client, session_factory)
    user_id = uuid.UUID(driver["user_id"])
    first_of_month = datetime.now(UTC).replace(day=1, hour=0, minute=5)

    await _seed_balance(session_factory, user_id=user_id, amount="50.000")
    await _commission_entry(
        session_factory, user_id=user_id, ride_id=None, amount="-1.000"
    )
    await _commission_entry(
        session_factory,
        user_id=user_id,
        ride_id=None,
        amount="-9.000",
        when=first_of_month - timedelta(days=1),
    )

    # **`now` يُقرأ بعد الكتابة**: النافذةُ تنتهي عنده، وقراءتُه قبلها تُخرج
    # القيدَ الذي كُتب بعده — وهو خطأُ المقياس لا خطأُ المقيس
    now = datetime.now(UTC)
    async with session_factory() as session:
        total = await commission_view.this_month(
            session, user_id=user_id, country=CountryCode.JO, now=now
        )
    assert total == Decimal("1.000"), total


async def test_the_monthly_total_is_quantized_to_three_places(
    client: AsyncClient, session_factory, jordan_wallet: None
) -> None:
    """**الشكلُ السابع**: صفرٌ محسوبٌ في بايثون يُسلسَل «0» لا «0.000»."""
    driver = await approved_driver(client, session_factory)
    body = (
        await client.get("/wallet/me/driver", headers=driver["headers"])
    ).json()
    assert body["commission_this_month"] == "0.000", body["commission_this_month"]


async def test_available_for_withdrawal_is_never_negative(
    client: AsyncClient, session_factory, jordan_wallet: None
) -> None:
    """**«المتاح» لا يكون سالباً بالتعريف** — أقلُّ ما يُسحب لا شيء.

    قِيس على جهازٍ حقيقيّ: رصيدٌ صفرٌ واحتجازُ ٥٫٠٠٠ رسم «الرصيد المتاح
    −5.000 د.أ»، والسالبُ يُقرأ ديناً — والمحتجَزُ ليس ديناً.
    """
    driver = await approved_driver(client, session_factory)
    body = (
        await client.get("/wallet/me/driver", headers=driver["headers"])
    ).json()
    assert Decimal(body["available_for_withdrawal"]) >= 0, body
    assert body["available_for_withdrawal"] == "0.000", body
