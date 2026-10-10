"""سوقُ الجزائر — المرحلةُ الأولى (SPEC §٧٣): **الأساسُ وخاناتُ العملة، والأردنُ وليبيا كما كانا حرفاً**.

**وكلُّ ادّعاءٍ عن السوقين القائمين يُقاس بالمقارنة لا بالقراءة**: التقريبُ القديمُ مكتوبٌ هنا كما كان (`_legacy`) ويُقارن بالجديد على
آلاف القيم، والصياغةُ على السلك يُشترط أن تعيد **الكائنَ نفسَه** لحمولةٍ أردنيّةٍ أو ليبيّة — لا ما يساويه.
"""

from __future__ import annotations

import ast
import json
import random
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core import money_wire
from app.core.currency import (
    COUNTRY_CURRENCY,
    COUNTRY_NAME,
    CURRENCY_DECIMALS,
    CURRENCY_LABEL,
    CURRENCY_NAME,
    money_text,
    round_to_currency,
)
from app.core.exceptions import AmountNotMultiple, InvalidInput
from app.core.phone import InvalidPhoneNumber, country_for_phone, normalize_phone, resolve_phone
from app.core.service_area import MARKET_BOX, box_for
from app.models.enums import CountryCode, Currency, ProviderKey, VehicleCategory
from app.models.feature_flag import FeatureFlag
from app.models.pricing import PricingRule
from app.models.user import User
from app.services import campaigns, pricing, rounding, wallet
from app.services.providers import credentials as credentials_service
from tests.helpers import MAPBOX_SECRET, RIDER, rider_session
from tests.money_format import offenders

ALGERIAN_RIDER = RIDER | {"phone": "0551234567", "country_code": "DZ", "name": "راكبٌ من الجزائر"}
ALGIERS = {"lat": 36.7538, "lng": 3.0588}
ALGIERS_EAST = {"lat": 36.7650, "lng": 3.0700}


def _legacy(amount: Decimal) -> Decimal:
    """**`round_money` قبل §٧٣ حرفاً** — المرجعُ الذي يُقاس عليه الأردنُ وليبيا."""
    return amount.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------ الاكتمال: كلُّ سوقٍ له كلُّ جداوله


def test_every_market_and_currency_is_declared_everywhere() -> None:
    """**سوقٌ بلا صفٍّ في جدولٍ واحدٍ يسقط في التشغيل لا هنا** — فيُشترط الاكتمالُ لكلِّ عضوٍ في التعدادين."""
    from app.core.phone import _COUNTRY_RULES

    assert set(COUNTRY_CURRENCY) == set(CountryCode)
    assert set(COUNTRY_NAME) == set(CountryCode)
    assert set(_COUNTRY_RULES) == set(CountryCode)
    assert set(campaigns.DEFAULT_TIMEZONES) == set(CountryCode)
    assert set(MARKET_BOX) == set(CountryCode)
    for table in (CURRENCY_DECIMALS, CURRENCY_LABEL, CURRENCY_NAME):
        assert set(table) == set(Currency)
    assert (CURRENCY_DECIMALS[Currency.JOD], CURRENCY_DECIMALS[Currency.LYD], CURRENCY_DECIMALS[Currency.DZD]) == (3, 3, 0)
    assert CURRENCY_LABEL[Currency.DZD] == "د.ج"


# ------------------------------------------------------------------ الهاتف


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+213551234567", "+213551234567"),
        ("00213661234567", "+213661234567"),
        ("+213 77 123 45 67", "+213771234567"),
    ],
)
def test_algerian_mobiles_in_international_form_are_accepted(raw: str, expected: str) -> None:
    assert resolve_phone(raw) == expected
    assert country_for_phone(expected) is CountryCode.DZ


@pytest.mark.parametrize("raw", ["0551234567", "551234567", "0661234567", "0771234567"])
def test_algerian_mobiles_in_national_form_are_accepted(raw: str) -> None:
    phone = normalize_phone(raw, CountryCode.DZ)
    assert phone.startswith("+213") and len(phone) == 13


@pytest.mark.parametrize("raw", ["021234567", "+21321234567", "0431234567", "0891234567", "05512345678"])
def test_algerian_landlines_and_malformed_numbers_are_refused(raw: str) -> None:
    """**الأرضيُّ لا يستقبل رمزَ تحقّق** (§٧٣-ج/٨) — ثمانيةُ أرقامٍ وطنيّة أو بادئةٌ غيرُ 5/6/7 تُردّ."""
    with pytest.raises(InvalidPhoneNumber):
        if raw.startswith("+"):
            resolve_phone(raw)
        else:
            normalize_phone(raw, CountryCode.DZ)


