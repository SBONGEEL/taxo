"""اشتراكات الكباتن: الشراء والسريان والانتهاء (SPEC القسم 8).

الثابت الذي تدور حوله كل هذه الاختبارات واحد: **لا اشتراك ساري = لا رحلات**،
وأن سريان الاشتراك يُقرأ بالساعة لا بعمود الحالة — فكبتنٌ انقضى وقته قبل أن
تمر المهمة الدورية خارجٌ من التوزيع الآن لا بعد خمس دقائق.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import PaymentMethod, SubscriptionStatus, WalletTransactionType
from app.models.subscription import DriverSubscription
from app.models.wallet import WalletTransaction
from app.services import subscriptions as subscriptions_service
from tests.helpers import (
    DRIVER,
    PICKUP,
    SUBSCRIPTION_PLAN_PRICE,
    approved_driver,
    bring_online,
    card_order_of,
    enable_card_provider,
    ensure_plan,
    request_ride,
    rider_session,
    simulate_card,
    subscribe_driver,
    topup_wallet,
    wait_for_offer,
    wait_for_status,
    wallet_of,
)

PURCHASE_KEY = "sub-key-000001"


async def _buy(
    client: AsyncClient, driver: dict, plan_id: uuid.UUID, *, key: str = PURCHASE_KEY
):
    return await client.post(
        "/subscriptions",
        json={"plan_id": str(plan_id), "idempotency_key": key},
        headers=driver["headers"],
    )


async def _my_subscription(client: AsyncClient, driver: dict) -> dict:
    response = await client.get("/subscriptions/me", headers=driver["headers"])
    assert response.status_code == 200, response.text
    return response.json()


async def _rows(session_factory, driver_id: uuid.UUID) -> list[DriverSubscription]:
    async with session_factory() as session:
        return list(
            (
                await session.scalars(
                    select(DriverSubscription)
                    .where(DriverSubscription.driver_id == driver_id)
                    .order_by(DriverSubscription.starts_at)
                )
            ).all()
        )


# -------------------------------------------------------------------- الخطط


async def test_driver_sees_only_active_plans_of_his_country(
    client: AsyncClient, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    await ensure_plan(session_factory, country="LY", name="خطة ليبية")
    await ensure_plan(
        session_factory, country="JO", name="خطة موقوفة", is_active=False
    )
    await ensure_plan(session_factory, country="JO")

    response = await client.get("/subscriptions/plans", headers=driver["headers"])
    assert response.status_code == 200, response.text
    names = {plan["name"] for plan in response.json()}
    assert names == {"خطة الاختبار الشهرية"}


async def test_rider_has_no_subscriptions_endpoint(client: AsyncClient) -> None:
    """الاشتراك للكباتن وحدهم — الراكب لا يشترك ولا يرى الخطط."""
    rider = await rider_session(client)
    response = await client.get("/subscriptions/me", headers=rider["headers"])
    assert response.status_code == 403, response.text


# ------------------------------------------------------------ الشراء بالمحفظة


async def test_wallet_purchase_activates_and_debits_the_ledger(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "50.000")

    response = await _buy(client, driver, plan_id)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "active"
    assert body["payment_method"] == "wallet"
    assert body["amount_paid"] == SUBSCRIPTION_PLAN_PRICE
    assert body["transaction_id"] is not None

    assert (await wallet_of(client, driver["headers"]))["balance"] == "20.000"

    mine = await _my_subscription(client, driver)
    assert mine["is_active"] is True
    assert mine["days_remaining"] == 30
    assert mine["current"]["id"] == body["id"]

    async with session_factory() as session:
        entry = await session.scalar(
            select(WalletTransaction).where(
                WalletTransaction.type == WalletTransactionType.SUBSCRIPTION_PAYMENT
            )
        )
    assert entry.amount == Decimal("-30.000")
    assert str(entry.id) == body["transaction_id"]


async def test_wallet_purchase_without_balance_is_rejected(
    client: AsyncClient, jordan_wallet: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)

    response = await _buy(client, driver, plan_id)
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "insufficient_balance"
    assert await _rows(session_factory, driver["driver_id"]) == []


async def test_wallet_purchase_needs_the_wallet_feature(
    client: AsyncClient, session_factory
) -> None:
    """بلا مفتاح `wallet_enabled` لا شراء من الرصيد — ليبيا كاش فقط."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)

    response = await _buy(client, driver, plan_id)
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "feature_disabled"


