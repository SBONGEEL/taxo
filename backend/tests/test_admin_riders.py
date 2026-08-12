"""حظرُ الحسابات وقراءةُ الركّاب من اللوحة (SPEC القسم 13/3).

**الحظرُ وتجميدُ المحفظة بابان لا باب**، وهذا ما يختبره الملف قبل كل شيء:
الحظرُ يغلق الحساب كلَّه، والتجميدُ يوقف حركةَ المال ويبقي صاحبَه راكباً يدفع
نقداً (القسم 4/13.3). ولو كان باباً واحداً لصار كلُّ شكٍّ ماليٍّ إغلاقاً، أو
بقي مالٌ مشبوهٌ يتحرك لأن صاحبَه لم يستحق الإغلاق.

**والحظرُ يسري على الجلسة القائمة فوراً** لأن `core/deps` يقرأ العمود في كل
طلب — لا لأن أحداً أبطل توكناً. واختبارُ ذلك صراحةً هو ما يمنع «تحسيناً»
لاحقاً يكتفي بإبطال الجلسات ثم يترك توكناً حياً دقائقَ بعد الحظر.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import RIDER, auth, register, rider_session


async def _rider_id(client: AsyncClient, headers: dict) -> str:
    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return me.json()["id"]


async def test_block_closes_the_account_for_its_live_session(
    client: AsyncClient, jordan_settings: None, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    user_id = await _rider_id(client, rider["headers"])

    before = await client.get("/auth/me", headers=rider["headers"])
    assert before.status_code == 200

    blocked = await client.post(
        f"/admin/users/{user_id}/block",
        json={"reason": "بلاغات متكررة من كباتن"},
        headers=admin_headers,
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["is_blocked"] is True

    # نفس التوكن، بلا إعادة دخول: العمود يُقرأ في كل طلب
    after = await client.get("/auth/me", headers=rider["headers"])
    assert after.status_code == 403

    lifted = await client.post(
        f"/admin/users/{user_id}/unblock", json={}, headers=admin_headers
    )
    assert lifted.status_code == 200, lifted.text
    assert lifted.json()["is_blocked"] is False
    assert (await client.get("/auth/me", headers=rider["headers"])).status_code == 200


async def test_block_requires_a_written_reason(
    client: AsyncClient, jordan_settings: None, admin_headers: dict
) -> None:
    """سببٌ فارغ يُردّ: «لماذا حُظر؟» سؤالٌ يُسأل بعد شهر."""
    rider = await rider_session(client)
    user_id = await _rider_id(client, rider["headers"])

    response = await client.post(
        f"/admin/users/{user_id}/block", json={"reason": "   "}, headers=admin_headers
    )
    # `InvalidInput` يردّ 422 كما يردّ FastAPI لأخطاء التحقق
    assert response.status_code == 422, response.text
    assert (await client.get("/auth/me", headers=rider["headers"])).status_code == 200


async def test_block_writes_an_audit_entry_with_its_reason(
    client: AsyncClient, jordan_settings: None, admin_headers: dict
) -> None:
    rider = await rider_session(client)
    user_id = await _rider_id(client, rider["headers"])

    await client.post(
        f"/admin/users/{user_id}/block",
        json={"reason": "احتيالٌ مثبت على كبتنين"},
        headers=admin_headers,
    )

    logs = await client.get(
        "/admin/settings/audit-logs",
        headers=admin_headers,
        params={"entity_type": "user", "entity_id": user_id},
    )
    assert logs.status_code == 200, logs.text
    entries = logs.json()
    assert entries, entries
    assert entries[0]["details"]["blocked"] is True
    assert "احتيال" in entries[0]["details"]["reason"]
    # اسمُ الفاعل يأتي مضموماً — لا مُعرّفٌ وحده يبحث عنه المشرف في جدولٍ آخر
    assert entries[0]["actor_name"]


async def test_support_may_not_block(
    client: AsyncClient, jordan_settings: None, support_headers: dict
) -> None:
    """القسم 13/8 يعطي الدعمَ قراءةً ومعالجةَ نزاعات — لا إغلاقَ حسابات."""
    rider = await rider_session(client)
    user_id = await _rider_id(client, rider["headers"])

    response = await client.post(
        f"/admin/users/{user_id}/block",
        json={"reason": "محاولةٌ من الدعم"},
        headers=support_headers,
    )
    assert response.status_code == 403
    assert (await client.get("/auth/me", headers=rider["headers"])).status_code == 200


async def test_staff_accounts_are_not_blockable_from_this_door(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, support_headers: dict
) -> None:
    """بابُ القسم 13/3 عن الركّاب — لا يُغلق به مشرفٌ على زميله."""
    staff = await client.get(
        "/admin/users", headers=admin_headers, params={"role": "support"}
    )
    assert staff.status_code == 200, staff.text
    support_id = staff.json()[0]["id"]

    response = await client.post(
        f"/admin/users/{support_id}/block",
        json={"reason": "خلافٌ إداري"},
        headers=admin_headers,
    )
    assert response.status_code == 422, response.text


async def test_freezing_a_wallet_leaves_the_account_open(
    client: AsyncClient,
    jordan_settings: None,
    jordan_wallet: None,
    admin_headers: dict,
) -> None:
    """البابان مستقلان: محفظةٌ مجمّدة وحسابٌ يعمل — وهو الغرضُ من فصلهما."""
    rider = await rider_session(client)
    user_id = await _rider_id(client, rider["headers"])

    frozen = await client.post(
        f"/admin/wallets/{user_id}/freeze", json={}, headers=admin_headers
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["frozen"] is True

    still_in = await client.get("/auth/me", headers=rider["headers"])
    assert still_in.status_code == 200
    assert still_in.json()["is_blocked"] is False


async def test_rider_list_filters_by_block_and_verification(
    client: AsyncClient, jordan_settings: None, admin_headers: dict
) -> None:
    first = await rider_session(client)
    second = await register(client, RIDER | {"phone": "0797878781", "name": "راكبةٌ أخرى"})
    assert auth(second)

    user_id = await _rider_id(client, first["headers"])
    await client.post(
        f"/admin/users/{user_id}/block",
        json={"reason": "سببٌ مكتوب للاختبار"},
        headers=admin_headers,
    )

    blocked = await client.get(
        "/admin/users",
        headers=admin_headers,
        params={"role": "rider", "is_blocked": True},
    )
    assert [row["id"] for row in blocked.json()] == [user_id]

    active = await client.get(
        "/admin/users",
        headers=admin_headers,
        params={"role": "rider", "is_blocked": False},
    )
    assert user_id not in [row["id"] for row in active.json()]

    by_name = await client.get(
        "/admin/users",
        headers=admin_headers,
        params={"role": "rider", "q": "أخرى"},
    )
    assert [row["name"] for row in by_name.json()] == ["راكبةٌ أخرى"]
