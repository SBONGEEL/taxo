"""**«نقاطي»** في تطبيق الراكب (البند ١٤، §٩٧/١٤) — الرصيدُ والمستوى والانتهاء، والاستبدالُ رصيداً."""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter

from app.core.deps import DbSession, RiderUser
from app.schemas.loyalty import LoyaltyOut, RedeemIn
from app.services import loyalty

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


@router.get("/me", response_model=LoyaltyOut)
async def my_points(rider: RiderUser, session: DbSession) -> LoyaltyOut:
    return LoyaltyOut(**dataclasses.asdict(await loyalty.standing(session, rider)))


@router.post("/me/redeem", response_model=LoyaltyOut)
async def redeem(payload: RedeemIn, rider: RiderUser, session: DbSession) -> LoyaltyOut:
    await loyalty.redeem(session, rider, payload.blocks)
    await session.commit()
    return LoyaltyOut(**dataclasses.asdict(await loyalty.standing(session, rider)))