def test_jordan_and_libya_phones_resolve_as_before() -> None:
    assert resolve_phone("+962791234567") == "+962791234567"
    assert resolve_phone("00218912345678") == "+218912345678"
    assert country_for_phone("+962791234567") is CountryCode.JO
    assert country_for_phone("+218912345678") is CountryCode.LY


# ------------------------------------------------------------------ التقريب: الأردنُ وليبيا حرفاً، والجزائريُّ بلا كسور


def test_jordan_and_libya_round_exactly_as_before() -> None:
    """**القيمةُ والنصُّ معاً** — على حدود النصف وعلى أربعة آلاف قيمةٍ عشوائيّةٍ بستِّ خاناتٍ موجبةً وسالبة."""
    rng = random.Random(73)
    samples = [Decimal(v) for v in ("0.0005", "0.0015", "0.0025", "-0.0025", "1.2345", "2.249", "2.250", "0", "-0.0005")]
    samples += [Decimal(rng.randint(-10**9, 10**9)) / Decimal(10**6) for _ in range(4000)]
    for currency in (Currency.JOD, Currency.LYD, "JOD", "LYD"):
        for value in samples:
            new = round_to_currency(value, currency)
            assert new == _legacy(value) and str(new) == str(_legacy(value)), (currency, value)
            assert str(pricing.round_money(value, currency)) == str(_legacy(value))
    for value in samples:
        assert str(pricing.as_money(value)) == str(_legacy(value))


@pytest.mark.parametrize(
    ("value", "expected"),
    [("150.5", "151.000"), ("150.499", "150.000"), ("150", "150.000"), ("-2.5", "-3.000"), ("0.4", "0.000")],
)
def test_the_algerian_dinar_rounds_to_a_whole_dinar(value: str, expected: str) -> None:
    """**دينارٌ صحيحٌ نصفُه للأعلى، بدقّة التخزين** — فلا يختلط مقياسان في جمعٍ واحد."""
    assert str(round_to_currency(Decimal(value), Currency.DZD)) == expected


def test_money_text_follows_the_currency_and_never_hides_a_fraction() -> None:
    assert money_text(Decimal("1.5"), Currency.JOD) == "1.500"
    assert money_text(Decimal("150.000"), Currency.DZD) == "150"
    assert money_text(Decimal("150.500"), Currency.DZD) == "150.500"


# ------------------------------------------------------------------ السلك والحارس


@pytest.mark.parametrize(
    "payload",
    [
        {"currency": "JOD", "fare": "8.000", "rows": [{"amount": "0"}, {"amount": "1.5"}]},
        {"currency": "LYD", "balance": "150.000", "nested": {"price": "2.500"}},
        {"fare": "8.000", "amount": "0", "distance_km": "4.000"},
        [{"currency": "JOD", "amount": "3.500"}, {"amount": "1.000"}],
    ],
)
def test_the_wire_returns_jordan_and_libya_payloads_untouched(payload) -> None:
    """**الكائنُ نفسُه لا ما يساويه** — فلا يتغيّر بايتٌ في جوابٍ أردنيٍّ أو ليبيّ، ولا يُصلَح صفرُ الشكل السابع (`"0"`) هنا."""
    before = json.dumps(payload, ensure_ascii=False)
    assert money_wire.normalize(payload) is payload
    assert json.dumps(payload, ensure_ascii=False) == before


def test_the_wire_shapes_dinar_amounts_and_nothing_else() -> None:
    payload = {
        "currency": "DZD",
        "fare": "150.000",
        "distance_km": "4.000",
        "rating": "5.000",
        "rows": [{"amount": "20.000", "commission_percent": "10.00"}],
        "other": {"currency": "JOD", "amount": "1.000"},
    }
    shaped = money_wire.normalize(payload)
    assert shaped["fare"] == "150"
    assert shaped["rows"][0]["amount"] == "20"
    assert shaped["distance_km"] == "4.000" and shaped["rating"] == "5.000"
    assert shaped["rows"][0]["commission_percent"] == "10.00"
    assert shaped["other"]["amount"] == "1.000"
    assert offenders(shaped) == []


def test_the_wire_never_hides_a_fraction_and_the_guard_catches_it() -> None:
    payload = {"currency": "DZD", "fare": "150.500"}
    assert money_wire.normalize(payload) is payload
    assert offenders(payload)


def test_the_money_guard_knows_the_currency() -> None:
    assert offenders({"currency": "DZD", "fare": "150"}) == []
    assert offenders({"currency": "DZD", "fare": "150.000"})
    assert offenders({"currency": "JOD", "fare": "150.000"}) == []
    assert offenders({"currency": "JOD", "fare": "150"})
    assert offenders({"currency": "LYD", "fare": "150.00"})
    # **الشكلُ السابع ممسوكٌ كما كان**: صفرٌ بلا خاناتٍ في سياقٍ بلا عملة
    assert offenders({"fare": "0"})
    # **والعملةُ تُورث من الأصل**
    assert offenders({"currency": "DZD", "rows": [{"amount": "20.000"}]})
    assert offenders({"currency": "DZD", "rows": [{"amount": "20"}]}) == []


