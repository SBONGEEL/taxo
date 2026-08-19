"""عروضُ اشتراكات الكباتن — البند ٥٤، الفروعُ الستةُ كما أُجيبت.

**وما يُقاس هنا ليس «هل يُخصم؟» بل أن المال يخرج مخصوماً في القنوات الأربع**:
مسارُ المحفظة يخصم من الرصيد **قبل** كتابة الصفّ، فحسابٌ في الموضع الخطأ يخصم
السعرَ كاملاً ويكتب صفّاً مخفَّضاً — وهو مالٌ من عدم لا خطأُ عرض.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.enums import CountryCode, FeatureKey, PaymentMethod
from app.models.subscription import DriverSubscription
from app.models.subscription_offer import (
    AUDIENCE_ALL,
    AUDIENCE_LAPSED,
    AUDIENCE_MANUAL,
    AUDIENCE_NEW_DRIVER,
    DISCOUNT_MONEY_PERCENT,
    SubscriptionOffer,
    SubscriptionOfferGrant,
)
from tests.helpers import (
    wallet_of,
    SECOND_DRIVER,
    approved_driver,
    ensure_plan,
    enable_features,
    topup_wallet,
)

pytestmark = pytest.mark.asyncio

PLAN_PRICE = Decimal("30.000")


async def buy(client, driver: dict, plan_id) -> object:
    return await client.post(
        "/subscriptions",
        json={"plan_id": str(plan_id), "idempotency_key": uuid.uuid4().hex},
        headers=driver["headers"],
    )


async def make_offer(
    session_factory,
    *,
    percent: str = "10",
    audience: str = AUDIENCE_ALL,
    name: str | None = None,
    max_uses: int = 1,
    budget: str | None = None,
    max_discount: str | None = None,
    lapsed_days: int | None = None,
    plan_id: uuid.UUID | None = None,
) -> uuid.UUID:
    async with session_factory() as session:
        offer = SubscriptionOffer(
            country_code=CountryCode.JO,
            name=name or f"عرض {uuid.uuid4().hex[:6]}",
            discount_type=DISCOUNT_MONEY_PERCENT,
            discount_value=Decimal(percent),
            max_discount=Decimal(max_discount) if max_discount else None,
            audience=audience,
            lapsed_days=lapsed_days,
            max_uses_per_driver=max_uses,
            total_budget=Decimal(budget) if budget else None,
            plan_id=plan_id,
            is_active=True,
        )
        session.add(offer)
        await session.commit()
        return offer.id


async def subscription_of(session_factory, driver_id) -> DriverSubscription:
    async with session_factory() as session:
        return (
            await session.execute(
                select(DriverSubscription)
                .where(DriverSubscription.driver_id == driver_id)
                .order_by(DriverSubscription.created_at.desc())
            )
        ).scalars().first()


# --------------------------------------------------- الحساب والقنوات


async def test_the_wallet_is_debited_the_discounted_amount(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """**أهمُّ اختبارٍ في الملف**: ما خرج من الرصيد = ما كُتب في الصفّ.

    حسابٌ يقع بعد القيد يخصم ٣٠ ويكتب ٢٧ — والفرقُ مالٌ من عدم.
    """
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="10")

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")
    before = Decimal((await wallet_of(client, driver["headers"]))["balance"])

    response = await buy(client, driver, plan_id)
    assert response.status_code in (200, 201), response.text

    after = Decimal((await wallet_of(client, driver["headers"]))["balance"])
    row = await subscription_of(session_factory, driver["driver_id"])

    assert row.list_price == PLAN_PRICE
    assert row.discount_amount == Decimal("3.000")
    assert row.amount_paid == Decimal("27.000")
    assert row.offer_discount_amount == Decimal("3.000")
    # الرصيدُ نقص بما دُفع لا بسعر الخطة
    assert before - after == Decimal("27.000")


async def test_no_offer_leaves_the_price_untouched(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    plan_id = await ensure_plan(session_factory)
    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")

    response = await buy(client, driver, plan_id)
    assert response.status_code in (200, 201), response.text
    row = await subscription_of(session_factory, driver["driver_id"])
    assert row.offer_id is None
    assert row.discount_amount == Decimal("0")
    assert row.amount_paid == PLAN_PRICE


async def test_the_flag_off_means_no_discount_at_all(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """**ميزةٌ لا حارس**: غيابُ الصفّ معطَّلة، فلا خصمَ ولو وُجد عرضٌ نشط."""
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="50")

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")
    await buy(client, driver, plan_id)
    row = await subscription_of(session_factory, driver["driver_id"])
    assert row.discount_amount == Decimal("0")
    assert row.amount_paid == PLAN_PRICE


# ------------------------------------------------------- (د) الأكبر وحدَه


async def test_the_largest_offer_wins_and_they_never_stack(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="10", name="عرض صغير")
    await make_offer(session_factory, percent="25", name="عرض كبير")

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")
    await buy(client, driver, plan_id)
    row = await subscription_of(session_factory, driver["driver_id"])
    # ٢٥٪ لا ٣٥٪ — الجمعُ خصمٌ لم يقصده كاتبُ أيٍّ منهما
    assert row.discount_amount == Decimal("7.500")


async def test_the_cap_bounds_the_percentage(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="50", max_discount="5.000")

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")
    await buy(client, driver, plan_id)
    row = await subscription_of(session_factory, driver["driver_id"])
    assert row.discount_amount == Decimal("5.000")


# ------------------------------------------------------ (ب) حدُّ الاستعمال


async def test_the_cap_is_counted_per_offer_not_per_month(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """التجديدُ المبكر يبدأ من `coverage_until` — فبلا حدٍّ يأخذ الخصمَ مراراً."""
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="10", max_uses=1)

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "200.000")

    discounts = []
    for _ in range(3):
        await buy(client, driver, plan_id)
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(DriverSubscription)
                .where(
                    DriverSubscription.driver_id == driver["driver_id"]
                )
                .order_by(DriverSubscription.created_at)
            )
        ).scalars().all()
        discounts = [row.discount_amount for row in rows]

    assert len(discounts) == 3
    assert discounts[0] == Decimal("3.000")
    # والثانيةُ والثالثةُ بلا خصم — الحدُّ لكل عرضٍ لا لكل شهر
    assert discounts[1] == Decimal("0")
    assert discounts[2] == Decimal("0")


# ------------------------------------------------------------ (٣) الجمهور


async def test_new_driver_audience_excludes_a_returning_buyer(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="20", audience=AUDIENCE_NEW_DRIVER)

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "200.000")

    for _ in range(2):
        await buy(client, driver, plan_id)
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(DriverSubscription)
                .where(
                    DriverSubscription.driver_id == driver["driver_id"]
                )
                .order_by(DriverSubscription.created_at)
            )
        ).scalars().all()

    # **الكبتنُ الذي اشترك مرةً لم يعد جديداً** — والشرطُ يُقاس لحظةَ الشراء
    assert rows[0].discount_amount == Decimal("6.000")
    assert rows[1].discount_amount == Decimal("0")


async def test_a_manual_offer_reaches_only_the_granted_driver(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    offer_id = await make_offer(
        session_factory, percent="30", audience=AUDIENCE_MANUAL
    )

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")

    await buy(client, driver, plan_id)
    row = await subscription_of(session_factory, driver["driver_id"])
    assert row.discount_amount == Decimal("0")

    async with session_factory() as session:
        session.add(
            SubscriptionOfferGrant(
                offer_id=offer_id,
                driver_id=driver["driver_id"],
                note="اختبار",
            )
        )
        await session.commit()

    await buy(client, driver, plan_id)
    row = await subscription_of(session_factory, driver["driver_id"])
    assert row.discount_amount == Decimal("9.000")


async def test_a_lapsed_offer_is_not_shown_to_a_covered_driver(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """**(و)**: وإلا صار العرضُ إعلاناً بأن الانقطاع يُكافأ."""
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(
        session_factory, percent="40", audience=AUDIENCE_LAPSED, lapsed_days=30
    )

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "200.000")

    # اشتراكٌ أولُ يجعل تغطيتَه سارية
    await buy(client, driver, plan_id)
    await buy(client, driver, plan_id)
    row = await subscription_of(session_factory, driver["driver_id"])
    assert row.discount_amount == Decimal("0")


# ------------------------------------------------------------ الميزانية


async def test_the_budget_stops_the_offer(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    # ميزانيةٌ تكفي خصماً واحداً (٣٫٠٠٠) ولا تكفي اثنين
    await make_offer(session_factory, percent="10", budget="4.000", max_uses=0)

    first = await approved_driver(client, session_factory, subscribed=False)
    second = await approved_driver(
        client, session_factory, payload=SECOND_DRIVER, subscribed=False,
        plate_number="AMM-9191",
    )
    for driver in (first, second):
        await topup_wallet(client, admin_headers, driver["user_id"], "100.000")
        await buy(client, driver, plan_id)

    async with session_factory() as session:
        rows = (
            await session.execute(select(DriverSubscription))
        ).scalars().all()
    discounts = sorted(row.discount_amount for row in rows)
    assert discounts == [Decimal("0"), Decimal("3.000")]


# ------------------------------------------------------------ التزامن


async def test_two_simultaneous_buyers_cannot_exceed_the_budget(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """**قفلُ صفّ العرض** — وبحذفه يمرّ الاثنان على ميزانيةٍ تكفي واحداً.

    **والتداخلُ مُرتَّبٌ عمداً لا متروكٌ للحظ**: أولُ نسخةٍ من هذا الاختبار
    استعملت `asyncio.gather` على مسار HTTP **فمرّت والقفلُ محذوف** — لأن الأولَ
    ثبّت قبل أن يبدأ الثاني، فلم يتداخلا أصلاً. فيُقاد المسارُ هنا بجلستين:
    الأولى تشتري وتُمسك معاملتَها، والثانيةُ تبدأ وهي مفتوحة.
    """
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="10", budget="4.000", max_uses=0)

    first = await approved_driver(client, session_factory, subscribed=False)
    second = await approved_driver(
        client,
        session_factory,
        payload=SECOND_DRIVER,
        subscribed=False,
        plate_number="AMM-9191",
    )
    for driver in (first, second):
        await topup_wallet(client, admin_headers, driver["user_id"], "100.000")

    async def _purchase(driver: dict, hold: float, delay: float) -> None:
        from app.models.driver import Driver
        from app.models.user import User
        from app.services import subscriptions

        await asyncio.sleep(delay)
        async with session_factory() as session:
            driver_row = await session.get(Driver, driver["driver_id"])
            user_row = await session.get(User, uuid.UUID(driver["user_id"]))
            await subscriptions.purchase_with_wallet(
                session,
                driver=driver_row,
                user=user_row,
                plan_id=plan_id,
                idempotency_key=uuid.uuid4().hex,
            )
            await asyncio.sleep(hold)
            await session.commit()

    await asyncio.wait_for(
        asyncio.gather(
            _purchase(first, hold=0.4, delay=0.0),
            _purchase(second, hold=0.0, delay=0.1),
        ),
        timeout=15,
    )

    async with session_factory() as session:
        given = Decimal(
            await session.scalar(
                select(func.coalesce(func.sum(DriverSubscription.discount_amount), 0))
            )
            or 0
        )
    # **الميزانيةُ حدٌّ لا اقتراح**: ٣٫٠٠٠ لواحدٍ منهما، ولا ٦٫٠٠٠ لكليهما
    assert given == Decimal("3.000"), given


async def test_two_simultaneous_manual_records_consume_one_use_not_two(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """حدُّ «مرةٍ واحدة» — و**قفلان يحرسانه، وأيُّهما كفى**.

    قِيس بالحذف لا بالقراءة، وثلاثَ مرات:

    * حذفُ قفلِ صفّ الكبتن وحدَه ← يمرّ (يُسلسِل قفلُ صفّ العرض).
    * حذفُ قفلِ صفّ العرض وحدَه ← يمرّ (يُسلسِل قفلُ صفّ الكبتن).
    * **حذفُهما معاً ← `['3.000', '3.000']`**: عرضٌ حدُّه واحدٌ مُنح مرتين.

    وهو شكلُ سلف الكباتن نفسُه (البند ١٥): قفلان يملكان الثابتَ معاً، فحذفُ
    أحدهما لا يُثبت شيئاً. **ولا يُقاس على مسار المحفظة**: هناك يُسلسِلهما
    القفلُ الاستشاريُّ للمحفظة أيضاً — ثالثٌ يخفي الاثنين — فيُقاد المسارُ
    اليدويُّ الذي لا يكتب قيداً في الدفتر أصلاً.
    """
    from app.models.driver import Driver
    from app.models.enums import PaymentMethod as Method
    from app.models.user import User
    from app.services import subscriptions

    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="10", max_uses=1)

    driver = await approved_driver(client, session_factory, subscribed=False)

    async def _record(hold: float, delay: float) -> None:
        await asyncio.sleep(delay)
        async with session_factory() as session:
            driver_row = await session.get(Driver, driver["driver_id"])
            user_row = await session.get(User, uuid.UUID(driver["user_id"]))
            actor = await session.scalar(
                select(User).where(User.role == "admin").limit(1)
            )
            await subscriptions.record_manual(
                session,
                driver=driver_row,
                user=user_row,
                plan_id=plan_id,
                method=Method.CASH,
                amount_paid=None,
                reference=None,
                actor=actor or user_row,
            )
            await asyncio.sleep(hold)
            await session.commit()

    await asyncio.wait_for(
        asyncio.gather(_record(0.4, 0.0), _record(0.0, 0.1)),
        timeout=15,
    )

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(DriverSubscription).where(
                    DriverSubscription.driver_id == driver["driver_id"]
                )
            )
        ).scalars().all()

    assert len(rows) == 2
    discounted = [row for row in rows if row.discount_amount > 0]
    assert len(discounted) == 1, [str(row.discount_amount) for row in rows]


async def test_the_cap_holds_on_the_wallet_path_too(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """نفسُ الحدّ على مسار المحفظة — **ويحرسه القفلان نفسُهما، لا ثالثَ لهما**.

    **والقفلُ الاستشاريُّ للمحفظة لا يحرسه، وقد قِيس**: بحذف قفلَي الكبتن
    والعرض وإبقائه وحدَه خرج `['3.000', '3.000']` — أي أنه **لا يمنع شيئاً**
    من هذا الحدّ. والسببُ في الترتيب لا في القفل: `offers.resolve` تقع
    **قبل** `wallet.record` في `purchase_with_wallet`، فيقرأ المساران عدَّ
    الاستعمالات قبل أن يطلب أيٌّ منهما قفلَ المحفظة — والقفلُ الذي يأتي بعد
    القراءة لا يُسلسِلها.

    فلا اعتمادَ صامتٌ هنا يُوثَّق، ولا اختبارٌ يمكن أن «يفشل بحذف قفل
    المحفظة»: ما لا يحرس شيئاً لا يُسقط بحذفه شيء. وهذا الاختبارُ يحرس الثابتَ
    على هذا المسار، ويسقط بحذف القفلين — كأخيه على المسار اليدوي.
    """
    from app.models.driver import Driver
    from app.models.user import User
    from app.services import subscriptions

    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="10", max_uses=1)

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "200.000")

    async def _purchase(hold: float, delay: float) -> None:
        await asyncio.sleep(delay)
        async with session_factory() as session:
            driver_row = await session.get(Driver, driver["driver_id"])
            user_row = await session.get(User, uuid.UUID(driver["user_id"]))
            await subscriptions.purchase_with_wallet(
                session,
                driver=driver_row,
                user=user_row,
                plan_id=plan_id,
                idempotency_key=uuid.uuid4().hex,
            )
            await asyncio.sleep(hold)
            await session.commit()

    await asyncio.wait_for(
        asyncio.gather(_purchase(0.4, 0.0), _purchase(0.0, 0.1)), timeout=15
    )

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(DriverSubscription).where(
                    DriverSubscription.driver_id == driver["driver_id"]
                )
            )
        ).scalars().all()
    discounted = [row for row in rows if row.discount_amount > 0]
    assert len(discounted) == 1, [str(row.discount_amount) for row in rows]


# --------------------------------------------------------------- اللوحة


async def test_the_panel_creates_lists_and_disables(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """**والإطفاءُ لا الحذف**: عرضٌ اشترى به أحدٌ يمحو حذفُه سببَ خصمه."""
    created = await client.post(
        "/admin/subscription-offers",
        params={"country_code": "JO"},
        json={
            "name": "ترحيبٌ بالكباتن",
            "discount_value": "15",
            "audience": "new_driver",
            "max_uses_per_driver": 1,
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    offer_id = created.json()["id"]

    listed = await client.get(
        "/admin/subscription-offers",
        params={"country_code": "JO"},
        headers=admin_headers,
    )
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item["id"] == offer_id)
    assert row["is_active"] is True
    # جدولُ التنازل يبدأ من صفرٍ لا من غياب
    assert row["subscriptions_sold"] == 0
    assert row["total_given_up"] == "0.000"
    assert row["manual_adjustments"] == 0

    off = await client.patch(
        f"/admin/subscription-offers/{offer_id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert off.status_code == 200
    assert off.json()["is_active"] is False


async def test_a_manual_grant_is_refused_on_a_computed_audience(
    client, admin_headers, jordan_wallet
) -> None:
    """منحٌ لعرضٍ جمهورُه محسوبٌ **لا أثرَ له** — فيُرفض بدل أن يُقبل ولا يفعل.

    وقبولُه يجعل المشرفَ يظنّ أنه منح كبتناً شيئاً، ثم يسأل «لماذا لم يصله؟».
    """
    created = await client.post(
        "/admin/subscription-offers",
        params={"country_code": "JO"},
        json={"name": "عرضٌ عام", "discount_value": "10", "audience": "all"},
        headers=admin_headers,
    )
    offer_id = created.json()["id"]

    refused = await client.post(
        f"/admin/subscription-offers/{offer_id}/grants",
        json={"driver_id": str(uuid.uuid4()), "note": "تجربة"},
        headers=admin_headers,
    )
    assert refused.status_code == 422, refused.text
    assert "اليدوي" in refused.json()["message"]


async def test_the_giveaway_table_marks_a_manual_adjustment(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """**وسمُ التسوية مقارنةٌ حيّةٌ بين رقمين مجمَّدين** لا عمودٌ يُخزَّن.

    ويقع حين يحصّل المشرفُ مبلغاً غيرَ المعبَّأ — بلا منعٍ وبلا سببٍ يُطلب.
    """
    from app.models.driver import Driver
    from app.models.enums import PaymentMethod as Method
    from app.models.user import User
    from app.services import subscriptions

    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    offer_id = await make_offer(session_factory, percent="10", max_uses=0)

    driver = await approved_driver(client, session_factory, subscribed=False)

    async with session_factory() as session:
        driver_row = await session.get(Driver, driver["driver_id"])
        user_row = await session.get(User, uuid.UUID(driver["user_id"]))
        # المشرفُ حصّل السعرَ كاملاً — خلافاً للمعبَّأ (٢٧)
        await subscriptions.record_manual(
            session,
            driver=driver_row,
            user=user_row,
            plan_id=plan_id,
            method=Method.CASH,
            amount_paid=PLAN_PRICE,
            reference=None,
            actor=user_row,
        )
        await session.commit()

    listed = await client.get(
        "/admin/subscription-offers",
        params={"country_code": "JO"},
        headers=admin_headers,
    )
    row = next(item for item in listed.json() if item["id"] == str(offer_id))
    assert row["subscriptions_sold"] == 1
    # **ما تنازلنا عنه صفرٌ** لأن المقبوض كامل — والوسمُ يقول إن ذلك بقرار مشرف
    assert row["total_given_up"] == "0.000"
    assert row["manual_adjustments"] == 1


# ------------------------------------------- «استفدتَ منه من قبل» (١٧.٧)


async def test_an_exhausted_offer_is_named_but_never_applied(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """**يُذكر ولا يُطبَّق**: من رأى الخصمَ ثم اختفى يظنّ التطبيقَ عطب.

    والتمييزُ هو المقصود: هذا **استفاد** فيُقال له، ومن لم يستحقّ قطُّ لا
    يُقال له شيء (الفرع و) — واختبارُ الحالتين معاً في ملفٍ واحد.
    """
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="10", max_uses=1, name="عرضٌ مرةً")

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")

    first = (await client.get("/subscriptions/plans", headers=driver["headers"])).json()
    row = next(p for p in first if p["id"] == str(plan_id))
    assert row["offer_name"] == "عرضٌ مرةً"
    assert row["exhausted_offer_name"] is None

    await buy(client, driver, plan_id)

    after = (await client.get("/subscriptions/plans", headers=driver["headers"])).json()
    row = next(p for p in after if p["id"] == str(plan_id))
    # لا خصمَ بعد الاستنفاد — **ويُقال سببُه**
    assert row["offer_name"] is None
    assert row["price_after_discount"] is None
    assert row["exhausted_offer_name"] == "عرضٌ مرةً"


async def test_a_driver_who_never_qualified_is_told_nothing(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """**الصمتُ لمن لم يستحقّ** — وإلا صار العرضُ إعلاناً عمّا ليس له."""
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(
        session_factory, percent="30", audience=AUDIENCE_MANUAL, max_uses=1
    )

    driver = await approved_driver(client, session_factory, subscribed=False)
    rows = (await client.get("/subscriptions/plans", headers=driver["headers"])).json()
    row = next(p for p in rows if p["id"] == str(plan_id))
    assert row["offer_name"] is None
    assert row["exhausted_offer_name"] is None


async def test_the_exhausted_line_never_shows_beside_a_live_discount(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """عرضٌ استُنفد **وآخرُ قائم** — يُعرض القائمُ وحدَه.

    وسطرٌ عن عرضٍ منتهٍ فوق خصمٍ يعمل يربك قارئَه ويشكّكه في الرقم المعروض.
    """
    await enable_features(
        session_factory, FeatureKey.SUBSCRIPTION_OFFERS_ENABLED.value
    )
    plan_id = await ensure_plan(session_factory)
    await make_offer(session_factory, percent="10", max_uses=1, name="مرةً واحدة")

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")
    await buy(client, driver, plan_id)

    # عرضٌ ثانٍ بلا حدّ — فيبقى منطبقاً
    await make_offer(session_factory, percent="5", max_uses=0, name="بلا حدّ")

    rows = (await client.get("/subscriptions/plans", headers=driver["headers"])).json()
    row = next(p for p in rows if p["id"] == str(plan_id))
    assert row["offer_name"] == "بلا حدّ"
    assert row["exhausted_offer_name"] is None


async def test_the_advance_terms_reach_the_driver_before_he_agrees(
    client, session_factory, admin_headers, jordan_wallet
) -> None:
    """شرطُ السداد يُنشر مع الأهلية — **قبل الموافقة لا بعدها**.

    وكان `GET /drivers/me/advances` لا يحمل الاقتطاعَ ولا الحدَّ الأدنى، فورقةُ
    التأكيد لا تجد ما تعرضه — بابٌ يطلب موافقةً على شرطٍ لا يُرى.
    """
    driver = await approved_driver(client, session_factory, subscribed=False)
    response = await client.get("/drivers/me/advances", headers=driver["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    for field in ("deduction_percent", "min_kept_amount", "term_days"):
        assert field in body, field
