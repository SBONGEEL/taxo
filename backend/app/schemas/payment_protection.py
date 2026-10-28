"""مخرجاتُ حماية الدفع في اللوحة (SPEC §٨٧) — الصحّةُ والمطابقةُ ودفترُ SofizPay."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.models.enums import CountryCode


class MethodWindowOut(BaseModel):
    opened: int
    paid: int
    failed: int
    cancelled: int
    pending: int
    processing: int
    #: **من المحسوم** (دُفع أو رُفض) بالمئة — `None` حين لا محسوم
    success_rate: int | None


class MethodHealthOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    integration: str | None
    enabled: bool
    hidden_reason: str | None
    hidden_at: datetime | None
    hidden_auto: bool
    gateway_down: bool
    failure_streak: int
    #: `today` · `week` · `month`
    windows: dict[str, MethodWindowOut]


class PaymentHealthOut(BaseModel):
    country_code: CountryCode
    streak_limit: int
    methods: list[MethodHealthOut]


class ReconciliationOut(BaseModel):
    id: uuid.UUID
    integration: str
    country_code: CountryCode
    window_start: datetime
    window_end: datetime
    checked: int
    matched: int
    mismatched: int
    unreachable: int
    trigger: str
    details: dict[str, Any]
    created_at: datetime


class LedgerEntryOut(BaseModel):
    id: str
    created_at: datetime
    direction: str
    amount: Decimal
    counterparty: str
    memo: str
    transaction_hash: str


class LedgerOut(BaseModel):
    account: str
    asset_code: str
    entries: list[LedgerEntryOut]
    #: **بلغ سقفَ القراءة قبل بداية النافذة** — ضيّق التاريخ
    truncated: bool


class LedgerBalanceOut(BaseModel):
    account: str
    asset_code: str
    balance: Decimal
    read_at: datetime