# ------------------------------------------------------------------ المدخلات


def test_a_fractional_dinar_typed_by_a_person_is_refused_with_its_neighbours() -> None:
    with pytest.raises(AmountNotMultiple) as raised:
        rounding.require_precise(Decimal("150.5"), Currency.DZD, field="amount")
    assert (raised.value.extra["lower"], raised.value.extra["upper"], raised.value.extra["unit"]) == ("150", "151", "1")
    rounding.require_precise(Decimal("150"), Currency.DZD)
    # **ولا عملَ له في عملةٍ بثلاث خانات**
    rounding.require_precise(Decimal("1.5"), Currency.JOD)
    rounding.require_precise(Decimal("1.234"), Currency.LYD)


async def test_the_write_guard_refuses_fractional_dinars_and_spares_jordan(session_factory) -> None:
    """**حارسُ الكتابة** (`core/money_guard.py`): مبلغٌ جزائريٌّ بكسرٍ يُردّ بنصٍّ يسمّي العمود؛ **والمعدّلُ ليس مبلغاً**؛ والأردنُ كما كان."""
    def rule(country: CountryCode, base: str, per_min: str = "0.100") -> PricingRule:
        return PricingRule(
            country_code=country,
            vehicle_category=VehicleCategory.ECONOMY,
            base_fare=Decimal(base),
            price_per_km=Decimal("0.500"),
            price_per_min=Decimal(per_min),
            minimum_fare=Decimal("2"),
            cancellation_fee=Decimal("0"),
        )

    async with session_factory() as session:
        session.add(rule(CountryCode.DZ, "100.5"))
        with pytest.raises(InvalidInput) as raised:
            await session.commit()
        assert raised.value.extra.get("field") == "base_fare"
        await session.rollback()

    async with session_factory() as session:
        session.add(rule(CountryCode.DZ, "100", per_min="5.25"))
        session.add(rule(CountryCode.JO, "1.5"))
        await session.commit()


async def test_the_ledger_refuses_a_fractional_dinar(client: AsyncClient, session_factory) -> None:
    rider = await rider_session(client, ALGERIAN_RIDER)
    async with session_factory() as session:
        user = await session.get(User, rider["user"]["id"])
        from app.models.enums import WalletTransactionType

        with pytest.raises(InvalidInput):
            await wallet.record(session, owner=user, tx_type=WalletTransactionType.ADJUSTMENT, amount=Decimal("10.5"))
        await session.rollback()


# ------------------------------------------------------------------ الدولة: الإعدادُ والظهورُ والتوقيتُ والنطاق


async def test_config_publishes_currency_from_its_single_home(client: AsyncClient) -> None:
    body = (await client.get("/config")).json()
    found = {entry["country_code"]: entry for entry in body["countries"]}
    assert (found["JO"]["currency_label"], found["JO"]["currency_name"], found["JO"]["currency_decimals"]) == (
        "د.أ",
        "دينار أردني",
        3,
    )
    assert (found["LY"]["currency_label"], found["LY"]["currency_decimals"]) == ("د.ل", 3)
    # الاختبارُ يبدأ من جداولَ فارغة — فالجزائرُ ظاهرةٌ بالسكوت هنا، وإخفاؤها يُقاس تحته بالصفِّ الذي تكتبه الترحيلة
    assert (found["DZ"]["currency"], found["DZ"]["currency_label"], found["DZ"]["currency_decimals"]) == ("DZD", "د.ج", 0)


