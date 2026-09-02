"""إلغاءُ اشتراكٍ من اللوحة — البند ٢ (§38، قرارُ المالك 2026-09-02).

**والقاعدةُ بنصِّه**: «الإلغاءُ فوريّ، وما لم يُستعمل يُردّ إلى محفظة الكبتن —
لأن «ألغيتُه» يجب أن تعني «أوقفتُه» وإلا كذب الزرّ؛ والردّ لأن الإلغاء بيد
الإدارة لا بيده، فاحتجازُ مالٍ عن مدّةٍ منعناه من استعمالها شكوى بلا جواب».

**وما يقيسه هذا الملفّ، أربعةٌ لا واحد:**

1. **أن المالَ يعود فعلاً** — قيدٌ في الدفتر لا رقمٌ في ردّ.
2. **وأن الصفوف المكدَّسة تسقط كلُّها** — الجاري بالتناسب والقادمُ كاملاً.
3. **وأن الشهرَ المجانيَّ لا يُنتج قيداً** — المدفوعُ صفرٌ فلا شيءَ يُردّ.
4. **وأن النسبةَ المجمَّدة تسقط** — وهو مخرجُ الانتهاء نفسُه.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.driver import Driver
from app.models.enums import (
    CountryCode,
    Currency,
    PaymentMethod,
    SubscriptionDurationType,
    SubscriptionStatus,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.wallet import WalletTransaction
from tests.helpers import DRIVER, approved_driver

pytestmark = pytest.mark.usefixtures("jordan_settings", "jordan_wallet")

MONTH = timedelta(days=30)


async def _plan(session_factory, price: str = "30.000") -> SubscriptionPlan:
    async with session_factory() as session:
        plan = await session.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == CountryCode.JO,
                SubscriptionPlan.duration_type == SubscriptionDurationType.MONTHLY,
            )
        )
        if plan is None:
            plan = SubscriptionPlan(
                name="شهري",
                duration_type=SubscriptionDurationType.MONTHLY,
                price=Decimal(price),
                currency=Currency.JOD,
                country_code=CountryCode.JO,
            )
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
        return plan


async def _subscription(
    session_factory,
    driver_id,
    *,
    starts_at: datetime,
    amount_paid: str,
    list_price: str = "30.000",
) -> None:
    """صفُّ اشتراكٍ بمدّةٍ محدَّدةٍ **موضوعُ القياس نفسُه**.

    **ولا يُقاد بمسار الشراء**: المقيسُ هو **ما يقع للمدّة عند الإلغاء**،
    والمدّةُ زمنٌ لا يُقاد — اشتراكٌ بدأ قبل عشرة أيام لا يُشترى في اختبار،
    وانتظارُه عشرة أيام ليس قياساً. **وهو الاستثناءُ المكتوب في
    `test_no_shortcut_fixtures`**: «حين يكون موضوعُ الاختبار العرضَ لا المسار».
    """
    plan = await _plan(session_factory)
    async with session_factory() as session:
        session.add(
            DriverSubscription(
                driver_id=driver_id,
                plan_id=plan.id,
                starts_at=starts_at,
                expires_at=starts_at + MONTH,
                amount_paid=Decimal(amount_paid),
                list_price=Decimal(list_price),
                discount_amount=Decimal(list_price) - Decimal(amount_paid),
                payment_method=PaymentMethod.WALLET,
                status=SubscriptionStatus.ACTIVE,
            )
        )
        driver = await session.get(Driver, driver_id)
        driver.commission_percent_from_subscription = Decimal("0")
        await session.commit()


async def _balance(session_factory, user_id) -> Decimal:
    async with session_factory() as session:
        return await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == user_id,
                WalletTransaction.owner_type == WalletOwnerType.DRIVER,
            )
        )


# ═════════════════════════ الردُّ بالتناسب — والمالُ يعود فعلاً


async def test_cancelling_refunds_the_unused_days_as_a_new_ledger_entry(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**نصفُ المدّةِ مضى ⇒ نصفُ المدفوع يعود** — قيداً جديداً لا تعديلَ رصيد.

    **والدفترُ لا يُعدَّل** (المطلقةُ الثانية): الردُّ قيدٌ دائنٌ نوعُه
    `refund`، **ولا `UPDATE` على قيدٍ قائم**.
    """
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    await _subscription(
        session_factory,
        driver["driver_id"],
        starts_at=datetime.now(UTC) - MONTH / 2,
        amount_paid="30.000",
    )
    before = await _balance(session_factory, driver["user_id"])

    row_id = str(
        (
            await client.get(
                "/admin/subscriptions", headers=admin_headers
            )
        ).json()[0]["id"]
    )

    # **المعاينةُ قبل الفعل** — وهي ما تقرؤه ورقةُ التأكيد
    preview = await client.get(
        f"/admin/subscriptions/{row_id}/cancellation-preview", headers=admin_headers
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["cancelled_count"] == 1
    promised = Decimal(preview.json()["total_refund"])
    assert Decimal("14.000") < promised <= Decimal("15.100"), promised

    done = await client.post(
        f"/admin/subscriptions/{row_id}/cancel",
        json={"reason": "طلبَ الكبتنُ الإيقافَ وسُوّي معه"},
        headers=admin_headers,
    )
    assert done.status_code == 200, done.text

    # **وما وعدت به المعاينةُ هو ما وقع** — بيتُ الحسبة واحد
    assert Decimal(done.json()["total_refund"]) == promised

    after = await _balance(session_factory, driver["user_id"])
    assert after - before == promised

    async with session_factory() as session:
        entry = await session.scalar(
            select(WalletTransaction).where(
                WalletTransaction.owner_id == driver["user_id"],
                WalletTransaction.type == WalletTransactionType.REFUND,
            )
        )
        assert entry is not None and entry.amount == promised
        row = await session.scalar(select(DriverSubscription))
        assert row.status is SubscriptionStatus.CANCELLED
        assert row.cancel_reason == "طلبَ الكبتنُ الإيقافَ وسُوّي معه"
        assert row.cancelled_at is not None and row.cancelled_by is not None
        assert row.refund_transaction_id == entry.id
        # **والنسبةُ المجمَّدة سقطت** — مخرجُ الانتهاء نفسُه
        assert (
            await session.scalar(
                select(Driver.commission_percent_from_subscription).where(
                    Driver.id == driver["driver_id"]
                )
            )
        ) is None


# ═════════════════════════ المكدَّس — «ألغيتُه» تعني كلَّ ما لم ينقضِ


async def test_a_stacked_future_period_is_cancelled_whole_with_no_proration(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**التجديدُ المبكر يكدّس صفّاً يبدأ لاحقاً** — ولم يبدأ فيُردّ كاملاً.

    **وزرٌّ يُبقي اشتراكاً قادماً بعد الإلغاء يكذب** (قرارُ المالك).
    """
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    now = datetime.now(UTC)
    await _subscription(
        session_factory, driver["driver_id"], starts_at=now - MONTH / 2,
        amount_paid="30.000",
    )
    await _subscription(
        session_factory, driver["driver_id"], starts_at=now + MONTH / 2,
        amount_paid="30.000",
    )
    before = await _balance(session_factory, driver["user_id"])

    rows = (await client.get("/admin/subscriptions", headers=admin_headers)).json()
    assert len(rows) == 2

    preview = (
        await client.get(
            f"/admin/subscriptions/{rows[0]['id']}/cancellation-preview",
            headers=admin_headers,
        )
    ).json()
    assert preview["cancelled_count"] == 2, preview
    # **القادمُ كاملاً بلا تناسب**: صفٌّ لم يبدأ ⇒ `started=false` وردُّه كلُّ
    # ما دُفع
    future = [line for line in preview["lines"] if not line["started"]]
    assert len(future) == 1
    assert Decimal(future[0]["refund"]) == Decimal("30.000")

    done = await client.post(
        f"/admin/subscriptions/{rows[0]['id']}/cancel",
        json={"reason": "إيقافٌ بطلبه"},
        headers=admin_headers,
    )
    assert done.status_code == 200, done.text
    assert done.json()["cancelled_count"] == 2

    after = await _balance(session_factory, driver["user_id"])
    assert after - before == Decimal(done.json()["total_refund"])

    async with session_factory() as session:
        states = list(await session.scalars(select(DriverSubscription.status)))
        assert states == [SubscriptionStatus.CANCELLED] * 2


# ═════════════════════════ الشهرُ المجانيّ — لا مدفوعَ فلا قيد


async def test_a_free_month_refunds_nothing_and_writes_no_ledger_entry(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**عرضُ الشهر المجاني `money_percent 100`** (§27.5) ⇒ `amount_paid` صفر.

    **فالردُّ صفرٌ ولا قيدَ يُكتب** — وقيدٌ بصفرٍ ضجيجٌ في كشفٍ ماليّ، **ولا
    يُقرأ «رُدَّ له مال»**. والصفُّ يبقى `refund_transaction_id = NULL`، ومعناها
    «لا قيد» لا «لم يُردّ شيء».
    """
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    await _subscription(
        session_factory,
        driver["driver_id"],
        starts_at=datetime.now(UTC) - MONTH / 3,
        amount_paid="0.000",
    )
    before = await _balance(session_factory, driver["user_id"])

    rows = (await client.get("/admin/subscriptions", headers=admin_headers)).json()
    done = await client.post(
        f"/admin/subscriptions/{rows[0]['id']}/cancel",
        json={"reason": "إيقافُ اشتراكٍ مجانيّ"},
        headers=admin_headers,
    )
    assert done.status_code == 200, done.text
    assert Decimal(done.json()["total_refund"]) == Decimal("0.000")

    assert await _balance(session_factory, driver["user_id"]) == before
    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count(WalletTransaction.id)).where(
                    WalletTransaction.type == WalletTransactionType.REFUND
                )
            )
        ) == 0
        row = await session.scalar(select(DriverSubscription))
        assert row.status is SubscriptionStatus.CANCELLED
        assert row.refund_transaction_id is None


