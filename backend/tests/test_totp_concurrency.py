"""تزامنُ العامل الثاني (المرحلة 12-د).

قاعدةُ المشروع صريحة: «أيُّ مسارٍ يغيّر حالة صفٍّ يقفله بـ`for_update` **قبل**
أن يفحص الانتقال». وهنا حالتان لا واحدة، وكلٌّ منهما «لمرةٍ واحدة»:

1. **رمزُ الاسترداد**: `used_at` يُقرأ ثم يُكتب.
2. **`last_step`**: خطوةُ الرمز المقبول تُقرأ ثم تُكتب.

والاختبارُ يستدعي **الخدمةَ** لا الراوتر، والتداخلُ **مُرتَّبٌ عمداً** (الأولى
تكتب ولا تُثبّت، والثانية تبدأ وهي مفتوحة): طلبان على HTTP يتداخلان إن رتّبتهما
جدولةُ الحلقة، وذاك اختبارٌ يمنح ثقةً لا يملكها — نفسُ منهج
`test_driver_documents_concurrency.py`.

**والتحقق بالحذف**: بحذف `with_for_update()` من `totp.consume_recovery_code`
يصير الجوابُ `["first", "second"]` — رمزُ «المرةِ الواحدة» قُبِل مرتين وقيدا
تدقيقٍ لرمزٍ واحد.
"""

from __future__ import annotations

import asyncio

from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.exceptions import InvalidTotpCode
from app.models.audit import AdminAuditLog
from app.models.totp import UserRecoveryCode, UserTotp
from app.models.user import User
from app.services import totp

DEADLOCK_TIMEOUT = 20
ADMIN_PHONE = "+962790000001"


async def _admin(session_factory) -> User:
    async with session_factory() as session:
        return await session.scalar(select(User).where(User.phone == ADMIN_PHONE))


async def _enroll(client: AsyncClient, headers: dict) -> tuple[str, list[str]]:
    enrolled = await client.post("/auth/me/totp/enroll", headers=headers)
    secret = enrolled.json()["secret"]
    confirmed = await client.post(
        "/auth/me/totp/confirm",
        json={"code": totp.code_at(secret, totp.current_step())},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    return secret, confirmed.json()["recovery_codes"]


async def test_one_recovery_code_is_spent_once_however_it_races(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    _, codes = await _enroll(client, admin_headers)
    admin = await _admin(session_factory)
    code = codes[0]

    outcomes: list[str] = []

    async def _consume_holding_the_transaction() -> None:
        async with session_factory() as session:
            await totp.consume_recovery_code(
                session, user_id=admin.id, code=code, actor=admin
            )
            await asyncio.sleep(0.3)
            await session.commit()
            outcomes.append("first")

    async def _consume_meanwhile() -> None:
        await asyncio.sleep(0.05)
        async with session_factory() as session:
            try:
                await totp.consume_recovery_code(
                    session, user_id=admin.id, code=code, actor=admin
                )
                await session.commit()
                outcomes.append("second")
            except InvalidTotpCode:
                outcomes.append("refused")

    await asyncio.wait_for(
        asyncio.gather(_consume_holding_the_transaction(), _consume_meanwhile()),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert sorted(outcomes) == ["first", "refused"]

    async with session_factory() as session:
        spent = await session.scalar(
            select(func.count())
            .select_from(UserRecoveryCode)
            .where(
                UserRecoveryCode.user_id == admin.id,
                UserRecoveryCode.used_at.is_not(None),
            )
        )
        assert spent == 1
        # الثابتُ الذي يملكه القفل: استهلاكٌ واحد ⇔ قيدُ تدقيقٍ واحد
        audits = await session.scalar(
            select(func.count())
            .select_from(AdminAuditLog)
            .where(AdminAuditLog.entity_type == "user_recovery_code")
        )
        assert audits == 1
        # وبقيتُها سليمة: القفلُ يحرس صفَّه لا الجدول
        left = await totp.remaining_recovery_codes(session, admin.id)
        assert left == totp.RECOVERY_CODE_COUNT - 1


async def test_one_code_cannot_open_two_sessions_at_once(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """`last_step` تحت قفلٍ أيضاً: رمزٌ واحدٌ لا يُقبل في نداءين متزامنين.

    وبلا القفل يقرأ النداءان `last_step` نفسها فيمرّان معاً — وهي ثلاثون ثانيةً
    يملكها من قرأ الرمز من فوق كتف صاحبه.
    """
    secret, _ = await _enroll(client, admin_headers)
    admin = await _admin(session_factory)
    # الخطوةُ التالية: خطوةُ التأكيد محروقةٌ عمداً، فرمزُها مرفوضٌ بحق
    step = totp.current_step() + 1
    code = totp.code_at(secret, step)

    outcomes: list[str] = []

    async def _verify_holding_the_transaction() -> None:
        async with session_factory() as session:
            await totp.verify_code(session, user_id=admin.id, code=code)
            await asyncio.sleep(0.3)
            await session.commit()
            outcomes.append("first")

    async def _verify_meanwhile() -> None:
        await asyncio.sleep(0.05)
        async with session_factory() as session:
            try:
                await totp.verify_code(session, user_id=admin.id, code=code)
                await session.commit()
                outcomes.append("second")
            except InvalidTotpCode:
                outcomes.append("refused")

    await asyncio.wait_for(
        asyncio.gather(_verify_holding_the_transaction(), _verify_meanwhile()),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert sorted(outcomes) == ["first", "refused"]

    async with session_factory() as session:
        record = await session.scalar(
            select(UserTotp).where(UserTotp.user_id == admin.id)
        )
        assert record.last_step == step


async def test_two_logins_at_once_leave_one_spent_code(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """ونفسُ الثابت على المسار الحقيقي: تحديان ورمزُ استردادٍ واحد.

    هذا اختبارُ HTTP لا خدمة، وهو **مكمّلٌ لا بديل**: يثبت أن الراوتر يمرّ من
    الخدمة نفسِها، ولا يثبت شيئاً عن القفل (لأن تداخلَه متروكٌ للجدولة).
    """
    _, codes = await _enroll(client, admin_headers)

    first = await client.post(
        "/auth/login", json={"phone": ADMIN_PHONE, "password": "StaffSecret123"}
    )
    second = await client.post(
        "/auth/login", json={"phone": ADMIN_PHONE, "password": "StaffSecret123"}
    )

    responses = await asyncio.wait_for(
        asyncio.gather(
            client.post(
                "/auth/login/totp",
                json={
                    "challenge_token": first.json()["challenge_token"],
                    "recovery_code": codes[0],
                },
            ),
            client.post(
                "/auth/login/totp",
                json={
                    "challenge_token": second.json()["challenge_token"],
                    "recovery_code": codes[0],
                },
            ),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200, 401]

    admin = await _admin(session_factory)
    async with session_factory() as session:
        spent = await session.scalar(
            select(func.count())
            .select_from(UserRecoveryCode)
            .where(
                UserRecoveryCode.user_id == admin.id,
                UserRecoveryCode.used_at.is_not(None),
            )
        )
        assert spent == 1
