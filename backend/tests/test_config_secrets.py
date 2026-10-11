"""**أسرارُ الإقلاع** — ما يقف بدونه الإقلاعُ ويسمّيه، **وما يقف بدونه الإنتاجُ وحدَه** (قرارُ المالك 2026-10-11).

`TAXO_CARD_CODE_PEPPER` شرطُ إقلاعٍ في الإنتاج: غائباً أو قصيراً يقف ويسمّيه **ولا يطبع قيمةً**؛ وفي التطوير والاختبار يُقلع بلاه
(بابُ البطاقات `503` كما بُني — `test_taxo_cards.py`).
"""

import pytest

from app.core.config import Settings, _require_secrets

DB = "postgresql+asyncpg://u:p@db:5432/x"
GOOD = "a" * 64


def _settings(**overrides) -> Settings:
    return Settings(database_url=DB, **overrides)


def test_production_refuses_to_boot_without_the_card_pepper() -> None:
    with pytest.raises(RuntimeError) as caught:
        _require_secrets(_settings(environment="production", taxo_card_code_pepper=None))
    assert "TAXO_CARD_CODE_PEPPER" in str(caught.value)


def test_production_refuses_an_empty_or_short_pepper_and_never_prints_it() -> None:
    for weak in ("", "short-secret-value-31-chars-xx"):
        with pytest.raises(RuntimeError) as caught:
            _require_secrets(_settings(environment="production", taxo_card_code_pepper=weak))
        assert "TAXO_CARD_CODE_PEPPER" in str(caught.value)
        if weak:
            assert weak not in str(caught.value)


def test_production_boots_with_the_pepper() -> None:
    values = _settings(environment="production", taxo_card_code_pepper=GOOD)
    assert _require_secrets(values) is values


@pytest.mark.parametrize("environment", ["development", "test"])
def test_other_environments_boot_without_it(environment: str) -> None:
    values = _settings(environment=environment, taxo_card_code_pepper=None)
    assert _require_secrets(values) is values


def test_database_url_still_required_everywhere() -> None:
    with pytest.raises(RuntimeError) as caught:
        _require_secrets(Settings(database_url="", environment="development"))
    assert "DATABASE_URL" in str(caught.value)
