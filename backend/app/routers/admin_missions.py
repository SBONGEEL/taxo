"""المهامُّ والمستوياتُ والشارات في اللوحة (البند ٥٣، §٦).

**والكتابةُ `admin` والقراءةُ للدعم**: مهمّةٌ شهريةٌ تُغيّر ترتيبَ التوزيع في
سوقٍ كامل قرارُ تشغيلٍ لا إجراءُ دعم، والسؤالُ «لماذا مستواي واحد؟» سؤالُ دعم.

**ولا زرَّ «ارفع مستوى هذا الكبتن»**: المستوى حكمٌ آليٌّ على أداءٍ مقيس، وزرٌّ
يرفعه بيدٍ يجعله محاباةً في **ترتيب التوزيع** — أي في المال. ومن أراد تقديراً
فبابُه الشارة، وهي لا تدخل التوزيع أصلاً. وهذا هو الفصلُ الذي وُجد الجدولان له.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import FleetManager, DbSession, StaffUser
from app.core.exceptions import NotFound
from app.models.badge import Badge
from app.models.driver import Driver
from app.models.mission import Mission
from app.models.enums import AuditAction, CountryCode, DriverStatus, FeatureKey
from app.models.user import User
from app.schemas.mission import (
    BadgeGrantIn,
    BadgeIn,
    BadgeOut,
    BadgeRevokeIn,
    GrantedBadgeOut,
    LevelOverviewOut,
    LevelSettingIn,
    LevelSettingOut,
    MissionIn,
    MissionOut,
    MissionPatch,
)
from app.services import audit
from app.services import deletion
from app.services import badges as badges_service
from app.services import missions as missions_service
from app.services import settings_service

router = APIRouter(prefix="/admin", tags=["admin"])


# ------------------------------------------------------------ المهامّ


@router.get("/missions", response_model=list[MissionOut])
async def list_missions(
    _staff: StaffUser,
    session: DbSession,
    country_code: CountryCode,
    month: date | None = Query(default=None),
) -> list[MissionOut]:
    rows = await missions_service.list_missions(
        session, country=country_code, month=month
    )
    return [MissionOut.model_validate(row, from_attributes=True) for row in rows]


@router.post("/missions", response_model=MissionOut, status_code=201)
async def create_mission(
    payload: MissionIn,
    admin: FleetManager,
    session: DbSession,
    country_code: CountryCode,
) -> MissionOut:
    mission = await missions_service.create_mission(
        session,
        country=country_code,
        month=payload.month,
        metric=payload.metric,
        target=payload.target,
        title=payload.title,
        description=payload.description,
        created_by=admin.id,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="mission",
        entity_id=mission.id,
        details={"country": country_code.value, "metric": payload.metric},
    )
    # **وإعادةُ التقييم فوريةٌ بعد كل تعديل** (§٣): وإلا عاش المستوى على تعريفٍ
    # لم يعد قائماً — وهو بعينه ما تمنعه قاعدةُ المقارنة الحيّة في الإحالة
    await missions_service.reevaluate(session, country_code)
    await session.commit()
    return MissionOut.model_validate(mission, from_attributes=True)


@router.patch("/missions/{mission_id}", response_model=MissionOut)
async def update_mission(
    mission_id: uuid.UUID,
    payload: MissionPatch,
    admin: FleetManager,
    session: DbSession,
) -> MissionOut:
    mission = await missions_service.update_mission(
        session,
        mission_id,
        title=payload.title,
        description=payload.description,
        target=payload.target,
        is_active=payload.is_active,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="mission",
        entity_id=mission.id,
        details={
            "fields": [
                name
                for name, value in (
                    ("title", payload.title),
                    ("description", payload.description),
                    ("target", payload.target),
                    ("is_active", payload.is_active),
                )
                if value is not None
            ]
        },
    )
    await missions_service.reevaluate(session, mission.country_code)
    await session.commit()
    return MissionOut.model_validate(mission, from_attributes=True)


@router.delete("/missions/{mission_id}", status_code=204)
async def delete_mission(
    mission_id: uuid.UUID, admin: FleetManager, session: DbSession
) -> None:
    """حذفُ مهمّةٍ **لم يبدأ شهرُها** (البند ٤، §39٫٤).

    **وما بدأ شهرُه يُطفأ لا يُحذف**: كباتنُ يعملون عليه الآن، **ومحوُه يمحو
    هدفاً سعَوا إليه**.
    """
    mission = await session.get(Mission, mission_id)
    if mission is None:
        raise NotFound("المهمّة غير موجودة")
    await deletion.mission_deletable(session, mission)
    # **لقطةٌ قبل الحذف** — فالمحذوفُ لا يُقرأ بعد حذفه
    before = audit.snapshot(mission, ("country_code", "month", "metric", "target", "title"))
    await session.delete(mission)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="mission",
        entity_id=mission_id,
        details={"deleted": before},
    )
    await session.commit()


@router.delete("/badges/{badge_id}", status_code=204)
async def delete_badge(
    badge_id: uuid.UUID, admin: FleetManager, session: DbSession
) -> None:
    """حذفُ شارةٍ **لم تُمنح لأحد** (البند ٤، §39٫٤).

    **ولا يُترك للمفتاح الأجنبيّ**: `CASCADE` على المنح **يمحوها معها صامتاً**
    — ومنحةٌ ممحوّةٌ تمحو خبراً عن إنسان.
    """
    badge = await session.get(Badge, badge_id)
    if badge is None:
        raise NotFound("الشارة غير موجودة")
    await deletion.badge_deletable(session, badge)
    before = audit.snapshot(badge, ("key", "label", "description", "icon"))
    await session.delete(badge)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="badge",
        entity_id=badge_id,
        details={"deleted": before},
    )
    await session.commit()


# ------------------------------------------------------------ المستويات


@router.get("/levels", response_model=LevelOverviewOut)
async def level_overview(
    _staff: StaffUser, session: DbSession, country_code: CountryCode
) -> LevelOverviewOut:
    """كم كبتناً في كل مستوى، ومتى حُسب — **مجموعٌ في القاعدة** (القسم 14)."""
    from app.models.mission import LevelSetting

    counts = await missions_service.level_counts(session, country_code)
    settings = list(
        (
            await session.scalars(
                select(LevelSetting)
                .where(LevelSetting.country_code == country_code)
                .order_by(LevelSetting.level)
            )
        ).all()
    )
    last = await session.scalar(
        select(func.max(Driver.level_computed_at))
        .join(User, User.id == Driver.user_id)
        .where(
            User.country_code == country_code,
            Driver.status == DriverStatus.APPROVED,
        )
    )
    return LevelOverviewOut(
        country_code=country_code,
        enabled=await settings_service.is_feature_enabled(
            session, country_code, FeatureKey.DRIVER_LEVELS_ENABLED
        ),
        counts=counts,
        settings=[
            LevelSettingOut.model_validate(row, from_attributes=True)
            for row in settings
        ],
        last_computed_at=last,
    )


@router.put("/levels/{level}", response_model=LevelSettingOut)
async def set_level_effect(
    level: int,
    payload: LevelSettingIn,
    admin: FleetManager,
    session: DbSession,
    country_code: CountryCode,
) -> LevelSettingOut:
    row = await missions_service.set_discount(
        session, country=country_code, level=level, meters=payload.discount_meters
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="level_settings",
        entity_id=row.id,
        details={"country": country_code.value, "level": level},
    )
    await session.commit()
    return LevelSettingOut.model_validate(row, from_attributes=True)


# ------------------------------------------------------------ الشارات


@router.get("/badges", response_model=list[BadgeOut])
async def list_badges(_staff: StaffUser, session: DbSession) -> list[BadgeOut]:
    return [
        BadgeOut.model_validate(row, from_attributes=True)
        for row in await badges_service.list_badges(session)
    ]


@router.post("/badges", response_model=BadgeOut, status_code=201)
async def create_badge(
    payload: BadgeIn, admin: FleetManager, session: DbSession
) -> BadgeOut:
    badge = await badges_service.create_badge(
        session,
        key=payload.key,
        label=payload.label,
        description=payload.description,
        icon=payload.icon,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="badge",
        entity_id=badge.id,
        details={"key": badge.key},
    )
    await session.commit()
    return BadgeOut.model_validate(badge, from_attributes=True)


@router.get("/drivers/{driver_id}/badges", response_model=list[GrantedBadgeOut])
async def driver_badges(
    driver_id: uuid.UUID, _staff: StaffUser, session: DbSession
) -> list[GrantedBadgeOut]:
    return [
        GrantedBadgeOut(
            badge=BadgeOut.model_validate(badge, from_attributes=True),
            granted_at=row.granted_at,
        )
        for row, badge in await badges_service.for_driver(session, driver_id)
    ]


@router.post("/drivers/{driver_id}/badges", status_code=201)
async def grant_badge(
    driver_id: uuid.UUID,
    payload: BadgeGrantIn,
    admin: FleetManager,
    session: DbSession,
) -> dict:
    await badges_service.grant(
        session,
        driver_id=driver_id,
        badge_id=payload.badge_id,
        actor=admin,
        note=payload.note,
    )
    await session.commit()
    return {"ok": True}


@router.post("/drivers/{driver_id}/badges/{badge_id}/revoke")
async def revoke_badge(
    driver_id: uuid.UUID,
    badge_id: uuid.UUID,
    payload: BadgeRevokeIn,
    admin: FleetManager,
    session: DbSession,
) -> dict:
    """**سحبٌ بـPOST لا DELETE**: السحبُ يحمل سبباً مكتوباً في جسمٍ، و`DELETE`
    بجسمٍ شكلٌ ترفضه بعضُ الوسائط بلا خطأٍ مفهوم — وسببٌ يضيع في الطريق يجعل
    قيدَ التدقيق يقول إن شيئاً حدث ولا يقول لماذا."""
    await badges_service.revoke(
        session,
        driver_id=driver_id,
        badge_id=badge_id,
        actor=admin,
        reason=payload.reason,
    )
    await session.commit()
    return {"ok": True}
