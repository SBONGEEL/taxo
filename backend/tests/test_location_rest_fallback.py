"""بديلُ REST حين يسقط المقبس (SPEC §10، وصلَه زرٌّ في 2026-08-19).

**وما يُقاس هنا ليس أن المسار يردّ ٢٠٤، بل أن الكبتن يبقى مرئياً للتوزيع.**
المسارُ مبنيٌّ منذ المرحلة ٤ ومختبَرٌ عرضاً في `bring_online`، لكن **لا شيءَ في
تطبيق الكبتن كان ينادِيه**: فمن سقط مقبسُه اختفى من الخريطة وخسر رحلاتِه، وخسر
الراكبُ سيارة. بابٌ بلا زرّ في أخطر موضع.
"""

from __future__ import annotations

import pytest

from app.core.redis_client import get_redis_client

pytestmark = pytest.mark.asyncio


async def test_rest_alone_keeps_a_driver_dispatchable(
    client, session_factory, jordan_settings
) -> None:
    """**بثٌّ عبر REST وحدَه يكفي ليبقى الكبتنُ في دائرة التوزيع.**

    وهذا هو شرطُ صلاحية البديل: لو كان المقبسُ وحدَه ما يُدخل الفهرسَ الجغرافي
    لصار البديلُ طمأنينةً كاذبة — يردّ ٢٠٤ ولا يجعل أحداً مرئياً.
    """
    from app.services import geo
    from tests.helpers import NEAR_PICKUP, approved_driver, rider_session

    redis_client = get_redis_client()
    driver = await approved_driver(client, session_factory)
    rider = await rider_session(client)

    online = await client.post("/drivers/me/online", headers=driver["headers"])
    assert online.status_code == 200, online.text

    # ولا مقبسَ في هذا الاختبار أصلاً — REST وحدَه
    located = await client.post(
        "/drivers/me/location",
        json={**NEAR_PICKUP, "heading": 90},
        headers=driver["headers"],
    )
    assert located.status_code == 204, located.text

    # **والقياسُ من الباب الذي يراه الراكب** — لا من دالّةٍ داخلية
    nearby = await client.get(
        "/drivers/nearby",
        params={"lat": NEAR_PICKUP["lat"], "lng": NEAR_PICKUP["lng"]},
        headers=rider["headers"],
    )
    assert nearby.status_code == 200, nearby.text
    assert len(nearby.json()) == 1, (
        "كبتنٌ يبثّ عبر REST ولا يظهر للراكب — فالبديلُ طمأنينةٌ كاذبة"
    )

    # ومفتاحُ الحضور موجود: هو ما يجعل موضعَه في الفهرس حيّاً لا بائتاً
    import uuid as _uuid

    from app.models.enums import CountryCode

    position = await geo.last_position(
        redis_client,
        driver_id=_uuid.UUID(str(driver["driver_id"])),
        country_code=CountryCode.JO,
    )
    assert position is not None


async def test_a_rest_broadcast_refreshes_presence_before_it_expires(
    client, session_factory, jordan_settings
) -> None:
    """**والبثُّ المتكرر يجدّد الحضور** — وهو ما يقيس صلاحيةَ فترة البديل.

    مفتاحُ `geo:presence` عمرُه ٦٠ ثانية، وفترةُ البديل في التطبيق ١٠ — فستّةُ
    أضعافِ هامش. وما يُثبَّت هنا أن كلَّ بثٍّ يعيد المهلةَ إلى أولها، فسلسلةُ
    طلباتٍ كلَّ عشر ثوانٍ لا تترك الكبتنَ يختفي بين اثنين.
    """
    from tests.helpers import NEAR_PICKUP, approved_driver

    redis_client = get_redis_client()
    driver = await approved_driver(client, session_factory)
    await client.post("/drivers/me/online", headers=driver["headers"])

    key = f"geo:presence:{driver['driver_id']}"
    for _ in range(3):
        answer = await client.post(
            "/drivers/me/location",
            json={**NEAR_PICKUP, "heading": 90},
            headers=driver["headers"],
        )
        assert answer.status_code == 204, answer.text
        ttl = await redis_client.ttl(key)
        # يُعاد إلى أعلى قيمةٍ في كل بثّ — لا يتناقص عبر الطلبات
        assert ttl > 45, f"مهلةُ الحضور {ttl} — البثُّ لا يجدّدها"
