"""سجل الرحلات في اللوحة (SPEC القسم 13/4).

**قراءةٌ لا غير، ولـ`staff` كلِّه.** الدعمُ يعالج النزاعات (القسم 13/8)، ولا
يُعالَج نزاعٌ على رحلةٍ لا تُقرأ: «أين سار ومتى» و«كم دُفع وبأي قناة» هما
مادةُ الفصل نفسها. أما القرارُ فيقع على **الدفعة** في `admin_payments`، لا
هنا: `resolution` تصف واقعةً مالية، والرحلةُ سجلٌّ لما جرى.

**ولا زرَّ إسنادٍ يدوي**: الرحلة تُعرض على كبتنٍ واحدٍ في كل لحظة (القسم 5.4)،
وزرٌّ يتخطى العرض يُسند رحلةً إلى من لم يقبلها — البند مؤجَّلٌ في
`FUTURE-FEATURES` لا ناقصٌ هنا.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Query

from app.core.deps import DbSession, StaffUser
from app.core.exceptions import NotFound
from app.models.enums import CountryCode, RideStatus
from app.models.ride import Ride
from app.schemas.admin_ride import (
    AdminRideDetail,
    AdminRideRow,
    RideDriverPartyOut,
    RidePartyOut,
    RidePaymentOut,
    RidePointOut,
    RideRatingOut,
)
from app.services import ride_log

router = APIRouter(prefix="/admin/rides", tags=["admin"])


def _row(ride: Ride, summary: ride_log.PaymentSummary) -> AdminRideRow:
    return AdminRideRow(
        id=ride.id,
        status=ride.status,
        country_code=ride.country_code,
        vehicle_category=ride.vehicle_category,
        currency=ride.currency,
        rider=RidePartyOut(
            user_id=ride.rider.id, name=ride.rider.name, phone=ride.rider.phone
        ),
        driver=(
            None
            if ride.driver is None
            else RideDriverPartyOut(
                user_id=ride.driver.user.id,
                name=ride.driver.user.name,
                phone=ride.driver.user.phone,
                driver_id=ride.driver.id,
                plate_number=ride_log.plate_of(ride),
            )
        ),
        pickup_address=ride.pickup_address,
        dropoff_address=ride.dropoff_address,
        distance_km=ride.distance_km,
        actual_distance_km=ride.actual_distance_km,
        estimated_fare=ride.estimated_fare,
        final_fare=ride.final_fare,
        cancellation_fee=ride.cancellation_fee,
        payment_methods=summary.methods,
        paid_amount=summary.paid_amount,
        has_open_dispute=summary.has_open_dispute,
        created_at=ride.created_at,
        completed_at=ride.completed_at,
        cancelled_at=ride.cancelled_at,
    )


@router.get("", response_model=list[AdminRideRow])
async def list_rides(
    _staff: StaffUser,
    session: DbSession,
    country_code: CountryCode | None = None,
    ride_status: RideStatus | None = None,
    driver_id: uuid.UUID | None = None,
    rider_id: uuid.UUID | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    q: str | None = Query(
        default=None, max_length=120, description="اسمٌ أو رقمٌ أو معرّف رحلة"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminRideRow]:
    """صفحةٌ من السجل — وملخّصُ الدفع مجموعٌ في القاعدة لا في الواجهة."""
    rides = await ride_log.list_rides(
        session,
        country=country_code,
        status=ride_status,
        driver_id=driver_id,
        rider_id=rider_id,
        from_at=from_at,
        to_at=to_at,
        query=q,
        limit=limit,
        offset=offset,
    )
    summaries = await ride_log.payment_summaries(session, [ride.id for ride in rides])
    return [
        _row(ride, summaries.get(ride.id, ride_log.EMPTY_SUMMARY)) for ride in rides
    ]


@router.get("/{ride_id}", response_model=AdminRideDetail)
async def get_ride(
    ride_id: uuid.UUID, _staff: StaffUser, session: DbSession
) -> AdminRideDetail:
    """تفاصيلُ رحلةٍ ومعها **مسارها الفعلي** — دليلُ النزاع (القسم 5.7/13.4)."""
    ride = await ride_log.get_ride(session, ride_id)
    if ride is None:
        raise NotFound("الرحلة غير موجودة")

    summaries = await ride_log.payment_summaries(session, [ride.id])
    payments = await ride_log.payments_of(session, ride.id)
    ratings = await ride_log.ratings_of(session, ride.id)
    route, truncated = await ride_log.route_of(session, ride.id)

    return AdminRideDetail(
        **_row(ride, summaries.get(ride.id, ride_log.EMPTY_SUMMARY)).model_dump(),
        pickup_lat=ride.pickup_lat,
        pickup_lng=ride.pickup_lng,
        dropoff_lat=ride.dropoff_lat,
        dropoff_lng=ride.dropoff_lng,
        duration_min=ride.duration_min,
        commission_percent_at_ride=ride.commission_percent_at_ride,
        gender_preference=ride.gender_preference,
        cancelled_reason=ride.cancelled_reason,
        cancel_reason_code=ride.cancel_reason_code,
        accepted_at=ride.accepted_at,
        arrived_at=ride.arrived_at,
        started_at=ride.started_at,
        payments=[
            RidePaymentOut(
                id=payment.id,
                method=payment.method,
                status=payment.status,
                amount=payment.amount,
                dispute_reason=payment.dispute_reason,
                resolution=(
                    None if payment.resolution is None else payment.resolution.value
                ),
                created_at=payment.created_at,
            )
            for payment in payments
        ],
        ratings=[
            RideRatingOut(
                rater_type=rating.rater_type,
                stars=rating.stars,
                comment=rating.comment,
                created_at=rating.created_at,
            )
            for rating in ratings
        ],
        route=[
            RidePointOut(lat=point.lat, lng=point.lng, created_at=point.created_at)
            for point in route
        ],
        route_truncated=truncated,
    )
