"""تكوينُ المجموعة تحت التزامن (المرحلة 12-ي) — **قبل المطابقة وقبل أي شاشة**.

نفسُ انضباط `test_ride_sharing_index.py`: الفهرسُ قِيس قبل أن تُكتب خدمة، وهذا
يقيس **ما لا يملكه الفهرس** — وهو ما كُتب صراحةً في `SPEC` §5.12 بأنه للخدمة:

> أن يكون مقعدُ الشريك في **مجموعة الكبتن نفسِها**. لا يعبّر عنه فهرسٌ فريد
> (يحتاج مقارنةً بين صفّين).

**والسباقُ الحقيقيُّ هنا راكبان ينضمّان إلى الرحلة نفسِها في اللحظة نفسِها.**
وهي حالٌ واقعيةٌ لا مفتعلة: المطابقةُ ترشّح المرشّحين دفعةً واحدة، فاثنان في
نفس الممرِّ يبلغان الرحلةَ الأولى معاً.

**وما يقع بلا قفلٍ ليس استثناءً بل مالٌ من لا شيء**: ثلاثةُ ركّابٍ على كبتنٍ
واحد، كلٌّ منهم بخصمٍ تتحمّله الشركة، وسيارةٌ فيها مقعدان.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.models.enums import CountryCode, Currency, RideStatus, VehicleCategory
from app.models.ride import SHARE_SEAT_PARTNER, Ride, make_point
from app.services import sharing as sharing_service
from tests.helpers import approved_driver, rider_session

DEADLOCK_TIMEOUT = 20.0
DISCOUNT = Decimal("25.00")


def _ride(*, rider_id, driver_id, status, share=DISCOUNT) -> Ride:
    return Ride(
        rider_id=rider_id,
        driver_id=driver_id,
        share_discount_percent_at_ride=share,
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


@pytest.fixture
async def stage(client: AsyncClient, session_factory) -> dict:
    """رحلةٌ أولى مقبولةٌ على كبتن، وراكبان ينتظران الانضمام."""
    driver = await approved_driver(client, session_factory)
    riders = []
    for index in range(3):
        body = await rider_session(
            client,
            {
                "phone": f"+96279555040{index}",
                "password": "Rider12345",
                "name": f"راكب {index}",
                "country_code": "JO",
                "role": "rider",
            },
        )
        riders.append(uuid.UUID(body["user"]["id"]))

    async with session_factory() as session:
        lead = _ride(
            rider_id=riders[0],
            driver_id=driver["driver_id"],
            status=RideStatus.ACCEPTED,
        )
        waiting = [
            _ride(rider_id=riders[i], driver_id=None, status=RideStatus.SEARCHING)
            for i in (1, 2)
        ]
        session.add_all([lead, *waiting])
        await session.commit()
        return {
            "driver_id": driver["driver_id"],
            "lead_id": lead.id,
            "waiting": [row.id for row in waiting],
        }


async def _join(session_factory, *, lead_id, ride_id, hold: float = 0.0) -> str:
    """محاولةُ التحاقٍ في معاملةٍ مستقلة — `ok` أو رمزُ الرفض."""
    async with session_factory() as session:
        lead = await session.get(Ride, lead_id)
        ride = await session.get(Ride, ride_id)
        try:
            await sharing_service.join_group(session, ride=ride, lead=lead)
            if hold:
                # يُبقي المعاملةَ مفتوحةً فيدخل الثاني في انتظار القفل فعلاً
                await asyncio.sleep(hold)
            await session.commit()
            return "ok"
        except AppError as caught:
            await session.rollback()
            return caught.code


async def test_two_riders_joining_at_once_fill_one_seat(session_factory, stage):
    """**الثابت**: مقعدٌ ثانٍ واحدٌ لا اثنان — والثاني يُرفض برمزٍ مفهوم.

    **وهذا الاختبارُ يحرس سلوكاً لا قفلاً، وقد قِيس ذلك**: بإسقاط
    `with_for_update` عن صفِّ الرحلة الأولى يبقى أخضر — لأن الملتقِطَ هو الفهرسُ
    الجزئيُّ `(driver_id, share_seat)`، وهو محروسٌ بالحذف في
    `test_ride_sharing_index.py`. فالمقعدُ ملكُ الفهرس، والخدمةُ تترجم
    `IntegrityError` إلى رمزٍ يقرؤه الراكب.

    وهو نفسُ شكلِ اختبارِ «مستخدمٍ واحدٍ للكوبون» في 12-ز: يمرّ بلا قفل لأن
    فهرساً آخر يمنع الحالةَ أصلاً — فيُوثَّق بما هو، لا بما نودّ أن يكون. وما
    يملكه القفلُ وحدَه في الاختبار الذي يليه.
    """
    results = await asyncio.wait_for(
        asyncio.gather(
            _join(
                session_factory,
                lead_id=stage["lead_id"],
                ride_id=stage["waiting"][0],
                hold=0.4,
            ),
            _join(
                session_factory,
                lead_id=stage["lead_id"],
                ride_id=stage["waiting"][1],
            ),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert sorted(results) == ["ok", "share_group_unavailable"], results

    async with session_factory() as session:
        lead = await session.get(Ride, stage["lead_id"])
        seats = await session.scalar(
            select(func.count())
            .select_from(Ride)
            .where(
                Ride.share_group_id == lead.share_group_id,
                Ride.share_seat == SHARE_SEAT_PARTNER,
            )
        )
        active = await session.scalar(
            select(func.count())
            .select_from(Ride)
            .where(
                Ride.driver_id == stage["driver_id"],
                Ride.status == RideStatus.ACCEPTED,
            )
        )
    assert seats == 1, "مقعدٌ ثانٍ واحد"
    assert active == 2, "راكبان على الكبتن لا ثلاثة"


async def test_a_join_racing_the_departure_loses(session_factory, stage):
    """**ما يملكه القفلُ وحدَه**: حالةُ الرحلة الأولى بين الفحص والكتابة.

    الاختبارُ الأولُ في هذا الملف **يمرّ بحذف `with_for_update` عن الرحلة
    الأولى** — قِيس ذلك — لأن الفهرسَ الجزئيَّ `(driver_id, share_seat)` يلتقط
    المقعدَ المكرَّر وحدَه. فالمقعدُ ملكُ الفهرس لا ملكُ القفل، والقاعدةُ في هذا
    المشروع أن يُبحث عن القفل الآخر قبل تصديق اختبار.

    **وما لا يلتقطه أيُّ فهرس** هو هذا: الكبتنُ ينطلق واللاحقُ يقرأ حالةً قديمة.
    بلا القفل يجتاز الفحصَ على قراءةٍ سابقةٍ للانطلاق ثم يكتب — فيصير راكبٌ
    ملحَقاً بسيارةٍ غادرت مكانه، وليس في القاعدة ما يعترض: صفٌّ سليمٌ تماماً
    يقول ما لم يقع. **ولا استثناءَ يُرفع ولا سطرَ في السجل.**

    والتشابكُ مقصودٌ لا متروكٌ للجدولة (شكلُ المرحلة 8): الانطلاقُ يمسك معاملتَه
    مفتوحةً ٤٠٠ms، واللاحقُ يبدأ بعد ١٠٠ms — فينتظر القفلَ فعلاً.
    """

    async def depart() -> None:
        async with session_factory() as session:
            lead = await session.scalar(
                select(Ride).where(Ride.id == stage["lead_id"]).with_for_update()
            )
            lead.status = RideStatus.IN_PROGRESS
            await session.flush()
            await asyncio.sleep(0.4)
            await session.commit()

    async def join_late() -> str:
        await asyncio.sleep(0.1)
        return await _join(
            session_factory,
            lead_id=stage["lead_id"],
            ride_id=stage["waiting"][0],
        )

    _, outcome = await asyncio.wait_for(
        asyncio.gather(depart(), join_late()), timeout=DEADLOCK_TIMEOUT
    )
    assert outcome == "share_group_unavailable", outcome

    async with session_factory() as session:
        joiner = await session.get(Ride, stage["waiting"][0])
    assert joiner.share_seat != SHARE_SEAT_PARTNER
    assert joiner.driver_id is None
    assert joiner.status is RideStatus.SEARCHING


async def test_the_partner_lands_in_the_drivers_own_group(session_factory, stage):
    """**ما لا يملكه الفهرس**: المجموعةُ والكبتنُ معاً من الرحلة الأولى.

    فهرسٌ فريدٌ لا يقارن صفّين، فلو أُسند الشريكُ إلى مجموعةٍ وكبتنٍ مختلفين
    لما اعترض شيءٌ في القاعدة — والنتيجةُ تجميعٌ يكذب على كلِّ تقريرٍ يقرؤه.
    """
    assert (
        await _join(
            session_factory,
            lead_id=stage["lead_id"],
            ride_id=stage["waiting"][0],
        )
        == "ok"
    )

    async with session_factory() as session:
        lead = await session.get(Ride, stage["lead_id"])
        partner = await session.get(Ride, stage["waiting"][0])

    assert lead.share_group_id is not None
    assert partner.share_group_id == lead.share_group_id
    assert partner.driver_id == lead.driver_id
    assert partner.share_seat == SHARE_SEAT_PARTNER
    assert partner.status is RideStatus.ACCEPTED


async def test_a_departed_ride_takes_no_partner(session_factory, stage):
    """**بعد الانطلاق لا التحاق**: الراكبُ في السيارة والباب أُغلق.

    وهذا شرطُ حالةٍ لا شرطُ قفل — لكنه يُقاس هنا لأن إسقاطَه يعني راكباً
    يُضاف إلى رحلةٍ سائرةٍ فيجد سيارةً لا تعود إليه.
    """
    async with session_factory() as session:
        lead = await session.get(Ride, stage["lead_id"])
        lead.status = RideStatus.IN_PROGRESS
        await session.commit()

    assert (
        await _join(
            session_factory,
            lead_id=stage["lead_id"],
            ride_id=stage["waiting"][0],
        )
        == "share_group_unavailable"
    )


async def test_a_solo_ride_takes_no_partner(session_factory, stage):
    """رحلةٌ لم تطلب المشاركة لا يُلحق بها أحد — نسبتُها صفر.

    فالخصمُ المجمَّد هو **طلبُ المشاركة نفسُه** (لا عمودَ ثانٍ يمكن أن يخالفه)،
    وإلحاقُ شريكٍ بمن لم يطلبها يضع في سيارته راكباً لم يوافق عليه.
    """
    async with session_factory() as session:
        lead = await session.get(Ride, stage["lead_id"])
        lead.share_discount_percent_at_ride = Decimal("0.00")
        await session.commit()

    assert (
        await _join(
            session_factory,
            lead_id=stage["lead_id"],
            ride_id=stage["waiting"][0],
        )
        == "share_group_unavailable"
    )
