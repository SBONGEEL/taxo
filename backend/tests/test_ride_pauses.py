"""الوقفةُ غير المخطَّطة وانتظارُ الوصول (SPEC §5.10-ب).

**والفروعُ الستةُ للمالك هي ما يُقاس هنا**، وأخطرُها الفرع (هـ): عدّادُ الوصول
**لا يبدأ خارج نطاق الالتقاء** — «وإلا صار «وصلت» الكاذبُ باباً للكسب». وهو
اختبارٌ يحرس **مالاً**، ويفشل بحذف شرط النطاق.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.pause import RidePause
from app.models.pricing import PricingRule
from app.models.ride import Ride
from app.services import pauses
from tests.helpers import (
    DRIVER,
    accepted_ride,
    approved_driver,
    bring_online,
    broadcast_location,
    completed_ride,
    rider_session,
    started_ride,
)

PICKUP_LAT = 31.9539
PICKUP_LNG = 35.9106


async def _set_pause_pricing(
    session_factory,
    *,
    per_min: str = "0.200",
    arrival_free: int = 2,
    cap: int = 0,
) -> None:
    async with session_factory() as session:
        await session.execute(
            update(PricingRule).values(
                pause_price_per_min=Decimal(per_min),
                arrival_free_minutes=arrival_free,
                pause_max_minutes=cap,
            )
        )
        await session.commit()


async def _age_pause(session_factory, ride_id: str, minutes: float) -> None:
    """يُقدّم بدايةَ الوقفة — **أرخصُ من انتظارٍ حقيقيّ وأصدقُ من رقمٍ مزروع**."""
    async with session_factory() as session:
        row = await session.scalar(
            select(RidePause).where(
                RidePause.ride_id == uuid.UUID(ride_id), RidePause.ended_at.is_(None)
            )
        )
        assert row is not None
        row.started_at = datetime.now(UTC) - timedelta(minutes=minutes)
        await session.commit()


def _assert_billed(
    charge: Decimal,
    *,
    minutes: str,
    rate: str,
    not_rate: str | None = None,
) -> None:
    """**حدٌّ لا مساواة — ولماذا، كي لا يُقرأ تراخياً.**

    `_age_pause` يكتب `started_at = now − دقائق`، **والرسمُ يُحسب في نداءٍ
    لاحقٍ بـ`now` الخاصِّ به**، والانتظارُ يُحتسب بالثانية (§5.10-ب). فكلُّ
    تأخّرٍ بين النداءين يدخل الحسابَ حقاً: عند ٠٫٢٠٠/دقيقة **٠٫٣ ثانيةٍ
    تساوي جزءاً من الألف بالضبط**. وهو ما أحمرَّ به
    `test_the_rate_is_frozen_against_a_later_settings_change` تحت حمل
    المجموعة (٢٠٢٦-٠٨-٢٤، ٢٫٠٠١ بدل ٢٫٠٠٠) **ومرّ منفرداً مرتين**.

    **وليست المساواةُ التامّةُ هي المحروس**: ما تحرسه هذه الاختباراتُ أن
    الرسمَ **بالمعدَّل المجمَّد ومن الوقت المجمَّد** — لا أن الثواني صفر.
    فكانت أضيقَ من معناها، تسقط على تأخّرِ شبكةٍ ولا تسقط على شيءٍ يخصُّ
    المال. **واختبارٌ يصيح على السليم يُضعَّف أو يُحذف**، وكلاهما يُسقط ما
    يحرسه حقاً.

    **فشرطان لا واحد، ولا يُستبدل المحروسُ بأضعفَ منه:**

    ١. **بالمعدَّل المجمَّد ومن وقته**: `دقائق × معدَّل` حدّاً أدنى، وفوقه
       **نصفُ دقيقةٍ** حدّاً أعلى. **والحدُّ الأعلى هو نصفُ الشرط الثاني**:
       هو ما يقول إن الحسابَ من `started_at` المجمَّد لا من زمنٍ آخر — فلو
       قُرئ زمنٌ لاحقٌ أو صفِّرت البدايةُ لَخرج المبلغُ عن المدى.
    ٢. **وليس بالمعدَّل الجديد**: يُسمَّى صراحةً حيث يوجد —
       `charge < not_rate` أي **أقلُّ من دقيقةٍ واحدةٍ بالسعر الجديد**،
       وهو الفرقُ الذي وُجد الاختبارُ لأجله (٢ لا ٥٠).

    **والهامشُ مقيسٌ لا مُقدَّر**: أسوأُ انحرافٍ رُصد ٠٫٠٠١ (≈٠٫٣ث)،
    والهامشُ نصفُ دقيقة — ≈١٠٠× ذلك، **ويبقى دون أصغرِ خطأِ معدَّلٍ بمراتب**.
    """
    lower = (Decimal(minutes) * Decimal(rate)).quantize(Decimal("0.001"))
    upper = lower + (Decimal(rate) / 2)
    assert lower <= charge < upper, (
        f"{charge} خارج [{lower}, {upper}) — فليس بالمعدَّل المجمَّد "
        f"({rate}/دقيقة) أو ليس محسوباً من وقت الوقفة المجمَّد"
    )
    if not_rate is not None:
        assert charge < Decimal(not_rate), (
            f"{charge} يبلغ دقيقةً بالمعدَّل الجديد ({not_rate}) — "
            "فالتجميدُ لم يصمد"
        )


# ------------------------------------------- الفرعُ (هـ): النطاقُ شرطُ العدّاد


async def test_no_arrival_counter_starts_outside_the_pickup_radius(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**قرارُ المالك (هـ) بتعليله**: «وإلا صار «وصلت» الكاذبُ باباً للكسب».

    ويُتحقَّق منه بحذف شرط النطاق في `mark_arrived`: عندها يبدأ العدّادُ لمن
    ضغط «وصلت» من الشارع المجاور — **وهو مالٌ يُصنع بضغطة**.
    """
    await _set_pause_pricing(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], driver)

    # **بعيدٌ عن نقطة الالتقاء** — نحو ثلاثة كيلومترات
    await broadcast_location(client, driver, lat=PICKUP_LAT + 0.03, lng=PICKUP_LNG
    )
    assert (
        await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    ).status_code == 200

    async with session_factory() as session:
        rows = await session.scalars(
            select(RidePause).where(RidePause.ride_id == uuid.UUID(ride["id"]))
        )
    assert list(rows) == [], "بدأ عدّادٌ خارج النطاق"


