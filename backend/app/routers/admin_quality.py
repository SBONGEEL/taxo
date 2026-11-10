"""**درجةُ جودة الكبتن في اللوحة** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٣) — الأوزانُ والمفتاحُ لكلِّ دولة، وتاريخُ كلِّ كبتن."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.core.deps import DbSession, RedisDep, SettingsWriter, StaffUser
from app.core.exceptions import NotFound
from app.models.driver import Driver
from app.models.enums import AuditAction, CountryCode
from app.models.quality import DriverQualityScore, QualitySetting
from app.models.user import User
from app.services import audit, quality

router = APIRouter(prefix="/admin/quality", tags=["admin"])


class QualitySettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_code: CountryCode
    enabled: bool
    w_acceptance: int
    w_cancellation: int
    w_rating: int
    w_complaints: int
    w_completed: int
    dispatch_bonus_m: int
    warn_below: int


class QualitySettingUpdate(BaseModel):
    enabled: bool | None = None
    w_acceptance: int | None = Field(default=None, ge=0, le=100)
    w_cancellation: int | None = Field(default=None, ge=0, le=100)
    w_rating: int | None = Field(default=None, ge=0, le=100)
    w_complaints: int | None = Field(default=None, ge=0, le=100)
    w_completed: int | None = Field(default=None, ge=0, le=100)
    dispatch_bonus_m: int | None = Field(default=None, ge=0, le=1000)
    warn_below: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def _not_all_zero(self) -> "QualitySettingUpdate":
        weights = [self.w_acceptance, self.w_cancellation, self.w_rating, self.w_complaints, self.w_completed]
        if all(value is not None for value in weights) and sum(weights) == 0:  # type: ignore[arg-type]
            raise ValueError("وزنٌ واحدٌ على الأقلّ فوق الصفر")
        return self


class QualityDayOut(BaseModel):
    day: date
    score: int


class DriverQualityOut(BaseModel):
    """الدرجةُ الآن (محسوبةً عند الطلب) ومكوّناتُها وأعدادُها، وتاريخُ آخر ٣٠ لقطةً يوميّة."""

    score: int
    enabled: bool
    parts: dict[str, float]
    counts: dict[str, float | int | None]
    history: list[QualityDayOut]


def _out(country: CountryCode, row: QualitySetting | None) -> QualitySettingOut:
    if row is not None:
        return QualitySettingOut.model_validate(row)
    d = quality.DEFAULTS
    return QualitySettingOut(
        country_code=country, enabled=d.enabled, w_acceptance=d.acceptance, w_cancellation=d.cancellation,
        w_rating=d.rating, w_complaints=d.complaints, w_completed=d.completed,
        dispatch_bonus_m=d.dispatch_bonus_m, warn_below=d.warn_below,
    )


@router.get("/settings", response_model=list[QualitySettingOut])
async def list_quality_settings(_staff: StaffUser, session: DbSession) -> list[QualitySettingOut]:
    """**كلُّ دولة** — والغائبةُ بالافتراضيّ (مطفأة)، فلا تُخترع لها صفّ."""
    rows = {row.country_code: row for row in (await session.scalars(select(QualitySetting))).all()}
    return [_out(country, rows.get(country)) for country in CountryCode]


@router.patch("/settings/{country_code}", response_model=QualitySettingOut)
async def update_quality_settings(
    country_code: CountryCode, payload: QualitySettingUpdate, admin: SettingsWriter, session: DbSession
) -> QualitySettingOut:
    """**المفتاحُ يحكم الأثرَ وحدَه** (الترتيبُ والإنذار) — والحسابُ اليوميُّ يجري في الحالين، فيُرى أثرُ الأوزان قبل الإشعال."""
    row = await session.scalar(
        select(QualitySetting).where(QualitySetting.country_code == country_code).with_for_update()
    )
    if row is None:
        row = QualitySetting(country_code=country_code)
        session.add(row)
        await session.flush()
        await session.refresh(row)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await session.flush()
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="quality_settings",
        entity_id=row.id,
        details=payload.model_dump(exclude_unset=True, mode="json"),
    )
    await session.commit()
    await session.refresh(row)
    return QualitySettingOut.model_validate(row)


async def driver_quality(session, redis, *, driver_id: uuid.UUID, country: CountryCode) -> DriverQualityOut:
    weights = await quality.settings_for(session, country)
    parts, counts = await quality.measure(session, redis, driver_id=driver_id)
    history = (
        await session.execute(
            select(DriverQualityScore.day, DriverQualityScore.score)
            .where(DriverQualityScore.driver_id == driver_id)
            .order_by(DriverQualityScore.day.desc())
            .limit(30)
        )
    ).all()
    return DriverQualityOut(
        score=quality.score_from(weights, parts),
        enabled=weights.enabled,
        parts=parts,
        counts=counts,
        history=[QualityDayOut(day=day, score=score) for day, score in reversed(history)],
    )


@router.get("/drivers/{driver_id}", response_model=DriverQualityOut)
async def admin_driver_quality(driver_id: uuid.UUID, _staff: StaffUser, session: DbSession, redis: RedisDep) -> DriverQualityOut:
    found = (
        await session.execute(select(User.country_code).join(Driver, Driver.user_id == User.id).where(Driver.id == driver_id))
    ).first()
    if found is None:
        raise NotFound("الكبتنُ غيرُ موجود")
    return await driver_quality(session, redis, driver_id=driver_id, country=found[0])
