"""«اختبار الاتصال» يختبر العقدَ نفسَه — لا يسقط مفتاحٌ إلى اختبار عقدٍ آخر، وفيسبوك يقرأ الصفحةَ ويرفض اسمَ المستخدم."""

from __future__ import annotations

import pytest

from app.core.exceptions import AppError
from app.models.enums import ProviderKey
from app.services.facebook import graph
from app.services.providers import health


async def test_facebook_reads_the_page_by_numeric_id(monkeypatch) -> None:
    async def summary(page):
        return {"id": "111911523627964", "name": "Taxo", "followers_count": 12}

    monkeypatch.setattr(graph, "summary", summary)
    detail = await health._run(ProviderKey.FACEBOOK_PAGE, {"page_id": "111911523627964", "page_token": "t"}, None)
    assert "Taxo" in detail and "111911523627964" in detail


async def test_facebook_refuses_a_username(monkeypatch) -> None:
    async def summary(page):
        return {"id": "111911523627964", "name": "Taxo"}

    monkeypatch.setattr(graph, "summary", summary)
    with pytest.raises(AppError) as caught:
        await health._run(ProviderKey.FACEBOOK_PAGE, {"page_id": "@taxoapp", "page_token": "t"}, None)
    assert "111911523627964" in caught.value.message


async def test_facebook_error_is_readable(monkeypatch) -> None:
    async def summary(page):
        raise graph.FacebookError("Invalid OAuth access token", 190)

    monkeypatch.setattr(graph, "summary", summary)
    with pytest.raises(AppError) as caught:
        await health._run(ProviderKey.FACEBOOK_PAGE, {"page_id": "1", "page_token": "t"}, None)
    assert "Invalid OAuth" in caught.value.message


async def test_no_key_falls_through_to_payout(monkeypatch) -> None:
    """**المفتاحُ بلا اختبارٍ يقول ذلك** — لا يُجيب عنه عقدُ التحويلات."""
    called: list[str] = []

    async def payout(values):
        called.append("payout")
        return "ok"

    monkeypatch.setattr(health, "_test_payout", payout)
    with pytest.raises(AppError) as caught:
        await health._run(ProviderKey.EMAIL, {}, None)
    assert called == [] and "لا اختبار" in caught.value.message
