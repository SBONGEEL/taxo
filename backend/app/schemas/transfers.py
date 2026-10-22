"""**تحويلُ BaridiMob بمراجعةٍ يدويّة** — العقدُ على السلك (SPEC §٨٢-ب).

**وما يراه المراجعُ من صاحب الطلب اسمُه الأوّلُ وهاتفٌ مقنَّعٌ لا غير** (§٨٢-ب/٥) — لا معرّفُه ولا هاتفُه كاملاً ولا بريدُه.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CountryCode, Currency, PaymentRequestPurpose, PaymentRequestStatus


class TransferOut(BaseModel):
    id: uuid.UUID
    public_ref: str
    country_code: CountryCode
    currency: Currency
    purpose: PaymentRequestPurpose
    amount: Decimal
    credited_amount: Decimal | None
    status: PaymentRequestStatus
    #: **رقمُ التحويل كما كتبه صاحبُه**
    reference: str | None
    transfer_date: date | None
    created_at: datetime
    reviewed_at: datetime | None
    #: **من حسم** — «المراجع» أو «المالك»؛ لا اسمُ إنسان
    reviewed_by: str | None
    rejection_reason: str | None
    has_receipt: bool
    receipt_content_type: str | None
    first_name: str
    masked_phone: str


class TransferSettingsOut(BaseModel):
    """**بطاقةُ المالك** — الطريقةُ كما هي الآن. `configured` مكتملةٌ لتُشعل، و`enabled` مشتعلةٌ للناس."""

    exists: bool
    configured: bool
    enabled: bool
    account_number: str | None
    account_holder: str | None
    account_holder_latin: str | None
    min_amount: Decimal | None
    max_amount: Decimal | None
    currency: Currency


class TransferSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: **RIP بعشرين رقماً** — تُحذف المسافاتُ قبل الفحص
    account_number: str | None = Field(default=None, max_length=40)
    account_holder: str | None = Field(default=None, max_length=120)
    account_holder_latin: str | None = Field(default=None, max_length=120)
    min_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    max_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    enabled: bool = False


class ReviewerOut(BaseModel):
    id: uuid.UUID
    name: str
    username: str | None
    is_blocked: bool
    has_factor: bool
    must_change_password: bool
    created_at: datetime


class ReviewerCreateIn(BaseModel):
    """**يكتبه المالكُ** — والكلمةُ مؤقّتةٌ يعطيها لصديقه، وتتغيّر عند أوّل دخول."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
