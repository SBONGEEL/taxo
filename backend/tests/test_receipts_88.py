"""إيصالاتُ PDF (SPEC §٨٨/٢، C7) — لدفعةٍ معتمدةٍ لصاحبها وحدَه، والرابطُ مرّةً واحدة."""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest
from httpx import AsyncClient

from tests.helpers import rider_session
from tests.payment_fakes import add_gateway_method, install_transport
from tests.test_dz_payments_82 import _deliver
from tests.test_payment_protection_87 import _open
from tests.test_payment_requests import ALGERIAN_RIDER, algeria_market

pytestmark = pytest.mark.asyncio


async def test_an_approved_topup_has_a_one_time_pdf_receipt_for_its_owner_only(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    request = await _open(client, rider["headers"], method_id)

    early = await client.post(f"/payment-requests/{request['id']}/receipt-link", headers=rider["headers"])
    assert early.status_code == 422, early.text  # لم تُعتمد بعد

    chargily.status[request["reference"]] = "paid"
    await _deliver(client, request["reference"])
    link = await client.post(f"/payment-requests/{request['id']}/receipt-link", headers=rider["headers"])
    assert link.status_code == 200, link.text
    path = urlsplit(link.json()["url"]).path
    path = path[path.index("/payment-requests/"):]
    pdf = await client.get(path)
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF") and len(pdf.content) > 1000
    assert (await client.get(path)).status_code == 404  # مرّةً واحدة

    other = await rider_session(client, {**ALGERIAN_RIDER, "phone": ALGERIAN_RIDER["phone"][:-3] + "777"})
    assert (await client.post(f"/payment-requests/{request['id']}/receipt-link", headers=other["headers"])).status_code == 404
