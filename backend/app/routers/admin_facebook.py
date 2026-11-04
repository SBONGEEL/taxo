"""قسمُ «فيسبوك» في لوحة التحكّم — **SPEC §٩٤/٢**، بصلاحيّة `facebook.manage` الحسّاسة.

الموافقةُ تُطلق مهمّةً تُجدوِل المنشورَ على فيسبوك نفسِه؛ وطلبُ التعديل والرفضُ لما لم يصل فيسبوك؛ وتغييرُ الموعد يعدّل فيسبوك إن
كان هناك. **وكلُّ فعلٍ سطرٌ في التدقيق باسم المشرف.**
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core import storage
from app.core.deps import DbSession, FacebookManager
from app.core.exceptions import AppError
from app.models.enums import AuditAction
from app.models.facebook import POST_KINDS, POST_LANGS, FacebookPost, FacebookPostRequest
from app.services import audit
from app.services.facebook import graph, posts as fb_posts

router = APIRouter(prefix="/admin/facebook", tags=["admin"])

#: حدُّ الصورة والفيديو — الفيديو القصيرُ لصفحةٍ يكفيه هذا
MAX_MEDIA_BYTES = 200 * 1024 * 1024
#: **مجلّدُ القناة في التخزين** — `core.storage` يقبل مجلّداً باسم UUID وحدَه، فلها معرّفٌ ثابتٌ مشتقٌّ من اسمها
MEDIA_FOLDER = str(uuid.uuid5(uuid.NAMESPACE_URL, "taxo:facebook-channel"))


def _sniff_media(head: bytes) -> tuple[str, str]:
    """صورةٌ (jpeg/png/webp) أو فيديو MP4 — **ولا PDF** وإن قبله مُفحِّصُ الوثائق."""
    if head[4:8] == b"ftyp":
        return "video/mp4", ".mp4"
    content_type, extension = storage.sniff(head)
    if content_type == "application/pdf":
        raise AppError("الملفُّ صورةٌ أو فيديو MP4 فقط")
    return content_type, extension


class PostOut(BaseModel):
    id: uuid.UUID
    title: str
    caption: str
    lang: str
    kind: str
    status: str
    group_key: str | None
    scheduled_at: datetime | None
    media_count: int
    media_types: list[str]
    preview_url: str | None
    review_note: str | None
    reviewed_at: datetime | None
    fb_post_id: str | None
    permalink: str | None
    published_at: datetime | None
    last_error: str | None
    stats: dict
    created_at: datetime


def _out(p: FacebookPost) -> PostOut:
    return PostOut(
        id=p.id, title=p.title, caption=p.caption, lang=p.lang, kind=p.kind, status=p.status, group_key=p.group_key,
        scheduled_at=p.scheduled_at, media_count=len(p.media_paths),
        media_types=["video" if m.endswith(".mp4") else "image" for m in p.media_paths],
        preview_url=p.preview_url, review_note=p.review_note, reviewed_at=p.reviewed_at, fb_post_id=p.fb_post_id,
        permalink=p.permalink, published_at=p.published_at, last_error=p.last_error, stats=p.stats or {},
        created_at=p.created_at,
    )


async def _audit(session, admin, post: FacebookPost, what: str, **details) -> None:
    await audit.record(session, actor=admin, action=AuditAction.UPDATE, entity_type="facebook_post", entity_id=post.id,
                       details={"what": what, "title": post.title, "status": post.status, **details})


def _enqueue(post_id: uuid.UUID) -> None:
    from app.tasks.facebook import push_post

    push_post.delay(str(post_id))


@router.get("/posts", response_model=list[PostOut])
async def list_posts(session: DbSession, admin: FacebookManager, status: str | None = None) -> list[PostOut]:
    stmt = select(FacebookPost).order_by(FacebookPost.scheduled_at.asc().nulls_last(), FacebookPost.created_at.desc())
    if status:
        stmt = stmt.where(FacebookPost.status == status)
    return [_out(p) for p in await session.scalars(stmt)]


@router.post("/posts", response_model=PostOut, status_code=201)
async def create_post(
    session: DbSession,
    admin: FacebookManager,
    title: str = Form(..., max_length=200),
    caption: str = Form(""),
    lang: str = Form("ar"),
    kind: str = Form("photo"),
    group_key: str | None = Form(None),
    scheduled_at: datetime | None = Form(None),
    files: list[UploadFile] = File(...),
) -> PostOut:
    if lang not in POST_LANGS or kind not in POST_KINDS:
        raise AppError("لغةٌ أو صيغةٌ غيرُ معروفة")
    if not files:
        raise AppError("أرفق صورةً أو فيديو")
    stored = [await storage.save(f, folder=MEDIA_FOLDER, sniffer=_sniff_media, max_bytes=MAX_MEDIA_BYTES) for f in files]
    post = await fb_posts.create(session, title=title, caption=caption, lang=lang, kind=kind, group_key=group_key,
                                 scheduled_at=scheduled_at, media=stored)
    await audit.record(session, actor=admin, action=AuditAction.CREATE, entity_type="facebook_post", entity_id=post.id,
                       details={"title": post.title, "lang": lang, "kind": kind, "files": len(stored)})
    await session.commit()
    return _out(post)


@router.get("/posts/{post_id}/media/{index}")
async def post_media(post_id: uuid.UUID, index: int, session: DbSession, admin: FacebookManager) -> FileResponse:
    post = await session.get(FacebookPost, post_id)
    if post is None:
        raise AppError("المنشور غير موجود")
    return FileResponse(fb_posts.media_file(post, index))


class EditIn(BaseModel):
    title: str | None = Field(None, max_length=200)
    caption: str | None = None


@router.patch("/posts/{post_id}", response_model=PostOut)
async def edit_post(post_id: uuid.UUID, body: EditIn, session: DbSession, admin: FacebookManager) -> PostOut:
    post = await fb_posts.edit(session, post_id, title=body.title, caption=body.caption)
    await _audit(session, admin, post, "edit")
    await session.commit()
    return _out(post)


@router.post("/posts/{post_id}/approve", response_model=PostOut)
async def approve_post(post_id: uuid.UUID, session: DbSession, admin: FacebookManager) -> PostOut:
    post = await fb_posts.approve(session, post_id, admin)
    await _audit(session, admin, post, "approve")
    await session.commit()
    _enqueue(post.id)
    return _out(post)


class DecideIn(BaseModel):
    decision: Literal["changes_requested", "rejected"]
    note: str | None = Field(None, max_length=2000)


@router.post("/posts/{post_id}/decide", response_model=PostOut)
async def decide_post(post_id: uuid.UUID, body: DecideIn, session: DbSession, admin: FacebookManager) -> PostOut:
    post = await fb_posts.decide(session, post_id, admin, status=body.decision, note=body.note)
    await _audit(session, admin, post, body.decision, note=body.note)
    await session.commit()
    return _out(post)


class RescheduleIn(BaseModel):
    scheduled_at: datetime


@router.post("/posts/{post_id}/reschedule", response_model=PostOut)
async def reschedule_post(post_id: uuid.UUID, body: RescheduleIn, session: DbSession, admin: FacebookManager) -> PostOut:
    post = await fb_posts.reschedule(session, post_id, body.scheduled_at)
    await _audit(session, admin, post, "reschedule", scheduled_at=body.scheduled_at.isoformat())
    await session.commit()
    return _out(post)


@router.post("/groups/{group_key}/approve", response_model=list[PostOut])
async def approve_group(group_key: str, session: DbSession, admin: FacebookManager) -> list[PostOut]:
    """**الموافقةُ الجماعيّة**: كلُّ ما في المجموعة بانتظار المراجعة — وما لا يصلح منها يُقال ولا يوقف الباقي."""
    ids = list(await session.scalars(
        select(FacebookPost.id).where(FacebookPost.group_key == group_key, FacebookPost.status.in_(fb_posts.REVIEWABLE))
        .order_by(FacebookPost.id)
    ))
    done: list[FacebookPost] = []
    for pid in ids:
        post = await fb_posts.approve(session, pid, admin)
        await _audit(session, admin, post, "approve", group=group_key)
        done.append(post)
    await session.commit()
    for post in done:
        _enqueue(post.id)
    return [_out(p) for p in done]


@router.post("/sync")
async def sync_now(session: DbSession, admin: FacebookManager) -> dict:
    try:
        counts = await fb_posts.sync(session)
    except graph.FacebookNotConfigured:
        raise AppError("عقدُ صفحة فيسبوك غيرُ مُدخَل في «عقود مزوّدي API»") from None
    except graph.FacebookError as exc:
        raise AppError(f"فيسبوك: {exc}") from None
    await session.commit()
    return counts


@router.get("/report")
async def report(session: DbSession, admin: FacebookManager) -> dict:
    return await fb_posts.report(session)


class RequestOut(BaseModel):
    id: uuid.UUID
    body: str
    count: int | None
    status: str
    answer: str | None
    created_at: datetime


def _req(r: FacebookPostRequest) -> RequestOut:
    return RequestOut(id=r.id, body=r.body, count=r.count, status=r.status, answer=r.answer, created_at=r.created_at)


@router.get("/requests", response_model=list[RequestOut])
async def list_requests(session: DbSession, admin: FacebookManager) -> list[RequestOut]:
    rows = await session.scalars(select(FacebookPostRequest).order_by(FacebookPostRequest.created_at.desc()))
    return [_req(r) for r in rows]


class RequestIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)
    count: int | None = Field(None, ge=1, le=50)


@router.post("/requests", response_model=RequestOut, status_code=201)
async def add_request(body: RequestIn, session: DbSession, admin: FacebookManager) -> RequestOut:
    req = await fb_posts.add_request(session, body.body, body.count, admin)
    await audit.record(session, actor=admin, action=AuditAction.CREATE, entity_type="facebook_post_request",
                       entity_id=req.id, details={"count": body.count})
    await session.commit()
    return _req(req)


class CloseIn(BaseModel):
    answer: str | None = Field(None, max_length=4000)


@router.post("/requests/{request_id}/done", response_model=RequestOut)
async def close_request(request_id: uuid.UUID, body: CloseIn, session: DbSession, admin: FacebookManager) -> RequestOut:
    req = await fb_posts.close_request(session, request_id, body.answer)
    await audit.record(session, actor=admin, action=AuditAction.UPDATE, entity_type="facebook_post_request",
                       entity_id=req.id, details={"status": "done"})
    await session.commit()
    return _req(req)
