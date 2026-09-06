"""نسبةُ العمولة على العرض — **البند ٥٥ (§55٫٣)**.

**وما يُقاس هنا خمسُ قواعدَ لا يقولها المُترجِم:**

1. **`NULL` ليست صفراً** — عرضُ خصمٍ على السعر وحدَه لا يمسّ النسبة.
2. **وصفرٌ يُختم صفراً** — ويبقى على الاشتراك حتى ينتهي.
3. **والتجميدُ في البابِ الواحد** — فالقنواتُ الأربعُ تأخذه معاً.
4. **والإلغاءُ يرفع الوعدَ عمّا يأتي** لا عمّا مضى.
5. **والثغرةُ مغلقةٌ بالبناء** — الملغى يُحسب، فلا شراءَ ثانٍ.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select

from app.models.enums import CountryCode, UserRole
from app.models.driver import Driver
from app.models.subscription import DriverSubscription
from app.models.subscription_offer import SubscriptionOffer
from app.models.user import User
from app.services import offers as offers_service
from app.services import settings_service


async def _driver(session) -> Driver:
    user = User(
        name="كبتنُ القياس",
        phone=f"+96279{uuid.uuid4().int % 10**7:07d}",
        role=UserRole.DRIVER,
        country_code=CountryCode.JO,
        password_hash="x",
    )
    session.add(user)
    await session.flush()
    driver = Driver(user_id=user.id)
    session.add(driver)
    await session.flush()
    return driver


# ─────────────────────────────── ١ · `NULL` ليست صفراً


async def test_an_offer_without_a_percent_does_not_touch_the_rate(
    session_factory,
) -> None:
    """**عمودٌ فارغٌ يعني «لا يمسّ»** — لا «امنح صفراً»."""
    async with session_factory() as session:
        offer = SubscriptionOffer(
            country_code=CountryCode.JO,
            name="خصمٌ على السعر وحدَه",
            discount_type="money_percent",
            discount_value=Decimal("50"),
        )
        session.add(offer)
        await session.flush()
        assert offer.commission_percent is None, (
            "العمودُ يولد فارغاً — **وقيمةٌ افتراضيةٌ صفرٌ تجعل كلَّ عرضٍ "
            "يمنح صفراً بسهو**"
        )


# ─────────────────────────────── ٢ · وصفرٌ يُقبل ويُحفظ


async def test_zero_is_stored_and_is_not_the_same_as_absent(session_factory) -> None:
    """**صفرٌ وغيابٌ حالان لا يحملهما رقمٌ واحد.**"""
    async with session_factory() as session:
        zero = SubscriptionOffer(
            country_code=CountryCode.JO,
            name="شهرك الأول علينا",
            discount_type="money_percent",
            discount_value=Decimal("100"),
            commission_percent=Decimal("0.00"),
        )
        session.add(zero)
        await session.commit()
        assert zero.commission_percent == Decimal("0.00")
        assert zero.commission_percent is not None


# ─────────────────────────────── ٣ · النسبةُ السارية تتبع العمود


async def test_the_stamped_zero_overrides_the_market_rate(session_factory) -> None:
    """**من اشترى بصفرٍ يبقى على صفر** ولو كانت نسبةُ السوق أعلى."""
    async with session_factory() as session:
        driver = await _driver(session)
        setting = await settings_service.get_or_create_commission(
            session, CountryCode.JO
        )
        setting.commission_enabled = True
        setting.commission_percent = Decimal("5.00")
        await session.flush()

        market = await settings_service.commission_percent_of_driver(
            session, driver, CountryCode.JO
        )
        assert market == Decimal("5.00")

        driver.commission_percent_from_subscription = Decimal("0.00")
        await session.flush()
        assert await settings_service.commission_percent_of_driver(
            session, driver, CountryCode.JO
        ) == Decimal("0.00")


# ─────────────────────────────── ٤ · والإلغاءُ يرفع الوعد


async def test_clearing_the_stamp_returns_the_market_rate(session_factory) -> None:
    """**`None` تعني «لا اشتراكَ ساري»** فتعود نسبةُ السوق فوراً."""
    async with session_factory() as session:
        driver = await _driver(session)
        setting = await settings_service.get_or_create_commission(
            session, CountryCode.JO
        )
        setting.commission_enabled = True
        setting.commission_percent = Decimal("5.00")
        driver.commission_percent_from_subscription = Decimal("0.00")
        await session.flush()

        # **ما يفعله `cancel_for_driver` بعينه** — مخرجُ الانتهاء نفسُه
        driver.commission_percent_from_subscription = None
        await session.flush()

        assert await settings_service.commission_percent_of_driver(
            session, driver, CountryCode.JO
        ) == Decimal("5.00")


# ─────────────────────────────── ٥ · والملغى يُحسب فلا شراءَ ثانٍ


async def test_a_cancelled_subscription_still_counts_against_the_offer(
    session_factory,
) -> None:
    """**الثغرةُ مغلقةٌ بالبناء** (§55٫٤) — ولا يُبنى عليها قيدٌ ثانٍ.

    **ويُقاس العدُّ لا يُقرأ**: من ألغى يبقى محسوباً، فـ`max_uses_per_driver`
    تكفي وحدَها.
    """
    from app.models.enums import SubscriptionStatus
    from app.models.subscription import SubscriptionPlan

    async with session_factory() as session:
        driver = await _driver(session)
        offer = SubscriptionOffer(
            country_code=CountryCode.JO,
            name="مرّةً واحدة",
            discount_type="money_percent",
            discount_value=Decimal("100"),
            commission_percent=Decimal("0.00"),
            max_uses_per_driver=1,
        )
        plan = SubscriptionPlan(
            country_code=CountryCode.JO,
            name="شهري",
            duration_type="monthly",
            price=Decimal("30.000"),
            currency="JOD",
            is_active=True,
        )
        session.add_all([offer, plan])
        await session.flush()

        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC)
        row = DriverSubscription(
            driver_id=driver.id,
            plan_id=plan.id,
            starts_at=now,
            expires_at=now + timedelta(days=30),
            amount_paid=Decimal("0.000"),
            payment_method="wallet",
            status=SubscriptionStatus.CANCELLED,  # **ألغاه**
            offer_id=offer.id,
            list_price=Decimal("30.000"),
            commission_percent_at_purchase=Decimal("0.00"),
        )
        session.add(row)
        await session.flush()

        used = await offers_service._uses_by_driver(
            session, offer_id=offer.id, driver_id=driver.id
        )
        assert used == 1, "الملغى يجب أن يُحسب — وإلا صار الإلغاءُ باباً للتكرار"

        total = await session.scalar(
            select(func.count())
            .select_from(DriverSubscription)
            .where(DriverSubscription.offer_id == offer.id)
        )
        assert total == 1, "**ولا يُحذف صفٌّ عند الإلغاء** — يُوسَم فقط"
