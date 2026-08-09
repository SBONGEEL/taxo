"""حساب السعر — المنطق المالي يُختبر وحدةً بلا شبكة ولا قاعدة (SPEC القسم 16)."""

from __future__ import annotations

from decimal import Decimal

from app.models.enums import CountryCode, VehicleCategory
from app.models.pricing import PricingRule
from app.services.directions import Route
from app.services.pricing import calculate_fare, round_money


def _rule(**overrides: str) -> PricingRule:
    amounts = {
        "base_fare": "1.000",
        "price_per_km": "0.500",
        "price_per_min": "0.100",
        "minimum_fare": "2.000",
        "cancellation_fee": "0.750",
    } | overrides
    return PricingRule(
        country_code=CountryCode.JO,
        vehicle_category=VehicleCategory.ECONOMY,
        **{key: Decimal(value) for key, value in amounts.items()},
    )


def _route(km: str, minutes: str) -> Route:
    return Route(distance_km=Decimal(km), duration_min=Decimal(minutes))


def test_fare_is_base_plus_distance_plus_duration() -> None:
    fare, minimum_applied = calculate_fare(_rule(), _route("10.000", "20.00"))

    # 1.000 + (10 × 0.500) + (20 × 0.100) = 8.000
    assert fare == Decimal("8.000")
    assert minimum_applied is False


def test_minimum_fare_wins_for_short_rides() -> None:
    fare, minimum_applied = calculate_fare(_rule(), _route("0.400", "1.00"))

    # 1.000 + 0.200 + 0.100 = 1.300 < 2.000
    assert fare == Decimal("2.000")
    assert minimum_applied is True


def test_fare_keeps_three_decimals_and_never_floats() -> None:
    fare, _ = calculate_fare(
        _rule(base_fare="0.800", price_per_km="0.350", price_per_min="0.050"),
        _route("7.123", "13.47"),
    )

    # 0.800 + 2.49305 + 0.6735 = 3.96655 → 3.967 بتقريب نصف لأعلى
    assert isinstance(fare, Decimal)
    assert fare == Decimal("3.967")
    assert fare.as_tuple().exponent == -3


def test_zero_length_route_still_charges_minimum() -> None:
    fare, minimum_applied = calculate_fare(_rule(), _route("0.000", "0.00"))

    assert fare == Decimal("2.000")
    assert minimum_applied is True


def test_round_money_uses_half_up_not_bankers_rounding() -> None:
    # التقريب المصرفي في بايثون يعطي 0.002 هنا؛ المطلوب 0.003
    assert round_money(Decimal("0.0025")) == Decimal("0.003")
