"""تزامنُ المحطات الوسيطة (المرحلة 12-ب).

**ما يملكه القفلُ هنا شيئان، وكلاهما يسقط بحذفه:**

1. **ختمُ الوصول واحد**: ضغطتان متزامنتان على «وصلتُ المحطة» تكتبان ختمين،
   فيبدأ عدّادُ الانتظار من الثاني ويضيع على الكبتن ما وقفه بينهما.
2. **`current_leg` يزيد مرةً لكل استئناف**: استئنافان متزامنان يزيدانه اثنين،
   فتُنسب نقاطُ الساق التالية إلى ساقٍ لم تبدأ ويُقرأ دليلُ النزاع خطأً.

**والاختبارُ على التداخل المرتَّب لا على `asyncio.gather` عبر HTTP**: نداءان
عبر العميل يتشابكان فقط إن شاءت حلقةُ الأحداث، وهو بالضبط ما يعطي ثقةً
كاذبة (وقع فعلاً في `test_driver_documents_concurrency`). فالاختبار يستدعي
الخدمةَ بجلستين، ويُبقي الأولى مفتوحةً بينما تبدأ الثانية — فتنتظر الثانيةُ
قفلَ الأولى في Postgres فعلاً.

**تحقُّقٌ بالحذف**: احذف `with_for_update` من `rides._locked_stop` وسيُبلغ
الاختبارُ عن ختمين/زيادتين بدل واحدة.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import AppError
from app.models.enums import FeatureKey
from app.models.ride import Ride, RideStop
from app.services import rides as rides_service
from tests.helpers import (
    DRIVER,
    approved_driver,
    bring_online,
    enable_features,
    rider_session,
    started_ride,
)
from tests.test_multi_stop import STOP_A, set_stop_pricing


async def _ride_at_stop(client, session_factory):
    await enable_features(session_factory, FeatureKey.MULTI_STOP_ENABLED.value)
    await set_stop_pricing(session_factory)
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await started_ride(client, rider["headers"], driver, stops=[dict(STOP_A)])
    return ride


# كم تُمسك الأولى قفلَها بعد أن تُشير للثانية بالبدء. ليست انتظاراً لنتيجة
# الثانية — تلك محجوزةٌ على القفل فلا تنتهي قبل أن تُفرج عنه الأولى، وانتظارُها
# جمودٌ في الاختبار نفسه (وقع في أول صياغةٍ لهذا الملف). الغرضُ أن تبلغ
# الثانيةُ `SELECT … FOR UPDATE` **فتحجز**، ثم تُطلقها الأولى بالـcommit
HOLD_SECONDS = 0.4


async def _call(
    session_factory,
    ride_id,
    stop_id,
    action,
    *,
    hold: asyncio.Event | None = None,
):
    """يستدعي الخدمةَ في جلسةٍ خاصة، ويُبقي المعاملة مفتوحةً عند الطلب."""
    async with session_factory() as session:
        ride = await rides_service.get_ride(session, ride_id)
        try:
            if action == "arrive":
                await rides_service.arrive_at_stop(session, ride, stop_id)
            else:
                await rides_service.resume_from_stop(session, ride, stop_id)
        except AppError as error:
            await session.rollback()
            return error.code

        if hold is not None:
            # المعاملةُ مفتوحةٌ والقفلُ مأخوذ — الآن تبدأ الثانية فتحجز
            hold.set()
            await asyncio.sleep(HOLD_SECONDS)
        await session.commit()
        return "ok"


async def test_two_arrivals_at_once_leave_one_stamp(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    ride = await _ride_at_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]

    first_holds = asyncio.Event()

    async def first():
        return await _call(
            session_factory, ride["id"], stop_id, "arrive", hold=first_holds
        )

    async def second():
        await asyncio.wait_for(first_holds.wait(), timeout=10)
        return await _call(session_factory, ride["id"], stop_id, "arrive")

    # الجمودُ يُعلَّق لا يرتفع، فالمهلةُ وحدها تُسقط الاختبار
    results = await asyncio.wait_for(
        asyncio.gather(first(), second(), return_exceptions=True), timeout=30
    )

    assert results.count("ok") == 1, results
    # الخاسرُ يرتدّ بالرمز المحدَّد لا بأي خطأ
    assert "invalid_ride_transition" in results, results

    async with session_factory() as session:
        stamps = (
            await session.scalars(
                select(RideStop.arrived_at).where(RideStop.ride_id == ride["id"])
            )
        ).all()
    assert sum(1 for stamp in stamps if stamp is not None) == 1, stamps


async def test_two_resumes_at_once_advance_the_leg_once(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**هذا ما يملكه القفلُ وحده**: عدّادُ الساق يزيد مرةً لا مرتين."""
    ride = await _ride_at_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]

    async with session_factory() as session:
        row = await rides_service.get_ride(session, ride["id"])
        await rides_service.arrive_at_stop(session, row, stop_id)
        await session.commit()

    first_holds = asyncio.Event()

    async def first():
        return await _call(
            session_factory, ride["id"], stop_id, "resume", hold=first_holds
        )

    async def second():
        await asyncio.wait_for(first_holds.wait(), timeout=10)
        return await _call(session_factory, ride["id"], stop_id, "resume")

    results = await asyncio.wait_for(
        asyncio.gather(first(), second(), return_exceptions=True), timeout=30
    )

    assert results.count("ok") == 1, results
    assert "invalid_ride_transition" in results, results

    async with session_factory() as session:
        row = await session.get(Ride, ride["id"])
        # **واحدةٌ لا اثنتان** — وبحذف القفل تصير 2
        assert row.current_leg == 1, row.current_leg
        stop = await session.scalar(
            select(RideStop).where(RideStop.ride_id == ride["id"])
        )
        assert stop.resumed_at is not None


