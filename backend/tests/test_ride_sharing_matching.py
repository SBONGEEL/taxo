"""المطابقةُ الجغرافية للمشاركة — الممرُّ وسقفُ الالتفاف ونافذةُ الانتظار.

ثلاثتُها **أرقامُ إعداداتٍ per-country** (SPEC §5.12)، فكلُّ اختبارٍ هنا يحرّك
الرقمَ نفسَه بدل أن يحرّك إحداثيات: رقمٌ يُقرأ من الجدول ولا يغيّر سلوكاً هو
حقلٌ في اللوحة لا يفعل شيئاً — وهذا المشروعُ شحن هذا الشكل من قبل.

**والالتفافُ هنا ٤٠ دقيقة بالبناء**: مسارُ الاختبار يعطي ٢٠ دقيقةً لكل ساق،
فالمنفردةُ ساقٌ واحدةٌ والمشتركةُ ثلاث. فالسقفُ الذي يقبل ما فوق الأربعين يقبل،
وما دونها يردّ — وهو ما يجعل الحدَّ مقيساً لا موصوفاً.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.enums import (
    CountryCode,
    Currency,
    Gender,
    GenderPreference,
    RideStatus,
    VehicleCategory,
)
from app.models.ride import Ride, make_point
from app.models.sharing import RideSharingSetting
from app.models.user import User
from app.services import sharing as sharing_service
from tests.helpers import approved_driver, rider_session

# نقطتا الرحلة الأولى — داخل عمّان، والمسافةُ بينهما بضعةُ كيلومترات
LEAD_PICKUP = (31.9500, 35.9100)
LEAD_DROPOFF = (31.9800, 35.8600)
# على الخط بينهما تقريباً: داخل ممرِّ الكيلومترين
NEAR_PICKUP = (31.9600, 35.8950)
NEAR_DROPOFF = (31.9750, 35.8700)
# المفرق — سبعون كيلومتراً شمال شرق عمّان، خارج أيِّ ممرّ
FAR_POINT = (32.3400, 36.2100)

WIDE_DETOUR = 45  # يتّسع للأربعين
TIGHT_DETOUR = 5


async def _settings(
    session_factory,
    *,
    corridor_km: Decimal = Decimal("2.000"),
    max_detour_minutes: int = WIDE_DETOUR,
    partner_wait_seconds: int = 300,
) -> None:
    async with session_factory() as session:
        row = await session.scalar(
            select(RideSharingSetting).where(
                RideSharingSetting.country_code == CountryCode.JO
            )
        )
        if row is None:
            row = RideSharingSetting(country_code=CountryCode.JO)
            session.add(row)
        row.discount_percent = Decimal("25.00")
        row.corridor_km = corridor_km
        row.max_detour_minutes = max_detour_minutes
        row.partner_wait_seconds = partner_wait_seconds
        await session.commit()


def _ride(
    *,
    rider_id,
    driver_id,
    pickup,
    dropoff,
    status=RideStatus.ACCEPTED,
    preference=GenderPreference.ANY,
) -> Ride:
    return Ride(
        rider_id=rider_id,
        driver_id=driver_id,
        share_discount_percent_at_ride=Decimal("25.00"),
        gender_preference=preference,
        country_code=CountryCode.JO,
        vehicle_category=VehicleCategory.ECONOMY,
        pickup_point=make_point(*pickup),
        dropoff_point=make_point(*dropoff),
        status=status,
        distance_km=Decimal("10.000"),
        duration_min=Decimal("20.00"),
        estimated_fare=Decimal("8.000"),
        currency=Currency.JOD,
        commission_percent_at_ride=Decimal("0.00"),
    )


@pytest.fixture
async def pair(client, session_factory, jordan_settings) -> dict:
    """رحلةٌ أولى مقبولةٌ على كبتن، وطلبٌ ثانٍ لم يُوزَّع بعد."""
    driver = await approved_driver(client, session_factory)
    riders = []
    for index in range(2):
        body = await rider_session(
            client,
            {
                "phone": f"+96279555070{index}",
                "password": "Rider12345",
                "name": f"راكب {index}",
                "country_code": "JO",
                "role": "rider",
            },
        )
        riders.append(body["user"]["id"])

    async with session_factory() as session:
        lead = _ride(
            rider_id=riders[0],
            driver_id=driver["driver_id"],
            pickup=LEAD_PICKUP,
            dropoff=LEAD_DROPOFF,
        )
        joiner = _ride(
            rider_id=riders[1],
            driver_id=None,
            pickup=NEAR_PICKUP,
            dropoff=NEAR_DROPOFF,
            status=RideStatus.SEARCHING,
        )
        session.add_all([lead, joiner])
        await session.commit()
        return {
            "lead_id": lead.id,
            "joiner_id": joiner.id,
            "riders": [r for r in riders],
        }


async def _match(session_factory, pair) -> sharing_service.Match | None:
    async with session_factory() as session:
        joiner = await session.get(Ride, pair["joiner_id"])
        rider = await session.get(User, joiner.rider_id)
        return await sharing_service.find_lead(session, joiner, rider)


async def test_a_ride_along_the_corridor_matches(session_factory, pair):
    """المرشَّحُ داخل الممرِّ وتحت السقف — والالتفافُ يُعاد مقيساً لا موصوفاً."""
    await _settings(session_factory)
    match = await _match(session_factory, pair)

    assert match is not None
    assert match.lead.id == pair["lead_id"]
    # ثلاثُ سيقانٍ بعشرين دقيقةً مقابل ساقٍ واحدة
    assert match.detour_minutes == Decimal("40.00")


async def test_a_ride_outside_the_corridor_does_not_match(session_factory, pair):
    """**نقطةٌ خارج الممرِّ تُقصى في القاعدة قبل أيِّ نداء خارجي.**

    وهذا ما يشتريه الممرُّ: بلا حدٍّ جغرافيٍّ يصير كلُّ طلبٍ في البلد مرشَّحاً،
    ونداءُ Mapbox لكلِّ واحدٍ منها في طريقٍ يقف عليه راكبٌ ينتظر.
    """
    await _settings(session_factory)
    async with session_factory() as session:
        joiner = await session.get(Ride, pair["joiner_id"])
        joiner.dropoff_point = make_point(*FAR_POINT)
        await session.commit()

    assert await _match(session_factory, pair) is None


async def test_the_corridor_is_measured_in_metres_not_degrees(session_factory, pair):
    """ممرٌّ بعرض **متر** لا يطابق شيئاً — والدرجةُ ١١١ ألفَ متر.

    **قِيس بالحذف**: بإسقاط تحويلَي `geography` معاً يقيس `ST_DWithin` بالدرجات،
    فيمرّ هذا ويمرّ معه المفرقُ على بعد سبعين كيلومتراً من ممرِّ الكيلومترين.
    وحذفُ **أحدهما** لا يُسقط شيئاً — PostGIS يحوّل الطرفَ الآخر ضمناً — فالاختبارُ
    يحرس الوحدةَ لا سطراً بعينه.
    """
    await _settings(session_factory, corridor_km=Decimal("0.001"))
    assert await _match(session_factory, pair) is None


async def test_a_detour_over_the_cap_is_refused(session_factory, pair):
    """السقفُ يحمي **من قَبِل أولاً**: رحلتُه لا تطول بلا حدّ لأجل خصمِ غيره."""
    await _settings(session_factory, max_detour_minutes=TIGHT_DETOUR)
    assert await _match(session_factory, pair) is None


async def test_a_lead_past_its_wait_window_is_not_offered(session_factory, pair):
    """نافذةُ الانتظار تُقاس من لحظة الطلب — ومن مضى وقتُه انطلق بأمره."""
    await _settings(session_factory, partner_wait_seconds=60)
    async with session_factory() as session:
        lead = await session.get(Ride, pair["lead_id"])
        lead.created_at = datetime.now(UTC) - timedelta(minutes=10)
        await session.commit()

    assert await _match(session_factory, pair) is None


async def test_a_lead_that_already_has_a_group_takes_nobody(session_factory, pair):
    """**لا شريكَ ثالث** (قرارُ المالك الثامن) — والمجموعةُ وحدَها تقول ذلك."""
    await _settings(session_factory)
    async with session_factory() as session:
        lead = await session.get(Ride, pair["lead_id"])
        lead.share_group_id = lead.id
        await session.commit()

    assert await _match(session_factory, pair) is None


async def test_a_gendered_ride_is_not_paired_with_a_man(session_factory, pair):
    """**أخطرُ ما في البند** (SPEC §5.12، ثالثاً): طلبٌ نسائيٌّ لا يجلس فيه رجل.

    والراكبُ هنا لم يخالف شيئاً — طلبُه عاديٌّ وتفضيلُه `any`. الذي يمنعه هو
    طلبُ **الأولى**: كبتنةٌ طلبتها لأمانها، فمقعدٌ ثانٍ لرجلٍ ينقض ما اشترته.
    """
    await _settings(session_factory)
    async with session_factory() as session:
        lead = await session.get(Ride, pair["lead_id"])
        lead.gender_preference = GenderPreference.FEMALE
        lead_rider = await session.get(User, lead.rider_id)
        lead_rider.gender = Gender.FEMALE
        joiner_rider = await session.get(User, pair["riders"][1])
        joiner_rider.gender = Gender.MALE
        await session.commit()

    assert await _match(session_factory, pair) is None


async def test_two_women_are_paired_on_a_gendered_ride(session_factory, pair):
    """والشرطُ ليس «لا مشاركةَ لطلبٍ نسائي» بل «لا مشاركةَ إلا مع راكبة».

    ولولا هذا النصفُ لصار الحارسُ إلغاءً للميزة عند من طلبتها — وهي نفسُ
    المطابقةِ ثنائيةِ الاتجاه في الخدمة النسائية (10-ج).
    """
    await _settings(session_factory)
    async with session_factory() as session:
        lead = await session.get(Ride, pair["lead_id"])
        lead.gender_preference = GenderPreference.FEMALE
        for rider_id in pair["riders"]:
            rider = await session.get(User, rider_id)
            rider.gender = Gender.FEMALE
        await session.commit()

    match = await _match(session_factory, pair)
    assert match is not None and match.lead.id == pair["lead_id"]


async def test_a_gendered_joiner_needs_a_woman_in_the_first_seat(
    session_factory, pair
):
    """والشرطُ متناظر: من اشترطت كبتنةً لا تُقحَم مع من لم يُعلن أنوثته.

    فحمايةُ الأولى وحدَها تترك الثانيةَ — التي اشترطت هي أيضاً — في المقعد الذي
    هربت منه.
    """
    await _settings(session_factory)
    async with session_factory() as session:
        joiner = await session.get(Ride, pair["joiner_id"])
        joiner.gender_preference = GenderPreference.FEMALE
        joiner_rider = await session.get(User, pair["riders"][1])
        joiner_rider.gender = Gender.FEMALE
        await session.commit()

    assert await _match(session_factory, pair) is None


async def test_a_departed_lead_is_not_a_candidate(session_factory, pair):
    """الالتحاقُ قبل الانطلاق وحدَه — وبعده البابُ مغلقٌ في المطابقة كما في الخدمة."""
    await _settings(session_factory)
    async with session_factory() as session:
        lead = await session.get(Ride, pair["lead_id"])
        lead.status = RideStatus.IN_PROGRESS
        await session.commit()

    assert await _match(session_factory, pair) is None
