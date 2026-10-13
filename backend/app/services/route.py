"""مسار الرحلة الفعلي: التقاطه، ومسافته، وأثرها في السعر (SPEC القسم 5.7).

هذا هو الاستثناء الوحيد لقاعدة «الموقع اللحظي في Redis وحده»: بثّ الكبتن
متطايرٌ بعمر ستين ثانية، والقسم 5.7 يطلب منه أثراً باقياً لغرضين —
**المسافة الفعلية** التي يُعاد عليها حساب `final_fare`، و**دليلُ النزاع** في
لوحة الإدارة (القسم 13.4).

**العيّنة نقطةٌ كل عشرين ثانية** لا كل بثّة: البثّ كل ثلاث ثوانٍ (القسم 10)
فتخزينه كله يعني عشرين صفاً لكل دقيقة رحلة بلا زيادةٍ تُذكر في دقة المسافة.
العشرون داخل نافذة «15-30 ثانية» التي نصّ عليها القسم 5.7.

**العدّاد هو مفتاح Redis نفسه**: `SET NX EX` على `dispatch`-نمطٍ مألوف —
وجود المفتاح يعني «العيّنة الأخيرة قريبة»، وانقضاؤه هو الإذن بالتالية. فلا
عدّادَ ثانٍ يمكن أن يفترق عنه، ولا يكتب عاملا uvicorn نقطتين لنفس اللحظة.

الالتقاط **لا يُسقط بثَّ الموقع بسقوطه**: كبتنٌ يختفي من التوزيع لأن كتابة
نقطة مسار فشلت خسارةٌ أكبر من نقطةٍ ضائعة. الفشل يُسجَّل ويُبتلع، كما في
`services/tracking.py`.
"""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.models.ride import Ride, RideRoutePoint, make_point

logger = logging.getLogger(__name__)

# داخل نافذة «نقطة كل 15-30 ثانية» (SPEC القسم 5.7)
SAMPLE_INTERVAL_SECONDS = 20

# شبكة أمان للمفتاح الرابط بين الكبتن ورحلته الجارية: يُحذف صراحةً عند
# الإنهاء أو الإلغاء، وهذا العمر لئلا يبقى إلى الأبد إن سقطت العملية بينهما
ACTIVE_RIDE_TTL_SECONDS = 6 * 60 * 60

_KM = Decimal("0.001")

# أقل عدد نقاط يصنع خطاً: نقطةٌ واحدة ليست مساراً ولا مسافة لها
MIN_POINTS_FOR_DISTANCE = 2

# انحرافٌ أكبر من هذا بين المسافة المقدّرة والفعلية يعيد حساب `final_fare`.
# القسم 5.7 يقول «الانحراف الكبير» بلا رقم؛ العشرون بالمئة رقمٌ يتجاوز خطأ
# تقدير Mapbox المعتاد وتحويلةً قصيرة، ولا يبلغه إلا مسارٌ اختلف فعلاً.
FARE_RECALC_DEVIATION_PERCENT = Decimal("20")


def active_ride_key(driver_id: uuid.UUID | str) -> str:
    """الرحلة التي يسير فيها هذا الكبتن الآن — يقرؤه كل بثّ موقع."""
    return f"route:ride:{driver_id}"


def sample_key(ride_id: uuid.UUID | str) -> str:
    return f"route:sample:{ride_id}"


def tail_key(ride_id: uuid.UUID | str) -> str:
    """**آخرُ نقطةٍ كُتبت من الدفعات** (§٧٥-ج): موضعُها وزمنُها ورقمُ دفعتها — عليه تُقاس عتبةُ الحركة ويُرتَّب ما بعده ويُعرف المكرَّر."""
    return f"route:tail:{ride_id}"


#: **عتبةُ الحركة الدنيا بين نقطتين مكتوبتين** — ما دونها رجفةُ GPS عند إشارةٍ حمراء، تُطيل المسافةَ ولا تُضيف طريقاً. **ولا تُقصِّر
#: مسافةً حقيقيّة**: المقارنةُ بآخر نقطةٍ *مكتوبة* لا بالتي قبلها، فالزحفُ البطيءُ يُكتب حين يبلغ مجموعُه العتبة.
MIN_POINT_METERS = 5.0
#: سقفُ النقاط في الدفعة الواحدة — دقيقتان من نقاط الثانية، **وما تراكم في انقطاعٍ أطول يُرسل دفعاتٍ متتالية**
MAX_BATCH_POINTS = 120


