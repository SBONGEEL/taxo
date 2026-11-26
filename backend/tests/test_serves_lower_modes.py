"""«الأعلى يأخذ الأدنى» بنمطين من اللوحة لكلِّ دولة (SPEC §١٢٠، قرارُ المالك ٢٠٢٦-١١-٢٦).

- **ب «إلزامي للجميع»**: كابتنُ «مريح» يأخذ طلبَ «اقتصادي» بلا مفتاح — **ولا يأخذ الأدنى طلبَ الأعلى أبداً**.
- **أ «باختيار الكابتن»**: يأخذه ما لم يُطفئ مفتاحَه، **والافتراضُ من الدولة**؛ والمفتاحُ لا يُكتب في غير النمط أ.
- **الترتيب**: «الفئة المطلوبة أوّلاً» يضيف الهامشَ إلى مسافة الأعلى وحدَه، و«الأقرب» لا يضيف شيئاً.
- **والتبديلُ من اللوحة يسري فوراً ويُكتب في سجلّ التدقيق.**
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog as AuditLog
from app.models.enums import CountryCode
from app.models.ride_category import RideCategory
from app.services import categories, dispatch
from tests.helpers import DRIVER, SECOND_DRIVER, approved_driver, bring_online

pytestmark = pytest.mark.usefixtures("jordan_settings")


async def _comfort_row(session_factory) -> None:
    async with session_factory() as session:
        session.add(
            RideCategory(country_code=CountryCode.JO, key="comfort", name="مريح", icon="directions_car", seats=4,
                         sort_order=1, is_active=True, is_builtin=True)
        )
        await session.commit()


async def _eligible(session_factory, driver_id, key: str) -> bool:
    async with session_factory() as session:
        levels = await dispatch._eligible_levels(session, [uuid.UUID(str(driver_id))], key, country=CountryCode.JO)
        return uuid.UUID(str(driver_id)) in levels


async def _set_mode(client: AsyncClient, admin_headers: dict, **fields) -> dict:
    response = await client.patch("/admin/settings/dispatch/JO", json=fields, headers=admin_headers)
    assert response.status_code == 200, response.text
    return response.json()


async def test_mandatory_mode_gives_lower_requests_to_every_higher_captain_and_is_audited(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    comfort = await approved_driver(client, session_factory, DRIVER, category="comfort")
    await bring_online(client, comfort)
    await _comfort_row(session_factory)
    assert not await _eligible(session_factory, comfort["driver_id"], "economy")

    body = await _set_mode(client, admin_headers, serves_lower_mode="mandatory")
    assert body["serves_lower_mode"] == "mandatory"
    # **فوراً** — الطلبُ التالي يقرأ النمط، بلا إعادة تشغيلٍ ولا إصدار
    assert await _eligible(session_factory, comfort["driver_id"], "economy")
    async with session_factory() as session:
        assert await categories.takers(session, CountryCode.JO, "comfort") == ["comfort"]
        logged = (
            await session.scalars(select(AuditLog).where(AuditLog.entity_type == "dispatch_settings"))
        ).all()
    assert any((row.details or {}).get("serves_lower_mode") == "mandatory" for row in logged)

    # **والمفتاحُ مخفيٌّ في ب** — والكتابةُ عليه مرفوضة
    mine = (await client.get("/drivers/me/serves-lower", headers=comfort["headers"])).json()
    assert mine["mode"] == "mandatory"
    refused = await client.put(
        "/drivers/me/serves-lower", json={"key": "economy", "enabled": False}, headers=comfort["headers"]
    )
    assert refused.status_code == 422, refused.text
    assert await _eligible(session_factory, comfort["driver_id"], "economy")


async def test_choice_mode_follows_the_captain_switch_and_the_country_default(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    comfort = await approved_driver(client, session_factory, DRIVER, category="comfort")
    await bring_online(client, comfort)
    await _comfort_row(session_factory)
    await _set_mode(client, admin_headers, serves_lower_mode="choice")

    mine = (await client.get("/drivers/me/serves-lower", headers=comfort["headers"])).json()
    assert mine == {"mode": "choice", "choices": [{"key": "economy", "name": "اقتصادي", "enabled": True}]}
    assert await _eligible(session_factory, comfort["driver_id"], "economy")

    off = await client.put("/drivers/me/serves-lower", json={"key": "economy", "enabled": False}, headers=comfort["headers"])
    assert off.status_code == 200, off.text
    assert off.json()["choices"][0]["enabled"] is False
    assert not await _eligible(session_factory, comfort["driver_id"], "economy")

    on = await client.put("/drivers/me/serves-lower", json={"key": "economy", "enabled": True}, headers=comfort["headers"])
    assert on.json()["choices"][0]["enabled"] is True
    assert await _eligible(session_factory, comfort["driver_id"], "economy")

    # **فئتُه نفسُها لا تُعرض مفتاحاً** — ولا فئةٌ لا تصلح لها مركبتُه
    stranger = await client.put("/drivers/me/serves-lower", json={"key": "comfort", "enabled": False}, headers=comfort["headers"])
    assert stranger.status_code == 422

    # **افتراضُ الدولة يحكم من لم يختر** — وصريحُ الاختيار يبقى
    await _set_mode(client, admin_headers, serves_lower_choice_default=False)
    assert await _eligible(session_factory, comfort["driver_id"], "economy")
    second = await approved_driver(client, session_factory, SECOND_DRIVER, category="comfort")
    assert not await _eligible(session_factory, second["driver_id"], "economy")

    # **والعودةُ إلى ب تشمل الجميع ولو أطفأ مفتاحَه**
    await client.put("/drivers/me/serves-lower", json={"key": "economy", "enabled": False}, headers=comfort["headers"])
    await _set_mode(client, admin_headers, serves_lower_mode="mandatory")
    assert await _eligible(session_factory, comfort["driver_id"], "economy")
    assert await _eligible(session_factory, second["driver_id"], "economy")


async def test_same_category_first_adds_the_margin_to_higher_captains_only(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    economy = await approved_driver(client, session_factory, DRIVER)
    comfort = await approved_driver(client, session_factory, SECOND_DRIVER, category="comfort")
    await _comfort_row(session_factory)
    ids = [uuid.UUID(str(economy["driver_id"])), uuid.UUID(str(comfort["driver_id"]))]

    async def penalties() -> dict:
        async with session_factory() as session:
            return await categories.higher_penalties(session, CountryCode.JO, "economy", ids)

    assert await penalties() == {}  # مطفأ
    await _set_mode(client, admin_headers, serves_lower_mode="mandatory", serves_lower_margin_meters=700)
    assert await penalties() == {ids[1]: 700}
    await _set_mode(client, admin_headers, serves_lower_order="nearest")
    assert await penalties() == {}
