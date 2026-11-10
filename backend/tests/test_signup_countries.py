"""مُنتقي الدول — الحالاتُ الأربعُ والعدُّ بلا أرقام (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٥).

**ما يُقاس، وكلٌّ يسقط بحذف ما يحرسه:**

١) **غيرُ الأسواق تُنشر بحالها** في `/config` — «متوقفة» افتراضاً، والمخفيّةُ لا تُنشر، والاسمُ بلغة الطلب.
٢) **«متوقفة» لسوقٍ مغلقٍ تُردّ بنصّها** قبل الرمز، **و«قريباً» بـ«قريباً في [الدولة]»**.
٣) **المحاولةُ تُعدّ بلا رقم** — عددٌ يوميٌّ لكلِّ دولة، والنشطةُ لا تُعدّ، والنصُّ بالفرنسيّة لمن طلبها.
٤) **الحالُ من اللوحة بصلاحيّة «الدول والحدود»** — مدقَّقة، والسوقُ لا يُضبط من هذا الباب.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode
from app.models.signup_country import SignupAttemptDaily
from app.models.user import User
from tests.conftest import _signup
from tests.test_markets import _set_open, markets_owner

pytestmark = pytest.mark.asyncio


def _others(body: dict) -> dict[str, dict]:
    return {entry["code"]: entry for entry in body["signup_countries"]}


async def test_other_countries_are_published_stopped_by_default_and_named_in_the_request_language(
    client: AsyncClient,
) -> None:
    body = (await client.get("/config")).json()
    others = _others(body)
    assert others["EG"] == {"code": "EG", "name": "مصر", "dial_code": "20", "state": "stopped"}
    assert not {"JO", "LY", "DZ"} & set(others), "الأسواقُ في `countries` بحالها — لا تتكرّر هنا"
    fr = _others((await client.get("/config", headers={"Accept-Language": "fr"})).json())
    assert fr["EG"]["name"] == "Égypte"


async def test_the_panel_sets_soon_or_hidden_and_the_change_is_audited(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    owner = await markets_owner(client, admin_headers)
    soon = await client.put("/admin/markets/signup-countries/MA", json={"display": "soon"}, headers=owner["headers"])
    assert soon.status_code == 200, soon.text
    hidden = await client.put("/admin/markets/signup-countries/TR", json={"display": "hidden"}, headers=owner["headers"])
    assert hidden.status_code == 200, hidden.text
    others = _others((await client.get("/config")).json())
    assert others["MA"]["state"] == "soon" and "TR" not in others
    codes = list(others)
    assert codes.index("MA") < codes.index("EG"), "«قريباً» قبل «متوقفة»"
    async with session_factory() as session:
        rows = (
            await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "signup_country_display"))
        ).all()
    assert {row.details["country_code"] for row in rows} == {"MA", "TR"}


async def test_a_market_is_not_set_from_the_other_countries_door(client: AsyncClient, admin_headers: dict) -> None:
    owner = await markets_owner(client, admin_headers)
    answer = await client.put("/admin/markets/signup-countries/LY", json={"display": "stopped"}, headers=owner["headers"])
    assert answer.status_code == 422, answer.text


async def test_a_full_admin_without_the_markets_grant_cannot_set_a_country(client: AsyncClient, admin_headers: dict) -> None:
    answer = await client.put("/admin/markets/signup-countries/MA", json={"display": "soon"}, headers=admin_headers)
    assert answer.status_code == 403, answer.text


async def test_a_stopped_market_refuses_signup_with_the_owner_text_before_anything_is_written(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _set_open(session_factory, CountryCode.LY, False)
    owner = await markets_owner(client, admin_headers)
    await client.put("/admin/markets/LY/signup-display", json={"display": "stopped"}, headers=owner["headers"])
    assert {e["country_code"]: e for e in (await client.get("/config")).json()["countries"]}["LY"]["signup"] == "stopped"
    answer = await client.post("/auth/register", json=_signup("0917654321", "كبتن", "LY", "driver"))
    assert answer.status_code == 403, answer.text
    assert answer.json()["code"] == "country_stopped"
    assert answer.json()["message"] == "خادم الدولة متوقف حالياً"
    async with session_factory() as session:
        assert (await session.scalar(select(User).where(User.phone == "+218917654321"))) is None


async def test_a_soon_market_says_soon_in_the_country(client: AsyncClient, session_factory) -> None:
    await _set_open(session_factory, CountryCode.LY, False)
    answer = await client.post("/auth/register", json=_signup("0917654321", "كبتن", "LY", "driver"))
    assert answer.status_code == 403 and answer.json()["message"] == "قريباً في ليبيا"


async def test_an_attempt_is_counted_per_country_without_a_number(client: AsyncClient, session_factory) -> None:
    first = await client.post("/auth/signup-attempts", json={"country": "EG"})
    assert first.status_code == 200, first.text
    assert first.json() == {"state": "stopped", "message": "خادم الدولة متوقف حالياً"}
    await client.post("/auth/signup-attempts", json={"country": "eg"})
    fr = await client.post("/auth/signup-attempts", json={"country": "LY"}, headers={"Accept-Language": "fr"})
    assert fr.json()["state"] in {"soon", "open"}
    async with session_factory() as session:
        rows = {row.country: row.attempts for row in (await session.scalars(select(SignupAttemptDaily))).all()}
    assert rows["EG"] == 2
    # **والجدولُ لا يحمل إلا اليومَ والدولةَ والعدد** — لا هاتفَ ولا جهازَ ولا عنوان
    assert set(SignupAttemptDaily.__table__.columns.keys()) == {"day", "country", "attempts"}


async def test_an_open_market_is_not_counted(client: AsyncClient, jordan_settings: None, session_factory) -> None:
    answer = await client.post("/auth/signup-attempts", json={"country": "JO"})
    assert answer.json() == {"state": "open", "message": None}
    async with session_factory() as session:
        assert (await session.scalar(select(SignupAttemptDaily).where(SignupAttemptDaily.country == "JO"))) is None


async def test_the_soon_text_is_french_for_a_french_request(client: AsyncClient, admin_headers: dict) -> None:
    owner = await markets_owner(client, admin_headers)
    await client.put("/admin/markets/signup-countries/MA", json={"display": "soon"}, headers=owner["headers"])
    answer = await client.post("/auth/signup-attempts", json={"country": "MA"}, headers={"Accept-Language": "fr"})
    assert answer.json() == {"state": "soon", "message": "Bientôt en Maroc"}


async def test_an_unknown_country_is_refused(client: AsyncClient) -> None:
    answer = await client.post("/auth/signup-attempts", json={"country": "ZZ"})
    assert answer.status_code == 404


async def test_the_panel_list_carries_every_country_with_its_attempts(client: AsyncClient, support_headers: dict) -> None:
    await client.post("/auth/signup-attempts", json={"country": "SA"})
    rows = (await client.get("/admin/markets/signup-countries", headers=support_headers)).json()
    by = {row["code"]: row for row in rows}
    assert by["SA"]["attempts_30d"] == 1 and by["SA"]["state"] == "stopped" and not by["SA"]["market"]
    assert by["JO"]["market"] and len(rows) >= 39
