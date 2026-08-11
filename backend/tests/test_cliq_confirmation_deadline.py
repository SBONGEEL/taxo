"""مهلةُ تأكيد حوالة كليك (SPEC القسم 6.2/6 — المرحلة 10).

«عند الرفض أو **انقضاء مهلة التأكيد** → `disputed`». الرفضُ مختبَرٌ في
`test_cliq_ride_payment.py`، وهذا الملف للانقضاء: أنه يقع، وأنه **يُجمَّد**
لحظة إدخال المرجع فلا يتحرك بتعديل الإعداد، وأنه لا يسبق كبتناً تكلّم.

**والتزامنُ هنا يملك ثابتاً بعينه**: أن الدفعة لا تصير نزاعاً ومالُها مُقيَّد.
الكنسُ يقرأ `pending` والكبتنُ يؤكّد في اللحظة نفسها — بلا قفلٍ يمرّان معاً،
فتُنازَع دفعةٌ وصل مالُها وكُتب قيدُ أرباحها. والتداخلُ مُرتَّبٌ عمداً كما في
`test_driver_documents_concurrency.py`: الأول يكتب ولا يُثبّت، والثاني يبدأ
وهو مفتوح — لا طلبان على HTTP يُرجى أن تُرتّبهما جدولةُ الحلقة.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import PaymentStatus, WalletTransactionType
from app.models.payment import Payment
from app.models.payment_setting import PaymentSetting
from app.models.wallet import WalletTransaction
from app.services import payments as payments_service
from tests.helpers import (
    DRIVER,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    enable_features,
    pay_ride,
    register,
    set_cliq_alias,
)

DEADLOCK_TIMEOUT = 20
DRIVER_ALIAS = "0799999999"
TRANSFER_REFERENCE = "FT24081012345678"


async def _cliq_payment(client: AsyncClient, session_factory) -> tuple[dict, dict, str]:
    """راكبٌ وكبتنٌ ودفعةُ كليك أدخل الراكب مرجعها فبدأت مهلتها."""
    await enable_features(session_factory, "cliq_enabled")
    body = await register(client, RIDER)
    rider = {"headers": auth(body)}
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)
    await set_cliq_alias(session_factory, driver["driver_id"], DRIVER_ALIAS)

    paid = (await pay_ride(client, rider["headers"], ride["id"], "cliq")).json()
    payment_id = paid["payments"][0]["id"]
    response = await client.post(
        f"/payments/{payment_id}/cliq-reference",
        json={"transfer_reference": TRANSFER_REFERENCE},
        headers=rider["headers"],
    )
    assert response.status_code == 200, response.text
    return rider, driver, payment_id


async def _age_deadline(session_factory, payment_id: str) -> None:
    """يُقدّم الموعد إلى الماضي — أرخصُ من انتظار أربعٍ وعشرين ساعة."""
    async with session_factory() as session:
        payment = await session.get(Payment, uuid.UUID(payment_id))
        payment.cliq_confirmation_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()


async def test_deadline_is_frozen_from_the_country_setting(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """المهلة تُكتب مع المرجع من إعداد الدولة، **ولا تتحرك بعده**.

    تعديلُ الإعداد لاحقاً يحكم ما يأتي بعده لا ما هو معلّق: كبتنٌ رأى «يبقى
    ست ساعات» لا يجوز أن تصير أمامه ساعةً لأن مشرفاً غيّر رقماً.
    """
    _rider, _driver, payment_id = await _cliq_payment(client, session_factory)

    async with session_factory() as session:
        payment = await session.get(Payment, uuid.UUID(payment_id))
        assert payment.cliq_reference_at is not None
        frozen = payment.cliq_confirmation_expires_at
        assert frozen is not None
        setting = await session.scalar(select(PaymentSetting))
        assert frozen - payment.cliq_reference_at == timedelta(
            hours=setting.cliq_confirmation_hours
        )

        setting.cliq_confirmation_hours = 1
        await session.commit()

    async with session_factory() as session:
        payment = await session.get(Payment, uuid.UUID(payment_id))
        assert payment.cliq_confirmation_expires_at == frozen


async def test_sweep_disputes_only_what_expired(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """دفعةٌ مهلتها قائمة لا تُمَسّ، والتي انقضت تصير نزاعاً بسببٍ مميَّز."""
    _rider, _driver, payment_id = await _cliq_payment(client, session_factory)

    async with session_factory() as session:
        assert await payments_service.expired_cliq_payment_ids(session) == []

    await _age_deadline(session_factory, payment_id)

    async with session_factory() as session:
        due = await payments_service.expired_cliq_payment_ids(session)
        assert due == [uuid.UUID(payment_id)]
        payment = await payments_service.expire_cliq_confirmation(session, due[0])
        await session.commit()
        assert payment.status is PaymentStatus.DISPUTED
        assert payment.dispute_reason == payments_service.AUTO_DISPUTE_REASON

    # ولا يتكرر: الصفُّ خرج من `pending` فلا يعود الاستعلام يراه
    async with session_factory() as session:
        assert await payments_service.expired_cliq_payment_ids(session) == []


async def test_confirmed_payment_is_never_swept(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """كبتنٌ أكّد قبل الانقضاء — والكنسُ يمر عليه ولا يقلب تأكيده نزاعاً."""
    _rider, driver, payment_id = await _cliq_payment(client, session_factory)

    confirmed = await client.post(
        f"/payments/{payment_id}/confirm", headers=driver["headers"]
    )
    assert confirmed.status_code == 200, confirmed.text

    await _age_deadline_even_if_confirmed(session_factory, payment_id)

    async with session_factory() as session:
        assert await payments_service.expired_cliq_payment_ids(session) == []
        # وحتى لو نُودي على الخدمة بمعرّفه مباشرةً، ترفض ولا تكتب
        assert (
            await payments_service.expire_cliq_confirmation(
                session, uuid.UUID(payment_id)
            )
            is None
        )


async def _age_deadline_even_if_confirmed(session_factory, payment_id: str) -> None:
    async with session_factory() as session:
        payment = await session.get(Payment, uuid.UUID(payment_id))
        payment.cliq_confirmation_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()


async def test_confirm_and_sweep_at_once_leave_a_coherent_payment(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """تأكيدٌ وكنسٌ في آنٍ واحد — والصفُّ يخرج بحالٍ واحدة يوافقها الدفتر.

    **هذا ما يملكه القفل**: بحذف `for_update=True` من `expire_cliq_confirmation`
    يقرأ الكنسُ `pending` بينما التأكيد مفتوحٌ في معاملته، فتصير الدفعة
    `disputed` **وقد كُتب قيدُ أرباحها** — نزاعٌ على مالٍ قُيّد فعلاً، وهو
    أسوأ ما يمكن أن ينتجه هذا المسار.
    """
    _rider, driver, payment_id = await _cliq_payment(client, session_factory)
    await _age_deadline(session_factory, payment_id)

    outcomes: list[str] = []

    async def _sweep_holding_the_transaction() -> None:
        async with session_factory() as session:
            result = await payments_service.expire_cliq_confirmation(
                session, uuid.UUID(payment_id)
            )
            await asyncio.sleep(0.3)
            await session.commit()
            outcomes.append("swept" if result is not None else "sweep-skipped")

    async def _confirm_meanwhile() -> None:
        await asyncio.sleep(0.05)
        response = await client.post(
            f"/payments/{payment_id}/confirm", headers=driver["headers"]
        )
        outcomes.append(
            "confirmed" if response.status_code == 200 else "confirm-refused"
        )

    await asyncio.wait_for(
        asyncio.gather(_sweep_holding_the_transaction(), _confirm_meanwhile()),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert sorted(outcomes) == ["confirm-refused", "swept"]

    async with session_factory() as session:
        payment = await session.get(Payment, uuid.UUID(payment_id))
        assert payment.status is PaymentStatus.DISPUTED
        # الثابت: نزاعٌ ⇔ لا قيدَ أرباحٍ لهذه الرحلة
        earnings = await session.scalar(
            select(func.count())
            .select_from(WalletTransaction)
            .where(
                WalletTransaction.ride_id == payment.ride_id,
                WalletTransaction.type == WalletTransactionType.RIDE_EARNING,
            )
        )
        assert earnings == 0
