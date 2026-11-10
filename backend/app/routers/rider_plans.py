"""**اشتراكُ الراكب** من التطبيق (البند ١٣، §٩٧/١٣) — الخططُ والاشتراكُ الحاليّ والشراءُ من المحفظة."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status

from app.core.currency import currency_for_country
from app.core.deps import DbSession, RiderUser
from app.models.rider_plan import RiderPlan
from app.schemas.rider_plan import MyPlanOut, MyPlansOut, RiderPlanOut
from app.services import pricing, rider_plans

router = APIRouter(prefix="/rider-plans", tags=["rider-plans"])


def _plan(plan: RiderPlan) -> RiderPlanOut:
    return RiderPlanOut.model_validate(plan, from_attributes=True)


async def _mine(session, rider) -> MyPlansOut:
    on = await rider_plans.enabled(session, rider.country_code)
    now = datetime.now(UTC)
    sub = await rider_plans.current(session, rider.id, now)
    current = None
    if sub is not None:
        plan = await session.get(RiderPlan, sub.plan_id)
        left = sub.monthly_cap - await rider_plans.used(session, sub.id, rider_plans.month_start(sub, now))
        current = MyPlanOut(
            plan_name=plan.name if plan else "",
            starts_at=sub.starts_at,
            ends_at=sub.ends_at,
            discount_percent=sub.discount_percent,
            per_ride_cap=sub.per_ride_cap,
            monthly_cap=sub.monthly_cap,
            saved=pricing.as_money(await rider_plans.used(session, sub.id)),
            month_left=pricing.as_money(max(left, 0)),
            can_renew=on and sub.ends_at - now <= rider_plans.RENEW_WINDOW,
        )
    plans = await rider_plans.plans_for(session, rider.country_code, active_only=True) if on else []
    return MyPlansOut(
        enabled=on, currency=str(currency_for_country(rider.country_code)), plans=[_plan(p) for p in plans], current=current
    )


@router.get("", response_model=MyPlansOut)
async def my_plans(rider: RiderUser, session: DbSession) -> MyPlansOut:
    return await _mine(session, rider)


@router.post("/{plan_id}/subscribe", response_model=MyPlansOut, status_code=status.HTTP_201_CREATED)
async def subscribe(plan_id: uuid.UUID, rider: RiderUser, session: DbSession) -> MyPlansOut:
    await rider_plans.purchase(session, rider=rider, plan_id=plan_id)
    await session.commit()
    return await _mine(session, rider)
