"""**قفلُ `map_names.put`** (SPEC §١٠٩-ب) — ما يملكه القفلُ وحدَه: **سلسلةُ التدقيق**. مشرفان يكتبان اسمَ المكان نفسِه معاً ⇐
إنشاءٌ واحدٌ وتعديلٌ واحد، **واسمُ التعديل «السابق» هو ما كتبه الأوّل** — لا اثنان يدّعيان الإنشاء ولا «سابقٌ» لم يكن. وبلا القفل يقرأ
الثاني الصفَّ قبل أن يُلتزَم الأوّل، فيُختم «سابقٌ» قديم.
"""

from __future__ import annotations

import asyncio

from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.models.map_name_fix import MapNameFix


async def test_two_writes_of_one_place_leave_a_coherent_trail(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    names = ["مستشفى العبدلي", "مستشفى العبدلي التخصصي"]
    answers = await asyncio.wait_for(
        asyncio.gather(*[
            client.put("/admin/map-names/n77", json={"country_code": "JO", "name_ar": name}, headers=admin_headers)
            for name in names
        ]),
        timeout=30,
    )
    assert sorted(a.status_code for a in answers) == [200, 200], [a.text for a in answers]

    async with session_factory() as session:
        trail = (await session.scalars(
            select(AdminAuditLog).where(AdminAuditLog.entity_type == "map_name_fix").order_by(AdminAuditLog.created_at)
        )).all()
        final = await session.get(MapNameFix, "n77")
    assert sorted(row.action.value for row in trail) == ["create", "update"]
    created = next(row for row in trail if row.action.value == "create")
    updated = next(row for row in trail if row.action.value == "update")
    assert updated.details["name_ar"]["before"] == created.details["name_ar"]["after"]
    assert final is not None and final.name_ar == updated.details["name_ar"]["after"]


async def test_two_updates_read_each_other(client: AsyncClient, admin_headers: dict, session_factory) -> None:
    first = await client.put("/admin/map-names/w5", json={"country_code": "JO", "name_ar": "بنك"}, headers=admin_headers)
    assert first.status_code == 200
    names = ["بنك بلوم", "بنك بلوم فرع العبدلي"]
    answers = await asyncio.wait_for(
        asyncio.gather(*[
            client.put("/admin/map-names/w5", json={"country_code": "JO", "name_ar": name}, headers=admin_headers)
            for name in names
        ]),
        timeout=30,
    )
    assert all(a.status_code == 200 for a in answers)
    async with session_factory() as session:
        updates = (await session.scalars(
            select(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "map_name_fix", AdminAuditLog.action == "update")
            .order_by(AdminAuditLog.created_at)
        )).all()
    pairs = [(row.details["name_ar"]["before"], row.details["name_ar"]["after"]) for row in updates]
    # **سلسلةٌ لا شجرة**: أحدُهما يبدأ من «بنك» والآخرُ من حيث انتهى الأوّل — وبلا القفل يقرأ الاثنان «بنك».
    # (`created_at` بدءُ المعاملة لا التزامُها، فالترتيبُ يُتتبَّع بالسلسلة لا بالوقت)
    first = next((pair for pair in pairs if pair[0] == "بنك"), None)
    assert first is not None and len(pairs) == 2, pairs
    second = next(pair for pair in pairs if pair is not first)
    assert second[0] == first[1], pairs