async def test_the_wait_notice_is_written_once_under_concurrency(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """عاملان في نفس الدورة لا يُخطران الطرفين مرتين عن وقوفٍ واحد."""
    from datetime import UTC, datetime, timedelta

    ride = await _ride_at_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]

    async with session_factory() as session:
        row = await rides_service.get_ride(session, ride["id"])
        await rides_service.arrive_at_stop(session, row, stop_id)
        await session.commit()

    async with session_factory() as session:
        stop = await session.get(RideStop, stop_id)
        stop.arrived_at = datetime.now(UTC) - timedelta(minutes=40)
        await session.commit()

    async def mark():
        async with session_factory() as session:
            result = await rides_service.mark_stop_notified(session, stop_id)
            await session.commit()
            return result is not None

    results = await asyncio.wait_for(
        asyncio.gather(mark(), mark(), return_exceptions=True), timeout=30
    )
    assert results.count(True) == 1, results


async def test_waiting_charge_is_unaffected_by_reading_it_twice(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """القراءةُ لا تكتب: عدّادُ الانتظار مشتقٌّ من الختمين لا عمودٌ يُراكم.

    وهو ما يجعل قراءتَه أثناء الوقوف آمنةً — والراكبُ يقرؤه كل بضع ثوانٍ.
    """
    from datetime import UTC, datetime, timedelta

    ride = await _ride_at_stop(client, session_factory)
    stop_id = ride["stops"][0]["id"]

    async with session_factory() as session:
        row = await rides_service.get_ride(session, ride["id"])
        await rides_service.arrive_at_stop(session, row, stop_id)
        await session.commit()

    async with session_factory() as session:
        stop = await session.get(RideStop, stop_id)
        stop.arrived_at = datetime.now(UTC) - timedelta(minutes=10)
        await session.commit()

    async with session_factory() as session:
        row = await rides_service.get_ride(session, ride["id"])
        now = datetime.now(UTC)
        first = await rides_service.waiting_charge_for(session, row, now)
        second = await rides_service.waiting_charge_for(session, row, now)

    assert first == second == Decimal("0.700"), (first, second)
