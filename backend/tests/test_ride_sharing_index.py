"""فهرسُ «رحلةُ الكبتن الجارية» تحت التزامن (المرحلة 12-ي، SPEC §5.12).

**هذا أوّلُ ما كُتب في هذه المرحلة، قبل أيِّ خدمةٍ وأيِّ شاشة**، بأمر قرارِ
المالك الثاني: الفهرسُ وحدَه هو المكانُ الذي تستطيع فيه المشاركةُ أن تصنع مالاً
من لا شيء — كبتنٌ يحمل رحلتين لا تجمعهما مجموعة يُحاسَب عليهما حسابَ رحلتين
منفصلتين، وقد ساق واحدة.

**والاختبارُ يضرب القاعدةَ مباشرةً لا عبر HTTP**، وهذا مقصود: ما يُقاس هنا
حارسٌ في القاعدة لا فرعٌ في خدمة. جلستان مستقلّتان تُدخلان صفَّين معاً
(`asyncio.gather`)، فتنتظر إحداهما قفلَ الفهرس في postgres فعلاً. ولو كُتب على
مستوى الخدمة لمرَّ أخضرَ على قاعدةٍ بلا فهرسٍ أصلاً.

**وأربعةُ ثوابتَ لا ثابتٌ واحد**، لأن الفهرس الجديد يجب أن يكسب الجديدَ **دون
أن يخسر القديم**:

1. رحلتان في **مجموعةٍ واحدة** على كبتنٍ واحد تنجحان — وهي الميزة.
2. **ثالثةٌ في المجموعة نفسِها تُرفض** — «راكبان لا أكثر».
3. رحلتان **منفردتان** على كبتنٍ واحد: تنجح واحدةٌ فقط — وهو الحارسُ القديم
   الذي كان `uq_rides_active_driver` يملكه وحدَه، ولا يجوز أن يسقط بتوسيعه.
4. مجموعتان مختلفتان على كبتنٍ واحد: تنجح واحدةٌ فقط — وإلا صار «كبتنٌ بمجموعةٍ
   واحدة» كلاماً.

والثالثُ والرابع هما ما أسقطا الصيغةَ التي اقترحتها المواصفةُ أولاً
(`COALESCE(share_group_id, id)`): انظر `test_two_solo_rides_on_one_driver`.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.enums import CountryCode, Currency, RideStatus, VehicleCategory
from app.models.ride import SHARE_SEAT_LEAD, SHARE_SEAT_PARTNER, Ride, make_point
from tests.helpers import approved_driver, rider_session

# مهلةٌ تحرس من الجمود: الجمود يعلّق ولا يرفع استثناءً، فلا يكشفه إلا انتهاؤها
DEADLOCK_TIMEOUT = 20.0


def _ride(
    *,
    rider_id: uuid.UUID,
    driver_id: uuid.UUID,
    group: uuid.UUID | None,
    seat: int = SHARE_SEAT_LEAD,
    status: RideStatus = RideStatus.ACCEPTED,
) -> Ride:
    """صفُّ رحلةٍ بأقلِّ ما يقبله الجدول — فما يُقاس هنا الفهرسُ لا التسعير."""
    return Ride(
        rider_id=rider_id,
        driver_id=driver_id,
        share_group_id=group,
        share_seat=seat,
        country_code=CountryCode.JO,
        vehicle_category=VehicleCategory.ECONOMY,
        pickup_point=make_point(31.95, 35.91),
        dropoff_point=make_point(31.98, 35.86),
        status=status,
        distance_km=Decimal("5.000"),
        duration_min=Decimal("12.00"),
        estimated_fare=Decimal("3.500"),
        currency=Currency.JOD,
        commission_percent_at_ride=Decimal("0.00"),
    )


async def _insert(session_factory, ride: Ride, *, hold: float = 0.0) -> str:
    """إدخالٌ في معاملةٍ مستقلة — يُرجع `ok` أو اسمَ الفهرس الذي رفضه.

    و`hold` يُبقي المعاملةَ مفتوحةً بعد الإدخال وقبل الإيداع، فيدخل الثاني
    فعلاً في انتظار قفل الفهرس بدل أن يتصادفَ الترتيبُ فيمرّان.
    """
    async with session_factory() as session:
        session.add(ride)
        try:
            await session.flush()
            if hold:
                await asyncio.sleep(hold)
            await session.commit()
            return "ok"
        except IntegrityError as caught:
            await session.rollback()
            text = str(caught)
            if "ck_rides_ride_share_seat_valid" in text:
                return "check"
            if "uq_rides_active" in text:
                return "conflict"
            return "other"


async def _active_count(session_factory, driver_id: uuid.UUID) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count())
            .select_from(Ride)
            .where(Ride.driver_id == driver_id, Ride.status == RideStatus.ACCEPTED)
        )


@pytest.fixture
async def parties(client: AsyncClient, session_factory) -> dict:
    """كبتنٌ معتمدٌ وثلاثةُ ركّاب — لكلِّ صفِّ رحلةٍ راكبُه (الشكل ب)."""
    driver = await approved_driver(client, session_factory)
    other = await approved_driver(
        client,
        session_factory,
        {
            "phone": "+962795550190",
            "password": "Driver12345",
            "name": "كبتنٌ آخر",
            "country_code": "JO",
            "role": "driver",
        },
        plate_number="AMM-9090",
    )
    riders = []
    for index in range(3):
        body = await rider_session(
            client,
            {
                "phone": f"+96279555010{index}",
                "password": "Rider12345",
                "name": f"راكب {index}",
                "country_code": "JO",
                "role": "rider",
            },
        )
        riders.append(uuid.UUID(body["user"]["id"]))
    return {
        "driver_id": driver["driver_id"],
        "other_driver_id": other["driver_id"],
        "riders": riders,
    }


async def test_two_riders_in_one_group_share_one_driver(session_factory, parties):
    """الميزةُ نفسُها: صفّان بمجموعةٍ واحدة على كبتنٍ واحد يمرّان معاً."""
    driver_id = parties["driver_id"]
    group = uuid.uuid4()

    results = await asyncio.wait_for(
        asyncio.gather(
            _insert(
                session_factory,
                _ride(
                    rider_id=parties["riders"][0],
                    driver_id=driver_id,
                    group=group,
                    seat=SHARE_SEAT_LEAD,
                ),
                hold=0.4,
            ),
            _insert(
                session_factory,
                _ride(
                    rider_id=parties["riders"][1],
                    driver_id=driver_id,
                    group=group,
                    seat=SHARE_SEAT_PARTNER,
                ),
            ),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert results == ["ok", "ok"], results
    assert await _active_count(session_factory, driver_id) == 2


async def test_a_third_rider_in_the_group_is_refused(session_factory, parties):
    """«راكبان لا أكثر» — والثالثُ يرتدّ من القاعدة لا من فرعٍ في خدمة."""
    driver_id = parties["driver_id"]
    group = uuid.uuid4()

    for index, seat in enumerate((SHARE_SEAT_LEAD, SHARE_SEAT_PARTNER)):
        assert (
            await _insert(
                session_factory,
                _ride(
                    rider_id=parties["riders"][index],
                    driver_id=driver_id,
                    group=group,
                    seat=seat,
                ),
            )
            == "ok"
        )

    # لا مقعدَ ثالثَ يطلبه: القيدُ يرفض `seat = 3`، والمقعدُ الثاني محجوز
    assert (
        await _insert(
            session_factory,
            _ride(
                rider_id=parties["riders"][2],
                driver_id=driver_id,
                group=group,
                seat=SHARE_SEAT_PARTNER,
            ),
        )
        == "conflict"
    )
    assert (
        await _insert(
            session_factory,
            _ride(
                rider_id=parties["riders"][2],
                driver_id=driver_id,
                group=group,
                seat=3,
            ),
        )
        == "check"
    )
    assert await _active_count(session_factory, driver_id) == 2


async def test_two_solo_rides_on_one_driver(session_factory, parties):
    """**الحارسُ القديم يجب أن ينجو من التوسيع.**

    رحلتان منفردتان (`share_group_id IS NULL`) على كبتنٍ واحد: واحدةٌ تمرّ.
    وهذا هو الثابتُ الذي أسقط `COALESCE(share_group_id, id)`: هي تعطي كلَّ صفٍّ
    مفتاحاً من مُعرِّفه هو، فيختلف المفتاحان ويمرّ الصفّان — أي أن الفهرسَ
    «الموسَّع» كان **يُلغي الحارسَ الذي جاء ليوسّعه**، بلا أن يُسقط اختباراً
    قائماً واحداً.
    """
    driver_id = parties["driver_id"]

    results = await asyncio.wait_for(
        asyncio.gather(
            _insert(
                session_factory,
                _ride(rider_id=parties["riders"][0], driver_id=driver_id, group=None),
                hold=0.4,
            ),
            _insert(
                session_factory,
                _ride(rider_id=parties["riders"][1], driver_id=driver_id, group=None),
            ),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert sorted(results) == ["conflict", "ok"], results
    assert await _active_count(session_factory, driver_id) == 1


async def test_two_different_groups_on_one_driver(session_factory, parties):
    """كبتنٌ لمجموعةٍ واحدة: مجموعتان متزامنتان تمرّ إحداهما."""
    driver_id = parties["driver_id"]

    results = await asyncio.wait_for(
        asyncio.gather(
            _insert(
                session_factory,
                _ride(
                    rider_id=parties["riders"][0],
                    driver_id=driver_id,
                    group=uuid.uuid4(),
                ),
                hold=0.4,
            ),
            _insert(
                session_factory,
                _ride(
                    rider_id=parties["riders"][1],
                    driver_id=driver_id,
                    group=uuid.uuid4(),
                ),
            ),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert sorted(results) == ["conflict", "ok"], results
    assert await _active_count(session_factory, driver_id) == 1


async def test_a_finished_ride_frees_the_driver(session_factory, parties):
    """الفهرسُ جزئيّ: رحلةٌ منتهيةٌ لا تحجز الكبتن — وإلا عمل مرةً واحدة."""
    driver_id = parties["driver_id"]

    assert (
        await _insert(
            session_factory,
            _ride(
                rider_id=parties["riders"][0],
                driver_id=driver_id,
                group=None,
                status=RideStatus.COMPLETED,
            ),
        )
        == "ok"
    )
    assert (
        await _insert(
            session_factory,
            _ride(rider_id=parties["riders"][1], driver_id=driver_id, group=None),
        )
        == "ok"
    )


async def test_a_group_holds_two_rides_whatever_the_drivers(session_factory, parties):
    """**ما يملكه `uq_rides_active_share_group` وحدَه.**

    حذفُ هذا الفهرس لا يُسقط أيَّ اختبارٍ آخر في الملف، لأن حارسَ الكبتن يسبقه
    في كلِّ حالةٍ تجمع الصفوفَ على كبتنٍ واحد. فما يملكه هو الحالُ التي **تفترق**
    فيها الصفوفُ على كباتن: مجموعةٌ صفّاها على كبتنين — وهي حالُ خطأٍ في الخدمة
    لا حالٌ مشروعة — ثم ثالثٌ يطلب الانضمام إليها على كبتنٍ ثالثٍ فارغ. حارسُ
    الكبتن لا يراه (كبتنُه خالٍ)، ولا يردّه إلا حدُّ المجموعة.

    ويُقاس بالحذف: بجعل الفهرس غيرَ فريدٍ يمرّ الثالثُ وتصير المجموعةُ ثلاثة.
    """
    group = uuid.uuid4()

    assert (
        await _insert(
            session_factory,
            _ride(
                rider_id=parties["riders"][0],
                driver_id=parties["driver_id"],
                group=group,
                seat=SHARE_SEAT_LEAD,
            ),
        )
        == "ok"
    )
    assert (
        await _insert(
            session_factory,
            _ride(
                rider_id=parties["riders"][1],
                driver_id=parties["other_driver_id"],
                group=group,
                seat=SHARE_SEAT_PARTNER,
            ),
        )
        == "ok"
    )

    # كبتنٌ ثالثٌ خالٍ، ومجموعةٌ ممتلئة: الردُّ من حدِّ المجموعة لا من حدِّ الكبتن
    third = await _insert(
        session_factory,
        _ride(
            rider_id=parties["riders"][2],
            driver_id=None,
            group=group,
            seat=SHARE_SEAT_PARTNER,
            status=RideStatus.ACCEPTED,
        ),
    )
    assert third == "conflict", third

    async with session_factory() as session:
        in_group = await session.scalar(
            select(func.count())
            .select_from(Ride)
            .where(Ride.share_group_id == group)
        )
    assert in_group == 2
