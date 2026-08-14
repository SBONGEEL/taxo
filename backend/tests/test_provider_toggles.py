"""مفاتيحُ التشغيل في العقود: نصٌّ من اللوحة لا يُقرأ عكسَ معناه.

**العطبُ الذي أنشأ هذا الملف**: بطاقةُ العقد لم تكن تصف نوعَ الحقل، فرسمت
اللوحةُ مفتاحَ «مزوّد وهمي» صندوقَ نصّ. فمن أطفأه كتب `"false"`، و`bool("false")`
في بايثون **صادق** — فاشتغل المزوّدُ الوهميُّ وهو مطفأ، في سبعة عقود ومعها
`test_mode` في بوابة البطاقة. ثمانيةُ مواضعَ من شكلٍ واحد.

**ولا يُكتفى باختبار Firebase**: العطبُ ليس في مزوّدٍ بل في **شكل القراءة**،
فيُختبر الشكلُ نفسُه على كلِّ عقدٍ له مفتاح.
"""

from __future__ import annotations

import pytest

from app.services.providers import credentials as credentials_service

FALSY = ["false", "False", "FALSE", "0", "no", "off", "", "  false  "]
TRUTHY = ["true", "True", "1", "yes", "on"]


@pytest.mark.parametrize("raw", FALSY)
def test_a_written_no_is_read_as_no(raw: str) -> None:
    """«لا» بأيِّ صيغةٍ كتبها مشرفٌ تبقى «لا»."""
    assert credentials_service.is_mock({"use_mock": raw}) is False


@pytest.mark.parametrize("raw", TRUTHY)
def test_a_written_yes_is_read_as_yes(raw: str) -> None:
    assert credentials_service.is_mock({"use_mock": raw}) is True


def test_a_real_boolean_still_works() -> None:
    """`scripts/seed.py` يكتب منطقاً حقيقياً — فلا يُكسر بالتطبيع."""
    assert credentials_service.is_mock({"use_mock": True}) is True
    assert credentials_service.is_mock({"use_mock": False}) is False


def test_a_missing_key_is_off() -> None:
    """عقدٌ بلا مفتاحٍ ليس وهمياً — والغيابُ إطفاءٌ لا اشتعال."""
    assert credentials_service.is_mock({"project_id": "x"}) is False
    assert credentials_service.is_mock(None) is False


def test_every_toggle_field_is_declared_not_guessed() -> None:
    """المفاتيحُ تُقرأ من البطاقات — فحقلٌ جديدٌ بنوع `toggle` يُطبَّع تلقائياً."""
    keys = credentials_service._toggle_keys()
    assert "use_mock" in keys
    assert "test_mode" in keys, "مفتاحُ وضع الاختبار في بوابة البطاقة — وهو ثامنُ المواضع"


def test_the_card_gateway_test_mode_is_not_a_string_switch() -> None:
    """`test_mode="false"` كان يضع بوابةَ الدفع في وضع الاختبار."""
    assert credentials_service.is_on({"test_mode": "false"}, "test_mode") is False
    assert credentials_service.is_on({"test_mode": "true"}, "test_mode") is True
