"""**الردودُ السريعة** (أمرُ المالك ٢٠٢٦-١١-٢٠ الرابع، البند ٥٠) — يقرؤها التطبيقان ويكتبها المشرفُ لكلِّ دولة.

والإرسالُ نفسُه بباب المحادثة القائم (`POST /rides/{id}/chat`) — هذا البابُ يقول **ما** يُرسل لا **كيف**.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, DbSession, SettingsWriter, StaffUser
from app.models.enums import CountryCode, FeatureKey
from app.services import quick_replies, settings_service

router = APIRouter(tags=["quick-replies"])


class QuickRepliesOut(BaseModel):
    enabled: bool
    texts: list[str]


@router.get("/quick-replies", response_model=QuickRepliesOut)
async def my_quick_replies(
    user: CurrentUser, session: DbSession, side: Literal["driver", "rider"] = Query(...)
) -> QuickRepliesOut:
    """ردودُ دولة المستخدم لجانبه — **ومطفأً `enabled=false` وقائمةٌ فارغة** فلا يُرسم زرّ."""
    if not await settings_service.is_feature_enabled(session, user.country_code, FeatureKey.QUICK_REPLIES):
        return QuickRepliesOut(enabled=False, texts=[])
    return QuickRepliesOut(enabled=True, texts=await quick_replies.texts_for(session, user.country_code, side))


class QuickReplySettingsOut(BaseModel):
    country_code: CountryCode
    driver_texts: list[str]
    rider_texts: list[str]


class QuickReplySettingsIn(BaseModel):
    driver_texts: list[str] = Field(default_factory=list, max_length=20)
    rider_texts: list[str] = Field(default_factory=list, max_length=20)


@router.get("/admin/quick-replies/{country_code}", response_model=QuickReplySettingsOut)
async def get_quick_reply_settings(country_code: CountryCode, session: DbSession, _: StaffUser) -> QuickReplySettingsOut:
    driver, rider = await quick_replies.settings_for(session, country_code)
    return QuickReplySettingsOut(country_code=country_code, driver_texts=driver, rider_texts=rider)


@router.put("/admin/quick-replies/{country_code}", response_model=QuickReplySettingsOut)
async def save_quick_reply_settings(
    country_code: CountryCode, body: QuickReplySettingsIn, session: DbSession, actor: SettingsWriter
) -> QuickReplySettingsOut:
    driver, rider = await quick_replies.save(
        session, country=country_code, driver_texts=body.driver_texts, rider_texts=body.rider_texts, actor=actor
    )
    await session.commit()
    return QuickReplySettingsOut(country_code=country_code, driver_texts=driver, rider_texts=rider)
