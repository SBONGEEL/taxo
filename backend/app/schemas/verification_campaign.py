"""مخطّطاتُ حملة تأكيد الأرقام (قرارُ المالك 2026-08-31)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode, VerificationCampaignStatus
from app.models.verification_campaign import DEFAULT_DEADLINE_DAYS


class VerificationCampaignCreate(BaseModel):
    """**تُنشأ مسوّدةً** — ولا حقلَ «أطلقها الآن»، فالإطلاقُ بابٌ ثانٍ بضغطة."""

    model_config = ConfigDict(extra="forbid")

    country_code: CountryCode
    #: **المهلةُ عمودٌ لا ثابت** — حملةٌ جاريةٌ تحمل مهلتَها التي أُطلقت بها
    deadline_days: int = Field(default=DEFAULT_DEADLINE_DAYS, ge=1, le=90)


class VerificationCampaignOut(BaseModel):
    """حالُ الحملة وتقدّمُها — **ويُقرأ `scope_size` قبل الإطلاق**."""

    id: uuid.UUID
    country_code: CountryCode
    status: VerificationCampaignStatus
    deadline_days: int
    started_at: datetime | None = None
    #: **لحظةُ التجمّد الآليّ** — و`null` تعني «تعمل»
    paused_at: datetime | None = None
    finished_at: datetime | None = None
    #: **كم حساباً تشمله الآن** — يُقرأ **قبل** الضغط لا بعده
    scope_size: int
    enrolled: int
    suspended: int
    resolved: int
