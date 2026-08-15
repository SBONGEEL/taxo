"""تزامنُ تحصيل رسوم الإلغاء — **الثابتُ الذي يملكه القفل، لا ما يحرسه غيرُه**.

قاعدةُ المشروع: مرحلةٌ تمسّ المال ليست منتهيةً بلا اختبار تزامن، ويُكتب
الاختبارُ للثابت الذي يملكه القفلُ نفسُه.

**وما يملكه هذا القفلُ ليس «صفَّين لرحلة»** — تلك يملكها `uq_cancellation_charge_ride`
في القاعدة — بل **رصيدٌ يُقرأ مرتين**: راكبٌ عليه رسمان ورصيدُه يكفي واحداً،
فيُحصَّلان في اللحظة نفسِها.

**والحذفُ يُنتج شيئين، أحدُهما أسوأُ من الآخر**: بترتيبٍ خاطئ (قراءةُ الرصيد
قبل القفل) يمرّ النداءان معاً على الرقم نفسِه، ثم يرمي `wallet.record` عند
الثاني `InsufficientBalance` — **داخل مسار الإلغاء**، فيرتدّ إلغاءُ راكبٍ ضغط
«ألغِ» ورأى رحلتَه تُلغى. أي أن العطبَ لا يظهر في المال بل في **رحلةٍ لم
تُلغَ**، وهو ما لا يخطر لمن يقرأ اسمَ الاستثناء.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.cancellation import RideCancellationCharge
from app.models.enums import CancellationChargeStatus, WalletTransactionType
from app.models.wallet import WalletTransaction
from app.services import cancellation
from tests.helpers import (
    DRIVER,
    SECOND_DRIVER,
    accepted_ride,
    approved_driver,
    bring_online,
    broadcast_location,
    rider_session,
    topup_wallet,
)

DEADLOCK_TIMEOUT = 20
FAR_AWAY = {"lat": 32.0060, "lng": 35.9106}


async def _collect(
    session_factory, charge_id: uuid.UUID, *, delay: float, hold: float = 0.0
) -> bool:
    """نداءٌ واحدٌ في جلسةٍ ومعاملةٍ خاصّتين — لا نداءان في جلسةٍ واحدة.

    **و`hold` هو ما يجعل الاختبارَ يملك ثابتَه**: الأولُ يحمل معاملتَه مفتوحةً
    بينما يبدأ الثاني، فيلتقي النداءان فعلاً على الرصيد نفسِه. وبدونه ينتهي
    الأولُ ويُودِع قبل أن يقرأ الثاني، فيمرّ الاختبارُ **بأيِّ ترتيبٍ للقفل** —
    وهو ما قِيس هنا حرفياً قبل أن يُكتب هذا السطر (الفخُّ نفسُه الذي وقع في
    اختبار الإحالة 12-ح، وحُلَّ بالتأخير الصريح لا بحدث `asyncio`).
    """
    await asyncio.sleep(delay)
    async with session_factory() as session:
        charge = await session.get(RideCancellationCharge, charge_id)
        settled = await cancellation.try_collect(session, charge)
        if hold:
            await asyncio.sleep(hold)
        await session.commit()
        return settled


async def test_two_debts_on_a_balance_that_covers_one_settle_exactly_one(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """واحدٌ يُسدَّد والآخر يبقى ديناً — **والدفترُ يوافق، ولا رصيدَ سالب**."""
    rider = await rider_session(client)

    charges: list[uuid.UUID] = []
    for driver_payload, plate in ((DRIVER, "AMM-4242"), (SECOND_DRIVER, "AMM-5353")):
        driver = await approved_driver(
            client, session_factory, driver_payload, plate_number=plate
        )
        await bring_online(client, driver)
        ride = await accepted_ride(client, rider["headers"], driver)
        await broadcast_location(client, driver, **FAR_AWAY)
        cancelled = await client.post(
            f"/rides/{ride['id']}/cancel",
            json={"reason": "غيّرت رأيي"},
            headers=rider["headers"],
        )
        assert cancelled.status_code == 200, cancelled.text

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(RideCancellationCharge).where(
                    RideCancellationCharge.payer_user_id
                    == uuid.UUID(rider["user"]["id"])
                )
            )
        ).all()
    assert len(rows) == 2
    fee = rows[0].amount
    charges = [row.id for row in rows]
    assert all(row.status is CancellationChargeStatus.PENDING for row in rows)

    # رصيدٌ يكفي رسماً واحداً وينقص عن الاثنين
    await topup_wallet(
        client, admin_headers, rider["user"]["id"], str(fee + Decimal("0.100"))
    )

    # **تأخيرٌ صريحٌ لا تزامنٌ يعتمد على جدولة الحلقة**: الأول يحمل معاملتَه
    # مفتوحةً والثاني يبدأ بعده — شكلُ المرحلة الثامنة نفسُه
    results = await asyncio.wait_for(
        asyncio.gather(
            _collect(session_factory, charges[0], delay=0, hold=0.4),
            _collect(session_factory, charges[1], delay=0.1),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )
    assert sorted(results) == [False, True]

    async with session_factory() as session:
        settled = await session.scalar(
            select(func.count()).where(
                RideCancellationCharge.id.in_(charges),
                RideCancellationCharge.status == CancellationChargeStatus.SETTLED,
            )
        )
        credited = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.type
                == WalletTransactionType.CANCELLATION_COMPENSATION
            )
        )
        lowest = await session.scalar(
            select(func.min(WalletTransaction.balance_after))
        )

    assert settled == 1
    assert Decimal(credited) == fee
    assert Decimal(lowest) >= 0
