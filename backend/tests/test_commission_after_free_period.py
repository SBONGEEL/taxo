"""**العمولةُ بعد فترة الكبتن المجّانيّة وحدَها** (أمرُ المالك العاشر ٢٠٢٦-١١-٢٥، SPEC §١١٤-ج).

* **قبل الإطلاق**: لا عمولةَ على أيِّ كبتن — ولو أُشعلت العمولةُ ٤٪، **ولو كان اشتراكُه المدفوعُ مجمَّداً على ٤٪**.
* **بعد الإطلاق ومنحتُه سارية** (٦٠ يوماً لمن سبق، ٧ لمن تأخّر): صفر.
* **بعد انقضاء منحته**: ٤٪ — **قيدٌ واحدٌ في الدفتر للرحلة**.

**وما يُقاس هو ما يُجمَّد على الرحلة لحظةَ القبول وما يُكتب في الدفتر بعد الدفع** — لا ما يرسمه شاشة.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import CountryCode, WalletTransactionType
from app.models.launch_campaign import LaunchCampaign, LaunchCampaignGrant
from app.models.ride import Ride
from app.models.wallet import WalletTransaction
from tests.helpers import (
    RIDER,
    SECOND_DRIVER,
    approved_driver,
    bring_online,
    completed_ride,
    pay_ride,
    rider_session,
    set_commission,
    topup_wallet,
)

#: **هذه الوحدةُ تضبط يومَ الإطلاق بنفسها** — فلا يُثبَّت في الماضي (`conftest._launched_market`)
CAMPAIGN_DEFAULTS = True


async def _launch_on(session_factory, day: date) -> None:
    async with session_factory() as session:
        session.add(LaunchCampaign(country_code=CountryCode.JO, launch_date=day))
        await session.commit()


async def _grant(session_factory, driver_id: uuid.UUID, *, ends_in: timedelta) -> None:
    """**منحةٌ تنتهي بعد `ends_in`** (أو انتهت إن كانت سالبة) — كما يكتبها المسحُ، بلا اشتراك: ما يُقاس هو الفترة لا المنحة."""
    now = datetime.now(UTC)
    async with session_factory() as session:
        session.add(
            LaunchCampaignGrant(
                driver_id=driver_id, country_code=CountryCode.JO, kind="pre",
                starts_at=now - timedelta(days=60), ends_at=now + ends_in,
            )
        )
        await session.commit()


async def _paid_ride(
    client: AsyncClient, admin_headers: dict, session_factory, driver: dict, phone: str
) -> tuple[Ride, tuple[int, Decimal]]:
    """رحلةٌ مكتملةٌ مدفوعةٌ بالمحفظة ⇐ (الرحلةُ كما حُفظت، (عددُ قيود العمولة لها، مجموعُها))."""
    rider = await rider_session(client, {**RIDER, "phone": phone})
    await topup_wallet(client, admin_headers, rider["user"]["id"], "50.000")
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)
    # **مفتاحٌ لكلِّ رحلة**: المفتاحُ الافتراضيُّ واحد، فدفعةُ الرحلة الثانية كانت تُعيد الأولى ولا تُنشأ (قِيس: «الدفعات []»)
    paid = await pay_ride(client, rider["headers"], ride["id"], "wallet", key=f"pay-{phone}")
    assert paid.status_code == 201, paid.text
    async with session_factory() as session:
        stored = await session.get(Ride, uuid.UUID(ride["id"]))
        # **العمولةُ تُكتب قيداً من محفظته، أو دَيناً حين لا يغطّيها رصيدُه المتاح** (`payments._charge_commission`) — والدَّينُ يُحصَّل
        # من الرصيد في المعاملة نفسِها. فـ«مرّةً لكلِّ رحلة» = قيودُ العمولة **ودُيونُها** معاً، لا أحدُهما.
        ledger = (
            await session.execute(
                select(func.count(), func.coalesce(func.sum(-WalletTransaction.amount), 0)).where(
                    WalletTransaction.ride_id == stored.id, WalletTransaction.type == WalletTransactionType.COMMISSION
                )
            )
        ).one()
        owed = (
            await session.execute(
                select(func.count(), func.coalesce(func.sum(DriverDebt.amount), 0)).where(DriverDebt.ride_id == stored.id)
            )
        ).one()
    return stored, (ledger[0] + owed[0], Decimal(ledger[1]) + Decimal(owed[1]))


async def _frozen_on_subscription(session_factory, driver_id) -> Decimal | None:
    async with session_factory() as session:
        return (await session.get(Driver, driver_id)).commission_percent_from_subscription


async def test_before_launch_no_captain_pays_commission_even_on_a_four_percent_subscription(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await set_commission(session_factory, "4")
    await _launch_on(session_factory, date.today() + timedelta(days=30))
    driver = await approved_driver(client, session_factory)
    # **اشتراكُه المدفوعُ اشتُري والعمولةُ ٤٪** ⇐ مجمَّدٌ عليها — وهو بعينه ما كان سيُحصَّل منه بلا القاعدة
    assert await _frozen_on_subscription(session_factory, driver["driver_id"]) == Decimal("4.00")

    me = (await client.get("/drivers/me", headers=driver["headers"])).json()
    assert Decimal(me["commission_percent"]) == 0, "شاشتُه تقول عمولةً قبل الإطلاق"

    ride, (count, total) = await _paid_ride(client, admin_headers, session_factory, driver, "0791000001")
    assert ride.commission_percent_at_ride == Decimal("0.00"), "رحلةُ ما قبل الإطلاق جُمّدت بعمولة"
    assert (count, Decimal(total)) == (0, 0), "عمولةٌ (قيدٌ أو دَين) قبل الإطلاق"


async def test_during_his_grant_nothing_and_after_it_four_percent_once_per_ride(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await set_commission(session_factory, "4")
    await _launch_on(session_factory, date.today() - timedelta(days=61))
    driver = await approved_driver(client, session_factory)
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        # **بلا اشتراكٍ مجمَّد** — فما يُقاس قاعدةُ الفترة لا وعدُ الاشتراك
        row.commission_percent_from_subscription = None
        # **كبتنُ ما قبل الإطلاق** — ونافذتُه الستّون انقضت أمس، فما يحكم بعدها منحتُه وحدَها
        row.first_approved_at = datetime.now(UTC) - timedelta(days=70)
        await session.commit()

    # **منحتُه ساريةٌ يوماً آخر** ⇐ صفر
    await _grant(session_factory, driver["driver_id"], ends_in=timedelta(days=1))
    ride, (count, total) = await _paid_ride(client, admin_headers, session_factory, driver, "0791000002")
    assert ride.commission_percent_at_ride == Decimal("0.00"), "عمولةٌ في فترته المجّانيّة"
    assert (count, Decimal(total)) == (0, 0)

    # **انقضت منحتُه** ⇐ ٤٪، وقيدٌ واحدٌ للرحلة
    async with session_factory() as session:
        grant = await session.scalar(select(LaunchCampaignGrant).where(LaunchCampaignGrant.driver_id == driver["driver_id"]))
        grant.ends_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()
    me = (await client.get("/drivers/me", headers=driver["headers"])).json()
    assert Decimal(me["commission_percent"]) == Decimal("4"), "انقضت فترتُه وشاشتُه ما زالت تقول صفراً"
    ride, (count, total) = await _paid_ride(client, admin_headers, session_factory, driver, "0791000003")
    assert ride.commission_percent_at_ride == Decimal("4.00")
    expected = (ride.final_fare * Decimal("0.04")).quantize(Decimal("0.001"))
    if count != 1:
        # **تشخيصٌ يُطبع مع السقوط**: دفعاتُ الرحلة وقيودُها كما كُتبت — فلا يُخمَّن أين ضاعت العمولة
        from app.models.payment import Payment

        async with session_factory() as session:
            pays = (await session.execute(select(Payment.method, Payment.amount, Payment.status).where(Payment.ride_id == ride.id))).all()
            txs = (await session.execute(select(WalletTransaction.type, WalletTransaction.amount).where(WalletTransaction.ride_id == ride.id))).all()
        raise AssertionError(f"قيودُ العمولة للرحلة {count} لا واحد · الأجرة {ride.final_fare} · الدفعات {pays} · القيود {txs}")
    assert Decimal(total) == expected, f"العمولةُ {total} لا {expected} (٤٪ من {ride.final_fare})"


async def test_the_campaign_without_zero_commission_charges_from_day_one(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**والإعفاءُ يتبع «بصفر عمولة» في الحملة** — يُطفئه المالكُ من اللوحة فتعود نسبةُ السوق ولو قبل الإطلاق."""
    from app.services import launch_campaign

    await set_commission(session_factory, "4")
    await _launch_on(session_factory, date.today() + timedelta(days=30))
    driver = await approved_driver(client, session_factory)
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        assert await launch_campaign.commission_free(session, row) is True
        campaign = await launch_campaign.get(session, CountryCode.JO)
        campaign.zero_commission = False
        await session.flush()
        assert await launch_campaign.commission_free(session, row) is False