async def test_the_arrival_counter_starts_inside_the_radius(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """وداخلَ النطاق يبدأ — **بالضغطة** (الفرع د)، لا بالاقتراب وحدَه."""
    await _set_pause_pricing(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], driver)

    await broadcast_location(client, driver, lat=PICKUP_LAT, lng=PICKUP_LNG
    )
    # **قبل الضغطة لا عدّاد** وإن كان واقفاً في النقطة
    async with session_factory() as session:
        before = (
            await session.scalars(
                select(RidePause).where(RidePause.ride_id == uuid.UUID(ride["id"]))
            )
        ).all()
    assert list(before) == []

    await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])

    async with session_factory() as session:
        row = await session.scalar(
            select(RidePause).where(RidePause.ride_id == uuid.UUID(ride["id"]))
        )
    assert row is not None
    assert row.kind == "arrival"
    assert row.free_minutes_at_pause == 2


async def test_no_counter_at_all_when_the_driver_is_silent(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**وصمتٌ يعني «لا عدّاد»**: الشكُّ لمن سيُحاسَب، وهو الراكب."""
    await _set_pause_pricing(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], driver)

    # لا بثَّ موقعٍ حيّاً — يُمسح مفتاحُ الحضور
    from app.core.redis_client import get_redis_client
    from app.services import geo

    redis = get_redis_client()
    await redis.delete(geo.presence_key(driver["driver_id"]))

    await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    async with session_factory() as session:
        rows = await session.scalars(
            select(RidePause).where(RidePause.ride_id == uuid.UUID(ride["id"]))
        )
    assert list(rows) == []


# --------------------------------------------- المهلةُ المجانية وحسابُ المال


async def test_the_free_grace_is_not_billed_and_what_is_over_it_is(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**من تأخّر دقيقتين لا يُحاسَب، ومن تأخّر عشرين يُحاسَب.**

    والحسابُ **بالثانية** كما في المحطات: ٥ دقائقَ − مهلةُ ٢ = ٣ × ٠٫٢٠٠.
    """
    await _set_pause_pricing(session_factory, per_min="0.200", arrival_free=2)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], driver)
    await broadcast_location(client, driver, lat=PICKUP_LAT, lng=PICKUP_LNG)
    await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])

    await _age_pause(session_factory, ride["id"], 5)

    body = (
        await client.get(f"/rides/{ride['id']}", headers=rider["headers"])
    ).json()
    # ٥ دقائقَ − مهلةُ ٢ = ٣ × ٠٫٢٠٠ — **حدّاً لا مساواةً** (`_assert_billed`)
    _assert_billed(Decimal(body["pause_charge"]), minutes="3", rate="0.200")
    # **والعدّادُ يُنشر للراكب وهو يمشي** — فلا مفاجأةَ في شاشة الدفع
    assert body["open_pause"] is not None
    assert Decimal(body["open_pause"]["waited_minutes"]) >= Decimal("5")


