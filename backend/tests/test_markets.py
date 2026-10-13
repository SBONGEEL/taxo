"""الدولُ والحدود (SPEC §٧٤-أ/٢–٤، أمرُ المالك ٢٠٢٦-١٠-١٣).

**ما يُقاس، وكلٌّ يسقط بحذف ما يحرسه:**

١) **المغلقةُ تُنشر للدخول بحالها** — ولا يُقفل أحدٌ خارج حسابه؛ **والتسجيلُ فيها يُردّ** قبل الرمز.
٢) **لا يُطلب في المغلقة جديد** — تقديرٌ ولا طلب؛ **وحسابُ التجربة يمرّ، واستعمالُه سطرٌ في التدقيق**.
٣) **الفتحُ يمرّ بفحص الجاهزيّة**: يُردّ بما نقص، **والفتحُ رغم النقص بسببٍ مكتوبٍ مدقَّق** — والإغلاقُ بلا شرط.
٤) **الصلاحيةُ للمالك**: لا يملكها المشرفُ الكامل افتراضاً، **وبابُ المفاتيح العامّ لا يكتب حالَ السوق**.
٥) **الحدود**: مفروضةً تردّ ما خرج، **ومرفوعةً تقبله بسوق الحساب**، وقائمةُ السماح تقبله والحدودُ مفروضة؛ **ورفعُها لا يفتح مغلقاً**.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode, FeatureKey, PolicyApp, PolicyDocType
from app.models.feature_flag import FeatureFlag
from app.models.privacy import PrivacyPolicy
from app.models.user import User
from app.services import settings_service
from tests.conftest import _signup, _staff_headers
from tests.helpers import DROPOFF, PICKUP, RIDER, rider_session

pytestmark = pytest.mark.asyncio

TRIPOLI_POINT = {"lat": 32.8935, "lng": 13.3669, "address": "طرابلس"}


async def _set_open(session_factory, country: CountryCode, open_: bool) -> None:
    async with session_factory() as session:
        await settings_service.set_flag(
            session, country_code=country, feature_key=FeatureKey.COUNTRY_VISIBLE, enabled=open_
        )
        await session.commit()


async def _mark_test(session_factory, user_id: str) -> None:
    async with session_factory() as session:
        await session.execute(update(User).where(User.id == user_id).values(is_test=True))
        await session.commit()


async def markets_owner(client: AsyncClient, admin_headers: dict, phone: str = "+962790000081") -> dict:
    """**مشرفٌ مُنح «الدول والحدود» بالاسم** — كما تمنحها المصفوفة: مجموعتُه الفعّالةُ ومعها الجديدة."""
    headers = await _staff_headers("admin", phone, "مالك الدول")
    me = (await client.get("/auth/me", headers=headers)).json()
    rows = (await client.get("/admin/permissions", headers=admin_headers)).json()
    row = next(item for item in rows if item["user_id"] == me["id"])
    assert "markets.manage" not in row["permissions"], "الصلاحيةُ وصلت بالافتراض — وهي «للمالك» لا لكلِّ مشرف"
    granted = await client.put(
        f"/admin/permissions/{me['id']}",
        json={"permissions": sorted(set(row["permissions"]) | {"markets.manage"})},
        headers=admin_headers,
    )
    assert granted.status_code == 200, granted.text
    return {"headers": headers, "id": me["id"]}


def _by_code(body: dict) -> dict[str, dict]:
    return {entry["country_code"]: entry for entry in body["countries"]}


# ─────────────────────────────────────────── ١) المغلقةُ في الدخول، والتسجيلُ فيها يُردّ


async def test_a_closed_country_is_published_for_login_with_its_state(client: AsyncClient, session_factory) -> None:
    await _set_open(session_factory, CountryCode.LY, False)
    body = (await client.get("/config")).json()
    entries = _by_code(body)
    assert set(entries) == {c.value for c in CountryCode}, "كلُّ دولةٍ في الدخول — فالحساباتُ القائمةُ تدخل دائماً"
    assert entries["LY"]["status"] == "closed" and entries["JO"]["status"] == "open"
    # **وافتراضُ المغلقة «قريباً»** بنصّ المالك
    assert entries["LY"]["signup"] == "soon" and entries["JO"]["signup"] == "open"
    assert entries["LY"]["name"] == "ليبيا" and entries["LY"]["dial_code"] == "218"
    # **والمفتوحةُ أوّلاً**، والافتراضيّةُ منها
    codes = [entry["country_code"] for entry in body["countries"]]
    assert codes.index("JO") < codes.index("LY")
    assert body["default_country_code"] == "JO"


async def test_the_country_name_follows_the_request_language(client: AsyncClient) -> None:
    body = (await client.get("/config", headers={"Accept-Language": "fr"})).json()
    assert _by_code(body)["DZ"]["name"] == "Algérie"


async def test_hidden_display_hides_a_closed_country_from_signup_only(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _set_open(session_factory, CountryCode.DZ, False)
    owner = await markets_owner(client, admin_headers)
    answer = await client.put("/admin/markets/DZ/signup-display", json={"display": "hidden"}, headers=owner["headers"])
    assert answer.status_code == 200, answer.text
    entry = _by_code((await client.get("/config")).json())["DZ"]
    assert entry["signup"] == "hidden" and entry["status"] == "closed"


async def test_signing_up_in_a_closed_country_is_refused_before_anything_is_written(
    client: AsyncClient, session_factory
) -> None:
    await _set_open(session_factory, CountryCode.LY, False)
    answer = await client.post("/auth/register", json=_signup("0917654321", "كبتن", "LY", "driver"))
    assert answer.status_code == 403, answer.text
    assert answer.json()["code"] == "signup_closed"
    assert "ليبيا" in answer.json()["message"]
    async with session_factory() as session:
        assert (await session.scalar(select(User).where(User.phone == "+218917654321"))) is None


async def test_an_account_in_a_closed_country_still_logs_in(client: AsyncClient, session_factory) -> None:
    """**لا يُقفل أحدٌ خارج حسابه** — الإغلاقُ يمنع الجديدَ لا الدخول."""
    rider = await rider_session(client)
    await _set_open(session_factory, CountryCode.JO, False)
    answer = await client.post(
        "/auth/login", json={"phone": RIDER["phone"], "password": RIDER["password"], "country_code": "JO"}
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["user"]["id"] == rider["user"]["id"]


# ─────────────────────────────────────────── ٢) لا جديدَ في المغلقة — إلا للتجربة


async def test_nothing_new_is_requested_in_a_closed_market(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    rider = await rider_session(client)
    await _set_open(session_factory, CountryCode.JO, False)
    ride = {"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"}
    for path in ("/rides/estimate", "/rides"):
        answer = await client.post(path, json=ride, headers=rider["headers"])
        assert answer.status_code == 403, (path, answer.text)
        assert answer.json()["code"] == "market_closed", answer.text


async def test_a_test_account_requests_in_a_closed_market_and_the_use_is_audited(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    rider = await rider_session(client)
    await _mark_test(session_factory, rider["user"]["id"])
    await _set_open(session_factory, CountryCode.JO, False)
    ride = {"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"}
    assert (await client.post("/rides/estimate", json=ride, headers=rider["headers"])).status_code == 200
    made = await client.post("/rides", json=ride, headers=rider["headers"])
    assert made.status_code == 201, made.text
    async with session_factory() as session:
        uses = (
            await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "test_market_use"))
        ).all()
    # **سطرٌ للطلب وحدَه** — التقديرُ قراءةٌ خالصة لا تُكتب
    assert [(row.details["country_code"], row.details["door"]) for row in uses] == [("JO", "ride")]
    assert str(uses[0].actor_id) == rider["user"]["id"]


async def test_an_open_market_passes_untouched(client: AsyncClient, jordan_settings: None) -> None:
    rider = await rider_session(client)
    made = await client.post(
        "/rides", json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"}, headers=rider["headers"]
    )
    assert made.status_code == 201, made.text


# ─────────────────────────────────────────── ٣) الفتحُ بفحص الجاهزيّة


async def _publish_policies(session_factory, country: CountryCode) -> None:
    async with session_factory() as session:
        for app in PolicyApp:
            for doc in PolicyDocType:
                session.add(
                    PrivacyPolicy(
                        country_code=country,
                        doc_type=doc,
                        app=app,
                        version=1,
                        min_accepted_version=1,
                        body_ar="نصٌّ منشور",
                        is_published=True,
                        published_at=datetime.now(UTC),
                    )
                )
        await session.commit()


async def test_opening_an_unready_market_is_refused_with_what_is_missing(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _set_open(session_factory, CountryCode.DZ, False)
    owner = await markets_owner(client, admin_headers)
    answer = await client.put("/admin/markets/DZ/status", json={"open": True}, headers=owner["headers"])
    assert answer.status_code == 409, answer.text
    body = answer.json()
    assert body["code"] == "market_not_ready"
    missing = " · ".join(body["missing"])
    for part in ("تسعيرةُ", "طريقةَ دفعٍ", "غيرُ منشورة", "التقريب"):
        assert part in missing, (part, body["missing"])
    assert _by_code((await client.get("/config")).json())["DZ"]["status"] == "closed"


async def test_opening_anyway_needs_a_written_reason_and_is_audited(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _set_open(session_factory, CountryCode.DZ, False)
    owner = await markets_owner(client, admin_headers)
    bare = await client.put("/admin/markets/DZ/status", json={"open": True, "force": True}, headers=owner["headers"])
    assert bare.status_code == 422, bare.text
    forced = await client.put(
        "/admin/markets/DZ/status",
        json={"open": True, "force": True, "reason": "تجربةُ إطلاقٍ مقصودة"},
        headers=owner["headers"],
    )
    assert forced.status_code == 200, forced.text
    assert next(row for row in forced.json()["countries"] if row["country_code"] == "DZ")["status"] == "open"
    async with session_factory() as session:
        row = await session.scalar(
            select(AdminAuditLog).where(AdminAuditLog.entity_type == "market").order_by(AdminAuditLog.created_at.desc())
        )
    assert row.details["forced"] is True and row.details["reason"] == "تجربةُ إطلاقٍ مقصودة"
    assert row.details["missing"] and str(row.actor_id) == owner["id"]


async def test_a_ready_market_opens_without_force(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings: None, jordan_wallet: None
) -> None:
    owner = await markets_owner(client, admin_headers)
    await _set_open(session_factory, CountryCode.JO, False)
    async with session_factory() as session:
        session.add(FeatureFlag(country_code=CountryCode.JO, feature_key=FeatureKey.CLIQ_ENABLED.value, enabled=True))
        await session.commit()
    await _publish_policies(session_factory, CountryCode.JO)
    listed = (await client.get("/admin/markets", headers=owner["headers"])).json()
    assert next(row for row in listed["countries"] if row["country_code"] == "JO")["readiness"] == []
    answer = await client.put("/admin/markets/JO/status", json={"open": True}, headers=owner["headers"])
    assert answer.status_code == 200, answer.text
    assert _by_code((await client.get("/config")).json())["JO"]["status"] == "open"


async def test_closing_needs_no_reason_and_touches_nothing_but_the_switch(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    owner = await markets_owner(client, admin_headers)
    answer = await client.put("/admin/markets/JO/status", json={"open": False}, headers=owner["headers"])
    assert answer.status_code == 200, answer.text
    assert _by_code((await client.get("/config")).json())["JO"]["status"] == "closed"


# ─────────────────────────────────────────── ٤) الصلاحية، والبابُ الوحيد


async def test_a_full_admin_does_not_hold_the_markets_switch_by_default(client: AsyncClient, admin_headers: dict) -> None:
    for method, path, body in (
        ("put", "/admin/markets/LY/status", {"open": True, "force": True, "reason": "محاولةٌ بلا صلاحية"}),
        ("put", "/admin/markets/LY/signup-display", {"display": "hidden"}),
        ("put", "/admin/markets/borders", {"enforced": False, "reason": "محاولةٌ بلا صلاحية"}),
    ):
        answer = await getattr(client, method)(path, json=body, headers=admin_headers)
        assert answer.status_code == 403, (path, answer.text)


async def test_support_reads_the_markets_page(client: AsyncClient, support_headers: dict) -> None:
    answer = await client.get("/admin/markets", headers=support_headers)
    assert answer.status_code == 200, answer.text
    assert {row["country_code"] for row in answer.json()["countries"]} == {c.value for c in CountryCode}
    assert answer.json()["borders_enforced"] is True


async def test_the_general_flag_door_no_longer_writes_the_market_state(client: AsyncClient, admin_headers: dict) -> None:
    answer = await client.put(
        "/admin/settings/feature-flags",
        json={"country_code": "LY", "feature_key": FeatureKey.COUNTRY_VISIBLE.value, "enabled": True},
        headers=admin_headers,
    )
    assert answer.status_code == 422, answer.text
    assert "«الدول»" in answer.json()["message"]


# ─────────────────────────────────────────── ٥) الحدود


async def _estimate_to_tripoli(client: AsyncClient, rider: dict):
    return await client.post(
        "/rides/estimate",
        json={"pickup": PICKUP, "dropoff": TRIPOLI_POINT, "vehicle_category": "economy"},
        headers=rider["headers"],
    )


async def test_lifting_the_borders_lets_the_account_work_from_anywhere_in_its_own_market(
    client: AsyncClient, admin_headers: dict, jordan_settings: None
) -> None:
    owner = await markets_owner(client, admin_headers)
    rider = await rider_session(client)
    assert (await _estimate_to_tripoli(client, rider)).json()["code"] == "outside_service_area"

    bare = await client.put("/admin/markets/borders", json={"enforced": False}, headers=owner["headers"])
    assert bare.status_code == 422, "رفعُ الحدود بلا سببٍ مكتوب"
    lifted = await client.put(
        "/admin/markets/borders", json={"enforced": False, "reason": "تجربةٌ من خارج البلد"}, headers=owner["headers"]
    )
    assert lifted.status_code == 200 and lifted.json()["borders_enforced"] is False
    quote = await _estimate_to_tripoli(client, rider)
    assert quote.status_code == 200, quote.text
    # **بسوق الحساب نفسِه** — العملةُ عملةُ الأردن ولو كان الطرفُ في طرابلس
    assert quote.json()["currency"] == "JOD"

    back = await client.put("/admin/markets/borders", json={"enforced": True}, headers=owner["headers"])
    assert back.status_code == 200 and back.json()["borders_enforced"] is True
    assert (await _estimate_to_tripoli(client, rider)).json()["code"] == "outside_service_area"


async def test_the_allow_list_lets_one_account_out_while_the_borders_hold(
    client: AsyncClient, admin_headers: dict, jordan_settings: None
) -> None:
    owner = await markets_owner(client, admin_headers)
    rider = await rider_session(client)
    granted = await client.post(
        "/admin/markets/borders/allowances",
        json={"phone": RIDER["phone"], "country_code": "JO", "reason": "حسابُ تجربة"},
        headers=owner["headers"],
    )
    assert granted.status_code == 200, granted.text
    allowance = granted.json()["allowances"][0]
    assert allowance["user_id"] == rider["user"]["id"]
    assert (await _estimate_to_tripoli(client, rider)).status_code == 200

    again = await client.post(
        "/admin/markets/borders/allowances",
        json={"user_id": rider["user"]["id"], "reason": "مرّةً ثانية"},
        headers=owner["headers"],
    )
    assert again.status_code == 409, again.text

    revoked = await client.post(f"/admin/markets/borders/allowances/{allowance['id']}/revoke", headers=owner["headers"])
    assert revoked.status_code == 200 and revoked.json()["allowances"] == []
    assert (await _estimate_to_tripoli(client, rider)).json()["code"] == "outside_service_area"


async def test_lifting_the_borders_never_opens_a_closed_market(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings: None
) -> None:
    owner = await markets_owner(client, admin_headers)
    rider = await rider_session(client)
    await client.put(
        "/admin/markets/borders", json={"enforced": False, "reason": "تجربةٌ من خارج البلد"}, headers=owner["headers"]
    )
    await _set_open(session_factory, CountryCode.JO, False)
    answer = await _estimate_to_tripoli(client, rider)
    assert answer.status_code == 403 and answer.json()["code"] == "market_closed", answer.text


# ─────────────────────────────────────────── ٦) ما يُخمَّن به افتراضُ المُختار


async def test_the_network_country_and_each_market_box_are_published(client: AsyncClient) -> None:
    """**أوّلُ تخمينٍ دولةُ الشبكة** (رأسُ Cloudflare)، **والموقعُ بصندوق نطاق الخدمة نفسِه** — ولا صندوقَ يُكتب في التطبيق."""
    from app.core import service_area

    body = (await client.get("/config", headers={"CF-IPCountry": "ly"})).json()
    assert body["network_country"] == "LY"
    box = service_area.MARKET_BOX[CountryCode.JO]
    assert _by_code(body)["JO"]["area"] == [box.min_lat, box.max_lat, box.min_lng, box.max_lng]
    # **وسوقٌ ليس عندنا لا يُخمَّن به**
    assert (await client.get("/config", headers={"CF-IPCountry": "FR"})).json()["network_country"] is None
    assert (await client.get("/config")).json()["network_country"] is None
