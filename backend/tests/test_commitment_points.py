"""**نقاطُ الالتزام** (§١١٤-ب، أمرُ المالك ٢٠٢٦-١١-٢٤ السادس) — الشرطُ اليوميّ، وحدُّ منتصف الليل، ومنعُ الغشّ، والتزامن.

* **التقييمُ دالّةٌ نقيّة** تُقاس بلا قاعدة: استراحاتٌ ≤ ساعةٍ ومجموعُها ≤ ساعتين داخل العشر، وما زاد يقطع المدّة.
* **ومنتصفُ الليل**: الدقيقةُ ٢٣:٥٩ ليومها والدقيقةُ ٠٠:٠٠ لليوم التالي — ومدّةٌ تنتهي عند ٢٤:٠٠ تامّة.
* **والتزامنُ على ما يملكه القفلُ وحدَه**: تقييمان متزامنان ليومٍ واحدٍ يكتبان صفّاً ونقاطاً مرّةً، وتحويلان متزامنان لنقاطٍ تكفي واحداً ينجح أحدُهما.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.commitment import DriverDutyDay, DriverPointsEntry, SubscriptionCreditEntry
from app.models.driver import Driver
from app.models.enums import CountryCode
from app.services import commitment
from tests.helpers import approved_driver, ensure_plan

AMMAN = ZoneInfo("Asia/Amman")
SHAPE = commitment.Shape(window_start=7 * 60, window_end=24 * 60, span=600, max_break=60, max_total=120)


def _day(*runs: tuple[int, int]) -> list[bool]:
    """دقائقُ اتّصالٍ من أزواج (بداية، نهايةٌ حصريّة) بالدقائق من منتصف الليل."""
    online = [False] * 1440
    for start, end in runs:
        for minute in range(start, end):
            online[minute] = True
    return online


H = 60


# ===================================================================== الدالّةُ النقيّة


def test_ten_straight_hours_meet_the_day() -> None:
    result = commitment.evaluate(_day((8 * H, 18 * H)), SHAPE)
    assert result.met and result.online_minutes == 600 and result.total_break == 0


def test_two_one_hour_breaks_inside_the_span_still_meet() -> None:
    # ٨ ساعاتٍ اتّصالاً وساعتا استراحةٍ منفصلتان داخل العشر
    result = commitment.evaluate(_day((8 * H, 11 * H), (12 * H, 15 * H), (16 * H, 18 * H)), SHAPE)
    assert result.met and result.break_count == 2 and result.total_break == 120 and result.online_minutes == 480


def test_a_break_over_one_hour_breaks_the_span() -> None:
    result = commitment.evaluate(_day((8 * H, 11 * H), (12 * H + 1, 18 * H + 1)), SHAPE)
    assert not result.met
    assert "استراحةٌ تجاوزت ساعة" in (result.reason or "")


def test_breaks_over_two_hours_in_total_break_the_span() -> None:
    # ثلاثُ استراحاتٍ كلٌّ ٤٥ دقيقة = ١٣٥ > ١٢٠
    runs = ((8 * H, 10 * H), (10 * H + 45, 12 * H), (12 * H + 45, 14 * H), (14 * H + 45, 19 * H))
    result = commitment.evaluate(_day(*runs), SHAPE)
    assert not result.met
    assert "مجموعُ الاستراحات" in (result.reason or "")


def test_two_hours_as_one_block_is_not_allowed() -> None:
    result = commitment.evaluate(_day((8 * H, 12 * H), (14 * H, 20 * H)), SHAPE)
    assert not result.met


def test_a_broken_morning_and_a_full_evening_meet_the_day() -> None:
    result = commitment.evaluate(_day((7 * H, 9 * H), (12 * H, 22 * H)), SHAPE)
    assert result.met and result.start == 12 * H


def test_outside_the_window_does_not_count() -> None:
    result = commitment.evaluate(_day((0, 7 * H), (20 * H, 24 * H)), SHAPE)
    assert not result.met


def test_a_span_ending_exactly_at_midnight_is_complete() -> None:
    result = commitment.evaluate(_day((14 * H, 24 * H)), SHAPE)
    assert result.met and result.end == 24 * H


def test_a_span_that_would_cross_midnight_cannot_start() -> None:
    result = commitment.evaluate(_day((15 * H, 24 * H)), SHAPE)
    assert not result.met


def test_progress_reports_hours_breaks_and_time_left() -> None:
    online = _day((8 * H, 10 * H), (10 * H + 30, 12 * H))
    now = commitment.progress(online, SHAPE, 12 * H + 9)
    assert now.state == "running"
    assert now.elapsed_minutes == 4 * H + 10 and now.breaks_used_minutes == 40 and now.current_break_minutes == 10
    assert now.remaining_minutes == 600 - (4 * H + 10)
    assert commitment.progress(online, SHAPE, 6 * H).state == "before_window"
    done = commitment.progress(_day((8 * H, 18 * H)), SHAPE, 19 * H)
    assert done.state == "met"
    broken = commitment.progress(_day((8 * H, 10 * H)), SHAPE, 11 * H + 30)
    assert broken.state == "broken" and broken.can_restart is True


def test_hours_are_counted_in_arabic() -> None:
    """«مدّةُ 10 ساعات» لا «10 ساعة» — وكانت تُقرأ في سجلّ الكابتن (فحصُ المالك ٢٦/١١)."""
    assert [commitment._hours(m) for m in (60, 120, 180, 600, 660, 90)] == [
        "ساعة", "ساعتين", "3 ساعات", "10 ساعات", "11 ساعةً", "1:30 ساعة",
    ]
    late = commitment.evaluate(_day((15 * H, 23 * H)), SHAPE)
    assert late.met is False and "10 ساعات" in (late.reason or "")


# ===================================================================== القاعدةُ واللوحة


async def _rule(client: AsyncClient, admin_headers: dict, **body) -> dict:
    response = await client.patch("/admin/commitment/rule", params={"country_code": "JO"}, json=body, headers=admin_headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_rule_is_off_with_no_values_and_cannot_be_enabled_without_them(
    client: AsyncClient, admin_headers: dict, jordan_settings: None
) -> None:
    rule = (await client.get("/admin/commitment/rule", params={"country_code": "JO"}, headers=admin_headers)).json()
    assert rule["is_enabled"] is False and rule["points_per_day"] is None and rule["credit_unit_value"] is None
    assert (rule["window_start"], rule["window_end"], rule["span_minutes"]) == ("07:00:00", "23:59:00", 600)
    refused = await client.patch("/admin/commitment/rule", params={"country_code": "JO"}, json={"is_enabled": True},
                                 headers=admin_headers)
    assert refused.status_code == 422


async def _ready_driver(client: AsyncClient, session_factory, admin_headers: dict, **rule) -> dict:
    await _rule(client, admin_headers, points_per_day=10, points_per_credit_unit=10, credit_unit_value="1.000",
                is_enabled=True, **rule)
    driver = await approved_driver(client, session_factory)
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        row.device_signals = {"mock_location": False, "rooted": False, "emulator": False}
        row.device_signals_at = datetime.now(UTC)
        await session.commit()
    commitment._SNAPSHOTS.clear()
    return driver


async def _fill(driver_id: uuid.UUID, day: date, *runs: tuple[int, int]) -> None:
    redis = get_redis_client()
    for start, end in runs:
        for minute in range(start, end):
            await redis.setbit(commitment.on_key(driver_id, day), minute, 1)


async def test_touch_writes_nothing_while_off_and_splits_days_at_local_midnight(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    redis = get_redis_client()
    driver_id = uuid.uuid4()
    late = datetime.combine(date(2026, 12, 3), time(23, 59), AMMAN)
    await commitment.touch(redis, driver_id=driver_id, country=CountryCode.JO, lat=31.95, lng=35.91, now=late)
    assert await redis.exists(commitment.on_key(driver_id, date(2026, 12, 3))) == 0

    await _rule(client, admin_headers, points_per_day=10, points_per_credit_unit=10, credit_unit_value="1.000",
                is_enabled=True, require_service_area=False)
    commitment._SNAPSHOTS.clear()
    await commitment.touch(redis, driver_id=driver_id, country=CountryCode.JO, lat=31.95, lng=35.91, now=late)
    await commitment.touch(
        redis, driver_id=driver_id, country=CountryCode.JO, lat=31.95, lng=35.91, now=late + timedelta(minutes=1)
    )
    assert await redis.getbit(commitment.on_key(driver_id, date(2026, 12, 3)), 23 * 60 + 59) == 1
    assert await redis.getbit(commitment.on_key(driver_id, date(2026, 12, 4)), 0) == 1
    assert await redis.getbit(commitment.on_key(driver_id, date(2026, 12, 3)), 0) == 0


async def test_a_met_day_earns_once_and_the_sweep_after_midnight_judges_yesterday(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    driver = await _ready_driver(client, session_factory, admin_headers)
    yesterday = datetime.now(AMMAN).date() - timedelta(days=1)
    await _fill(driver["driver_id"], yesterday, (14 * H, 24 * H))
    just_after_midnight = datetime.combine(yesterday + timedelta(days=1), time(0, 5), AMMAN)
    async with session_factory() as session:
        done = await commitment.sweep(session, get_redis_client(), now=just_after_midnight)
        await session.commit()
    assert done["JO"] == 1
    async with session_factory() as session:
        await commitment.sweep(session, get_redis_client(), now=just_after_midnight + timedelta(minutes=10))
        await session.commit()
        day = await session.scalar(select(DriverDutyDay).where(DriverDutyDay.driver_id == driver["driver_id"]))
        points = (await session.scalars(select(DriverPointsEntry.points).where(
            DriverPointsEntry.driver_id == driver["driver_id"]))).all()
    assert day.status == "met" and day.rides_completed == 0
    assert points == [10]
    mine = (await client.get("/drivers/me/commitment", headers=driver["headers"])).json()
    assert mine["points_balance"] == 10 and mine["credit_value_of_points"] == "1.000"
    assert mine["recent"][0]["status"] == "met"


async def test_mock_location_disqualifies_the_day_with_a_visible_reason(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    driver = await _ready_driver(client, session_factory, admin_headers)
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        row.device_signals = {"mock_location": True, "rooted": False}
        await session.commit()
    day = datetime.now(AMMAN).date() - timedelta(days=1)
    await _fill(driver["driver_id"], day, (8 * H, 18 * H))
    async with session_factory() as session:
        rule = await commitment.get_rule(session, CountryCode.JO)
        row = await session.get(Driver, driver["driver_id"])
        written = await commitment.evaluate_driver_day(
            session, get_redis_client(), driver=row, country=CountryCode.JO, day=day, rule=rule
        )
        await session.commit()
    assert written.status == "disqualified" and "موقعٌ وهمي" in written.reason
    mine = (await client.get("/drivers/me/commitment", headers=driver["headers"])).json()
    assert mine["points_balance"] == 0 and "موقعٌ وهمي" in mine["recent"][0]["reason"]


async def test_two_concurrent_evaluations_of_one_day_write_one_row_and_one_award(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    driver = await _ready_driver(client, session_factory, admin_headers)
    day = datetime.now(AMMAN).date() - timedelta(days=1)
    await _fill(driver["driver_id"], day, (8 * H, 18 * H))

    async def one() -> None:
        async with session_factory() as session:
            await commitment.evaluate_country_day(session, get_redis_client(), country=CountryCode.JO, day=day)
            await session.commit()

    await asyncio.wait_for(asyncio.gather(one(), one(), one(), return_exceptions=True), timeout=30)
    async with session_factory() as session:
        days = await session.scalar(select(func.count()).select_from(DriverDutyDay).where(
            DriverDutyDay.driver_id == driver["driver_id"]))
        points = await session.scalar(select(func.coalesce(func.sum(DriverPointsEntry.points), 0)).where(
            DriverPointsEntry.driver_id == driver["driver_id"]))
    assert days == 1 and points == 10


async def _grant_points(session_factory, driver_id: uuid.UUID, points: int) -> None:
    async with session_factory() as session:
        session.add(DriverPointsEntry(driver_id=driver_id, country_code=CountryCode.JO, kind="adjustment",
                                      points=points, remaining=points, reason="اختبار"))
        await session.commit()


async def test_two_concurrent_conversions_of_points_that_cover_one(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    driver = await _ready_driver(client, session_factory, admin_headers)
    await _grant_points(session_factory, driver["driver_id"], 10)

    async def convert() -> int:
        response = await client.post("/drivers/me/commitment/convert", json={"points": 10}, headers=driver["headers"])
        return response.status_code

    codes = Counter(await asyncio.wait_for(asyncio.gather(convert(), convert(), convert()), timeout=30))
    assert codes == Counter({200: 1, 409: 2})
    async with session_factory() as session:
        credit = await session.scalar(select(func.sum(SubscriptionCreditEntry.amount)).where(
            SubscriptionCreditEntry.driver_id == driver["driver_id"]))
        negative = await session.scalar(select(func.count()).select_from(SubscriptionCreditEntry).where(
            SubscriptionCreditEntry.balance_after < 0))
        left = await session.scalar(select(func.sum(DriverPointsEntry.remaining)).where(
            DriverPointsEntry.driver_id == driver["driver_id"]))
    assert credit == Decimal("1.000") and negative == 0 and left == 0


async def test_conversion_is_in_whole_units_and_credit_pays_only_subscriptions(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    driver = await _ready_driver(client, session_factory, admin_headers)
    await _grant_points(session_factory, driver["driver_id"], 25)
    odd = await client.post("/drivers/me/commitment/convert", json={"points": 15}, headers=driver["headers"])
    assert odd.status_code == 422
    plan_id = await ensure_plan(session_factory, name="خطةُ الرصيد", price="2.000")
    short = await client.post("/subscriptions/credit", json={"plan_id": str(plan_id), "idempotency_key": "credit-short-1"},
                              headers=driver["headers"])
    assert short.status_code == 409
    ok = await client.post("/drivers/me/commitment/convert", json={"points": 20}, headers=driver["headers"])
    assert ok.status_code == 200 and ok.json()["credit_balance"] == "2.000"
    bought = await client.post("/subscriptions/credit", json={"plan_id": str(plan_id), "idempotency_key": "credit-buy-1"},
                               headers=driver["headers"])
    assert bought.status_code == 200, bought.text
    again = await client.post("/subscriptions/credit", json={"plan_id": str(plan_id), "idempotency_key": "credit-buy-1"},
                              headers=driver["headers"])
    assert again.status_code == 200 and again.json()["id"] == bought.json()["id"]
    async with session_factory() as session:
        balance = await session.scalar(select(func.sum(SubscriptionCreditEntry.amount)).where(
            SubscriptionCreditEntry.driver_id == driver["driver_id"]))
    assert balance == Decimal("0.000")


@pytest.mark.parametrize("cap", [5])
async def test_the_daily_cap_trims_an_award(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory, cap: int
) -> None:
    driver = await _ready_driver(client, session_factory, admin_headers, daily_points_cap=cap)
    day = datetime.now(AMMAN).date() - timedelta(days=1)
    await _fill(driver["driver_id"], day, (8 * H, 18 * H))
    async with session_factory() as session:
        await commitment.evaluate_country_day(session, get_redis_client(), country=CountryCode.JO, day=day)
        await session.commit()
        points = await session.scalar(select(func.sum(DriverPointsEntry.points)).where(
            DriverPointsEntry.driver_id == driver["driver_id"]))
    assert points == cap


async def test_outside_the_service_area_shows_a_reason_live(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory, monkeypatch
) -> None:
    """**خارج نطاق الخدمة ⇐ سببٌ ظاهرٌ في البطاقة** (أمرُ المالك ٢٦/١١): كانت دقائقُ الخارج تُقرأ «استراحة» بلا سبب. **والحسابُ كما هو**:
    الدقائقُ لا تُحسب، وتُقرأ داخلَ النطاق كما كانت؛ والعودةُ إلى الداخل تُزيل السبب."""
    driver = await _ready_driver(client, session_factory, admin_headers, require_service_area=True)
    noon = datetime.combine(datetime.now(AMMAN).date(), time(12, 0), AMMAN)
    monkeypatch.setattr(commitment, "_now", lambda: noon.astimezone(UTC))
    redis = get_redis_client()
    await _fill(driver["driver_id"], noon.date(), (10 * H, 11 * H + 50))
    for minute in (11 * H + 59, 12 * H):
        await redis.setbit(commitment.out_key(uuid.UUID(str(driver["driver_id"])), noon.date()), minute, 1)

    today = (await client.get("/drivers/me/commitment", headers=driver["headers"])).json()["today"]
    assert today["state"] == "running" and today["reason"] == commitment.OUT_OF_AREA_REASON
    assert today["online_minutes"] == 110

    await _fill(driver["driver_id"], noon.date(), (11 * H + 59, 12 * H + 1))
    back = (await client.get("/drivers/me/commitment", headers=driver["headers"])).json()["today"]
    assert back["reason"] is None

