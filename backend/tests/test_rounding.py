"""لا كسورَ في المال: التقريبُ إلى وحدة الدولة (SPEC §٧٠) — **الجزءُ الأوّل: القاعدةُ والسجلُّ ومسارُ الرحلة**.

ما يحرسه هذا الملف:

- **حدودُ الوحدة** (§٧٠-أ/١٤): `.249` · `.250` · `.251` · `.749` · `.750` بالأقرب (نصفُه للأعلى)، و«للأعلى» و«للأدنى»، والوحدتان
  `0.250` و`1.000` — **ومطفأً هويّةٌ حرفاً**.
- **المثالان (أ) و(ب) من §٧٠-ج بأرقامهما** بالمسار الحقيقيّ: رحلةٌ نقديّة، ورحلةٌ بالمحفظة بقسيمة ٢٠٪ وعمولة ١٠٪.
- **سطورُ الأجرة تُجمع إلى `final_fare` حرفاً**، وسطرُ «تقريب» موجبٌ أو سالب، **والعمولةُ على الأجرة المسعَّرة بلا سطر التقريب**.
- **المحفظةُ تدفع أكبرَ مضاعفٍ لا يتجاوز رصيدَها** والباقي نقداً مضاعفٌ، والكسرُ القديمُ يبقى فيها.
- **مقدَّمُ الساعة يُقرَّب عند البدء ولا يُقرَّب المجموعُ مرّتين.**
- **الإعدادُ من اللوحة مدقَّقٌ ويُختم وقتُ إشعاله، ويُنشر لكلِّ سوق**؛ ورحلةٌ طُلبت قبل الإشعال تُقرَّب عند إنهائها بعده.
- **مطفأً لا يتغيّر شيء**، **وإشعالُه لا يمسّ رصيداً ولا قيداً قائماً** (بصمةُ المال قبل وبعد).

**ولا صفَّ رحلةٍ ولا دفعةٍ مكتوبٌ بيد** (`test_no_shortcut_fixtures`): كلُّ رحلةٍ من الطلب إلى الإنهاء، وكلُّ دفعةٍ من بابها.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.debt import DriverDebt
from app.models.enums import CountryCode, FeatureKey, PromoDiscountType, RoundingMode, WalletTransactionType
from app.models.promo import PromoCode
from app.models.ride import Ride
from app.models.rounding import MoneyRounding
from app.models.service_setting import ServiceSetting
from app.models.wallet import WalletTransaction
from app.services import rounding
from app.services.directions import Route
from app.services.rounding import DISABLED, RoundingPolicy
from scripts import money_fingerprint
from tests.helpers import (
    DRIVER,
    DROPOFF,
    PICKUP,
    approved_driver,
    bring_online,
    enable_features,
    pay_ride,
    payments_of,
    rider_session,
    set_commission,
    topup_wallet,
    wait_for_offer,
    wallet_of,
)

HALF = RoundingPolicy(enabled=True, unit=Decimal("0.500"), mode=RoundingMode.NEAREST)


def _policy(unit: str, mode: str) -> RoundingPolicy:
    return RoundingPolicy(enabled=True, unit=Decimal(unit), mode=RoundingMode(mode))


# ------------------------------------------------------------------ القاعدة


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        # حدودُ المالك بنصّها (§٧٠-أ/١٤) — و«الأقرب» نصفُه للأعلى
        ("2.249", "2.000"),
        ("2.250", "2.500"),
        ("2.251", "2.500"),
        ("2.749", "2.500"),
        ("2.750", "3.000"),
        # ومثالُه في الطلب: `3.364` تصير `3.500`
        ("3.364", "3.500"),
        ("3.000", "3.000"),
        ("0.249", "0.000"),
    ],
)
def test_nearest_half_dinar_at_the_unit_edges(amount: str, expected: str) -> None:
    rounded, difference = rounding.round_amount(Decimal(amount), HALF)
    assert rounded == Decimal(expected)
    assert difference == Decimal(expected) - Decimal(amount)
    assert str(rounded) == expected, "ثلاثُ خاناتٍ كعمود المال"


@pytest.mark.parametrize(
    ("unit", "mode", "amount", "expected"),
    [
        ("0.500", "up", "2.001", "2.500"),
        ("0.500", "up", "2.500", "2.500"),
        ("0.500", "down", "2.999", "2.500"),
        ("0.500", "down", "2.500", "2.500"),
        ("0.250", "nearest", "2.124", "2.000"),
        ("0.250", "nearest", "2.125", "2.250"),
        ("0.250", "nearest", "2.374", "2.250"),
        ("0.250", "nearest", "2.375", "2.500"),
        ("0.250", "up", "2.251", "2.500"),
        ("0.250", "down", "2.499", "2.250"),
        ("1.000", "nearest", "2.499", "2.000"),
        ("1.000", "nearest", "2.500", "3.000"),
        ("1.000", "up", "2.001", "3.000"),
        ("1.000", "down", "2.999", "2.000"),
    ],
)
def test_up_down_and_other_units(unit: str, mode: str, amount: str, expected: str) -> None:
    assert rounding.round_amount(Decimal(amount), _policy(unit, mode))[0] == Decimal(expected)


def test_switched_off_it_is_the_identity_and_the_helpers_agree() -> None:
    """**مطفأً هويّةٌ حرفاً** — المبلغُ نفسُه وفرقٌ صفريّ، فلا يتغيّر مبلغٌ واحدٌ في سوقٍ لم يُشعَل."""
    assert rounding.round_amount(Decimal("3.364"), DISABLED) == (Decimal("3.364"), Decimal("0.000"))
    assert rounding.floor_to_unit(Decimal("2.700"), DISABLED) == Decimal("2.700")
    assert rounding.is_multiple(Decimal("2.701"), DISABLED)

    assert rounding.floor_to_unit(Decimal("2.700"), HALF) == Decimal("2.500")
    assert rounding.floor_to_unit(Decimal("0.499"), HALF) == Decimal("0.000")
    assert rounding.is_multiple(Decimal("4.000"), HALF) and not rounding.is_multiple(Decimal("4.100"), HALF)
    # **باقٍ سالبٌ أقلُّ من نصف وحدة يُقرَّب إلى صفر** — نصفُه للأعلى بمعناه (مقدَّمُ ساعةٍ قُرِّب للأعلى ولم يزد شيء)
    assert rounding.round_amount(Decimal("-0.250"), HALF) == (Decimal("0.000"), Decimal("0.250"))
    assert rounding.round_amount(Decimal("-0.125"), HALF)[0] == Decimal("0.000")


# ------------------------------------------------------------------ أدوات


def _route(monkeypatch: pytest.MonkeyPatch, km: str, minutes: str) -> None:
    """مسارٌ بطولٍ معلوم — **بديلُ Mapbox نفسُه** بمسافةٍ أخرى (والتوكنُ يُقرأ من العقود كما في `conftest`)."""
    from app.services import directions

    async def _fetch_route(token: str, *waypoints, with_geometry: bool = False, with_steps: bool = False):
        return Route(
            distance_km=Decimal(km),
            duration_min=Decimal(minutes),
            geometry=[[p.lng, p.lat] for p in waypoints] if with_geometry else None,
            steps=None,
        )

    monkeypatch.setattr(directions, "fetch_route", _fetch_route)


async def _enable(
    client: AsyncClient, admin_headers: dict, *, unit: str = "0.500", mode: str = "nearest"
) -> dict:
    """**الإشعالُ من بابه** — `PATCH` اللوحة بصلاحية الإعدادات، لا كتابةٌ في الصفّ."""
    response = await client.patch(
        "/admin/settings/payments/JO",
        json={"rounding_enabled": True, "rounding_unit": unit, "rounding_mode": mode},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _requested(client: AsyncClient, rider: dict, *, promo_code: str | None = None) -> dict:
    body: dict = {"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"}
    if promo_code:
        body["promo_code"] = promo_code
    created = await client.post("/rides", json=body, headers=rider)
    assert created.status_code == 201, created.text
    return created.json()


async def _drive(client: AsyncClient, ride: dict, driver: dict) -> dict:
    """من الطلب إلى «بدأت» — **وإعادةُ المحاولة حين تنقضي مهلةُ العرض تحت الحمل** (علّةُ `helpers.accepted_ride`)."""
    for attempt in range(3):
        await wait_for_offer(ride["id"], driver["driver_id"])
        accepted = await client.post(f"/rides/{ride['id']}/accept", headers=driver["headers"])
        if accepted.status_code == 200:
            break
        if accepted.json().get("code") != "ride_offer_expired" or attempt == 2:
            break
    assert accepted.status_code == 200, accepted.text
    for step in ("arrive", "start"):
        moved = await client.post(f"/rides/{ride['id']}/{step}", headers=driver["headers"])
        assert moved.status_code == 200, moved.text
    return moved.json()


async def _complete(client: AsyncClient, ride: dict, driver: dict) -> dict:
    done = await client.post(f"/rides/{ride['id']}/complete", headers=driver["headers"])
    assert done.status_code == 200, done.text
    return done.json()


def _lines(ride: dict) -> dict[str, str]:
    return {line["kind"]: line["amount"] for line in ride["fare_lines"]}


def _lines_sum(ride: dict) -> Decimal:
    return sum((Decimal(line["amount"]) for line in ride["fare_lines"]), Decimal(0))


async def _journal(session_factory, ride_id: str) -> list[MoneyRounding]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(MoneyRounding).where(MoneyRounding.source_id == uuid.UUID(ride_id))
            )
        )


async def _ledger_sum(session_factory, ride_id: str, kind: WalletTransactionType) -> Decimal:
    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.ride_id == uuid.UUID(ride_id), WalletTransaction.type == kind
            )
        )
    return Decimal(total or 0)


async def _commission_of(session_factory, payment_id: str) -> Decimal:
    """**عمولةُ دفعةٍ بعينها كما كُتبت** — قيدُها في الدفتر بمفتاحها (`commission:<الدفعة>`)، أو دَينُها حين قُبضت باليد."""
    async with session_factory() as session:
        entry = await session.scalar(
            select(WalletTransaction.amount).where(WalletTransaction.idempotency_key == f"commission:{payment_id}")
        )
        if entry is not None:
            return -entry
        debt = await session.scalar(select(DriverDebt.amount).where(DriverDebt.payment_id == uuid.UUID(payment_id)))
    return Decimal(debt or 0)


async def _captain_net(session_factory, ride_id: str, user_id) -> Decimal:
    """**صافي ما قُيِّد للكبتن من هذه الرحلة** — أجرٌ وعمولةٌ وتصحيحُ ردّ، كلُّ قيدٍ يحمل معرّفَها."""
    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.ride_id == uuid.UUID(ride_id),
                WalletTransaction.owner_id == uuid.UUID(str(user_id)),
            )
        )
    return Decimal(total or 0)


# ------------------------------------------------------------------ الإعداد


async def test_the_setting_is_edited_from_the_panel_audited_stamped_and_published(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """**إعدادان في اللوحة لكلِّ دولة، مدقَّقان** (§٧٠-أ/٦) — **ومطفأٌ بالترحيلة**، ووقتُ الإشعال يُختم، **ويُنشر في `/config`**."""
    listed = await client.get("/admin/settings/payments", headers=admin_headers)
    jordan = next(row for row in listed.json() if row["country_code"] == "JO")
    assert (jordan["rounding_enabled"], jordan["rounding_unit"], jordan["rounding_mode"]) == (False, "0.500", "nearest")
    assert jordan["rounding_enabled_at"] is None

    # **وحدةٌ صفريّةٌ واتجاهٌ مخترَعٌ يُردّان** — صفرٌ يقسم عليه الحساب
    for bad in ({"rounding_unit": "0"}, {"rounding_unit": "0.0005"}, {"rounding_mode": "sideways"}):
        refused = await client.patch("/admin/settings/payments/JO", json=bad, headers=admin_headers)
        assert refused.status_code == 422, (bad, refused.text)

    enabled = await _enable(client, admin_headers, unit="0.250", mode="up")
    assert (enabled["rounding_enabled"], enabled["rounding_unit"], enabled["rounding_mode"]) == (True, "0.250", "up")
    assert enabled["rounding_enabled_at"] is not None

    async with session_factory() as session:
        entry = await session.scalar(
            select(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "payment_setting")
            .order_by(AdminAuditLog.created_at.desc())
        )
    changes = entry.details["changes"]
    assert changes["rounding_enabled"] == {"before": False, "after": True}
    assert changes["rounding_unit"] == {"before": "0.500", "after": "0.250"}
    assert changes["rounding_mode"] == {"before": "nearest", "after": "up"}
    assert changes["rounding_enabled_at"]["before"] is None and changes["rounding_enabled_at"]["after"]

    config = (await client.get("/config")).json()
    published = {c["country_code"]: c for c in config["countries"]}
    assert (published["JO"]["rounding_enabled"], published["JO"]["rounding_unit"], published["JO"]["rounding_mode"]) == (
        True,
        "0.250",
        "up",
    )
    # **ليبيا لا يُمسّ صفُّها** — مطفأةٌ كما كانت
    if "LY" in published:
        assert published["LY"]["rounding_enabled"] is False


# ------------------------------------------------------------------ المثال (أ)


async def test_example_a_a_cash_ride(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory, monkeypatch
) -> None:
    """**(أ) رحلةٌ نقديّة** (§٧٠-ج): `1.000 + 1.664 + 0.700 = 3.364` ⇐ `3.500`، و«تقريب» `+0.136`. يدفع `3.500` نقداً،
    **والعمولةُ على `3.364`: `0.336` دَينٌ على الكبتن** — صافيه `3.164`. **والسجلّ**: (رحلة · `3.364` ⇐ `3.500` · `+0.136`)."""
    _route(monkeypatch, "3.328", "7.00")
    await set_commission(session_factory, "10")
    await _enable(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    # **التقديرُ قبل الطلب مقرَّب** — والدقيقةُ معه لمعاينة القسيمة
    quote = await client.post(
        "/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF}, headers=rider["headers"]
    )
    assert quote.status_code == 200, quote.text
    assert (quote.json()["estimated_fare"], quote.json()["priced_fare"]) == ("3.500", "3.364")

    ride = await _requested(client, rider["headers"])
    assert ride["estimated_fare"] == "3.364", "المحفوظُ بدقّته — التقريبُ مرّةً عند الإنهاء"
    # **والعدّادُ الحيُّ مقرَّبٌ بالقاعدة نفسِها** — وعدّادُ الراكب بلا خصمٍ هو هو
    assert ride["current_fare"] == ride["rider_estimate"] == "3.500"
    started = await _drive(client, ride, driver)
    assert started["current_fare"] == "3.500"

    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "3.500"
    assert _lines(done) == {"base": "1.000", "distance": "1.664", "time": "0.700", "rounding": "0.136"}
    assert _lines_sum(done) == Decimal(done["final_fare"]), "التفصيلُ يُجمع إلى الأجرة المقرَّبة حرفاً"

    [row] = await _journal(session_factory, ride["id"])
    assert (row.source_kind, row.precise, row.rounded, row.difference) == (
        "ride",
        Decimal("3.364"),
        Decimal("3.500"),
        Decimal("0.136"),
    )
    assert (row.unit, row.mode, str(row.user_id)) == (Decimal("0.500"), "nearest", rider["user"]["id"])

    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    assert paid.status_code == 201, paid.text
    [cash] = paid.json()["payments"]
    assert (cash["method"], cash["amount"]) == ("cash", "3.500")
    confirmed = await client.post(f"/payments/{cash['id']}/confirm", headers=driver["headers"])
    assert confirmed.status_code == 200, confirmed.text

    async with session_factory() as session:
        debt = await session.scalar(
            select(func.coalesce(func.sum(DriverDebt.amount), 0)).where(DriverDebt.ride_id == uuid.UUID(ride["id"]))
        )
    assert Decimal(debt) == Decimal("0.336"), "العمولةُ على الأجرة المسعَّرة بلا سطر التقريب"
    state = await payments_of(client, rider["headers"], ride["id"])
    assert state["outstanding"] == "0.000"


# ------------------------------------------------------------------ المثال (ب)


async def test_example_b_a_wallet_ride_with_a_twenty_percent_coupon(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory, monkeypatch
) -> None:
    """**(ب) بالمحفظة وقسيمة ٢٠٪** (§٧٠-ج): `4.870` ⇐ القسيمةُ أوّلاً `0.974` ⇐ على الراكب `3.896` ⇐ `4.000` ⇐ «تقريب» `+0.104`
    ⇐ النهائيّة `4.974`. **المحفظة `10.000 ⇐ 6.000`**. الكبتن: `4.000 + 0.974 = 4.974`، والعمولةُ على `4.870`: **`0.487`** ⇐ صافيه
    `4.487`. **ولم يُقرَّب إلا مرّة** — على ما بعد النسبة."""
    _route(monkeypatch, "6.140", "8.00")
    await enable_features(session_factory, FeatureKey.PROMO_CODES_ENABLED.value)
    await set_commission(session_factory, "10")
    async with session_factory() as session:
        session.add(
            PromoCode(
                code="TWENTY",
                country_code=CountryCode.JO,
                discount_type=PromoDiscountType.PERCENT,
                discount_value=Decimal("20"),
                max_discount=None,
                budget_total=Decimal("100.000"),
                per_user_limit=1,
            )
        )
        await session.commit()
    await _enable(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "10.000")

    # **معاينةُ القسيمة على الدقيقة ثمّ يُقرَّب الباقي** — `priced_fare` من التقدير
    quote = (
        await client.post("/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF}, headers=rider["headers"])
    ).json()
    preview = await client.post(
        "/rides/promo/validate",
        json={"code": "TWENTY", "country_code": "JO", "fare": quote["priced_fare"]},
        headers=rider["headers"],
    )
    assert preview.status_code == 200, preview.text
    assert (preview.json()["discount"], preview.json()["fare_after"]) == ("0.974", "4.000")
    # **والنسخةُ القديمةُ ترسل `estimated_fare` المقرَّب** (`5.000`) — **فيُستردّ دقيقُه ممّا نشره التقدير** ولا يُحسب الخصمُ على
    # مقرَّبٍ ثمّ يُقرَّب ثانيةً (مراجعةُ المال البند ١١): الخصمُ `0.974` لا `1.000`
    assert quote["estimated_fare"] == "5.000"
    old_client = await client.post(
        "/rides/promo/validate",
        json={"code": "TWENTY", "country_code": "JO", "fare": quote["estimated_fare"]},
        headers=rider["headers"],
    )
    assert old_client.status_code == 200, old_client.text
    assert (old_client.json()["discount"], old_client.json()["fare_after"]) == ("0.974", "4.000"), "قُرِّبت المعاينةُ مرّتين"

    ride = await _requested(client, rider["headers"], promo_code="TWENTY")
    # **العدّادُ هو الأجرةُ كما ستُحفظ**: الخصمُ أوّلاً ثمّ يُقرَّب الباقي ويُضاف فرقُه
    assert ride["current_fare"] == "4.974"
    # **وعدّادُ الراكب ما سيدفعه** (مراجعةُ المال البند ٨): بعد الخصم المجمَّد مقرَّباً — لا الإجماليُّ `4.974` الذي ليس مضاعفاً
    assert ride["rider_estimate"] == "4.000"
    await _drive(client, ride, driver)
    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "4.974"
    assert _lines(done)["rounding"] == "0.104"
    assert _lines_sum(done) == Decimal("4.974")

    state = await payments_of(client, rider["headers"], ride["id"])
    assert state["outstanding"] == "4.000", "النهائيّة − الخصم = مضاعفٌ للوحدة"
    promo_row = next(p for p in state["payments"] if p["method"] == "promo")
    assert (promo_row["amount"], promo_row["status"]) == ("0.974", "confirmed")

    paid = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert paid.status_code == 201, paid.text
    wallet_row = next(p for p in paid.json()["payments"] if p["method"] == "wallet")
    assert wallet_row["amount"] == "4.000"
    assert (await wallet_of(client, rider["headers"]))["balance"] == "6.000"

    earned = await _ledger_sum(session_factory, ride["id"], WalletTransactionType.RIDE_EARNING)
    commission = await _ledger_sum(session_factory, ride["id"], WalletTransactionType.COMMISSION)
    assert earned == Decimal("4.974")
    assert commission == Decimal("-0.487"), "العمولةُ على 4.870 — لا على سطر التقريب"
    assert earned + commission == Decimal("4.487")
    # **وصفّاً صفّاً كاليوم** (مراجعةُ المال البند ٣): القسيمةُ `0.974 × 10٪ = 0.097` بوعائها الذي كان، **ودفعةُ الراكب تحمل الفرقَ
    # كلَّه خارج وعائها** `4.000 × 3.896 / 4.000 = 3.896` ⇐ `0.390` — لا `0.095 + 0.392` بالتوزيع الموحَّد
    assert await _commission_of(session_factory, promo_row["id"]) == Decimal("0.097")
    assert await _commission_of(session_factory, wallet_row["id"]) == Decimal("0.390")

    [row] = await _journal(session_factory, ride["id"])
    assert (row.precise, row.rounded, row.difference) == (Decimal("3.896"), Decimal("4.000"), Decimal("0.104"))


# ------------------------------------------------------------------ المحفظةُ والاتجاهُ للأدنى


async def test_a_short_wallet_pays_the_largest_multiple_and_the_rest_is_cash(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory, monkeypatch
) -> None:
    """**المحفظةُ تدفع أكبرَ مضاعفٍ للوحدة لا يتجاوز رصيدَها** والباقي نقداً — **فالباقي مضاعفٌ أيضاً**، والكسرُ القديمُ يبقى
    في المحفظة لصاحبه (§٧٠-ج/٤)."""
    _route(monkeypatch, "3.328", "7.00")
    await _enable(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "2.700")

    ride = await _requested(client, rider["headers"])
    await _drive(client, ride, driver)
    await _complete(client, ride, driver)

    paid = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert paid.status_code == 201, paid.text
    rows = sorted((p["method"], p["amount"]) for p in paid.json()["payments"])
    assert rows == [("cash", "1.000"), ("wallet", "2.500")]
    assert (await wallet_of(client, rider["headers"]))["balance"] == "0.200"


async def test_rounding_down_writes_a_negative_line_and_the_commission_stays_on_the_priced_fare(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory, monkeypatch
) -> None:
    """**للأدنى**: `3.364 ⇐ 3.000` وسطرٌ **سالب** `−0.364` — والسطورُ تُجمع إلى `3.000`، **والعمولةُ على `3.364` كما هي**."""
    _route(monkeypatch, "3.328", "7.00")
    await set_commission(session_factory, "10")
    await _enable(client, admin_headers, mode="down")
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    ride = await _requested(client, rider["headers"])
    await _drive(client, ride, driver)
    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "3.000"
    assert _lines(done)["rounding"] == "-0.364"
    assert _lines_sum(done) == Decimal("3.000")

    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    [cash] = paid.json()["payments"]
    assert cash["amount"] == "3.000"
    assert (await client.post(f"/payments/{cash['id']}/confirm", headers=driver["headers"])).status_code == 200
    async with session_factory() as session:
        debt = await session.scalar(
            select(func.coalesce(func.sum(DriverDebt.amount), 0)).where(DriverDebt.ride_id == uuid.UUID(ride["id"]))
        )
    assert Decimal(debt) == Decimal("0.336")


# ------------------------------------------------------------------ قبل الإشعال وبعده


async def test_a_ride_requested_before_ignition_is_rounded_when_it_completes_after(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory, monkeypatch
) -> None:
    """**«الإنهاءُ هو المعاملة»** (§٧٠-ج/٧): عرضُها قبل الإشعال بلا تقريب (سياسةُ لحظة الطلب)، **والمحفوظُ بإعداد لحظة الإنهاء**."""
    _route(monkeypatch, "3.328", "7.00")
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    ride = await _requested(client, rider["headers"])
    assert ride["current_fare"] == "3.364"
    await _drive(client, ride, driver)
    await _enable(client, admin_headers)
    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "3.500"
    assert _lines(done)["rounding"] == "0.136"


async def test_switched_off_nothing_changes(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory, monkeypatch
) -> None:
    """**مطفأً كما كان حرفاً**: لا سطرَ ولا صفَّ في السجلّ، والتقديرُ والعدّادُ والأجرةُ بدقّتها — وهو حالُ السوقين بعد `0104`."""
    _route(monkeypatch, "3.328", "7.00")
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    quote = (
        await client.post("/rides/estimate", json={"pickup": PICKUP, "dropoff": DROPOFF}, headers=rider["headers"])
    ).json()
    assert quote["estimated_fare"] == quote["priced_fare"] == "3.364"
    ride = await _requested(client, rider["headers"])
    assert ride["current_fare"] == "3.364"
    # **وعدّادُ الراكب ما عرضه قبل §٧٠ حرفاً** (مراجعةُ المال البند ٨): `estimated_fare` — لا تغيّرَ بلا إذن المالك
    assert ride["rider_estimate"] == ride["estimated_fare"] == "3.364"
    await _drive(client, ride, driver)
    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "3.364"
    assert "rounding" not in _lines(done)
    assert await _journal(session_factory, ride["id"]) == []


# ------------------------------------------------------------------ بالساعة


async def test_an_hourly_prepay_is_rounded_at_start_and_the_ride_is_rounded_once(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**المقدَّمُ يُقرَّب عند البدء** (`7.875 ⇐ 8.000`) **والإنهاءُ يقرّب ما بقي** — باقٍ سالبٌ `−0.125` يُقرَّب إلى صفر، فيرتفع
    الفرقُ إلى ما دُفع: الأجرةُ `8.000` وسطرُ «تقريب» `+0.125`، **ولا يبقى فلسٌ دفعه الراكبُ خارج الأجرة بلا سطر**. والسجلُّ
    يقرأ الرحلةَ كلَّها: `7.875 ⇐ 8.000`."""
    async with session_factory() as session:
        session.add_all(
            [ServiceSetting(country_code="JO", hourly_rate=Decimal("7.875")), ServiceSetting(country_code="LY")]
        )
        await session.commit()
    await enable_features(session_factory, FeatureKey.HOURLY_ENABLED.value)
    await _enable(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")

    created = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": PICKUP, "vehicle_category": "economy", "hourly": {"hours": 1, "prepay": "wallet"}},
        headers=rider["headers"],
    )
    assert created.status_code == 201, created.text
    ride = created.json()
    await _drive(client, ride, driver)
    started = await payments_of(client, rider["headers"], ride["id"])
    assert [(p["method"], p["amount"]) for p in started["payments"]] == [("wallet", "8.000")]

    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "8.000"
    assert _lines(done) == {"hourly": "7.875", "rounding": "0.125"}
    state = await payments_of(client, rider["headers"], ride["id"])
    assert state["outstanding"] == "0.000"
    [row] = await _journal(session_factory, ride["id"])
    assert (row.precise, row.rounded, row.difference) == (Decimal("7.875"), Decimal("8.000"), Decimal("0.125"))


