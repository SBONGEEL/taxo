"""رمزُ التسليم بين التطبيقين (2026-08-19، SPEC §23).

**وما يُقاس هنا ليس أن التبديل يعمل، بل أنه لا يمنح شيئاً**: الرمزُ ينقل جلسةً
لمن يملك دورَ الهدف، ويُرفض لمن لا يملكه، ولا يُقبل مرتين، ولا في تطبيقٍ غير
الذي صدر له.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.enums import UserRole
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant

pytestmark = pytest.mark.asyncio


async def _grant(session_factory, user_id: str, role: UserRole) -> None:
    async with session_factory() as session:
        session.add(UserRoleGrant(user_id=uuid.UUID(user_id), role=role))
        await session.commit()


async def test_a_dual_role_account_moves_its_session_without_logging_in(
    client, session_factory
) -> None:
    """**لا كلمةَ مرورٍ ولا رمزَ تحقق** — أثبت هويّتَه في التطبيق الذي أصدره."""
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)

    started = await client.post(
        "/auth/handoff", json={"target": "driver"}, headers=rider["headers"]
    )
    assert started.status_code == 200, started.text
    token = started.json()["token"]

    exchanged = await client.post(
        "/auth/handoff/exchange", json={"token": token, "app": "driver"}
    )
    assert exchanged.status_code == 200, exchanged.text
    body = exchanged.json()
    assert body["user"]["id"] == rider["user"]["id"]
    assert body["tokens"]["access_token"]


async def test_an_account_without_the_target_role_is_refused_at_the_door(
    client,
) -> None:
    """**الزرُّ لا يمنح دوراً**: من لا يملك دورَ الهدف يُرفض قبل أن يصدر رمز."""
    from tests.helpers import rider_session

    rider = await rider_session(client)
    refused = await client.post(
        "/auth/handoff", json={"target": "driver"}, headers=rider["headers"]
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "wrong_app_for_role"


async def test_the_token_is_single_use(client, session_factory) -> None:
    """رمزٌ يُقبل مرتين رمزُ جلسةٍ لا رمزُ تسليم."""
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)
    token = (
        await client.post(
            "/auth/handoff", json={"target": "driver"}, headers=rider["headers"]
        )
    ).json()["token"]

    first = await client.post(
        "/auth/handoff/exchange", json={"token": token, "app": "driver"}
    )
    assert first.status_code == 200
    again = await client.post(
        "/auth/handoff/exchange", json={"token": token, "app": "driver"}
    )
    assert again.status_code == 401, again.text


async def test_a_token_issued_for_one_app_is_refused_in_another(
    client, session_factory
) -> None:
    """**مربوطٌ بهدفه**: رمزٌ يصلح لأيِّ تطبيق هو رمزُ جلسةٍ عامّ."""
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)
    token = (
        await client.post(
            "/auth/handoff", json={"target": "driver"}, headers=rider["headers"]
        )
    ).json()["token"]

    wrong = await client.post(
        "/auth/handoff/exchange", json={"token": token, "app": "rider"}
    )
    assert wrong.status_code == 401, wrong.text


async def test_a_role_withdrawn_between_issue_and_exchange_kills_the_token(
    client, session_factory
) -> None:
    """**الفحصُ يُعاد كاملاً عند المبادلة** — الرمزُ ليس إذناً مجمَّداً."""
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)
    token = (
        await client.post(
            "/auth/handoff", json={"target": "driver"}, headers=rider["headers"]
        )
    ).json()["token"]

    async with session_factory() as session:
        await session.execute(
            UserRoleGrant.__table__.delete().where(
                UserRoleGrant.user_id == uuid.UUID(rider["user"]["id"]),
                UserRoleGrant.role == UserRole.DRIVER,
            )
        )
        await session.commit()

    refused = await client.post(
        "/auth/handoff/exchange", json={"token": token, "app": "driver"}
    )
    assert refused.status_code == 403, refused.text


async def test_a_blocked_account_cannot_exchange(client, session_factory) -> None:
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)
    token = (
        await client.post(
            "/auth/handoff", json={"target": "driver"}, headers=rider["headers"]
        )
    ).json()["token"]

    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(rider["user"]["id"]))
        user.is_blocked = True
        await session.commit()

    refused = await client.post(
        "/auth/handoff/exchange", json={"token": token, "app": "driver"}
    )
    assert refused.status_code == 401, refused.text


async def test_the_token_is_not_a_refresh_token(client, session_factory) -> None:
    """**ولا يُنقل رمزُ التجديد نفسُه**: تدويرُه أحاديٌّ، فحاملان يُبطل أحدُهما الآخر."""
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)
    token = (
        await client.post(
            "/auth/handoff", json={"target": "driver"}, headers=rider["headers"]
        )
    ).json()["token"]

    # لا يُقبل حيث يُقبل رمزُ التجديد
    misused = await client.post("/auth/refresh", json={"refresh_token": token})
    assert misused.status_code == 401, misused.text


async def test_the_window_is_short_and_published(client, session_factory) -> None:
    """المهلةُ تُنشر فتعرف الواجهةُ متى تُعيد الطلبَ بدل أن تخمّن."""
    from app.services import handoff
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)
    body = (
        await client.post(
            "/auth/handoff", json={"target": "driver"}, headers=rider["headers"]
        )
    ).json()
    assert body["expires_in"] == handoff.TOKEN_TTL_SECONDS
    # **تسع النافذةُ إقلاعاً بارداً وتبقى قصيرة**: أسوأُ ما قِيس ١٥٫١ ثانية،
    # فحدٌّ أدنى يمنع عودةَ الثلاثين، وحدٌّ أعلى يمنع أن تصير جلسةً ثانية
    assert 60 <= handoff.TOKEN_TTL_SECONDS <= 300


async def test_the_panel_is_not_a_handoff_target(client, session_factory) -> None:
    """ولا يتّسع التسليمُ للوحة ولو حمل الحسابُ الدورين."""
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)
    refused = await client.post(
        "/auth/handoff", json={"target": "panel"}, headers=rider["headers"]
    )
    assert refused.status_code == 403, refused.text


async def test_no_switching_while_a_ride_is_running(
    client, session_factory, jordan_settings, stub_mapbox, fast_dispatch
) -> None:
    """**لا تبديلَ أثناء عملٍ قائم** — والزرُّ يقول لماذا، لا يُعطَّل صامتاً."""
    from tests.helpers import accepted_ride, approved_driver, bring_online, rider_session

    rider = await rider_session(client)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    await accepted_ride(client, rider["headers"], driver)

    await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)
    refused = await client.post(
        "/auth/handoff", json={"target": "driver"}, headers=rider["headers"]
    )
    assert refused.status_code == 409, refused.text
    body = refused.json()
    assert body["code"] == "handoff_blocked_by_active_work"
    assert body["message"]


async def test_the_account_publishes_its_roles_in_a_stable_order(client) -> None:
    """الزرُّ يقرأ ما يملكه من الجلسة — لا يسأل الشبكةَ عند كل ضغطة."""
    from tests.helpers import rider_session

    rider = await rider_session(client)
    me = await client.get("/auth/me", headers=rider["headers"])
    assert me.status_code == 200, me.text
    assert me.json()["roles"] == ["rider"]


async def test_a_wrong_target_attempt_burns_the_token(client, session_factory) -> None:
    """**محاولةٌ في تطبيقٍ غير الهدف تستهلك الرمز** — وهذا مقصود.

    `consume` تحذف قبل أن تفحص (`GETDEL`)، فلا تبقى نافذةٌ يُبادَل فيها الرمزُ
    مرتين من طلبين متزامنين — ولا يبقى **مِسبارٌ** يُجرَّب به الرمزُ على
    التطبيقين حتى يُصيب. وثمنُه ضغطةٌ ثانية، وهو أرخص من الاثنين.

    قِيس على السلك (2026-08-19): محاولةٌ خاطئةٌ ثم صحيحةٌ ⇒ كلتاهما `401`.
    """
    from tests.helpers import rider_session

    rider = await rider_session(client)
    await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)
    token = (
        await client.post(
            "/auth/handoff", json={"target": "driver"}, headers=rider["headers"]
        )
    ).json()["token"]

    wrong = await client.post(
        "/auth/handoff/exchange", json={"token": token, "app": "rider"}
    )
    assert wrong.status_code == 401

    # والصحيحةُ بعدها لا تجد شيئاً
    right = await client.post(
        "/auth/handoff/exchange", json={"token": token, "app": "driver"}
    )
    assert right.status_code == 401
