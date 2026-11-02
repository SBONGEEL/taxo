"""مثالُ التسعير في اللوحة وخاناتُ العرض (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §٥ و§٧٣-ج/٧).

- **المثالُ بدوالّ الرحلة نفسِها**: أسطرُه تساوي `fare_breakdown` حرفاً، ومجموعُه كجمع `_final_fare`.
- **والمسوّدةُ لا تُكتب**: مثالٌ بقيمٍ لم تُحفظ يترك الصفَّ المحفوظ كما هو.
- **وخاناتُ العرض لا تنزل عن خانات المال ولا تمسّ مبلغاً**: الأردنيُّ ٣ لا يُضبط ٢، والجزائريُّ يُرفع إلى ٢ للعرض وحدَه.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.currency import CURRENCY_DECIMALS
from app.models.enums import CountryCode, Currency
from app.models.pricing import PricingRule
from app.services import pricing
from app.services.directions import Route

DRAFT = {
    "base_fare": "1.000",
    "price_per_km": "0.250",
    "price_per_min": "0.050",
    "minimum_fare": "2.000",
    "cancellation_fee": "0.500",
    "stop_fee": "0.200",
    "stop_free_minutes": 3,
    "stop_price_per_min": "0.100",
    "stop_max_wait_minutes": 0,
    "pause_price_per_min": "0.100",
    "arrival_free_minutes": 5,
    "pause_max_minutes": 0,
}


async def test_the_example_is_the_real_formula_line_by_line(client, admin_headers, jordan_settings) -> None:
    response = await client.post(
        "/admin/settings/pricing/example",
        headers=admin_headers,
        json={
            "country_code": "JO",
            "vehicle_category": "economy",
            "distance_km": "10",
            "duration_min": "15",
            "stops": 1,
            "wait_minutes_per_stop": "8",
            "pause_minutes": "4",
            "arrival_wait_minutes": "6",
            "draft": DRAFT,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # **والسطورُ هي `fare_breakdown` نفسُها** — لا صيغةَ ثانيةَ في الباب
    rule = PricingRule(country_code=CountryCode.JO, vehicle_category="economy", **{
        key: Decimal(value) if isinstance(value, str) else value for key, value in DRAFT.items()
    })
    fare, minimum, lines = pricing.fare_breakdown(rule, Route(distance_km=Decimal(10), duration_min=Decimal(15)), 1)
    assert body["fare"] == str(fare) == "4.450"  # 1 + 10×0.25 + 15×0.05 + محطةٌ 0.2
    assert body["minimum_fare_applied"] is minimum is False
    assert [(line["kind"], line["amount"]) for line in body["lines"]] == [(line.kind, str(line.amount)) for line in lines]

    assert body["waiting_charge"] == "0.500"  # (8 − 3) × 0.1
    assert body["pause_charge"] == "0.400"  # 4 × 0.1 — الوقفةُ بلا مهلة
    assert body["arrival_charge"] == "0.100"  # (6 − 5) × 0.1
    assert body["total"] == "5.450"
    assert body["rounding_enabled"] is False and body["payable"] == body["total"]


async def test_a_short_trip_shows_the_minimum_as_its_own_line(client, admin_headers, jordan_settings) -> None:
    body = (
        await client.post(
            "/admin/settings/pricing/example",
            headers=admin_headers,
            json={"country_code": "JO", "vehicle_category": "economy", "distance_km": "1", "duration_min": "2"},
        )
    ).json()
    # المحفوظ: 1 + 0.5 + 0.2 = 1.700 < 2.000
    assert body["fare"] == "2.000" and body["minimum_fare_applied"] is True
    assert body["lines"][-1] == {"kind": "minimum", "amount": "0.300", "quantity": None}


async def test_a_draft_example_writes_nothing(client, admin_headers, jordan_settings) -> None:
    before = (await client.get("/admin/settings/pricing?country_code=JO", headers=admin_headers)).json()
    response = await client.post(
        "/admin/settings/pricing/example",
        headers=admin_headers,
        json={
            "country_code": "JO",
            "vehicle_category": "economy",
            "distance_km": "5",
            "duration_min": "10",
            "draft": {"price_per_km": "9.000"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["fare"] == "47.000"  # 1 + 5×9 + 10×0.1
    after = (await client.get("/admin/settings/pricing?country_code=JO", headers=admin_headers)).json()
    assert [rule["price_per_km"] for rule in after] == [rule["price_per_km"] for rule in before]


async def test_no_saved_rule_and_no_draft_is_refused_with_the_fields(client, admin_headers) -> None:
    response = await client.post(
        "/admin/settings/pricing/example",
        headers=admin_headers,
        json={"country_code": "DZ", "vehicle_category": "economy", "distance_km": "5", "duration_min": "10"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_input"


async def test_algeria_example_is_in_whole_dinars(client, admin_headers) -> None:
    draft = {**DRAFT, "base_fare": "150", "price_per_km": "45", "price_per_min": "7", "minimum_fare": "200",
             "stop_fee": "0", "stop_price_per_min": "0", "pause_price_per_min": "0"}
    body = (
        await client.post(
            "/admin/settings/pricing/example",
            headers=admin_headers,
            json={"country_code": "DZ", "vehicle_category": "economy", "distance_km": "6.4", "duration_min": "13",
                  "draft": draft},
        )
    ).json()
    assert body["currency"] == Currency.DZD.value
    # 150 + 6.4×45 (288) + 13×7 (91) = 529 — **دينارٌ صحيح**
    assert body["fare"] == "529"


async def test_display_decimals_default_to_the_currency_and_never_go_below_it(client, admin_headers) -> None:
    for country, currency in (("JO", Currency.JOD), ("DZ", Currency.DZD), ("LY", Currency.LYD)):
        read = (await client.get(f"/admin/settings/display-decimals/{country}", headers=admin_headers)).json()
        assert read["display_decimals"] == read["currency_decimals"] == CURRENCY_DECIMALS[currency]

    refused = await client.put("/admin/settings/display-decimals/JO", headers=admin_headers, json={"decimals": 2})
    assert refused.status_code == 422, refused.text
    assert (await client.put("/admin/settings/display-decimals/DZ", headers=admin_headers, json={"decimals": 4})).status_code == 422

    raised = await client.put("/admin/settings/display-decimals/DZ", headers=admin_headers, json={"decimals": 2})
    assert raised.status_code == 200, raised.text
    assert raised.json() == {"country_code": "DZ", "display_decimals": 2, "currency_decimals": 0}

    # **والنشرُ يحمل الاثنين**: الرسمُ بخانتين، والإدخالُ والسلكُ بخانات المال كما كانا
    config = (await client.get("/config")).json()
    dz = next(c for c in config["countries"] if c["country_code"] == "DZ")
    assert (dz["display_decimals"], dz["currency_decimals"]) == (2, 0)


async def test_support_reads_display_decimals_but_cannot_write(client, support_headers) -> None:
    assert (await client.get("/admin/settings/display-decimals/JO", headers=support_headers)).status_code == 200
    assert (
        await client.put("/admin/settings/display-decimals/DZ", headers=support_headers, json={"decimals": 1})
    ).status_code == 403
