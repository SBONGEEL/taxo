"""**خيارُ البطاقة لا يُنشر بلا عقد بطاقةٍ نشط** (أمرُ المالك ٢٠٢٦-١١-٢١ الخامس، البند ٤).

قِيس على الإنتاج ٢١/١١: كبتنٌ اختار «البطاقة» لاشتراكه في دولةٍ مفتاحُها مرفوعٌ بيدٍ ولا عقدَ Telr فيها، فوقع على 503
`card_gateway_unavailable`. **و`/config` بيتُ ما تعرضه التطبيقاتُ الثلاث** (اشتراكُ الكبتن، شحنُ المحفظة، دفعُ الرحلة — كلُّها
`useFeature(…, "card_enabled")`)، فالمفتاحُ يُنشر **كما يعمل**: مرفوعاً بلا عقدٍ نشطٍ مطفأ، ومع العقد مشتعل.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import enable_card_provider, enable_features


async def _card(client: AsyncClient, country: str = "JO") -> bool:
    body = (await client.get("/config", params={"country_code": country})).json()
    return body["countries"][0]["features"]["card_enabled"]


async def test_raised_flag_without_a_contract_is_published_off(client: AsyncClient, session_factory) -> None:
    await enable_features(session_factory, "card_enabled")
    assert await _card(client) is False


async def test_active_contract_publishes_it_on(client: AsyncClient, session_factory) -> None:
    await enable_card_provider(session_factory)
    assert await _card(client) is True


async def test_the_panel_still_sees_the_written_flag(client: AsyncClient, session_factory, admin_headers: dict) -> None:
    """**الصفُّ لا يُمسّ**: اللوحةُ ترى ما كُتب، والتطبيقُ يرى ما يعمل."""
    await enable_features(session_factory, "card_enabled")
    flags = (await client.get("/admin/settings/feature-flags", headers=admin_headers)).json()
    assert {row["country_code"]: row["flags"] for row in flags}["JO"]["card_enabled"] is True
    assert await _card(client) is False
