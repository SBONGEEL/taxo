"""تزامنُ بيع الكباتن لبطاقات TAXO (`services/captain_cards.py`، الترحيلة `0189`).

* **السقفُ اليوميُّ ما يملكه قفلُ الكبتن وحدَه** (`drivers_service.lock` في `captain_cards.purchase`): بلا قفلٍ يقرأ شراءان متزامنان «صفرَ بطاقاتٍ
  اليوم» معاً فيمرّان فوق السقف — **ويسقط الاختبارُ الأوّلُ بحذف القفل** (قِيس ٢٠٢٦-١١-٢٣).
* **والرصيدُ يحرسه قفلُ المحفظة** في `wallet.record` وقيدُ `balance_after >= 0` — فالاختبارُ الثاني يبقى أخضرَ بلا قفل الكبتن، **ويُكتب ذلك**.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.taxo_card import CardBatch
from app.models.wallet import WalletTransaction
from tests.test_captain_cards import _buy, _captain, _ledger, _market
from tests.test_taxo_cards import card_pepper  # noqa: F401

pytestmark = pytest.mark.asyncio


async def test_two_purchases_at_once_cannot_pass_the_daily_cap(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    """**ما يملكه قفلُ الكبتن وحدَه**: بلا `drivers_service.lock` يقرأ الطلبان «صفرَ بطاقاتٍ اليوم» معاً فيمرّان — ٤ بطاقاتٍ تحت سقف ٣.
    والرصيدُ هنا يكفي الاثنين، فلا يردّ قفلُ المحفظة أحدَهما بدلاً منه."""
    _, denom = await _market(client, session_factory, admin_headers, cap=3)
    captain = await _captain(client, session_factory, funds="10000")
    results = await asyncio.wait_for(
        asyncio.gather(_buy(client, captain, denom, 2), _buy(client, captain, denom, 2)), timeout=30
    )
    assert Counter(r.status_code for r in results) == Counter({200: 1, 429: 1})
    assert next(r for r in results if r.status_code == 429).json()["code"] == "captain_card_daily_cap"
    entries = await _ledger(session_factory, captain["user_id"])
    assert sum(e.amount for e in entries) == Decimal("-1800.000")
    async with session_factory() as session:
        sold = await session.scalar(select(func.coalesce(func.sum(CardBatch.quantity), 0)).where(CardBatch.kind == "captain"))
        assert sold == 2


async def test_two_purchases_at_once_cannot_overdraw(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    """رصيدٌ يكفي شراءً واحداً: واحدٌ ينجح والآخرُ `insufficient_balance`، ومجموعُ الدفتر كلفةُ واحد، ولا رصيدَ سالب."""
    _, denom = await _market(client, session_factory, admin_headers)
    captain = await _captain(client, session_factory, funds="1800")
    results = await asyncio.wait_for(
        asyncio.gather(_buy(client, captain, denom, 2), _buy(client, captain, denom, 2)), timeout=30
    )
    assert Counter(r.status_code for r in results) == Counter({200: 1, 409: 1})
    assert next(r for r in results if r.status_code == 409).json()["code"] == "insufficient_balance"
    async with session_factory() as session:
        rows = (await session.scalars(select(WalletTransaction).where(WalletTransaction.owner_id == captain["user_id"]))).all()
        assert sum(r.amount for r in rows) == Decimal("0.000")
        assert all(r.balance_after >= 0 for r in rows)
        assert await session.scalar(select(func.count()).select_from(CardBatch).where(CardBatch.kind == "captain")) == 1
