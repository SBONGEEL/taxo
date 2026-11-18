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


@pytest.fixture(autouse=True)
async def _rows_as_production(session_factory) -> None:
    """**حالُ الإنتاج بعد `0173`**: كلُّ دولةٍ غيرِ سوقٍ صفُّها «متوقفة» صريحاً — والتفريغُ بين الاختبارات يمحو ما كتبته الترحيلة.
    **وغيابُ الصفِّ صار «مخفية»** (الدولةُ الجديدة)، ويقيسه `test_a_country_without_a_row_is_hidden_until_the_owner_chooses`."""
    from app.core.countries import CATALOGUE
    from app.models.enums import SignupDisplay
    from app.models.signup_country import SignupCountry

    markets = {code.value for code in CountryCode}
    async with session_factory() as session:
        for country in CATALOGUE:
            if country.code not in markets and country.code != "KM":
                session.add(SignupCountry(code=country.code, display=SignupDisplay.STOPPED))
        await session.commit()


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


# ── أمرُ المالك ٢٠٢٦-١١-١٨ الثاني: «ظاهرة» ونصُّها و«أعلمني»، والدولةُ الجديدةُ مخفيّة ─────────────────────────────────


async def test_a_country_without_a_row_is_hidden_until_the_owner_chooses(client: AsyncClient) -> None:
    """**جزرُ القمر بلا صفّ** (التجهيزُ يتركها) — كدولةٍ أُضيفت إلى القائمة اليوم: **لا تُنشر**، والباقيةُ «متوقفة» كما كانت."""
    others = _others((await client.get("/config")).json())
    assert "KM" not in others
    assert others["EG"]["state"] == "stopped"


async def test_a_visible_country_is_published_first_and_answers_with_the_owner_text(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    owner = await markets_owner(client, admin_headers)
    put = await client.put(
        "/admin/markets/signup-countries/SA", json={"display": "visible"}, headers=owner["headers"]
    )
    assert put.status_code == 200, put.text
    others = _others((await client.get("/config")).json())
    assert others["SA"]["state"] == "visible" and list(others)[0] == "SA", "«ظاهرة» أوّلاً كالعاملة"
    answer = await client.post("/auth/signup-attempts", json={"country": "SA"})
    assert answer.json() == {"state": "visible", "message": "TAXO سيبدأ قريباً في السعودية. سنُعلمك فور الإطلاق."}

    custom = await client.put(
        "/admin/markets/signup-countries/SA",
        json={"display": "visible", "message": "نصلكم قريباً في الرياض"},
        headers=owner["headers"],
    )
    row = next(item for item in custom.json() if item["code"] == "SA")
    assert row["visible_message"] == "نصلكم قريباً في الرياض"
    assert (await client.post("/auth/signup-attempts", json={"country": "SA"})).json()["message"] == "نصلكم قريباً في الرياض"
    async with session_factory() as session:
        logs = (
            await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "signup_country_display"))
        ).all()
    assert any("visible_message" in log.details["changes"] for log in logs), "تغييرُ النصِّ مدقَّقٌ بمن غيّره"


async def test_launch_interest_is_kept_once_and_only_for_a_visible_country(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    from app.models.signup_country import LaunchInterest

    refused = await client.post("/auth/launch-interest", json={"country": "EG", "phone": "1001234567"})
    assert refused.status_code == 422, "«متوقفة» لا تأخذ رقماً"
    owner = await markets_owner(client, admin_headers)
    await client.put("/admin/markets/signup-countries/EG", json={"display": "visible"}, headers=owner["headers"])
    for _ in range(2):
        # **والأرقامُ العربيّةُ تُقرأ لاتينيّة** — والرقمُ نفسُه مرّتين صفٌّ واحد
        ok = await client.post("/auth/launch-interest", json={"country": "EG", "phone": "٠١٠٠١٢٣٤٥٦٧"})
        assert ok.status_code == 204, ok.text
    async with session_factory() as session:
        rows = (await session.scalars(select(LaunchInterest))).all()
    assert [(row.country, row.phone) for row in rows] == [("EG", "+201001234567")]
    listed = (await client.get("/admin/markets/signup-countries", headers=owner["headers"])).json()
    assert next(item for item in listed if item["code"] == "EG")["interests"] == 1


async def test_a_visible_closed_market_never_creates_an_account(client: AsyncClient, admin_headers: dict, session_factory) -> None:
    """**«ظاهرة» شكلٌ لا فتح** — سوقٌ مغلقٌ ظاهرٌ يردّ التسجيلَ قبل أيِّ صفٍّ كما تردّه «قريباً»."""
    await _set_open(session_factory, CountryCode.LY, False)
    owner = await markets_owner(client, admin_headers)
    put = await client.put("/admin/markets/LY/signup-display", json={"display": "visible"}, headers=owner["headers"])
    assert put.status_code == 200, put.text
    entry = {e["country_code"]: e for e in (await client.get("/config")).json()["countries"]}["LY"]
    assert entry["signup"] == "visible"
    answer = await client.post("/auth/register", json=_signup("0917654322", "كبتن", "LY", "driver"))
    assert answer.status_code == 403
    async with session_factory() as session:
        assert (await session.scalar(select(User).where(User.phone == "+218917654322"))) is None


async def test_a_launch_interest_is_deleted_after_twelve_months_and_a_fresh_one_stays(session_factory) -> None:
    """**«ويُحذف بعد ١٢ شهراً»** بنصِّ السياسة المنشورة (١٨/١١) — يسقط إن حُذف الكنسُ أو طالت العتبة."""
    from datetime import UTC, datetime, timedelta

    from app.models.signup_country import LaunchInterest
    from app.services import signup_countries
    from app.tasks.celery_app import celery_app

    now = datetime.now(UTC)
    async with session_factory() as session:
        session.add(LaunchInterest(country="EG", phone="+201000000001", created_at=now - timedelta(days=366)))
        session.add(LaunchInterest(country="EG", phone="+201000000002", created_at=now - timedelta(days=300)))
        await session.commit()
    async with session_factory() as session:
        assert await signup_countries.sweep_interests(session) == 1
    async with session_factory() as session:
        left = [row.phone for row in (await session.scalars(select(LaunchInterest))).all()]
    assert left == ["+201000000002"]
    assert "sweep-launch-interests" in celery_app.conf.beat_schedule
