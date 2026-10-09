"""تزامنُ «ادفع كلَّ ما عليك» مقرَّباً (SPEC §٧٠-ج/٦) — **الزائدُ يعود مرّةً واحدة**.

**ولا قفلَ جديداً في الجزء الثاني**: زائدُ التقريب يُكتب **تحت القفل القائم لمساره** — صفُّ المطالبة في تأكيد سداد الدَّين
(`cliq_debts._locked`)، وصفُّ الكبتن ثمّ صفُّ السلفة في السداد الكامل (`drivers.lock` · `advances.outstanding_for`) — **وقفلُ
المحفظة آخرُها** كما في ترتيب `CLAUDE.md`. فما يُقاس هنا **الثابتُ الذي يملكه ذلك القفلُ بعد أن صار يكتب قيداً ثانياً**:

- **تأكيدان متزامنان لمطالبة «الدَّين كلّه»**: واحدٌ يمرّ والآخرُ `409`، **وقيدُ `rounding` واحدٌ وصفُّ السجلّ واحد**. **وقِيس
  بالحذف** (٢٠٢٦-١٠-٠٩): بنزع `with_for_update` من `cliq_debts._locked` يقرأ الاثنان `created` فيمرّان معاً — `Counter({200: 2})`،
  والثاني يجد الدَّينَ صفراً فيقرأ ما وصل «زائداً حقيقيّاً» — **فسقط هذا الاختبار**، وعاد أخضرَ بعودة القفل.
- **سدادان كاملان متزامنان لسلفة**: واحدٌ يمرّ والآخرُ `404`، **والزائدُ يعود مرّةً** والمسدَّدُ الدَّينُ حرفاً، ولا رصيدَ سالب.

**ومسارٌ جديدٌ بعد مراجعة المال** (البند ١): **عمولةُ مقدَّم الساعة تُكتب عند الإنهاء** (`payments.settle_deferred_commission`)،
ويسابقه اثنان — **وما يحرس كلّاً مقيسٌ لا مفترض** (٢٠٢٦-١٠-٠٩):

- **تأكيدُ الكبتن لمقدَّمٍ نقديٍّ معلَّق**: الإنهاءُ **يقفل الصفَّ المعلَّق** بعد صفِّ الرحلة — والثابت: **عمولةُ المقدَّم تُكتب مرّةً
  واحدة** (`0.788`). **وبحذف القفل** يقرأ التأكيدُ الأجرةَ فارغةً (الإنهاءُ لم يُثبَّت) فيؤجّلها، والإنهاءُ قرأ الصفَّ معلَّقاً فتخطّاه —
  **فلا تُكتب عمولةٌ أبداً**: سقط هذا الاختبارُ بالحذف وعاد أخضرَ بعودة القفل.
- **ردُّ مقدَّم المحفظة من اللوحة**: **لا قفلَ له في المسار** — قيدُ الردّ في الدفتر يحمل `ride_id`، ففحصُ مفتاحه الأجنبيّ يطلب
  `FOR KEY SHARE` على صفِّ الرحلة الذي يقفله الإنهاءُ `FOR UPDATE`، **فينتظر الردُّ تثبيتَ الإنهاء قبل أن يقرأ العمولة**. وكان قفلُ
  الصفِّ له في أوّل صياغةٍ **فلم يُسقط حذفُه الاختبار** (التسلسلُ قائمٌ بالمفتاح الأجنبيّ)، **وكان يصنع جموداً** (الردُّ يمسك الدفعةَ
  وينتظر الرحلة، والإنهاءُ يمسك الرحلةَ وينتظر الدفعة) — فنُزع. والثابتُ المقيس: **صافي الكبتن من مقدَّمٍ رُدّ صفر**.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import WalletTransactionType
from app.models.ride import Ride
from app.models.rounding import MoneyRounding
from app.models.wallet import WalletTransaction
from app.services import advances as advances_service
from app.services import rides as rides_service
from tests import test_advances as advances_tests
from tests import test_rounding as rounding_tests
from tests.helpers import (
    DRIVER,
    NEAR_PICKUP,
    approved_driver,
    bring_online,
    completed_ride,
    ensure_plan,
    pay_ride,
    payments_of,
    rider_session,
    set_commission,
    topup_wallet,
)
from tests.test_payments import _only, _online_driver, _rider

pytestmark = pytest.mark.asyncio


async def _enable_rounding(client: AsyncClient, admin_headers: dict) -> None:
    response = await client.patch(
        "/admin/settings/payments/JO",
        json={"rounding_enabled": True, "rounding_unit": "0.500", "rounding_mode": "nearest"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


async def _rounding_entries(session_factory, user_id) -> list[WalletTransaction]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(WalletTransaction).where(
                    WalletTransaction.owner_id == uuid.UUID(str(user_id)),
                    WalletTransaction.type == WalletTransactionType.ROUNDING,
                )
            )
        )


async def _journal(session_factory, kind: str) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(MoneyRounding).where(MoneyRounding.source_kind == kind)
            )
            or 0
        )


async def _together(*requests):
    results = await asyncio.wait_for(
        asyncio.gather(*requests, return_exceptions=True),
        # **المهلةُ هي ما يُفشل الجمود** — الجمودُ يعلّق ولا يرفع استثناءً
        timeout=30.0,
    )
    return Counter(r.status_code for r in results if not isinstance(r, BaseException)), results


async def test_two_confirmations_of_a_whole_debt_claim_return_the_excess_once(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await set_commission(session_factory, "10")
    await _enable_rounding(client, admin_headers)
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider["headers"], driver)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())
    assert (await client.post(f"/payments/{payment['id']}/confirm", headers=driver["headers"])).status_code == 200

    claim = await client.post("/drivers/me/debt/cliq", json={"amount": "1.000"}, headers=driver["headers"])
    assert claim.status_code == 201, claim.text
    path = f"/admin/drivers/debts/claims/{claim.json()['id']}/confirm"

    codes, results = await _together(
        *[client.post(path, json={"credited": "1.000"}, headers=admin_headers) for _ in range(2)]
    )
    assert codes == Counter({200: 1, 409: 1}), (codes, [getattr(r, "text", r) for r in results])
    loser = next(r for r in results if not isinstance(r, BaseException) and r.status_code == 409)
    assert loser.json()["code"] == "invalid_status_transition", loser.text

    [returned] = await _rounding_entries(session_factory, driver["user_id"])
    assert returned.amount == Decimal("0.200")
    assert await _journal(session_factory, "debt_settlement") == 1


async def test_two_full_repayments_of_an_advance_return_the_excess_once(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    await ensure_plan(session_factory, name="يوميُّ التقريب", price="2.000", duration="daily")
    await advances_tests._enable(session_factory, min_kept_amount=Decimal("0"))
    await _enable_rounding(client, admin_headers)
    driver = await approved_driver(client, session_factory, DRIVER)
    await advances_tests._qualify(session_factory, driver["driver_id"])
    taken = await client.post("/drivers/me/advances", json={"amount": "2.000"}, headers=driver["headers"])
    assert taken.status_code == 201, taken.text

    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "50.000")
    await bring_online(client, driver, NEAR_PICKUP)
    ride = await completed_ride(client, rider["headers"], driver)
    assert (await pay_ride(client, rider["headers"], ride["id"], "wallet")).status_code == 201

    codes, results = await _together(
        *[client.post("/drivers/me/advances/repay", headers=driver["headers"]) for _ in range(2)]
    )
    assert codes == Counter({200: 1, 404: 1}), (codes, [getattr(r, "text", r) for r in results])

    [returned] = await _rounding_entries(session_factory, driver["user_id"])
    assert returned.amount == Decimal("0.100")
    assert await _journal(session_factory, "advance_repayment") == 1
    async with session_factory() as session:
        assert await advances_service.repaid_amount(session, returned.advance_id) == Decimal("2.000")
        lowest = await session.scalar(
            select(func.min(WalletTransaction.balance_after)).where(
                WalletTransaction.owner_id == uuid.UUID(str(driver["user_id"]))
            )
        )
    assert lowest >= 0


async def test_a_refund_racing_the_completion_reverses_exactly_the_deferred_prepay_commission(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الإنهاءُ يكتب عمولةَ مقدَّم المحفظة المؤجَّلة ويبقي معاملتَه مفتوحة، والردُّ يبدأ في أثنائها**. **والثابت**: صافي الكبتن من
    مقدَّمٍ رُدّ صفر — العمولةُ المكتوبة (`0.788`) تُعكس معه حرفاً. **ويحرسه صفُّ الرحلة لا قفلٌ في هذا المسار**: قيدُ الردّ يحمل
    `ride_id` فينتظر تثبيتَ الإنهاء قبل أن يقرأ العمولة (رأسُ الملفّ يقول ما قِيس).
    """
    ride, driver, rider = await rounding_tests._hourly_started(client, admin_headers, session_factory, commission="10")
    [prepay] = (await payments_of(client, rider["headers"], ride["id"]))["payments"]
    # **إشارةٌ لا مهلة لبدء الردّ**: الإنهاءُ أطولُ من أيِّ مهلةٍ ثابتة (المكالمةُ والمسارُ والوقفاتُ والتقريب)، **فردٌّ يبدأ بعد مهلةٍ
    # قد يُثبَّت قبل أن يقرأ الإنهاءُ حالَ المقدَّم** — فيمرّ الاختبارُ ولو حُذف القفل (قِيس ٢٠٢٦-١٠-٠٩). والإشارةُ تُرفع **بعد** أن
    # كتب الإنهاءُ العمولةَ، **والتثبيتُ بعدها بمهلة** — فتقع قراءةُ الردّ داخل معاملةٍ مفتوحة
    written = asyncio.Event()

    async def complete_holding_open() -> None:
        async with session_factory() as session:
            row = await session.get(Ride, uuid.UUID(ride["id"]))
            captain = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
            await rides_service.complete_ride(session, row, captain)
            written.set()
            await asyncio.sleep(0.6)  # يبقى صفُّ المقدَّم مقفولاً بينما يبدأ الردّ
            await session.commit()

    async def refund_meanwhile():
        await written.wait()  # بعد أن كتب الإنهاءُ العمولةَ وقبل أن يثبّتها
        return await client.post(
            f"/admin/payments/{prepay['id']}/refund", json={"reason": "ردٌّ في أثناء الإنهاء"}, headers=admin_headers
        )

    _, refunded = await asyncio.wait_for(asyncio.gather(complete_holding_open(), refund_meanwhile()), timeout=30.0)
    assert refunded.status_code == 200, refunded.text

    async with session_factory() as session:
        net = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.ride_id == uuid.UUID(ride["id"]),
                WalletTransaction.owner_id == uuid.UUID(str(driver["user_id"])),
            )
        )
        commission = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.ride_id == uuid.UUID(ride["id"]),
                WalletTransaction.type == WalletTransactionType.COMMISSION,
            )
        )
    assert Decimal(net) == 0, f"بقي للكبتن من مقدَّمٍ رُدّ {net} (العمولة {commission})"
    assert Decimal(commission) in (Decimal("0"), Decimal("-0.788")), commission


