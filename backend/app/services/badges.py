"""الشارات — **تقديرٌ إنسانيٌّ بيد المشرف** (البند ٥٣، §٤).

**ولا تدخل الشاراتُ ترتيبَ التوزيع بحال**، وهذا الملفُّ هو موضعُ الحراسة: لا
دالّةَ هنا يستدعيها `dispatch`، ولا عمودَ على `drivers` يُقرأ في مسار العرض.
المستوى مقيسٌ من عملٍ منجز، والشارةُ تقدير — وجعلُ التقدير يزيد الطلباتِ يجعل
المشرفَ **يوزّع المال بيده**.

**والمنحُ والسحبُ يكتبان قيدَ تدقيق** كأي كتابةٍ إدارية، و`note` سببٌ مكتوب — وهو
استثناءُ «السببِ المكتوب» نفسُه الذي في تعليق الكبتن: قيدُ التدقيق لا يحمل القيمَ
عادةً، وهذه قيمتُها **هي** الغرضُ من القيد.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.badge import Badge, DriverBadge
from app.models.driver import Driver
from app.models.enums import AuditAction
from app.models.user import User
from app.services import audit


class BadgeNotFound(NotFound):
    code = "badge_not_found"
    message = "الشارة غير موجودة"


class BadgeAlreadyGranted(Conflict):
    code = "badge_already_granted"
    message = "الشارة ممنوحةٌ لهذا الكبتن"


async def list_badges(
    session: AsyncSession, *, active_only: bool = False
) -> list[Badge]:
    stmt = select(Badge).order_by(Badge.label)
    if active_only:
        stmt = stmt.where(Badge.is_active.is_(True))
    return list((await session.scalars(stmt)).all())


async def create_badge(
    session: AsyncSession,
    *,
    key: str,
    label: str,
    description: str | None = None,
    icon: str | None = None,
) -> Badge:
    badge = Badge(
        key=key.strip().lower(),
        label=label.strip(),
        description=description,
        icon=icon,
    )
    session.add(badge)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("مفتاح الشارة مستعمل") from exc
    return badge


async def for_driver(
    session: AsyncSession, driver_id: uuid.UUID
) -> list[tuple[DriverBadge, Badge]]:
    """شاراتُ كبتنٍ مع تعريفها — **ضمٌّ واحدٌ لا استعلامٌ لكلٍّ**."""
    rows = await session.execute(
        select(DriverBadge, Badge)
        .join(Badge, Badge.id == DriverBadge.badge_id)
        .where(DriverBadge.driver_id == driver_id)
        .order_by(DriverBadge.granted_at.desc())
    )
    return [(granted, badge) for granted, badge in rows.all()]


async def grant(
    session: AsyncSession,
    *,
    driver_id: uuid.UUID,
    badge_id: uuid.UUID,
    actor: User,
    note: str,
) -> DriverBadge:
    """يمنح شارةً **بسببٍ مكتوب**. الـcommit للمستدعي.

    **والسببُ شرطٌ لا حقلٌ اختياري**: شارةٌ بلا سببٍ تُقرأ بعد شهرٍ فلا يعرف
    أحدٌ لماذا مُنحت ولا هل تُسحب — وهي القيمةُ الوحيدةُ التي يحملها قيدُ
    التدقيق هنا، فبغيرها يسجّل القيدُ أن شيئاً حدث ولا يقول ماذا.
    """
    if not note.strip():
        raise InvalidInput("سبب منح الشارة مطلوب")

    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise NotFound("الكبتن غير موجود")
    badge = await session.get(Badge, badge_id)
    if badge is None:
        raise BadgeNotFound()

    row = DriverBadge(
        driver_id=driver_id,
        badge_id=badge_id,
        granted_by=actor.id,
        note=note.strip(),
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise BadgeAlreadyGranted() from exc

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.CREATE,
        entity_type="driver_badge",
        entity_id=row.id,
        details={"driver_id": str(driver_id), "badge": badge.key, "note": note.strip()},
    )
    return row


async def revoke(
    session: AsyncSession,
    *,
    driver_id: uuid.UUID,
    badge_id: uuid.UUID,
    actor: User,
    reason: str,
) -> None:
    """يسحب شارةً **بسببٍ مكتوب** — والسحبُ حدثٌ يُسجَّل كالمنح.

    **ويُحذف الصفُّ ولا يُوسَم مسحوباً**: الشارةُ إمّا معروضةٌ أو لا، وعمودُ
    `revoked_at` كان سيجعل «هل يحملها؟» سؤالاً يُجاب من مكانين. والأثرُ الباقي
    قيدُ التدقيق — وهو موضعُ التاريخ في هذا المشروع كلِّه.
    """
    if not reason.strip():
        raise InvalidInput("سبب سحب الشارة مطلوب")

    row = await session.scalar(
        select(DriverBadge).where(
            DriverBadge.driver_id == driver_id, DriverBadge.badge_id == badge_id
        )
    )
    if row is None:
        raise BadgeNotFound()

    badge = await session.get(Badge, badge_id)
    await session.delete(row)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.DELETE,
        entity_type="driver_badge",
        entity_id=row.id,
        details={
            "driver_id": str(driver_id),
            "badge": badge.key if badge else str(badge_id),
            "reason": reason.strip(),
        },
    )
