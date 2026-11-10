"""**تجاربُ الأسعار** في اللوحة (البند ٤، §٩٧/٤) — المالكُ ينشئ ويبدأ ويوقف ويقرّر، **وكلُّ خطوةٍ مدقَّقة**.

**والتطبيقُ كتابةٌ على التسعيرة** فيمرّ بحارسها (`money_guards.require_pricing_writes`) كتعديلها باليد.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.enums import AuditAction, CountryCode, PriceExperimentStatus
from app.models.price_experiment import PriceExperiment
from app.schemas.price_experiment import ArmStatsOut, PriceExperimentIn, PriceExperimentOut
from app.services import audit, money_guards, price_experiments

router = APIRouter(prefix="/admin/price-experiments", tags=["admin-price-experiments"])


async def _out(session, experiment: PriceExperiment) -> PriceExperimentOut:
    arms = await price_experiments.compare(session, experiment)
    now = datetime.now(UTC)
    return PriceExperimentOut(
        id=experiment.id, country_code=experiment.country_code, name=experiment.name, adjust_percent=experiment.adjust_percent,
        share_percent=experiment.share_percent, days=experiment.days, center_lat=experiment.center_lat,
        center_lng=experiment.center_lng, radius_km=experiment.radius_km, status=experiment.status,
        started_at=experiment.started_at, ends_at=experiment.ends_at, stopped_at=experiment.stopped_at,
        decided_at=experiment.decided_at,
        expired=experiment.status == PriceExperimentStatus.RUNNING.value and experiment.ends_at is not None and experiment.ends_at <= now,
        can_apply=experiment.radius_km is None
        and experiment.status in (PriceExperimentStatus.RUNNING.value, PriceExperimentStatus.STOPPED.value),
        arms=[ArmStatsOut(**dataclasses.asdict(arm)) for arm in arms],
    )


@router.get("", response_model=list[PriceExperimentOut])
async def list_experiments(_staff: StaffUser, session: DbSession, country_code: CountryCode = Query()) -> list[PriceExperimentOut]:
    rows = await session.scalars(
        select(PriceExperiment)
        .where(PriceExperiment.country_code == country_code)
        .order_by(PriceExperiment.created_at.desc())
        .limit(50)
    )
    return [await _out(session, experiment) for experiment in rows]


@router.post("", response_model=PriceExperimentOut, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    payload: PriceExperimentIn, admin: SettingsWriter, session: DbSession, country_code: CountryCode = Query()
) -> PriceExperimentOut:
    experiment = await price_experiments.create(session, country=country_code, actor=admin, data=payload.model_dump())
    await audit.record(
        session, actor=admin, action=AuditAction.CREATE, entity_type="price_experiment", entity_id=experiment.id,
        details={"country_code": country_code.value, "adjust_percent": str(experiment.adjust_percent),
                 "share_percent": experiment.share_percent, "days": experiment.days,
                 "area": None if experiment.radius_km is None else str(experiment.radius_km)},
    )
    await session.commit()
    return await _out(session, experiment)


@router.post("/{experiment_id}/{action}", response_model=PriceExperimentOut)
async def move_experiment(experiment_id: uuid.UUID, action: str, admin: SettingsWriter, session: DbSession) -> PriceExperimentOut:
    if action not in ("start", "stop", "apply", "cancel"):
        from app.core.exceptions import NotFound

        raise NotFound("لا فعلَ بهذا الاسم")
    if action == "apply":
        current = await session.get(PriceExperiment, experiment_id)
        if current is not None:
            await money_guards.require_pricing_writes(session, actor=admin, country_code=current.country_code, entity_id=current.id)
    experiment, changes = await price_experiments.move(session, experiment_id, action)
    await audit.record(
        session, actor=admin, action=AuditAction.UPDATE, entity_type="price_experiment", entity_id=experiment.id,
        details={"action": action, "status": experiment.status, **({"pricing": changes} if changes else {})},
    )
    await session.commit()
    return await _out(session, experiment)
