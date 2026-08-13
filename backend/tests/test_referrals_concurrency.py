"""تزامنُ مكافآت الإحالة (المرحلة 12-ح).

قاعدةُ المشروع: «مرحلةٌ تمسّ المال ليست منتهيةً بلا اختبار تزامن»، **واختبِرِ
الثابتَ الذي يملكه القفلُ نفسُه** لا ثابتاً يحرسه غيرُه.

**والثابتُ الذي يملكه `referrals._locked` هو صفُّ الإحالة لا قيدُ الدفتر**:
مفتاحُ التكرار `referral:{id}` يمنع القيدَ الثاني على كل حال، فاختبارٌ يعدّ
القيودَ يمرّ ولو حُذف القفل ولا يثبت عنه شيئاً.

**وما وقع فعلاً عند الحذف** (لا ما توقّعتُه): الجوابُ `['paid', 'paid']`. لا
استثناءَ ولا قيدٌ ثانٍ — `wallet.record` يجد مفتاحَ التكرار فيعيد **القيدَ
القائم** بلا خطأ، فتكتب الثانيةُ `rewarded_at` فوق الأولى وتعلن أنها دفعت. أي
أن **المنصّةَ تظنّ أنها دفعت مكافأتين والدفترُ يحمل واحدة** — وذلك أسوأ من
استثناء: الاستثناءُ يُرى في السجل، وهذا يُقرأ في تقرير الكلفة رقماً ضعف الحقيقة.
ومن هنا: مفتاحُ التكرار حَدَّ الضررَ ولم يمنعه، وهي بعينُها قاعدةُ المشروع «لا
تُقِم مفتاحَ تكرارٍ مقامَ قفل».

**والتداخلُ مُرتَّبٌ صريحاً** لا مُترَكٌ لجدولة الحلقة: جلسةٌ تحمل معاملتَها
مفتوحةً بينما تبدأ الثانية — كما في `test_stage8_concurrency.py`. ونداءان
عبر HTTP في `asyncio.gather` قد لا يتداخلان أصلاً، وهو النجاحُ الكاذب الذي
كُتبت هذه القاعدة لأجله (`CLAUDE.md`).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.driver import Driver
from app.models.enums import Gender, WalletTransactionType
from app.models.referral import DriverReferral
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import referrals as referrals_service
from tests.helpers import (
    DRIVER,
    SECOND_DRIVER,
    approved_driver,
    auth,
    enable_features,
    register,
)

DEADLOCK_TIMEOUT = 20


async def _ready(
    client: AsyncClient, admin_headers: dict, session_factory
) -> tuple[uuid.UUID, uuid.UUID]:
    """إحالةٌ مستحقّةٌ تماماً — يبقى دفعُها فقط."""
    await enable_features(
        session_factory, "driver_referrals_enabled", "wallet_enabled"
    )
    policy = await client.put(
        "/admin/referrals/settings?country_code=JO",
        json={"reward_amount": "5.000", "required_rides": 0},
        headers=admin_headers,
    )
    assert policy.status_code == 200, policy.text

    referrer = await register(client, DRIVER)
    mine = await client.get("/drivers/me/referrals", headers=auth(referrer))
    code = mine.json()["code"]

    referred = await approved_driver(
        client,
        session_factory,
        SECOND_DRIVER | {"referral_code": code},
        plate_number="AMM-7777",
    )
    async with session_factory() as session:
        driver = await session.get(Driver, referred["driver_id"])
        user = await session.get(User, driver.user_id)
        user.gender = Gender.FEMALE
        user.gender_verified_at = datetime.now(UTC)
        await session.commit()

    async with session_factory() as session:
        referral = await session.scalar(
            select(DriverReferral).where(
                DriverReferral.referred_driver_id == referred["driver_id"]
            )
        )
        return referral.id, uuid.UUID(referrer["user"]["id"])


async def test_two_sweeps_at_once_pay_one_reward(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """دورتان متزامنتان: مكافأةٌ واحدةٌ وقيدٌ واحدٌ ولا استثناء.

    والتداخلُ مُرتَّب: الأولى تقفل الصفَّ وتكتب وتبقي معاملتَها مفتوحة، ثم تبدأ
    الثانيةُ فتنتظر القفلَ — وبعد الـcommit تقرأ الصفَّ **مكافأً** فتعود بـ
    `None` هادئة. وبحذف القفل تقرأ الثانيةُ `rewarded_at IS NULL` وتُعلن دفعاً
    ثانياً لا وجودَ له في الدفتر: `['paid', 'paid']`.
    """
    referral_id, referrer_user_id = await _ready(client, admin_headers, session_factory)

    # **التداخلُ بمهلٍ صريحة كما في `test_stage8_concurrency.py`** لا بأحداث:
    # الحدثُ يوقظ الأولى فتُثبت في اللحظة نفسها التي تبدأ فيها الثانيةُ قراءتَها،
    # فتسبقُها الـcommit ويقرأ الثاني حالةً مثبتةً — فيمرّ الاختبارُ ولو حُذف
    # القفل. والمقصودُ أن تقع قراءةُ الثانية **داخل** معاملةِ الأولى المفتوحة.
    async def first() -> str:
        async with session_factory() as session:
            result = await referrals_service.pay(session, referral_id)
            await asyncio.sleep(0.4)  # تبقى المعاملةُ مفتوحةً بينما تقرأ الثانية
            await session.commit()
            return "paid" if result is not None else "skipped"

    async def second() -> str:
        await asyncio.sleep(0.1)  # بعد كتابةِ الأولى وقبل تثبيتها
        async with session_factory() as session:
            result = await referrals_service.pay(session, referral_id)
            await session.commit()
            return "paid" if result is not None else "skipped"

    outcomes = await asyncio.wait_for(
        asyncio.gather(first(), second()), timeout=DEADLOCK_TIMEOUT
    )
    assert sorted(outcomes) == ["paid", "skipped"], outcomes

    async with session_factory() as session:
        entries = (
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.type == WalletTransactionType.REFERRAL_BONUS
                )
            )
        ).all()
        assert len(entries) == 1
        assert entries[0].owner_id == referrer_user_id
        assert entries[0].amount == Decimal("5.000")
        assert entries[0].balance_after >= 0

        row = await session.get(DriverReferral, referral_id)
        assert row.rewarded_at is not None
        assert row.reward_amount == Decimal("5.000")
        assert row.transaction_id == entries[0].id


async def test_two_signups_with_two_codes_leave_one_referral(
    client: AsyncClient, session_factory, admin_headers: dict
):
    """**والفرادةُ في القاعدة تملك ثابتَها**: حسابٌ واحدٌ يُحال مرةً واحدة.

    وهذا الاختبارُ **يمرّ بحذف كلِّ قفل** — يملكه `UNIQUE (referred_driver_id)`
    وحدَه، وهو مكتوبٌ هنا صريحاً كي لا يُقرأ نجاحُه دليلاً على قفلٍ لا يحرسه
    (نفسُ ما وُثِّق عن حدِّ المستخدم في الكوبونات).
    """
    await enable_features(session_factory, "driver_referrals_enabled")
    first = await register(client, DRIVER)
    second = await register(client, SECOND_DRIVER)

    async with session_factory() as session:
        one = await session.scalar(
            select(Driver).where(Driver.user_id == uuid.UUID(first["user"]["id"]))
        )
        two = await session.scalar(
            select(Driver).where(Driver.user_id == uuid.UUID(second["user"]["id"]))
        )
        codes = (one.referral_code, two.referral_code)
        target = two.id

    async def attach(code: str) -> str:
        async with session_factory() as session:
            referred = await session.get(Driver, target)
            try:
                await referrals_service.attach(session, referred=referred, code=code)
                await session.commit()
                return "attached"
            except referrals_service.ReferralNotAllowed:
                return "refused"

    outcomes = await asyncio.wait_for(
        asyncio.gather(attach(codes[0]), attach(codes[0])), timeout=DEADLOCK_TIMEOUT
    )
    assert outcomes.count("attached") == 1, outcomes

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(DriverReferral)
            .where(DriverReferral.referred_driver_id == target)
        )
    assert count == 1
    assert codes[1]  # رمزُ الثاني موجودٌ ولم يُستعمل
