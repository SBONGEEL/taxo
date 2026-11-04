"""منطقُ قناة فيسبوك: المراجعةُ والجدولةُ والمزامنةُ والتقرير (SPEC §٩٤/٢–٣).

## كلُّ تغييرِ حالٍ يقفل صفَّه قبل أن يفحص الانتقال

`_locked` يقرأ الصفَّ بـ`FOR UPDATE` — **فموافقتان معاً لا تُطلقان جدولتين**، وموافقةٌ ورفضٌ معاً لا ينتهيان «مرفوضاً ومجدولاً».

## والجدولةُ على فيسبوك تحت قفل صفّها — **استثناءٌ مكتوبٌ بعلّته**

النداءُ نفسُه هو ما يُنشئ المنشورَ على فيسبوك، فلا يُسأل قبله ثم يُطبَّق: مهمّتان بلا قفلٍ تُنشئان منشورين. **ونطاقُ القفل صفٌّ
واحدٌ ومهلتُه محدودة** (`graph.TIMEOUT`) — كـ`withdrawals.pay_via_provider` في `CLAUDE.md`.

## ولا حذفَ ولا رفضَ لما صار على فيسبوك

قاعدةُ المالك «لا يُحذف منشور»: المجدولُ هناك **يُعاد موعدُه** من القناة ولا يُرفض منها — فرفضُه يحتاج حذفَه من فيسبوك.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.exceptions import AppError, Conflict, NotFound
from app.models.facebook import FacebookPost, FacebookPostRequest
from app.models.user import User
from app.services.facebook import graph

logger = logging.getLogger(__name__)

#: فيسبوك يقبل الجدولةَ بين عشر دقائق وخمسةٍ وسبعين يوماً من الآن
MIN_LEAD = timedelta(minutes=10)
MAX_LEAD = timedelta(days=75)

REVIEWABLE = ("pending_review", "changes_requested", "failed")
#: ما لم يصل فيسبوك بعد — يُعدَّل ويُرفض ويُطلب تعديلُه
OFF_FACEBOOK = ("pending_review", "changes_requested", "approved", "failed")


def now() -> datetime:
    return datetime.now(UTC)


async def _locked(session: AsyncSession, post_id: uuid.UUID) -> FacebookPost:
    post = await session.scalar(
        select(FacebookPost).where(FacebookPost.id == post_id).with_for_update()
        .execution_options(populate_existing=True)
    )
    if post is None:
        raise NotFound("المنشور غير موجود")
    return post


def _check_time(at: datetime | None) -> datetime:
    if at is None:
        raise AppError("حدّد موعدَ النشر أوّلاً")
    if at.tzinfo is None:
        raise AppError("الموعدُ يحتاج منطقةً زمنيّة")
    lead = at - now()
    if lead < MIN_LEAD:
        raise AppError("فيسبوك يقبل الجدولةَ بعد عشر دقائق على الأقلّ من الآن")
    if lead > MAX_LEAD:
        raise AppError("فيسبوك لا يقبل الجدولةَ أبعدَ من ٧٥ يوماً")
    return at


# ───────────────────────── المراجعة

async def approve(session: AsyncSession, post_id: uuid.UUID, reviewer: User) -> FacebookPost:
    post = await _locked(session, post_id)
    if post.status not in REVIEWABLE:
        raise Conflict("لا يُوافَق على منشورٍ في هذه الحال")
    if not post.media_paths:
        raise Conflict("المنشورُ بلا صورةٍ أو فيديو")
    _check_time(post.scheduled_at)
    post.status = "approved"
    post.review_note = None
    post.last_error = None
    post.reviewed_by_id = reviewer.id
    post.reviewed_at = now()
    return post


async def decide(session: AsyncSession, post_id: uuid.UUID, reviewer: User, *, status: str, note: str | None) -> FacebookPost:
    """«اطلب تعديلاً» أو «ارفض» — **لما لم يصل فيسبوك وحدَه**."""
    assert status in ("changes_requested", "rejected")
    post = await _locked(session, post_id)
    if post.status not in OFF_FACEBOOK:
        raise Conflict("المنشورُ على فيسبوك — يُعاد موعدُه ولا يُرفض من هنا")
    if status == "changes_requested" and not (note or "").strip():
        raise AppError("اكتب ما تريد تعديلَه")
    post.status = status
    post.review_note = (note or "").strip() or None
    post.reviewed_by_id = reviewer.id
    post.reviewed_at = now()
    return post


async def edit(session: AsyncSession, post_id: uuid.UUID, *, title: str | None, caption: str | None) -> FacebookPost:
    post = await _locked(session, post_id)
    if post.status not in OFF_FACEBOOK or post.status == "approved":
        raise Conflict("لا يُعدَّل نصُّ منشورٍ موافَقٍ عليه أو على فيسبوك")
    if title is not None:
        post.title = title.strip()[:200] or post.title
    if caption is not None:
        post.caption = caption
    if post.status == "changes_requested":
        post.status = "pending_review"
    return post


async def reschedule(session: AsyncSession, post_id: uuid.UUID, at: datetime) -> FacebookPost:
    post = await _locked(session, post_id)
    if post.status in ("published", "rejected"):
        raise Conflict("لا موعدَ لمنشورٍ منشورٍ أو مرفوض")
    at = _check_time(at)
    if post.status == "scheduled" and post.fb_post_id:
        page = await graph.page(session)
        try:
            await graph.reschedule(page, post.fb_post_id, at)
        except graph.FacebookError as exc:
            raise Conflict(f"فيسبوك رفض تغييرَ الموعد: {exc}") from None
    post.scheduled_at = at
    return post


# ───────────────────────── الإنشاء من القناة

async def create(session: AsyncSession, *, title: str, caption: str, lang: str, kind: str, group_key: str | None,
                 scheduled_at: datetime | None, media: list[storage.StoredFile]) -> FacebookPost:
    post = FacebookPost(
        title=title.strip()[:200], caption=caption, lang=lang, kind=kind, group_key=(group_key or None),
        scheduled_at=scheduled_at, media_paths=[m.relative_path for m in media], status="pending_review",
    )
    session.add(post)
    await session.flush()
    return post


# ───────────────────────── الجدولةُ على فيسبوك (مهمّةُ Celery)

async def push(session: AsyncSession, post_id: uuid.UUID) -> str:
    """يُنشئ المنشورَ على فيسبوك **غيرَ منشورٍ بموعده** — تحت قفل الصفّ (انظر رأسَ الملفّ)."""
    post = await _locked(session, post_id)
    if post.status != "approved" or post.fb_post_id:
        return "skip"
    try:
        page = await graph.page(session)
        at = _check_time(post.scheduled_at)
        files = [storage.resolve(p) for p in post.media_paths]
        if post.kind == "video":
            fb_id = await graph.schedule_video(page, files[0], post.title, post.caption, at)
        elif post.kind == "carousel" and len(files) > 1:
            fb_id = await graph.schedule_carousel(page, files, post.caption, at)
        else:
            fb_id = await graph.schedule_photo(page, files[0], post.caption, at)
    except (graph.FacebookError, graph.FacebookNotConfigured, AppError) as exc:
        post.status = "failed"
        post.last_error = str(exc) or type(exc).__name__
        return "failed"
    post.fb_post_id = fb_id
    post.status = "scheduled"
    post.last_error = None
    return "scheduled"


# ───────────────────────── المزامنة

def _first_line(text: str) -> str:
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else "منشور"
    return line[:200]


def _lang_of(text: str) -> str:
    letters = re.findall(r"[A-Za-zÀ-ÿ]", text or "")
    arabic = re.findall(r"[؀-ۿ]", text or "")
    return "fr" if len(letters) > len(arabic) else "ar"


def _ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), UTC)
    return datetime.fromisoformat(str(value).replace("+0000", "+00:00"))


async def sync(session: AsyncSession) -> dict[str, int]:
    """يقرأ المجدولَ والمنشورَ من فيسبوك ويحدّث القناة: **حالٌ ورابطٌ وأرقام** — ويستورد ما جُدول من خارجها صفّاً «مجدولاً»."""
    page = await graph.page(session)
    scheduled = await graph.scheduled_posts(page)
    published = await graph.published_posts(page)
    counts = {"imported": 0, "updated": 0}
    for item, is_pub in [(x, False) for x in scheduled] + [(x, True) for x in published]:
        fb_id = str(item["id"])
        if not page.owns(fb_id):
            continue
        post = await session.scalar(
            select(FacebookPost).where(FacebookPost.fb_post_id == fb_id).with_for_update()
        )
        if post is None:
            message = item.get("message") or ""
            post = FacebookPost(
                title=_first_line(message), caption=message, lang=_lang_of(message),
                kind="photo", status="published" if is_pub else "scheduled", fb_post_id=fb_id,
                scheduled_at=_ts(item.get("scheduled_publish_time")) or _ts(item.get("created_time")),
                preview_url=item.get("full_picture"), media_paths=[],
            )
            session.add(post)
            counts["imported"] += 1
        else:
            counts["updated"] += 1
        if is_pub:
            post.status = "published"
            post.published_at = post.published_at or _ts(item.get("created_time"))
            post.permalink = item.get("permalink_url") or post.permalink
            post.stats = graph.stats_of(item)
            post.stats_at = now()
        if item.get("full_picture") and not post.preview_url:
            post.preview_url = item["full_picture"]
    await session.flush()
    return counts


# ───────────────────────── التقرير

async def report(session: AsyncSession) -> dict:
    by_status = dict((await session.execute(
        select(FacebookPost.status, func.count()).group_by(FacebookPost.status)
    )).all())
    week_ago = now() - timedelta(days=7)
    published = list(await session.scalars(
        select(FacebookPost).where(FacebookPost.status == "published").order_by(FacebookPost.published_at.desc())
    ))
    totals = {"reactions": 0, "comments": 0, "shares": 0}
    for p in published:
        for k in totals:
            totals[k] += int((p.stats or {}).get(k) or 0)
    top = sorted(published, key=lambda p: sum(int((p.stats or {}).get(k) or 0) for k in totals), reverse=True)[:5]
    page_info: dict | None = None
    error: str | None = None
    try:
        page_info = await graph.summary(await graph.page(session))
    except graph.FacebookNotConfigured:
        error = "عقدُ صفحة فيسبوك غيرُ مُدخَل في «عقود مزوّدي API»"
    except graph.FacebookError as exc:
        error = str(exc)
    upcoming = await session.scalar(
        select(func.count()).select_from(FacebookPost).where(
            FacebookPost.status == "scheduled", FacebookPost.scheduled_at >= now()
        )
    )
    return {
        "by_status": by_status,
        "published_this_week": sum(1 for p in published if p.published_at and p.published_at >= week_ago),
        "upcoming": upcoming or 0,
        "totals": totals,
        "top": [{"id": str(p.id), "title": p.title, "permalink": p.permalink, "stats": p.stats} for p in top],
        "page": page_info,
        "page_error": error,
    }


# ───────────────────────── الطلبات

async def add_request(session: AsyncSession, body: str, count: int | None, by: User) -> FacebookPostRequest:
    if not body.strip():
        raise AppError("اكتب ما تطلبه")
    req = FacebookPostRequest(body=body.strip(), count=count, status="open", created_by_id=by.id)
    session.add(req)
    await session.flush()
    return req


async def close_request(session: AsyncSession, request_id: uuid.UUID, answer: str | None) -> FacebookPostRequest:
    req = await session.scalar(
        select(FacebookPostRequest).where(FacebookPostRequest.id == request_id).with_for_update()
    )
    if req is None:
        raise NotFound("الطلب غير موجود")
    req.status = "done"
    req.answer = (answer or "").strip() or None
    return req


def media_file(post: FacebookPost, index: int) -> Path:
    if index < 0 or index >= len(post.media_paths):
        raise NotFound("الملف غير موجود")
    return storage.resolve(post.media_paths[index])
