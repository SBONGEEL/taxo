"""**الاعتمادُ الاستثنائيّ ومتابعةُ الوثائق** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١).

## الاعتماد
`approve` يعتمد الكبتنَ **وُجدت الوثائقُ أو لم توجد** — بصلاحيّة `drivers.exceptional` (حسّاسة: للمالك ومن يمنحه بالاسم)
**وسببٍ مكتوبٍ في التدقيق**. **والرقمُ المُثبَت باقٍ شرطاً** (`verification.require_verified`): أمرُ المالك عن الوثائق، والرقمُ هو ما
تصله عليه حوالاتُ كليك — اعتمادُ رقمٍ مجهولٍ إرسالُ مالٍ إليه.

ويُوسَم الحساب «معتمد دون وثائق» (`exceptional_approved_at`، يراه المشرفون وحدَهم)، **وتبدأ مهلةُ الرفع** من إعداد الدولة.

## ما بعده
* **«طلب الوثائق»** (`request_documents`) — إشعارٌ في الصندوق وPush بزرٍّ إلى شاشة الرفع، لفردٍ أو لكلِّ الموسومين.
* **التذكيرُ الدوريّ** (`sweep`) بتكرار الدولة (١ · ٣ · ٧ أيام)، **ويُطفأ لكلِّ شخص** (`set_followup`).
* **المهلة**: تذكيرٌ قبل انتهائها بثلاثة أيامٍ وبيوم، **ثمّ تجميدٌ آليٌّ** بسببٍ مكتوب؛ والمشرفُ يمدّها لكلِّ شخص.
* **«تجميد/إلغاء التجميد»** (`freeze`/`unfreeze`) — بسببٍ إلزاميٍّ مدقَّق ورسالةٍ واضحةٍ للكبتن. **وإلغاءُ تجميد الموسوم يعيده
  معتمداً استثنائيّاً** بلا شرط الوثائق؛ وغيرُه يمرّ بحارسَي الاعتماد العاديّ.
* **الرفعُ لا يُسقط اعتمادَه** (`documents.upload`) — يدخل المراجعةَ العاديّة وهو يعمل، **ويزول الوسمُ عند الاعتماد العاديّ**
  (`drivers.approve` ⇐ `clear`).

**والقفل**: كلُّ فعلٍ يكتب حالَ الكبتن يقفل صفَّه أوّلاً (`drivers.lock`) — ترتيبُ الأقفال: صفُّ الكبتن وحدَه.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput
from app.models.document_setting import (
    DEFAULT_DEADLINE_DAYS,
    DEFAULT_EXPIRY_NOTICE_DAYS,
    DEFAULT_REMINDER_DAYS,
    REMINDER_CHOICES,
    DocumentSetting,
)
from app.models.driver import Driver
from app.models.enums import AuditAction, CountryCode, DriverStatus
from app.models.user import User
from app.services import audit

MIN_REASON = 4
#: **أيامُ التذكير قبل انتهاء المهلة** — والمرحلةُ تُكتب (`deadline_warning_stage`) فلا يتكرّر تذكيرُ اليوم نفسِه
DEADLINE_WARNINGS: tuple[int, ...] = (3, 1)


def _now() -> datetime:
    return datetime.now(UTC)


def _reason(text: str | None, what: str) -> str:
    value = (text or "").strip()
    if len(value) < MIN_REASON:
        raise InvalidInput(f"{what} — اكتب السبب ({MIN_REASON} أحرف على الأقل)", field="reason")
    return value


# ------------------------------------------------------------------ الإعدادات


@dataclass(frozen=True, slots=True)
class Settings:
    deadline_days: int
    reminder_days: int
    expiry_notice_days: tuple[int, ...]


async def settings_for(session: AsyncSession, country: CountryCode) -> Settings:
    row = await session.get(DocumentSetting, country)
    if row is None:
        return Settings(DEFAULT_DEADLINE_DAYS, DEFAULT_REMINDER_DAYS, DEFAULT_EXPIRY_NOTICE_DAYS)
    notice = tuple(sorted({int(d) for d in row.expiry_notice_days if int(d) > 0}, reverse=True)) or DEFAULT_EXPIRY_NOTICE_DAYS
    return Settings(row.exceptional_deadline_days, row.exceptional_reminder_days, notice)


async def save_settings(
    session: AsyncSession,
    *,
    country: CountryCode,
    deadline_days: int,
    reminder_days: int,
    expiry_notice_days: list[int],
    actor: User,
) -> Settings:
    if not 1 <= deadline_days <= 180:
        raise InvalidInput("المهلةُ بين يومٍ و١٨٠ يوماً", field="exceptional_deadline_days")
    if reminder_days not in REMINDER_CHOICES:
        raise InvalidInput("التكرارُ يوميّ أو كلَّ ثلاثة أيام أو أسبوعيّ", field="exceptional_reminder_days")
    notice = sorted({int(d) for d in expiry_notice_days}, reverse=True)
    if not notice or len(notice) > 5 or any(not 1 <= d <= 120 for d in notice):
        raise InvalidInput("أيامُ التنبيه: من يومٍ إلى خمسة أيام، كلٌّ بين ١ و١٢٠", field="expiry_notice_days")
    row = await session.get(DocumentSetting, country, with_for_update=True)
    before = None if row is None else {
        "deadline": row.exceptional_deadline_days, "reminder": row.exceptional_reminder_days, "notice": list(row.expiry_notice_days)
    }
    if row is None:
        row = DocumentSetting(country_code=country)
        session.add(row)
    row.exceptional_deadline_days = deadline_days
    row.exceptional_reminder_days = reminder_days
    row.expiry_notice_days = notice
    row.updated_by = actor.id
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="document_settings",
        details={
            "country_code": country.value,
            "from": before,
            "to": {"deadline": deadline_days, "reminder": reminder_days, "notice": notice},
        },
    )
    await session.flush()
    return Settings(deadline_days, reminder_days, tuple(notice))


# ------------------------------------------------------------------ الاعتمادُ والتجميد


async def _country_of(session: AsyncSession, driver: Driver) -> CountryCode:
    owner = await session.get(User, driver.user_id)
    return owner.country_code


async def approve(session: AsyncSession, *, driver: Driver, actor: User, reason: str | None) -> Driver:
    from app.services import drivers as drivers_service
    from app.services import verification

    text = _reason(reason, "سببُ الاعتماد")
    owner = await session.get(User, driver.user_id)
    verification.require_verified(owner)
    await drivers_service.lock(session, driver)
    settings = await settings_for(session, owner.country_code)
    now = _now()
    driver.exceptional_approved_at = now
    driver.exceptional_approved_by = actor.id
    driver.exceptional_reason = text
    driver.documents_deadline_at = now + timedelta(days=settings.deadline_days)
    driver.document_reminders_enabled = True
    driver.document_reminded_at = None
    driver.deadline_warning_stage = 0
    await drivers_service.set_status(session, driver=driver, status=DriverStatus.APPROVED, actor=actor, reason=text)
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="driver_exceptional_approval",
        entity_id=driver.id,
        details={"reason": text, "deadline": driver.documents_deadline_at.isoformat()},
    )
    return driver


def clear(driver: Driver) -> None:
    """**الاعتمادُ العاديُّ يزيل الوسم** — يُنادى من `drivers.approve` بعد حارسيه."""
    driver.exceptional_approved_at = None
    driver.exceptional_approved_by = None
    driver.exceptional_reason = None
    driver.documents_deadline_at = None
    driver.document_reminded_at = None
    driver.deadline_warning_stage = 0


async def freeze(session: AsyncSession, *, driver: Driver, actor: User | None, reason: str | None, automatic: bool = False) -> Driver:
    from app.services import drivers as drivers_service

    text = reason.strip() if automatic and reason else _reason(reason, "سببُ التجميد")
    await drivers_service.lock(session, driver)
    if driver.status is DriverStatus.SUSPENDED:
        raise InvalidInput("الحسابُ مجمَّدٌ أصلاً")
    await drivers_service.set_status(session, driver=driver, status=DriverStatus.SUSPENDED, actor=actor, reason=text)
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="driver_freeze",
        entity_id=driver.id,
        details={"reason": text, "automatic": automatic},
    )
    return driver


async def unfreeze(session: AsyncSession, *, driver: Driver, actor: User, reason: str | None) -> Driver:
    from app.services import drivers as drivers_service

    text = _reason(reason, "سببُ إلغاء التجميد")
    await drivers_service.lock(session, driver)
    if driver.status is not DriverStatus.SUSPENDED:
        raise InvalidInput("الحسابُ ليس مجمَّداً")
    if driver.exceptional_approved_at is not None:
        # **الموسومُ يعود معتمداً استثنائيّاً** — ومهلتُه إن انقضت تُمدّ أسبوعاً كي لا يُجمَّد آليّاً في الدورة التالية
        if driver.documents_deadline_at is not None and driver.documents_deadline_at <= _now():
            driver.documents_deadline_at = _now() + timedelta(days=7)
            driver.deadline_warning_stage = 0
        await drivers_service.set_status(session, driver=driver, status=DriverStatus.APPROVED, actor=actor, reason=text)
    else:
        await drivers_service.approve(session, driver=driver, actor=actor)
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="driver_unfreeze",
        entity_id=driver.id,
        details={"reason": text},
    )
    return driver


async def set_followup(
    session: AsyncSession, *, driver: Driver, actor: User, reminders: bool | None, extend_days: int | None
) -> Driver:
    if driver.exceptional_approved_at is None:
        raise InvalidInput("هذا الحسابُ ليس «معتمداً دون وثائق»")
    changes: dict[str, object] = {}
    if reminders is not None:
        driver.document_reminders_enabled = reminders
        changes["reminders"] = reminders
    if extend_days is not None:
        if not 1 <= extend_days <= 90:
            raise InvalidInput("التمديدُ بين يومٍ و٩٠ يوماً", field="extend_days")
        base = max(driver.documents_deadline_at or _now(), _now())
        driver.documents_deadline_at = base + timedelta(days=extend_days)
        driver.deadline_warning_stage = 0
        changes["deadline"] = driver.documents_deadline_at.isoformat()
    await audit.record(
        session, actor=actor, action=AuditAction.UPDATE, entity_type="driver_document_followup", entity_id=driver.id, details=changes
    )
    await session.flush()
    return driver


async def flagged(session: AsyncSession, *, country: CountryCode | None = None) -> list[Driver]:
    stmt = select(Driver).where(Driver.exceptional_approved_at.is_not(None))
    if country is not None:
        stmt = stmt.join(User, User.id == Driver.user_id).where(User.country_code == country)
    return list((await session.scalars(stmt)).all())


async def request_documents(session: AsyncSession, redis: Redis, *, drivers: list[Driver], actor: User) -> int:
    from app.services import notifications

    sent = 0
    for driver in drivers:
        await notifications.publish_documents_requested(session, redis, user_id=driver.user_id, deadline=driver.documents_deadline_at)
        sent += 1
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="driver_documents_request",
        details={"count": sent, "driver_ids": [str(d.id) for d in drivers][:50]},
    )
    return sent


# ------------------------------------------------------------------ الدورةُ اليوميّة


async def sweep(session: AsyncSession, redis: Redis, *, now: datetime | None = None) -> dict[str, int]:
    """**التذكيرُ والمهلةُ والتجميدُ الآليّ** — مرّةً في اليوم؛ وكلُّ كبتنٍ يُلتزم وحدَه فعطلُ واحدٍ لا يوقف الباقين."""
    from app.services import documents, notifications

    now = now or _now()
    counts = {"reminded": 0, "warned": 0, "frozen": 0}
    for driver in await flagged(session):
        if driver.status is not DriverStatus.APPROVED:
            continue
        if not await documents.missing_required(session, driver.id):
            continue  # **رفع كلَّ شيء** — ينتظر المراجعةَ العاديّة، فلا تذكيرَ ولا تجميد
        country = await _country_of(session, driver)
        settings = await settings_for(session, country)
        deadline = driver.documents_deadline_at
        if deadline is not None and deadline <= now:
            await freeze(session, driver=driver, actor=None, reason=notifications.DEADLINE_FROZEN_REASON, automatic=True)
            await session.commit()
            await notifications.publish_account_frozen(
                session, redis, user_id=driver.user_id, reason=notifications.DEADLINE_FROZEN_REASON, documents=True
            )
            counts["frozen"] += 1
            continue
        if deadline is not None:
            days_left = (deadline - now).days
            # **عددُ العتبات التي عُبرت** لا أوّلُها — من بقي له نصفُ يومٍ عبر الاثنتين
            stage = sum(1 for d in DEADLINE_WARNINGS if days_left < d)
            if stage > driver.deadline_warning_stage:
                driver.deadline_warning_stage = stage
                await session.commit()
                await notifications.publish_documents_requested(session, redis, user_id=driver.user_id, deadline=deadline, urgent=True)
                counts["warned"] += 1
                continue
        if not driver.document_reminders_enabled:
            continue
        last = driver.document_reminded_at or driver.exceptional_approved_at
        if last is not None and now - last >= timedelta(days=settings.reminder_days) - timedelta(hours=1):
            driver.document_reminded_at = now
            await session.commit()
            await notifications.publish_documents_requested(session, redis, user_id=driver.user_id, deadline=deadline)
            counts["reminded"] += 1
    return counts


def is_exceptional(driver: Driver) -> bool:
    return driver.exceptional_approved_at is not None


__all__ = [
    "approve",
    "clear",
    "flagged",
    "freeze",
    "is_exceptional",
    "request_documents",
    "save_settings",
    "set_followup",
    "settings_for",
    "sweep",
    "unfreeze",
]

