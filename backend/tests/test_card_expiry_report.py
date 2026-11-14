"""الصلاحيةُ والتقرير (SPEC §١٠٠-ب/١٢ و١٤).

**التذكيرُ يرى ما ينتهي قريباً وفيه غيرُ مستعمَل** · **التمديدُ إلى الأمام وحدَه وبسببٍ مكتوبٍ ومدقَّق، والبطاقةُ تعمل بعده** ·
**التقريرُ بالنوع جمعُ أرقام الدفعات نفسِها**: الالتزامُ القائم وقيمةُ المنتهية بلا استعمال ونسبةُ الاستعمال.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.audit import AdminAuditLog
from app.models.taxo_card import CardBatch
from tests.helpers import rider_session
from tests.test_taxo_cards import ALGERIAN_RIDER, card_market, card_pepper, issue, redeem  # noqa: F401

pytestmark = pytest.mark.asyncio


async def test_an_expiring_batch_is_listed_and_extended_with_a_reason(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await card_market(session_factory)
    soon = await issue(client, admin_headers, quantity=2, lasts=timedelta(days=10))
    later = await issue(client, admin_headers, quantity=2, lasts=timedelta(days=200))
    listed = (await client.get("/admin/taxo-cards/expiring?country=DZ&days=30", headers=admin_headers)).json()
    assert [row["id"] for row in listed] == [soon["batch"]["id"]]
    assert later["batch"]["id"] not in {row["id"] for row in listed}

    batch_id = soon["batch"]["id"]
    old = datetime.fromisoformat(soon["batch"]["expires_at"])
    backward = await client.post(f"/admin/taxo-cards/batches/{batch_id}/extend", json={
        "expires_at": (old - timedelta(days=1)).isoformat(), "reason": "خطأ"}, headers=admin_headers)
    assert backward.status_code == 422
    no_reason = await client.post(f"/admin/taxo-cards/batches/{batch_id}/extend", json={
        "expires_at": (old + timedelta(days=60)).isoformat(), "reason": ""}, headers=admin_headers)
    assert no_reason.status_code == 422
    extended = await client.post(f"/admin/taxo-cards/batches/{batch_id}/extend", json={
        "expires_at": (old + timedelta(days=60)).isoformat(), "reason": "طلبُ المحلّ قبل العيد"}, headers=admin_headers)
    assert extended.status_code == 200, extended.text
    assert datetime.fromisoformat(extended.json()["expires_at"]) > old
    async with session_factory() as session:
        rows = (await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "card_batch"))).all()
        assert any((row.details or {}).get("action") == "extend" for row in rows)
    assert batch_id not in {row["id"] for row in (await client.get("/admin/taxo-cards/expiring?country=DZ&days=30", headers=admin_headers)).json()}


async def test_an_expired_card_works_again_after_an_extension(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    batch = await issue(client, admin_headers, quantity=1, lasts=timedelta(days=30))
    batch_id = batch["batch"]["id"]
    code = batch["codes"][0]["code"]
    async with session_factory() as session:
        await session.execute(update(CardBatch).where(CardBatch.id == batch_id).values(valid_from=datetime.now(UTC) - timedelta(hours=2), expires_at=datetime.now(UTC) - timedelta(hours=1)))
        await session.commit()
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await redeem(client, rider["headers"], code)).status_code == 409
    extended = await client.post(f"/admin/taxo-cards/batches/{batch_id}/extend", json={
        "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(), "reason": "بطاقةُ عميلٍ انتهت قبل أن يشحن"},
        headers=admin_headers)
    assert extended.status_code == 200, extended.text
    assert (await redeem(client, rider["headers"], code)).status_code == 200


async def test_the_kind_report_adds_up_the_batches(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    await card_market(session_factory)
    live = await issue(client, admin_headers, quantity=3, lasts=timedelta(days=90))
    lapsed = await issue(client, admin_headers, quantity=2, lasts=timedelta(days=90))
    async with session_factory() as session:
        await session.execute(
            update(CardBatch).where(CardBatch.id == lapsed["batch"]["id"]).values(valid_from=datetime.now(UTC) - timedelta(hours=2), expires_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await session.commit()
    rider = await rider_session(client, ALGERIAN_RIDER)
    assert (await redeem(client, rider["headers"], live["codes"][0]["code"])).status_code == 200
    report = {row["kind"]: row for row in (await client.get("/admin/taxo-cards/report/kinds?country=DZ", headers=admin_headers)).json()}
    printed = report["batch"]
    assert printed["batches"] == 2 and printed["cards"] == 5 and printed["redeemed"] == 1
    assert printed["unused"] == 2 and printed["expired"] == 2
    assert printed["issued_amount"] == "5000" and printed["redeemed_amount"] == "1000"
    assert printed["outstanding_amount"] == "2000" and printed["expired_amount"] == "2000"
    assert printed["redemption_rate"] == "20.0" and printed["currency"] == "DZD"
    assert report["gift"]["cards"] == 0 and report["pos"]["cards"] == 0 and report["corporate"]["cards"] == 0