async def test_the_window_counts_from_launch_even_when_his_grant_waits_behind_a_paid_subscription(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**قِيس على الإنتاج ٢٠٢٦-١١-٢٥**: منحةُ الكبتن تُلحق بعد اشتراكه المدفوع، فتبدأ في فبراير لمن اشترى شهراً في ديسمبر — **ولا يُحصَّل منه
    شيءٌ بين ١/١ وبدئها**: ٦٠ يوماً من الإطلاق لمن سبقه، و٧ من اعتماده لمن بعده، **بلا منحةٍ مكتوبةٍ بعد**."""
    from app.services import launch_campaign

    launch = date.today() - timedelta(days=10)
    await _launch_on(session_factory, launch)
    early = await approved_driver(client, session_factory)
    late = await approved_driver(client, session_factory, SECOND_DRIVER)
    async with session_factory() as session:
        campaign = await launch_campaign.get(session, CountryCode.JO)
        campaign.is_enabled = True
        start = await launch_campaign.launch_at(session, campaign)
        before = await session.get(Driver, early["driver_id"])
        before.first_approved_at = start - timedelta(days=3)
        after = await session.get(Driver, late["driver_id"])
        after.first_approved_at = datetime.now(UTC) - timedelta(days=2)
        await session.commit()
    async with session_factory() as session:
        before = await session.get(Driver, early["driver_id"])
        after = await session.get(Driver, late["driver_id"])
        assert await launch_campaign.commission_free(session, before) is True, "عمولةٌ في أيّامه الستّين لأنّ منحتَه لم تبدأ"
        assert await launch_campaign.commission_free(session, before, now=start + timedelta(days=59)) is True
        assert await launch_campaign.commission_free(session, before, now=start + timedelta(days=60, minutes=1)) is False
        assert await launch_campaign.commission_free(session, after) is True, "عمولةٌ في أيّامه السبعة"
        assert await launch_campaign.commission_free(session, after, now=after.first_approved_at + timedelta(days=7, minutes=1)) is False
        # **والحملةُ مطفأةً بعد الإطلاق لا نافذةَ لها** — كما لا منحَ لها
        campaign = await launch_campaign.get(session, CountryCode.JO)
        campaign.is_enabled = False
        await session.flush()
        assert await launch_campaign.commission_free(session, before) is False
