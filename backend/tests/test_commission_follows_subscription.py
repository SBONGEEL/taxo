"""تشغيلُ العمولة لا يمسّ اشتراكاً قائماً (2026-08-20، SPEC §25.11).

**وما يُقاس هنا ليس صدقَ الوعد وحدَه، بل أن الزرَّ صار قابلاً للاستعمال**:
بلا هذا الربط، أولُ ضغطةٍ على «شغّل العمولة» تمسّ كلَّ من اشترك أمسِ على وعد
صفر — فلا يُضغط أبداً ويبقى مبنيّاً لا يُستعمل.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.commission import CommissionSetting
from app.models.driver import Driver
from app.models.enums import CommissionAppliesTo, CountryCode
from app.models.ride import Ride

pytestmark = pytest.mark.asyncio


async def _enable_commission(session_factory, percent: str = "15") -> None:
    async with session_factory() as session:
        row = await session.scalar(
            select(CommissionSetting).where(
                CommissionSetting.country_code == CountryCode.JO
            )
        )
        if row is None:
            row = CommissionSetting(country_code=CountryCode.JO)
            session.add(row)
        row.commission_enabled = True
        row.commission_percent = Decimal(percent)
        row.applies_to = CommissionAppliesTo.ALL_RIDES
        await session.commit()


async def test_a_running_subscription_keeps_its_frozen_percent(
    client, session_factory, jordan_settings, stub_mapbox, fast_dispatch
) -> None:
    """**من اشترى على صفرٍ يُكمل مدّتَه بصفر** — ولو أُشعلت العمولةُ بعده."""
    from tests.helpers import accepted_ride, approved_driver, bring_online, rider_session

    driver = await approved_driver(client, session_factory)

    # اشتراكُه كُتب والعمولةُ مطفأة ⇒ النسبةُ المجمَّدةُ صفر
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        assert row.commission_percent_from_subscription == Decimal("0.00"), (
            "الشراءُ لم يكتب العمودَ المحضَّر"
        )

    # ثم تُشعَل العمولة
    await _enable_commission(session_factory, "15")

    rider = await rider_session(client)
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider["headers"], driver)

    async with session_factory() as session:
        stored = await session.get(Ride, ride["id"])
        assert stored.commission_percent_at_ride == Decimal("0.00"), (
            "إشعالُ العمولة مسَّ صاحبَ اشتراكٍ قائم — والوعدُ «ما دام سارياً»"
        )


async def test_a_driver_with_no_subscription_pays_the_market_percent(
    client, session_factory, jordan_settings, stub_mapbox, fast_dispatch
) -> None:
    """**ومن لا اشتراكَ له تُطبَّق نسبةُ سوقه** — و`None` ليست صفراً."""
    from tests.helpers import accepted_ride, approved_driver, bring_online, rider_session

    await _enable_commission(session_factory, "15")
    driver = await approved_driver(client, session_factory)

    # يُمحى أثرُ اشتراكه ليُقاس مسارُ «لا اشتراك»
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        row.commission_percent_from_subscription = None
        await session.commit()

    rider = await rider_session(client)
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider["headers"], driver)

    async with session_factory() as session:
        stored = await session.get(Ride, ride["id"])
        assert stored.commission_percent_at_ride == Decimal("15.00")


async def test_expiry_lifts_him_to_the_new_percent(
    client, session_factory, jordan_settings
) -> None:
    """**وانتهاءُ التغطية يرفعه إلى النسبة الجديدة** — لا يُبقيه على وعدٍ انقضى."""
    from datetime import UTC, datetime, timedelta

    from app.models.subscription import DriverSubscription
    from app.services import subscriptions
    from tests.helpers import approved_driver

    driver = await approved_driver(client, session_factory)
    await _enable_commission(session_factory, "15")

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        assert row.commission_percent_from_subscription == Decimal("0.00")

        # يُقدَّم انتهاؤه إلى الماضي
        subs = (
            await session.scalars(
                select(DriverSubscription).where(
                    DriverSubscription.driver_id == driver["driver_id"]
                )
            )
        ).all()
        # **يُقدَّم الطرفان معاً**: `ck_..._period_positive` يمنع نهايةً قبل
        # بدايةٍ — حارسٌ يعمل، فالماضي يُبنى بإزاحةِ الاثنين لا بواحد
        for sub in subs:
            sub.starts_at = datetime.now(UTC) - timedelta(days=31)
            sub.expires_at = datetime.now(UTC) - timedelta(hours=1)
        await session.commit()

    async with session_factory() as session:
        await subscriptions.expire_due(session)
        await session.commit()

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        assert row.commission_percent_from_subscription is None, (
            "انقضى اشتراكُه والعمودُ ما زال يحمل وعدَه"
        )


async def test_the_purchase_freezes_the_percent_on_the_subscription_row(
    client, session_factory, jordan_settings
) -> None:
    """**والتجميدُ على الصفِّ نفسِه** — فتعديلُ الإعداد لا يحرّك بيعاً وقع."""
    from app.models.subscription import DriverSubscription
    from tests.helpers import approved_driver

    driver = await approved_driver(client, session_factory)

    async with session_factory() as session:
        sub = await session.scalar(
            select(DriverSubscription).where(
                DriverSubscription.driver_id == driver["driver_id"]
            )
        )
        assert sub is not None
        assert sub.commission_percent_at_purchase == Decimal("0.00")

    await _enable_commission(session_factory, "20")

    async with session_factory() as session:
        sub = await session.scalar(
            select(DriverSubscription).where(
                DriverSubscription.driver_id == driver["driver_id"]
            )
        )
        assert sub.commission_percent_at_purchase == Decimal("0.00"), (
            "تعديلُ الإعداد حرّك بيعاً وقع"
        )
