"""الجلسةُ تبقى حتى «تسجيل الخروج»، والبصمةُ تبقى بعده (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §60-ج).

- **جوابُ تجديدٍ ضاع** (تطبيقٌ قُتل والطلبُ في الطريق) لا يُخرج صاحبَه ولو بعد المهلة — **ما لم يُستعمل الحاليّ**؛ ومن استعمله ثمّ
  عاد السابقُ فذاك فرعان ⇒ الإبطالُ كما كان (`test_auth.py`).
- **البصمةُ بعد الخروج**: الخروجُ يُنهي الجلسةَ على الخادم، وبيانُ الجهاز يفتح جلسةً جديدة ويُدوَّر.
- **ويُبطَل** بتغيير الكلمة واستعادتها وبالحظر وبـ«الدخول بحساب آخر» — **ولا يمسّه الخروجُ العاديّ**.
- **وحسابٌ بعاملٍ ثانٍ لا يُعطاه**.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.security import decode_token
from app.models.auth_session import AuthSession
from app.services.token_service import GRACE
from tests.helpers import RIDER, auth, register

DEVICE = "device-0001-abcdef"


async def _age_rotation(session_factory) -> None:
    async with session_factory() as session:
        for row in (await session.scalars(select(AuthSession))).all():
            row.current_issued_at -= GRACE + timedelta(hours=3)
        await session.commit()


async def test_a_refresh_reply_lost_hours_ago_does_not_sign_the_user_out(client, session_factory) -> None:
    body = await register(client, RIDER)
    old = body["tokens"]["refresh_token"]
    rotated = await client.post("/auth/refresh", json={"refresh_token": old})
    assert rotated.status_code == 200
    # **التطبيقُ قُتل قبل أن يحفظ الجواب** — ثمّ فُتح بعد ساعات بالرمز القديم، ولم يُستعمل الحاليُّ قطّ
    await _age_rotation(session_factory)
    back = await client.post("/auth/refresh", json={"refresh_token": old})
    assert back.status_code == 200, back.text
    # **الحاليُّ نفسُه يُعاد سكُّه** — المعرِّفُ واحدٌ ولو اختلف النصُّ بوقت إصداره
    def claims(token: str) -> tuple[str, str]:
        payload = decode_token(token, "refresh")
        return payload["sid"], payload["jti"]

    assert claims(back.json()["refresh_token"]) == claims(rotated.json()["refresh_token"])
    assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {back.json()['access_token']}"})).status_code == 200


async def test_a_used_pair_then_its_predecessor_is_still_theft(client, session_factory) -> None:
    body = await register(client, RIDER)
    old = body["tokens"]["refresh_token"]
    rotated = (await client.post("/auth/refresh", json={"refresh_token": old})).json()
    # **الحاليُّ وصل صاحبَه واستُعمل** — فعودةُ السابق بعد المهلة فرعٌ ثانٍ
    assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {rotated['access_token']}"})).status_code == 200
    await _age_rotation(session_factory)
    assert (await client.post("/auth/refresh", json={"refresh_token": old})).status_code == 401
    assert (await client.post("/auth/refresh", json={"refresh_token": rotated["refresh_token"]})).status_code == 401


async def _enroll(client, headers: dict, app: str = "rider") -> str:
    response = await client.post("/auth/device-login/enroll", headers=headers, json={"device_id": DEVICE, "app": app})
    assert response.status_code == 200, response.text
    return response.json()["secret"]


async def test_fingerprint_login_survives_logout_and_rotates(client) -> None:
    body = await register(client, RIDER)
    secret = await _enroll(client, auth(body))

    out = await client.post("/auth/logout", json={"refresh_token": body["tokens"]["refresh_token"]})
    assert out.status_code == 204
    # **الخروجُ أنهى الجلسةَ على الخادم**
    assert (await client.get("/auth/me", headers=auth(body))).status_code == 401

    login = await client.post("/auth/device-login", json={"device_id": DEVICE, "secret": secret, "app": "rider"})
    assert login.status_code == 200, login.text
    fresh = login.json()
    assert fresh["user"]["phone"].endswith("791111111")
    assert fresh["device_secret"] != secret
    assert (await client.get("/auth/me", headers=auth(fresh))).status_code == 200

    # **المصروفُ لا يعود**، والجديدُ يعمل
    assert (await client.post("/auth/device-login", json={"device_id": DEVICE, "secret": secret, "app": "rider"})).status_code == 401
    again = await client.post(
        "/auth/device-login", json={"device_id": DEVICE, "secret": fresh["device_secret"], "app": "rider"}
    )
    assert again.status_code == 200, again.text


async def test_wrong_device_or_app_is_refused_alike(client) -> None:
    body = await register(client, RIDER)
    secret = await _enroll(client, auth(body))
    wrong_device = await client.post("/auth/device-login", json={"device_id": "device-9999-zzzz", "secret": secret, "app": "rider"})
    wrong_app = await client.post("/auth/device-login", json={"device_id": DEVICE, "secret": secret, "app": "driver"})
    assert wrong_device.status_code == wrong_app.status_code == 401
    assert wrong_device.json()["code"] == wrong_app.json()["code"]


async def test_forget_removes_the_binding(client) -> None:
    body = await register(client, RIDER)
    secret = await _enroll(client, auth(body))
    forgot = await client.post("/auth/device-login/forget", json={"device_id": DEVICE, "secret": secret, "app": "rider"})
    assert forgot.status_code == 204
    assert (await client.post("/auth/device-login", json={"device_id": DEVICE, "secret": secret, "app": "rider"})).status_code == 401


async def test_password_reset_removes_the_binding(client) -> None:
    from app.services.firebase_auth import mock_token

    body = await register(client, RIDER)
    secret = await _enroll(client, auth(body))
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
    assert (await client.post("/auth/device-login", json={"device_id": DEVICE, "secret": secret, "app": "rider"})).status_code == 401


async def test_admin_suspension_removes_the_binding(client, admin_headers) -> None:
    body = await register(client, RIDER)
    secret = await _enroll(client, auth(body))
    me = (await client.get("/auth/me", headers=auth(body))).json()
    blocked = await client.post(
        f"/admin/users/{me['id']}/block", json={"reason": "اختبار إيقاف الحساب"}, headers=admin_headers
    )
    assert blocked.status_code == 200, blocked.text
    assert (await client.post("/auth/device-login", json={"device_id": DEVICE, "secret": secret, "app": "rider"})).status_code == 401


async def test_a_second_enroll_replaces_the_first(client) -> None:
    body = await register(client, RIDER)
    first = await _enroll(client, auth(body))
    second = await _enroll(client, auth(body))
    assert (await client.post("/auth/device-login", json={"device_id": DEVICE, "secret": first, "app": "rider"})).status_code == 401
    assert (await client.post("/auth/device-login", json={"device_id": DEVICE, "secret": second, "app": "rider"})).status_code == 200


async def test_one_secret_spent_twice_at_once_opens_one_session(client) -> None:
    """**القفلُ يملك التدوير** — سرٌّ واحدٌ يُقدَّم مرّتين معاً: بلا `FOR UPDATE` يقرأ الطلبان الصفَّ نفسَه ويدوّرانه كلاهما،
    فتقوم جلستان من سرٍّ صُرف مرّة ويبقى في يد كلٍّ منهما سرٌّ «جديد» أحدُهما ميّت."""
    import asyncio
    from collections import Counter

    body = await register(client, RIDER)
    secret = await _enroll(client, auth(body))
    payload = {"device_id": DEVICE, "secret": secret, "app": "rider"}
    responses = await asyncio.wait_for(
        asyncio.gather(*(client.post("/auth/device-login", json=payload) for _ in range(3))), timeout=30
    )
    assert Counter(r.status_code for r in responses) == Counter({200: 1, 401: 2})
    winner = next(r.json() for r in responses if r.status_code == 200)
    assert (
        await client.post("/auth/device-login", json={**payload, "secret": winner["device_secret"]})
    ).status_code == 200


async def test_device_login_is_rate_limited_per_device(client) -> None:
    from app.core.config import settings

    statuses = []
    for _ in range(settings.login_rate_limit_attempts + 1):
        response = await client.post(
            "/auth/device-login", json={"device_id": DEVICE, "secret": "x" * 43, "app": "rider"}
        )
        statuses.append(response.status_code)
    assert statuses[-1] == 429, statuses
