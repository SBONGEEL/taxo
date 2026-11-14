"""بطاقاتُ الشركات بفاتورة (SPEC §١٠٠-ب/٧، أمرُ المالك ٢٠٢٦-١١-١٢ البند ٧).

**الدفعةُ تُعلَّم بالشركة ورقمِ فاتورةٍ متتابعٍ في سوقها** · **بلا محلّ** · **الفاتورةُ بلا رمز** · **وبياناتُ البائع يكتبها المالك وحدَه**.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.test_card_sellers import _owner
from tests.test_taxo_cards import card_market, card_pepper  # noqa: F401

pytestmark = pytest.mark.asyncio


async def _denomination(client: AsyncClient, admin_headers: dict) -> str:
    made = await client.post("/admin/taxo-cards/denominations", json={"country_code": "DZ", "amount": "1000"}, headers=admin_headers)
    assert made.status_code == 201, made.text
    return made.json()["id"]


def _body(denom: str, **extra) -> dict:
    start = datetime.now(UTC) - timedelta(minutes=1)
    return {
        "country_code": "DZ", "denomination_id": denom, "quantity": 3, "valid_from": start.isoformat(),
        "expires_at": (start + timedelta(days=180)).isoformat(),
    } | extra


async def test_a_corporate_batch_carries_the_company_and_a_sequential_invoice(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    denom = await _denomination(client, admin_headers)
    first = await client.post("/admin/taxo-cards/batches", json=_body(
        denom, buyer_company="شركةُ الأفق للنقل", buyer_tax_number="123456789"), headers=admin_headers)
    assert first.status_code == 201, first.text
    batch = first.json()["batch"]
    assert batch["buyer_company"] == "شركةُ الأفق للنقل" and batch["invoice_number"] == "INV-DZ-000001"
    assert batch["shop_id"] is None
    plain = await client.post("/admin/taxo-cards/batches", json=_body(denom), headers=admin_headers)
    assert plain.json()["batch"]["invoice_number"] is None
    second = await client.post("/admin/taxo-cards/batches", json=_body(denom, buyer_company="مؤسّسةُ النخيل"), headers=admin_headers)
    assert second.json()["batch"]["invoice_number"] == "INV-DZ-000002"

    invoice = await client.get(f"/admin/taxo-cards/batches/{batch['id']}/invoice", headers=admin_headers)
    assert invoice.status_code == 200 and invoice.content.startswith(b"%PDF")
    assert "INV-DZ-000001.pdf" in invoice.headers["content-disposition"]
    codes = [row["code"] for row in first.json()["codes"]]
    assert not any(code.encode() in invoice.content or code.replace("-", "").encode() in invoice.content for code in codes)
    none = await client.get(f"/admin/taxo-cards/batches/{plain.json()['batch']['id']}/invoice", headers=admin_headers)
    assert none.status_code == 422


async def test_a_corporate_batch_has_no_shop(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    denom = await _denomination(client, admin_headers)
    shop = await client.post("/admin/taxo-cards/shops", json={
        "country_code": "DZ", "name": "مكتبةُ الأمل", "discount_percent": "5", "payment_mode": "after_sale"}, headers=admin_headers)
    refused = await client.post("/admin/taxo-cards/batches", json=_body(
        denom, shop_id=shop.json()["id"], buyer_company="شركةُ الأفق"), headers=admin_headers)
    assert refused.status_code == 422


async def test_only_the_owner_writes_the_seller_on_the_invoice(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    owner = await _owner(session_factory)
    body = {"country_code": "DZ", "invoice_seller_name": "اسمٌ تجريبيّ", "invoice_seller_tax_number": "000"}
    assert (await client.put("/admin/taxo-cards/invoice-settings", json=body, headers=admin_headers)).status_code == 403
    saved = await client.put("/admin/taxo-cards/invoice-settings", json=body, headers=owner)
    assert saved.status_code == 200 and saved.json()["invoice_seller_name"] == "اسمٌ تجريبيّ"
    read = (await client.get("/admin/taxo-cards/invoice-settings?country=DZ", headers=admin_headers)).json()
    assert read["invoice_seller_tax_number"] == "000"
