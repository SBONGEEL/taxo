"""**خططُ اشتراك الركّاب** في اللوحة (البند ١٣، §٩٧/١٣) — المبالغُ يضعها المالك، **والإنشاءُ والإيقافُ مدقَّقان**.

**ولا تعديلَ لخطّةٍ بعد إنشائها إلا إيقافُها**: من اشترى اشترى شروطاً مجمَّدة، والخطّةُ الجديدةُ صفٌّ جديد.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.core.exceptions import NotFound
from app.models.enums import AuditAction, CountryCode
from app.models.rider_plan import RiderPlan, RiderPlanSubscription, RiderPlanUse
from app.schemas.rider_plan import RiderPlanAdminOut, RiderPlanIn, RiderPlanPatch
from app.services import audit, pricing, rider_plans

router = APIRouter(prefix="/admin/rider-plans", tags=["admin-rider-plans"])


async def _out(session, plan: RiderPlan) -> RiderPlanAdminOut:
    now = datetime.now(UTC)
    active = await session.scalar(
        select(func.count()).select_from(RiderPlanSubscription).where(
            RiderPlanSubscription.plan_id == plan.id, RiderPlanSubscription.starts_at <= now, RiderPlanSubscription.ends_at > now
        )
    )
    revenue = await session.scalar(
        select(func.coalesce(func.sum(RiderPlanSubscription.price_paid), 0)).where(RiderPlanSubscription.plan_id == plan.id)
    )
    discounts = await session.scalar(
        select(func.coalesce(func.sum(RiderPlanUse.amount), 0))
        .join(RiderPlanSubscription, RiderPlanUse.subscription_id == RiderPlanSubscription.id)
        .where(RiderPlanSubscription.plan_id == plan.id)
    )
    return RiderPlanAdminOut(
        id=plan.id, country_code=plan.country_code, name=plan.name, days=plan.days, price=plan.price,
        discount_percent=plan.discount_percent, per_ride_cap=plan.per_ride_cap, monthly_cap=plan.monthly_cap, terms=plan.terms,
        bearer=plan.bearer, is_active=plan.is_active, active_subscribers=active or 0,
        revenue=pricing.as_money(revenue), discounts=pricing.as_money(discounts),
    )


@router.get("", response_model=list[RiderPlanAdminOut])
async def list_plans(_staff: StaffUser, session: DbSession, country_code: CountryCode = Query()) -> list[RiderPlanAdminOut]:
    return [await _out(session, plan) for plan in await rider_plans.plans_for(session, country_code, active_only=False)]


@router.post("", response_model=RiderPlanAdminOut, status_code=status.HTTP_201_CREATED)
async def create_plan(payload: RiderPlanIn, admin: SettingsWriter, session: DbSession, country_code: CountryCode = Query()) -> RiderPlanAdminOut:
    plan = await rider_plans.create_plan(session, country=country_code, actor=admin, data=payload.model_dump())
    await audit.record(
        session, actor=admin, action=AuditAction.CREATE, entity_type="rider_plan", entity_id=plan.id,
        details={"country_code": country_code.value, "price": str(plan.price), "days": plan.days,
                 "discount_percent": str(plan.discount_percent), "per_ride_cap": str(plan.per_ride_cap),
                 "monthly_cap": str(plan.monthly_cap), "bearer": plan.bearer},
    )
    await session.commit()
    return await _out(session, plan)


@router.patch("/{plan_id}", response_model=RiderPlanAdminOut)
async def update_plan(plan_id: uuid.UUID, payload: RiderPlanPatch, admin: SettingsWriter, session: DbSession) -> RiderPlanAdminOut:
    plan = await session.get(RiderPlan, plan_id)
    if plan is None:
        raise NotFound("الخطّةُ غيرُ موجودة")
    changes = audit.apply_changes(plan, payload.model_dump())
    await audit.record(session, actor=admin, action=AuditAction.UPDATE, entity_type="rider_plan", entity_id=plan.id, changes=changes)
    await session.commit()
    return await _out(session, plan)
