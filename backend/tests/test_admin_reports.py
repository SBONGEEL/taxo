"""التقارير والإحصاءات (SPEC القسم 13/5).

**ما يختبره هذا الملف هو أن النِسَب تنزل محسوبة** لا أن العدّ صحيح وحده:
«متوسط قيمة الرحلة» و«معدّل الإلغاء» كلاهما قسمةُ مجموعٍ على عدد، ولو تُركا
للوحة لقُسم رقمان مسقوفان بخمسين فقُرئ متوسطُ الصفحة متوسطَ الشهر — وهو نفس ما
يحصر القسم 14 الحسابَ في الخلفية لأجله.

**و«سائقٌ نشط» من أنهى رحلةً** لا من رفع مفتاح الاتصال: الحضورُ نيّةٌ والرحلةُ
عمل، وعدُّ المتصلين الآن مكانُه «نظرة عامة».
"""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient

from tests.helpers import (
    DRIVER,
    SECOND_DRIVER,
    SUBSCRIPTION_PLAN_PRICE,
    approved_driver,
    bring_online,
    completed_ride,
    accepted_ride,
    ensure_plan,
    rider_session,
)


async def _reports(client: AsyncClient, headers: dict, **params) -> dict:
    response = await client.get(
        "/admin/stats/reports",
        headers=headers,
        params={"country_code": "JO", **params},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_average_and_cancellation_rate_arrive_computed(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    body = await _reports(client, admin_headers)

    fare = Decimal(ride["final_fare"] or ride["estimated_fare"])
    # رحلةٌ واحدة مكتملة: المتوسطُ أجرتُها، والإلغاءُ صفر
    assert Decimal(body["avg_ride_fare"]) == fare
    assert Decimal(body["cancellation_rate"]) == Decimal("0.00")
    assert body["active_drivers"] == 1
    assert body["currency"] == "JOD"

    # **كلُّ يومٍ في النافذة صفٌّ ولو بصفر**: الرسمُ على الأيام التي فيها رحلةٌ
    # وحدها يضغط الفجوات، فيُقرأ شهرٌ فيه ثلاثة أيام عملٍ ثلاثةَ أيامٍ متتالية
    days = body["revenue_by_day"]
    assert len(days) == 30
    assert sum(row["rides"] for row in days) == 1
    assert sum(Decimal(row["revenue"]) for row in days) == fare
    # واليومُ الأخير هو اليوم — النافذة تنتهي عند الآن
    assert Decimal(days[-1]["revenue"]) == fare


async def test_cancellation_rate_counts_both_sides(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """رحلةٌ مكتملة وأخرى ملغاة ⇒ ٥٠٪ — والنسبةُ مئويةٌ لا كسر."""
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    await completed_ride(client, rider["headers"], driver)

    # الإلغاء بعد القبول وقبل البدء: لا إلغاء من `in_progress` (القسم 5)
    second = await accepted_ride(client, rider["headers"], driver)
    cancelled = await client.post(
        f"/rides/{second['id']}/cancel",
        json={"reason": "تعطّلت المركبة"},
        headers=driver["headers"],
    )
    assert cancelled.status_code == 200, cancelled.text

    body = await _reports(client, admin_headers)
    assert Decimal(body["cancellation_rate"]) == Decimal("50.00")


async def test_top_drivers_are_ranked_by_completed_rides(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    first = await approved_driver(client, session_factory, DRIVER)
    second = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-9999"
    )

    await bring_online(client, first)
    await completed_ride(client, rider["headers"], first)
    await completed_ride(client, rider["headers"], first)

    await bring_online(client, second)
    await completed_ride(client, rider["headers"], second)

    body = await _reports(client, admin_headers)
    names = [row["name"] for row in body["top_drivers"]]
    assert names[0] == DRIVER["name"]
    assert body["top_drivers"][0]["completed_rides"] == 2
    assert SECOND_DRIVER["name"] in names


async def test_subscription_sales_are_reported_by_plan(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """تقاريرُ الاشتراكات تقيس ما **بيع في الفترة** لا ما هو سارٍ الآن.

    والصفُّ يُكتب في `helpers.subscribe_driver` بنفس شكل ما يكتبه المسار
    الحقيقي، فالقياسُ على الجدول لا على المسار.
    """
    plan_id = await ensure_plan(session_factory)
    await approved_driver(client, session_factory, DRIVER)

    body = await _reports(client, admin_headers)

    assert body["subscriptions_sold"] == 1
    assert Decimal(body["subscription_revenue"]) == Decimal(SUBSCRIPTION_PLAN_PRICE)
    assert [row["plan_id"] for row in body["sales_by_plan"]] == [str(plan_id)]


async def test_reports_are_scoped_to_the_requested_country(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    await completed_ride(client, rider["headers"], driver)

    libya = await _reports(client, admin_headers, country_code="LY")
    # الأيامُ حاضرةٌ والأرقامُ صفر: النافذةُ نافذةٌ ولو لم تقع فيها رحلة
    assert all(row["rides"] == 0 for row in libya["revenue_by_day"])
    assert Decimal(libya["avg_ride_fare"]) == Decimal("0.000")
    assert Decimal(libya["cancellation_rate"]) == Decimal("0.00")
    assert libya["currency"] == "LYD"


async def test_empty_period_divides_by_nothing(
    client: AsyncClient, jordan_settings: None, admin_headers: dict
) -> None:
    """فترةٌ بلا رحلات: أصفارٌ لا قسمةٌ على صفر — الحارسُ في الخدمة لا في العرض."""
    body = await _reports(client, admin_headers, period="today")
    assert Decimal(body["avg_ride_fare"]) == Decimal("0.000")
    assert Decimal(body["cancellation_rate"]) == Decimal("0.00")
    assert body["active_drivers"] == 0
    assert body["top_drivers"] == []


async def test_support_reads_reports(
    client: AsyncClient, jordan_settings: None, support_headers: dict
) -> None:
    response = await client.get(
        "/admin/stats/reports",
        headers=support_headers,
        params={"country_code": "JO"},
    )
    assert response.status_code == 200, response.text
