"""تزامنُ حملة تأكيد الأرقام — **والقفلُ يُقاس بحذفه** (2026-08-31).

## ملفٌّ باسمه لا قسمٌ في ملفٍّ آخر

`test_locks_have_tests` **لا يقرأ إلا `test_*concurrency*.py`** — فاختبارٌ
صحيحٌ في ملفٍّ لا يطابق الاسمَ **يمرّ ولا يُحسب**، ويبقى القفلُ بلا شاهدٍ
يعرفه الحارس. (قِيس في اليوم نفسِه.)

## وتشابكٌ مرتَّبٌ لا `gather` على بابين

**أوّلُ نسخةٍ كانت `asyncio.gather` على نداءَي HTTP — ومرّت والقفلُ محذوف.**
وذلك بعينه ما يحذّر منه هذا المشروع: **نداءان في `gather` يتشابكان فقط إن
شاءت حلقةُ الأحداث**، وغالباً ينتهي الأول قبل أن يبدأ الثاني — **فيمرّ
الاختبارُ لأن التزامنَ لم يقع، لا لأن القفلَ عمل**.

**فالنسخةُ التي تقيس تفتح جلستين وتُرتّب التشابك بيدها**: الأولى تأخذ القفلَ
**وتُبقي معاملتَها مفتوحة**، والثانيةُ تبدأ فتقف عليه. وهي طريقةُ
`test_driver_documents_concurrency.py` نفسُها.

**وقِيس بحذف القفل**: نُزع `.with_for_update()` من `_locked` **فمرّ الإطلاقان
كلاهما** ولم يُرفع `Conflict` — وأُعيد فاخضرّ.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import AppError
from app.models.enums import CountryCode, UserRole, VerificationCampaignStatus
from app.models.user import User
from app.models.verification_campaign import VerificationCampaign
from app.services import verification_campaign


async def _draft(session_factory) -> VerificationCampaign:
    async with session_factory() as session:
        campaign = await verification_campaign.create_draft(
            session, country=CountryCode.JO
        )
        await session.commit()
        return campaign


async def _an_admin(session) -> User:
    return await session.scalar(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )


async def test_two_simultaneous_starts_leave_one_launch(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**إطلاقان متشابكان: واحدٌ ينجح والآخرُ يُرفض بنصّه.**

    **وبلا القفل يمرّ الاثنان**: كلاهما يقرأ `draft` قبل أن يكتب الآخر،
    فيكتبان `running` **ويسجّل كلاهما قيدَ تدقيق** — فتبدو الحملةُ أُطلقت
    مرّتين، **ويقرأ من يراجع أن مشرفاً أطلقها بعد أن أطلقها**.
    """
    campaign = await _draft(session_factory)

    async with session_factory() as first, session_factory() as second:
        actor_one = await _an_admin(first)
        actor_two = await _an_admin(second)

        # ── الأولى تأخذ القفلَ **وتُبقي معاملتَها مفتوحة**
        await verification_campaign.start(
            first, campaign_id=campaign.id, actor=actor_one
        )

        # ── والثانيةُ تبدأ فتقف على القفل
        blocked = asyncio.create_task(
            verification_campaign.start(
                second, campaign_id=campaign.id, actor=actor_two
            )
        )
        # **مهلةٌ قصيرةٌ تُثبت أنها واقفة** — ولو مرّت لكان القفلُ غائباً
        await asyncio.sleep(0.3)
        assert not blocked.done(), (
            "الثانيةُ لم تقف على القفل — **وهذا هو العطبُ نفسُه**: قرأت "
            "`draft` والأولى لم تودع بعد."
        )

        await first.commit()

        # ── وبعد الإيداع ترى الثانيةُ `running` فتُرفض بنصّها
        with pytest.raises(AppError) as caught:
            await blocked
        assert caught.value.status_code == 409

    # **والحقيقةُ في الصفِّ لا في الجواب**: أُطلقت مرّةً واحدةً بمُطلقٍ واحد
    async with session_factory() as session:
        row = await session.get(VerificationCampaign, campaign.id)
        assert row.status is VerificationCampaignStatus.RUNNING
        assert row.started_by_id is not None
