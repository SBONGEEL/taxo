"""مهمّتا الصيانة (المرحلة 12): تقليمُ الصندوق وكنسُ الطلبات المعلّقة.

**وأهمُّ ما يُختبر هنا نفيٌ لا إثبات**: أن الكنسَ **لا يكتب حالةً نهائيةً لم
يقلها المزود**. `apply_state` في القناتين يرفض ما ليس `created`، فحالةٌ محليةٌ
مخترَعةٌ تجعل إشعارَ المزود المتأخّرَ يُهمَل بصمت — بطاقةٌ خُصمت ومحفظةٌ لم
تُشحن. فاختبارٌ يتأكّد أن الطلبَ المعلّقَ **يبقى معلّقاً** حين يقول المزودُ
«معلّق» هو الاختبارُ الذي يحرس المال، لا الذي يتأكّد من الحذف.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.models.enums import PaymentStatus, ProviderOrderStatus
from app.models.notification import UserNotification
from app.models.payment import Payment
from app.models.provider_order import ProviderOrder
from app.services import inbox, order_maintenance
from tests.helpers import (
    approved_driver,
    bring_online,
    completed_ride,
    enable_card_provider,
    enable_features,
    rider_session,
)


async def _age_order(session_factory, cart_id: str, *, minutes: int) -> None:
    """يُقدّم عمرَ الطلب — الزمنُ هو مدخلُ هذه المهمة، فيُزوَّر لا يُنتظر."""
    async with session_factory() as session:
        await session.execute(
            update(ProviderOrder)
            .where(ProviderOrder.cart_id == cart_id)
            .values(created_at=datetime.now(UTC) - timedelta(minutes=minutes))
        )
        await session.commit()


async def _order_of(session_factory, cart_id: str) -> ProviderOrder:
    async with session_factory() as session:
        row = await session.scalar(
            select(ProviderOrder).where(ProviderOrder.cart_id == cart_id)
        )
        assert row is not None
        return row


async def _card_ride_order(
    client: AsyncClient, session_factory, admin_headers: dict
) -> tuple[dict, str]:
    """رحلةٌ منتهيةٌ وطلبُ دفعٍ ببطاقةٍ مفتوحٌ عليها."""
    await enable_features(session_factory, "card_enabled")
    await enable_card_provider(session_factory)

    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await completed_ride(client, rider["headers"], driver)

    response = await client.post(
        f"/rides/{ride['id']}/payments",
        json={
            "method": "card",
            "amount": ride["final_fare"],
            "idempotency_key": f"card:{ride['id']}",
        },
        headers=rider["headers"],
    )
    assert response.status_code == 201, response.text
    order = await _order_of(session_factory, response.json()["card_order"]["cart_id"])
    return rider, order.cart_id


# ------------------------------------------------- كنسُ الطلبات المعلّقة


async def test_a_pending_order_the_provider_still_calls_open_stays_open(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings
):
    """**القاعدةُ التي تحرس المال**: لا حالةَ نهائيةً لم يقلها المزود.

    ولو كتب الكنسُ `cancelled` هنا لرفض `apply_state` كلَّ إشعارٍ لاحق — فبطاقةٌ
    خُصمت بعد دقيقةٍ من الكنس تصير مالاً لا يجد صفَّه. والمزودُ الوهميُّ هنا لم
    يُحسم بعد، فهو حالُ راكبٍ تركَ الصفحةَ مفتوحة.
    """
    _rider, cart_id = await _card_ride_order(client, session_factory, admin_headers)
    await _age_order(session_factory, cart_id, minutes=45)

    async with session_factory() as session:
        tally = await order_maintenance.sweep(session)

    order = await _order_of(session_factory, cart_id)
    assert order.status is ProviderOrderStatus.CREATED, tally
    assert tally["open"] == 1
    assert tally["dropped"] == 0

    # والدفعةُ ما زالت `pending` — لم يُلمس شيء
    async with session_factory() as session:
        payment = await session.get(Payment, order.payment_id)
    assert payment.status is PaymentStatus.PENDING


async def test_the_sweep_applies_the_answer_the_provider_gives(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings
):
    """ومن حسمه المزودُ يُسوّى بجوابه — الكنسُ بابُ سؤالٍ لا بابُ حكم."""
    rider, cart_id = await _card_ride_order(client, session_factory, admin_headers)

    # **حالُ المزود تُضبط مباشرةً لا عبر `/payments/card/mock/…`**: ذاك المسار
    # يضبطها **ثم يسوّي بنفسه**، فيصير الطلبُ محسوماً قبل أن يمرّ الكنسُ — ولا
    # يبقى في الاختبار ما يُختبر. فتُضبط الحالةُ عند المزود ويُترك الاكتشافُ
    # للكنس، كما يفعل `test_stage8_concurrency.py` مع مزوّد كليك
    from app.core.redis_client import get_redis_client
    from app.services.card_gateway.mock import MockCardGateway

    await MockCardGateway(get_redis_client()).set_outcome(cart_id, "declined")
    await _age_order(session_factory, cart_id, minutes=45)

    async with session_factory() as session:
        tally = await order_maintenance.sweep(session)

    order = await _order_of(session_factory, cart_id)
    assert order.status is ProviderOrderStatus.FAILED, tally
    assert tally["settled"] == 1

    # **وتحريرُ الدفعة هو الغرضُ كلُّه**: `pending` تحجز أجرةَ الرحلة فلا
    # يستطيع صاحبُها الدفعَ بقناةٍ أخرى (نصُّ `_mark_failed`)
    async with session_factory() as session:
        payment = await session.get(Payment, order.payment_id)
    assert payment.status is PaymentStatus.FAILED

    owed = await client.get(f"/rides/{order.ride_id}/payments", headers=rider["headers"])
    assert Decimal(owed.json()["outstanding"]) > 0


async def test_an_order_that_never_reached_the_provider_is_dropped_with_its_payment(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings
):
    """ما لا مرجعَ له لم يصل المزودَ، فلا مالَ يمكن أن يكون تحرّك — ويُسقط.

    وهذه هي الحالةُ التي تحبس الراكب: دفعةٌ `pending` على طلبٍ ميتٍ تجعل رحلتَه
    تُقرأ مدفوعةً، فلا هو دفع ولا يستطيع أن يدفع.
    """
    rider, cart_id = await _card_ride_order(client, session_factory, admin_headers)
    async with session_factory() as session:
        await session.execute(
            update(ProviderOrder)
            .where(ProviderOrder.cart_id == cart_id)
            .values(
                provider_order_ref=None,
                created_at=datetime.now(UTC) - timedelta(minutes=45),
            )
        )
        await session.commit()

    async with session_factory() as session:
        tally = await order_maintenance.sweep(session)

    order = await _order_of(session_factory, cart_id)
    assert order.status is ProviderOrderStatus.FAILED, tally
    assert order.failure_reason == "لم يُفتح لدى المزود"
    assert tally["dropped"] == 1

    async with session_factory() as session:
        payment = await session.get(Payment, order.payment_id)
    assert payment.status is PaymentStatus.FAILED

    # ويستطيع الآن أن يدفع كاشاً — وهو المقصود
    again = await client.post(
        f"/rides/{order.ride_id}/payments",
        json={
            "method": "cash",
            "amount": str(payment.amount),
            "idempotency_key": f"cash-after-sweep:{order.ride_id}",
        },
        headers=rider["headers"],
    )
    assert again.status_code == 201, again.text


async def test_a_young_unopened_order_is_left_alone(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings
):
    """**والمهلةُ نصفُ ساعةٍ لا دقائق**: نداءُ فتحٍ انقطع بعد أن أنشأ المزودُ
    طلبَه يترك مرجعَنا فارغاً وطلبَه حيّاً، وإشعارُه يصل في ثوانٍ. فإسقاطٌ
    فوريٌّ يجعل ذلك المالَ يضيع، والانتظارُ يجعله يجد صفَّه.
    """
    _rider, cart_id = await _card_ride_order(client, session_factory, admin_headers)
    async with session_factory() as session:
        await session.execute(
            update(ProviderOrder)
            .where(ProviderOrder.cart_id == cart_id)
            .values(
                provider_order_ref=None,
                # أقدمُ من مهلة السؤال وأحدثُ من مهلة الإسقاط
                created_at=datetime.now(UTC) - timedelta(minutes=25),
            )
        )
        await session.commit()

    async with session_factory() as session:
        tally = await order_maintenance.sweep(session)

    order = await _order_of(session_factory, cart_id)
    assert order.status is ProviderOrderStatus.CREATED, tally
    assert tally["open"] == 1


async def test_a_fresh_order_is_not_asked_about(
    client: AsyncClient, session_factory, admin_headers: dict, jordan_settings
):
    """طلبٌ عمرُه دقيقتان يعني عميلاً على الصفحة — وسؤالُ المزود عنه نداءٌ يُهدر."""
    _rider, cart_id = await _card_ride_order(client, session_factory, admin_headers)

    async with session_factory() as session:
        stale = await order_maintenance.stale_orders(session)
    assert stale == []


# ------------------------------------------------- تقليمُ صندوق الوارد


async def _seed_notification(session_factory, user_id: str, *, days_old: int) -> None:
    async with session_factory() as session:
        row = UserNotification(
            user_id=uuid.UUID(user_id),
            kind="ride_completed",
            title="اكتملت رحلتك",
            body="شكراً لاستخدامك تاكسو",
            data={"type": "ride_completed"},
        )
        session.add(row)
        await session.flush()
        await session.execute(
            update(UserNotification)
            .where(UserNotification.id == row.id)
            .values(created_at=datetime.now(UTC) - timedelta(days=days_old))
        )
        await session.commit()


async def test_the_trim_removes_what_passed_the_retention_and_keeps_the_rest(
    client: AsyncClient, session_factory
):
    """التقليمُ بالعمر وحده — والحدُّ ثابتٌ في الخدمة لا إعدادٌ في اللوحة."""
    rider = await rider_session(client)
    user_id = rider["user"]["id"]
    await _seed_notification(session_factory, user_id, days_old=120)
    await _seed_notification(session_factory, user_id, days_old=91)
    await _seed_notification(session_factory, user_id, days_old=10)

    async with session_factory() as session:
        removed = await inbox.trim(session)
        await session.commit()
        remaining = await session.scalar(
            select(func.count()).select_from(UserNotification)
        )
    assert removed == 2
    assert remaining == 1


async def test_the_trim_deletes_unread_rows_too(
    client: AsyncClient, session_factory
):
    """**والمقروءُ وغيرُه معاً** — قرارٌ لا سهو.

    إشعارٌ لم يُقرأ بعد تسعين يوماً لن يُقرأ، والصندوقُ أثرُ الحدث لا مصدرُه:
    الرحلةُ ودفعتُها وقيدُ الدفتر تحمل الحقيقةَ ولا تُحذف. وإبقاءُ غير المقروء
    إلى الأبد يجعل الجدولَ ينمو بمن لا يفتح تطبيقَه.
    """
    rider = await rider_session(client)
    await _seed_notification(session_factory, rider["user"]["id"], days_old=200)

    unread = await client.get("/me/notifications/unread-count", headers=rider["headers"])
    assert unread.json()["unread"] == 1

    async with session_factory() as session:
        assert await inbox.trim(session) == 1
        await session.commit()

    after = await client.get("/me/notifications/unread-count", headers=rider["headers"])
    assert after.json()["unread"] == 0


async def test_the_trim_is_capped_per_cycle(client: AsyncClient, session_factory):
    """الحذفُ على دفعاتٍ: جدولٌ متراكمٌ من شهورٍ لا يُحذف في معاملةٍ واحدة."""
    rider = await rider_session(client)
    for _ in range(3):
        await _seed_notification(session_factory, rider["user"]["id"], days_old=100)

    async with session_factory() as session:
        first = await inbox.trim(session, limit=2)
        await session.commit()
        second = await inbox.trim(session, limit=2)
        await session.commit()
    assert (first, second) == (2, 1)
