"""المهامُّ والمستوياتُ والشارات (البند ٥٣، `design/MISSIONS-LEVELS.md` §٩).

**والاختبارُ الأولُ هنا هو القيدُ الذي لا يُتجاوز**: الأقربُ يبقى الأول، والمستوى
يفصل بين المتقاربين ولا يعلو المسافة أبداً. وسببُه طرفان لا طرف — **راكبٌ ينتظر
أطولَ ليُكافأ كبتنٌ آخر** يدفع ثمنَ ما لا ناقةَ له فيه، **وكباتنُ المستوى الأدنى
تقلُّ طلباتُهم فلا يتقدّمون فيتركون التطبيق** — نظامُ تحفيزٍ يصير سببَ تسرّب.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.driver import Driver
from app.models.enums import CountryCode, RideStatus
from app.models.mission import LevelSetting, Mission
from app.models.ride import Ride
from app.services import missions as missions_service
from tests.helpers import DRIVER, SECOND_DRIVER, approved_driver, enable_features


async def _month(session_factory) -> "object":
    async with session_factory() as session:
        return await missions_service._country_month(session, CountryCode.JO)


async def _mission(
    session_factory, *, metric: str = "completed_rides", target: str = "2"
) -> uuid.UUID:
    async with session_factory() as session:
        month = await missions_service._country_month(session, CountryCode.JO)
        mission = await missions_service.create_mission(
            session,
            country=CountryCode.JO,
            month=month,
            metric=metric,
            target=Decimal(target),
            title="مهمة الشهر",
        )
        await session.commit()
        return mission.id


async def _set_discount(session_factory, level: int, meters: int) -> None:
    async with session_factory() as session:
        await missions_service.set_discount(
            session, country=CountryCode.JO, level=level, meters=meters
        )
        await session.commit()


async def _complete_rides(session_factory, driver_id: uuid.UUID, count: int) -> None:
    """رحلاتٌ **مكتملة** تُكتب مباشرةً — والمقصودُ قياسُ العدّ لا مسارُ الرحلة."""
    async with session_factory() as session:
        driver = await session.get(Driver, driver_id)
        rider_id = await session.scalar(
            select(Ride.rider_id).limit(1)
        ) or driver.user_id
        now = datetime.now(UTC)
        for index in range(count):
            session.add(
                Ride(
                    rider_id=rider_id,
                    driver_id=driver_id,
                    country_code=CountryCode.JO,
                    status=RideStatus.COMPLETED,
                    completed_at=now - timedelta(minutes=index + 1),
                    vehicle_category="economy",
                    pickup_point="SRID=4326;POINT(35.9 31.95)",
                    dropoff_point="SRID=4326;POINT(35.95 31.99)",
                    distance_km=Decimal("2.500"),
                    duration_min=8,
                    estimated_fare=Decimal("3.000"),
                    final_fare=Decimal("3.000"),
                    currency="JOD",
                    commission_percent_at_ride=Decimal("10"),
                )
            )
        await session.commit()


# ------------------------------------------------- القيدُ الذي لا يُتجاوز


async def _rank(session, presences, ride):
    """يستدعي **ترتيبَ التوزيع الحقيقي** لا نسخةً منه.

    واختبارٌ يعيد كتابةَ المعادلة في جسمه يقيس المعادلةَ التي كتبها هو — فيبقى
    أخضرَ ولو حُذف القيدُ من `dispatch` كلَّه. وهو بعينه الشكلُ الذي جعل اختبارَ
    الخدمة النسائية يمرّ مع حذف القاعدة في 10-ج.
    """
    from app.services import dispatch

    levels = await dispatch._eligible_levels(
        session,
        [p.driver_id for p in presences],
        ride.vehicle_category,
    )
    ranked = [p for p in presences if p.driver_id in levels]
    discounts = await missions_service.discounts_for(session, ride.country_code)
    if discounts:
        ranked.sort(
            key=lambda p: (
                p.distance_km * 1000 - discounts.get(levels[p.driver_id], 0),
                p.distance_km,
            )
        )
    return ranked


async def test_a_far_high_level_driver_never_beats_a_near_low_level_one(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**القيدُ نفسُه** (§٩): الأقربُ يبقى الأول مهما علا مستوى البعيد.

    ويُتحقَّق منه بحذف الحدِّ (`MAX_LEVEL_DISCOUNT_METERS`) وجعل الخصم كيلومتراً:
    عندها يسبق البعيدُ فيفشل — فهو يحرس القاعدة لا يصفها. **والحدُّ في القاعدة
    أيضاً**، فرقمٌ يمرّ من طبقةٍ عليا لا يجد الجدولَ مفتوحاً بعده.
    """
    await enable_features(session_factory, "driver_levels_enabled")
    await _set_discount(session_factory, 3, 100)

    near = await approved_driver(client, session_factory, DRIVER)
    far = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-5301"
    )
    async with session_factory() as session:
        # `_eligible_levels` تقرأ العمود لا ريدِس، فالحضورُ يُكتب مباشرةً —
        # والمقصودُ هنا **الترتيب** لا شرطُ الأهلية (له اختباراتُه)
        await session.execute(
            update(Driver)
            .where(Driver.id.in_([near["driver_id"], far["driver_id"]]))
            .values(is_online=True)
        )
        await session.execute(
            update(Driver).where(Driver.id == far["driver_id"]).values(level=3)
        )
        await session.commit()

    class P:
        def __init__(self, driver_id, distance_km):
            self.driver_id = driver_id
            self.distance_km = distance_km

    class R:
        country_code = CountryCode.JO
        vehicle_category = "economy"

    # القريبُ على ٥٠٠م بمستوى صفر، والبعيدُ على ١٫٥كم بأعلى مستوى
    async with session_factory() as session:
        ranked = await _rank(
            session,
            [P(near["driver_id"], 0.5), P(far["driver_id"], 1.5)],
            R(),
        )
    assert ranked[0].driver_id == near["driver_id"], "البعيدُ سبق القريبَ — القيدُ انكسر"

    # **وأقصى إزاحةٍ = الخصمُ نفسُه**: من على ٥٤٠م بأعلى مستوى يسبق من على ٥٠٠م
    # بمستوى صفر — وأربعون متراً هي كلُّ ما اشتراه المستوى، لا أكثر
    async with session_factory() as session:
        ranked = await _rank(
            session,
            [P(near["driver_id"], 0.5), P(far["driver_id"], 0.54)],
            R(),
        )
    assert ranked[0].driver_id == far["driver_id"]

    # **ومطفأً يعود الترتيبُ حرفياً كما هو اليوم**: الأقربُ أولاً بلا استثناء
    await _set_discount(session_factory, 3, 0)
    async with session_factory() as session:
        ranked = await _rank(
            session,
            [P(near["driver_id"], 0.5), P(far["driver_id"], 0.54)],
            R(),
        )
    assert ranked[0].driver_id == near["driver_id"]


