# -*- coding: utf-8 -*-
"""نطاقُ الخدمة — **حدٌّ بالبلد لا بالمسافة** (قرارُ المالك ٢٠٢٦-٠٩-١٠).

**والقياساتُ أربعةٌ بأعيانها**، وكلٌّ منها يسقط بحذف ما يحرسه:

١) عمّان ← طرابلس تُرفض **عند التقدير وعند الطلب معاً**.
٢) **العقبة ← إربد (نحو ٣٥٠ كم) تمرّ** — فالحدُّ بالبلد لا بالمسافة.
٣) البابان مقيسان **منفردين**: حذفُ النداء من أحدهما يُسقط اختبارَه وحدَه.
٤) كلُّ سوقٍ في `CountryCode` له صندوقٌ مصرَّح — فلا يُشحن سوقٌ بلا حدّ.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.exceptions import OutsideServiceArea
from app.core import service_area
from app.models.enums import CountryCode
from tests.helpers import PICKUP, DROPOFF, rider_session

# نقاطٌ حقيقيةٌ تُقرأ بأسمائها لا بأرقامٍ عارية
AMMAN = (31.9539, 35.9106)
AQABA = (29.5321, 35.0063)
IRBID = (32.5556, 35.8500)
TRIPOLI = (32.8935, 13.3669)


class _P:
    """نقطةٌ ببنية `lat`/`lng` — نفسُ ما يمرّره البابان."""

    def __init__(self, lat: float, lng: float) -> None:
        self.lat = lat
        self.lng = lng


def _pt(pair: tuple[float, float]) -> _P:
    return _P(*pair)


# ─────────────────────────────────────────── ٤) اكتمالُ الأسواق


def test_every_market_declares_a_box() -> None:
    """**سوقٌ بلا صندوقٍ لا يُشحن** — وصفرٌ مقروءٌ عطبٌ لا سلامة."""
    missing = [c for c in CountryCode if c not in service_area.MARKET_BOX]
    assert not missing, f"أسواقٌ بلا صندوقٍ مصرَّح: {[c.value for c in missing]}"


def test_each_box_holds_its_own_capital() -> None:
    """**الصندوقُ يحوي البلدَ** — ولو ضاق لَرفض رحلةً مشروعة."""
    capitals = {CountryCode.JO: AMMAN, CountryCode.LY: (32.8872, 13.1913)}
    for country, (lat, lng) in capitals.items():
        assert service_area.MARKET_BOX[country].holds(lat, lng), country.value


# ─────────────────────────────────────────── ٢) الحدُّ بالبلد لا بالمسافة


def test_a_long_ride_inside_the_country_passes() -> None:
    """**العقبة ← إربد نحو ٣٥٠ كم — وتمرّ.**

    وهذا هو القياسُ الذي يُسقط أيَّ حدٍّ بالمسافة لو كُتب يوماً.
    """
    service_area.require_inside_market(CountryCode.JO, [_pt(AQABA), _pt(IRBID)])


def test_a_short_ride_across_the_border_is_refused() -> None:
    """ولا يمرّ ما خرج ولو كان أقربَ من رحلةٍ داخليةٍ طويلة."""
    with pytest.raises(OutsideServiceArea):
        service_area.require_inside_market(CountryCode.JO, [_pt(AMMAN), _pt(TRIPOLI)])


def test_the_pickup_is_checked_not_only_the_dropoff() -> None:
    """**الطرفان يُفحصان** — وأربعون من اثنتين وستّين كان انطلاقُها هو الخارج."""
    with pytest.raises(OutsideServiceArea):
        service_area.require_inside_market(CountryCode.JO, [_pt(TRIPOLI), _pt(AMMAN)])


def test_the_message_names_the_country_and_carries_no_latin_letter() -> None:
    """نصٌّ عربيٌّ باسم البلد من بيته — لا «الأردن» مخبوزةً في الشيفرة."""
    with pytest.raises(OutsideServiceArea) as caught:
        service_area.require_inside_market(CountryCode.JO, [_pt(TRIPOLI)])
    message = caught.value.message
    assert "الأردن" in message, message
    assert not any("a" <= ch.lower() <= "z" for ch in message), message


# ─────────────────────────────── ١+٣) البابان — مقيسان منفردين عبر مسارَيهما

TRIPOLI_POINT = {"lat": 32.8935, "lng": 13.3669, "address": "طرابلس"}


async def test_the_estimate_door_refuses_a_point_outside_the_market(
    client: AsyncClient, jordan_settings: None
) -> None:
    """**بابُ التقدير** — ولو قَبِل هنا ورُفض عند التأكيد لبنى الراكبُ على رقمٍ ثم رُدّ."""
    rider = await rider_session(client)
    response = await client.post(
        "/rides/estimate",
        headers=rider["headers"],
        json={
            "pickup": PICKUP,
            "dropoff": TRIPOLI_POINT,
            "vehicle_category": "economy",
        },
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "outside_service_area", body
    assert "الأردن" in body["message"], body


async def test_the_request_door_refuses_a_point_outside_the_market(
    client: AsyncClient, jordan_settings: None
) -> None:
    """**بابُ الطلب** — وهو الذي ينشئ الصفَّ، فحارسُه لا يكفي في التقدير وحدَه."""
    rider = await rider_session(client)
    response = await client.post(
        "/rides",
        headers=rider["headers"],
        json={
            "pickup": PICKUP,
            "dropoff": TRIPOLI_POINT,
            "vehicle_category": "economy",
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "outside_service_area", response.text


async def test_a_ride_wholly_inside_the_market_still_passes_both_doors(
    client: AsyncClient, jordan_settings: None
) -> None:
    """**ولا يصيح على السليم** — نفسُ الطلب داخل البلد يمرّ من البابين."""
    rider = await rider_session(client)
    quote = await client.post(
        "/rides/estimate",
        headers=rider["headers"],
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
    )
    assert quote.status_code == 200, quote.text
    made = await client.post(
        "/rides",
        headers=rider["headers"],
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
    )
    assert made.status_code == 201, made.text
