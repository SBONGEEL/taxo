"""**تقريبُ الأسعار وعرضُها من اللوحة** (أمرُ المالك ٢٠٢٦-١١-١٩، `design/OWNER-2026-11-19-FARE-ROUNDING.md` §٧) — الاختباراتُ السبعة:

١) كلُّ تركيبةٍ صحيحة ومنها الحوافّ (1.725 بخطوة 0.05 أعلى/أدنى/أقرب) · ٢) أجرةُ الأردن بالافتراضيّ مضاعفُ 0.05 دائماً ·
٣) التقديرُ = النهائيّةُ = المحصَّل · ٤) الجزائرُ وليبيا كما كانتا حرفاً · ٥) رحلةٌ جاريةٌ لا يمسّها تغييرُ الإعداد —
ومعها: الخاناتُ تلائم الخطوة وإلّا لا حفظ، والحفظُ في سجلّ التدقيق، والعرضُ لا يُخفي فلساً.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.models.enums import Currency, RoundingMode
from app.models.payment_setting import PaymentSetting
from app.services import fare_rounding, rounding
from app.services.rounding import FareSurface, RoundingPolicy
from tests.helpers import DRIVER, DROPOFF, PICKUP, approved_driver, bring_online, pay_ride, rider_session, set_commission
from tests.test_rounding import _complete, _drive, _requested, _route

D = Decimal
JORDAN = {
    "decimals": 2, "step": "0.050", "mode": "nearest",
    "on_estimate": True, "on_final": True, "on_negotiation": True, "on_cancellation": True,
}


def _policy(step: str, mode: str) -> RoundingPolicy:
    return RoundingPolicy(enabled=True, unit=D(step), mode=RoundingMode(mode))


# ------------------------------------------------------------------ ١) كلُّ تركيبة، والحوافّ


@pytest.mark.parametrize(
    ("step", "mode", "amount", "expected"),
    [
        # **أمثلةُ المالك** — الأردن خطوة 0.05 الأقرب
        ("0.05", "nearest", "1.720", "1.700"), ("0.05", "nearest", "1.730", "1.750"), ("0.05", "nearest", "1.780", "1.800"),
        # **الحافّةُ 1.725** بالاتجاهات الثلاثة — النصفُ للأعلى في «الأقرب»
        ("0.05", "nearest", "1.725", "1.750"), ("0.05", "up", "1.725", "1.750"), ("0.05", "down", "1.725", "1.700"),
        ("0.05", "nearest", "1.724", "1.700"), ("0.05", "up", "1.701", "1.750"), ("0.05", "down", "1.749", "1.700"),
        ("0.05", "up", "1.700", "1.700"), ("0.05", "down", "1.700", "1.700"),
        ("0.01", "nearest", "1.725", "1.730"), ("0.01", "down", "1.729", "1.720"), ("0.01", "up", "1.721", "1.730"),
        ("0.10", "nearest", "1.750", "1.800"), ("0.10", "nearest", "1.749", "1.700"), ("0.10", "up", "1.701", "1.800"),
        ("0.25", "nearest", "1.125", "1.250"), ("0.25", "down", "1.249", "1.000"), ("0.25", "up", "1.001", "1.250"),
        ("0.50", "nearest", "2.249", "2.000"), ("0.50", "nearest", "2.250", "2.500"), ("0.50", "up", "2.001", "2.500"),
        ("1", "nearest", "6.567", "7.000"), ("1", "nearest", "6.499", "6.000"), ("1", "down", "6.999", "6.000"),
        ("10", "nearest", "294.000", "290.000"), ("10", "nearest", "295.000", "300.000"), ("10", "up", "291.000", "300.000"),
        # **قيمةٌ مخصّصة**
        ("0.125", "nearest", "1.0625", "1.125"), ("0.2", "down", "1.399", "1.200"),
    ],
)
def test_every_step_and_direction_including_the_edges(step: str, mode: str, amount: str, expected: str) -> None:
    rounded, difference = rounding.round_amount(D(amount), _policy(step, mode))
    assert rounded == D(expected)
    assert difference == rounding.as_money(D(expected) - D(amount))


def test_without_a_step_the_fare_is_exact() -> None:
    assert rounding.round_amount(D("1.725"), rounding.DISABLED) == (D("1.725"), D("0.000"))


# ------------------------------------------------------------------ ٢) الأردن بالافتراضيّ مضاعفُ 0.05 دائماً


def test_a_jordan_fare_with_the_defaults_is_always_a_multiple_of_005() -> None:
    policy = _policy("0.05", "nearest")
    amount = D("0.001")
    while amount < D("60"):
        result = rounding.rounded(amount, policy)
        assert result % D("0.05") == 0, (amount, result)
        assert abs(result - amount) <= D("0.025"), (amount, result)
        amount += D("0.037")


# ------------------------------------------------------------------ الخاناتُ والخطوة، والعرض


@pytest.mark.parametrize(
    ("decimals", "step", "currency", "ok"),
    [
        (2, "0.05", Currency.JOD, True), (3, "0.05", Currency.JOD, True), (1, "0.05", Currency.JOD, False),
        (0, "0.05", Currency.JOD, False), (1, "0.5", Currency.JOD, True), (0, "1", Currency.LYD, True),
        (3, None, Currency.JOD, True), (2, None, Currency.JOD, False), (0, "10", Currency.DZD, True),
        (0, "0.5", Currency.DZD, False), (3, "0.0005", Currency.JOD, False), (0, None, Currency.DZD, True),
    ],
)
def test_the_decimals_must_fit_the_step(decimals: int, step: str | None, currency: Currency, ok: bool) -> None:
    message = rounding.fit_message(decimals, D(step) if step else None, currency)
    assert (message is None) is ok, message
    if not ok:
        assert any("؀" <= ch <= "ۿ" for ch in message), "رسالةٌ عربيّة"


def test_the_display_never_hides_a_non_zero_digit() -> None:
    assert fare_rounding.shown(D("1.750"), 2) == "1.75"
    assert fare_rounding.shown(D("1.725"), 2) == "1.725", "مبلغٌ قديمٌ بفلوسه لا يُقرَّب صامتاً في العرض"
    assert fare_rounding.shown(D("2.000"), 0) == "2"
    assert fare_rounding.shown(D("290.000"), 0) == "290"
    assert fare_rounding.shown(D("7.000"), 3) == "7.000"


def test_libya_shows_a_whole_fare_without_decimals_and_a_fraction_with_two() -> None:
    """**«8 د.ل» لا «8.000 د.ل»، و«8.50 د.ل» بكسر** (أمرُ المالك ٢٠٢٦-١١-١٩) — عرضٌ وحدَه، ولا تُخفى خانةٌ غيرُ صفريّة."""
    assert fare_rounding.shown(D("8.000"), 2, trim_whole=True) == "8"
    assert fare_rounding.shown(D("8.500"), 2, trim_whole=True) == "8.50"
    assert fare_rounding.shown(D("8.125"), 2, trim_whole=True) == "8.125"
    assert fare_rounding.shown(D("8.000"), 2) == "8.00", "بلا المفتاح لا يتغيّر شيء"
    assert rounding.fit_message(2, None, Currency.LYD, trim_whole=True) is None
    assert rounding.fit_message(2, None, Currency.LYD) is not None, "والقاعدةُ القديمةُ باقيةٌ لمن لم يختره"


async def test_the_trim_switch_is_saved_audited_and_served_in_config(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    saved = await client.put(
        "/admin/settings/fare-rounding/JO", json={**JORDAN, "trim_whole": True}, headers=admin_headers
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["trim_whole"] is True
    async with session_factory() as session:
        row = await session.scalar(
            select(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "market_display_decimals")
            .order_by(AdminAuditLog.created_at.desc())
        )
    assert row is not None and row.details["changes"]["display_trim_whole"] == {"from": False, "to": True}
    config = (await client.get("/config", params={"country": "JO"})).json()
    face = config.get("country") or config
    found = [face] if "display_trim_whole" in face else [c for c in config.get("countries", []) if c.get("country_code") == "JO"]
    assert found and found[0]["display_trim_whole"] is True, config


# ------------------------------------------------------------------ ٤) الجزائرُ وليبيا كما كانتا


@pytest.mark.parametrize(("unit", "mode"), [("10", "nearest"), ("1.000", "nearest"), ("0.500", "nearest"), ("0.250", "up")])
def test_the_seeded_fare_rounding_equals_the_rounding_it_replaces(unit: str, mode: str) -> None:
    """**الترحيلة `0176` تبذر تقريبَ الأجرة من العامّ صفّاً صفّاً** — فالأجرةُ في كلِّ سوقٍ كما كانت حرفاً (الجزائر 10 · ليبيا 1)."""
    setting = PaymentSetting(rounding_enabled=True, rounding_unit=D(unit), rounding_mode=mode)
    setting.fare_step, setting.fare_mode = setting.rounding_unit, setting.rounding_mode
    setting.fare_on_estimate = setting.fare_on_final = setting.fare_on_negotiation = setting.fare_on_cancellation = True
    old = rounding.policy_of(setting)
    for surface in FareSurface:
        new = rounding.fare_policy_of(setting, surface)
        amount = D("0.013")
        while amount < D("400"):
            assert rounding.rounded(amount, new) == rounding.rounded(amount, old), (surface, amount)
            amount += D("3.917")


def test_a_switched_off_surface_is_exact() -> None:
    setting = PaymentSetting(rounding_enabled=True, rounding_unit=D("0.500"), rounding_mode="nearest")
    setting.fare_step, setting.fare_mode = D("0.050"), "nearest"
    setting.fare_on_estimate, setting.fare_on_final, setting.fare_on_negotiation, setting.fare_on_cancellation = True, True, False, True
    assert rounding.fare_policy_of(setting, FareSurface.NEGOTIATION) == rounding.DISABLED
    assert rounding.fare_policy_of(setting, FareSurface.FINAL).unit == D("0.050")
    assert rounding.policy_of(setting).unit == D("0.500"), "التقريبُ العامُّ (الإكراميّات والشحن والاشتراكات) لم يُمسّ"


# ------------------------------------------------------------------ اللوحة: الحفظ والتدقيق والمعاينة


async def test_saving_refuses_decimals_that_do_not_fit_and_audits_what_it_saves(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    refused = await client.put("/admin/settings/fare-rounding/JO", json={**JORDAN, "decimals": 1}, headers=admin_headers)
    assert refused.status_code == 422, refused.text
    assert "خانتين" in refused.json()["message"] or "2" in refused.json()["message"]

    saved = await client.put("/admin/settings/fare-rounding/JO", json=JORDAN, headers=admin_headers)
    assert saved.status_code == 200, saved.text
    assert (saved.json()["decimals"], saved.json()["step"], saved.json()["mode"]) == (2, "0.050", "nearest")
    async with session_factory() as session:
        row = await session.scalar(
            select(AdminAuditLog).where(AdminAuditLog.entity_type == "fare_rounding").order_by(AdminAuditLog.created_at.desc())
        )
    assert row is not None and row.details["changes"]["step"] == {"from": None, "to": "0.050"}
    assert row.details["changes"]["decimals"]["to"] == 2



async def test_only_a_settings_writer_can_save(client: AsyncClient, jordan_settings: None) -> None:
    rider = await rider_session(client)
    denied = await client.put("/admin/settings/fare-rounding/JO", json=JORDAN, headers=rider["headers"])
    assert denied.status_code in (401, 403), denied.text


async def test_the_preview_shows_ten_fares_before_and_after_without_saving(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    preview = await client.post(
        "/admin/settings/fare-rounding/JO/preview", json={**JORDAN, "amount": "1.730"}, headers=admin_headers
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["fit_error"] is None
    assert (body["amount"]["after"], body["amount"]["after_text"]) == ("1.750", "1.75")
    assert len(body["samples"]) == 10
    for sample in body["samples"]:
        assert D(sample["after"]) % D("0.05") == 0
        assert sample["before"] == sample["precise"], "قبلُ: لا تقريبَ للأجرة في التطوير"
    bad = await client.post(
        "/admin/settings/fare-rounding/JO/preview", json={**JORDAN, "decimals": 1}, headers=admin_headers
    )
    assert bad.status_code == 200 and bad.json()["fit_error"]
    async with session_factory() as session:
        setting = await session.scalar(select(PaymentSetting).where(PaymentSetting.country_code == "JO"))
    assert setting is None or setting.fare_step is None, "المعاينةُ لا تكتب"


# ------------------------------------------------------------------ ٣) و٥) على رحلةٍ حقيقيّة


async def _jordan_ride(client, admin_headers, session_factory, monkeypatch):
    _route(monkeypatch, "3.328", "7.00")  # 1.000 + 1.664 + 0.700 = 3.364
    await set_commission(session_factory, "10")
    saved = await client.put("/admin/settings/fare-rounding/JO", json=JORDAN, headers=admin_headers)
    assert saved.status_code == 200, saved.text
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    return driver, rider


async def test_the_estimate_the_final_fare_and_the_charge_are_equal(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory, monkeypatch
) -> None:
    driver, rider = await _jordan_ride(client, admin_headers, session_factory, monkeypatch)
    quote = await client.post("/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF}, headers=rider["headers"])
    assert quote.status_code == 200, quote.text
    assert (quote.json()["estimated_fare"], quote.json()["priced_fare"]) == ("3.350", "3.364")

    ride = await _requested(client, rider["headers"])
    assert ride["rider_estimate"] == ride["current_fare"] == "3.350"
    await _drive(client, ride, driver)
    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "3.350"
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    assert paid.status_code == 201, paid.text
    [cash] = paid.json()["payments"]
    assert cash["amount"] == quote.json()["estimated_fare"] == done["final_fare"], "ما يُعرض = ما يُحصَّل"


async def test_a_ride_in_progress_keeps_the_rounding_it_was_requested_with(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory, monkeypatch
) -> None:
    driver, rider = await _jordan_ride(client, admin_headers, session_factory, monkeypatch)
    ride = await _requested(client, rider["headers"])
    await _drive(client, ride, driver)

    # **المشرفُ يغيّر الإعدادَ والرحلةُ جارية** — دينارٌ كاملٌ للأعلى
    changed = await client.put(
        "/admin/settings/fare-rounding/JO", json={**JORDAN, "decimals": 0, "step": "1.000", "mode": "up"}, headers=admin_headers
    )
    assert changed.status_code == 200, changed.text

    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "3.350", "الرحلةُ الجاريةُ بتقريبها المجمَّد عند الطلب"
    later = await client.post("/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF}, headers=rider["headers"])
    assert later.json()["estimated_fare"] == "4.000", "والجديدةُ بالإعداد الجديد"