async def test_a_mid_ride_pause_has_no_free_grace(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**الوقفةُ لم تدخل التقدير، فالعدّادُ يبدأ بالضغطة** — ولا مهلةَ فيها.

    ومهلةٌ هنا تعني وقتاً يقفه الكبتنُ بلا مقابلٍ على شيءٍ لم يُحسب له أصلاً.
    """
    await _set_pause_pricing(session_factory, per_min="0.200", arrival_free=5)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)

    assert (
        await client.post(f"/rides/{ride['id']}/pause", headers=driver["headers"])
    ).status_code == 200
    await _age_pause(session_factory, ride["id"], 3)

    body = (await client.get(f"/rides/{ride['id']}", headers=rider["headers"])).json()
    assert body["open_pause"]["free_minutes"] == 0
    # ٣ دقائقَ بلا مهلة × ٠٫٢٠٠ — **حدّاً لا مساواةً** (`_assert_billed`)
    _assert_billed(Decimal(body["pause_charge"]), minutes="3", rate="0.200")


async def test_the_pause_charge_is_inside_the_final_fare(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**داخلةٌ في `final_fare`، وسطرٌ مستقلٌّ في التفصيل** (الفرع و).

    المجموعُ واحدٌ والسببُ ظاهر — ولا مبلغان يُجمعان بيد.
    """
    await _set_pause_pricing(session_factory, per_min="0.500", arrival_free=0)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)

    await client.post(f"/rides/{ride['id']}/pause", headers=driver["headers"])
    await _age_pause(session_factory, ride["id"], 4)

    before = (await client.get(f"/rides/{ride['id']}", headers=rider["headers"])).json()
    estimated = Decimal(before["estimated_fare"])

    finished = await client.post(
        f"/rides/{ride['id']}/complete", headers=driver["headers"]
    )
    assert finished.status_code == 200, finished.text
    row = finished.json()
    charge = Decimal(row["pause_charge"])
    assert charge >= Decimal("2.000")
    assert Decimal(row["final_fare"]) == estimated + charge


async def test_completing_closes_an_open_pause_so_it_stops_growing(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**وقفةٌ تبقى مفتوحةً تُقاس حتى الآن** — فتكبر كلَّما فُتحت الشاشة."""
    await _set_pause_pricing(session_factory, per_min="0.500", arrival_free=0)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)

    await client.post(f"/rides/{ride['id']}/pause", headers=driver["headers"])
    await _age_pause(session_factory, ride["id"], 2)
    await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])

    async with session_factory() as session:
        row = await session.scalar(
            select(RidePause).where(RidePause.ride_id == uuid.UUID(ride["id"]))
        )
    assert row.ended_at is not None


async def test_starting_the_ride_closes_the_arrival_wait(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """بدءُ الرحلة يوقف عدّادَ الوصول — والراكبُ صار في السيارة."""
    await _set_pause_pricing(session_factory, per_min="0.200", arrival_free=0)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], driver)
    await broadcast_location(client, driver, lat=PICKUP_LAT, lng=PICKUP_LNG)
    await client.post(f"/rides/{ride['id']}/arrive", headers=driver["headers"])
    await client.post(f"/rides/{ride['id']}/start", headers=driver["headers"])

    async with session_factory() as session:
        row = await session.scalar(
            select(RidePause).where(RidePause.ride_id == uuid.UUID(ride["id"]))
        )
    assert row is not None and row.ended_at is not None


# ------------------------------------------------------- التجميدُ والفروع


async def test_the_rate_is_frozen_against_a_later_settings_change(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**تعديلُ اللوحة يحكم ما يأتي لا وقفةً يقف فيها كبتنٌ الآن.**"""
    await _set_pause_pricing(session_factory, per_min="0.200", arrival_free=0)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)
    await client.post(f"/rides/{ride['id']}/pause", headers=driver["headers"])
    await _age_pause(session_factory, ride["id"], 10)

    # المشرفُ يضاعف السعر بعد أن بدأت الوقفة
    await _set_pause_pricing(session_factory, per_min="5.000", arrival_free=0)

    body = (await client.get(f"/rides/{ride['id']}", headers=rider["headers"])).json()
    # **الشرطان معاً**: بالمعدَّل المجمَّد ومن وقته (١٠ × ٠٫٢٠٠)، **وليس
    # بالجديد** — فلو قُرئ ٥٫٠٠٠ لَبلغ الرسمُ ٥٠٫٠٠٠. و«حدٌّ لا مساواة»
    # علّتُه في `_assert_billed`، وليست تراخياً.
    _assert_billed(
        Decimal(body["pause_charge"]),
        minutes="10",
        rate="0.200",
        not_rate="5.000",
    )


