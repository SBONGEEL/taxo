"""العنوانُ بلا فاصلةٍ فارغة (اختبارُ طلب الرحلة ٢٠٢٦-١١-١٩) — `maps.tidy_address`."""

from app.services.maps import tidy_address


def test_an_empty_level_leaves_no_empty_comma():
    assert tidy_address("شارع بهجت الحمصي 9، ، عمّان، الأردن") == "شارع بهجت الحمصي 9، عمّان، الأردن"
    assert tidy_address("الاردن / الممر الاول ، ، عمّان، الأردن") == "الاردن / الممر الاول، عمّان، الأردن"


def test_latin_commas_and_order_are_kept():
    assert tidy_address("Rue Didouche, , Alger, Algérie") == "Rue Didouche، Alger، Algérie"
    assert tidy_address("أ، ب، ج") == "أ، ب، ج"


def test_nothing_left_is_none():
    assert tidy_address(None) is None
    assert tidy_address("") is None
    assert tidy_address(" ، , ") is None
