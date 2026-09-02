"""الرحلةُ الجارية في ملفِّ الكبتن — البند ٦ (§39٫٦).

**وهو البابُ الثاني الذي يقرن هويةً بموقع**، فما يُختبر هنا ليس «أترسم
الخريطةُ خطّاً» بل الأربعةُ التي تجعله بابَ مواقعَ لا بابَ عرض:

1. **`admin` وحدَه** — ولو فُتح للدعم لَصار حصرُ الخريطة على المشرف بلا معنى:
   من يتتبّع كبتناً بمعرِّفه يتتبّعهم واحداً واحداً.
2. **ولا رحلةَ = صمتٌ** (`null`)، لا خريطةٌ فارغةٌ تُقرأ عطباً.
3. **وصمتُ البثِّ يُقال ولا يُخترع له موضع**: الرحلةُ تبقى والدبّوسُ يذهب.
4. **وقيدُ التدقيق يخصُّه ولا يستعير قيدَ الخريطة** — ويُكتب حين يخرج موضعٌ
   فعلاً، فقيدٌ عن قراءةٍ لم تكشف موضعاً يصف أكثرَ ممّا جرى.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.enums import AuditAction
from tests.helpers import (
    DRIVER,
    accepted_ride,
    add_route_points,
    approved_driver,
    bring_online,
    rider_session,
)

# مسارٌ معلومُ الشكل — ثلاثُ نقاطٍ تكفي لتقول «خطٌّ لا نقطة»
_ROUTE = [(31.9539, 35.9106), (31.9600, 35.9150), (31.9660, 35.9200)]


async def _live(client: AsyncClient, headers: dict, driver_id):
    response = await client.get(
        f"/admin/live/drivers/{driver_id}/ride", headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _driver_live_entries(session_factory) -> int:
    async with session_factory() as session:
        return await session.scalar(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(
                AdminAuditLog.action == AuditAction.READ,
                AdminAuditLog.entity_type == "driver_live",
            )
        )


async def test_no_active_ride_is_silence_not_an_empty_map(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """كبتنٌ متصلٌ بلا رحلة ⇒ `null` — **فيصمت القسمُ ولا يرسم خريطةً فارغة**.

    وخريطةٌ بلا شيءٍ عليها تُقرأ عطباً في اللوحة لا «لا رحلةَ الآن»، وهي «لا
    نتائج» التي ليست «لا بيانات» بعينها.
    """
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)

    assert await _live(client, admin_headers, driver["driver_id"]) is None
    # **ولا قيدَ لِما لم يُكشف**: لم يخرج موضعٌ، فلا اقترانَ يُسجَّل
    assert await _driver_live_entries(session_factory) == 0


async def test_active_ride_carries_its_route_and_his_position(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """الرحلةُ الجارية ومعها مسارُها من `ride_route_points` وموضعُه من البثّ."""
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider["headers"], driver)
    await add_route_points(session_factory, ride["id"], _ROUTE)

    body = await _live(client, admin_headers, driver["driver_id"])

    assert body is not None
    assert body["ride_id"] == ride["id"]
    assert body["status"] == "accepted"
    assert body["accepted_at"] is not None
    assert body["started_at"] is None
    assert len(body["route"]) == len(_ROUTE)
    assert body["route_truncated"] is False
    # الموضعُ من مفتاح الحضور لا من عمود — ومعه عمرُه
    assert body["position"] is not None
    assert isinstance(body["position"]["lat"], float)
    assert body["position"]["stale"] is False
    assert body["position"]["seconds_since_update"] is not None
    # **ولا اسمَ راكبٍ ولا رقمَ ولا مال**: بابُ مواقعَ لا بابُ سجلِّ رحلات
    assert "rider" not in body and "final_fare" not in body


async def test_support_is_refused_and_so_is_the_stranger(
    client: AsyncClient, jordan_settings: None, session_factory, support_headers: dict
) -> None:
    """**من فُتح له هذا فُتحت له الخريطةُ كلُّها** — كبتناً كبتناً."""
    driver = await approved_driver(client, session_factory, DRIVER)

    refused = await client.get(
        f"/admin/live/drivers/{driver['driver_id']}/ride", headers=support_headers
    )
    assert refused.status_code == 403, refused.text

    anonymous = await client.get(f"/admin/live/drivers/{driver['driver_id']}/ride")
    assert anonymous.status_code == 401


async def test_silence_keeps_the_ride_and_drops_the_dot(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """ذهب مفتاحُ الحضور: **الرحلةُ باقيةٌ والموضعُ `null`** — لا موضعٌ عند الصفر.

    **وهذه هي الحالُ التي لا تجيبها الخريطةُ الحيّة**: كبتنٌ مات هاتفُه في
    رحلة يختفي منها كلَّها، فيُقرأ «ليس في رحلة» — وهو فيها.
    """
    from app.core.redis_client import get_redis_client
    from app.services import geo

    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider["headers"], driver)

    await get_redis_client().delete(geo.presence_key(driver["driver_id"]))
    body = await _live(client, admin_headers, driver["driver_id"])

    assert body is not None and body["ride_id"] == ride["id"]
    assert body["position"] is None
    # **ولا قيدَ**: لم يخرج موضعٌ، فلا اقترانَ بين هوّيةٍ وموقع
    assert await _driver_live_entries(session_factory) == 0


async def test_one_audit_entry_per_watching_session_and_it_names_the_driver(
    client: AsyncClient, jordan_settings: None, session_factory, admin_headers: dict
) -> None:
    """قيدٌ واحدٌ للجلسة، **باسم الكبتن لا باسم «الخريطة الحيّة»**.

    قيدٌ يقول «قرأ خريطةَ الأردن» عمّن فتح ملفَّ كبتنٍ واحدٍ يصف فعلاً لم يقع،
    **وسجلُّ التدقيق يُقرأ بعد شهرٍ ليقال ماذا جرى**.
    """
    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    await accepted_ride(client, rider["headers"], driver)

    for _ in range(3):
        await _live(client, admin_headers, driver["driver_id"])

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(AdminAuditLog.action == AuditAction.READ)
            )
        ).all()

    assert len(rows) == 1, "الخنق معطّل: كل استطلاعٍ يكتب قيداً"
    assert rows[0].entity_type == "driver_live"
    assert rows[0].entity_id == driver["driver_id"]


async def test_an_unknown_driver_is_not_found(
    client: AsyncClient, jordan_settings: None, admin_headers: dict
) -> None:
    """معرّفٌ لا يقابل كبتناً **خطأٌ مسمّى، لا «لا رحلة»** — والفرقُ يُقرأ."""
    import uuid

    response = await client.get(
        f"/admin/live/drivers/{uuid.uuid4()}/ride", headers=admin_headers
    )
    assert response.status_code == 404, response.text
