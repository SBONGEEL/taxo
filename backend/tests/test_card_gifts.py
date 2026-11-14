"""بطاقاتُ الهدية بالكشط (SPEC §١٠٠-أ/٣، أمرُ المالك ٢٠٢٦-١١-١٣ البند ٣).

**الرمزُ معمًّى حتى يُكشط ثمّ يُمحى** · **الكشطُ مرّةً واحدةً ولو تزامن** · **الرابطُ لا يُخزَّن** · **ولا رمزَ في تدقيقٍ ولا في ردٍّ قبل
الكشط** · الإلغاءُ بسببٍ مكتوب · والحالُ بأوقاتها حتى الاستعمال.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.models.taxo_card import CardBatch, CardGiftLink, TaxoCard
from app.services import card_gifts
from tests.helpers import rider_session
from tests.test_taxo_cards import ALGERIAN_RIDER, card_market, card_pepper, redeem  # noqa: F401


async def _denomination(client: AsyncClient, admin_headers: dict) -> str:
    made = await client.post("/admin/taxo-cards/denominations", json={"country_code": "DZ", "amount": "1000"}, headers=admin_headers)
    if made.status_code == 201:
        return made.json()["id"]
    return (await client.get("/admin/taxo-cards/denominations?country=DZ", headers=admin_headers)).json()[0]["id"]


async def make_gift(client: AsyncClient, admin_headers: dict, *, delivery: str = "link", design: str = "night", **extra) -> dict:
    body = {
        "country_code": "DZ", "denomination_id": await _denomination(client, admin_headers), "design": design,
        "delivery": delivery, "expires_at": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
        "recipient_name": "سارة", "message": "كلُّ عامٍ وأنتِ بخير",
    } | extra
    made = await client.post("/admin/taxo-cards/gifts", json=body, headers=admin_headers)
    assert made.status_code == 201, made.text
    return made.json()


def token_of(created: dict) -> str:
    url = created["url"]
    assert url.startswith("https://taxo.tajora.ly/gift#")
    return url.split("#", 1)[1]


async def test_a_link_gift_keeps_only_an_encrypted_code_and_no_link(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    created = await make_gift(client, admin_headers)
    token = token_of(created)
    assert created["code"] is None and created["serial"].startswith("DZ-G")
    assert created["gift"]["state"] == "created" and created["gift"]["design"] == "night"
    async with session_factory() as session:
        card = await session.scalar(select(TaxoCard).where(TaxoCard.serial == created["serial"]))
        link = await session.scalar(select(CardGiftLink))
        batch = await session.get(CardBatch, card.batch_id)
        assert batch.kind == "gift" and batch.quantity == 1
        # **الرمزُ معمًّى لا نصّ**، والرابطُ بصمتُه وحدَها
        assert card.code_envelope and "ciphertext" in card.code_envelope
        assert link.token_hash == card_gifts.token_hash(token) and token not in str(link.__dict__)
        audit_text = str((await session.scalars(select(AdminAuditLog.details))).all())
        assert token not in audit_text


async def test_open_shows_the_gift_without_its_code(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    created = await make_gift(client, admin_headers, design="sunrise")
    opened = await client.post("/public/gift/open", json={"token": token_of(created)})
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["amount"] == "1000" and body["currency"] == "DZD" and body["design"] == "sunrise"
    assert body["recipient_name"] == "سارة" and body["state"] == "opened" and "code" not in body
    again = await client.post("/public/gift/open", json={"token": token_of(created)})
    assert again.status_code == 200
    listed = (await client.get("/admin/taxo-cards/gifts?country=DZ", headers=admin_headers)).json()
    assert listed[0]["state"] == "opened" and listed[0]["open_count"] == 2 and listed[0]["opened_at"]


async def test_scratch_reveals_once_wipes_the_copy_and_the_code_redeems(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    created = await make_gift(client, admin_headers)
    token = token_of(created)
    scratched = await client.post("/public/gift/scratch", json={"token": token})
    assert scratched.status_code == 200, scratched.text
    code = scratched.json()["code"]
    assert len(code.replace("-", "")) == 16
    twice = await client.post("/public/gift/scratch", json={"token": token})
    assert twice.status_code == 409 and "كُشطت" in twice.text
    async with session_factory() as session:
        card = await session.scalar(select(TaxoCard).where(TaxoCard.serial == created["serial"]))
        assert card.code_envelope is None  # **مُحي بعد الكشط**
        rows = (await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "card_gift_link"))).all()
        assert any(row.details.get("action") == "scratch" for row in rows)
        assert code not in str([row.details for row in rows]) and code.replace("-", "") not in str([row.details for row in rows])
    rider = await rider_session(client, ALGERIAN_RIDER)
    used = await redeem(client, rider["headers"], code)
    assert used.status_code == 200, used.text
    listed = (await client.get("/admin/taxo-cards/gifts?country=DZ", headers=admin_headers)).json()
    assert listed[0]["state"] == "redeemed" and listed[0]["redeemed_at"]


async def test_two_scratches_at_once_reveal_the_code_once(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    """**ما يملكه قفلُ صفِّ الرابط**: بلا القفل يقرأ الكشطان «لم يُكشط» معاً ويخرج الرمزُ مرّتين."""
    await card_market(session_factory)
    token = token_of(await make_gift(client, admin_headers))
    results = await asyncio.wait_for(
        asyncio.gather(*[client.post("/public/gift/scratch", json={"token": token}) for _ in range(3)]), timeout=30
    )
    assert Counter(r.status_code for r in results) == Counter({200: 1, 409: 2})
    assert all(r.json()["code"] == "gift_unavailable" for r in results if r.status_code == 409)


async def test_a_cancelled_gift_cannot_be_scratched_and_needs_a_reason(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    created = await make_gift(client, admin_headers)
    gift_id = created["gift"]["id"]
    assert (await client.post(f"/admin/taxo-cards/gifts/{gift_id}/cancel", json={"reason": ""}, headers=admin_headers)).status_code == 422
    done = await client.post(f"/admin/taxo-cards/gifts/{gift_id}/cancel", json={"reason": "أُرسلت لرقمٍ خاطئ"}, headers=admin_headers)
    assert done.status_code == 200 and done.json()["state"] == "cancelled"
    refused = await client.post("/public/gift/scratch", json={"token": token_of(created)})
    assert refused.status_code == 409 and "أُلغيت" in refused.text
    async with session_factory() as session:
        card = await session.scalar(select(TaxoCard).where(TaxoCard.serial == created["serial"]))
        assert card.status.value == "cancelled" and card.code_envelope is None
    again = await client.post(f"/admin/taxo-cards/gifts/{gift_id}/cancel", json={"reason": "مرّةً ثانية"}, headers=admin_headers)
    assert again.status_code == 409


async def test_sent_is_recorded_by_channel(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    created = await make_gift(client, admin_headers)
    sent = await client.post(f"/admin/taxo-cards/gifts/{created['gift']['id']}/sent", json={"channel": "whatsapp"}, headers=admin_headers)
    assert sent.status_code == 200 and sent.json()["state"] == "sent" and sent.json()["sent_channel"] == "whatsapp"
    bad = await client.post(f"/admin/taxo-cards/gifts/{created['gift']['id']}/sent", json={"channel": "fax"}, headers=admin_headers)
    assert bad.status_code == 422


async def test_unknown_links_are_refused_and_rate_limited(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    headers = {"x-forwarded-for": "203.0.113.77"}
    statuses = [
        (await client.post("/public/gift/scratch", json={"token": f"not-a-real-token-{i:04d}"}, headers=headers)).status_code
        for i in range(12)
    ]
    assert statuses[:10] == [404] * 10 and statuses[10:] == [429, 429]


async def test_a_print_gift_returns_its_code_once_and_prints_with_a_scratch_area(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    created = await make_gift(client, admin_headers, delivery="print", design="city")
    assert created["url"] is None and created["gift"] is None and created["code"]["serial"] == created["serial"]
    async with session_factory() as session:
        card = await session.scalar(select(TaxoCard).where(TaxoCard.serial == created["serial"]))
        assert card.code_envelope is None  # **المطبوعةُ لا تُخزّن رمزاً**
    password = "gift-pass-" + "2026"
    printed = await client.post(
        f"/admin/taxo-cards/batches/{created['batch_id']}/export",
        json={"format": "gift", "design": "city", "password": password, "codes": [created["code"]]}, headers=admin_headers,
    )
    assert printed.status_code == 200, printed.text
    assert printed.content.startswith(b"%PDF") and b"/Encrypt" in printed.content
    # **وصيغةُ الهدية لا تُطبع بها دفعةٌ عاديّة، ولا العكس**
    wrong = await client.post(
        f"/admin/taxo-cards/batches/{created['batch_id']}/export",
        json={"format": "sheet", "password": password, "codes": [created["code"]]}, headers=admin_headers,
    )
    assert wrong.status_code == 422


@pytest.mark.parametrize("field,value", [("design", "neon"), ("delivery", "pigeon")])
async def test_unknown_design_or_delivery_is_refused(client: AsyncClient, session_factory, admin_headers: dict, field: str, value: str) -> None:
    await card_market(session_factory)
    body = {
        "country_code": "DZ", "denomination_id": await _denomination(client, admin_headers), "design": "night", "delivery": "link",
        "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
    } | {field: value}
    assert (await client.post("/admin/taxo-cards/gifts", json=body, headers=admin_headers)).status_code == 422


async def test_gifts_need_a_finance_session(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = {
        "country_code": "DZ", "denomination_id": await _denomination(client, admin_headers), "design": "night",
        "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
    }
    assert (await client.post("/admin/taxo-cards/gifts", json=body)).status_code in (401, 403)