async def test_there_is_no_limit_on_the_number_of_pauses(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**لا حدَّ لعددها** (الفرع ج): وحدٌّ عدديٌّ يعاقب رحلةً طويلةً بطبيعتها."""
    await _set_pause_pricing(session_factory, per_min="0.100", arrival_free=0)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)

    for _ in range(5):
        assert (
            await client.post(f"/rides/{ride['id']}/pause", headers=driver["headers"])
        ).status_code == 200
        assert (
            await client.post(f"/rides/{ride['id']}/resume", headers=driver["headers"])
        ).status_code == 200

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(RidePause).where(RidePause.ride_id == uuid.UUID(ride["id"]))
            )
        ).all()
    assert len(rows) == 5


async def test_the_cap_notifies_and_never_ends_the_ride(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**يُنبَّه الطرفان ولا تُنهى الرحلة** (الفرع أ) — الإنهاءُ فعلُ الكبتن."""
    from app.tasks.pauses import _sweep

    await _set_pause_pricing(session_factory, per_min="0.100", arrival_free=0, cap=3)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)
    await client.post(f"/rides/{ride['id']}/pause", headers=driver["headers"])
    await _age_pause(session_factory, ride["id"], 9)

    assert await _sweep() == 1
    # **ولا تُنبَّه مرتين** — الختمُ تحت القفل
    assert await _sweep() == 0

    async with session_factory() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
    assert row.status.value == "in_progress", "أُنهيت الرحلةُ بالسقف"


# --------------------------------------------------------------- التزامن


async def test_two_simultaneous_presses_open_one_pause_not_two(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**الفهرسُ الجزئيُّ هو حارسُ المال.**

    وبحذف `uq_ride_pauses_open` تُفتح وقفتان على رحلةٍ واحدة، **فيُحتسب الوقتُ
    مرتين على راكبٍ وقف مرة** — مالٌ من عدمٍ بلا استثناءٍ ولا سطرِ سجل.
    """
    await _set_pause_pricing(session_factory, per_min="0.500", arrival_free=0)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)

    results = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post(f"/rides/{ride['id']}/pause", headers=driver["headers"])
                for _ in range(3)
            )
        ),
        timeout=30,
    )
    codes = Counter(response.status_code for response in results)
    assert codes[200] == 1, codes

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(RidePause).where(RidePause.ride_id == uuid.UUID(ride["id"]))
            )
        ).all()
    assert len(rows) == 1


async def test_resuming_with_no_open_pause_is_refused(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """«استئناف» بلا وقفةٍ يُرفض — **زرٌّ يعمل ثم لا يفعل شيئاً يُعلّم التكرار**."""
    await _set_pause_pricing(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)

    refused = await client.post(
        f"/rides/{ride['id']}/resume", headers=driver["headers"]
    )
    assert refused.status_code == 404
    assert refused.json()["code"] == "no_open_pause"


async def test_only_the_rides_driver_can_pause_it(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """والراكبُ لا يوقف عدّاداً يُحاسَب به — **الفرع ب: بيد الكبتن وحدَه**."""
    await _set_pause_pricing(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await started_ride(client, rider["headers"], driver)

    refused = await client.post(
        f"/rides/{ride['id']}/pause", headers=rider["headers"]
    )
    assert refused.status_code in (403, 404)