async def _hourly_started(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    *,
    commission: str | None = None,
    prepay: str = "wallet",
) -> tuple[dict, dict, dict]:
    """**ساعةٌ بسعر `7.875` تُدفع من المحفظة (أو نقداً) وقد بدأت** — مقدَّمُها `8.000` مقرَّباً بالأقرب. يعيد (الرحلة، الكبتن، الراكب)."""
    async with session_factory() as session:
        session.add_all(
            [ServiceSetting(country_code="JO", hourly_rate=Decimal("7.875")), ServiceSetting(country_code="LY")]
        )
        await session.commit()
    await enable_features(session_factory, FeatureKey.HOURLY_ENABLED.value)
    if commission is not None:
        await set_commission(session_factory, commission)
    await _enable(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    created = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": PICKUP, "vehicle_category": "economy", "hourly": {"hours": 1, "prepay": prepay}},
        headers=rider["headers"],
    )
    assert created.status_code == 201, created.text
    ride = created.json()
    await _drive(client, ride, driver)
    return ride, driver, rider


async def test_an_hourly_wallet_prepay_is_commissioned_at_completion_on_the_priced_fare(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**مراجعةُ المال البند ١**: عمولةُ المقدَّم **على المسعَّر لا على المقرَّب المدفوع** — فلا تُكتب عند البدء (`8.000 × 10٪ =
    0.800`) بل عند الإنهاء. ساعةٌ و٣ دقائقَ زائدة (`0.300`) ⇐ المسعَّرُ `8.175` ⇐ الباقي `0.175` يُقرَّب إلى صفر (سطرٌ `−0.175`)
    ⇐ النهائيّةُ `8.000` — **والعمولةُ `0.818` على `8.175`**: الزيادةُ التي قُرِّبت لا تضيع عمولتُها، والفرقُ لا تمسّه العمولة."""
    ride, driver, rider = await _hourly_started(client, admin_headers, session_factory, commission="10")
    started = await payments_of(client, rider["headers"], ride["id"])
    assert [(p["method"], p["amount"]) for p in started["payments"]] == [("wallet", "8.000")]
    assert await _ledger_sum(session_factory, ride["id"], WalletTransactionType.COMMISSION) == 0, (
        "عمولةُ المقدَّم كُتبت عند البدء على المقرَّب — قبل أن تُعرف الأجرةُ المسعَّرة"
    )

    # ساعةٌ وثلاثُ دقائق — **ونصفُ دقيقةٍ هامشٌ** فلا يعبر الإنهاءُ إلى الدقيقة الرابعة تحت الحمل
    async with session_factory() as session:
        row = await session.get(Ride, uuid.UUID(ride["id"]))
        row.started_at = datetime.now(UTC) - timedelta(minutes=63, seconds=30)
        await session.commit()
    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "8.000"
    assert _lines(done) == {"hourly": "7.875", "hourly_extra_time": "0.300", "rounding": "-0.175"}
    assert _lines_sum(done) == Decimal("8.000")
    assert (await payments_of(client, rider["headers"], ride["id"]))["outstanding"] == "0.000"
    [journal] = await _journal(session_factory, ride["id"])
    assert (journal.precise, journal.rounded) == (Decimal("8.175"), Decimal("8.000"))

    assert await _ledger_sum(session_factory, ride["id"], WalletTransactionType.RIDE_EARNING) == Decimal("8.000")
    assert await _ledger_sum(session_factory, ride["id"], WalletTransactionType.COMMISSION) == Decimal("-0.818"), (
        "العمولةُ ليست على الأجرة المسعَّرة 8.175"
    )


async def test_a_refund_reverses_the_commission_that_was_written_not_a_recomputed_one(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**مراجعةُ المال البند ١**: الاستردادُ **يقرأ العمولةَ التي كُتبت** ولا يعيد حسابَها. مقدَّمُ ساعةٍ يُردّ في أثناء الرحلة —
    **وعمولتُه لم تُكتب بعد** (تنتظر الأجرة) — فيُعكس أجرُه كلُّه `8.000`: صافي الكبتن من الرحلة صفر. **وبإعادة الحساب** كان
    الردُّ يطرح عمولةً لم تُخصم (`0.800`) فيبقى للكبتن مالٌ رُدّ إلى الراكب. **ثمّ الإنهاءُ لا يكتب عمولةً على مقدَّمٍ رُدّ.**"""
    ride, driver, rider = await _hourly_started(client, admin_headers, session_factory, commission="10")
    [prepay] = (await payments_of(client, rider["headers"], ride["id"]))["payments"]

    refunded = await client.post(
        f"/admin/payments/{prepay['id']}/refund", json={"reason": "ردُّ مقدَّمٍ في أثناء الرحلة"}, headers=admin_headers
    )
    assert refunded.status_code == 200, refunded.text
    assert (await wallet_of(client, rider["headers"]))["balance"] == "20.000"
    assert await _captain_net(session_factory, ride["id"], driver["user_id"]) == 0, (
        "الردُّ طرح عمولةً لم تُكتب — فبقي للكبتن مالٌ رُدّ"
    )

    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "8.000"
    assert (await payments_of(client, rider["headers"], ride["id"]))["outstanding"] == "8.000"
    assert await _ledger_sum(session_factory, ride["id"], WalletTransactionType.COMMISSION) == 0, (
        "كُتبت عمولةٌ على مقدَّمٍ رُدّ"
    )


async def test_switching_rounding_off_during_an_hourly_ride_does_not_strand_the_prepay_fraction(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**مراجعةُ المال البند ٢**: سياسةُ التقريب التي قُرِّب بها المقدَّمُ **تُجمَّد على الرحلة**، وبها يُقرَّب الباقي. أُطفئ التقريبُ
    في أثناء الرحلة — **والراكبُ دفع `8.000` عن `7.875`**: الفرقُ `+0.125` سطرُ «تقريب» وصفٌّ في السجلّ بوحدته واتجاهه المجمَّدين،
    لا ثُمنُ دينارٍ دُفع بلا سطر (`outstanding` سالبٌ كان يُقرأ «مدفوعة»)."""
    ride, driver, rider = await _hourly_started(client, admin_headers, session_factory)
    off = await client.patch("/admin/settings/payments/JO", json={"rounding_enabled": False}, headers=admin_headers)
    assert off.status_code == 200, off.text

    done = await _complete(client, ride, driver)
    assert done["final_fare"] == "8.000", "أُطفئ التقريبُ فبقي فرقُ المقدَّم بلا سطر"
    assert _lines(done) == {"hourly": "7.875", "rounding": "0.125"}
    assert (await payments_of(client, rider["headers"], ride["id"]))["outstanding"] == "0.000"
    [row] = await _journal(session_factory, ride["id"])
    assert (row.precise, row.rounded, row.difference, row.unit, row.mode) == (
        Decimal("7.875"),
        Decimal("8.000"),
        Decimal("0.125"),
        Decimal("0.500"),
        "nearest",
    )


# ------------------------------------------------------------------ العمولةُ صفّاً صفّاً


async def test_with_commission_on_cashless_rides_only_a_cash_rider_keeps_todays_coupon_commission(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory, monkeypatch
) -> None:
    """**مراجعةُ المال البند ٣**: صفُّ القسيمة وعاؤه كاليوم حرفاً — المثالُ (ب) والعمولةُ على غير النقد وحدَه، **والراكبُ يدفع
    `4.000` نقداً**: عمولةُ الرحلة كلُّها عمولةُ القسيمة **`0.097` كاليوم** (`0.974 × 10٪`)، لا `0.095` يحمل من فرق التقريب."""
    _route(monkeypatch, "6.140", "8.00")
    await enable_features(session_factory, FeatureKey.PROMO_CODES_ENABLED.value)
    await set_commission(session_factory, "10", "cashless_rides")
    async with session_factory() as session:
        session.add(
            PromoCode(
                code="TWENTY",
                country_code=CountryCode.JO,
                discount_type=PromoDiscountType.PERCENT,
                discount_value=Decimal("20"),
                max_discount=None,
                budget_total=Decimal("100.000"),
                per_user_limit=1,
            )
        )
        await session.commit()
    await _enable(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    ride = await _requested(client, rider["headers"], promo_code="TWENTY")
    await _drive(client, ride, driver)
    done = await _complete(client, ride, driver)
    assert (done["final_fare"], _lines(done)["rounding"]) == ("4.974", "0.104")

    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    assert paid.status_code == 201, paid.text
    cash = next(p for p in paid.json()["payments"] if p["method"] == "cash")
    assert cash["amount"] == "4.000"
    assert (await client.post(f"/payments/{cash['id']}/confirm", headers=driver["headers"])).status_code == 200

    promo_row = next(p for p in (await payments_of(client, rider["headers"], ride["id"]))["payments"] if p["method"] == "promo")
    assert await _commission_of(session_factory, promo_row["id"]) == Decimal("0.097"), "عمولةُ القسيمة حملت من فرق التقريب"
    assert await _commission_of(session_factory, cash["id"]) == 0
    assert await _ledger_sum(session_factory, ride["id"], WalletTransactionType.COMMISSION) == Decimal("-0.097")


# ------------------------------------------------------------------ البصمة


async def test_switching_rounding_on_changes_no_existing_balance_or_ledger_entry(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory, monkeypatch
) -> None:
    """**شرطُ المالك**: «No existing balance or ledger entry changes» — **بصمةُ المال قبل الإشعال وبعده**.

    مالٌ قائمٌ بكسور (شحنٌ ورحلةٌ مدفوعةٌ بالمحفظة قبل الإشعال)، ثمّ الإشعالُ: **لا يتغيّر شيءٌ البتّة**. ثمّ رحلةٌ مقرَّبةٌ بعده:
    **ما كان قبل يبقى حرفاً** (`as_of`)، **والجديدُ يُرى** — فالأداةُ لا تعمى عن صفِّ السجلّ الجديد.
    """
    monkeypatch.setattr(money_fingerprint, "SessionLocal", session_factory)
    _route(monkeypatch, "3.328", "7.00")
    await set_commission(session_factory, "10")
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "10.123")

    old = await _requested(client, rider["headers"])
    await _drive(client, old, driver)
    await _complete(client, old, driver)
    assert (await pay_ride(client, rider["headers"], old["id"], "wallet", key="old-ride")).status_code == 201
    assert (await wallet_of(client, rider["headers"]))["balance"] == "6.759"

    before = await money_fingerprint.fingerprint()
    await _enable(client, admin_headers)
    assert money_fingerprint.compare(before, await money_fingerprint.fingerprint()) == ([], [])
    assert (await wallet_of(client, rider["headers"]))["balance"] == "6.759", "الكسرُ القديمُ لا يُمسّ"

    new = await _requested(client, rider["headers"])
    await _drive(client, new, driver)
    await _complete(client, new, driver)
    paid = await pay_ride(client, rider["headers"], new["id"], "wallet", key="new-ride")
    assert paid.status_code == 201, paid.text
    assert (await wallet_of(client, rider["headers"]))["balance"] == "3.259"

    assert money_fingerprint.compare(before, await money_fingerprint.fingerprint(as_of=before["taken_at"]))[0] == []
    live = money_fingerprint.compare(before, await money_fingerprint.fingerprint())[0]
    assert any(line.startswith(f"table {money_fingerprint.ROUNDINGS}") for line in live), live