async def test_unapproved_driver_cannot_subscribe(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """اشتراكٌ يبدأ عدُّه فوراً لا يُباع لحسابٍ لا يستطيع العمل به."""
    from app.models.driver import Driver
    from app.models.enums import DriverStatus

    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "50.000")

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        row.status = DriverStatus.PENDING
        await session.commit()

    response = await _buy(client, driver, plan_id)
    assert response.status_code == 403, response.text
    assert await _rows(session_factory, driver["driver_id"]) == []


async def test_plan_of_another_country_is_not_found(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "50.000")
    libyan_plan = await ensure_plan(session_factory, country="LY", name="خطة ليبية")

    response = await _buy(client, driver, libyan_plan)
    assert response.status_code == 404, response.text


async def test_inactive_plan_cannot_be_bought(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "50.000")
    stopped = await ensure_plan(
        session_factory, name="خطة موقوفة", is_active=False
    )

    response = await _buy(client, driver, stopped)
    assert response.status_code == 409, response.text


async def test_same_idempotency_key_buys_once(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "90.000")

    first = await _buy(client, driver, plan_id)
    second = await _buy(client, driver, plan_id)

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(await _rows(session_factory, driver["driver_id"])) == 1
    assert (await wallet_of(client, driver["headers"]))["balance"] == "60.000"


async def test_free_plan_writes_no_ledger_entry(
    client: AsyncClient, jordan_wallet: None, session_factory
) -> None:
    """خطةٌ بلا ثمن (القسم 4 يجيزها) تفتح اشتراكاً بلا قيد — لم يتحرك مال."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    free_plan = await ensure_plan(
        session_factory, name="خطة ترويجية", price="0.000"
    )

    response = await _buy(client, driver, free_plan)
    assert response.status_code == 201, response.text
    assert response.json()["transaction_id"] is None
    async with session_factory() as session:
        assert await session.scalar(select(func.count(WalletTransaction.id))) == 0


async def test_renewal_stacks_on_the_remaining_days(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """من جدّد مبكراً لا يُحرق ما تبقّى له: الجديد يبدأ من نهاية القديم."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "90.000")

    first = await _buy(client, driver, plan_id, key="renew-key-01")
    second = await _buy(client, driver, plan_id, key="renew-key-02")
    assert second.status_code == 201, second.text

    assert second.json()["starts_at"] == first.json()["expires_at"]
    mine = await _my_subscription(client, driver)
    assert mine["days_remaining"] == 60
    assert mine["coverage_until"] == second.json()["expires_at"]
    # والصف الحالي هو الساري الآن لا آخر ما اشتُري
    assert mine["current"]["id"] == first.json()["id"]

    history = await client.get(
        "/subscriptions/me/history", headers=driver["headers"]
    )
    assert len(history.json()) == 2


# ------------------------------------------------------------------ التوزيع


async def test_driver_without_subscription_receives_no_offer(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """لا اشتراك ساري = لا رحلات (SPEC القسم 8)."""
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, subscribed=False)
    await bring_online(client, driver)

    ride = await request_ride(client, rider["headers"])
    body = await wait_for_status(
        client, rider["headers"], ride["id"], "no_driver_found"
    )
    assert body["driver"] is None


async def test_driver_without_subscription_is_hidden_from_the_rider_map(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """ما لا يُسنَد إليه لا يُعرض سيارةً متاحة (SPEC القسم 10)."""
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, subscribed=False)
    await bring_online(client, driver)

    async def _nearby() -> list[dict]:
        response = await client.get(
            "/drivers/nearby",
            params={"lat": PICKUP["lat"], "lng": PICKUP["lng"]},
            headers=rider["headers"],
        )
        assert response.status_code == 200, response.text
        return response.json()

    assert await _nearby() == []

    await subscribe_driver(session_factory, driver["driver_id"])
    assert len(await _nearby()) == 1


