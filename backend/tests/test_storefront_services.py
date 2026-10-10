"""**بلاطاتُ «خدماتك» تتبع مفاتيحَ السوق — ولا «قريباً» عالقةٌ بعد الإشعال** (أمرُ المالك ٢٠٢٦-١٠-١٠، SPEC §٧٢).

**العلّةُ مقيسةٌ على الإنتاج**: رأى المالكُ «قريباً» على المطار والطرد والرحلات في رئيسية الكبتن **وقد أشعل كلَّ شيءٍ في الأردن** —
البلاطاتُ صفوفٌ كتبتها اللوحةُ «قريباً» بلا مقصد، ولا شيءَ يربطها بالمفاتيح. **فالحارسُ هنا في الاتجاهين**:
* **وقتَ التشغيل**: بلاطةُ خدمةٍ مشتعلةٍ لا تُرسل «قريباً» أبداً، ومطفأةٍ لا تُرسل «تُفتح»؛ و«قريباً» بلا مقصدٍ لا تُرسل؛ ودورٌ لا شاشةَ له لا يرى.
* **وقتَ البناء** في `tools/check-service-tiles.mjs` (حاويةُ الاختبار لا ترى الواجهتين): لكلِّ خدمةٍ شاشةٌ في تطبيق من يراها، و«قريباً»
  لا تُكتب نصّاً إلا حيث تُقرأ من مفتاحٍ أو من حال البلاطة.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.helpers import approved_driver, enable_features, rider_session

pytestmark = pytest.mark.usefixtures("jordan_settings")


async def _tile(client: AsyncClient, headers: dict, **fields) -> dict:
    body = {"country_code": "JO", "icon": "package", "audience": "by_country", "status": "soon"} | fields
    response = await client.post("/admin/settings/service-tiles", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _seen(client: AsyncClient, headers: dict, surface: str) -> dict[str, str]:
    body = (await client.get("/storefront", params={"surface": surface}, headers=headers)).json()
    return {tile["key"]: tile["status"] for tile in body["tiles"]}


async def test_a_service_tile_follows_the_market_switch_not_its_stored_status(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**«قريباً» المكتوبةُ في الصفّ لا تبقى بعد الإشعال** — المفتاحُ يحكم، في الاتجاهين."""
    await _tile(client, admin_headers, key="parcel", title="طرود", destination="/services/parcel")
    await _tile(client, admin_headers, key="offers", title="عروض", destination="/services/offers")
    await _tile(client, admin_headers, key="taxo_man", title="Taxo Man", audience="all_drivers")
    driver = await approved_driver(client, session_factory)
    rider = await rider_session(client)

    # مطفأة ⇐ «قريباً» — ولا بلاطةَ بلا مقصد
    assert await _seen(client, driver["headers"], "driver") == {"parcel": "soon", "offers": "soon"}
    # **والراكبُ لا شاشةَ عروضٍ له** فلا يراها
    assert await _seen(client, rider["headers"], "rider") == {"parcel": "soon"}

    await enable_features(session_factory, "parcel_enabled", "subscription_offers_enabled")
    assert await _seen(client, driver["headers"], "driver") == {"parcel": "active", "offers": "active"}
    assert await _seen(client, rider["headers"], "rider") == {"parcel": "active"}


async def test_a_hidden_service_tile_stays_hidden_whatever_the_switch(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**«مخفيّ» قرارُ المشرف** — المفتاحُ يقرّر «تُفتح» أو «قريباً» لما يُعرض، لا يُظهر ما أخفاه."""
    await _tile(client, admin_headers, key="airport", title="مطارات", destination="/services/airport", status="hidden")
    await enable_features(session_factory, "airport_enabled")
    driver = await approved_driver(client, session_factory)
    assert await _seen(client, driver["headers"], "driver") == {}


async def test_market_and_taxo_man_say_soon_and_the_delivery_switch_refuses_to_turn_on(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**«تسوّق» و«Taxo Man» «قريباً» بمفتاح التوصيل** (SPEC §٧٢-هـ) — **وبابُ الإشعال يرفضه** ما دام التوصيلُ غيرَ مبنيّ."""
    await _tile(client, admin_headers, key="shop", title="تسوق", audience="all_riders", destination="/services/market")
    await _tile(client, admin_headers, key="taxo_man", title="Taxo Man", audience="all_drivers", destination="/services/delivery")
    driver = await approved_driver(client, session_factory)
    rider = await rider_session(client)
    assert await _seen(client, driver["headers"], "driver") == {"taxo_man": "soon"}
    assert await _seen(client, rider["headers"], "rider") == {"shop": "soon"}

    on = await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "JO", "feature_key": "delivery_enabled", "enabled": True},
        headers=admin_headers,
    )
    assert on.status_code == 422 and "مؤجَّل" in on.json()["message"]
    assert await _seen(client, driver["headers"], "driver") == {"taxo_man": "soon"}
