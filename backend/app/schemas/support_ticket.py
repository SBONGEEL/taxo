"""مخطّطاتُ التذاكر (البندان ٨ و٩)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TicketKind = Literal["support", "lost_item", "complaint"]
TicketStatus = Literal["open", "in_review", "resolved", "rejected"]
ComplaintCategory = Literal["behavior", "vehicle", "route", "fare", "safety", "other"]


class SupportMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    #: `user` صاحبُ الطلب · `party` الكبتنُ في خيط المفقودات · `staff` فريقُ الدعم — **بلا أسماءٍ ولا أرقام**
    author_role: Literal["user", "party", "staff"]
    body: str
    created_at: datetime


class SupportTicketOut(BaseModel):
    id: uuid.UUID
    kind: TicketKind
    status: TicketStatus
    category: ComplaintCategory | None
    ride_id: uuid.UUID | None
    #: صفتي في هذا الطلب — صاحبُه، أو الكبتنُ في خيط مفقوداتٍ على رحلته
    my_role: Literal["user", "party"]
    decision_reason: str | None
    has_photo: bool
    created_at: datetime
    last_message_at: datetime


class SupportTicketDetailOut(SupportTicketOut):
    messages: list[SupportMessageOut]


class SupportMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class AdminRideBrief(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime


class AdminTicketOut(BaseModel):
    id: uuid.UUID
    kind: TicketKind
    status: TicketStatus
    category: ComplaintCategory | None
    app: Literal["rider", "driver"]
    country_code: str
    ride_id: uuid.UUID | None
    user_id: uuid.UUID
    user_name: str | None
    against_user_id: uuid.UUID | None
    against_name: str | None
    needs_staff: bool
    decision_reason: str | None
    handled_at: datetime | None
    has_photo: bool
    created_at: datetime
    last_message_at: datetime


class AdminTicketPage(BaseModel):
    items: list[AdminTicketOut]
    total: int
    waiting: int


class AdminAccountBrief(BaseModel):
    """**الحسابُ وآخرُ رحلاته بجانب المحادثة** (البند ٨) — ما يحتاجه المشرفُ ليجيب بلا تنقّل."""

    name: str
    phone: str | None
    roles: list[str]
    created_at: datetime
    rides: list[AdminRideBrief]


class AdminTicketDetailOut(AdminTicketOut):
    messages: list[SupportMessageOut]
    account: AdminAccountBrief


class AdminDecisionIn(BaseModel):
    status: Literal["in_review", "resolved", "rejected"]
    reason: str | None = Field(default=None, max_length=1000)