async def test_the_discount_is_capped_at_a_hundred_meters(
    session_factory, jordan_settings: None
) -> None:
    """**حدُّ المالك** — وهو ما يجعل «يقلّص النطاق قليلاً لا يلغيه» قابلاً للقياس."""
    from app.core.exceptions import InvalidInput

    async with session_factory() as session:
        try:
            await missions_service.set_discount(
                session, country=CountryCode.JO, level=3, meters=101
            )
        except InvalidInput:
            pass
        else:  # pragma: no cover - الفشلُ هو الغرض
            raise AssertionError("قُبل خصمٌ فوق الحدّ")


async def test_the_feature_off_leaves_the_order_exactly_as_it_is_today(
    session_factory, jordan_settings: None
) -> None:
    """**مطفأً: الترتيبُ حرفياً كما هو اليوم** (§٩) — بلا فرعٍ ثانٍ في الشيفرة."""
    await _set_discount(session_factory, 3, 100)
    async with session_factory() as session:
        assert await missions_service.discounts_for(session, CountryCode.JO) == {}

    await enable_features(session_factory, "driver_levels_enabled")
    async with session_factory() as session:
        assert await missions_service.discounts_for(session, CountryCode.JO) == {3: 100}


async def test_a_zero_discount_is_off_without_a_condition_in_the_code(
    session_factory, jordan_settings: None
) -> None:
    """**صفرٌ يعني مطفأ** — والمفتاحُ وحدَه لا يكفي (قاعدةُ نسبة المشاركة)."""
    await enable_features(session_factory, "driver_levels_enabled")
    await _set_discount(session_factory, 3, 0)
    async with session_factory() as session:
        assert await missions_service.discounts_for(session, CountryCode.JO) == {}


