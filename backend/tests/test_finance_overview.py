"""«المالية العامة» (SPEC §٧٤-أ/٩) — **كلُّ الدول متجاورةً، كلٌّ بعملته، ولا تُجمع العملاتُ إلا في المجموع التقريبيّ الموسوم**.

**ما يُقاس:**
١) **الصلاحيةُ المستقلّة** — المشرفُ الكاملُ بلا منحٍ يُردّ، والقارئُ يرى الدولَ الثلاث كلّاً بعملته **وحكماً واحداً على المطابقة**.
٢) **بلا سعرٍ لا مجموع** — ومع الأسعار مجموعٌ = Σ (مبلغُ الدولة × سعرُ عملتها) بخانتين، **موسوماً «تقريبي — بسعر صرف تضعه الإدارة»**.
٣) **عملةٌ لها مبلغٌ ولا سعرَ لها تُسمّى** ولا يُرسم المجموعُ كاملاً بصفرٍ مكانها.
٤) **رقمُ الدولة هنا هو رقمُ «مالية الدولة» حرفاً** — بانٍ واحد.
٥) **كلُّ عرضٍ وتصديرٍ وضبطِ سعرٍ سطرٌ في التدقيق.**
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from tests.helpers import rider_session, topup_wallet
from tests.test_finance_summary import finance_reader

pytestmark = pytest.mark.asyncio


def _metric(country: dict, key: str) -> dict:
    return next(metric for group in country["groups"] for metric in group["metrics"] if metric["key"] == key)


async def test_the_overview_needs_the_separate_permission(client: AsyncClient, admin_headers: dict) -> None:
    for path in ("/admin/finance/overview", "/admin/finance/rates", "/admin/finance/overview/export"):
        answer = await client.get(path, headers=admin_headers)
        assert answer.status_code == 403, (path, answer.text)


async def test_every_country_side_by_side_in_its_own_currency(client: AsyncClient, admin_headers: dict) -> None:
    reader = await finance_reader(client, admin_headers)
    body = (await client.get("/admin/finance/overview", headers=reader["headers"])).json()
    currencies = {country["window"]["country_code"]: country["window"]["currency"] for country in body["countries"]}
    assert currencies == {"JO": "JOD", "LY": "LYD", "DZ": "DZD"}
    assert body["reconciled"] is True
    assert body["combined"] is None, "بلا سعر صرفٍ لا مجموعَ يجمع عملتين"


async def test_the_country_column_is_the_country_page_itself(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None
) -> None:
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "12.500")
    reader = await finance_reader(client, admin_headers)
    overview = (await client.get("/admin/finance/overview", headers=reader["headers"])).json()
    page = (await client.get("/admin/finance/summary", params={"country_code": "JO"}, headers=reader["headers"])).json()
    jordan = next(country for country in overview["countries"] if country["window"]["country_code"] == "JO")
    assert jordan["groups"] == page["groups"]
    assert _metric(jordan, "topups")["amount"] == "12.500"


async def test_the_combined_total_is_approximate_and_names_what_it_lacks(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_wallet: None
) -> None:
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "10.000")
    reader = await finance_reader(client, admin_headers)

    # **سعرُ الأردن وحدَه**: المجموعُ بالدولار = 10 × 1.41 = 14.10
    rates = await client.put(
        "/admin/finance/rates", json={"reference": "usd", "rates": [{"currency": "JOD", "rate": "1.41"}]}, headers=reader["headers"]
    )
    assert rates.status_code == 200, rates.text
    assert rates.json()["reference"] == "USD"
    body = (await client.get("/admin/finance/overview", headers=reader["headers"])).json()
    combined = body["combined"]
    assert combined["reference"] == "USD" and combined["note"] == "تقريبي — بسعر صرف تضعه الإدارة"
    topups = next(metric for metric in combined["metrics"] if metric["key"] == "topups")
    assert topups["approx_value"] == "14.10" and topups["missing"] == []
    assert combined["rates"][0]["currency"] == "JOD"

    # **والسعرُ الأحدثُ يحكم، والقديمُ يبقى في التاريخ**
    await client.put(
        "/admin/finance/rates", json={"reference": "USD", "rates": [{"currency": "JOD", "rate": "1.40"}]}, headers=reader["headers"]
    )
    body = (await client.get("/admin/finance/overview", headers=reader["headers"])).json()
    assert next(m for m in body["combined"]["metrics"] if m["key"] == "topups")["approx_value"] == "14.00"

    # **عملةٌ لها مبلغٌ بلا سعرٍ تُسمّى** — والمجموعُ لا يُرسم كاملاً
    await client.put(
        "/admin/finance/rates", json={"reference": "EUR", "rates": [{"currency": "DZD", "rate": "0.0068"}]}, headers=reader["headers"]
    )
    body = (await client.get("/admin/finance/overview", headers=reader["headers"])).json()
    topups = next(m for m in body["combined"]["metrics"] if m["key"] == "topups")
    assert body["combined"]["reference"] == "EUR"
    assert topups["approx_value"] is None and topups["missing"] == ["JOD"]

    async with session_factory() as session:
        rows = (await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "exchange_rates"))).all()
    assert len(rows) == 3


async def test_a_zero_or_bad_rate_is_refused(client: AsyncClient, admin_headers: dict) -> None:
    reader = await finance_reader(client, admin_headers)
    for body in (
        {"reference": "USD", "rates": [{"currency": "JOD", "rate": "0"}]},
        {"reference": "US", "rates": [{"currency": "JOD", "rate": "1.4"}]},
        {"reference": "U$D", "rates": [{"currency": "JOD", "rate": "1.4"}]},
    ):
        answer = await client.put("/admin/finance/rates", json=body, headers=reader["headers"])
        assert answer.status_code == 422, (body, answer.text)


async def test_every_view_and_export_is_audited(client: AsyncClient, admin_headers: dict, session_factory) -> None:
    reader = await finance_reader(client, admin_headers)
    assert (await client.get("/admin/finance/overview", headers=reader["headers"])).status_code == 200
    exported = await client.get("/admin/finance/overview/export", headers=reader["headers"])
    assert exported.status_code == 200
    assert exported.content[:2] == b"PK"
    async with session_factory() as session:
        rows = (
            await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "finance_summary"))
        ).all()
    views = [(row.details["view"], row.details["export"]) for row in rows if row.details.get("view") == "overview"]
    assert views == [("overview", False), ("overview", True)]
