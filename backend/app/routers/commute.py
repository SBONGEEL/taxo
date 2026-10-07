"""أبوابُ الراكب لاشتراك المشوار الثابت (SPEC §٦٣-ج/٦) — يسعّر ويشتري ويعلّق ويلغي ويفكّ كبتنَه.

**`router` واحدٌ لكلِّ ملفّ** — `check:contract` يقرأ `@router` وأوّلَ `prefix` في الملفّ، وملفٌّ بموجّهين أخفى أبوابَ الكبتن عنه
(أمسكه وكيلُ الشاشات ٢٠٢٦-١٠-٠٧). وأبوابُ الكبتن في `commute_driver.py`.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.currency import currency_for_country
from app.core.deps import DbSession, RiderUser
from app.models.driver import Driver
from app.models.rider_subscription import RiderSubscription
from app.models.user import User
from app.schemas.commute import (
    CommuteOut,
    CommutePlanIn,
    CommuteQuoteOut,
    CommuteSuspendIn,
)
from app.services import commute
from app.services.directions import Coordinates

router = APIRouter(prefix="/me/commutes", tags=["commutes"])


def _plan(payload: CommutePlanIn) -> commute.Plan:
    return commute.Plan(
        pickup=Coordinates(lat=payload.pickup.lat, lng=payload.pickup.lng),
        dropoff=Coordinates(lat=payload.dropoff.lat, lng=payload.dropoff.lng),
        pickup_address=payload.pickup_address,
        dropoff_address=payload.dropoff_address,
        weekdays=payload.weekdays,
        go_time=payload.go_time,
        return_time=payload.return_time,
        starts_on=payload.starts_on,
    )


async def _out(session, row: RiderSubscription) -> CommuteOut:
    captain = None
    if row.driver_id is not None:
        captain = await session.scalar(
            select(User.name).join(Driver, Driver.user_id == User.id).where(Driver.id == row.driver_id)
        )
    return CommuteOut(
        id=row.id,
        status=row.status,
        pickup_address=row.pickup_address,
        dropoff_address=row.dropoff_address,
        weekdays=row.weekdays,
        go_time=row.go_time,
        return_time=row.return_time,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        discount_percent=row.discount_percent,
        price_per_ride=row.price_per_ride,
        rides_total=row.rides_total,
        rides_done=await commute.completed_rides(session, row.id),
        amount_paid=row.amount_paid,
        currency=currency_for_country(row.country_code),
        suspended_days=[date.fromisoformat(d) for d in row.suspended_days],
        captain_name=captain,
    )


@router.post("/quote", response_model=CommuteQuoteOut)
async def quote_commute(payload: CommutePlanIn, rider: RiderUser, session: DbSession) -> CommuteQuoteOut:
    priced = await commute.quote(session, rider=rider, plan=_plan(payload))
    return CommuteQuoteOut(
        discount_percent=priced.discount_percent,
        price_per_ride=priced.price_per_ride,
        rides_total=priced.rides_total,
        total=priced.total,
        ends_on=priced.ends_on,
        currency=currency_for_country(rider.country_code),
    )


@router.post("", response_model=CommuteOut, status_code=status.HTTP_201_CREATED)
async def buy_commute(payload: CommutePlanIn, rider: RiderUser, session: DbSession) -> CommuteOut:
    row = await commute.purchase(session, rider=rider, plan=_plan(payload))
    await session.commit()
    return await _out(session, row)


@router.get("", response_model=list[CommuteOut])
async def my_commutes(rider: RiderUser, session: DbSession) -> list[CommuteOut]:
    rows = await session.scalars(
        select(RiderSubscription).where(RiderSubscription.rider_id == rider.id).order_by(RiderSubscription.starts_on.desc())
    )
    return [await _out(session, row) for row in rows]


@router.post("/{subscription_id}/suspend", response_model=CommuteOut)
async def suspend_day(
    subscription_id: uuid.UUID, payload: CommuteSuspendIn, rider: RiderUser, session: DbSession
) -> CommuteOut:
    row = await commute.suspend(session, subscription_id=subscription_id, rider=rider, day=payload.day)
    await session.commit()
    return await _out(session, row)


@router.post("/{subscription_id}/cancel", response_model=CommuteOut)
async def cancel_commute(subscription_id: uuid.UUID, rider: RiderUser, session: DbSession) -> CommuteOut:
    """**الحجوزُ القادمةُ تُلغى، وما لم يُستعمل يعود رصيداً لا نقداً.**"""
    await commute.cancel(session, subscription_id=subscription_id, rider=rider)
    await session.commit()
    row = await session.get(RiderSubscription, subscription_id)
    assert row is not None
    return await _out(session, row)


@router.delete("/{subscription_id}/captain", response_model=CommuteOut)
async def release_captain(subscription_id: uuid.UUID, rider: RiderUser, session: DbSession) -> CommuteOut:
    """**الراكبُ يستبدل كبتنَه** — يفكّه فيعود المشوارُ مفتوحاً لغيره."""
    row = await commute.release(session, subscription_id=subscription_id, by_rider=rider)
    await session.commit()
    return await _out(session, row)
