"""**صرفُ سرِّ البصمة مرّتين معاً** (SPEC §60-ج، `services/device_logins.py`) — والقفلُ مقيسٌ بحذفه.

ما يملكه قفلُ صفِّ البيان وحدَه: **سرٌّ واحدٌ يفتح جلسةً واحدة**. بغيره يقرأ الطلبان البيانَ نفسَه قبل أن يُلتزم أحدُهما، فيمرّان
الفحصَ معاً ويُصدر كلٌّ منهما جلسةً وسرّاً جديداً — **سرٌّ مسروقٌ يُصرف مع صاحبه فلا يُسقط أحدُهما الآخر**، ويضيع أحدُ السرّين
فيخرج صاحبُه من البصمة بلا سبب. ومعه: الثاني ينتظر الأوّلَ ثمّ يُعيد قراءةَ الصفّ فلا يطابق السرَّ القديم ⇒ رفضٌ واحدٌ بعلّته.

**وقِيس بحذفه** (٢٠٢٦-١١-٠٣): بلا `with_for_update()` في `device_logins._live` صار `Counter({200: 2})` — جلستان من سرٍّ واحد.
"""

from __future__ import annotations

import asyncio
from collections import Counter

from sqlalchemy import func, select

from app.models.auth_session import AuthSession
from app.models.device_login import DeviceLogin
from tests.helpers import RIDER, auth, register

DEVICE = "device-0002-concurrent"


async def test_one_secret_spent_twice_at_once_opens_one_session(client, session_factory) -> None:
    body = await register(client, RIDER)
    enrolled = await client.post("/auth/device-login/enroll", headers=auth(body), json={"device_id": DEVICE, "app": "rider"})
    assert enrolled.status_code == 200, enrolled.text
    secret = enrolled.json()["secret"]
    async with session_factory() as session:
        sessions_before = await session.scalar(select(func.count()).select_from(AuthSession))

    request = {"device_id": DEVICE, "secret": secret, "app": "rider"}
    results = await asyncio.wait_for(
        asyncio.gather(*(client.post("/auth/device-login", json=request) for _ in range(2))),
        timeout=20,
    )

    assert Counter(r.status_code for r in results) == Counter({200: 1, 401: 1}), [r.text for r in results]
    loser = next(r for r in results if r.status_code == 401)
    assert loser.json()["code"] == "invalid_credentials"
    async with session_factory() as session:
        # **جلسةٌ واحدةٌ جديدة**، **وبيانٌ حيٌّ واحدٌ بالسرِّ الذي ردّه الفائز**
        assert await session.scalar(select(func.count()).select_from(AuthSession)) == sessions_before + 1
        live = (await session.scalars(select(DeviceLogin).where(DeviceLogin.revoked_at.is_(None)))).all()
        assert len(live) == 1
    winner = next(r for r in results if r.status_code == 200).json()
    again = await client.post("/auth/device-login", json=request | {"secret": winner["device_secret"]})
    assert again.status_code == 200, again.text
