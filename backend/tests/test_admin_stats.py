"""نظرة عامة — التجميع في الخلفية حصراً (SPEC القسم 13/1).

وأهمُّ ما يختبره هذا الملف ليس صحّة العدّ وحدها بل **حدودَ ما يُعدّ**:

- **بالدولة**: اللوحة تدير سوقين، ورقمٌ يجمعهما لا يقول شيئاً عن أيٍّ منهما.
- **بيوم الدولة لا يوم الخادم**: خادمُ UTC يقصّ ثلاث ساعاتٍ من أول اليوم في
  عمّان ويضم ثلاثاً من أمس — فالنافذة تُحسب بمِنطقة الدولة.
- **والمتصلون من مفتاح الحضور لا من العمود**: من أُغلق تطبيقه فجأةً يبقى
  `is_online` مرفوعاً حتى ينقضي مفتاحُه، فعدُّ العمود يَعِد بسائقين لا وجود لهم.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select

from app.core.redis_client import get_redis_client
from app.models.enums import CountryCode
from app.models.ride import Ride
from app.services import geo, stats
from tests.helpers import (
    DRIVER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    register,
    rider_session,
)


async def _overview(client: AsyncClient, headers: dict, **params) -> dict:
    response = await client.get(
        "/admin/stats/overview",
        headers=headers,
        params={"country_code": "JO", **params},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_overview_counts_and_sums_completed_rides(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    body = await _overview(client, admin_headers)

    assert body["completed_rides"] == 1
    assert body["cancelled_rides"] == 0
    # الإيراد نصٌّ بثلاث منازل كبقية المال، ويطابق أجرة الرحلة
    assert body["revenue"] == ride["final_fare"] or body["revenue"] == ride[
        "estimated_fare"
    ]
    assert len(body["rides_by_hour"]) == 24
    assert sum(body["rides_by_hour"]) == 1
    # القنواتُ الأربع حاضرةٌ دائماً ولو بصفر — رسمٌ بخانةٍ غائبة يقرأ ناقصاً
    assert set(body["payment_mix"]) == {"cash", "cliq", "card", "wallet"}


async def test_overview_is_scoped_to_the_requested_country(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """رحلةٌ أردنية لا تُعدّ في نظرةِ ليبيا — ولو كانت الوحيدة في القاعدة."""
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    await completed_ride(client, rider["headers"], driver)

    jordan = await _overview(client, admin_headers)
    libya = await _overview(client, admin_headers, country_code="LY")

    assert jordan["completed_rides"] == 1
    assert libya["completed_rides"] == 0
    assert libya["revenue"] in ("0", "0.000", "0.0")


async def test_today_window_follows_the_country_timezone(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """رحلةٌ وقعت بعد منتصف ليل عمّان وقبل منتصف ليل UTC تُعدّ في «اليوم».

    وهذه بالضبط الحالة التي يخطئ فيها خادمُ UTC: الساعة الواحدة صباحاً في
    عمّان هي العاشرة مساءً من **أمس** بـUTC، فنافذةٌ تُحسب بـUTC تُسقطها.
    """
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    amman = ZoneInfo("Asia/Amman")
    now = datetime.now(UTC)
    # لحظةٌ بعد منتصف ليل عمّان بقليل: **يومٌ واحدٌ في عمّان وأمسٌ في UTC**،
    # وهي بالضبط ما يخطئ فيه خادمٌ يحسب بـUTC.
    #
    # و`min` مع «الآن» ليست زينة: النافذة تنتهي عند اللحظة الحالية، فلو ثُبِّتت
    # الرحلة على 00:30 وشُغِّل الاختبار في 00:10 لصارت الرحلةُ **في المستقبل**
    # فتسقط من العدّ — واختبارٌ يرسب نصفَ ساعةٍ كل ليلة يُقرأ عطلاً في الكود
    # لا في نفسه. وقع هذا فعلاً حين مرّت الجلسة بمنتصف الليل.
    start_of_day = datetime.combine(
        now.astimezone(amman).date(), datetime.min.time(), tzinfo=amman
    )
    local_midnight = max(
        start_of_day,
        min(start_of_day + timedelta(minutes=30), now.astimezone(amman) - timedelta(seconds=30)),
    )

    async with session_factory() as session:
        row = await session.scalar(select(Ride).where(Ride.id == ride["id"]))
        row.created_at = local_midnight.astimezone(UTC)
        await session.commit()

    body = await _overview(client, admin_headers, period="today")
    assert body["completed_rides"] == 1, body

    from_at = datetime.fromisoformat(body["from_at"])
    # بدايةُ النافذة منتصفُ ليل عمّان — لا منتصفُ ليل UTC
    assert from_at.astimezone(amman).hour == 0
    assert from_at.astimezone(amman).minute == 0


async def test_online_count_reads_presence_not_the_column(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """من ذهب مفتاحُ حضوره لا يُعدّ متصلاً ولو بقي عمودُه مرفوعاً.

    وبحذف هذه القاعدة يَعِد الرقمُ المشرفَ بسائقين على الطريق وليس منهم أحد،
    فيرى «طلبات بانتظار سائق» ولا يفهم لماذا لا يُقبل أحدها.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)

    before = await _overview(client, admin_headers)
    assert before["online_drivers"] == 1

    # يُحاكي صمتاً أطول من عمر المفتاح: العضو باقٍ في الفهرس والحضور ذهب
    redis = get_redis_client()
    await redis.delete(geo.presence_key(driver["driver_id"]))

    after = await _overview(client, admin_headers)
    assert after["online_drivers"] == 0
    assert await stats.online_driver_count(redis, CountryCode.JO) == 0


async def test_overview_is_readable_by_support_but_needs_a_session(
    client: AsyncClient, jordan_settings: None, support_headers: dict
) -> None:
    """«نظرة عامة» تقريرُ حالٍ لا إجراء — و`support` يعالج النزاعات فيحتاج عددها."""
    allowed = await client.get(
        "/admin/stats/overview",
        headers=support_headers,
        params={"country_code": "JO"},
    )
    assert allowed.status_code == 200, allowed.text

    anonymous = await client.get(
        "/admin/stats/overview", params={"country_code": "JO"}
    )
    assert anonymous.status_code == 401
