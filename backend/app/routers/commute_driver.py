"""أبوابُ الكبتن لاشتراك المشوار الثابت (SPEC §٦٣-ج/٦) — العروضُ واعتمادُه واعتذارُه. **`router` واحدٌ** (انظر `commute.py`)."""


from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.core.currency import currency_for_country
from app.core.deps import CurrentDriver, DbSession
from app.core.exceptions import NotFound
from app.models.rider_subscription import RiderSubscription
from app.models.user import User
from app.schemas.commute import CommuteOfferOut
from app.services import commute

router = APIRouter(prefix="/drivers/me", tags=["commutes"])


def _offer(row: RiderSubscription) -> CommuteOfferOut:
    return CommuteOfferOut(
        id=row.id,
        pickup_address=row.pickup_address,
        dropoff_address=row.dropoff_address,
        weekdays=row.weekdays,
        go_time=row.go_time,
        return_time=row.return_time,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        price_per_ride=row.price_per_ride,
        rides_total=row.rides_total,
        currency=currency_for_country(row.country_code),
        approved=row.driver_id is not None,
    )


@router.get("/commute-offers", response_model=list[CommuteOfferOut])
async def commute_offers(driver: CurrentDriver, session: DbSession) -> list[CommuteOfferOut]:
    user = await session.get(User, driver.user_id)
    if user is None:
        raise NotFound()
    return [_offer(row) for row in await commute.open_offers(session, driver=driver, user=user)]


@router.get("/commutes", response_model=list[CommuteOfferOut])
async def my_driver_commutes(driver: CurrentDriver, session: DbSession) -> list[CommuteOfferOut]:
    rows = await session.scalars(
        select(RiderSubscription).where(RiderSubscription.driver_id == driver.id, RiderSubscription.status == "active")
    )
    return [_offer(row) for row in rows]


@router.post("/commutes/{subscription_id}/approve", response_model=CommuteOfferOut)
async def approve_commute(subscription_id: uuid.UUID, driver: CurrentDriver, session: DbSession) -> CommuteOfferOut:
    row = await commute.approve(session, subscription_id=subscription_id, driver=driver)
    out = _offer(row)
    await session.commit()
    return out


@router.post("/commutes/{subscription_id}/release", response_model=CommuteOfferOut)
async def leave_commute(subscription_id: uuid.UUID, driver: CurrentDriver, session: DbSession) -> CommuteOfferOut:
    row = await commute.release(session, subscription_id=subscription_id, driver=driver)
    out = _offer(row)
    await session.commit()
    return out
