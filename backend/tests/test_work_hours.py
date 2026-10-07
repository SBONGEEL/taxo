"""ساعاتُ العمل (SPEC §٦٢-ج/٣٧، §٦٤-ج) — **رقمٌ لا موقع، ودقيقةٌ تُعدّ مرّة، ومطفأً لا يُجمع شيء**.

ما يحرسه:
- **الحيُّ وحدَه يُعدّ** (مفتاحُ الحضور) — لا من رفع المفتاحَ وصمت.
- **دورتان في الدقيقة نفسِها دقيقةٌ واحدة** (مفتاحُ الدقيقة).
- **مطفأً لا صفَّ يُكتب** — البياناتُ الشخصيةُ لا تُجمع قبل نشر سطرها.
- **الأرباحُ تحمل دقائقَ النافذة**، و`null` حيث المفتاحُ مطفأ.
- **ما جاوز ثلاثةَ عشرَ شهراً يُجمع شهرياً ويُحذف يوميُّه**، والإدارةُ تراه.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.core.redis_client import get_redis_client
from app.models.activity import DriverActivityDay, DriverActivityMonth
from app.models.enums import CountryCode
from app.services import activity, geo
from tests.helpers import approved_driver, bring_online, enable_features

FLAG = "work_hours_enabled"


async def _tick(session_factory, moment: datetime) -> int:
    async with session_factory() as session:
        counted = await activity.tick(session, get_redis_client(), now=moment)
        await session.commit()
        return counted


async def _rows(session_factory) -> list[DriverActivityDay]:
    async with session_factory() as session:
        return list(await session.scalars(select(DriverActivityDay)))


async def test_switched_off_nothing_is_recorded(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    assert await _tick(session_factory, datetime.now(UTC)) == 0
    assert await _rows(session_factory) == []


async def test_a_live_captain_gains_one_minute_per_minute_and_a_repeated_tick_counts_once(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    moment = datetime(2026, 10, 7, 9, 30, 10, tzinfo=UTC)

    assert await _tick(session_factory, moment) == 1
    assert await _tick(session_factory, moment + timedelta(seconds=20)) == 0, "الدقيقةُ نفسُها عُدّت مرّتين"
    assert await _tick(session_factory, moment + timedelta(minutes=1)) == 1
    rows = await _rows(session_factory)
    assert [(row.driver_id, row.online_minutes) for row in rows] == [(driver["driver_id"], 2)]

    # **الصامتُ لا يُعدّ**: مفتاحُ حضوره انقضى وإن بقي في الفهرس
    await get_redis_client().delete(geo.presence_key(driver["driver_id"]))
    assert await _tick(session_factory, moment + timedelta(minutes=2)) == 0


async def test_earnings_carry_the_windows_minutes_and_null_when_off(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    driver = await approved_driver(client, session_factory)
    off = await client.get("/drivers/me/earnings?period=today", headers=driver["headers"])
    assert off.status_code == 200 and off.json()["online_minutes"] is None, off.text

    await enable_features(session_factory, FLAG)
    from app.services.stats import _zone

    async with session_factory() as session:
        # **يومُ السوق لا يومُ UTC** — بعد التاسعة مساءً بتوقيت غرينتش صار في عمّان الغد
        today = datetime.now(UTC).astimezone(await _zone(session, CountryCode.JO)).date()
    async with session_factory() as session:
        session.add_all(
            [
                DriverActivityDay(driver_id=driver["driver_id"], day=today, online_minutes=250),
                DriverActivityDay(driver_id=driver["driver_id"], day=today - timedelta(days=3), online_minutes=60),
                DriverActivityDay(driver_id=driver["driver_id"], day=today - timedelta(days=40), online_minutes=999),
            ]
        )
        await session.commit()
    day = (await client.get("/drivers/me/earnings?period=today", headers=driver["headers"])).json()
    week = (await client.get("/drivers/me/earnings?period=week", headers=driver["headers"])).json()
    assert day["online_minutes"] == 250
    assert week["online_minutes"] == 310


async def test_old_days_roll_up_into_months_and_the_staff_sees_them(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    driver = await approved_driver(client, session_factory)
    today = date(2026, 10, 7)
    old = today - timedelta(days=activity.DAILY_RETENTION_DAYS + 5)
    async with session_factory() as session:
        session.add_all(
            [
                DriverActivityDay(driver_id=driver["driver_id"], day=old, online_minutes=100),
                DriverActivityDay(driver_id=driver["driver_id"], day=old + timedelta(days=1), online_minutes=20),
                DriverActivityDay(driver_id=driver["driver_id"], day=today, online_minutes=7),
            ]
        )
        await session.commit()
        removed = await activity.roll_up(session, today=today)
        await session.commit()
    assert removed == 2
    async with session_factory() as session:
        months = list(await session.scalars(select(DriverActivityMonth)))
    assert [(row.month.day, row.online_minutes) for row in months] in ([(1, 120)], [(1, 100), (1, 20)])
    assert sum(row.online_minutes for row in months) == 120
    assert [row.day for row in await _rows(session_factory)] == [today]

    seen = await client.get(f"/admin/drivers/{driver['driver_id']}/activity", headers=admin_headers)
    assert seen.status_code == 200, seen.text
    body = seen.json()
    assert body["enabled"] is True and len(body["days"]) == 30
    assert body["today_minutes"] == 7 and body["week_minutes"] == 7 and body["month_minutes"] == 7
    assert sum(row["minutes"] for row in body["months"]) == 120
    assert (await client.get(f"/admin/drivers/{uuid.uuid4()}/activity", headers=admin_headers)).status_code == 404
