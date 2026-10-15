"""الخريطة الحيّة — الهويةُ تخرج من بابٍ واحد، وتُسجَّل (SPEC القسم 13/1).

ثلاثةٌ تُختبر هنا، وأهمُّها الثالث:

1. **`admin` وحده**: الدعم يقرأ التقارير ويعالج النزاعات، ولا شيء في عمله
   يحتاج أين يقف كلُّ كبتنٍ الآن باسمه ورقمه.
2. **قيدُ تدقيقٍ واحد للجلسة**: قيدٌ لكل استعلامٍ يغرق السجل، وصفرُ قيودٍ
   يجعل أوسعَ قراءةٍ في النظام أخفَّها أثراً.
3. **ولا يتسرب شيءٌ من هذا إلى تطبيق الراكب**: نفس السائق يظهر في اللوحة
   باسمه وفي `/drivers/nearby` بمعرّفٍ مستعار. هذا الاختبار هو ما يمنع «توحيد»
   المسارين لاحقاً، لأن التوحيد سيُسقطه.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.models.audit import AdminAuditLog
from app.models.enums import AuditAction, CountryCode
from app.models.user import User
from app.services import live_map
from tests.helpers import (
    DRIVER,
    FAR_PICKUP,
    NEAR_PICKUP,
    OTHER_RIDER,
    SECOND_DRIVER,
    approved_driver,
    bring_online,
    request_ride,
    rider_session,
)


async def _map(client: AsyncClient, headers: dict, country: str = "JO"):
    response = await client.get(
        "/admin/live/map", headers=headers, params={"country_code": country}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_map_shows_connected_drivers_with_identity(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)

    body = await _map(client, admin_headers)

    assert len(body["drivers"]) == 1
    row = body["drivers"][0]
    assert row["driver_id"] == str(driver["driver_id"])
    assert row["name"] and row["phone"].startswith("+962")
    assert row["plate_number"] == "AMM-4242"
    assert row["on_ride"] is False
    # الموقع من Redis لا من عمود: لا شيء في القاعدة يحمل هذه الإحداثيات
    assert isinstance(row["lat"], float) and isinstance(row["lng"], float)


async def test_support_is_refused(
    client: AsyncClient, jordan_settings: None, support_headers: dict
) -> None:
    """أوسعُ قراءةٍ في اللوحة ليست لأقلِّ أدوارها صلاحية."""
    response = await client.get(
        "/admin/live/map", headers=support_headers, params={"country_code": "JO"}
    )
    assert response.status_code == 403, response.text

    anonymous = await client.get("/admin/live/map", params={"country_code": "JO"})
    assert anonymous.status_code == 401


async def test_opening_the_map_writes_one_audit_entry_per_session(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """جلسةُ مراقبةٍ = قيدٌ واحد، مهما استعلمت الشاشة.

    وبلا الخنق تكتب شاشةٌ تُحدَّث كل خمس ثوانٍ مئتي قيدٍ في الساعة، فتصير
    قرارات المشرف الحقيقية إبرةً في كومة قراءات.
    """
    for _ in range(3):
        await _map(client, admin_headers)

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(
                AdminAuditLog.action == AuditAction.READ,
                AdminAuditLog.entity_type == "live_map",
            )
        )
        entry = await session.scalar(
            select(AdminAuditLog).where(AdminAuditLog.entity_type == "live_map")
        )

    assert count == 1, "الخنق معطّل: كل استعلامٍ يكتب قيداً"
    assert entry.details == {"country_code": "JO"}


async def test_a_second_country_is_a_separate_session(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    """فتحُ سوقٍ آخر قراءةٌ أخرى — الخنقُ بالدولة لا بالمشرف وحده.

    **والأسواقُ من مصدرها لا من قائمةٍ تُكتب هنا** (SPEC §٧٣-ج): كان `["JO", "LY"]` حرفاً، فيسقط أوّلَ سوقٍ يُضاف ولا يقول إن
    الخنقَ عطب — يقول إن القائمةَ قديمة. **فكلُّ سوقٍ في التعداد يُفتح، وكلُّ سوقٍ يترك قيدَه.**
    """
    for country in CountryCode:
        await _map(client, admin_headers, country.value)

    async with session_factory() as session:
        countries = (
            await session.scalars(
                select(AdminAuditLog.details).where(
                    AdminAuditLog.entity_type == "live_map"
                )
            )
        ).all()

    assert sorted(row["country_code"] for row in countries) == sorted(c.value for c in CountryCode)


async def test_rider_facing_paths_still_carry_no_identity(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """نفسُ الكبتن: باسمه في اللوحة، وبمعرّفٍ مستعارٍ عند الراكب.

    وهذا هو الاختبار الذي يجب أن يُقرأ قبل أي «تبسيط» يوحّد الدالتين: القسم 10
    يحصر ما يراه الراكب في إحداثياتٍ واتجاهٍ وفئة، والاسمُ والرقم واللوحة ليست
    منها.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    panel = await _map(client, admin_headers)
    assert panel["drivers"][0]["name"]

    nearby = await client.get(
        "/drivers/nearby",
        headers=rider["headers"],
        params={"lat": 31.9539, "lng": 35.9106},
    )
    assert nearby.status_code == 200, nearby.text
    seen = nearby.json()
    assert seen, "الكبتن نفسه يجب أن يظهر للراكب — مجهَّلاً"
    for row in seen:
        assert "name" not in row and "phone" not in row
        assert "driver_id" not in row and "plate_number" not in row
        assert row["ref"] != str(driver["driver_id"])


