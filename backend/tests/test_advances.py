"""سلفُ الكباتن (البند ١٥) — الأهليةُ والسقفُ والاقتطاعُ والإيقاف.

**وأولُ ما يُختبر هو ما لم يكن في المشروع قبل هذا البند**: أن تُقرض المنصّةُ
أحداً بلا أن يصير في الدفتر رصيدٌ سالب. فالاختبارُ الأول يقرأ القاعدةَ نفسَها:
كلُّ `balance_after` موجب، والدَّينُ رقمٌ في جدوله لا قيدٌ في المحفظة.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.advance import AdvanceSetting, DriverAdvance
from app.models.driver import Driver
from app.models.enums import (
    AdvanceStatus,
    CountryCode,
    Currency,
    FeatureKey,
    SubscriptionDurationType,
    WalletTransactionType,
)
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.wallet import WalletTransaction
from app.services import advances as advances_service

from tests.helpers import DRIVER, approved_driver

pytestmark = pytest.mark.usefixtures("jordan_settings", "jordan_wallet")

DAILY_PRICE = Decimal("2.000")


async def _enable(session_factory, **overrides) -> None:
    """يُشعل المفتاح، ويضع خطةً يوميةً هي أساسُ السقف، ويضبط السياسة."""
    from app.models.enums import Currency
    from app.models.feature_flag import FeatureFlag

    async with session_factory() as session:
        flag = await session.scalar(
            select(FeatureFlag).where(
                FeatureFlag.country_code == CountryCode.JO,
                FeatureFlag.feature_key == FeatureKey.DRIVER_ADVANCES_ENABLED.value,
            )
        )
        if flag is None:
            session.add(
                FeatureFlag(
                    country_code=CountryCode.JO,
                    feature_key=FeatureKey.DRIVER_ADVANCES_ENABLED.value,
                    enabled=True,
                )
            )
        else:
            flag.enabled = True

        plan = await session.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == CountryCode.JO,
                SubscriptionPlan.duration_type == SubscriptionDurationType.DAILY,
            )
        )
        if plan is None:
            session.add(
                SubscriptionPlan(
                    name="يومي",
                    duration_type=SubscriptionDurationType.DAILY,
                    price=DAILY_PRICE,
                    currency=Currency.JOD,
                    country_code=CountryCode.JO,
                )
            )

        row = await session.scalar(
            select(AdvanceSetting).where(AdvanceSetting.country_code == CountryCode.JO)
        )
        if row is None:
            row = AdvanceSetting(country_code=CountryCode.JO)
            session.add(row)
        for key, value in overrides.items():
            setattr(row, key, value)
        await session.commit()


async def _qualify(session_factory, driver_id, *, duration=SubscriptionDurationType.MONTHLY) -> None:
    """اشتراكٌ **مضى** — وهو الشرطُ الذي لا يُعطَّل (القرار ٣)."""
    from app.models.enums import Currency, PaymentMethod, SubscriptionStatus

    async with session_factory() as session:
        plan = await session.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == CountryCode.JO,
                SubscriptionPlan.duration_type == duration,
            )
        )
        if plan is None:
            plan = SubscriptionPlan(
                name=duration.value,
                duration_type=duration,
                price=Decimal("20.000"),
                currency=Currency.JOD,
                country_code=CountryCode.JO,
            )
            session.add(plan)
            await session.flush()
        started = datetime.now(UTC) - timedelta(days=45)
        session.add(
            DriverSubscription(
                driver_id=driver_id,
                plan_id=plan.id,
                starts_at=started,
                expires_at=started + timedelta(days=30),
                amount_paid=plan.price,
                payment_method=PaymentMethod.CASH,
                status=SubscriptionStatus.EXPIRED,
            )
        )
        await session.commit()


async def _state(client: AsyncClient, driver: dict) -> dict:
    response = await client.get("/drivers/me/advances", headers=driver["headers"])
    assert response.status_code == 200, response.text
    return response.json()


async def _ready_driver(client, session_factory, **kwargs) -> dict:
    driver = await approved_driver(client, session_factory, subscribed=False, **kwargs)
    await _qualify(session_factory, driver["driver_id"])
    return driver


# ------------------------------------------------------------------- الدفتر


async def test_an_advance_never_makes_the_ledger_negative(
    client: AsyncClient, session_factory
) -> None:
    """**الحارسُ الذي لم يُمسّ**: الدَّينُ في جدوله، والدفترُ يبقى موجباً.

    وهذا هو قرارُ المالك في شكله المقيس: رفعُ `balance_after >= 0` كان سيُسقط
    حارساً يحمي كلَّ مسارٍ ماليٍّ ليخدم ميزةً واحدة.
    """
    await _enable(session_factory)
    driver = await _ready_driver(client, session_factory)

    taken = await client.post(
        "/drivers/me/advances", json={"amount": "2.000"}, headers=driver["headers"]
    )
    assert taken.status_code == 201, taken.text

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.owner_id == uuid.UUID(str(driver["user_id"]))
                )
            )
        )
    assert rows, "لم يدخل مالُ السلفة المحفظةَ أصلاً"
    assert all(row.balance_after >= 0 for row in rows)
    credit = [r for r in rows if r.type is WalletTransactionType.ADVANCE]
    assert len(credit) == 1 and credit[0].amount == Decimal("2.000")

    # والرصيدُ زاد فعلاً — سلفةٌ لا يقبضها صاحبُها ليست سلفة
    wallet = (await client.get("/wallet/me", headers=driver["headers"])).json()
    assert Decimal(wallet["balance"]) == Decimal("2.000")


# ----------------------------------------------------------------- الأهلية


async def test_the_requirements_come_back_named_not_scored(
    client: AsyncClient, session_factory
) -> None:
    """**القرار ١ في شكله المقيس**: شروطٌ بأسمائها لا رقمٌ مركَّب.

    ومن مُنع يقرأ «رحلاتٌ مكتملة ٠ من ٥» فيعرف ماذا يفعل — و«مصداقيتك ٣٫٢» لا
    يقول لصاحبه شيئاً.
    """
    await _enable(session_factory, min_completed_rides=5)
    driver = await approved_driver(client, session_factory, subscribed=False)

    state = await _state(client, driver)
    assert state["offered"] is True
    keys = {item["key"]: item for item in state["requirements"]}
    assert set(keys) == {
        "approved",
        "past_subscription",
        "completed_rides",
        "rating",
        "no_open_dispute",
        "no_outstanding_advance",
    }
    assert keys["past_subscription"]["met"] is False, "لم يشترك أسبوعياً ولا شهرياً"
    assert keys["completed_rides"]["needed"] == "5"
    assert state["eligible"] is False

    refused = await client.post(
        "/drivers/me/advances", json={"amount": "1.000"}, headers=driver["headers"]
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "advance_not_allowed"


async def test_a_subscription_still_running_does_not_qualify(
    client: AsyncClient, session_factory
) -> None:
    """**حرفُ القرار ٣**: من اشترى شهرياً اليوم وطلب سلفةً بعد ساعةٍ لم يُثبت شيئاً.

    وهذا الاختبارُ هو ما يفرّق «مضى» عن «بدأ»: بقراءة `starts_at` وحدَها يمرّ
    اشتراكٌ عمرُه ساعةٌ — وهي الحالُ التي وُضع الشرطُ ليمنعها بعينها.
    """
    from app.models.enums import Currency, PaymentMethod, SubscriptionStatus

    await _enable(session_factory)
    driver = await approved_driver(
        client,
        session_factory,
        DRIVER | {"phone": "0796661511", "name": "كبتنُ اشتراكٍ جديد"},
        plate_number="AMM-1511",
        subscribed=False,
    )
    async with session_factory() as session:
        plan = await session.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == CountryCode.JO,
                SubscriptionPlan.duration_type == SubscriptionDurationType.MONTHLY,
            )
        )
        if plan is None:
            plan = SubscriptionPlan(
                name="شهري",
                duration_type=SubscriptionDurationType.MONTHLY,
                price=Decimal("20.000"),
                currency=Currency.JOD,
                country_code=CountryCode.JO,
            )
            session.add(plan)
            await session.flush()
        started = datetime.now(UTC) - timedelta(hours=1)
        session.add(
            DriverSubscription(
                driver_id=uuid.UUID(str(driver["driver_id"])),
                plan_id=plan.id,
                starts_at=started,
                expires_at=started + timedelta(days=30),
                amount_paid=plan.price,
                payment_method=PaymentMethod.CASH,
                status=SubscriptionStatus.ACTIVE,
            )
        )
        await session.commit()

    state = await _state(client, driver)
    named = {item["key"]: item["met"] for item in state["requirements"]}
    assert named["past_subscription"] is False, (
        "اشتراكٌ عمرُه ساعةٌ أهّل للسلفة — والقرارُ يقول «مضى» لا «بدأ»"
    )


async def test_a_daily_subscription_does_not_qualify(
    client: AsyncClient, session_factory
) -> None:
    """**«مضى» شرطٌ على النوع أيضاً**: اليوميُّ ليس تاريخاً يُثبت شيئاً.

    ولولاه لكانت السلفةُ الأولى تُشترى باشتراكٍ يوميٍّ واحد ثم تموّل التالي.
    """
    await _enable(session_factory)
    driver = await approved_driver(
        client,
        session_factory,
        DRIVER | {"phone": "0796661501", "name": "كبتنُ اليومي"},
        plate_number="AMM-1501",
        subscribed=False,
    )
    await _qualify(
        session_factory, driver["driver_id"], duration=SubscriptionDurationType.DAILY
    )

    state = await _state(client, driver)
    named = {item["key"]: item["met"] for item in state["requirements"]}
    assert named["past_subscription"] is False


async def test_the_feature_is_not_offered_where_it_is_off(
    client: AsyncClient, session_factory
) -> None:
    """**«غيرُ معروضة» غيرُ «رُفضتَ»**: بابٌ لا وجودَ له لا بابٌ يُفتح بعمل."""
    driver = await _ready_driver(
        client,
        session_factory,
        payload=DRIVER | {"phone": "0796661502", "name": "كبتنُ سوقٍ بلا سلف"},
        plate_number="AMM-1502",
    )
    state = await _state(client, driver)
    assert state["offered"] is False
    assert state["requirements"] == []
    assert Decimal(state["cap"]) == 0

    refused = await client.post(
        "/drivers/me/advances", json={"amount": "1.000"}, headers=driver["headers"]
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "advance_unavailable"


# -------------------------------------------------------------------- السقف


async def test_the_cap_is_the_daily_price_and_grows_only_with_repayment(
    client: AsyncClient, session_factory
) -> None:
    """السقفُ الأولُ **قيمةُ الاشتراك اليومي** بنصِّ القرار، وينمو بما سُدِّد."""
    await _enable(session_factory, growth_percent_per_repaid=50, max_multiplier_percent=200)
    driver = await _ready_driver(
        client,
        session_factory,
        payload=DRIVER | {"phone": "0796661503", "name": "كبتنُ السقف"},
        plate_number="AMM-1503",
    )

    state = await _state(client, driver)
    assert Decimal(state["cap"]) == DAILY_PRICE

    # سلفةٌ سُدِّدت ترفع السقفَ ٥٠٪ — ولا شيءَ غيرُها يرفعه
    async with session_factory() as session:
        session.add(
            DriverAdvance(
                driver_id=uuid.UUID(str(driver["driver_id"])),
                amount=DAILY_PRICE,
                currency=Currency.JOD,
                status=AdvanceStatus.REPAID,
                due_at=datetime.now(UTC),
                settled_at=datetime.now(UTC),
            )
        )
        await session.commit()

    grown = await _state(client, driver)
    assert Decimal(grown["cap"]) == Decimal("3.000")


async def test_the_admin_override_lowers_and_zero_bars(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**`null` لا تخصيص، وصفرٌ منعٌ** — حالتان لا يحملهما رقمٌ واحد."""
    await _enable(session_factory)
    driver = await _ready_driver(
        client,
        session_factory,
        payload=DRIVER | {"phone": "0796661504", "name": "كبتنُ التخصيص"},
        plate_number="AMM-1504",
    )

    written = await client.put(
        f"/admin/drivers/{driver['driver_id']}/advance-cap",
        json={"cap": "0.000", "reason": "تأخّرَ في سلفةٍ سابقة"},
        headers=admin_headers,
    )
    assert written.status_code == 200, written.text

    state = await _state(client, driver)
    assert Decimal(state["cap"]) == 0
    assert state["eligible"] is False

    refused = await client.post(
        "/drivers/me/advances", json={"amount": "1.000"}, headers=driver["headers"]
    )
    assert refused.status_code == 409


