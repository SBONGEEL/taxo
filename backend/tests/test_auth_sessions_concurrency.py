"""تزامنُ تجديد الجلسة — قفلُ صفِّ `auth_sessions` في `token_service.rotate` (SPEC §60).

**وما يملكه القفلُ وحدَه**: أن **رمزاً واحداً يُقدَّم في اللحظة نفسِها من تبويبين
أو من إعادة طلبٍ ضاع جوابُه** يُخرج **رمزاً حيّاً واحداً** للجميع. بلا القفل
يقرأ الطلبان الرمزَ الحاليَّ نفسَه، **فيدوّر كلٌّ منهما إلى رمزٍ غيرِ رمز الآخر**،
ويفوز آخرُ من يلتزم — **فيحمل الآخرُ رمزاً ليس حاليّاً ولا سابقاً**، وتجديدُه
التالي يُقرأ سرقةً فتُبطل الجلسةُ كلُّها: **صاحبُ الحساب يخرج بلا أن يضغط شيئاً**،
وهو نقيضُ القرار.

**وما لا يملكه — يُقال**: الإبطالُ (الخروج، إنهاءُ الكلّ، كشفُ إعادة الاستعمال)
**يكتب `revoked_at` بعمودٍ لا يكتبه التدوير**، فيبقى الإبطالُ نافذاً ولو تسابقا
بلا قفل. فلا يُكتب هنا اختبارٌ يدّعي أنه يحرس ذلك بالقفل.

**وقِيس بحذف القفل**: نزعُ `.with_for_update()` من `token_service._locked` يُسقط
`test_one_token_presented_at_once_yields_one_live_token` — ثلاثةُ رموزٍ مختلفة بدل
واحد (انظر STATE.md، شجرةُ إعادة التصميم).
"""

from __future__ import annotations

import asyncio
from collections import Counter

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.auth_session import AuthSession
from tests.helpers import RIDER, register

# مهلةُ الجمع — **التعليقُ المتبادلُ يعلّق ولا يرتفع**، فالمهلةُ وحدَها تُسقطه
DEADLOCK_TIMEOUT = 30.0


async def test_one_token_presented_at_once_yields_one_live_token(
    client: AsyncClient, session_factory
) -> None:
    body = await register(client, RIDER)
    token = body["tokens"]["refresh_token"]

    responses = await asyncio.wait_for(
        asyncio.gather(
            *(
                client.post("/auth/refresh", json={"refresh_token": token})
                for _ in range(3)
            )
        ),
        timeout=DEADLOCK_TIMEOUT,
    )
    assert Counter(r.status_code for r in responses) == Counter({200: 3}), [
        r.text for r in responses
    ]

    # **رمزٌ واحدٌ للجميع** — الحاليُّ نفسُه يُعاد سكُّه حرفاً في مهلة السماح
    issued = {r.json()["refresh_token"] for r in responses}
    assert len(issued) == 1, "تفرّعت السلسلةُ إلى أكثر من رمزٍ حيّ"
    assert token not in issued

    # والرمزُ الواحدُ حيٌّ فعلاً، والجلسةُ واحدةٌ لم تُبطل
    (live,) = issued
    again = await client.post("/auth/refresh", json={"refresh_token": live})
    assert again.status_code == 200, again.text

    async with session_factory() as session:
        rows = (await session.scalars(select(AuthSession))).all()
    assert len(rows) == 1
    assert rows[0].revoked_at is None


async def test_many_tabs_refreshing_together_never_sign_their_owner_out(
    client: AsyncClient, session_factory
) -> None:
    """**ستّةُ تبويباتٍ في دورتين** — كلُّ دورةٍ بالرمز الذي أخرجته التي قبلها.

    وهي الحالُ التي يُفتح فيها الحاسوبُ بعد نومٍ فتنطلق تبويباتُ اللوحة كلُّها
    معاً: **لا تُبطل الجلسة، ولا يُرفض أحد**.
    """
    body = await register(client, RIDER)
    token = body["tokens"]["refresh_token"]

    for _ in range(2):
        responses = await asyncio.wait_for(
            asyncio.gather(
                *(
                    client.post("/auth/refresh", json={"refresh_token": token})
                    for _ in range(6)
                )
            ),
            timeout=DEADLOCK_TIMEOUT,
        )
        assert {r.status_code for r in responses} == {200}, [r.text for r in responses]
        issued = {r.json()["refresh_token"] for r in responses}
        assert len(issued) == 1
        (token,) = issued

    async with session_factory() as session:
        revoked = await session.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(AuthSession.revoked_at.is_not(None))
        )
    assert revoked == 0
