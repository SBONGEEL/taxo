"""صفحةُ «دفعات البطاقات» (SPEC §١٠٠-أ/٢، أمرُ المالك ٢٠٢٦-١١-١٣) — العدُّ بالحال الأربع، وبطاقاتُ الدفعة بلا رمز، والبحث والترشيح والإلغاء."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import update

from app.models.taxo_card import CardBatch
from tests.helpers import rider_session
from tests.test_payment_requests import ALGERIAN_RIDER
from tests.test_taxo_cards import card_market, card_pepper, issue, redeem  # noqa: F401


async def _cards(client: AsyncClient, headers: dict, batch_id: str, **query) -> dict:
    response = await client.get(f"/admin/taxo-cards/batches/{batch_id}/cards", params=query, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_batch_lists_its_cards_by_state_without_any_code(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=4)
    batch_id = body["batch"]["id"]
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await redeem(client, rider["headers"], body["codes"][0]["code"])).status_code == 200
    second = (await _cards(client, admin_headers, batch_id, q="000002"))["cards"][0]
    assert (await client.post(f"/admin/taxo-cards/cards/{second['id']}/cancel", json={"reason": "ضاعت"}, headers=admin_headers)).status_code == 200

    listed = await _cards(client, admin_headers, batch_id)
    assert listed["total"] == 4
    states = {card["serial"][-6:]: card["state"] for card in listed["cards"]}
    assert states == {"000001": "redeemed", "000002": "cancelled", "000003": "unused", "000004": "unused"}
    used = listed["cards"][0]
    assert used["redeemed_by_name"] and used["redeemed_at"]
    # **ولا رمزَ في أيِّ ردّ** — لا حقلَ ولا قيمة
    raw = str(listed)
    assert "code" not in listed["cards"][0] and not any(row["code"] in raw or row["code"].replace("-", "") in raw for row in body["codes"])

    # البحثُ باسم من استعملها، والترشيحُ بالحال
    by_name = await _cards(client, admin_headers, batch_id, q=used["redeemed_by_name"][:3])
    assert [card["serial"] for card in by_name["cards"]] == [used["serial"]]
    assert (await _cards(client, admin_headers, batch_id, state="unused"))["total"] == 2
    assert (await _cards(client, admin_headers, batch_id, state="expired"))["total"] == 0

    batch = (await client.get("/admin/taxo-cards/batches?country=DZ", headers=admin_headers)).json()[0]
    assert (batch["unused"], batch["redeemed"], batch["expired"], batch["cancelled"]) == (2, 1, 0, 1)


async def test_unused_cards_of_a_lapsed_batch_read_expired(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=2)
    async with session_factory() as session:
        await session.execute(
            update(CardBatch).where(CardBatch.id == body["batch"]["id"]).values(expires_at=CardBatch.valid_from + timedelta(seconds=1))
        )
        await session.commit()
    batch = (await client.get("/admin/taxo-cards/batches?country=DZ", headers=admin_headers)).json()[0]
    assert (batch["unused"], batch["expired"], batch["active"]) == (0, 2, 2)
    assert (await _cards(client, admin_headers, body["batch"]["id"], state="expired"))["total"] == 2
    assert (await _cards(client, admin_headers, body["batch"]["id"], state="unused"))["total"] == 0


async def test_the_page_needs_a_panel_session(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    body = await issue(client, admin_headers, quantity=1)
    refused = await client.get(f"/admin/taxo-cards/batches/{body['batch']['id']}/cards")
    assert refused.status_code in (401, 403)