@dataclass(frozen=True, slots=True)
class TripPoint:
    lat: float
    lng: float
    heading: float | None
    #: لحظةُ التسجيل في الهاتف (مللي ثانية) — **تُستعمل فروقُها لا قيمتُها**: ساعةُ الهاتف قد تبعد دقائق عن ساعة الخادم
    t: int


def _meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rad = math.radians
    dlat, dlng = rad(lat2 - lat1), rad(lng2 - lng1)
    h = math.sin(dlat / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(dlng / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


# ------------------------------------------------------------------ الالتقاط


async def begin(redis: Redis, *, driver_id: uuid.UUID, ride_id: uuid.UUID) -> None:
    """يبدأ التقاط المسار مع `in_progress` — قبلها الكبتن في طريقه للراكب."""
    await redis.set(
        active_ride_key(driver_id), str(ride_id), ex=ACTIVE_RIDE_TTL_SECONDS
    )


async def end(redis: Redis, *, driver_id: uuid.UUID) -> None:
    """يوقف الالتقاط عند الإنهاء أو الإلغاء."""
    await redis.delete(active_ride_key(driver_id))


async def capture(
    redis: Redis,
    *,
    driver_id: uuid.UUID,
    lat: float,
    lng: float,
    heading: float | None,
) -> None:
    """يُستدعى مع كل بثّ موقع، ويكتب نقطةً كل `SAMPLE_INTERVAL_SECONDS` فقط.

    لا يعرف المستدعي شيئاً عن الرحلة: هذه الدالة تسأل Redis وحدها، فبثّ كبتنٍ
    بلا رحلة جارية يمر من هنا بقراءة مفتاح واحدة ثم ينصرف.
    """
    ride_id = await redis.get(active_ride_key(driver_id))
    if ride_id is None:
        return

    # المفتاح والعدّاد شيء واحد: من يضعه هو من يكتب النقطة
    if not await redis.set(
        sample_key(ride_id), "1", nx=True, ex=SAMPLE_INTERVAL_SECONDS
    ):
        return

    try:
        async with SessionLocal() as session:
            # **الساقُ تُقرأ من الرحلة لا تُحسب هنا** (المرحلة 12-ب): كاتبُ
            # `current_leg` واحدٌ (`rides.resume_from_stop` تحت قفل الصف)،
            # والملتقِطُ ينسخ ما وجده. وقراءةُ عمودٍ واحدٍ أرخصُ من عدِّ
            # المحطات المستأنَفة في مسارٍ يمرّ كل عشرين ثانية لكل رحلة
            leg = await session.scalar(
                select(Ride.current_leg).where(Ride.id == uuid.UUID(ride_id))
            )
            session.add(
                RideRoutePoint(
                    ride_id=uuid.UUID(ride_id),
                    point=make_point(lat, lng),
                    heading=None if heading is None else Decimal(str(heading)),
                    leg=leg or 0,
                )
            )
            await session.commit()
    except Exception:  # pragma: no cover - لا يُسقط بثَّ الموقع
        logger.exception("تعذّر تسجيل نقطة مسار للرحلة %s", ride_id)


async def capture_points(
    redis: Redis,
    *,
    driver_id: uuid.UUID,
    points: list[TripPoint],
    seq: int | None,
    received_at: float | None = None,
) -> bool:
    """**دفعةُ نقاط الرحلة** (§٧٥-ج) — كلُّها تُكتب لا عيّنةٌ منها، فلا تقصر مسافةُ الأجرة ولا يضيع منعطف.

    * **الترتيبُ بزمن الاستلام**: آخرُ نقطةٍ في الدفعة «الآن» عند الخادم، وما قبلها بفروقها في ساعة الهاتف — فلا يُخلط زمنُ هاتفٍ
      منحرفِ الساعة بزمن الخادم، **ولا تسبق نقطةٌ ما كُتب قبلها** (تُزاح بعد الذيل بمللي ثانية).
    * **والمكرَّرُ لا يُكتب مرّتين**: دفعةٌ أُعيد إرسالُها بعد انقطاعٍ (`seq` ≤ آخر ما كُتب) تُقبل ولا تُكتب — فيُردّ إقرارُها ويُمحى من
      الهاتف.
    * **وعتبةُ الحركة** `MIN_POINT_METERS` من آخر نقطةٍ مكتوبة.

    يعيد `True` إن قُبلت الدفعة فيُقَرّ بها — كُتبت، أو كانت مكرّرة، **أو لا رحلةَ جارية** (النقاطُ لا مكانَ لها، وإبقاؤها في الهاتف
    لا يجد لها مكاناً غداً) — و`False` إن تعذّرت الكتابة وحدَه، **فلا إقرار وتُعاد**.
    """
    ride_id = await redis.get(active_ride_key(driver_id))
    if ride_id is None or not points:
        return True
    ride_id = ride_id.decode() if isinstance(ride_id, bytes) else str(ride_id)
    raw = await redis.get(tail_key(ride_id))
    tail = json.loads(raw) if raw else {}
    if seq is not None and tail.get("seq") is not None and seq <= int(tail["seq"]):
        return True

    received = time.time() if received_at is None else received_at
    ordered = sorted(points, key=lambda p: p.t)
    last_t = ordered[-1].t
    floor = float(tail.get("at") or 0)
    last_lat, last_lng = tail.get("lat"), tail.get("lng")
    rows: list[tuple[TripPoint, float]] = []
    for point in ordered:
        at = received - max(0, last_t - point.t) / 1000
        if at <= floor:
            at = floor + 0.001
        if last_lat is not None and _meters(last_lat, last_lng, point.lat, point.lng) < MIN_POINT_METERS:
            continue
        rows.append((point, at))
        floor, last_lat, last_lng = at, point.lat, point.lng

    try:
        if rows:
            async with SessionLocal() as session:
                leg = await session.scalar(select(Ride.current_leg).where(Ride.id == uuid.UUID(ride_id)))
                for point, at in rows:
                    session.add(
                        RideRoutePoint(
                            ride_id=uuid.UUID(ride_id),
                            point=make_point(point.lat, point.lng),
                            heading=None if point.heading is None else Decimal(str(point.heading)),
                            leg=leg or 0,
                            created_at=datetime.fromtimestamp(at, UTC),
                        )
                    )
                await session.commit()
        new_tail = {"seq": seq if seq is not None else tail.get("seq"), "at": floor, "lat": last_lat, "lng": last_lng}
        await redis.set(tail_key(ride_id), json.dumps(new_tail), ex=ACTIVE_RIDE_TTL_SECONDS)
    except Exception:  # pragma: no cover - لا يُسقط البثّ — والدفعةُ بلا إقرارٍ تُعاد
        logger.exception("تعذّر تسجيل دفعة نقاطٍ للرحلة %s", ride_id)
        return False
    return True


# -------------------------------------------------------------- المسافة


# `ST_MakeLine` مجمِّعٌ يقبل geometry لا geography، ثم يُعاد الخط إلى
# geography ليأتي `ST_Length` بالأمتار على سطح الكرة لا بالدرجات. الترتيب
# داخل المجمِّع لا خارجه: بغيره يصنع postgres خطاً بترتيبٍ غير محدّد فتخرج
# مسافةٌ أطول من الحقيقة.
_DISTANCE_SQL = text(
    """
    SELECT
        count(*) AS point_count,
        ST_Length(
            ST_MakeLine(point::geometry ORDER BY created_at, id)::geography
        ) AS meters
    FROM ride_route_points
    WHERE ride_id = :ride_id
    """
)


async def actual_distance_km(
    session: AsyncSession, ride_id: uuid.UUID
) -> Decimal | None:
    """طول المسار المسجَّل بالكيلومترات، أو `None` إن لم تكفِ النقاط.

    `None` لا صفر: رحلةٌ صمت فيها تطبيق الكبتن لا مسافة فعلية موثوقة لها،
    وصفرٌ هنا يعني «سارت صفر كيلومتر» فيهبط السعر إلى الحد الأدنى ظلماً.
    """
    row = (await session.execute(_DISTANCE_SQL, {"ride_id": ride_id})).one()
    if row.point_count < MIN_POINTS_FOR_DISTANCE or row.meters is None:
        return None
    return (Decimal(str(row.meters)) / 1000).quantize(_KM, rounding=ROUND_HALF_UP)


def deviates(estimated_km: Decimal, actual_km: Decimal) -> bool:
    """هل انحرفت الفعلية عن المقدّرة انحرافاً يستوجب إعادة الحساب؟

    في الاتجاهين: مسارٌ أطول يُنصف الكبتن، وأقصرُ يُنصف الراكب. القسم 5.7
    يقول «عند الانحراف الكبير» بلا تفضيل طرف.
    """
    if estimated_km <= 0:
        return actual_km > 0
    deviation = abs(actual_km - estimated_km) / estimated_km * 100
    return deviation > FARE_RECALC_DEVIATION_PERCENT