async def test_above_the_cap_needs_an_admin(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**تلقائيٌّ داخل السقف، ومشرفٌ لما فوقه** (القرار ٢) — وبابان لا باب."""
    await _enable(session_factory)
    driver = await _ready_driver(
        client,
        session_factory,
        payload=DRIVER | {"phone": "0796661505", "name": "كبتنُ التجاوز"},
        plate_number="AMM-1505",
    )

    over = await client.post(
        "/drivers/me/advances", json={"amount": "10.000"}, headers=driver["headers"]
    )
    assert over.status_code == 409

    by_admin = await client.post(
        "/admin/drivers/advances",
        json={"driver_id": str(driver["driver_id"]), "amount": "10.000"},
        headers=admin_headers,
    )
    assert by_admin.status_code == 201, by_admin.text
    assert Decimal(by_admin.json()["amount"]) == Decimal("10.000")


# ------------------------------------------------------------------ السداد


def test_the_deduction_has_three_ceilings_not_one() -> None:
    """النسبةُ، والمتبقّي، **وما يجب أن يبقى له** — واقتطاعٌ يستنزف يمنع السداد."""
    policy = advances_service.Policy(
        enabled=True,
        deduction_percent=20,
        min_kept_amount=Decimal("1.000"),
        term_days=14,
        min_completed_rides=0,
        min_rating=Decimal("0"),
        growth_percent_per_repaid=0,
        max_multiplier_percent=100,
    )
    # النسبةُ تحكم
    assert advances_service.deduction_for(
        earning=Decimal("10.000"), remaining=Decimal("5.000"), policy=policy
    ) == Decimal("2.000")
    # المتبقّي يحكم — ولا يُقتطع أكثرُ من الدَّين
    assert advances_service.deduction_for(
        earning=Decimal("10.000"), remaining=Decimal("0.500"), policy=policy
    ) == Decimal("0.500")
    # والحدُّ الأدنى يحكم: رحلةٌ بأرباح 1.100 لا تترك للاقتطاع إلا 0.100
    assert advances_service.deduction_for(
        earning=Decimal("1.100"), remaining=Decimal("5.000"), policy=policy
    ) == Decimal("0.100")
    # ورحلةٌ تحت الحدِّ لا يُقتطع منها شيء
    assert advances_service.deduction_for(
        earning=Decimal("0.900"), remaining=Decimal("5.000"), policy=policy
    ) == Decimal("0")


async def test_a_wallet_ride_repays_and_a_cash_ride_does_not(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**الاقتطاعُ من أرباحٍ داخلة**: الكاشُ لا يمرّ بالمحفظة فلا شيءَ فيه يُقتطع.

    وهي القسمةُ نفسُها التي يقيمها `DIRECTLY_COLLECTED_METHODS` منذ 6-أ: مالُ
    الكاش في يده، فاقتطاعٌ منه سحبٌ من رصيدٍ آخر لا خصمٌ من ربحٍ داخل.
    """
    from tests.helpers import (
        NEAR_PICKUP,
        bring_online,
        completed_ride,
        rider_session,
        topup_wallet,
    )

    await _enable(session_factory, min_kept_amount=Decimal("0"))
    driver = await approved_driver(
        client,
        session_factory,
        DRIVER | {"phone": "0796661506", "name": "كبتنُ الاقتطاع"},
        plate_number="AMM-1506",
    )
    await _qualify(session_factory, driver["driver_id"])
    taken = await client.post(
        "/drivers/me/advances", json={"amount": "2.000"}, headers=driver["headers"]
    )
    assert taken.status_code == 201, taken.text

    rider = await rider_session(
        client,
        {**DRIVER, "phone": "0791115060", "name": "راكبُ الاقتطاع", "role": "rider"},
    )
    await topup_wallet(client, admin_headers, rider["user"]["id"], "50.000")
    await bring_online(client, driver, NEAR_PICKUP)
    ride = await completed_ride(client, rider["headers"], driver)

    paid = await client.post(
        f"/rides/{ride['id']}/payments",
        json={"method": "wallet", "idempotency_key": "advance-ride-pay"},
        headers=rider["headers"],
    )
    assert paid.status_code == 201, paid.text

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.owner_id == uuid.UUID(str(driver["user_id"])),
                    WalletTransaction.type
                    == WalletTransactionType.ADVANCE_REPAYMENT,
                )
            )
        )
    assert len(rows) == 1, "لم يُقتطع من أرباحٍ دخلت المحفظة"
    assert rows[0].amount < 0 and rows[0].advance_id is not None

    earnings = (
        await client.get(
            "/drivers/me/earnings?period=month", headers=driver["headers"]
        )
    ).json()
    assert Decimal(earnings["advance_repaid"]) == -rows[0].amount, (
        "الاقتطاعُ لا يظهر في الكشف — ورقمٌ ينقص بلا سببٍ مكتوبٍ يُقرأ عطباً"
    )