async def test_expired_period_drops_the_driver_before_the_sweep_runs(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """صفٌّ انقضى وقته وحالتُه `active` بعد — الساعة هي الحكم لا العمود.

    هذا بالضبط ما يقع بين دورتي المهمة الدورية. لو كان التوزيع يقرأ العمود
    وحده لأخذ هذا الكبتنُ رحلةً بلا اشتراك.
    """
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, subscribed=False)
    await bring_online(client, driver)

    plan_id = await ensure_plan(session_factory)
    now = datetime.now(UTC)
    async with session_factory() as session:
        session.add(
            DriverSubscription(
                driver_id=driver["driver_id"],
                plan_id=plan_id,
                starts_at=now - timedelta(days=30),
                expires_at=now - timedelta(seconds=5),
                amount_paid=Decimal(SUBSCRIPTION_PLAN_PRICE),
                payment_method=PaymentMethod.CASH,
                status=SubscriptionStatus.ACTIVE,
            )
        )
        await session.commit()

    ride = await request_ride(client, rider["headers"])
    await wait_for_status(client, rider["headers"], ride["id"], "no_driver_found")

    mine = await _my_subscription(client, driver)
    assert mine["is_active"] is False
    assert mine["days_remaining"] == 0


async def test_subscribed_driver_still_receives_offers(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الحارس الجديد لا يمنع من له اشتراك — وإلا لصار المنعُ عاماً."""
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)

    ride = await request_ride(client, rider["headers"])
    assert await wait_for_offer(ride["id"], driver["driver_id"])


# ------------------------------------------------------------- الكنس الدوري


async def _sweep(session_factory) -> subscriptions_service.SweepResult:
    async with session_factory() as session:
        result = await subscriptions_service.sweep(session)
        await session.commit()
    return result


async def _write_subscription(
    session_factory, driver_id: uuid.UUID, *, starts_in: timedelta, ends_in: timedelta
) -> uuid.UUID:
    plan_id = await ensure_plan(session_factory)
    now = datetime.now(UTC)
    async with session_factory() as session:
        row = DriverSubscription(
            driver_id=driver_id,
            plan_id=plan_id,
            starts_at=now + starts_in,
            expires_at=now + ends_in,
            amount_paid=Decimal(SUBSCRIPTION_PLAN_PRICE),
            payment_method=PaymentMethod.CASH,
            status=SubscriptionStatus.ACTIVE,
        )
        session.add(row)
        await session.commit()
        return row.id


async def test_sweep_marks_expired_and_takes_the_driver_offline(
    client: AsyncClient, session_factory
) -> None:
    from app.models.driver import Driver

    driver = await approved_driver(client, session_factory, subscribed=False)
    await bring_online(client, driver)
    await _write_subscription(
        session_factory,
        driver["driver_id"],
        starts_in=-timedelta(days=30),
        ends_in=-timedelta(minutes=1),
    )

    result = await _sweep(session_factory)
    assert [notice.driver_id for notice in result.expired] == [driver["driver_id"]]
    assert result.expired[0].went_offline is True

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        assert row.is_online is False
        statuses = (await session.scalars(select(DriverSubscription.status))).all()
    assert list(statuses) == [SubscriptionStatus.EXPIRED]

    # ودورةٌ ثانية لا تجد شيئاً — التعليم لا يتكرر
    assert (await _sweep(session_factory)).expired == []


async def test_sweep_leaves_a_driver_on_a_ride_online(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """إسقاط حضوره وسط رحلة يقطع خريطة راكبه ويوقظ تنبيه انقطاعٍ لم يقع."""
    from app.models.driver import Driver
    from tests.helpers import accepted_ride

    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    await accepted_ride(client, rider["headers"], driver)

    async with session_factory() as session:
        await session.execute(
            DriverSubscription.__table__.update().values(
                expires_at=datetime.now(UTC) - timedelta(minutes=1)
            )
        )
        await session.commit()

    result = await _sweep(session_factory)
    assert result.expired[0].went_offline is False
    async with session_factory() as session:
        assert (await session.get(Driver, driver["driver_id"])).is_online is True


async def test_sweep_ignores_a_driver_who_already_renewed(
    client: AsyncClient, session_factory
) -> None:
    """انقضاء صفٍّ ليس انقضاء تغطية — من جدّد لا يُنبَّه ولا يُخرَج."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    await bring_online(client, driver)
    await _write_subscription(
        session_factory,
        driver["driver_id"],
        starts_in=-timedelta(days=30),
        ends_in=-timedelta(minutes=1),
    )
    await _write_subscription(
        session_factory,
        driver["driver_id"],
        starts_in=-timedelta(minutes=1),
        ends_in=timedelta(days=30),
    )

    result = await _sweep(session_factory)
    assert result.expired == []
    assert result.expiring == []


async def test_the_three_day_notice_fires_in_its_own_band(
    client: AsyncClient, session_factory
) -> None:
    """نافذتان لا واحدة (البند ١٢) — **وكلٌّ في نطاقها وحدَه**.

    من بقي له عشرون ساعةً هو داخلَ نافذة الثلاثة أيام أيضاً؛ وبلا حدٍّ أدنى
    لكلِّ نطاق يصله التنبيهان في اللحظة نفسِها، فيقول الأولُ «ثلاثة أيام» وقد
    بقي يوم. والاختبارُ يفشل بحذف `after` من `EXPIRY_NOTICE_WINDOWS`.
    """
    early = await approved_driver(client, session_factory, subscribed=False)
    await _write_subscription(
        session_factory,
        early["driver_id"],
        starts_in=-timedelta(days=27),
        ends_in=timedelta(days=2),
    )
    soon = await approved_driver(
        client,
        session_factory,
        DRIVER | {"phone": "0796660001", "name": "كبتنٌ يوشك"},
        plate_number="AMM-6601",
        subscribed=False,
    )
    await _write_subscription(
        session_factory,
        soon["driver_id"],
        starts_in=-timedelta(days=29),
        ends_in=timedelta(hours=20),
    )

    result = await _sweep(session_factory)
    windows = {
        str(notice.driver_id): int(within.total_seconds() // 3600)
        for within, notice in result.expiring
    }
    assert windows[str(early["driver_id"])] == 72
    assert windows[str(soon["driver_id"])] == 24
    # ولا يظهر أحدُهما في نافذتين
    assert len(result.expiring) == 2


async def test_the_two_windows_do_not_share_one_key(
    client: AsyncClient, session_factory
) -> None:
    """مفتاحٌ لكلِّ نافذة — وإلا ابتلعت الأولى الثانيةَ وهي أشدُّ لزوماً."""
    from app.core.redis_client import get_redis_client

    driver = await approved_driver(client, session_factory, subscribed=False)
    subscription_id = await _write_subscription(
        session_factory,
        driver["driver_id"],
        starts_in=-timedelta(days=27),
        ends_in=timedelta(days=2),
    )
    redis = get_redis_client()
    async with session_factory() as session:
        await subscriptions_service.publish_sweep(
            session, redis, await _sweep(session_factory)
        )

    early = subscriptions_service.notice_key(
        subscription_id, subscriptions_service.EARLY_NOTICE_WINDOW
    )
    late = subscriptions_service.notice_key(
        subscription_id, subscriptions_service.EXPIRY_NOTICE_WINDOW
    )
    assert early != late
    assert await redis.get(early) is not None, "لم يُسجَّل تنبيهُ الثلاثة أيام"
    assert await redis.get(late) is None, (
        "مفتاحُ نافذة اليوم كُتب مع الثلاثة أيام — فتنبيهُ الغد لن يصل"
    )


async def test_sweep_notices_expiry_within_a_day_once(
    client: AsyncClient, session_factory
) -> None:
    """تنبيه الأربع والعشرين ساعة يُبث مرة لا في كل دورة (SPEC القسم 8)."""
    from app.core.redis_client import get_redis_client
    from app.ws import events

    driver = await approved_driver(client, session_factory, subscribed=False)
    subscription_id = await _write_subscription(
        session_factory,
        driver["driver_id"],
        starts_in=-timedelta(days=29),
        ends_in=timedelta(hours=6),
    )

    redis = get_redis_client()
    channel = events.user_channel(driver["user_id"])
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    result = await _sweep(session_factory)
    # **مع نافذتها** منذ البند ١٢: النطاقُ (24 ساعة] هو صاحبُ هذا التنبيه،
    # ونافذةُ الثلاثة أيام تستثنيه فلا يصل التنبيهان معاً
    assert [
        (int(within.total_seconds() // 3600), notice.subscription_id)
        for within, notice in result.expiring
    ] == [(24, subscription_id)]
    async with session_factory() as session:
        # منذ المرحلة 8 يمر البثّ بطبقة الإشعارات فيحتاج جلسةً لقراءة الأجهزة
        await subscriptions_service.publish_sweep(session, redis, result)

    async def _next_event() -> dict | None:
        deadline = asyncio.get_running_loop().time() + 5
        while asyncio.get_running_loop().time() < deadline:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=0.2
            )
            if message is not None:
                return json.loads(message["data"])
        return None

    event = await _next_event()
    assert event is not None and event["type"] == "subscription_expiring"

    # البث الثاني لا يقع: أثر التنبيه محفوظ في Redis
    async with session_factory() as session:
        await subscriptions_service.publish_sweep(
            session, redis, await _sweep(session_factory)
        )
    assert await _next_event() is None
    await pubsub.unsubscribe(channel)
    await pubsub.aclose()


# ------------------------------------------------------------ الشراء بالبطاقة


async def test_card_purchase_activates_only_after_the_provider_pays(
    client: AsyncClient, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await enable_card_provider(session_factory)

    opened = await client.post(
        "/subscriptions/card",
        json={"plan_id": str(plan_id)},
        headers=driver["headers"],
    )
    assert opened.status_code == 201, opened.text
    order = opened.json()
    assert order["purpose"] == "subscription"
    assert order["status"] == "created"
    assert order["redirect_url"]

    # قبل جواب المزود لا اشتراك — ولا رحلة
    assert await _rows(session_factory, driver["driver_id"]) == []
    assert (await _my_subscription(client, driver))["is_active"] is False

    paid = await simulate_card(client, driver["headers"], order["cart_id"])
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"

    mine = await _my_subscription(client, driver)
    assert mine["is_active"] is True
    assert mine["current"]["payment_method"] == "card"
    assert mine["current"]["amount_paid"] == SUBSCRIPTION_PLAN_PRICE
    # **لا قيد في الدفتر**: المال خرج من البطاقة لا من المحفظة
    assert mine["current"]["transaction_id"] is None
    async with session_factory() as session:
        entries = await session.scalar(
            select(func.count(WalletTransaction.id))
        )
    assert entries == 0


async def test_card_purchase_settles_once_under_a_repeated_notice(
    client: AsyncClient, session_factory
) -> None:
    """استعلامٌ بعد التسوية لا يفتح اشتراكاً ثانياً."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await enable_card_provider(session_factory)

    opened = await client.post(
        "/subscriptions/card",
        json={"plan_id": str(plan_id)},
        headers=driver["headers"],
    )
    cart_id = opened.json()["cart_id"]
    await simulate_card(client, driver["headers"], cart_id)
    await card_order_of(client, driver["headers"], cart_id)

    assert len(await _rows(session_factory, driver["driver_id"])) == 1


async def test_declined_card_leaves_no_subscription(
    client: AsyncClient, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await enable_card_provider(session_factory)

    opened = await client.post(
        "/subscriptions/card",
        json={"plan_id": str(plan_id)},
        headers=driver["headers"],
    )
    declined = await simulate_card(
        client, driver["headers"], opened.json()["cart_id"], outcome="declined"
    )
    assert declined.json()["status"] == "failed"
    assert await _rows(session_factory, driver["driver_id"]) == []


async def test_card_purchase_needs_an_active_contract(
    client: AsyncClient, session_factory
) -> None:
    """قرارٌ إداري لا نقصُ تنفيذ: بلا عقد Telr مفعّل القناةُ مغلقة."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)

    response = await client.post(
        "/subscriptions/card",
        json={"plan_id": str(plan_id)},
        headers=driver["headers"],
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "feature_disabled"


# -------------------------------------------------------------------- اللوحة


async def test_admin_records_a_cash_subscription_with_audit(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)

    response = await client.post(
        "/admin/subscriptions",
        json={
            "driver_id": str(driver["driver_id"]),
            "plan_id": str(plan_id),
            "method": "cash",
            "reference": "إيصال 7788",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["payment_method"] == "cash"
    assert body["amount_paid"] == SUBSCRIPTION_PLAN_PRICE
    assert body["transaction_id"] is None

    assert (await _my_subscription(client, driver))["is_active"] is True

    logs = await client.get(
        "/admin/settings/audit-logs",
        params={"entity_type": "driver_subscription"},
        headers=admin_headers,
    )
    entries = logs.json()
    assert len(entries) == 1
    # أسماء الحقول وقنواتها لا مبالغها (SPEC القسم 14)
    assert entries[0]["details"] == {
        "driver_id": str(driver["driver_id"]),
        "method": "cash",
    }


async def test_admin_cannot_record_a_wallet_subscription(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """القنوات الفورية يفتحها صاحبها ويشهد عليها الدفتر — لا تُسجَّل يدوياً."""
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)

    response = await client.post(
        "/admin/subscriptions",
        json={
            "driver_id": str(driver["driver_id"]),
            "plan_id": str(plan_id),
            "method": "wallet",
        },
        headers=admin_headers,
    )
    assert response.status_code == 422, response.text


async def test_support_reads_reports_but_does_not_record(
    client: AsyncClient, admin_headers: dict, support_headers: dict, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    plan_id = await ensure_plan(session_factory)
    await client.post(
        "/admin/subscriptions",
        json={
            "driver_id": str(driver["driver_id"]),
            "plan_id": str(plan_id),
            "method": "cliq",
        },
        headers=admin_headers,
    )

    listing = await client.get("/admin/subscriptions", headers=support_headers)
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 1

    denied = await client.post(
        "/admin/subscriptions",
        json={
            "driver_id": str(driver["driver_id"]),
            "plan_id": str(plan_id),
            "method": "cash",
        },
        headers=support_headers,
    )
    assert denied.status_code == 403, denied.text


async def test_driver_cannot_read_the_admin_report(
    client: AsyncClient, session_factory
) -> None:
    driver = await approved_driver(client, session_factory, subscribed=False)
    response = await client.get("/admin/subscriptions", headers=driver["headers"])
    assert response.status_code == 403, response.text


async def test_report_filters_by_status_and_driver(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    first = await approved_driver(client, session_factory, subscribed=False)
    second = await approved_driver(
        client,
        session_factory,
        DRIVER | {"phone": "0799999999"},
        plate_number="AMM-9999",
        subscribed=False,
    )
    await subscribe_driver(session_factory, first["driver_id"])
    await _write_subscription(
        session_factory,
        second["driver_id"],
        starts_in=-timedelta(days=40),
        ends_in=-timedelta(days=10),
    )
    await _sweep(session_factory)

    expired = await client.get(
        "/admin/subscriptions",
        params={"subscription_status": "expired"},
        headers=admin_headers,
    )
    assert [row["driver_id"] for row in expired.json()] == [str(second["driver_id"])]

    of_first = await client.get(
        "/admin/subscriptions",
        params={"driver_id": str(first["driver_id"])},
        headers=admin_headers,
    )
    assert len(of_first.json()) == 1


async def test_report_filters_by_country(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    driver = await approved_driver(client, session_factory)

    jordan = await client.get(
        "/admin/subscriptions", params={"country_code": "JO"}, headers=admin_headers
    )
    libya = await client.get(
        "/admin/subscriptions", params={"country_code": "LY"}, headers=admin_headers
    )
    assert [row["driver_id"] for row in jordan.json()] == [str(driver["driver_id"])]
    assert libya.json() == []