async def test_the_hidden_row_hides_algeria_from_the_apps_not_from_the_panel(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**صفُّ `0111` نفسُه** (`country_visible = false`) — يُخفيها من `/config` وتراها اللوحةُ مطفأة (§٢٤)."""
    async with session_factory() as session:
        session.add(FeatureFlag(country_code=CountryCode.DZ, feature_key="country_visible", enabled=False))
        await session.commit()

    published = {entry["country_code"] for entry in (await client.get("/config")).json()["countries"]}
    assert "DZ" not in published and {"JO", "LY"} <= published

    panel = (await client.get("/admin/countries", headers=admin_headers)).json()["countries"]
    algeria = next(row for row in panel if row["country_code"] == "DZ")
    assert algeria["visible"] is False and algeria["name"] == "الجزائر"


async def test_algeria_quiet_hours_default_to_algiers(session_factory) -> None:
    async with session_factory() as session:
        setting = await campaigns.get_or_create_settings(session, CountryCode.DZ)
        assert setting.timezone == "Africa/Algiers"
        await session.rollback()


def test_algiers_is_inside_algeria_and_amman_is_not() -> None:
    assert box_for(CountryCode.DZ).holds(ALGIERS["lat"], ALGIERS["lng"])
    assert not box_for(CountryCode.DZ).holds(31.9539, 35.9106)


# ------------------------------------------------------------------ من الطرف إلى الطرف


async def test_an_algerian_estimate_is_whole_dinars_on_the_wire(client: AsyncClient, session_factory) -> None:
    """**حسابٌ يُنشئ كسراً يُقرَّب إلى دينارٍ صحيح، ويخرج على السلك بلا خانات** — وحارسُ العميل في `conftest` يفحص الصيغةَ بعملتها.

    `100 + 10 × 30 + 20 × 5.33 = 506.6 ⇐ 507` (الطريقُ المستعار: ١٠ كم و٢٠ دقيقة).
    """
    async with session_factory() as session:
        session.add(
            PricingRule(
                country_code=CountryCode.DZ,
                vehicle_category=VehicleCategory.ECONOMY,
                base_fare=Decimal("100"),
                price_per_km=Decimal("30"),
                price_per_min=Decimal("5.33"),
                minimum_fare=Decimal("150"),
                cancellation_fee=Decimal("50"),
            )
        )
        await credentials_service.upsert(
            session,
            provider_key=ProviderKey.MAPBOX,
            country_code=None,
            values={"public_token": "pk.test", "secret_token": MAPBOX_SECRET},
            is_active=True,
        )
        await session.commit()

    rider = await rider_session(client, ALGERIAN_RIDER)
    response = await client.post(
        "/rides/estimate",
        json={"pickup": ALGIERS, "dropoff": ALGIERS_EAST, "vehicle_category": "economy"},
        headers=rider["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["currency"] == "DZD"
    assert body["estimated_fare"] == "507" and body["priced_fare"] == "507"


# ------------------------------------------------------------------ حارسٌ ساكن: لا خطوةَ مالٍ مكتوبةً خارج بيتها


APP = Path(__file__).resolve().parents[1] / "app"
#: **خطواتٌ بثلاث خاناتٍ ليست مالاً** — كلٌّ بعلّته، وما عداها يُسقط الحارس
NOT_MONEY_STEPS = {
    "core/currency.py": "بيتُها",
    "services/directions.py": "كيلومتراتُ الطريق",
    "services/route.py": "كيلومتراتُ المسار المسجَّل",
    "services/pauses.py": "دقائقُ الوقفة",
}


def test_no_money_step_is_written_outside_its_home() -> None:
    """**`Decimal("0.001")` على مالٍ خارج `core/currency.py` يُسقط البناء** (§٧٣-ج/٤) — ونداءُ `round_money` بلا عملةٍ كذلك."""
    literal = re.compile(r'Decimal\("0\.001"\)')
    found, bare = [], []
    for path in APP.rglob("*.py"):
        rel = path.relative_to(APP).as_posix()
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            if literal.search(line) and not line.lstrip().startswith("#") and rel not in NOT_MONEY_STEPS:
                found.append(f"{rel}:{number}")
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name == "round_money" and len(node.args) + len(node.keywords) != 2:
                    bare.append(f"{rel}:{node.lineno}")
    assert not found, f"خطوةُ مالٍ مكتوبةٌ خارج بيتها: {found}"
    assert not bare, f"`round_money` بلا عملة: {bare}"


async def test_no_algerian_row_is_seeded_with_an_invented_price() -> None:
    """**لا قيمةَ ماليّةً جزائريّةً تُخترع** (§٧٣-ب): لا تسعيرةَ ولا خطط، والحدودُ والبقشيشُ أصفار، وسقفُ الدَّين فارغ، والسوقُ مخفيّ."""
    from scripts import seed

    assert seed.PRICING_DEFAULTS[(CountryCode.DZ, VehicleCategory.ECONOMY)] is None
    assert seed.PRICING_DEFAULTS[(CountryCode.DZ, VehicleCategory.COMFORT)] is None
    assert seed.PLAN_DEFAULTS[CountryCode.DZ] == []
    assert all(Decimal(value) == 0 for value in seed.WALLET_DEFAULTS[CountryCode.DZ].values())
    assert all(Decimal(value) == 0 for value in seed.TIP_DEFAULTS[CountryCode.DZ].values())
    assert seed.DEBT_CEILING_DEFAULTS[CountryCode.DZ] is None
    flags = seed.FEATURE_DEFAULTS[CountryCode.DZ]
    from app.models.enums import FeatureKey

    assert flags[FeatureKey.COUNTRY_VISIBLE] is False
    assert [key for key, on in flags.items() if on] == [FeatureKey.OTP_VERIFICATION_ENABLED]