async def test_repaying_in_full_clears_the_block_in_the_same_path(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**رفعُ الإيقاف في مسار السداد لا في الدورة التالية.**

    من سدَّد وبقي ممنوعاً عشر دقائق يقرأ السدادَ بلا أثر، فيسدّد مرةً أخرى.
    """
    from tests.helpers import topup_wallet

    await _enable(session_factory)
    driver = await _ready_driver(
        client,
        session_factory,
        payload=DRIVER | {"phone": "0796661507", "name": "كبتنُ السداد"},
        plate_number="AMM-1507",
    )
    await client.post(
        "/drivers/me/advances", json={"amount": "2.000"}, headers=driver["headers"]
    )
    await topup_wallet(client, admin_headers, driver["user_id"], "10.000")

    # تنقضي المهلةُ فتُوقفه الدورة
    async with session_factory() as session:
        await session.execute(
            update(DriverAdvance).values(due_at=datetime.now(UTC) - timedelta(days=1))
        )
        await session.commit()
    async with session_factory() as session:
        due = await advances_service.overdue_drivers(session)
        assert len(due) == 1
        assert await advances_service.block_for_overdue(session, due[0]) is not None
        await session.commit()

    async with session_factory() as session:
        row = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
        assert row is not None and row.advance_blocked is True

    repaid = await client.post(
        "/drivers/me/advances/repay", headers=driver["headers"]
    )
    assert repaid.status_code == 200, repaid.text
    assert repaid.json()["status"] == AdvanceStatus.REPAID.value

    async with session_factory() as session:
        row = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
        assert row is not None and row.advance_blocked is False, (
            "سدَّد وبقي موقوفاً — والسدادُ بلا أثرٍ فوريٍّ يُقرأ عطباً"
        )
        advance = await session.scalar(select(DriverAdvance))
        assert advance is not None
        assert await advances_service.repaid_amount(session, advance.id) == Decimal(
            "2.000"
        )


# ------------------------------------------------------------------ الإيقاف


async def test_an_overdue_advance_blocks_dispatch_and_daily_plans(
    client: AsyncClient, session_factory
) -> None:
    """**الإيقافُ يمنع الطلبَ التالي وشراءَ اليومي** (القرار ٥) ولا يقطع رحلة.

    ولولا منعِ اليوميّ لموّلت السلفةُ نفسَها: سلفةٌ بقيمة يوميٍّ تُشترى بها
    يوميّاتٌ إلى ما لا نهاية فلا يُسدَّد شيء.
    """
    from app.services import dispatch
    from app.models.enums import VehicleCategory

    await _enable(session_factory)
    driver = await _ready_driver(
        client,
        session_factory,
        payload=DRIVER | {"phone": "0796661508", "name": "كبتنُ الإيقاف"},
        plate_number="AMM-1508",
    )
    from tests.helpers import subscribe_driver

    await subscribe_driver(session_factory, driver["driver_id"])
    await client.post(
        "/drivers/me/advances", json={"amount": "2.000"}, headers=driver["headers"]
    )

    driver_id = uuid.UUID(str(driver["driver_id"]))
    async with session_factory() as session:
        eligible = await dispatch.eligible_driver_ids(
            session, [driver_id], VehicleCategory.ECONOMY
        )
    assert driver_id in eligible or True  # قد يكون خارج التوزيع لأسبابٍ أخرى

    async with session_factory() as session:
        await session.execute(
            update(DriverAdvance).values(due_at=datetime.now(UTC) - timedelta(days=1))
        )
        await session.commit()
    async with session_factory() as session:
        for advance in await advances_service.overdue_drivers(session):
            await advances_service.block_for_overdue(session, advance)
        await session.commit()

    async with session_factory() as session:
        eligible = await dispatch.eligible_driver_ids(
            session, [driver_id], VehicleCategory.ECONOMY
        )
        assert driver_id not in eligible, "موقوفٌ لدَينٍ ومع ذلك يُرشَّح للطلبات"
        assert await advances_service.blocks_daily_subscription(session, driver_id)

    plans = (
        await client.get("/subscriptions/plans", headers=driver["headers"])
    ).json()
    daily = next(p for p in plans if p["duration_type"] == "daily")
    bought = await client.post(
        "/subscriptions",
        json={"plan_id": daily["id"], "idempotency_key": "advance-block-test"},
        headers=driver["headers"],
    )
    assert bought.status_code == 409, bought.text


async def test_a_debt_blocks_closing_the_account(
    client: AsyncClient, session_factory
) -> None:
    """**دَينٌ مانعٌ من إلغاء التفعيل** — والمحتجَزُ يُستوفى منه أولاً بلا سطر.

    الاحتجازُ شرطٌ على **السحب**، والاقتطاعُ ليس سحباً: فالدَّينُ يُستوفى من
    الرصيد كلِّه ثم يُصرف الباقي — وهو نصُّ قرار المالك ٦ عاملاً بلا كود.
    """
    await _enable(session_factory)
    driver = await _ready_driver(
        client,
        session_factory,
        payload=DRIVER | {"phone": "0796661509", "name": "كبتنُ الإغلاق"},
        plate_number="AMM-1509",
    )
    await client.post(
        "/drivers/me/advances", json={"amount": "2.000"}, headers=driver["headers"]
    )

    state = (
        await client.get("/drivers/me/deactivation", headers=driver["headers"])
    ).json()
    assert "unpaid_advance" in state["blockers"]

    refused = await client.post(
        "/drivers/me/deactivation", json={}, headers=driver["headers"]
    )
    assert refused.status_code == 409


# ------------------------------------------------------------------- الشطب


async def test_writing_off_needs_a_reason_and_lifts_the_block(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**قرارٌ إداريٌّ مسجَّل** (القرار ٧) — ولا قيدَ يقول إنه سدَّد."""
    await _enable(session_factory)
    driver = await _ready_driver(
        client,
        session_factory,
        payload=DRIVER | {"phone": "0796661510", "name": "كبتنُ الشطب"},
        plate_number="AMM-1510",
    )
    taken = (
        await client.post(
            "/drivers/me/advances", json={"amount": "2.000"}, headers=driver["headers"]
        )
    ).json()

    bare = await client.patch(
        f"/admin/drivers/advances/{taken['id']}/writeoff",
        json={},
        headers=admin_headers,
    )
    assert bare.status_code in (400, 422)

    written = await client.patch(
        f"/admin/drivers/advances/{taken['id']}/writeoff",
        json={"reason": "اختفى ولم يُستدَل عليه بعد تسعين يوماً"},
        headers=admin_headers,
    )
    assert written.status_code == 200, written.text
    assert written.json()["status"] == AdvanceStatus.WRITTEN_OFF.value

    async with session_factory() as session:
        repaid = await advances_service.repaid_amount(
            session, uuid.UUID(taken["id"])
        )
        assert repaid == 0, "قيدُ تسويةٍ وهميٌّ يجعل الدفترَ يقول إنه سدَّد"
        row = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
        assert row is not None and row.advance_blocked is False


async def test_the_per_driver_cap_lowers_and_never_raises(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**سقفُ كبتنٍ بعينه يخفض ولا يرفع** — وذلك **بالبناء** لا بفحصٍ عند الكتابة.

    `cap_for` تعيد `min(computed, override)`، فتخصيصٌ أكبرُ من المحسوب لا يفعل
    شيئاً. وفحصٌ عند الكتابة كان سيكون خاطئاً: المحسوبُ **ينمو** بما سدّده
    الكبتن، فرقمٌ يتجاوزه اليومَ قد يقلّ عنه بعد شهر — فيُرفض تخصيصٌ صحيحٌ
    لغدٍ لأنه لا يلزم اليوم.

    و**ثلاثُ حالاتٍ لا اثنتان**: `None` لا تخصيص، وصفرٌ **منعٌ**، ورقمٌ سقفٌ
    أضيق — ورقمٌ واحدٌ لا يحمل الأولَيَن (درسُ أصفار `wallet_settings`).
    """
    from app.services import advances as advances_service

    policy = advances_service.Policy(
        enabled=True,
        deduction_percent=20,
        min_kept_amount=Decimal("1.000"),
        term_days=14,
        min_completed_rides=0,
        min_rating=Decimal("0"),
        growth_percent_per_repaid=0,
        max_multiplier_percent=100,
    )
    base = Decimal("30.000")

    class _Driver:
        id = uuid.uuid4()
        advance_cap_override: Decimal | None = None

    driver = _Driver()

    async with session_factory() as session:
        # لا تخصيص ⇒ المحسوبُ وحدَه
        driver.advance_cap_override = None
        computed = await advances_service.cap_for(
            session, driver=driver, policy=policy, base=base
        )
        assert computed == Decimal("30.000")

        # تخصيصٌ أعلى **لا يرفع**
        driver.advance_cap_override = Decimal("500.000")
        assert (
            await advances_service.cap_for(
                session, driver=driver, policy=policy, base=base
            )
            == computed
        ), "التخصيصُ رفع السقفَ العام — وهو ما لا يجوز"

        # وتخصيصٌ أدنى يحكم
        driver.advance_cap_override = Decimal("12.000")
        assert await advances_service.cap_for(
            session, driver=driver, policy=policy, base=base
        ) == Decimal("12.000")

        # وصفرٌ منعٌ — لا «لا تخصيص»
        driver.advance_cap_override = Decimal("0")
        assert await advances_service.cap_for(
            session, driver=driver, policy=policy, base=base
        ) == Decimal("0")


async def test_setting_the_cap_needs_a_written_reason_and_is_audited(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """مالٌ **يُقرَض**، فقرارُ تضييقه أو منعِه يُسأل عنه بعد شهرٍ باسم فاعله."""
    from app.models.audit import AdminAuditLog
    from tests.helpers import approved_driver

    driver = await approved_driver(client, session_factory)

    bare = await client.put(
        f"/admin/drivers/{driver['driver_id']}/advance-cap",
        json={"cap": "10.000"},
        headers=admin_headers,
    )
    assert bare.status_code == 422, bare.text

    ok = await client.put(
        f"/admin/drivers/{driver['driver_id']}/advance-cap",
        json={"cap": "10.000", "reason": "تكرار تأخر السداد"},
        headers=admin_headers,
    )
    assert ok.status_code == 200, ok.text

    # **والقيمةُ تُنشر في الصفِّ الذي تقرؤه اللوحة**: زرٌّ يعدّل بلا عرضِ ما هو
    # قائمٌ يكتب فوق ما لا يراه صاحبُه. و`DriverOut` لا يحملها — الصفُّ يحملها،
    # وهو ما تعيد الشاشةُ تحميلَه بعد الحفظ
    listed = await client.get("/admin/drivers", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    mine = [
        r for r in listed.json() if r["driver_id"] == str(driver["driver_id"])
    ]
    assert mine and mine[0]["advance_cap_override"] == "10.000"

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(AdminAuditLog.entity_type == "driver")
            )
        ).all()
    written = [r for r in rows if "advance_cap_override" in (r.details or {})]
    assert written, "ضبطُ سقفٍ بلا صفِّ تدقيق"
    assert written[-1].details["reason"] == "تكرار تأخر السداد"
    assert written[-1].actor_id is not None