async def test_pending_rides_are_the_ones_nobody_took(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """«طلبات بانتظار سائق»: الرحلة قبل القبول، وتختفي بعده."""
    rider = await rider_session(client)
    ride = await request_ride(client, rider["headers"])

    body = await _map(client, admin_headers)
    pending = body["pending_rides"]
    assert len(pending) == 1
    assert pending[0]["ride_id"] == ride["id"]
    assert pending[0]["status"] in ("requested", "searching")


async def test_silent_member_is_not_on_the_map(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """من ذهب مفتاحُ حضوره اختفى من الخريطة ولو بقي في الفهرس الجغرافي."""
    from app.core.redis_client import get_redis_client
    from app.services import geo

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    assert len((await _map(client, admin_headers))["drivers"]) == 1

    await get_redis_client().delete(geo.presence_key(driver["driver_id"]))

    assert (await _map(client, admin_headers))["drivers"] == []


async def test_audit_window_is_a_module_constant(client: AsyncClient) -> None:
    """نافذةُ الخنق قيمةُ وحدةٍ لا رقمٌ مبعثر — كي يقلبها اختبارٌ عند الحاجة."""
    assert live_map.AUDIT_WINDOW_SECONDS > 0


# --------------------------------------------------------------------------- حساباتُ التجربة (SPEC §٧٦-ل)


async def _mark_test(session_factory, user_id) -> None:
    async with session_factory() as session:
        await session.execute(update(User).where(User.id == uuid.UUID(str(user_id))).values(is_test=True))
        await session.commit()


async def test_a_test_captain_is_drawn_marked_moves_and_is_not_counted(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """**بلاغُ المالك ٢٠٢٦-١٠-١٥** (SPEC §٧٦-ل): كبتنُ تجربةٍ «متّصلٌ» في بطاقة السعة **ولا شيءَ على الخريطة** — كانت تُخفيه (§٦٥-ج)
    فقُرئت معطوبة. **الآن يُرسم موسوماً ويتحرّك حين يتحرّك**، **والعدُّ كما كان**: «متصلون» في الخريطة بلا التجربة = «متصلٌ الآن»."""
    real = await approved_driver(client, session_factory, DRIVER)
    tester = await approved_driver(client, session_factory, SECOND_DRIVER, plate_number="AMM-1002")
    await _mark_test(session_factory, tester["user_id"])
    await bring_online(client, real, NEAR_PICKUP)
    await bring_online(client, tester, FAR_PICKUP)

    rows = {row["driver_id"]: row for row in (await _map(client, admin_headers))["drivers"]}
    assert set(rows) == {str(real["driver_id"]), str(tester["driver_id"])}
    assert rows[str(tester["driver_id"])]["is_test"] is True
    assert rows[str(real["driver_id"])]["is_test"] is False
    assert abs(rows[str(tester["driver_id"])]["lat"] - FAR_PICKUP["lat"]) < 1e-4

    # **ويتحرّك حين يتحرّك** — الموضعُ من البثّ نفسِه
    moved = await client.post(
        "/drivers/me/location", json={"lat": 32.0100, "lng": 35.9200, "heading": 45}, headers=tester["headers"]
    )
    assert moved.status_code == 204, moved.text
    after = next(
        row for row in (await _map(client, admin_headers))["drivers"] if row["driver_id"] == str(tester["driver_id"])
    )
    assert abs(after["lat"] - 32.0100) < 1e-4 and abs(after["lng"] - 35.9200) < 1e-4

    # **والعدُّ لا يتغيّر**: النظرةُ العامّةُ تطرح التجربة، والخريطةُ تطرحها من «متصلون» بـ`is_test`
    overview = await client.get("/admin/stats/overview", params={"country_code": "JO"}, headers=admin_headers)
    assert overview.status_code == 200, overview.text
    street = [row for row in (await _map(client, admin_headers))["drivers"] if not row["is_test"]]
    assert overview.json()["online_drivers"] == len(street) == 1


async def test_a_test_riders_request_is_drawn_marked(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """**وطلبُ راكبِ التجربة يُرسم موسوماً** — وكان يُخفى كالكبتن، فرحلةُ اختبارٍ تنتظر سائقاً لا تظهر لمن يراقبها."""
    rider = await rider_session(client)
    tester = await rider_session(client, OTHER_RIDER)
    await _mark_test(session_factory, tester["user"]["id"])
    real_ride = await request_ride(client, rider["headers"])
    test_ride = await request_ride(client, tester["headers"])

    pending = {row["ride_id"]: row for row in (await _map(client, admin_headers))["pending_rides"]}
    assert pending[real_ride["id"]]["is_test"] is False
    assert pending[test_ride["id"]]["is_test"] is True
