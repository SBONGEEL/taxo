"""**العددُ مع معدوده** (أمرُ المالك ٢٠٢٦-١١-٢٥: «يتبقّى 1 أيام» ⇒ «يتبقّى يوم واحد») — `core/arabic_count.py`.

يُقاس **الجدولُ كلُّه** (الصفر · ١ · ٢ رفعاً وجرّاً · ٣–١٠ · ١١–٩٩ · المئاتُ بآخر خانتين)، **ونصوصُ الإشعارات التي كانت تكتب
العددَ في القالب** تُبنى به الآن — فـ«بقي لك 1 أيام» لا تعود.
"""

from __future__ import annotations

import pytest

from app.core.arabic_count import count_of
from app.services import launch_campaign, verification_campaign


@pytest.mark.parametrize(
    ("n", "after", "expected"),
    [
        (0, False, "0 يوم"),
        (1, False, "يوم واحد"),
        (2, False, "يومان"),
        (2, True, "يومين"),
        (3, False, "3 أيام"),
        (10, False, "10 أيام"),
        (11, False, "11 يوماً"),
        (60, True, "60 يوماً"),
        (99, False, "99 يوماً"),
        (100, False, "100 يوم"),
        (102, False, "102 يوم"),
        (103, False, "103 أيام"),
        (111, False, "111 يوماً"),
    ],
)
def test_days_take_the_right_form(n: int, after: bool, expected: str) -> None:
    assert count_of(n, "day", after=after) == expected


def test_every_unit_has_six_forms() -> None:
    from app.core.arabic_count import UNITS

    assert set(UNITS) == {"day", "hour", "minute", "ride", "point"}
    assert count_of(1, "minute") == "دقيقة واحدة" and count_of(2, "hour", after=True) == "ساعتين"
    assert count_of(15, "minute") == "15 دقيقةً" and count_of(5, "ride") == "5 رحلات"


def test_the_templates_carry_the_counted_word_not_the_number() -> None:
    """**القالبُ يحمل المعدودَ كاملاً** — ولا يبقى فيه «{days} أيام» ولا «{days} يوماً»."""
    for text in (launch_campaign.BANNER, *verification_campaign.REMINDER_TEXTS):
        for unit in ("أيام", "يوماً"):
            assert f"}} {unit}" not in text, text
    banner = launch_campaign.BANNER.format(pre=count_of(60, "day", after=True), post=count_of(7, "day"))
    assert banner == "سجّل قبل الإطلاق واحصل على 60 يوماً مجاناً بدون عمولة — بعد الإطلاق 7 أيام فقط"
    assert verification_campaign.REMINDER_TEXTS[1].format(days=count_of(1, "day")).startswith("بقي يوم واحد لتأكيد رقمك")
