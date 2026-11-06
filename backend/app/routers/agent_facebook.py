"""**بابُ وكيل فيسبوك إلى قناة «فيسبوك»** — بمفتاح خدمةٍ لا بحساب المالك (أمرُ المالك ٢٠٢٦-١١-٠٦، SPEC §٩٤/٧).

**ما يفتحه المفتاحُ وحدَه**: قراءةُ منشورات القناة بقرارات المالك (موافقة · طلبُ تعديل · رفض · موعد)، وإضافةُ مسوّدةٍ للمراجعة، وتسجيلُ
منشورٍ نُشر أو جُدول على فيسبوك ليُتابَع في القناة، وقراءةُ طلبات المالك. **ولا يحكم على شيء**: الموافقةُ والرفضُ والتعديلُ والموعدُ
أبوابُ `/admin/facebook` بحساب المالك وحدَه.

**ولا يفتح غيرَ هذا الملفّ**: المفتاحُ ليس رمزَ جلسة، و`facebook_agent` لا يُستعمل إلا هنا — فلا مالَ ولا مستخدمين ولا كباتن ولا رحلات
ولا إعدادات. **والخادمُ لا يحمل المفتاح**: بصمتُه SHA-256 وحدَها (`FACEBOOK_AGENT_KEY_SHA256`) — لا تُعاد منها، والمفتاحُ نفسُه في
`~/.taxo-secrets/facebook/` على جهاز الوكيل. **وسحبُه**: حذفُ البصمة (أو استبدالُها) في إيداعٍ يمرّ بالبوّابات.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core import storage
from app.core.deps import DbSession
from app.core.exceptions import AppError, Conflict, InvalidToken
from app.models.enums import AuditAction
from app.models.facebook import POST_KINDS, POST_LANGS, FacebookPost, FacebookPostRequest
from app.routers.admin_facebook import (
    MAX_MEDIA_BYTES,
    MEDIA_FOLDER,
    PostOut,
    RequestOut,
    _out,
    _req,
    _sniff_media,
)
from app.services import audit
from app.services.facebook import posts as fb_posts

#: **بصمةُ مفتاح وكيل فيسبوك** — SHA-256 لمفتاحٍ عشوائيٍّ بـ٢٥٦ بتّاً (٢٠٢٦-١١-٠٦). ليست سرّاً: لا يُستخرج منها المفتاح
FACEBOOK_AGENT_KEY_SHA256 = "34f6d7d94e655a1c66940fd04497e6906e96c6f0f18acf8fa8e6f48d69cd867d"

#: **من فعل** في سطر التدقيق — لا مشرفَ وراء المفتاح
AGENT = "facebook-agent"


async def facebook_agent(x_taxo_agent_key: Annotated[str | None, Header()] = None) -> str:
    """**المفتاحُ في ترويسة `X-TAXO-Agent-Key`** — يُقارن ببصمته في زمنٍ ثابت. وغيابُه أو خطؤه `401` كجلسةٍ غيرِ صالحة."""
    if not x_taxo_agent_key or not FACEBOOK_AGENT_KEY_SHA256:
        raise InvalidToken()
    digest = hashlib.sha256(x_taxo_agent_key.encode()).hexdigest()
    if not hmac.compare_digest(digest, FACEBOOK_AGENT_KEY_SHA256):
        raise InvalidToken()
    return AGENT


FacebookAgent = Annotated[str, Depends(facebook_agent)]

router = APIRouter(prefix="/agent/facebook", tags=["agent"])


@router.get("/posts", response_model=list[PostOut])
async def list_posts(session: DbSession, agent: FacebookAgent, status: str | None = None) -> list[PostOut]:
    """**منشوراتُ القناة بقرارات المالك** — `status` و`review_note` (ملاحظةُ التعديل أو الرفض) و`reviewed_at` و`scheduled_at`."""
    stmt = select(FacebookPost).order_by(FacebookPost.scheduled_at.asc().nulls_last(), FacebookPost.created_at.desc())
    if status:
        stmt = stmt.where(FacebookPost.status == status)
    return [_out(p) for p in await session.scalars(stmt)]


@router.post("/posts", response_model=PostOut, status_code=201)
async def add_draft(
    session: DbSession,
    agent: FacebookAgent,
    title: str = Form(..., max_length=200),
    caption: str = Form(""),
    lang: str = Form("ar"),
    kind: str = Form("photo"),
    group_key: str | None = Form(None),
    scheduled_at: datetime | None = Form(None),
    files: list[UploadFile] = File(...),
) -> PostOut:
    """**مسوّدةٌ للمراجعة** — تدخل «بانتظار المراجعة» كما تدخل من اللوحة، والقرارُ للمالك."""
    if lang not in POST_LANGS or kind not in POST_KINDS:
        raise AppError("لغةٌ أو صيغةٌ غيرُ معروفة")
    if not files:
        raise AppError("أرفق صورةً أو فيديو")
    stored = [await storage.save(f, folder=MEDIA_FOLDER, sniffer=_sniff_media, max_bytes=MAX_MEDIA_BYTES) for f in files]
    post = await fb_posts.create(session, title=title, caption=caption, lang=lang, kind=kind, group_key=group_key,
                                 scheduled_at=scheduled_at, media=stored)
    await audit.record(session, actor=None, action=AuditAction.CREATE, entity_type="facebook_post", entity_id=post.id,
                       details={"by": AGENT, "title": post.title, "lang": lang, "kind": kind, "files": len(stored)})
    await session.commit()
    return _out(post)


class RecordIn(BaseModel):
    """**منشورٌ قائمٌ على فيسبوك** — نُشر أو جُدول هناك، ويُسجَّل ليُتابَع في القناة (إحصاءاته وموعده)."""

    status: Literal["published", "scheduled"]
    fb_post_id: str = Field(..., min_length=3, max_length=80)
    title: str = Field(..., min_length=1, max_length=200)
    caption: str = ""
    lang: str = "ar"
    kind: str = "photo"
    permalink: str | None = Field(None, max_length=500)
    published_at: datetime | None = None
    scheduled_at: datetime | None = None


@router.post("/posts/record", response_model=PostOut, status_code=201)
async def record_post(body: RecordIn, session: DbSession, agent: FacebookAgent) -> PostOut:
    if body.lang not in POST_LANGS or body.kind not in POST_KINDS:
        raise AppError("لغةٌ أو صيغةٌ غيرُ معروفة")
    if body.status == "scheduled" and body.scheduled_at is None:
        raise AppError("المجدولُ يحتاج موعده")
    if await session.scalar(select(FacebookPost.id).where(FacebookPost.fb_post_id == body.fb_post_id)):
        raise Conflict("هذا المنشورُ مسجَّلٌ في القناة")
    post = FacebookPost(
        title=body.title.strip()[:200], caption=body.caption, lang=body.lang, kind=body.kind, status=body.status,
        fb_post_id=body.fb_post_id, permalink=body.permalink, scheduled_at=body.scheduled_at,
        published_at=body.published_at if body.status == "published" else None, media_paths=[],
    )
    session.add(post)
    await session.flush()
    await audit.record(session, actor=None, action=AuditAction.CREATE, entity_type="facebook_post", entity_id=post.id,
                       details={"by": AGENT, "recorded": body.status, "title": post.title})
    await session.commit()
    return _out(post)


@router.get("/requests", response_model=list[RequestOut])
async def list_requests(session: DbSession, agent: FacebookAgent) -> list[RequestOut]:
    """**طلباتُ المالك للوكيل** من القناة — تُقرأ ولا تُغلق من هنا."""
    rows = await session.scalars(select(FacebookPostRequest).order_by(FacebookPostRequest.created_at.desc()))
    return [_req(r) for r in rows]
