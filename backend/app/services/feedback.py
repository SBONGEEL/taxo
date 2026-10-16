"""«أرسل ملاحظة» من التطبيقين (SPEC §٧٦/٤) — **الكاتبُ والقارئُ والماحي في موضعٍ واحد**.

* **الصورةُ تمرّ بـ`core/storage` وحدَه** (الاسمُ يُولَّد، والنوعُ من البايتات، والحجمُ بالقراءة) **ثمّ تُرفض إن لم تكن صورة**: بابُ
  الوثائق يقبل PDF، وصورةُ الشاشة صورة.
* **عشرُ ملاحظاتٍ في الساعة لكلِّ حساب** — دلوٌ باسمه لا يشارك الدخولَ ولا تقاريرَ الأعطال.
* **والمحوُ ملفّاً وصفّاً**: مع تجهيل الحساب (`rows_of_user`)، **وبعد سنة** (`expired_rows`) — الصفُّ ثمّ الالتزامُ ثمّ الملفّ
  (`delete_files`)، فانقطاعٌ بينهما يترك ملفّاً يتيماً يكنسه الكنسُ الأسبوعيّ، **لا صفّاً يَعِد بملفٍّ محذوف**.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit, storage
from app.core.exceptions import InvalidInput, NotFound, RateLimited
from app.models.feedback import AppFeedback
from app.models.user import User

logger = logging.getLogger(__name__)

APPS = ("rider", "driver")
PER_HOUR = 10
SCREENSHOT_MAX_BYTES = 5 * 1024 * 1024
RETENTION_DAYS = 365
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _clip(value: str | None, limit: int) -> str | None:
    value = (value or "").strip()
    return value[:limit] or None


async def create(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User | None = None,
    guest=None,
    app: str,
    message: str,
    app_version: str | None = None,
    web_build: str | None = None,
    platform: str | None = None,
    route: str | None = None,
    screenshot=None,
) -> AppFeedback:
    """يكتب ملاحظةً — **والحدُّ قبل الملفّ**: من تجاوز نصيبَه لا يُكتب له شيءٌ على القرص."""
    if app not in APPS:
        raise InvalidInput("التطبيقُ راكبٌ أو كبتن", field="app")
    text = (message or "").strip()
    if not text:
        raise InvalidInput("اكتب ملاحظتك", field="message")
    if len(text) > 2000:
        raise InvalidInput("الملاحظةُ أطولُ من ٢٠٠٠ حرف", field="message")

    # **حسابٌ أو ضيفٌ — واحدٌ لا اثنان** (SPEC §٧٦-ن/٣)، وللضيف دلوٌ باسم جلسته
    assert (user is None) != (guest is None)
    sender = f"feedback:{user.id}" if user is not None else f"feedback:guest:{guest.id}"
    limit = await rate_limit.hit(redis, sender, limit=PER_HOUR, window_seconds=3600)
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    feedback_id = uuid.uuid4()
    stored = None
    if screenshot is not None:
        stored = await storage.save(screenshot, folder=str(feedback_id), max_bytes=SCREENSHOT_MAX_BYTES)
        if stored.content_type not in _IMAGE_TYPES:
            await storage.delete(stored.relative_path)
            raise InvalidInput("صورةُ الشاشة صورةٌ (PNG أو JPEG أو WebP)", field="screenshot")

    row = AppFeedback(
        id=feedback_id,
        user_id=user.id if user is not None else None,
        guest_session_id=guest.id if guest is not None else None,
        app=app,
        message=text,
        app_version=_clip(app_version, 40),
        web_build=_clip(web_build, 80),
        platform=_clip(platform, 16),
        route=_clip(route, 120),
        screenshot_path=stored.relative_path if stored else None,
        screenshot_type=stored.content_type if stored else None,
    )
    session.add(row)
    await session.flush()
    return row


@dataclass(slots=True)
class FeedbackRow:
    feedback: AppFeedback
    user_name: str | None
    user_phone: str | None


async def page(
    session: AsyncSession,
    *,
    status: str = "all",
    app: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FeedbackRow], int, int]:
    """الأحدثُ أوّلاً — **ومعها عددُ الجديدة** (ما تقرؤه شارةُ القائمة) **والمجموعُ بعد التصفية**."""
    # **`outerjoin`**: ملاحظةُ الضيف بلا حساب (SPEC §٧٦-ن/٣) — وربطٌ داخليٌّ كان سيُسقطها من القائمة بصمت
    query = select(AppFeedback, User.name, User.phone).outerjoin(User, User.id == AppFeedback.user_id)
    count = select(func.count()).select_from(AppFeedback)
    if status == "new":
        query = query.where(AppFeedback.handled_at.is_(None))
        count = count.where(AppFeedback.handled_at.is_(None))
    elif status == "handled":
        query = query.where(AppFeedback.handled_at.is_not(None))
        count = count.where(AppFeedback.handled_at.is_not(None))
    if app in APPS:
        query = query.where(AppFeedback.app == app)
        count = count.where(AppFeedback.app == app)
    rows = (
        await session.execute(
            query.order_by(AppFeedback.created_at.desc(), AppFeedback.id.desc()).limit(limit).offset(offset)
        )
    ).all()
    total = int(await session.scalar(count) or 0)
    new_count = int(
        await session.scalar(select(func.count()).select_from(AppFeedback).where(AppFeedback.handled_at.is_(None))) or 0
    )
    return [FeedbackRow(row, name, phone) for row, name, phone in rows], total, new_count


async def get(session: AsyncSession, feedback_id: uuid.UUID, *, for_update: bool = False) -> AppFeedback:
    query = select(AppFeedback).where(AppFeedback.id == feedback_id)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = await session.scalar(query)
    if row is None:
        raise NotFound("الملاحظةُ غيرُ موجودة")
    return row


async def set_handled(session: AsyncSession, feedback_id: uuid.UUID, *, admin: User, handled: bool) -> AppFeedback:
    """**يُقفل الصفُّ قبل أن يُقرأ حالُه** (`CLAUDE.md`): مشرفان يضغطان معاً لا يكتب أحدُهما فوق قرار الآخر بختمٍ قرأه قبله."""
    row = await get(session, feedback_id, for_update=True)
    if handled and row.handled_at is None:
        row.handled_at = datetime.now(UTC)
        row.handled_by = admin.id
    elif not handled:
        row.handled_at = None
        row.handled_by = None
    await session.flush()
    return row


async def _drop_rows(session: AsyncSession, where) -> list[str]:
    """يحذف الصفوفَ **ويعيد مساراتِ صورها** — والملفّاتُ تُمحى بعد الالتزام (`delete_files`)، كالوثائق في حذف الحساب: التزامٌ سقط بعد
    محو الملفّ يترك صفّاً يَعِد بصورةٍ محذوفة، وملفٌّ يبقى بعد صفّه يكنسه الكنسُ الأسبوعيّ."""
    paths = [
        path
        for path in (await session.scalars(select(AppFeedback.screenshot_path).where(where))).all()
        if path
    ]
    await session.execute(delete(AppFeedback).where(where))
    await session.flush()
    return paths


async def delete_files(paths: list[str]) -> None:
    for path in paths:
        try:
            await storage.delete(path)
        except OSError:  # pragma: no cover - الكنسُ الأسبوعيُّ يلتقطه
            logger.warning("تعذّر محوُ صورة ملاحظة")


async def rows_of_user(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """**مع تجهيل الحساب** — نصٌّ حرٌّ قد يحمل ما يعرّف صاحبه، فلا يبقى بعده. يعيد مساراتِ الصور لتُمحى بعد الالتزام."""
    return await _drop_rows(session, AppFeedback.user_id == user_id)


async def expired_rows(session: AsyncSession, *, now: datetime | None = None) -> list[str]:
    """**ما مضت عليه سنة** — والمدّةُ هي المكتوبةُ في سياسة الخصوصية (SPEC §٧٦/٣). يعيد مساراتِ الصور لتُمحى بعد الالتزام."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=RETENTION_DAYS)
    return await _drop_rows(session, AppFeedback.created_at < cutoff)