# ------------------------------------------------------- المهامُّ والتقدّم


async def test_progress_counts_completed_rides_only(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**رحلةٌ ملغاةٌ أو متنازَعٌ عليها لا تُقرِّب أحداً من هدفه** (§٩)."""
    await enable_features(session_factory, "driver_levels_enabled")
    await _mission(session_factory, target="3")
    driver = await approved_driver(client, session_factory, DRIVER)
    await _complete_rides(session_factory, driver["driver_id"], 2)

    # ورحلةٌ ملغاةٌ في الشهر نفسِه لا تُحسب
    async with session_factory() as session:
        row = await session.scalar(
            select(Ride).where(Ride.driver_id == driver["driver_id"]).limit(1)
        )
        session.add(
            Ride(
                rider_id=row.rider_id,
                driver_id=driver["driver_id"],
                country_code=CountryCode.JO,
                status=RideStatus.CANCELLED_BY_RIDER,
                completed_at=datetime.now(UTC),
                vehicle_category="economy",
                pickup_point="SRID=4326;POINT(35.9 31.95)",
                dropoff_point="SRID=4326;POINT(35.95 31.99)",
                distance_km=Decimal("2.500"),
                duration_min=8,
                estimated_fare=Decimal("3.000"),
                currency="JOD",
                commission_percent_at_ride=Decimal("10"),
            )
        )
        await session.commit()

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        progress = await missions_service.progress_for(session, driver=row)
    assert len(progress) == 1
    assert progress[0].value == Decimal(2)
    assert progress[0].done is False


async def test_lowering_a_target_raises_whoever_was_waiting_on_it(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**التقدّمُ مقيسٌ حيّاً** (§٩): تنزيلُ الهدف يرفع في الدورة التالية، ولا
    يمسّ صفّاً بيد — قاعدةُ «flagged» ومقارنةُ الإحالة الحيّة نفسُها."""
    await enable_features(session_factory, "driver_levels_enabled")
    mission_id = await _mission(session_factory, target="5")
    driver = await approved_driver(client, session_factory, DRIVER)
    await _complete_rides(session_factory, driver["driver_id"], 3)

    async with session_factory() as session:
        await missions_service.reevaluate(session, CountryCode.JO)
        await session.commit()
        row = await session.get(Driver, driver["driver_id"])
        assert row.level == 0
        assert row.level_computed_at is not None

    async with session_factory() as session:
        await missions_service.update_mission(
            session, mission_id, target=Decimal("3")
        )
        await session.commit()

    async with session_factory() as session:
        await missions_service.reevaluate(session, CountryCode.JO)
        await session.commit()
        row = await session.get(Driver, driver["driver_id"])
        assert row.level == 3


async def test_one_metric_cannot_have_two_missions_in_a_month(
    session_factory, jordan_settings: None
) -> None:
    """هدفان لمعيارٍ واحدٍ يجعلان «هل أنجزها؟» سؤالاً بجوابين."""
    await _mission(session_factory, target="2")
    async with session_factory() as session:
        month = await missions_service._country_month(session, CountryCode.JO)
        try:
            await missions_service.create_mission(
                session,
                country=CountryCode.JO,
                month=month,
                metric="completed_rides",
                target=Decimal("9"),
                title="مهمة ثانية",
            )
        except missions_service.MissionExists:
            pass
        else:  # pragma: no cover
            raise AssertionError("قُبلت مهمّةٌ ثانيةٌ لنفس المعيار")


async def test_an_unknown_metric_is_refused_not_swallowed(
    session_factory, jordan_settings: None
) -> None:
    """مهمّةٌ بمعيارٍ لا يقرؤه أحدٌ تُعرض للكباتن ولا تُنجَز أبداً."""
    from app.core.exceptions import InvalidInput

    async with session_factory() as session:
        month = await missions_service._country_month(session, CountryCode.JO)
        try:
            await missions_service.create_mission(
                session,
                country=CountryCode.JO,
                month=month,
                metric="active_hours",
                target=Decimal("10"),
                title="ساعات",
            )
        except InvalidInput:
            pass
        else:  # pragma: no cover
            raise AssertionError("قُبل معيارٌ لا مصدرَ له")


# ------------------------------------------------------------- المستوى


async def test_the_level_is_zeroed_when_the_feature_is_off(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**مطفأً يُصفَّر لا يُترك**: مستوىً باقٍ يعيد ترتيباً حُسب على تعريفٍ زال."""
    await enable_features(session_factory, "driver_levels_enabled")
    await _mission(session_factory, target="1")
    driver = await approved_driver(client, session_factory, DRIVER)
    await _complete_rides(session_factory, driver["driver_id"], 2)

    async with session_factory() as session:
        await missions_service.reevaluate(session, CountryCode.JO)
        await session.commit()
        assert (await session.get(Driver, driver["driver_id"])).level == 3

    from app.models.feature_flag import FeatureFlag

    async with session_factory() as session:
        await session.execute(
            update(FeatureFlag)
            .where(
                FeatureFlag.country_code == CountryCode.JO,
                FeatureFlag.feature_key == "driver_levels_enabled",
            )
            .values(enabled=False)
        )
        await session.commit()

    async with session_factory() as session:
        await missions_service.reevaluate(session, CountryCode.JO)
        await session.commit()
        assert (await session.get(Driver, driver["driver_id"])).level == 0


async def test_a_new_driver_is_level_zero_not_missing(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**والصفرُ مستوىً** لا نقص — فلا يُعامَل الجديدُ معاملةَ الناقص."""
    driver = await approved_driver(client, session_factory, DRIVER)
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
    assert row.level == 0
    assert row.level_computed_at is None


# ------------------------------------------------------------- الشارات


async def test_a_badge_needs_a_written_reason_and_lands_in_the_audit_log(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings: None
) -> None:
    """**السببُ شرطٌ لا حقلٌ اختياري**: شارةٌ بلا سببٍ تُقرأ بعد شهرٍ فلا يعرف
    أحدٌ لماذا مُنحت ولا هل تُسحب."""
    driver = await approved_driver(client, session_factory, DRIVER)
    created = await client.post(
        "/admin/badges",
        json={"key": "helper", "label": "عونٌ في ليلةٍ عصيبة"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    badge_id = created.json()["id"]

    refused = await client.post(
        f"/admin/drivers/{driver['driver_id']}/badges",
        json={"badge_id": badge_id, "note": ""},
        headers=admin_headers,
    )
    assert refused.status_code == 422

    granted = await client.post(
        f"/admin/drivers/{driver['driver_id']}/badges",
        json={"badge_id": badge_id, "note": "أعاد حقيبةً لراكب"},
        headers=admin_headers,
    )
    assert granted.status_code == 201, granted.text

    from app.models.audit import AdminAuditLog as AuditLog

    async with session_factory() as session:
        entry = await session.scalar(
            select(AuditLog).where(AuditLog.entity_type == "driver_badge")
        )
    assert entry is not None
    assert entry.details["note"] == "أعاد حقيبةً لراكب"


async def test_a_badge_never_touches_the_dispatch_order(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings: None
) -> None:
    """**ولا تدخل الشاراتُ ترتيبَ التوزيع بحال** (§٤).

    وجعلُ التقدير يزيد الطلباتِ يجعل المشرفَ **يوزّع المال بيده** — وهذا هو
    الفرقُ الذي وُجد الجدولان لأجله. فالشارةُ تُمنح ولا يتبدّل شيءٌ في الترتيب.
    """
    await enable_features(session_factory, "driver_levels_enabled")
    await _set_discount(session_factory, 3, 100)

    near = await approved_driver(client, session_factory, DRIVER)
    far = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-5302"
    )
    async with session_factory() as session:
        await session.execute(
            update(Driver)
            .where(Driver.id.in_([near["driver_id"], far["driver_id"]]))
            .values(is_online=True)
        )
        await session.commit()

    badge = (
        await client.post(
            "/admin/badges",
            json={"key": "star", "label": "نجمة"},
            headers=admin_headers,
        )
    ).json()
    await client.post(
        f"/admin/drivers/{far['driver_id']}/badges",
        json={"badge_id": badge["id"], "note": "خدمةٌ ممتازة"},
        headers=admin_headers,
    )

    class P:
        def __init__(self, driver_id, distance_km):
            self.driver_id = driver_id
            self.distance_km = distance_km

    class R:
        country_code = CountryCode.JO
        vehicle_category = "economy"

    async with session_factory() as session:
        ranked = await _rank(
            session, [P(near["driver_id"], 0.5), P(far["driver_id"], 0.6)], R()
        )
    # كلاهما مستوى صفر، والشارةُ لا تُقدِّم صاحبَها — فالأقربُ أوّلاً
    assert ranked[0].driver_id == near["driver_id"]


async def test_the_driver_screen_states_the_effect_in_meters(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings: None
) -> None:
    """**الأثرُ يُقال بصدق أو لا يُقال** (§٦): «يقرّبك ٥٠م» جملةٌ تُقاس، و«أولويةٌ
    في الطلبات» وعدٌ يعدّه صاحبُه ولا يجده."""
    await enable_features(session_factory, "driver_levels_enabled")
    await _mission(session_factory, target="1")
    await _set_discount(session_factory, 3, 50)
    driver = await approved_driver(client, session_factory, DRIVER)
    await _complete_rides(session_factory, driver["driver_id"], 2)

    async with session_factory() as session:
        await missions_service.reevaluate(session, CountryCode.JO)
        await session.commit()

    body = (await client.get("/drivers/me/progress", headers=driver["headers"])).json()
    assert body["enabled"] is True
    assert body["level"] == 3
    assert body["level_effect_meters"] == 50
    assert body["missions_done"] == 1
    assert body["missions_total"] == 1
    # **الهدفُ والقيمةُ بمقياسٍ واحد**: رحلاتٌ بلا كسور
    assert body["missions"][0]["value"] == "2"
    assert body["missions"][0]["target"] == "1"


async def test_the_screen_answers_with_enabled_false_not_a_404(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """مطفأً تُخفى الشاشةُ في التطبيق — ومنفذٌ يرتدّ خطأً يجعلها تبدو معطوبةً
    لمن وصلها برابطٍ قديم. **والشاراتُ تبقى**: تقديرٌ نالَه صاحبُه."""
    driver = await approved_driver(client, session_factory, DRIVER)
    body = (await client.get("/drivers/me/progress", headers=driver["headers"])).json()
    assert body["enabled"] is False
    assert body["missions"] == []
    assert body["level"] == 0
