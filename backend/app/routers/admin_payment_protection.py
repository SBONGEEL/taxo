"""**حمايةُ الدفع في اللوحة** (SPEC §٨٧، أمرُ المالك ٢٠٢٦-١٠-٢٨) — صحّةُ الطرق، وسجلُّ المطابقة اليوميّة، ودفترُ SofizPay ورصيدُه.

**ومن يرى ماذا**: الصحّةُ والمطابقةُ لطاقم اللوحة (`read.only`)، **وتشغيلُ المطابقة الآن للمالك**؛ **ومعاملاتُ SofizPay لمن مُنح
`gateway_ledger.read`** (لا تُعطى افتراضاً)، **والرصيدُ للمالك وحدَه**. وكلُّ عرضٍ للدفتر وتصديرٍ سطرٌ في التدقيق.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.core.deps import DbSession, GatewayLedgerReader, ListReader, OwnerUser
from app.models.enums import AuditAction, CountryCode
from app.schemas.payment_protection import (
    LedgerBalanceOut,
    LedgerEntryOut,
    LedgerOut,
    PaymentHealthOut,
    ReconciliationOut,
)
from app.services import audit, payment_protection, sofizpay_ledger

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/payment-health", response_model=PaymentHealthOut)
async def payment_health(_reader: ListReader, session: DbSession, country: CountryCode = Query()) -> PaymentHealthOut:
    return PaymentHealthOut.model_validate(await payment_protection.health(session, country))


@router.get("/payment-health/reconciliations", response_model=list[ReconciliationOut])
async def list_reconciliations(
    _reader: ListReader, session: DbSession, country: CountryCode | None = Query(default=None)
) -> list[ReconciliationOut]:
    return [ReconciliationOut.model_validate(r, from_attributes=True) for r in await payment_protection.reconciliations(session, country)]


@router.post("/payment-health/reconciliations/run", response_model=list[ReconciliationOut])
async def run_reconciliation(owner: OwnerUser, session: DbSession) -> list[ReconciliationOut]:
    """**«طابِق الآن»** — المالكُ وحدَه؛ تقريرٌ لا يكتب في الدفتر."""
    await audit.record(session, actor=owner, action=AuditAction.UPDATE, entity_type="gateway_reconciliation",
                       details={"action": "run"})
    await session.commit()
    reports = await payment_protection.reconcile_daily(session, trigger="manual")
    return [ReconciliationOut.model_validate(r, from_attributes=True) for r in reports]


def _window(since: date | None, until: date | None) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(since, time.min, tzinfo=UTC) if since else None
    end = datetime.combine(until, time.min, tzinfo=UTC) + timedelta(days=1) if until else None
    return start, end


async def _ledger(session, reader, country, since, until, direction, search, min_amount, max_amount, *, export: bool):
    account = await sofizpay_ledger.account_for(session, country)
    start, end = _window(since, until)
    found, truncated = await sofizpay_ledger.entries(
        account, since=start, until=end, direction=direction, search=search, min_amount=min_amount, max_amount=max_amount
    )
    # **كلُّ عرضٍ وتصديرٍ سطرٌ في التدقيق** — كالملخّصات المالية: معاملاتُ حساب التاجر كلُّها
    await audit.record(
        session, actor=reader, action=AuditAction.READ, entity_type="gateway_ledger",
        details={"action": "export" if export else "view", "country": country.value, "count": len(found)},
    )
    await session.commit()
    return account, found, truncated


@router.get("/sofizpay/transactions", response_model=LedgerOut)
async def sofizpay_transactions(
    reader: GatewayLedgerReader,
    session: DbSession,
    country: CountryCode = Query(default=CountryCode.DZ),
    since: date | None = Query(default=None),
    until: date | None = Query(default=None),
    direction: str | None = Query(default=None, pattern="^(in|out)$"),
    search: str | None = Query(default=None, max_length=120),
    min_amount: Decimal | None = Query(default=None, ge=0),
    max_amount: Decimal | None = Query(default=None, ge=0),
) -> LedgerOut:
    account, found, truncated = await _ledger(
        session, reader, country, since, until, direction, search, min_amount, max_amount, export=False
    )
    return LedgerOut(
        account=account, asset_code=sofizpay_ledger.ASSET_CODE, truncated=truncated,
        entries=[
            LedgerEntryOut(
                id=e.id, created_at=e.created_at, direction=e.direction, amount=e.amount, counterparty=e.counterparty,
                memo=e.memo, transaction_hash=e.transaction_hash,
            )
            for e in found
        ],
    )


@router.get("/sofizpay/transactions.csv")
async def sofizpay_transactions_csv(
    reader: GatewayLedgerReader,
    session: DbSession,
    country: CountryCode = Query(default=CountryCode.DZ),
    since: date | None = Query(default=None),
    until: date | None = Query(default=None),
    direction: str | None = Query(default=None, pattern="^(in|out)$"),
    search: str | None = Query(default=None, max_length=120),
    min_amount: Decimal | None = Query(default=None, ge=0),
    max_amount: Decimal | None = Query(default=None, ge=0),
) -> Response:
    _account, found, _truncated = await _ledger(
        session, reader, country, since, until, direction, search, min_amount, max_amount, export=True
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["created_at", "direction", "amount", "asset", "counterparty", "memo", "transaction_hash"])
    for e in found:
        writer.writerow([e.created_at.isoformat(), e.direction, str(e.amount), sofizpay_ledger.ASSET_CODE,
                         e.counterparty, e.memo, e.transaction_hash])
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sofizpay-transactions.csv"', "Cache-Control": "no-store"},
    )


@router.get("/sofizpay/balance", response_model=LedgerBalanceOut)
async def sofizpay_balance(
    owner: OwnerUser, session: DbSession, country: CountryCode = Query(default=CountryCode.DZ)
) -> LedgerBalanceOut:
    """**رصيدُ حساب SofizPay — للمالك وحدَه، قراءةً** من Stellar بالمفتاح العامّ."""
    account = await sofizpay_ledger.account_for(session, country)
    value = await sofizpay_ledger.balance(account)
    return LedgerBalanceOut(account=account, asset_code=sofizpay_ledger.ASSET_CODE, balance=value, read_at=datetime.now(UTC))
