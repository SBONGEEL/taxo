"""**دفترُ حساب SofizPay من Stellar** (SPEC §٨٧/٤، أمرُ المالك ٢٠٢٦-١٠-٢٨) — رصيدُ الحساب ومعاملاتُه **قراءةً بالمفتاح العامّ وحدَه**.

**لمَ يُقرأ من Stellar**: حسابُ التاجر عند SofizPay حسابُ Stellar (`G…`)، وعملتُه رمزُ `DZT` بمُصدِره — **وكلاهما عامّان** على Horizon
بلا مفتاحٍ ولا تسجيل، كما يقرؤهما الـSDK الرسميّ (`get_balance` و`get_transactions`). **فلا سرَّ على الخادم ولا نداءَ يكتب**: لا إرسالَ ولا
سحبَ ولا تحويلَ ولا شحنَ ولا فواتير — **بابُ قراءةٍ وحدَه** (`GET` على Horizon)، وشرطُ المالك نصّاً.

**ومن يرى ماذا**: المعاملاتُ لمن مُنح `gateway_ledger.read` (المالكُ بدوره)، **والرصيدُ للمالك وحدَه**.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.enums import CountryCode, ProviderKey
from app.services import payment_gateways
from app.services.providers import credentials as credentials_service

HORIZON = "https://horizon.stellar.org"
#: **عملةُ SofizPay على Stellar** — رمزٌ ومُصدِرٌ من الـSDK الرسميّ (`sofizpay/client.py` و`transactions.py`، 1.0.2)
ASSET_CODE = "DZT"
ASSET_ISSUER = "GCAZI7YBLIDJWIVEL7ETNAZGPP3LC24NO6KAOBWZHUERXQ7M5BC52DLV"
#: **سقفُ ما يُقرأ في طلبٍ واحد** — عشرُ صفحاتٍ بمئتين؛ وما بعده يُطلب بمرشّح التاريخ
MAX_PAGES = 10
PAGE_SIZE = 200
_PUBLIC_KEY = re.compile(r"^G[A-Z2-7]{55}$")
_PAYMENT_TYPES = frozenset({"payment", "path_payment_strict_receive", "path_payment_strict_send"})


class LedgerUnavailable(AppError):
    """**لا حسابَ SofizPay بمفتاحٍ عامٍّ صالح في هذا السوق** (`503`)."""

    status_code = 503
    code = "gateway_ledger_unavailable"
    message = "لا حسابَ SofizPay بمفتاحٍ عامٍّ صالح في عقد هذه الدولة — أدخله في «عقود مزوّدي API»."


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    id: str
    created_at: datetime
    #: `in` وارد إلى حسابنا · `out` خارجٌ منه
    direction: str
    amount: Decimal
    counterparty: str
    memo: str
    transaction_hash: str


def valid_public_key(value: str | None) -> bool:
    return bool(value) and bool(_PUBLIC_KEY.match(value or ""))


async def account_for(session: AsyncSession, country: CountryCode) -> str:
    """**المفتاحُ العامُّ من عقد SofizPay** — مفعَّلاً أو موقوفاً: الدفترُ يُقرأ ولو كانت الطريقةُ مخفيّة."""
    values = await credentials_service.get_values(session, ProviderKey.SOFIZPAY, country, active_only=False)
    account = str((values or {}).get("account") or "").strip()
    if not valid_public_key(account):
        raise LedgerUnavailable()
    return account


async def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = path if path.startswith("http") else f"{HORIZON}{path}"
    try:
        async with payment_gateways.http_client() as http:
            response = await http.get(url, params=params, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise payment_gateways.GatewayDown() from exc
    if response.status_code == 404:
        raise LedgerUnavailable("حسابُ SofizPay غيرُ موجودٍ على Stellar — تحقّق من المفتاح العامّ")
    if response.status_code >= 500:
        raise payment_gateways.GatewayDown()
    if response.status_code >= 400:
        raise payment_gateways.GatewayError("رفض Stellar الطلب")
    try:
        body = response.json()
    except ValueError as exc:
        raise payment_gateways.GatewayError("جوابٌ غيرُ مقروءٍ من Stellar") from exc
    return body if isinstance(body, dict) else {}


def _money(value: object) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(Decimal("0.001"))
    except (InvalidOperation, ValueError):
        return None


async def balance(account: str) -> Decimal:
    """**رصيدُ DZT في الحساب** — من Horizon كما يقرؤه `get_balance` في الـSDK؛ وحسابٌ بلا خطِّ ثقةٍ لـDZT رصيدُه صفر."""
    body = await _get(f"/accounts/{account}")
    for item in body.get("balances") or []:
        if item.get("asset_code") == ASSET_CODE and item.get("asset_issuer") == ASSET_ISSUER:
            return _money(item.get("balance")) or Decimal("0.000")
    return Decimal("0.000")


def entry_of(account: str, record: dict[str, Any]) -> LedgerEntry | None:
    """**سجلُّ Horizon ⇐ معاملةُ DZT** — وما ليس دفعةَ DZT (خطُّ ثقة · XLM · عملةٌ أخرى) يُطرح."""
    if record.get("type") not in _PAYMENT_TYPES:
        return None
    if record.get("asset_code") != ASSET_CODE or record.get("asset_issuer") != ASSET_ISSUER:
        return None
    amount = _money(record.get("amount"))
    if amount is None:
        return None
    incoming = record.get("to") == account
    try:
        created = datetime.fromisoformat(str(record.get("created_at")).replace("Z", "+00:00"))
    except ValueError:
        return None
    transaction = record.get("transaction") if isinstance(record.get("transaction"), dict) else {}
    return LedgerEntry(
        id=str(record.get("id") or record.get("paging_token") or ""),
        created_at=created,
        direction="in" if incoming else "out",
        amount=amount,
        counterparty=str(record.get("from") if incoming else record.get("to") or ""),
        memo=str(transaction.get("memo") or ""),
        transaction_hash=str(record.get("transaction_hash") or ""),
    )


async def entries(
    account: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    direction: str | None = None,
    search: str | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
) -> tuple[list[LedgerEntry], bool]:
    """**معاملاتُ DZT للحساب، الأحدثُ أوّلاً، بالمرشّحات** — ويعيد «أبقي ما لم يُقرأ؟» حين يبلغ السقفَ قبل بداية النافذة."""
    found: list[LedgerEntry] = []
    url: str | None = f"/accounts/{account}/payments"
    params: dict[str, Any] | None = {"order": "desc", "limit": PAGE_SIZE, "join": "transactions"}
    needle = (search or "").strip().lower()
    for _ in range(MAX_PAGES):
        if url is None:
            return found, False
        body = await _get(url, params)
        records = ((body.get("_embedded") or {}).get("records")) or []
        if not records:
            return found, False
        for record in records:
            entry = entry_of(account, record)
            if entry is None:
                continue
            if since is not None and entry.created_at < since:
                return found, False
            if until is not None and entry.created_at > until:
                continue
            if direction in ("in", "out") and entry.direction != direction:
                continue
            if min_amount is not None and entry.amount < min_amount:
                continue
            if max_amount is not None and entry.amount > max_amount:
                continue
            if needle and needle not in f"{entry.memo} {entry.transaction_hash} {entry.counterparty}".lower():
                continue
            found.append(entry)
        nxt = ((body.get("_links") or {}).get("next") or {}).get("href")
        url, params = (nxt, None) if nxt else (None, None)
    return found, url is not None


async def latest_cursor(account: str) -> str | None:
    """**مؤشّرُ آخر سجلّ** — نقطةُ بداية المراقبة: ما بعده جديد."""
    body = await _get(f"/accounts/{account}/payments", {"order": "desc", "limit": 1})
    records = ((body.get("_embedded") or {}).get("records")) or []
    # **حسابٌ بلا سجلّ يبدأ من أوّله** — `now` مؤشّرُ بثٍّ لا سؤالٍ دوريّ: لا يتقدّم أبداً في `order=asc`
    return str(records[0].get("paging_token")) if records else "0"


async def incoming_since(account: str, cursor: str) -> tuple[list[LedgerEntry], str]:
    """**ما وصل بعد المؤشّر** — بترتيب الوصول، ومعه المؤشّرُ الجديد. صفحةٌ واحدةٌ تكفي دورةً بعشرين ثانية."""
    body = await _get(
        f"/accounts/{account}/payments", {"order": "asc", "limit": PAGE_SIZE, "cursor": cursor, "join": "transactions"}
    )
    records = ((body.get("_embedded") or {}).get("records")) or []
    arrived = [e for r in records if (e := entry_of(account, r)) is not None and e.direction == "in"]
    newest = str(records[-1].get("paging_token")) if records else cursor
    return arrived, newest
