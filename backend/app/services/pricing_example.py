"""مثالُ التسعير في اللوحة (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §٥/١٤) — **رحلةٌ مفترضةٌ تُسعَّر بالدوالّ التي تُسعِّر الرحلةَ الحقيقيّة**.

المالكُ يكتب مسافةً وزمناً (ومحطاتٍ وانتظاراً ووقفةً إن شاء) فيرى الأجرةَ مفصَّلةً حقلاً حقلاً بالقيم الحاليّة — **أو بقيمٍ لم تُحفظ
بعد** ليرى أثرَ ما سيكتبه قبل أن يكتبه.

**ولا صيغةَ هنا**: أجرةُ الطريق من `pricing.fare_breakdown` حرفاً (هي ما يُسعِّر به `estimate` والإنهاء)، ورسمُ الانتظار من
`pricing.waiting_charge`، والوقفةُ وانتظارُ الوصول من `pauses.charge_of`، والجمعُ كجمع `rides._final_fare`، والتقريبُ من
`rounding.rounded`. **فمثالٌ يخالف ما يدفعه الراكبُ لا ينشأ إلا إن افترقت الدوالُّ نفسُها** — وهو ما تحرسه اختباراتُها.

**وما لا يدخله المثال** يُقال في الشاشة: رسومُ الكبتن (المطار) والمنطقةُ الوعرة والذروةُ والخصومات — لكلٍّ بابُه.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.core.currency import currency_for_country
from app.models.enums import Currency
from app.models.pricing import PricingRule
from app.services import pauses, pricing, rounding
from app.services.directions import Route
from app.services.pricing import FareLine, as_money


@dataclass(frozen=True, slots=True)
class PricingExample:
    currency: Currency
    #: **أجرةُ الطريق** كما تُقدَّر قبل الطلب — وأسطرُها تُجمع إليها حرفاً (`fare_breakdown`)
    fare: Decimal
    minimum_fare_applied: bool
    lines: tuple[FareLine, ...]
    #: رسمُ الانتظار عند المحطات (لكلِّ محطةٍ مهلتُها) · والوقفةُ أثناء الرحلة (بلا مهلة) · وانتظارُ الوصول (بمهلته)
    waiting_charge: Decimal
    pause_charge: Decimal
    arrival_charge: Decimal
    #: **الأجرةُ النهائيّة قبل التقريب** — كجمع `_final_fare`
    total: Decimal
    rounding_enabled: bool
    #: **ما يدفعه الراكبُ** بعد تقريب السوق (§٧٠) — ويساوي `total` والتقريبُ مطفأ
    payable: Decimal


def _minutes_ago(now: datetime, minutes: Decimal) -> datetime:
    return now - timedelta(seconds=float(minutes * 60))


def example(
    rule: PricingRule,
    *,
    distance_km: Decimal,
    duration_min: Decimal,
    stops: int,
    wait_minutes_per_stop: Decimal,
    pause_minutes: Decimal,
    arrival_wait_minutes: Decimal,
    policy: rounding.RoundingPolicy,
) -> PricingExample:
    currency = currency_for_country(rule.country_code)
    fare, minimum_applied, lines = pricing.fare_breakdown(
        rule, Route(distance_km=distance_km, duration_min=duration_min), stops
    )

    # **محطاتٌ وقفاتٌ مفترضةٌ بختمين** — الدوالُّ نفسُها تقيس ما بين الختمين كما تقيسه على رحلةٍ حقيقيّة
    now = datetime.now(UTC)
    stands = [
        SimpleNamespace(arrived_at=_minutes_ago(now, wait_minutes_per_stop), resumed_at=now)
        for _ in range(stops if wait_minutes_per_stop > 0 else 0)
    ]
    waiting = pricing.waiting_charge(
        stands,  # type: ignore[arg-type]
        free_minutes=rule.stop_free_minutes,
        price_per_min=rule.stop_price_per_min,
        now=now,
        currency=currency,
    )

    def _pause(minutes: Decimal, free: int) -> Decimal:
        if minutes <= 0:
            return Decimal("0.000")
        stand = SimpleNamespace(
            started_at=_minutes_ago(now, minutes),
            ended_at=now,
            price_per_min_at_pause=rule.pause_price_per_min,
            free_minutes_at_pause=free,
        )
        return pauses.charge_of(stand, now, currency)  # type: ignore[arg-type]

    pause = _pause(pause_minutes, 0)
    arrival = _pause(arrival_wait_minutes, rule.arrival_free_minutes)

    total = pricing.round_money(fare + waiting + pause + arrival, currency)
    return PricingExample(
        currency=currency,
        fare=fare,
        minimum_fare_applied=minimum_applied,
        lines=tuple(lines),
        waiting_charge=as_money(waiting),
        pause_charge=as_money(pause),
        arrival_charge=as_money(arrival),
        total=total,
        rounding_enabled=policy.enabled,
        payable=rounding.rounded(total, policy),
    )
