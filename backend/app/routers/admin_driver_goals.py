"""**أهدافُ الكبتن بمكافأة** في اللوحة (البند ١٦، §٩٧/١٦) — المبالغُ يضعها المالك، **والإنشاءُ والإيقافُ مدقَّقان**."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.driver_goal import DriverGoal
from app.models.enums import AuditAction, CountryCode
from app.schemas.driver_goal import DriverGoalIn, DriverGoalOut, DriverGoalPatch
from app.services import audit, driver_goals

router = APIRouter(prefix="/admin/driver-goals", tags=["admin-driver-goals"])


async def _out(session, goal: DriverGoal) -> DriverGoalOut:
    total, count = await driver_goals.spent(session, goal.id)
    return DriverGoalOut(
        id=goal.id, country_code=goal.country_code, title=goal.title, description=goal.description, target=goal.target,
        starts_at=goal.starts_at, ends_at=goal.ends_at, reward_amount=goal.reward_amount, budget_cap=goal.budget_cap,
        is_active=goal.is_active, spent=total, awards=count,
    )


@router.get("", response_model=list[DriverGoalOut])
async def list_goals(_staff: StaffUser, session: DbSession, country_code: CountryCode = Query()) -> list[DriverGoalOut]:
    rows = await session.scalars(
        select(DriverGoal).where(DriverGoal.country_code == country_code).order_by(DriverGoal.starts_at.desc()).limit(100)
    )
    return [await _out(session, goal) for goal in rows]


@router.post("", response_model=DriverGoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal(payload: DriverGoalIn, admin: SettingsWriter, session: DbSession, country_code: CountryCode = Query()) -> DriverGoalOut:
    goal = await driver_goals.create(session, country=country_code, actor=admin, data=payload.model_dump())
    await audit.record(
        session, actor=admin, action=AuditAction.CREATE, entity_type="driver_goal", entity_id=goal.id,
        details={"country_code": country_code.value, "target": goal.target, "reward_amount": str(goal.reward_amount),
                 "budget_cap": str(goal.budget_cap)},
    )
    await session.commit()
    return await _out(session, goal)


@router.patch("/{goal_id}", response_model=DriverGoalOut)
async def update_goal(goal_id: uuid.UUID, payload: DriverGoalPatch, admin: SettingsWriter, session: DbSession) -> DriverGoalOut:
    goal = await driver_goals.locked(session, goal_id)
    changes = audit.apply_changes(goal, payload.model_dump(exclude_unset=True))
    await audit.record(
        session, actor=admin, action=AuditAction.UPDATE, entity_type="driver_goal", entity_id=goal.id, changes=changes,
    )
    await session.commit()
    return await _out(session, goal)
