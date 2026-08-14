"""التجديدُ التلقائي (البند ١٤) — ثلاثُ محاولاتٍ من المحفظة وحدَها.

**وقرارُ المالك يحكم الملف**: من المحفظة لا من قناةٍ خارجية، وثلاثُ محاولاتٍ
موزّعةٍ على نافذة اليوم (الرصيدُ قد يصل بينها)، وفشلُ الأخيرة يُقال صراحةً.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.redis_client import get_redis_client
from app.models.driver import Driver
from app.models.subscription import DriverSubscription
from app.models.enums import PaymentMethod, SubscriptionStatus
from app.models.wallet import WalletTransaction
from app.services import subscriptions as subscriptions_service
from app.services import wallet as wallet_service
from app.models.enums import WalletTransactionType

from tests.helpers import DRIVER, approved_driver, ensure_plan

pytestmark = pytest.mark.usefixtures("jordan_settings", "jordan_wallet")


async def _subscription_ending_in(
    session_factory, driver_id: str, *, ends_in: timedelta, plan_id: uuid.UUID
) -> uuid.UUID:
    now = datetime.now(UTC)
    async with session_factory() as session:
        row = DriverSubscription(
            driver_id=uuid.UUID(str(driver_id)),
            plan_id=plan_id,
            status=SubscriptionStatus.ACTIVE,
            starts_at=now - timedelta(days=29),
            expires_at=now + ends_in,
            payment_method=PaymentMethod.WALLET,
            amount_paid=Decimal("30.000"),
        )
        session.add(row)
        await session.commit()
        return row.id


async def _enable_auto_renew(session_factory, driver_id: str) -> None:
    async with session_factory() as session:
        await session.execute(
            update(Driver)
            .where(Driver.id == uuid.UUID(str(driver_id)))
            .values(auto_renew=True)
        )
        await session.commit()


async def _topup(session_factory, user_id: str, amount: str) -> None:
    async with session_factory() as session:
        from app.models.user import User

        user = await session.get(User, uuid.UUID(str(user_id)))
        assert user is not None
        await wallet_service.record(
            session,
            owner=user,
            tx_type=WalletTransactionType.TOPUP,
            amount=Decimal(amount),
            reference="شحنٌ للاختبار",
            idempotency_key=f"test-topup:{uuid.uuid4()}",
        )
        await session.commit()


async def _count_subscriptions(session_factory, driver_id: str) -> int:
    async with session_factory() as session:
        rows = await session.scalars(
            select(DriverSubscription.id).where(
                DriverSubscription.driver_id == uuid.UUID(str(driver_id))
            )
        )
        return len(list(rows))


async def test_a_driver_who_did_not_ask_is_never_charged(
    client: AsyncClient, session_factory
) -> None:
    """**الإذنُ صريحٌ أو لا يكون**: مفتاحٌ مطفأٌ يعني محفظةً لا تُمسّ."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan = await ensure_plan(session_factory)
    await _subscription_ending_in(
        session_factory, driver["driver_id"], ends_in=timedelta(hours=3), plan_id=plan
    )
    await _topup(session_factory, driver["user_id"], "500.000")

    assert await subscriptions_service.renew_due(get_redis_client()) == 0
    assert await _count_subscriptions(session_factory, driver["driver_id"]) == 1