# ═════════════════════════ الأبوابُ ترفض ما يجب أن ترفضه


async def test_a_reason_is_required_and_support_may_not_cancel(
    client: AsyncClient, session_factory, admin_headers: dict, support_headers: dict
) -> None:
    """**السببُ إلزاميّ، والقرارُ لـ`admin` وحدَه** — مالٌ يخرج لا إجراءُ دعم."""
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    await _subscription(
        session_factory, driver["driver_id"],
        starts_at=datetime.now(UTC) - MONTH / 4, amount_paid="30.000",
    )
    rows = (await client.get("/admin/subscriptions", headers=admin_headers)).json()
    path = f"/admin/subscriptions/{rows[0]['id']}/cancel"

    assert (
        await client.post(path, json={"reason": "  "}, headers=admin_headers)
    ).status_code == 422
    assert (
        await client.post(path, json={"reason": "سببٌ كافٍ"}, headers=support_headers)
    ).status_code == 403


async def test_cancelling_twice_refuses_instead_of_refunding_again(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**ولا يُقرأ «أُلغي» عن لا شيء**: الثانيةُ ترتدّ ٤٠٩ بلا قيدٍ ثانٍ."""
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    await _subscription(
        session_factory, driver["driver_id"],
        starts_at=datetime.now(UTC) - MONTH / 2, amount_paid="30.000",
    )
    rows = (await client.get("/admin/subscriptions", headers=admin_headers)).json()
    path = f"/admin/subscriptions/{rows[0]['id']}/cancel"

    first = await client.post(path, json={"reason": "إيقاف"}, headers=admin_headers)
    assert first.status_code == 200, first.text
    after_first = await _balance(session_factory, driver["user_id"])

    second = await client.post(path, json={"reason": "إيقاف"}, headers=admin_headers)
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "no_subscription_to_cancel"
    assert await _balance(session_factory, driver["user_id"]) == after_first


# ═════════════════════════ أهليةُ السلفة — والملغى لا يؤهِّل


async def test_a_cancelled_subscription_does_not_qualify_for_an_advance(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**قرارُ المالك 2026-09-02**: «من رددنا له مالَه لم يشترِ دورةَ عمل».

    **والقياسُ بالنقض**: اشتراكٌ أُلغي **ومرّ تاريخُ انتهائه الأصليّ** ⇒ غيرُ
    مؤهَّل. **وبلا الاستثناء في `_has_qualifying_subscription` يخضرّ الشرطُ
    محقّاً في القديم** — لأن الدالّة تقرأ الساعةَ ولا تقرأ الحالة.

    **ولا يُقاس بالباب**: الأهليةُ شروطٌ ستّة، وسقوطُ الطلب قد يكون لأيٍّ منها
    — فيُسأل الشرطُ نفسُه بالاسم، وإلا صار الاختبارُ يمرّ لسببٍ آخر.
    """
    from app.services.advances import _has_qualifying_subscription

    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    # **اشتراكٌ انقضى فعلاً** — يؤهِّل قبل الإلغاء
    await _subscription(
        session_factory, driver["driver_id"],
        starts_at=datetime.now(UTC) - MONTH * 3, amount_paid="30.000",
    )
    async with session_factory() as session:
        assert await _has_qualifying_subscription(session, driver["driver_id"]) is True

    # **ثمّ يُعلَّم ملغى** — كما يعلّمه بابُ الإلغاء
    async with session_factory() as session:
        row = await session.scalar(select(DriverSubscription))
        row.status = SubscriptionStatus.CANCELLED
        await session.commit()

    async with session_factory() as session:
        assert await _has_qualifying_subscription(session, driver["driver_id"]) is False


# ═════════════════════════ التزامن — والثابتُ أن المالَ يعود مرّةً


async def test_two_cancellations_at_once_refund_once(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**إلغاءان متزامنان ⇒ ردٌّ واحد** (قاعدةُ «مرحلةٌ تمسّ مالاً بلا اختبار
    تزامنٍ ليست منتهية»).

    **وحارسان لا واحد، ولكلٍّ ما يملكه**: `_locked_driver` يملك **حالَ الصفّ**
    فيمنع إلغاءين يقرآن «ساري» معاً، ومفتاحُ التكرار
    `subscription_refund:{id}` يملك **المال** فيمنع قيدين. **والثابتُ يُقاس
    على الدفتر لا على الرمز**: مجموعُ قيود الردّ **قيدٌ واحد**، والخاسرُ يرتدّ
    برمزه المسمّى لا بخطأٍ عامّ.

    **ويُطلق الطلبان على حلقة الأحداث نفسِها** بجلستين ومعاملتين، فينتظر
    أحدهما قفلَ الآخر في القاعدة فعلاً — ولا يُقاس التوقيت.
    """
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    await _subscription(
        session_factory, driver["driver_id"],
        starts_at=datetime.now(UTC) - MONTH / 2, amount_paid="30.000",
    )
    before = await _balance(session_factory, driver["user_id"])
    rows = (await client.get("/admin/subscriptions", headers=admin_headers)).json()
    path = f"/admin/subscriptions/{rows[0]['id']}/cancel"

    # **يصيح بالاستثناء أوّلاً** — عدٌّ يصفّي ما لا يفهمه يسمّي العطبَ باسم غيره
    results = await asyncio.wait_for(
        asyncio.gather(
            client.post(path, json={"reason": "إيقافٌ متزامن"}, headers=admin_headers),
            client.post(path, json={"reason": "إيقافٌ متزامن"}, headers=admin_headers),
            return_exceptions=True,
        ),
        timeout=30,
    )
    for result in results:
        if isinstance(result, BaseException):
            raise result

    codes = Counter(response.status_code for response in results)
    assert codes == Counter({200: 1, 409: 1}), codes
    loser = next(r for r in results if r.status_code == 409)
    assert loser.json()["code"] == "no_subscription_to_cancel"

    async with session_factory() as session:
        entries = await session.scalar(
            select(func.count(WalletTransaction.id)).where(
                WalletTransaction.owner_id == driver["user_id"],
                WalletTransaction.type == WalletTransactionType.REFUND,
            )
        )
        assert entries == 1, entries
        # **والرصيدُ ارتفع بمقدارِ ردٍّ واحد** — لا ضعفَه
        assert await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == driver["user_id"],
                WalletTransaction.owner_type == WalletOwnerType.DRIVER,
            )
        ) - before == Decimal(
            next(r for r in results if r.status_code == 200).json()["total_refund"]
        )
