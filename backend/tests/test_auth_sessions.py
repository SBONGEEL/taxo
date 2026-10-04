"""جلساتُ الدخول — **تبقى حتى يخرج صاحبُها** (SPEC §60، قرارُ المالك ٢٠٢٦-١٠-٠٤).

**والقرارُ نفسُه أباح تغييراً واحداً وشرط أربعةً معه**، وكلُّ اختبارٍ هنا يقيس
واحداً منها بعينه لا وصفَه:

1. **«إنهاءُ كلِّ الجلسات» يُنهي جلسةَ الجهاز الآخر** — طلبُه التالي، وتجديدُه،
   **ومقبسُه المفتوح**، ورمزُ إشعاره.
2. **الخروجُ يُنهي الجلسةَ على الخادم** لا على الجهاز وحدَه — وجلسةً واحدةً لا كلَّها.
3. **حسابُ الطوارئ يصيح في كلِّ استعمال** — والاستعمالُ صار استئنافاً بعد غياب.
4. **الجلساتُ تنجو من إعادة تشغيل الخادم أو Redis** — فهي صفوفٌ في القاعدة.

ومعها ما يجعل «تبقى» صادقة: **لا عمرَ ولا مهلةَ خمول**، **ورموزُ ما قبل §60 لا
تُخرج أحداً** يومَ التحويل.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from httpx_ws import HTTPXWSException, aconnect_ws
from sqlalchemy import func, select

from app.core.redis_client import get_redis_client
from app.models.auth_session import AuthSession
from app.models.device import DeviceToken
from app.ws import events
from tests.conftest import ws_client
from tests.helpers import RIDER, register

WS_RIDER = "http://test/api/v1/ws/rider"
RECEIVE_TIMEOUT = 12.0


def _bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _second_device(client: AsyncClient, payload: dict = RIDER) -> dict:
    """دخولٌ ثانٍ للحساب نفسِه — **جهازٌ آخر**، فجلسةٌ أخرى."""
    response = await client.post(
        "/auth/login",
        json={
            "phone": payload["phone"],
            "password": payload["password"],
            "country_code": payload["country_code"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["tokens"]


async def _receive(ws, *, of_type: str) -> dict:
    async def _read() -> dict:
        while True:
            message = await ws.receive_json()
            if message.get("type") == of_type:
                return message

    return await asyncio.wait_for(_read(), timeout=RECEIVE_TIMEOUT)


async def _closed(ws) -> bool:
    """**المقبسُ أُغلق من الخادم** — قراءةٌ ترتفع بإغلاقه، لا مهلةٌ تنقضي.

    **وأمرُ الإغلاق نفسُه لا يصل التطبيقَ أبداً**: وصولُه عطبٌ لا رسالة — وهو
    بعينه ما أمسكه هذا الاختبارُ في مقبس الراكب قبل أن يُودَع.
    """

    async def _drain() -> None:
        while True:
            message = await ws.receive_json()
            assert message.get("type") != "session_revoked", "وصل أمرُ الإغلاق إلى التطبيق"

    try:
        await asyncio.wait_for(_drain(), timeout=RECEIVE_TIMEOUT)
    except HTTPXWSException:
        return True
    except TimeoutError:
        return False
    return False


# ---------------------------------------------------------------- تبقى


async def test_a_session_has_no_age_and_no_idle_limit(
    client: AsyncClient, session_factory
) -> None:
    """**رمزُ التجديد بلا `exp`، والجلسةُ تُجدَّد بعد سنةٍ من الصمت.**

    وكان قبل §60 يموت بعد ثلاثين يوماً — **ولا شيءَ يحمل عمراً اليوم**: يُقدَّم
    ختمُ الصفِّ نفسِه سنةً، وهو وحدَه ما يقرؤه التجديد.
    """
    from app.core.security import decode_token

    body = await register(client, RIDER)
    refresh_token = body["tokens"]["refresh_token"]
    assert "exp" not in decode_token(refresh_token, "refresh")

    async with session_factory() as session:
        for row in (await session.scalars(select(AuthSession))).all():
            row.created_at -= timedelta(days=400)
            row.current_issued_at -= timedelta(days=400)
            row.last_used_at -= timedelta(days=400)
        await session.commit()

    refreshed = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200, refreshed.text
    me = await client.get("/auth/me", headers=_bearer(refreshed.json()["access_token"]))
    assert me.status_code == 200


async def test_sessions_survive_a_redis_restart(client: AsyncClient) -> None:
    """**Redis يُفرَغ كلُّه — والجلسةُ باقية** (§60-ب/٤).

    وكان مفتاحُ التجديد في Redis، **فسقوطُه أو إعادةُ تشغيله بلا قرصٍ يُخرج
    الجميع**. والإفراغُ أشدُّ من إعادة التشغيل: لا شيءَ يبقى فيه البتّة.
    """
    body = await register(client, RIDER)
    await get_redis_client().flushdb()

    me = await client.get("/auth/me", headers=_bearer(body["tokens"]["access_token"]))
    assert me.status_code == 200
    refreshed = await client.post(
        "/auth/refresh", json={"refresh_token": body["tokens"]["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text


async def test_sessions_survive_a_server_restart(client: AsyncClient) -> None:
    """**لا شيءَ من الجلسة في ذاكرة العملية** — فإعادةُ التشغيل لا تمسّها.

    يُقاس بما تعيده إعادةُ التشغيل فعلاً: **محرّكُ القاعدة يُتخلّص من اتصالاته**
    واتصالُ Redis يُغلق ويُفتح غيرُه — ثمّ يُجدَّد الرمزُ نفسُه.
    """
    from app.core.db import engine
    from app.core.redis_client import close_redis_client

    body = await register(client, RIDER)
    await engine.dispose()
    await close_redis_client()

    refreshed = await client.post(
        "/auth/refresh", json={"refresh_token": body["tokens"]["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text


# ---------------------------------------------------------------- الخروج


async def test_logout_ends_this_session_on_the_server_and_only_it(
    client: AsyncClient, session_factory
) -> None:
    """**الخروجُ يُسقط توكنَ الوصول نفسَه عند طلبه التالي** — لا بعد انتهائه.

    وكان قبل §60 يمحو مفتاحَ التجديد وحدَه، **فيبقى توكنُ الوصول يعمل حتى
    ينتهي**. **والجهازُ الآخرُ لا يُمسّ**: الخروجُ ليس «إنهاءَ الكلّ».
    """
    body = await register(client, RIDER)
    other = await _second_device(client)

    out = await client.post(
        "/auth/logout", json={"refresh_token": body["tokens"]["refresh_token"]}
    )
    assert out.status_code == 204

    assert (
        await client.get("/auth/me", headers=_bearer(body["tokens"]["access_token"]))
    ).status_code == 401
    assert (
        await client.post(
            "/auth/refresh", json={"refresh_token": body["tokens"]["refresh_token"]}
        )
    ).status_code == 401

    assert (
        await client.get("/auth/me", headers=_bearer(other["access_token"]))
    ).status_code == 200

    async with session_factory() as session:
        reasons = sorted(
            str(reason)
            for reason in (await session.scalars(select(AuthSession.revoked_reason))).all()
        )
    assert reasons == ["None", "logout"]


async def test_logout_closes_that_sessions_socket_and_spares_the_other(
    client: AsyncClient, jordan_settings: None
) -> None:
    """**مقبسُ الجلسة المُنهاة يُغلق، ومقبسُ الأخرى يبقى يتلقّى.**"""
    body = await register(client, RIDER)
    user_id = body["user"]["id"]
    other = await _second_device(client)

    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_RIDER}?token={body['tokens']['access_token']}", client=sockets
        ) as mine, aconnect_ws(
            f"{WS_RIDER}?token={other['access_token']}", client=sockets
        ) as theirs:
            await _receive(mine, of_type="connected")
            await _receive(theirs, of_type="connected")

            await client.post(
                "/auth/logout", json={"refresh_token": body["tokens"]["refresh_token"]}
            )
            assert await _closed(mine), "بقي مقبسُ الجلسة المُنهاة مفتوحاً"

            # **والأخرى حيّةٌ تتلقّى** — قياسٌ موجبٌ لا غيابُ إغلاقٍ في مهلة
            await events.publish(
                get_redis_client(), events.user_channel(user_id), {"type": "probe"}
            )
            assert (await _receive(theirs, of_type="probe"))["type"] == "probe"


# ------------------------------------------------------------ إنهاءُ الكلّ


async def test_ending_all_sessions_signs_the_other_device_out(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**هاتفٌ ضاع**: من جهازٍ آخر يُنهى كلُّ شيء — وهذا الجهازُ معه (§60-ب/١).

    والجهازُ الضائعُ يُقاس من أربع جهات: طلبُه التالي، وتجديدُه، **ومقبسُه
    المفتوح**، **ورمزُ إشعاره** — هاتفٌ تُبطل جلستُه ويبقى يتلقّى إشعاراتِ الحساب
    ليس هاتفاً أُخرج.
    """
    lost = await register(client, RIDER)
    here = await _second_device(client)

    device = await client.put(
        "/me/devices",
        json={"device_id": "lost-phone-1", "token": "fcm-token-of-the-lost-phone", "platform": "android"},
        headers=_bearer(lost["tokens"]["access_token"]),
    )
    assert device.status_code == 200, device.text

    async with ws_client() as sockets:
        async with aconnect_ws(
            f"{WS_RIDER}?token={lost['tokens']['access_token']}", client=sockets
        ) as lost_socket:
            await _receive(lost_socket, of_type="connected")

            ended = await client.post(
                "/auth/sessions/revoke-all", headers=_bearer(here["access_token"])
            )
            assert ended.status_code == 204, ended.text
            assert await _closed(lost_socket), "بقي مقبسُ الهاتف الضائع مفتوحاً"

    for tokens in (lost["tokens"], here):
        assert (
            await client.get("/auth/me", headers=_bearer(tokens["access_token"]))
        ).status_code == 401
        assert (
            await client.post(
                "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            )
        ).status_code == 401

    async with session_factory() as session:
        live = await session.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(AuthSession.revoked_at.is_(None))
        )
        devices = await session.scalar(select(func.count()).select_from(DeviceToken))
    assert live == 0
    assert devices == 0