async def test_it_renews_once_per_attempt_window(
    client: AsyncClient, session_factory
) -> None:
    """يُجدَّد مرةً واحدة، ودورةٌ تالية على الموعد نفسِه لا تخصم ثانيةً."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan = await ensure_plan(session_factory)
    await _subscription_ending_in(
        session_factory, driver["driver_id"], ends_in=timedelta(hours=3), plan_id=plan
    )
    await _enable_auto_renew(session_factory, driver["driver_id"])
    await _topup(session_factory, driver["user_id"], "500.000")

    redis = get_redis_client()
    assert await subscriptions_service.renew_due(redis) == 1
    assert await subscriptions_service.renew_due(redis) == 0, (
        "دورةٌ ثانيةٌ على الموعد نفسِه خصمت مرةً أخرى — أثرُ المحاولة لا يعمل"
    )
    assert await _count_subscriptions(session_factory, driver["driver_id"]) == 2

    # قيدٌ واحدٌ في الدفتر لا قيدان
    async with session_factory() as session:
        rows = await session.scalars(
            select(WalletTransaction).where(
                WalletTransaction.owner_id == uuid.UUID(str(driver["user_id"])),
                WalletTransaction.type == WalletTransactionType.SUBSCRIPTION_PAYMENT,
            )
        )
        assert len(list(rows)) == 1


async def test_an_empty_wallet_is_silent_until_the_last_attempt(
    client: AsyncClient, session_factory
) -> None:
    """**ولا يُقال الفشلُ إلا في الأخيرة**: الرصيدُ قد يصل قبل التالية، فإشعارٌ
    مبكّرٌ يصير كذباً — وثلاثةُ إشعاراتٍ بفشلٍ واحدٍ في يومٍ واحد ضجيج."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan = await ensure_plan(session_factory)
    # ثلاثُ ساعاتٍ: داخلَ الموعدين الأول والثاني، خارجَ الأخير (ساعتان)
    await _subscription_ending_in(
        session_factory, driver["driver_id"], ends_in=timedelta(hours=3), plan_id=plan
    )
    await _enable_auto_renew(session_factory, driver["driver_id"])

    async with session_factory() as session:
        candidates = await subscriptions_service.due_renewals(session)
    attempts = sorted(int(c.attempt.total_seconds() // 3600) for c in candidates)
    assert attempts == [16, 24], "المواعيدُ المستحقّة الآن ليست هي المتوقَّعة"
    assert not any(c.last for c in candidates), (
        "موعدُ الساعتين استُحقّ مبكّراً — فسيُقال الفشلُ قبل أوانه"
    )

    # بلا رصيد: لا اشتراكَ جديد، ولا انهيارَ في الدورة
    assert await subscriptions_service.renew_due(get_redis_client()) == 0
    assert await _count_subscriptions(session_factory, driver["driver_id"]) == 1


async def test_a_second_cycle_does_not_announce_the_same_renewal(
    client: AsyncClient, session_factory
) -> None:
    """**تجديدٌ وقع لا يُعاد إعلانُه** — قِيس على الجهاز قبل أن يُكتب هذا.

    مفتاحُ التكرار يجعل `purchase_with_wallet` تعيد الاشتراكَ القائم بلا خصم،
    وهذا صحيحٌ للمال وخاطئٌ للخبر: صفَّان في صندوق الوارد بقيدٍ واحدٍ في الدفتر.
    """
    from app.models.notification import UserNotification

    driver = await approved_driver(
        client,
        session_factory,
        DRIVER | {"phone": "0796660015", "name": "كبتنُ الإعلان"},
        plate_number="AMM-1515",
        subscribed=False,
    )
    plan = await ensure_plan(session_factory)
    await _subscription_ending_in(
        session_factory, driver["driver_id"], ends_in=timedelta(hours=3), plan_id=plan
    )
    await _enable_auto_renew(session_factory, driver["driver_id"])
    await _topup(session_factory, driver["user_id"], "500.000")

    redis = get_redis_client()
    assert await subscriptions_service.renew_due(redis) == 1

    # أثرُ المحاولات يُمحى — كما لو أُعيدت الدورةُ يدوياً أو انهارت وأُعيدت
    for attempt in subscriptions_service.RENEWAL_ATTEMPTS:
        await redis.delete(
            subscriptions_service.renewal_key(
                (await _newest_subscription_id(session_factory, driver["driver_id"])),
                attempt,
            )
        )
    assert await subscriptions_service.renew_due(redis) == 0, (
        "أُعلن التجديدُ مرتين — والدفترُ فيه قيدٌ واحد"
    )

    async with session_factory() as session:
        rows = await session.scalars(
            select(UserNotification).where(
                UserNotification.user_id == uuid.UUID(str(driver["user_id"])),
                UserNotification.kind == "subscription_renewed",
            )
        )
        assert len(list(rows)) == 1


async def _newest_subscription_id(session_factory, driver_id: str) -> uuid.UUID:
    async with session_factory() as session:
        row = await session.scalar(
            select(DriverSubscription.id)
            .where(DriverSubscription.driver_id == uuid.UUID(str(driver_id)))
            .order_by(DriverSubscription.created_at.desc())
            .limit(1)
        )
        assert row is not None
        return row


async def test_the_last_attempt_says_it_failed(
    client: AsyncClient, session_factory
) -> None:
    """آخرُ محاولةٍ تفشل تُقال صراحةً — صفٌّ في صندوق الوارد لا صمت."""
    from app.models.notification import UserNotification

    driver = await approved_driver(
        client,
        session_factory,
        DRIVER | {"phone": "0796660014", "name": "كبتنُ التجديد"},
        plate_number="AMM-1414",
        subscribed=False,
    )
    plan = await ensure_plan(session_factory)
    await _subscription_ending_in(
        session_factory, driver["driver_id"], ends_in=timedelta(hours=1), plan_id=plan
    )
    await _enable_auto_renew(session_factory, driver["driver_id"])

    assert await subscriptions_service.renew_due(get_redis_client()) == 0

    async with session_factory() as session:
        rows = await session.scalars(
            select(UserNotification).where(
                UserNotification.user_id == uuid.UUID(str(driver["user_id"])),
                UserNotification.kind == "subscription_renewal_failed",
            )
        )
        assert len(list(rows)) == 1, "الفشلُ الأخير لم يُقل — والكبتن يظنّ نفسه مجدَّداً"