async def test_a_cash_prepay_confirmed_during_the_completion_is_commissioned_exactly_once(
    client: AsyncClient, admin_headers: dict, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الإنهاءُ يقرأ مقدَّماً نقديّاً معلَّقاً ويبقي معاملتَه مفتوحة، والكبتنُ يؤكّد استلامَه في أثنائها**. **والثابتُ الذي يملكه قفلُ
    الصفِّ المعلَّق** (`settle_deferred_commission`): **عمولةُ المقدَّم دَينٌ واحدٌ `0.788`** — على المسعَّر `7.875` لا المقرَّب.

    **وبحذف القفل** يمضي التأكيدُ فيقرأ الأجرةَ فارغةً (الإنهاءُ لم يُثبَّت) فيؤجّل العمولة، والإنهاءُ تخطّى الصفَّ لأنه قرأه معلَّقاً —
    **فلا دَينَ ولا قيد: عمولةٌ ضاعت بلا سطر**.
    """
    ride, driver, rider = await rounding_tests._hourly_started(
        client, admin_headers, session_factory, commission="10", prepay="cash"
    )
    [prepay] = (await payments_of(client, rider["headers"], ride["id"]))["payments"]
    assert (prepay["method"], prepay["status"], prepay["amount"]) == ("cash", "pending", "8.000")
    read = asyncio.Event()

    async def complete_holding_open() -> None:
        async with session_factory() as session:
            row = await session.get(Ride, uuid.UUID(ride["id"]))
            captain = await session.get(Driver, uuid.UUID(str(driver["driver_id"])))
            await rides_service.complete_ride(session, row, captain)
            read.set()
            await asyncio.sleep(0.6)  # يبقى الصفُّ المعلَّقُ مقفولاً بينما يؤكّده الكبتن
            await session.commit()

    async def confirm_meanwhile():
        await read.wait()  # بعد أن قرأ الإنهاءُ الصفَّ معلَّقاً وقبل أن يثبّت
        return await client.post(f"/payments/{prepay['id']}/confirm", headers=driver["headers"])

    _, confirmed = await asyncio.wait_for(asyncio.gather(complete_holding_open(), confirm_meanwhile()), timeout=30.0)
    assert confirmed.status_code == 200, confirmed.text

    async with session_factory() as session:
        debts = list(
            await session.scalars(select(DriverDebt.amount).where(DriverDebt.payment_id == uuid.UUID(prepay["id"])))
        )
    assert debts == [Decimal("0.788")], f"عمولةُ المقدَّم النقديّ: {debts}"
