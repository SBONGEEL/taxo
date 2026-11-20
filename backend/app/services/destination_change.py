"""**«تعديل الوجهة»** — عرضٌ ثمّ تأكيد (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-أ).

**ثلاثُ قواعدَ تحكم الملفّ كلَّه:**

1. **العرضُ لا يغيّر شيئاً** — `quote` يحسب ويحفظ صفّاً بحاله `quoted`؛ والرحلةُ لا تُمسّ إلا في `confirm`.
2. **المعادلةُ نفسُها** — `pricing.estimate` حرفاً، بلا قيمةٍ ولا سطرٍ جديد: قبل البدء من الانطلاق إلى الوجهة الجديدة، **وأثناء الرحلة
   على طريقٍ مركَّب** = المقطوعُ فعلاً (نقاطُ المسار، أو طريقُ الانطلاق إلى موضع الكبتن إن صمت تطبيقُه) + من موضع الكبتن الآن إلى الوجهة
   الجديدة، **وزمنُهما** (ما مضى منذ البدء + الباقي). **وموضعُ الكبتن مجهولاً لا يُخمَّن**: ٤٠٩ «حاول بعد لحظات».
3. **التأكيدُ يقفل الرحلةَ أوّلاً** (`for_update`، ترتيبُ الأقفال: الرحلةُ ثمّ صفُّ العرض) ثمّ يتحقّق من كلِّ شيءٍ من جديد — الحالُ والمفتاحُ
   والعرضُ حيٌّ **وأجرةُ الرحلة ووجهتُها كما كانتا لحظةَ العرض**. **والتأكيدُ مرّتين يردّ النتيجةَ نفسَها** (انقطاعُ الشبكة بعد الإرسال).

**والمؤكَّدُ يُجمَّد** (`has_confirmed` يقرؤه `rides._final_fare`): لا يعيده انحرافُ الطريق، كالسعر المتّفق عليه.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, Conflict, NotFound
from app.models.destination_change import (
    CONFIRMED,
    DECLINED,
    EXPIRED,
    PHASE_IN_RIDE,
    PHASE_SEARCHING,
    QUOTED,
    RideDestinationChange,
)
from app.models.enums import AuditAction, FeatureKey, RideStatus
from app.models.ride import Ride, make_point
from app.models.user import User
from app.services import audit, directions, geo, pricing, rounding, route, settings_service
from app.services.directions import Coordinates, Route

logger = logging.getLogger(__name__)

#: عمرُ العرض — يكفي لقراءة السعر والضغط، ولا يبقى سعرُ طريقٍ قديمٍ صالحاً بعد أن تحرّكت السيارة
QUOTE_TTL = timedelta(minutes=2)

SEARCHING_STATUSES = frozenset({RideStatus.REQUESTED, RideStatus.SEARCHING})
IN_RIDE_STATUSES = frozenset({RideStatus.ACCEPTED, RideStatus.ARRIVED, RideStatus.IN_PROGRESS})


class DestinationChangeDisabled(AppError):
    status_code = 403
    code = "feature_disabled"
    message = "تعديلُ الوجهة غيرُ متاحٍ الآن"


class DestinationChangeNotAllowed(Conflict):
    code = "destination_change_not_allowed"
    message = "لا يمكن تعديلُ وجهة هذه الرحلة"


class DriverPositionUnknown(Conflict):
    code = "driver_position_unknown"
    message = "تعذّر معرفةُ موضع الكبتن الآن — حاول بعد لحظات"


class QuoteNoLongerValid(Conflict):
    code = "destination_quote_expired"
    message = "انتهت صلاحيةُ السعر المعروض — اطلب سعراً جديداً"


def _now() -> datetime:
    return datetime.now(UTC)


def phase_of(ride: Ride) -> str | None:
    if ride.status in SEARCHING_STATUSES:
        return PHASE_SEARCHING
    if ride.status in IN_RIDE_STATUSES:
        return PHASE_IN_RIDE
    return None


def ineligible_reason(ride: Ride) -> str | None:
    """**ما لا يُعدَّل بنوعه** (§١٠٩-أ/٧) — كلٌّ سعرُه على غير «انطلاق ⇐ وجهة». و`None` = يُعدَّل.

    **والتطبيقان يحسبان الشرطَ نفسَه** (`lib/destination-change.ts`) ليخفيا الزرّ — وهذا البابُ يرفض ما يصله على كلِّ حال."""
    if ride.ride_type != "standard":
        return "type"  # الطردُ وبالساعة
    if ride.commute_id is not None:
        return "commute"
    if ride.share_group_id is not None:
        return "shared"
    if ride.negotiated_fare is not None or ride.negotiation_offer is not None:
        return "negotiated"
    if (ride.stops_count or 0) > 0:
        return "stops"
    return None


async def _require_allowed(session: AsyncSession, ride: Ride) -> str:
    phase = phase_of(ride)
    if phase is None or ineligible_reason(ride) is not None:
        raise DestinationChangeNotAllowed()
    key = FeatureKey.DESTINATION_CHANGE_SEARCHING if phase == PHASE_SEARCHING else FeatureKey.DESTINATION_CHANGE_IN_RIDE
    if not await settings_service.is_feature_enabled(session, ride.country_code, key):
        raise DestinationChangeDisabled()
    return phase


@dataclass(frozen=True)
class _Priced:
    estimate: pricing.FareEstimate
    traveled_km: Decimal | None


async def _price(session: AsyncSession, redis: Redis, ride: Ride, target: Coordinates) -> _Priced:
    pickup = Coordinates(lat=ride.pickup_lat, lng=ride.pickup_lng)
    if ride.status != RideStatus.IN_PROGRESS:
        # **قبل البدء: تقديرُ الطلب نفسُه** — كأنّ الراكبَ طلب هذه الوجهةَ من البداية
        estimate = await pricing.estimate(
            session,
            country_code=ride.country_code,
            vehicle_category=ride.vehicle_category,
            pickup=pickup,
            dropoff=target,
            rider_id=ride.rider_id,
        )
        return _Priced(estimate, None)

    position = (
        await geo.last_position(redis, driver_id=ride.driver_id, country_code=ride.country_code)
        if ride.driver_id is not None
        else None
    )
    if position is None:
        raise DriverPositionUnknown()
    here = Coordinates(lat=position.lat, lng=position.lng)
    remaining = await directions.route_between(session, here, target, ride.country_code)
    traveled = await route.actual_distance_km(session, ride.id)
    if traveled is None:
        # **تطبيقٌ صامتٌ لا يُصفَّر مقطوعُه** — طريقُ الانطلاق إلى موضعه الآن، لا صفرٌ يُهبط السعر ولا رقمٌ يُخترع
        traveled = (await directions.route_between(session, pickup, here, ride.country_code)).distance_km
    started = ride.started_at or _now()
    elapsed = Decimal(max(0.0, (_now() - started).total_seconds()) / 60).quantize(Decimal("0.01"))
    combined = Route(
        distance_km=(traveled + remaining.distance_km).quantize(Decimal("0.001")),
        duration_min=(elapsed + remaining.duration_min).quantize(Decimal("0.01")),
    )
    estimate = await pricing.estimate(
        session,
        country_code=ride.country_code,
        vehicle_category=ride.vehicle_category,
        pickup=pickup,
        dropoff=target,
        rider_id=ride.rider_id,
        route=combined,
    )
    return _Priced(estimate, traveled)


async def quote(
    session: AsyncSession,
    redis: Redis,
    *,
    ride: Ride,
    rider: User,
    lat: float,
    lng: float,
    address: str | None,
) -> RideDestinationChange:
    """**يحسب ويحفظ عرضاً — ولا يمسّ الرحلة.** الـcommit للراوتر."""
    phase = await _require_allowed(session, ride)
    target = Coordinates(lat=lat, lng=lng)
    from app.services import markets

    # **الوجهةُ الجديدةُ داخل السوق** كما يُشترط على الطلب نفسِه (`rides.request_ride`)
    await markets.require_inside(session, rider, [target])
    priced = await _price(session, redis, ride, target)
    estimate = priced.estimate
    row = RideDestinationChange(
        ride_id=ride.id,
        phase=phase,
        status=QUOTED,
        old_lat=ride.dropoff_lat,
        old_lng=ride.dropoff_lng,
        old_address=ride.dropoff_address,
        new_lat=lat,
        new_lng=lng,
        new_address=(address or "").strip()[:255] or None,
        old_fare=ride.estimated_fare,
        new_fare=estimate.fare,
        # **ما يراه الراكبُ هو ما سيُحفظ** — مقرَّباً بسياسة رحلته المجمَّدة كالعدّاد الحيّ (§٧٠-ج/٤)
        shown_fare=rounding.ride_display_fare(ride, estimate.fare),
        new_fare_lines=pricing.lines_json(estimate.lines),
        new_distance_km=estimate.route.distance_km,
        new_duration_min=estimate.route.duration_min,
        new_captain_fees=estimate.captain_fees,
        new_facility_id=estimate.facility_id,
        traveled_km=priced.traveled_km,
        expires_at=_now() + QUOTE_TTL,
    )
    session.add(row)
    await session.flush()
    return row


async def _locked_change(session: AsyncSession, ride: Ride, change_id: uuid.UUID) -> RideDestinationChange:
    row = (
        await session.execute(
            select(RideDestinationChange)
            .where(RideDestinationChange.id == change_id, RideDestinationChange.ride_id == ride.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound()
    return row


async def confirm(
    session: AsyncSession,
    redis: Redis,
    *,
    ride: Ride,
    change_id: uuid.UUID,
    actor: User,
) -> tuple[Ride, RideDestinationChange, bool]:
    """يطبّق العرضَ على الرحلة — و`applied=False` حين كان مؤكَّداً من قبل (التأكيدُ الثاني يردّ النتيجةَ نفسَها). الـcommit للراوتر."""
    # **الرحلةُ أوّلاً ثمّ صفُّ العرض** — ترتيبُ الأقفال (`CLAUDE.md`)، والإنهاءُ والإلغاءُ يقفلانها قبل أن يقرآ
    await session.refresh(ride, with_for_update=True)
    change = await _locked_change(session, ride, change_id)
    if change.status == CONFIRMED:
        return ride, change, False
    if change.status != QUOTED:
        raise QuoteNoLongerValid()
    if change.expires_at <= _now():
        change.status = EXPIRED
        change.decided_at = _now()
        await session.flush()
        raise QuoteNoLongerValid()
    phase = await _require_allowed(session, ride)
    # **عرضٌ على سعرٍ لم يعد قائماً لا يُطبَّق** — تغيّرت الأجرةُ أو الوجهةُ أو الطورُ منذ حُسب
    if (
        phase != change.phase
        or ride.estimated_fare != change.old_fare
        or (round(ride.dropoff_lat, 6), round(ride.dropoff_lng, 6)) != (round(change.old_lat, 6), round(change.old_lng, 6))
    ):
        change.status = EXPIRED
        change.decided_at = _now()
        await session.flush()
        raise QuoteNoLongerValid()

    before = {
        "dropoff_address": ride.dropoff_address,
        "dropoff": [ride.dropoff_lat, ride.dropoff_lng],
        "estimated_fare": str(ride.estimated_fare),
    }
    ride.dropoff_point = make_point(change.new_lat, change.new_lng)
    ride.dropoff_address = change.new_address
    ride.distance_km = change.new_distance_km
    ride.duration_min = change.new_duration_min
    ride.estimated_fare = change.new_fare
    ride.fare_lines = change.new_fare_lines
    ride.captain_fees_at_ride = change.new_captain_fees
    ride.facility_id = change.new_facility_id
    # **المسارُ يُعاد للاثنين** (§١٠٩-أ/٥) — يُمحى فيرسمه `route_line.ensure` من جديد، وأثناء الرحلة من موضع الكبتن الآن
    ride.route_polyline = None
    ride.route_steps = None
    change.status = CONFIRMED
    change.decided_at = _now()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="ride",
        entity_id=ride.id,
        details={"destination_change": str(change.id), "phase": change.phase},
        changes={
            "dropoff_address": {"old": before["dropoff_address"], "new": change.new_address},
            "dropoff": {"old": before["dropoff"], "new": [change.new_lat, change.new_lng]},
            "estimated_fare": {"old": before["estimated_fare"], "new": str(change.new_fare)},
        },
    )
    await session.flush()
    if ride.status == RideStatus.IN_PROGRESS:
        await _redraw_from_driver(session, redis, ride, Coordinates(lat=change.new_lat, lng=change.new_lng))
    # **الإحداثيّاتُ الأربعُ محسوبةٌ من عمودَي النقطة** — والـflush يُبطلها كلَّها (و`updated_at` يكتبه الخادم)، فتُقرأ من القاعدة
    # الآن لا عند البثّ: بعد الإيداع لا قراءةَ كسولةَ في جلسةٍ غير متزامنة
    await session.refresh(
        ride, attribute_names=["pickup_lat", "pickup_lng", "dropoff_lat", "dropoff_lng", "updated_at"]
    )
    return ride, change, True


async def _redraw_from_driver(session: AsyncSession, redis: Redis, ride: Ride, target: Coordinates) -> None:
    """**المسارُ من موضع الكبتن الآن إلى الوجهة الجديدة** — بلا خصمٍ من سقف إعادة التوجيه: لم ينحرف أحد. وفشلُه لا يُسقط التأكيد."""
    if ride.driver_id is None:
        return
    position = await geo.last_position(redis, driver_id=ride.driver_id, country_code=ride.country_code)
    if position is None:
        return
    try:
        drawn = await directions.route_between(
            session,
            Coordinates(lat=position.lat, lng=position.lng),
            target,
            country_code=ride.country_code,
            with_geometry=True,
        )
    except AppError as exc:
        logger.warning("تعذّر رسمُ مسار الوجهة الجديدة للرحلة %s: %s", ride.id, exc.code)
        return
    if drawn.geometry is not None:
        ride.route_polyline = json.dumps(drawn.geometry, separators=(",", ":"))
        await session.flush()


async def decline(session: AsyncSession, *, ride: Ride, change_id: uuid.UUID) -> RideDestinationChange:
    """**الرفضُ لا يمسّ الرحلة** — يُكتب في تاريخها وحدَه. ورفضُ ما أُكِّد أو انقضى لا يغيّر حالَه."""
    await session.refresh(ride, with_for_update=True)
    change = await _locked_change(session, ride, change_id)
    if change.status == QUOTED:
        change.status = DECLINED
        change.decided_at = _now()
        await session.flush()
    return change


async def has_confirmed(session: AsyncSession, ride_id: uuid.UUID) -> bool:
    """أأكّد الراكبُ وجهةً جديدةً لهذه الرحلة؟ — **فأجرتُها مجمَّدةٌ على ما أكّده** (`rides._final_fare`)."""
    return bool(
        await session.scalar(
            select(
                exists().where(
                    RideDestinationChange.ride_id == ride_id,
                    RideDestinationChange.status == CONFIRMED,
                )
            )
        )
    )


async def history(session: AsyncSession, ride_id: uuid.UUID) -> list[RideDestinationChange]:
    """تاريخُ العروض بترتيبها — ما عُرض وما أُكِّد وما رُفض وما انقضى."""
    rows = (
        await session.scalars(
            select(RideDestinationChange)
            .where(RideDestinationChange.ride_id == ride_id)
            .order_by(RideDestinationChange.created_at)
        )
    ).all()
    return list(rows)


def effective_status(row: RideDestinationChange, now: datetime | None = None) -> str:
    """**المنقضي يُقرأ منقضياً** ولو لم يُكتب — قراءةٌ لا كتابة (لا يُمسّ الصفُّ في جلسةٍ قد تُفرَغ)."""
    if row.status == QUOTED and row.expires_at <= (now or _now()):
        return EXPIRED
    return row.status
