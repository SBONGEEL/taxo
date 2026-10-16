"""وضعُ الضيف — بابان لا ثالثَ لهما (SPEC §٧٦-ن/أ).

* `POST /guest/sessions` — **بلا مصادقة**: يبدأ جلسةَ عرضٍ إن كان المفتاحُ مشتعلاً لهذا التطبيق، بحدٍّ لكلِّ جهازٍ وعنوان.
* `POST /guest/feedback` — **برمز `guest` وحدَه**: «أرسل ملاحظة» تعمل للضيف وتصل اللوحةَ موسومةً «ضيف».

**وكلُّ ما عداهما لا يقبل رمزَ الضيف**: نوعُه `guest` لا `access` — فلا رحلةَ ولا محفظةَ ولا دفعَ ولا مقبسَ ولا محادثة.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.deps import ClientIP, DbSession, RedisDep
from app.core.exceptions import InvalidToken
from app.core.i18n import current_language
from app.models.guest import GuestSession
from app.schemas.feedback import FeedbackSentOut
from app.schemas.guest import GuestStartIn, GuestStartOut
from app.services import feedback as feedback_service
from app.services import guest as guest_service

router = APIRouter(prefix="/guest", tags=["guest"])
_bearer = HTTPBearer(auto_error=False)


async def current_guest(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> GuestSession:
    if credentials is None or not credentials.credentials:
        raise InvalidToken("مطلوب رمزُ جلسة التجربة")
    return await guest_service.authenticate(session, credentials.credentials)


@router.post("/sessions", response_model=GuestStartOut, status_code=status.HTTP_201_CREATED)
async def start_guest(
    payload: GuestStartIn, request: Request, session: DbSession, redis: RedisDep, ip: ClientIP
) -> GuestStartOut:
    row, token = await guest_service.start(
        session,
        redis,
        app=payload.app,
        device_id=payload.device_id,
        ip=ip,
        language=current_language(),
        region=(request.headers.get("cf-ipcountry") or "").strip() or None,
    )
    await session.commit()
    return GuestStartOut(guest_id=str(row.id), token=token, retention_days=guest_service.RETENTION_DAYS)


@router.post("/feedback", response_model=FeedbackSentOut, status_code=status.HTTP_201_CREATED)
async def guest_feedback(
    session: DbSession,
    redis: RedisDep,
    guest: Annotated[GuestSession, Depends(current_guest)],
    app: Annotated[Literal["rider", "driver"], Form()],
    message: Annotated[str, Form(min_length=1, max_length=2000)],
    app_version: Annotated[str | None, Form(max_length=40)] = None,
    web_build: Annotated[str | None, Form(max_length=80)] = None,
    platform: Annotated[str | None, Form(max_length=16)] = None,
    route: Annotated[str | None, Form(max_length=120)] = None,
    screenshot: Annotated[UploadFile | None, File(description="صورةُ شاشةٍ اختياريّة")] = None,
) -> FeedbackSentOut:
    row = await feedback_service.create(
        session,
        redis,
        guest=guest,
        app=app,
        message=message,
        app_version=app_version,
        web_build=web_build,
        platform=platform,
        route=route,
        screenshot=screenshot,
    )
    await session.commit()
    return FeedbackSentOut(id=row.id, created_at=row.created_at)
