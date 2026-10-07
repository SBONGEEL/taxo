"""أبوابُ الكبتن للحجز المضمون (SPEC §٦٣-ج/٣) — العروضُ والقبولُ والتأكيدُ والاعتذار.

**والإشعاراتُ بعد الـcommit** كما في القبول: إعلامُ الراكب بكبتنه، وإعلامُه حين يعود حجزُه مفتوحاً.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.core.currency import currency_for_country
from app.core.deps import CurrentDriver, DbSession, RedisDep
from app.models.booking import RideBooking
from app.models.user import User
from app.schemas.guarantee import GuaranteeCancelCostOut, GuaranteeOfferOut
from app.schemas.ride import RideOut
from app.services import approach, dispatch, guarantees, notifications
from app.services import rides as rides_service
from app.ws import events

router = APIRouter(prefix="/drivers/me", tags=["guarantees"])


def _offer(row: RideBooking) -> GuaranteeOfferOut:
    return GuaranteeOfferOut(
        id=row.id,
        scheduled_at=row.scheduled_at,
        vehicle_category=row.vehicle_category,
        pickup_lat=row.pickup_lat,
        pickup_lng=row.pickup_lng,
        pickup_address=row.pickup_address,
        dropoff_lat=row.dropoff_lat,
        dropoff_lng=row.dropoff_lng,
        dropoff_address=row.dropoff_address,
        estimated_fare_at_booking=row.estimated_fare_at_booking,
        guarantee_fee=row.guarantee_fee_at_booking,
        currency=currency_for_country(row.country_code),
        accepted=row.driver_id is not None,
        confirm_requested=row.confirm_requested_at is not None,
    )


async def _user(session, driver) -> User:
    user = await session.get(User, driver.user_id)
    assert user is not None
    return user


@router.get("/guarantee-offers", response_model=list[GuaranteeOfferOut])
async def guarantee_offers(driver: CurrentDriver, session: DbSession) -> list[GuaranteeOfferOut]:
    """«عروضٌ تنتظرك» — حجوزٌ مضمونةٌ بلا كبتنٍ في نافذة العرض. **وفارغةٌ لمن حُجب أو حيث الخدمةُ مطفأة.**"""
    rows = await guarantees.open_offers(session, driver=driver, user=await _user(session, driver))
    return [_offer(row) for row in rows]


@router.get("/guarantees", response_model=list[GuaranteeOfferOut])
async def my_guarantees(driver: CurrentDriver, session: DbSession) -> list[GuaranteeOfferOut]:
    """ما قبله ولم يُنفَّذ بعد — «القادمة»."""
    rows = await session.scalars(
        select(RideBooking)
        .where(RideBooking.driver_id == driver.id, RideBooking.guaranteed.is_(True))
        .where(RideBooking.status == "pending")
        .order_by(RideBooking.scheduled_at)
    )
    return [_offer(row) for row in rows]


@router.post("/guarantees/{booking_id}/accept", response_model=GuaranteeOfferOut)
async def accept_guarantee(
    booking_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> GuaranteeOfferOut:
    user = await _user(session, driver)
    booking = await guarantees.accept(session, booking_id=booking_id, driver=driver, user=user)
    out = _offer(booking)
    rider_id = booking.rider_id
    await session.commit()
    await notifications.publish_guarantee_accepted(
        session, redis, rider_id=rider_id, booking_id=booking_id, captain_name=user.name
    )
    return out


@router.post("/guarantees/{booking_id}/withdraw", response_model=GuaranteeOfferOut)
async def withdraw_guarantee(
    booking_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> GuaranteeOfferOut:
    """**قبل التأكيد بلا أثر** — وبعده تُلغى الرحلةُ من بابها (`/rides/{id}/cancel`) فتقع العقوبة هناك."""
    await guarantees.withdraw(session, booking_id=booking_id, driver=driver)
    booking = await session.get(RideBooking, booking_id)
    assert booking is not None
    out = _offer(booking)
    rider_id = booking.rider_id
    await session.commit()
    await notifications.publish_guarantee_reopened(session, redis, rider_id=rider_id, booking_id=booking_id)
    return out


@router.get("/rides/{ride_id}/guarantee-cost", response_model=GuaranteeCancelCostOut)
async def guarantee_cancel_cost(ride_id: uuid.UUID, driver: CurrentDriver, session: DbSession) -> GuaranteeCancelCostOut:
    """**ورقةُ الإلغاء تقول الثمنَ قبل «تأكيد الإلغاء»** — رحلةٌ مضمونةٌ أكّدها ⇒ رسمُها من محفظته إلى الراكب، وإنذار."""
    booking, row, country = await guarantees.cancel_cost(session, ride_id=ride_id, driver=driver)
    return GuaranteeCancelCostOut(
        cancel_penalty=booking.guarantee_fee_at_booking if booking is not None else None,
        currency=currency_for_country(country),
        ban_threshold=row.guarantee_ban_threshold if row is not None else 2,
        ban_days=row.guarantee_ban_days if row is not None else 30,
    )


@router.post("/guarantees/{booking_id}/confirm", response_model=RideOut)
async def confirm_guarantee(
    booking_id: uuid.UUID, driver: CurrentDriver, session: DbSession, redis: RedisDep
) -> RideOut:
    """**«نعم، في الطريق»** — الرحلةُ تُنشأ مسنَدةً إليه، ويُعلَم الراكبُ كما يُعلَم بالقبول."""
    ride = await guarantees.confirm(session, booking_id=booking_id, driver=driver)
    out = RideOut.from_ride(ride)
    await session.commit()
    await dispatch.release_offer(redis, ride.id, driver.id)
    await notifications.publish_ride_event(session, redis, ride, events.RideEvent.DRIVER_ASSIGNED)
    await approach.arm(
        redis,
        session,
        driver_id=driver.id,
        ride_id=out.id,
        country_code=out.country_code,
        pickup_lat=out.pickup.lat,
        pickup_lng=out.pickup.lng,
    )
    return out
