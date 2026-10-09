"""لا كسورَ في المال (SPEC §٧٠) — **الجزءُ الثالث: ما تقرؤه الشاشاتُ من الخلفية لتعرض التقريبَ بلا حساب** (§١٤).

الواجهاتُ لا تحسب مالاً: سطرُ «تقريب» في تطبيقَي الراكب والكبتن يُقرأ من `fare_lines`، **واللوحةُ لا تنشر لها `fare_lines`** —
فكان فرقُ التقريب في تفصيل رحلتها لا يُعرض إلا بطرح «النهائيّة − المقدَّرة − الرسوم» في الشاشة، وهو حسابُ مالٍ يمنعه §١٤
**ويخلط التقريبَ بانحراف الطريق**. فصار حقلاً: `AdminRideDetail.rounding_amount` **من سجلّ التقريب** (`money_roundings`)، القيدِ
الصريح لكلِّ فلس.

ما يحرسه:
- **مشتعلاً**: الحقلُ فرقُ صفِّ السجلّ بعينه، **وهو مبلغُ سطر «تقريب» نفسُه** الذي يقرؤه التطبيقان — موجباً (المثال أ) وسالباً
  (للأدنى).
- **مطفأً**: `null` لا صفر — السجلُّ لا يحمل صفراً، وصفرٌ في حقلِ مالٍ يُقرأ مبلغاً.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import DRIVER, approved_driver, bring_online, rider_session
from tests.test_rounding import _complete, _drive, _enable, _lines, _requested, _route


async def _admin_detail(client: AsyncClient, admin_headers: dict, ride_id: str) -> dict:
    detail = await client.get(f"/admin/rides/{ride_id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    return detail.json()


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        # **(أ)**: `3.364 ⇐ 3.500` و«تقريب» `+0.136`
        ("nearest", "0.136"),
        # **للأدنى**: `3.364 ⇐ 3.000` وسطرٌ سالب
        ("down", "-0.364"),
    ],
)
async def test_the_panel_reads_the_ride_rounding_from_the_journal(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    session_factory,
    monkeypatch,
    mode: str,
    expected: str,
) -> None:
    """**اللوحةُ ترى فرقَ التقريب من سجلّه** — وهو سطرُ «تقريب» الذي يراه الراكبُ والكبتن حرفاً، بلا حسابٍ في شاشة."""
    _route(monkeypatch, "3.328", "7.00")
    await _enable(client, admin_headers, mode=mode)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    ride = await _requested(client, rider["headers"])
    # **قبل الإنهاء لا صفّ** — التقريبُ المحفوظُ مرّةً عند الإنهاء
    assert (await _admin_detail(client, admin_headers, ride["id"]))["rounding_amount"] is None

    await _drive(client, ride, driver)
    done = await _complete(client, ride, driver)
    detail = await _admin_detail(client, admin_headers, ride["id"])
    assert detail["rounding_amount"] == expected
    assert detail["rounding_amount"] == _lines(done)["rounding"], "ما تراه اللوحةُ هو سطرُ التطبيقين بعينه"
    assert detail["final_fare"] == done["final_fare"]


async def test_switched_off_the_panel_reads_null_not_zero(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory, monkeypatch
) -> None:
    """**مطفأً `null` لا `0.000`** — لا صفَّ في السجلّ، وصفرٌ في حقلِ مالٍ يُقرأ مبلغاً فيرسم سطراً لا وجودَ له."""
    _route(monkeypatch, "3.328", "7.00")
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    ride = await _requested(client, rider["headers"])
    await _drive(client, ride, driver)
    done = await _complete(client, ride, driver)
    assert "rounding" not in _lines(done)
    assert (await _admin_detail(client, admin_headers, ride["id"]))["rounding_amount"] is None
