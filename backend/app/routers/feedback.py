"""«أرسل ملاحظة» — بابُ التطبيقين (SPEC §٧٦/٤). **نصٌّ وصورةُ شاشةٍ اختياريّة**، ومعهما ما يلزم لقراءتها.

**ولا يحتاج دوراً بعينه**: حسابٌ واحدٌ قد يملك الدورين، **والتطبيقُ الذي كُتبت منه هو ما يُسجَّل** (`app`) — لا دورُ الحساب.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, UploadFile, status

from app.core.deps import CurrentUser, DbSession, RedisDep
from app.schemas.feedback import FeedbackSentOut
from app.services import feedback as feedback_service

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackSentOut, status_code=status.HTTP_201_CREATED)
async def send_feedback(
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
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
        user=user,
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