async def test_ending_all_sessions_needs_a_live_session(client: AsyncClient) -> None:
    """**البابُ لصاحب جلسةٍ حيّة** — لا يُنادى بلا توكن."""
    assert (await client.post("/auth/sessions/revoke-all")).status_code == 401


# ----------------------------------------------- كلمةُ المرور والعاملُ الثاني


async def test_an_admin_password_change_keeps_this_session_and_ends_the_others(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**«تُبطَل بقيةُ الجلسات لا هذه»** — وعدُ الشاشة منذ بُنيت، صار مقيساً.

    وكان قبل §60 يمحو مفتاحَ هذه أيضاً، **فتسقط بعد ربع ساعةٍ رغم الوعد**.
    """
    login = await client.post(
        "/auth/login", json={"phone": "+962790000001", "password": "StaffSecret123"}
    )
    assert login.status_code == 200, login.text
    here = login.json()["tokens"]

    changed = await client.put(
        "/admin/account/password",
        json={"current_password": "StaffSecret123", "new_password": "AnotherSecret456"},
        headers=_bearer(here["access_token"]),
    )
    assert changed.status_code == 204, changed.text

    assert (
        await client.get("/auth/me", headers=_bearer(here["access_token"]))
    ).status_code == 200
    assert (
        await client.post("/auth/refresh", json={"refresh_token": here["refresh_token"]})
    ).status_code == 200
    # والجلسةُ الأخرى (جلسةُ الفيكستشر) سقطت عند طلبها التالي
    assert (await client.get("/auth/me", headers=admin_headers)).status_code == 401


async def test_a_password_reset_ends_every_session(client: AsyncClient) -> None:
    """**الاستعادةُ تُخرج الجميعَ ثم تفتح جلسةً واحدةً جديدة** — كما كانت.

    والفرقُ عن §60 أن توكنَ الوصول القديمَ **يسقط عند طلبه التالي** لا بعد
    انتهائه — كلمةٌ تُغيَّر لأن القديمة تسرّبت لا تترك ربعَ ساعةٍ لمن سرّبها.
    """
    from app.services.firebase_auth import mock_token

    body = await register(client, RIDER)
    reset = await client.post(
        "/auth/password-reset",
        json={
            "phone": RIDER["phone"],
            "country_code": "JO",
            "verification_token": mock_token("+962791111111"),
            "new_password": "BrandNewSecret789",
        },
    )
    assert reset.status_code == 200, reset.text

    assert (
        await client.get("/auth/me", headers=_bearer(body["tokens"]["access_token"]))
    ).status_code == 401
    assert (
        await client.get(
            "/auth/me", headers=_bearer(reset.json()["tokens"]["access_token"])
        )
    ).status_code == 200


# ------------------------------------------------------------ حسابُ الطوارئ


async def _break_glass(session_factory, username: str) -> None:
    from app.core.security import hash_password
    from app.models.enums import CountryCode, UserRole
    from app.models.user import User
    from app.models.user_role_grant import UserRoleGrant
    from app.services import admin_credentials

    async with session_factory() as session:
        user = User(
            phone=None,
            name="مشرف — الطوارئ",
            role=UserRole.ADMIN,
            country_code=CountryCode.JO,
            role_grants=[UserRoleGrant(role=UserRole.ADMIN)],
            password_hash=hash_password("StaffSecret123"),
        )
        session.add(user)
        await session.flush()
        await admin_credentials.create(
            session, user=user, username=username, is_break_glass=True
        )
        await session.commit()


async def _alerts(session_factory) -> list[dict]:
    from app.models.audit import AdminAuditLog

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_type == "admin_break_glass_login"
                )
            )
        ).all()
    return [row.details for row in rows]


async def test_the_break_glass_account_still_alerts_on_every_use(
    client: AsyncClient, session_factory
) -> None:
    """**كلُّ استعمالٍ له صياحُه** — والجلسةُ لم تعد تموت فتفرض دخولاً جديداً.

    فالاستئنافُ بعد غيابٍ يصيح كما يصيح الدخول (`note_resume`)، **والعملُ
    المتّصلُ لا يصيح** — وإلا صار الصياحُ ضجيجاً يُقرأ ولا يُميَّز.
    """
    from app.services.token_service import BREAK_GLASS_RESUME_GAP

    await _break_glass(session_factory, "tawaari.thani")
    login = await client.post(
        "/auth/login",
        json={"username": "tawaari.thani", "password": "StaffSecret123", "app": "panel"},
    )
    assert login.status_code == 200, login.text
    assert len(await _alerts(session_factory)) == 1

    # عملٌ متّصل: تجديدٌ بعد دقائق لا يصيح
    first = await client.post(
        "/auth/refresh", json={"refresh_token": login.json()["tokens"]["refresh_token"]}
    )
    assert first.status_code == 200, first.text
    assert len(await _alerts(session_factory)) == 1

    # غيابٌ ثم عودة: يصيح بالنوع نفسِه، و`resumed` يقول إنه استئناف
    async with session_factory() as session:
        for row in (await session.scalars(select(AuthSession))).all():
            row.last_used_at -= BREAK_GLASS_RESUME_GAP + timedelta(minutes=1)
        await session.commit()
    resumed = await client.post(
        "/auth/refresh", json={"refresh_token": first.json()["refresh_token"]}
    )
    assert resumed.status_code == 200, resumed.text
    alerts = await _alerts(session_factory)
    assert len(alerts) == 2
    resumes = [alert for alert in alerts if alert.get("resumed")]
    assert len(resumes) == 1
    assert resumes[0]["username"] == "tawaari.thani"


async def test_an_ordinary_admin_resuming_is_not_marked_break_glass(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """ولا يُصاح على العاديّ إذا عاد — الصياحُ للبابِ النائم وحدَه."""
    from app.services.token_service import BREAK_GLASS_RESUME_GAP

    login = await client.post(
        "/auth/login", json={"phone": "+962790000001", "password": "StaffSecret123"}
    )
    async with session_factory() as session:
        for row in (await session.scalars(select(AuthSession))).all():
            row.last_used_at -= BREAK_GLASS_RESUME_GAP + timedelta(minutes=1)
        await session.commit()
    resumed = await client.post(
        "/auth/refresh", json={"refresh_token": login.json()["tokens"]["refresh_token"]}
    )
    assert resumed.status_code == 200, resumed.text
    assert await _alerts(session_factory) == []


# ------------------------------------------------------ يومُ التحويل نفسُه


async def test_a_token_issued_before_60_is_adopted_once(
    client: AsyncClient, session_factory
) -> None:
    """**رموزُ ما قبل §60 لا تُخرج أحداً**: رمزٌ مفتاحُه في Redis يُقبل مرّةً
    ويصير جلسةً في القاعدة — **ثمّ لا يُقبل ثانية** كما لم يكن يُقبل."""
    from app.core.security import _create_token

    body = await register(client, RIDER)
    subject = body["user"]["id"]
    legacy, jti, _ = _create_token(subject, "refresh", timedelta(days=30))
    await get_redis_client().set(f"auth:refresh:{subject}:{jti}", "1")

    adopted = await client.post("/auth/refresh", json={"refresh_token": legacy})
    assert adopted.status_code == 200, adopted.text
    me = await client.get("/auth/me", headers=_bearer(adopted.json()["access_token"]))
    assert me.status_code == 200

    replay = await client.post("/auth/refresh", json={"refresh_token": legacy})
    assert replay.status_code == 401

    async with session_factory() as session:
        sessions = await session.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(AuthSession.user_id == uuid.UUID(subject))
        )
    # جلسةُ التسجيل، والجلسةُ التي صار إليها الرمزُ القديم
    assert sessions == 2


@pytest.mark.parametrize("revoke_reason", ["password_changed", "logout_all"])
async def test_a_pre_60_token_does_not_outlive_a_revocation(
    client: AsyncClient, revoke_reason: str
) -> None:
    """**ومفتاحُ ما قبل §60 يُمحى مع كلِّ إبطالٍ للكلّ** — وإلا عادت جلسةٌ أُبطلت
    عند أوّل تجديدٍ برمزٍ قديم."""
    from app.core.security import _create_token

    body = await register(client, RIDER)
    subject = body["user"]["id"]
    legacy, jti, _ = _create_token(subject, "refresh", timedelta(days=30))
    await get_redis_client().set(f"auth:refresh:{subject}:{jti}", "1")

    if revoke_reason == "logout_all":
        ended = await client.post(
            "/auth/sessions/revoke-all",
            headers=_bearer(body["tokens"]["access_token"]),
        )
        assert ended.status_code == 204
    else:
        from app.services.firebase_auth import mock_token

        reset = await client.post(
            "/auth/password-reset",
            json={
                "phone": RIDER["phone"],
                "country_code": "JO",
                "verification_token": mock_token("+962791111111"),
                "new_password": "BrandNewSecret789",
            },
        )
        assert reset.status_code == 200, reset.text

    refused = await client.post("/auth/refresh", json={"refresh_token": legacy})
    assert refused.status_code == 401
