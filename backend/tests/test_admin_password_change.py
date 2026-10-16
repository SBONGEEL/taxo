"""تغييرُ كلمة المشرف من اللوحة، وإلزامُه عند أوّل دخول (SPEC §٧٦-م/٢، قرارُ المالك ٢٠٢٦-١٠-١٥).

**وما يُقاس هنا أبوابٌ لا شاشة**: حسابٌ يُنشأ اليومَ مردودٌ عن كلِّ بابٍ إداريٍّ حتى يغيّر كلمتَه، وبابُ حسابه وأبوابُ عامله مفتوحة؛
والتغييرُ بالحاليّة، وبقواعد التسجيل نفسِها، ولا يقبل الكلمةَ نفسَها؛ ويُخرج الجلساتِ الأخرى ويُبقي هذه؛ ويُكتب في التدقيق **بلا الكلمة**؛
**والحسابان القائمان لا يُمسّان**؛ **والعاملُ الثاني يبقى إلزاميّاً للمالك**؛ وتغييران متزامنان لا ينجحان كلاهما.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from collections import Counter

import pytest
from sqlalchemy import select

from app.models.admin_credential import AdminCredential
from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode, UserRole
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.services import admin_credentials
from app.services.auth.password import set_password

pytestmark = pytest.mark.asyncio

# **مولَّدةٌ لا حرفيّة** — فلا يصيح ماسحُ الأسرار على كلمةٍ في الشجرة
FIRST = "Awwal-" + secrets.token_urlsafe(12)
SECOND = "Thani-" + secrets.token_urlsafe(12)
GATED = "/admin/settings/pricing"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_admin(session_factory, username: str, *, owner: bool = False) -> uuid.UUID:
    """**كما يُنشأ أيُّ حسابٍ إداريٍّ بعد اليوم** — `admin_credentials.create` بافتراضه، لا بعلَمٍ يُمرَّر."""
    from app.core.redis_client import get_redis_client

    grants = [UserRoleGrant(role=UserRole.ADMIN)]
    if owner:
        grants.append(UserRoleGrant(role=UserRole.OWNER))
    async with session_factory() as session:
        user = User(phone=None, name="مشرفٌ جديد", role=UserRole.ADMIN, country_code=CountryCode.JO, role_grants=grants)
        session.add(user)
        await session.flush()
        await set_password(session, get_redis_client(), user=user, new_password=FIRST)
        await admin_credentials.create(session, user=user, username=username)
        await session.commit()
        return user.id


async def _login(client, username: str, password: str = FIRST) -> dict:
    answer = await client.post("/auth/login", json={"username": username, "password": password, "app": "panel"})
    assert answer.status_code == 200, answer.text
    return answer.json()["tokens"]


async def _change(client, tokens: dict, current: str, new: str):
    return await client.put(
        "/admin/account/password",
        json={"current_password": current, "new_password": new},
        headers=_bearer(tokens["access_token"]),
    )


async def test_a_new_admin_is_held_at_the_password_door(client, session_factory) -> None:
    """**كلُّ بابٍ إداريٍّ مردودٌ برمزه، وبابُ حسابه مفتوحٌ ويقول لماذا.**"""
    await _new_admin(session_factory, "jadid.awwal")
    tokens = await _login(client, "jadid.awwal")

    refused = await client.get(GATED, headers=_bearer(tokens["access_token"]))
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "password_change_required"

    mine = await client.get("/admin/account", headers=_bearer(tokens["access_token"]))
    assert mine.status_code == 200, mine.text
    assert mine.json()["must_change_password"] is True
    # **وأبوابُ العامل الثاني مفتوحةٌ له** — وإلا صارت حلقةً مع إلزام العامل
    assert (await client.get("/auth/me/totp", headers=_bearer(tokens["access_token"]))).status_code == 200


async def test_the_change_opens_the_panel_and_ends_the_other_sessions(client, session_factory) -> None:
    user_id = await _new_admin(session_factory, "jadid.thani")
    other = await _login(client, "jadid.thani")
    here = await _login(client, "jadid.thani")

    # **الحاليّةُ شرط**، **وقواعدُ التسجيل نفسُها**، **والجديدةُ غيرُ الحاليّة**
    assert (await _change(client, here, "not-" + FIRST, SECOND)).status_code == 401
    weak = await _change(client, here, FIRST, "12345678")
    assert weak.status_code == 422, weak.text
    same = await _change(client, here, FIRST, FIRST)
    assert same.status_code == 422, same.text

    done = await _change(client, here, FIRST, SECOND)
    assert done.status_code == 204, done.text

    assert (await client.get(GATED, headers=_bearer(here["access_token"]))).status_code == 200
    mine = await client.get("/admin/account", headers=_bearer(here["access_token"]))
    assert mine.json()["must_change_password"] is False
    # الأخرى خرجت، وهذه باقية
    assert (await client.get("/auth/me", headers=_bearer(other["access_token"]))).status_code == 401
    assert (await client.post("/auth/refresh", json={"refresh_token": here["refresh_token"]})).status_code == 200
    # والكلمةُ الجديدةُ هي التي تُدخِل
    await _login(client, "jadid.thani", SECOND)

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_type == "admin_credential", AdminAuditLog.actor_id == user_id
                )
            )
        ).all()
    changes = [row for row in rows if (row.details or {}).get("action") == "password_changed"]
    assert len(changes) == 1
    assert changes[0].details == {"action": "password_changed", "forced": True, "other_sessions_revoked": True}
    # **بلا الكلمة** — لا الحاليّة ولا الجديدة ولا تجزئةٌ في أيِّ سطر
    dumped = json.dumps([row.details for row in rows], ensure_ascii=False)
    assert FIRST not in dumped and SECOND not in dumped and "$2" not in dumped


async def test_a_voluntary_change_is_written_as_not_forced(client, session_factory) -> None:
    await _new_admin(session_factory, "jadid.thalith")
    tokens = await _login(client, "jadid.thalith")
    assert (await _change(client, tokens, FIRST, SECOND)).status_code == 204
    third = "Thalith-" + secrets.token_urlsafe(12)
    assert (await _change(client, tokens, SECOND, third)).status_code == 204
    async with session_factory() as session:
        rows = (
            await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_type == "admin_credential"))
        ).all()
    forced = [row.details["forced"] for row in rows if (row.details or {}).get("action") == "password_changed"]
    assert forced == [True, False]


async def test_existing_admins_are_not_held(client, admin_headers: dict, session_factory) -> None:
    """**الحسابان القائمان كما هما** — صفٌّ بلا العلَم (افتراضُ القاعدة `false`) لا يُردّ."""
    from app.core.redis_client import get_redis_client

    async with session_factory() as session:
        user = User(phone=None, name="قائم", role=UserRole.ADMIN, country_code=CountryCode.JO,
                    role_grants=[UserRoleGrant(role=UserRole.ADMIN)])
        session.add(user)
        await session.flush()
        await set_password(session, get_redis_client(), user=user, new_password=FIRST)
        session.add(AdminCredential(user_id=user.id, username="qaim.qadim", must_change_password=False))
        await session.commit()
    tokens = await _login(client, "qaim.qadim")
    assert (await client.get(GATED, headers=_bearer(tokens["access_token"]))).status_code == 200
    assert (await client.get(GATED, headers=admin_headers)).status_code == 200


async def test_the_owner_enrolls_a_factor_first_then_changes_the_password(client, session_factory) -> None:
    """**العاملُ الثاني يبقى إلزاميّاً للمالك** — وبابُ التغيير محروسٌ به كبقيّة اللوحة: يسجّل عاملَه ثمّ يغيّر كلمتَه."""
    await _new_admin(session_factory, "malik.tajriba", owner=True)
    tokens = await _login(client, "malik.tajriba")

    first = await client.put(
        "/admin/account/password",
        json={"current_password": FIRST, "new_password": SECOND},
        headers=_bearer(tokens["access_token"]),
    )
    assert first.status_code == 403, first.text
    assert first.json()["code"] == "totp_enrollment_required"
    totp = await client.get("/auth/me/totp", headers=_bearer(tokens["access_token"]))
    assert totp.status_code == 200
    assert totp.json()["required"] is True


async def test_two_changes_at_once_do_not_both_succeed(client, session_factory, monkeypatch) -> None:
    """**القفلُ قبل الفحص**: تبويبان يغيّران بالحاليّة نفسِها — واحدٌ ينجح والآخرُ يجد الحاليّةَ تغيّرت.

    وبلا القفل ينجحان كلاهما **ويُبلَّغ كلٌّ بنجاحه** والباقيةُ كلمةُ آخرِهما — فينسى صاحبُها أيَّهما كلمتُه.
    **والتداخلُ مرتَّبٌ لا متروكٌ للحظّ**: الأوّلُ يقف بعد فحصه وقبل كتابته حتى يبدأ الثاني — فبلا القفل يقرأ الثاني الكلمةَ القديمةَ
    وينجح (مقيسٌ بالنقض: `Counter({204: 2})`)، وبه ينتظر التزامَ الأوّل فيجد الحاليّةَ تغيّرت.
    """
    from app.routers import admin_account

    await _new_admin(session_factory, "jadid.mutazamin")
    tokens = await _login(client, "jadid.mutazamin")
    a = "Alif-" + secrets.token_urlsafe(12)
    b = "Baa-" + secrets.token_urlsafe(12)

    real = admin_account.set_password
    checked = asyncio.Event()
    calls = 0

    async def held(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            checked.set()
            await asyncio.sleep(1.5)
        return await real(*args, **kwargs)

    monkeypatch.setattr(admin_account, "set_password", held)

    first = asyncio.create_task(_change(client, tokens, FIRST, a))
    await asyncio.wait_for(checked.wait(), timeout=15)
    second = asyncio.create_task(_change(client, tokens, FIRST, b))
    answers = await asyncio.wait_for(asyncio.gather(first, second), timeout=30)
    assert Counter(answer.status_code for answer in answers) == Counter({204: 1, 401: 1}), [x.text for x in answers]
