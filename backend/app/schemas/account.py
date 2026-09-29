"""حمولاتُ بابِ الحساب — **حذفُه بعد مهلة** (SPEC §59)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DeletionRequestIn(BaseModel):
    """**المبلغُ الذي يُقرّ بضياعه كما هو** — أو لا شيءَ حين لا رصيد.

    نصٌّ لا رقمٌ عائم: يُكتب بأرقامٍ لاتينية ويُقارَن بالرصيد حرفاً بعد
    التقريب إلى ثلاث منازل — **فموافقةٌ على غير ما في المحفظة ليست موافقة**.
    """

    forfeit_amount: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=3
    )


class DeletionStateOut(BaseModel):
    """ما تحتاجه شاشةُ الحذف في نداءٍ واحد — **والموانعُ كلُّها لا أوّلُها**."""

    requested_at: datetime | None
    due_at: datetime | None
    #: رمزُ سبب التأجيل إن حلّ الموعدُ ولم يقع — والنصُّ في الشاشة
    deferred_reason: str | None
    blockers: list[str]
    rider_balance: Decimal
    driver_balance: Decimal
    forfeit_amount: Decimal | None
    currency: str
    is_driver: bool
    #: **خيارُ التحويل يظهر حين يكون مفعّلاً في دولته وحدَه** (قرارُ المالك)
    transfer_enabled: bool


class PendingDeletionRow(BaseModel):
    """حسابٌ في مهلة الحذف كما يراه المشرف — **وموعدُ تجهيله وسببُ تأجيله**."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str | None
    deletion_requested_at: datetime
    deletion_due_at: datetime
    deletion_deferred_reason: str | None
    deletion_deferred_at: datetime | None
