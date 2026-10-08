"""تزامنُ المدفوعات غير المؤكَّدة — **قفلٌ لكلِّ تغيير حالٍ جديد، وكلُّ اختبارٍ هنا يسقط بحذف قفله** (SPEC §٦٤-ج، `CLAUDE.md`).

**التداخلُ مُرتَّبٌ عمداً لا متروكٌ للحظ** (نمطُ `test_stage8_concurrency.py`): طرفٌ يقفل الصفَّ ويكتب ويُمسك معاملتَه مفتوحةً
(`asyncio.sleep`)، والطرفُ الآخر يبدأ وهي مفتوحة — **من بابه الحقيقيّ على عميل الاختبار** حيث للباب باب. بالقفل ينتظر الثاني
فيرى ما كتبه الأوّلُ ويُردّ برمزه بعينه؛ **وبغيره يقرأ الحالَ القديمةَ فيكتب فوق ما حُسم** — وهو ما يُثبَت بحذف القفل.

**والحكمُ على الثابت لا على التوقيت**: انتقالٌ واحدٌ نجح، ورمزُ الخاسر بعينه، ومقروءاً من القاعدة مباشرة.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.notification import UserNotification
from app.models.payment import Payment
from app.models.ride import Ride
from app.services import payments as payments_service
from app.services import unconfirmed_payments as service
from tests.helpers import enable_features, set_cliq_alias, set_commission
from tests.test_payments import _online_driver, _rider
from tests.test_unconfirmed_payments import FLAG, AUTO_FLAG, completed_with, rows_of

pytestmark = pytest.mark.asyncio

#: مدّةُ إمساك المعاملة الأولى، وتأخُّرُ الثانية عنها — ومهلةُ الجمود
HOLD = 0.4
LAG = 0.05
DEADLOCK_TIMEOUT = 15


async def _pending_cash(client: AsyncClient, session_factory) -> tuple[dict, dict, Payment]:
    await enable_features(session_factory, FLAG)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    _requested, ride = await completed_with(client, rider["headers"], driver, "cash")
    payment = (await rows_of(session_factory, ride["id"]))[0]
    return rider, driver, payment


async def _captain_confirms_holding(session_factory, driver: dict, payment_id: uuid.UUID) -> None:
    """**«استلمت» من بابه القائم** (`confirm_by_driver` بقفل صفِّ الدفعة) — **ثمّ يُمسك المعاملةَ مفتوحة**."""
    async with session_factory() as session:
        captain = await session.get(Driver, driver["driver_id"])
        payment = await payments_service.get_payment(session, payment_id, for_update=True)
        await payments_service.confirm_by_driver(session, payment=payment, driver=captain)
        await asyncio.sleep(HOLD)
        await session.commit()


async def _row(session_factory, payment_id: uuid.UUID) -> Payment:
    async with session_factory() as session:
        return await session.get(Payment, payment_id)


async def _debts(session_factory, payment_id: uuid.UUID) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count(DriverDebt.id)).where(DriverDebt.payment_id == payment_id)
            )
        )


async def test_declare_while_the_captain_confirms_records_no_declaration_on_a_settled_payment(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**«سلّمتُ» و«استلمت» معاً** — بالقفل ينتظر الإقرارُ فيجد الدفعةَ مؤكَّدةً ويُردّ.

    بغير قفل `POST /payments/{id}/declare` يقرأ `pending` والتأكيدُ مفتوح، **فيُختم إقرارٌ بعد الحسم** ويُقال للراكب «بانتظار
    الكبتن» عن مالٍ حُسم — وهو ما يسقط به هذا الاختبار.
    """
    rider, driver, payment = await _pending_cash(client, session_factory)

    async def _declare_meanwhile():
        await asyncio.sleep(LAG)
        return await client.post(f"/payments/{payment.id}/declare", headers=rider["headers"])

    _held, declared = await asyncio.wait_for(
        asyncio.gather(
            _captain_confirms_holding(session_factory, driver, payment.id), _declare_meanwhile()
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert declared.status_code == 409, declared.text
    assert declared.json()["code"] == "invalid_payment_transition"
    final = await _row(session_factory, payment.id)
    assert (final.status.value, final.confirmed_by.value) == ("confirmed", "driver")
    assert final.declared_at is None


async def test_change_method_while_the_captain_confirms_never_voids_a_confirmed_payment(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**«غيّر طريقة الدفع» و«استلمت» معاً** — انتقالٌ واحدٌ ينجح، **ولا صفَّ جديدٌ يُفتح**.

    بغير قفل صفِّ الدفعة في `change_method` يقرأ `pending` فيكتب `voided` فوق دفعةٍ أكّدها الكبتنُ ودَينُ عمولتها قائم، **ويفتح
    دفعاً جديداً بالأجرة كاملة — فيدفع الراكبُ مرّتين**.

    **وبلا عمولة**: التأكيدُ لا يكتب شيئاً يشير إلى الرحلة، فلا يقف بين الطرفين إلا قفلُ صفِّ الدفعة — وهو ما يُقاس. والعمولةُ
    (ودَينُها الذي يأخذ على الرحلة `FOR KEY SHARE`) في اختبار الجمود أدناه.
    """
    rider, driver, payment = await _pending_cash(client, session_factory)
    # **الدفعُ الجديدُ ينجح لو مرّ** (كليك مشتعلٌ والكبتنُ له اسمٌ مستعار) — فسقوطُ الاختبار بلا القفل سقوطُ الثابت لا الإعداد
    await enable_features(session_factory, "cliq_enabled")
    await set_cliq_alias(session_factory, driver["driver_id"], "ZAID.JO")

    async def _change_meanwhile():
        await asyncio.sleep(LAG)
        return await client.post(
            f"/payments/{payment.id}/change-method",
            json={"method": "cliq", "idempotency_key": "race-change-0001"},
            headers=rider["headers"],
        )

    _held, changed = await asyncio.wait_for(
        asyncio.gather(
            _captain_confirms_holding(session_factory, driver, payment.id), _change_meanwhile()
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert changed.status_code == 409, changed.text
    assert changed.json()["code"] == "invalid_payment_transition"
    final = await _row(session_factory, payment.id)
    assert (final.status.value, final.confirmed_by.value, final.voided_at) == ("confirmed", "driver", None)
    assert len(await rows_of(session_factory, str(final.ride_id))) == 1


async def test_admin_resolve_while_the_captain_confirms_writes_one_ruling(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**«احسم: مدفوع» و«استلمت» معاً** — حكمٌ واحدٌ ودَينٌ واحد.

    بغير قفل الحسم يقرأ المشرفُ `pending` فيُسوّي ثانيةً فوق تسويةٍ مفتوحة — **حكمان لواقعةٍ واحدة**، ويسقط على قيد الدَّين
    الفريد أو يكتب `admin` فوق `driver`.
    """
    await set_commission(session_factory, "10")
    _rider_, driver, payment = await _pending_cash(client, session_factory)

    async def _resolve_meanwhile():
        await asyncio.sleep(LAG)
        return await client.post(
            f"/admin/payments/unconfirmed/{payment.id}/resolve",
            json={"outcome": "paid", "reason": "اتصلنا بالطرفين وتأكّدنا"},
            headers=admin_headers,
        )

    _held, resolved = await asyncio.wait_for(
        asyncio.gather(
            _captain_confirms_holding(session_factory, driver, payment.id), _resolve_meanwhile()
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert resolved.status_code == 409, resolved.text
    assert resolved.json()["code"] == "invalid_payment_transition"
    final = await _row(session_factory, payment.id)
    assert (final.confirmed_by.value, final.resolution) == ("driver", None)
    assert await _debts(session_factory, payment.id) == 1


async def test_auto_confirm_while_the_captain_confirms_leaves_the_humans_confirmation(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**القاعدةُ والكبتنُ معاً** — يبقى تأكيدُ الإنسان، ولا تُكتب «أتمّته القاعدة» فوقه.

    بغير قفل `auto_confirm_one` يقرأ `pending` فيكتب `auto_rule` ومعاييرَه فوق «استلمت» — **وتُفتح على الكبتن نافذةُ اعتراضٍ
    على مالٍ أكّده هو**.
    """
    rider, driver, payment = await _pending_cash(client, session_factory)
    await enable_features(session_factory, AUTO_FLAG)
    assert (await client.post(f"/payments/{payment.id}/declare", headers=rider["headers"])).status_code == 200
    async with session_factory() as session:
        await session.execute(
            update(Payment)
            .where(Payment.id == payment.id)
            .values(
                declared_at=Payment.declared_at - timedelta(hours=25),
                driver_reminders=4,
                # **الإنذارُ الأخيرُ في موعده بعد الإقرار** (+٢٣ س) ومضت ساعتُه — شرطُ الإتمام كاملاً
                driver_reminded_at=Payment.declared_at - timedelta(hours=2),
            )
        )
        await session.commit()

    async def _auto_meanwhile():
        await asyncio.sleep(LAG)
        async with session_factory() as session:
            outcome = await service.auto_confirm_one(session, payment.id)
            await session.commit()
            return outcome

    _held, outcome = await asyncio.wait_for(
        asyncio.gather(
            _captain_confirms_holding(session_factory, driver, payment.id), _auto_meanwhile()
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert outcome is None
    final = await _row(session_factory, payment.id)
    assert (final.confirmed_by.value, final.auto_confirm_criteria) == ("driver", None)


async def test_two_reminder_sweeps_at_once_send_one_reminder(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**كنسان معاً ⇒ تذكيرٌ واحدٌ لكلِّ طرف**. بغير قفل `remind_one` يقرأ الثاني العددَ صفراً فيرسل الموعدَ نفسَه ثانيةً."""
    from app.core.redis_client import get_redis_client

    _rider_, _driver, payment = await _pending_cash(client, session_factory)
    async with session_factory() as session:
        ended = (await session.get(Ride, payment.ride_id)).completed_at
    moment = ended + timedelta(minutes=11)

    async def _sweep(lag: float, hold: float) -> int:
        await asyncio.sleep(lag)
        async with session_factory() as session:
            notices = await service.remind_one(session, payment.id, now=moment)
            await asyncio.sleep(hold)
            await session.commit()
            await service.send(session, get_redis_client(), notices)
            return len(notices)

    sent = await asyncio.wait_for(
        asyncio.gather(_sweep(0, HOLD), _sweep(LAG, 0)), timeout=DEADLOCK_TIMEOUT
    )

    assert sorted(sent) == [0, 2], sent
    async with session_factory() as session:
        delivered = int(
            await session.scalar(
                select(func.count(UserNotification.id)).where(
                    UserNotification.kind == service.REMINDER_KIND
                )
            )
        )
        row = await session.get(Payment, payment.id)
    assert delivered == 2
    assert (row.driver_reminders, row.rider_reminders) == (1, 1)


async def test_admin_dispute_while_the_captain_confirms_leaves_the_confirmation(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**«حوّل إلى نزاع» من الطابور و«استلمت» معاً** (مراجعةُ ٢٠٢٦-١٠-٠٧) — تأكيدٌ واحدٌ ودَينٌ واحدٌ ولا نزاعَ فوقه.

    بغير قفل `POST /admin/payments/unconfirmed/{id}/dispute` يقرأ المشرفُ `pending` فيكتب `disputed` وسببَه **فوق دفعةٍ أكّدها
    الكبتنُ ودَينُ عمولتها قائم** — فتصير مالاً مقيَّداً على دفعةٍ «في نزاع» يُحكم فيها ثانيةً.
    """
    await set_commission(session_factory, "10")
    _rider_, driver, payment = await _pending_cash(client, session_factory)

    async def _dispute_meanwhile():
        await asyncio.sleep(LAG)
        return await client.post(
            f"/admin/payments/unconfirmed/{payment.id}/dispute",
            json={"reason": "تعارض بين روايتي الطرفين"},
            headers=admin_headers,
        )

    _held, disputed = await asyncio.wait_for(
        asyncio.gather(
            _captain_confirms_holding(session_factory, driver, payment.id), _dispute_meanwhile()
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert disputed.status_code == 409, disputed.text
    assert disputed.json()["code"] == "invalid_payment_transition"
    final = await _row(session_factory, payment.id)
    assert (final.status.value, final.confirmed_by.value) == ("confirmed", "driver")
    assert (final.dispute_reason, final.disputed_at) == (None, None)
    assert await _debts(session_factory, payment.id) == 1


async def _auto_confirmed(client: AsyncClient, session_factory) -> tuple[dict, dict, Payment]:
    """كاشٌ أُتمّ آلياً بشروطه كلِّها — **ونافذةُ اعتراضه مفتوحة**."""
    rider, driver, payment = await _pending_cash(client, session_factory)
    await enable_features(session_factory, AUTO_FLAG)
    assert (await client.post(f"/payments/{payment.id}/declare", headers=rider["headers"])).status_code == 200
    async with session_factory() as session:
        await session.execute(
            update(Payment)
            .where(Payment.id == payment.id)
            .values(
                declared_at=Payment.declared_at - timedelta(hours=25),
                driver_reminders=4,
                driver_reminded_at=Payment.declared_at - timedelta(hours=2),
            )
        )
        await session.commit()
    async with session_factory() as session:
        assert await service.auto_confirm_one(session, payment.id) is not None
        await session.commit()
    return rider, driver, payment


async def test_two_objections_at_once_record_one_reason(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**«لم أستلم هذا المبلغ» مرّتين معاً** (مراجعةُ ٢٠٢٦-١٠-٠٧) — اعتراضٌ واحدٌ بسببه، والثاني يُردّ `conflict`.

    بغير قفل `POST /payments/{id}/object` يقرأ الثاني `objected_at` فارغاً والأوّلُ مفتوح، **فيكتب سببَه فوق سببٍ أُعلن** —
    والمشرفُ يحكم في اعتراضٍ غير الذي قُدِّم أوّلاً.
    """
    _rider_, driver, payment = await _auto_confirmed(client, session_factory)

    async def _object_holding() -> None:
        async with session_factory() as session:
            captain = await session.get(Driver, driver["driver_id"])
            locked = await payments_service.get_payment(session, payment.id, for_update=True)
            await service.object_auto_confirm(
                session, payment=locked, driver=captain, reason="الاعتراض الأول"
            )
            await asyncio.sleep(HOLD)
            await session.commit()

    async def _object_meanwhile():
        await asyncio.sleep(LAG)
        return await client.post(
            f"/payments/{payment.id}/object",
            json={"reason": "الاعتراض الثاني"},
            headers=driver["headers"],
        )

    _held, second = await asyncio.wait_for(
        asyncio.gather(_object_holding(), _object_meanwhile()), timeout=DEADLOCK_TIMEOUT
    )

    assert second.status_code == 409, second.text
    assert second.json()["code"] == "conflict"
    final = await _row(session_factory, payment.id)
    assert (final.status.value, final.objection_reason) == ("confirmed", "الاعتراض الأول")


async def test_pay_now_while_the_admin_rules_on_the_dispute_leaves_one_outcome(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, session_factory
) -> None:
    """**«سأدفع الآن» وحكمُ المشرف «مدفوع» معاً** على نزاع كاش (§٢-٣/§٦) — حكمٌ واحدٌ ولا إلغاءَ فوقه ولا دفعٌ ثانٍ.

    بغير قفل صفِّ الدفعة في `change_method` يقرأ الراكبُ `disputed` فيُلغي **دفعةً حكم المشرفُ أنها دُفعت** ودَينُ عمولتها
    قائم، ويفتح دفعاً جديداً بالأجرة كاملة — **فيدفعها مرّتين**.

    **وحكمُ «مدفوع» يأخذ على الرحلة `FOR KEY SHARE` من غير أن يطلبه** (تحديثان لصفِّ الدفعة في معاملةٍ واحدة — الثاني يفحص المفتاحَ
    الأجنبيّ): **ولو قفل التبديلُ الرحلةَ بـ`FOR UPDATE` لوقف عندها فمرّ هذا الاختبارُ بلا قفل الدفعة** (قِيس ٢٠٢٦-١٠-٠٧) — وبـ`FOR NO
    KEY UPDATE` لا يقف إلا عند صفِّ الدفعة، فيُقاس قفلُها.
    """
    from app.models.enums import DisputeResolution
    from app.models.user import User

    rider, driver, payment = await _pending_cash(client, session_factory)
    disputed = await client.post(
        f"/payments/{payment.id}/dispute", json={"reason": "لم يدفع"}, headers=driver["headers"]
    )
    assert disputed.status_code == 200, disputed.text

    # **الراكبُ يبدأ بعد أن يُمسك المشرفُ القفلَ لا بعد مهلةٍ ثابتة**: الحكمُ يقرأ أكثرَ قبل أن يقفل، ومهلةٌ ثابتةٌ قد تُطلق الراكبَ
    # قبله — فيُقاس ترتيبٌ آخرُ غيرُ المقصود
    holding = asyncio.Event()

    async def _admin_rules_holding() -> None:
        async with session_factory() as session:
            admin = await session.scalar(select(User).where(User.phone == "+962790000001"))
            locked = await payments_service.get_payment(session, payment.id, for_update=True)
            await service.admin_resolve(
                session,
                payment=locked,
                actor=admin,
                outcome=DisputeResolution.PAID,
                reason="اتصلنا بالطرفين وتأكّدنا",
            )
            holding.set()
            await asyncio.sleep(HOLD * 2)
            await session.commit()

    async def _pay_now_meanwhile():
        await holding.wait()
        await asyncio.sleep(LAG)
        return await client.post(
            f"/payments/{payment.id}/change-method",
            json={"method": "cash", "idempotency_key": "race-pay-now-01"},
            headers=rider["headers"],
        )

    _held, paid_now = await asyncio.wait_for(
        asyncio.gather(_admin_rules_holding(), _pay_now_meanwhile()), timeout=DEADLOCK_TIMEOUT
    )

    assert paid_now.status_code == 409, paid_now.text
    assert paid_now.json()["code"] == "invalid_payment_transition"
    final = await _row(session_factory, payment.id)
    assert (final.status.value, final.confirmed_by.value, final.voided_at) == ("confirmed", "admin", None)
    assert final.resolution.value == "paid"
    assert len(await rows_of(session_factory, str(final.ride_id))) == 1


async def test_change_method_against_a_commission_bearing_confirmation_does_not_deadlock(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**التبديلُ يقفل الرحلةَ ثمّ الدفعة، و«استلمت» يقفل الدفعةَ ثمّ يأخذ على الرحلة `FOR KEY SHARE`** (إدراجُ دَين العمولة يفحص
    مفتاحَه الأجنبيَّ إلى `rides`) — **فلا يُجمَدان** (قِيس ٢٠٢٦-١٠-٠٧).

    التداخلُ مُرتَّبٌ على النافذة الخطرة بعينها: الكبتنُ يقفل الدفعةَ ويقف **قبل** أن يُسوّي، والتبديلُ يقفل الرحلةَ في وقفته ثمّ
    ينتظر الدفعة، ثمّ يُدرج الكبتنُ الدَّين. **وبـ`FOR UPDATE` على الرحلة** ينتظر الكبتنُ التبديلَ والتبديلُ الكبتنَ — جمودٌ
    يُسقط أحدَهما؛ **وبـ`FOR NO KEY UPDATE`** (`_lock_ride_for_change`) لا يتعارض القفلان فيمضي الكبتنُ ويُردّ التبديل.
    """
    await set_commission(session_factory, "10")
    rider, driver, payment = await _pending_cash(client, session_factory)
    await enable_features(session_factory, "cliq_enabled")
    await set_cliq_alias(session_factory, driver["driver_id"], "ZAID.JO")
    locked = asyncio.Event()

    async def _captain_locks_then_confirms() -> None:
        async with session_factory() as session:
            captain = await session.get(Driver, driver["driver_id"])
            held = await payments_service.get_payment(session, payment.id, for_update=True)
            locked.set()
            await asyncio.sleep(HOLD)  # التبديلُ يقفل الرحلةَ الآن ثمّ ينتظر الدفعة
            await payments_service.confirm_by_driver(session, payment=held, driver=captain)
            await session.flush()  # إدراجُ الدَّين ⇒ `FOR KEY SHARE` على الرحلة
            await asyncio.sleep(LAG)
            await session.commit()

    async def _change_meanwhile():
        await locked.wait()
        await asyncio.sleep(LAG)
        return await client.post(
            f"/payments/{payment.id}/change-method",
            json={"method": "cliq", "idempotency_key": "race-deadlock-01"},
            headers=rider["headers"],
        )

    _held, changed = await asyncio.wait_for(
        asyncio.gather(_captain_locks_then_confirms(), _change_meanwhile()),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert changed.status_code == 409, changed.text
    assert changed.json()["code"] == "invalid_payment_transition"
    final = await _row(session_factory, payment.id)
    assert (final.status.value, final.confirmed_by.value, final.voided_at) == ("confirmed", "driver", None)
    assert await _debts(session_factory, payment.id) == 1
    assert len(await rows_of(session_factory, str(final.ride_id))) == 1
