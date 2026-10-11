"""تزامنُ بطاقات TAXO (`services/taxo_cards`، SPEC §٧٣-هـ المرحلة ٢/٧) — **حسابان يُدخلان الرمزَ نفسَه في اللحظة نفسِها**.

**والثابتُ ما يملكه قفلُ صفِّ البطاقة**: ينجح واحدٌ ويخسر الآخرُ بالرمز المحدّد (`taxo_card_rejected`: «استُعملت»)، وقيدٌ واحدٌ في الدفتر.
**وبلا القفل** يقرأ الاثنان «قائمة»، فيصطدم الثاني بالفهرس الفريد لمرجع الدفعة (حارسُه الثاني) **فيخرج بخطأٍ لا برفضٍ مفهوم** —
والمالُ لا يُقيَّد مرّتين، **لكنّ الاختبارَ يسقط**: وهو الإثباتُ أن القفلَ هو ما يحرس هذا الثابت.
"""

from __future__ import annotations

import asyncio
from collections import Counter

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import settings
from app.models.enums import WalletTransactionType
from app.models.wallet import WalletTransaction
from app.services import taxo_cards  # noqa: F401 — الخدمةُ التي يحرسها هذا الملفّ
from tests.helpers import rider_session
from tests.test_payment_requests import ALGERIAN_RIDER, SECOND_ALGERIAN
from tests.test_taxo_cards import card_market, issue


@pytest.fixture(autouse=True)
def card_pepper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "taxo_card_code_pepper", "test-pepper-for-cards")


async def test_two_accounts_entering_one_code_at_once_top_up_once(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=1)
    code = body["codes"][0]["code"]
    first = await rider_session(client, ALGERIAN_RIDER)
    second = await rider_session(client, SECOND_ALGERIAN)

    responses = await asyncio.wait_for(
        asyncio.gather(
            client.post("/taxo-cards/redeem", json={"code": code}, headers=first["headers"]),
            client.post("/taxo-cards/redeem", json={"code": code}, headers=second["headers"]),
        ),
        timeout=30,
    )
    assert Counter(r.status_code for r in responses) == Counter({200: 1, 422: 1})
    loser = next(r for r in responses if r.status_code == 422)
    assert loser.json()["code"] == "taxo_card_rejected" and "استُعملت" in loser.json()["message"]
    async with session_factory() as session:
        entries = await session.scalar(
            select(func.count()).select_from(WalletTransaction).where(WalletTransaction.type == WalletTransactionType.TAXO_CARD)
        )
    assert entries == 1
