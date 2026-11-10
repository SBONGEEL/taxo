"""**التذاكر** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٨ و٩) — الكاتبُ والقارئُ والحاكمُ في موضعٍ واحد.

* **الملكيّةُ أوّلاً** (لا IDOR): صاحبُ التذكرة يراها، **والكبتنُ يرى خيطَ المفقودات على رحلته وحدَه** — لا الشكوى عليه.
* **والرحلةُ لطرفيها** (`rides.get_ride_for_party`) و**سابقةٌ** (مكتملةٌ أو ملغاة) في ٣٠ يوماً.
* **لا أرقامَ هواتفَ بين الراكب والكبتن** في خيط المفقودات (`chat_filter`)، والمشرفُ مستثنى.
* **وتغييرُ الحال يقفل الصفَّ قبل فحص الانتقال** (`with_for_update`)، **والسببُ إلزاميٌّ للحسم**، ويُدقَّق ويُبلَّغ صاحبُها.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit, storage
from app.core.exceptions import Conflict, InvalidInput, NotFound, RateLimited
from app.models.enums import AuditAction, RideStatus
from app.models.support_ticket import (
    ACTIVE_STATUSES,
    COMPLAINT_CATEGORIES,
    TICKET_KINDS,
    SupportMessage,
    SupportTicket,
)
from app.models.user import User

RIDE_WINDOW_DAYS = 30
OPEN_PER_HOUR = 10
MESSAGES_PER_HOUR = 60
PHOTO_MAX_BYTES = 5 * 1024 * 1024
BODY_MAX = 2000
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_PAST = {RideStatus.COMPLETED, RideStatus.CANCELLED_BY_RIDER, RideStatus.CANCELLED_BY_DRIVER}


class TicketActive(Conflict):
    code = "support_ticket_active"
    message = "لك طلبٌ قائمٌ من هذا النوع على هذه الرحلة"


class TicketClosed(Conflict):
    code = "support_ticket_closed"
    message = "الطلبُ مغلق — افتح طلباً جديداً إن احتجت"


class TicketTransition(Conflict):
    code = "support_ticket_transition"
    message = "لا يُنقل الطلبُ من حاله إلى هذه"


_TRANSITIONS = {
    "open": {"in_review", "resolved", "rejected"},
    "in_review": {"resolved", "rejected"},
}


def _body(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise InvalidInput("اكتب رسالتك", field="body")
    if len(text) > BODY_MAX:
        raise InvalidInput("الرسالةُ أطولُ من ٢٠٠٠ حرف", field="body")
    return text


def _no_phone(text: str) -> None:
    from app.services import chat_filter

    violation = chat_filter.check(text)
    if violation is chat_filter.Violation.PHONE:
        raise InvalidInput("لا أرقامَ هواتفَ هنا — التواصلُ عبر التطبيق", field="body")
    if violation is chat_filter.Violation.LINK:
        raise InvalidInput("لا روابطَ هنا", field="body")


async def _limit(redis: Redis, bucket: str, per_hour: int) -> None:
    hit = await rate_limit.hit(redis, bucket, limit=per_hour, window_seconds=3600)
    if not hit.allowed:
        raise RateLimited(retry_after=hit.retry_after)


async def open_ticket(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User,
    app: str,
    kind: str,
    body: str,
    ride_id: uuid.UUID | None = None,
    category: str | None = None,
    photo=None,
) -> SupportTicket:
    from app.services import rides as rides_service

    if kind not in TICKET_KINDS:
        raise InvalidInput("نوعُ الطلب غيرُ معروف", field="kind")
    text = _body(body)
    against = None
    if kind == "complaint":
        if category not in COMPLAINT_CATEGORIES:
            raise InvalidInput("اختر فئةَ الشكوى", field="category")
    else:
        category = None
    if kind != "support" and ride_id is None:
        raise InvalidInput("اختر الرحلة", field="ride_id")
    if ride_id is not None:
        ride = await rides_service.get_ride_for_party(session, ride_id, user)
        driver_user_id = ride.driver.user_id if ride.driver is not None else None
        side_rider = ride.rider_id == user.id
        against = driver_user_id if side_rider else ride.rider_id
        if kind != "support":
            if ride.status not in _PAST:
                raise InvalidInput("هذا للرحلات المنتهية — والجاريةُ لها زرُّ الطوارئ والمحادثة", field="ride_id")
            if ride.created_at < datetime.now(UTC) - timedelta(days=RIDE_WINDOW_DAYS):
                raise InvalidInput("مضى على الرحلة أكثرُ من ٣٠ يوماً", field="ride_id")
        if kind == "lost_item":
            if not side_rider or driver_user_id is None:
                raise InvalidInput("«نسيت شيئاً» للراكب في رحلةٍ لها كبتن", field="kind")
            _no_phone(text)
    await _limit(redis, f"support:open:{user.id}", OPEN_PER_HOUR)

    ticket_id = uuid.uuid4()
    stored = None
    if photo is not None:
        stored = await storage.save(photo, folder=str(ticket_id), max_bytes=PHOTO_MAX_BYTES)
        if stored.content_type not in _IMAGE_TYPES:
            await storage.delete(stored.relative_path)
            raise InvalidInput("الصورةُ PNG أو JPEG أو WebP", field="photo")

    now = datetime.now(UTC)
    ticket = SupportTicket(
        id=ticket_id,
        user_id=user.id,
        country_code=user.country_code,
        app=app,
        kind=kind,
        ride_id=ride_id,
        against_user_id=against,
        category=category,
        status="open",
        needs_staff=True,
        photo_path=stored.relative_path if stored else None,
        photo_type=stored.content_type if stored else None,
        last_message_at=now,
    )
    session.add(ticket)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        if stored is not None:
            await storage.delete(stored.relative_path)
        raise TicketActive() from None
    session.add(SupportMessage(ticket_id=ticket.id, author_id=user.id, author_role="user", body=text))
    await session.flush()
    if kind == "lost_item" and against is not None:
        # **الكبتنُ يعرف فوراً** — ويردّ من الخيط نفسِه، بلا رقم
        from app.services import notifications

        await notifications.publish_support_event(session, redis, user_id=against, ticket=ticket, event="lost_item")
    return ticket


@dataclass(slots=True)
class Access:
    ticket: SupportTicket
    role: str  # user · party


async def for_member(session: AsyncSession, ticket_id: uuid.UUID, user: User, *, lock: bool = False) -> Access:
    """صاحبُها، **أو الكبتنُ في خيط المفقودات على رحلته** — وغيرُهما ٤٠٤ لا ٤٠٣ (لا يُكشف وجودُها)."""
    query = select(SupportTicket).where(SupportTicket.id == ticket_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    ticket = await session.scalar(query)
    if ticket is not None:
        if ticket.user_id == user.id:
            return Access(ticket, "user")
        if ticket.kind == "lost_item" and ticket.against_user_id == user.id:
            return Access(ticket, "party")
    raise NotFound("الطلبُ غيرُ موجود")


async def mine(session: AsyncSession, user: User) -> list[SupportTicket]:
    rows = await session.scalars(
        select(SupportTicket)
        .where(
            (SupportTicket.user_id == user.id)
            | ((SupportTicket.kind == "lost_item") & (SupportTicket.against_user_id == user.id))
        )
        .order_by(SupportTicket.last_message_at.desc())
        .limit(50)
    )
    return list(rows.all())


async def messages(session: AsyncSession, ticket_id: uuid.UUID) -> list[SupportMessage]:
    rows = await session.scalars(
        select(SupportMessage).where(SupportMessage.ticket_id == ticket_id).order_by(SupportMessage.created_at, SupportMessage.id)
    )
    return list(rows.all())


async def post(session: AsyncSession, redis: Redis, *, ticket_id: uuid.UUID, user: User, body: str) -> SupportMessage:
    access = await for_member(session, ticket_id, user, lock=True)
    ticket = access.ticket
    if ticket.status not in ACTIVE_STATUSES:
        raise TicketClosed()
    text = _body(body)
    if ticket.kind == "lost_item":
        _no_phone(text)
    await _limit(redis, f"support:msg:{user.id}", MESSAGES_PER_HOUR)
    message = SupportMessage(ticket_id=ticket.id, author_id=user.id, author_role=access.role, body=text)
    session.add(message)
    ticket.needs_staff = True
    ticket.last_message_at = datetime.now(UTC)
    await session.flush()
    if access.role == "party":
        from app.services import notifications

        await notifications.publish_support_event(session, redis, user_id=ticket.user_id, ticket=ticket, event="party_reply")
    return message


async def staff_reply(session: AsyncSession, redis: Redis, *, ticket_id: uuid.UUID, actor: User, body: str) -> SupportMessage:
    from app.services import notifications

    ticket = await _locked(session, ticket_id)
    if ticket.status not in ACTIVE_STATUSES:
        raise TicketClosed()
    text = _body(body)
    message = SupportMessage(ticket_id=ticket.id, author_id=actor.id, author_role="staff", body=text)
    session.add(message)
    ticket.needs_staff = False
    ticket.last_message_at = datetime.now(UTC)
    moved = ticket.status == "open"
    if moved:
        ticket.status = "in_review"
    await session.flush()
    await notifications.publish_support_event(session, redis, user_id=ticket.user_id, ticket=ticket, event="staff_reply")
    if ticket.kind == "lost_item" and ticket.against_user_id is not None:
        await notifications.publish_support_event(session, redis, user_id=ticket.against_user_id, ticket=ticket, event="staff_reply")
    return message


async def _locked(session: AsyncSession, ticket_id: uuid.UUID) -> SupportTicket:
    ticket = await session.scalar(
        select(SupportTicket).where(SupportTicket.id == ticket_id).with_for_update().execution_options(populate_existing=True)
    )
    if ticket is None:
        raise NotFound("الطلبُ غيرُ موجود")
    return ticket


async def decide(
    session: AsyncSession, redis: Redis, *, ticket_id: uuid.UUID, actor: User, status: str, reason: str | None
) -> SupportTicket:
    """**القفلُ قبل الفحص**: حسمان متزامنان لا يكتب ثانيهما فوق الأوّل — يأخذ ٤٠٩."""
    from app.services import audit, notifications

    ticket = await _locked(session, ticket_id)
    if status not in _TRANSITIONS.get(ticket.status, set()):
        raise TicketTransition()
    note = (reason or "").strip()
    if status in ("resolved", "rejected") and len(note) < 3:
        raise InvalidInput("اكتب سببَ القرار", field="reason")
    previous = ticket.status
    ticket.status = status
    if status in ("resolved", "rejected"):
        ticket.decision_reason = note
        ticket.handled_by = actor.id
        ticket.handled_at = datetime.now(UTC)
        ticket.needs_staff = False
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="support_ticket",
        entity_id=ticket.id,
        details={"from": previous, "to": status, "reason": note or None},
    )
    await notifications.publish_support_event(session, redis, user_id=ticket.user_id, ticket=ticket, event="status")
    return ticket


@dataclass(slots=True)
class Page:
    rows: list[SupportTicket]
    total: int
    waiting: int


async def page(
    session: AsyncSession,
    *,
    status: str | None,
    kind: str | None,
    country=None,
    waiting_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> Page:
    filters = []
    if status == "active":
        filters.append(SupportTicket.status.in_(ACTIVE_STATUSES))
    elif status:
        filters.append(SupportTicket.status == status)
    if kind:
        filters.append(SupportTicket.kind == kind)
    if country is not None:
        filters.append(SupportTicket.country_code == country)
    if waiting_only:
        filters.append(SupportTicket.needs_staff.is_(True))
        filters.append(SupportTicket.status.in_(ACTIVE_STATUSES))
    total = int(await session.scalar(select(func.count()).select_from(SupportTicket).where(*filters)) or 0)
    waiting = int(
        await session.scalar(
            select(func.count())
            .select_from(SupportTicket)
            .where(SupportTicket.needs_staff.is_(True), SupportTicket.status.in_(ACTIVE_STATUSES))
        )
        or 0
    )
    rows = await session.scalars(
        select(SupportTicket)
        .where(*filters)
        .order_by(SupportTicket.needs_staff.desc(), SupportTicket.last_message_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page(list(rows.all()), total, waiting)


async def get(session: AsyncSession, ticket_id: uuid.UUID) -> SupportTicket:
    ticket = await session.get(SupportTicket, ticket_id)
    if ticket is None:
        raise NotFound("الطلبُ غيرُ موجود")
    return ticket


async def stats(session: AsyncSession, *, country=None, days: int = 90) -> dict:
    """**إحصاءٌ لكلِّ كبتنٍ وفئة** (البند ٩) — الشكاوى غيرُ المرفوضة على كلِّ طرفٍ، وكلُّ نوعٍ وحالٍ وفئة."""
    since = datetime.now(UTC) - timedelta(days=days)
    base = [SupportTicket.created_at >= since]
    if country is not None:
        base.append(SupportTicket.country_code == country)
    by_kind = (
        await session.execute(
            select(SupportTicket.kind, SupportTicket.status, func.count()).where(*base).group_by(SupportTicket.kind, SupportTicket.status)
        )
    ).all()
    by_category = (
        await session.execute(
            select(SupportTicket.category, func.count())
            .where(*base, SupportTicket.kind == "complaint")
            .group_by(SupportTicket.category)
        )
    ).all()
    against = (
        await session.execute(
            select(SupportTicket.against_user_id, User.name, func.count())
            .join(User, User.id == SupportTicket.against_user_id)
            .where(*base, SupportTicket.kind == "complaint", SupportTicket.status != "rejected", SupportTicket.app == "rider")
            .group_by(SupportTicket.against_user_id, User.name)
            .order_by(func.count().desc())
            .limit(20)
        )
    ).all()
    return {
        "days": days,
        "by_kind": [{"kind": kind, "status": status, "count": int(count)} for kind, status, count in by_kind],
        "by_category": [{"category": category or "other", "count": int(count)} for category, count in by_category],
        "drivers": [{"user_id": str(uid), "name": name, "complaints": int(count)} for uid, name, count in against],
    }


async def complaints_against(session: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    """**لدرجة الجودة** (البند ٣) — شكاوى الركّاب على هذا الكبتن ما لم تُرفض."""
    return int(
        await session.scalar(
            select(func.count())
            .select_from(SupportTicket)
            .where(
                SupportTicket.against_user_id == user_id,
                SupportTicket.kind == "complaint",
                SupportTicket.app == "rider",
                SupportTicket.status != "rejected",
                SupportTicket.created_at >= since,
            )
        )
        or 0
    )


async def erase_for_account(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """**مع تجهيل الحساب** — تذاكرُه تُمحى بصورها (نصٌّ حرٌّ يعرّف صاحبه)، **ورسائلُه في خيوط غيره تُمحى**. يعيد مساراتِ الصور."""
    paths = [
        path
        for path in (
            await session.scalars(select(SupportTicket.photo_path).where(SupportTicket.user_id == user_id, SupportTicket.photo_path.is_not(None)))
        ).all()
        if path
    ]
    await session.execute(delete(SupportMessage).where(SupportMessage.author_id == user_id))
    await session.execute(delete(SupportTicket).where(SupportTicket.user_id == user_id))
    return paths
