"""دَينُ الكبتن — **الطريقُ المسدودُ مقيساً في الاتجاهين** (2026-08-30).

## ما يُقاس هنا ليس ميزةً بل عطبٌ كان حيّاً

قبل الترحيلة `0061`: رحلةُ كاشٍ بعمولةٍ ورصيدٌ صفرٌ ⇒ `wallet.record` يرفض
السالبَ ⇒ التسويةُ **تُرمى** بجملةٍ تقول «اشحن المحفظة»، **وبابُ شحن محفظة
الكبتن مُلغى**. فالكبتنُ **لا يُنهي رحلتَه**.

**والاتجاهُ الثاني هو ما يجعل القياسَ قياساً**: أن الرصيدَ الكافي **ما زال
يُخصم لحظتَه** كما كان — فالإصلاحُ لم يؤجّل تحصيلَ من يملك، ولم يُرخِ حارسَ
«لا رصيد سالب» الذي أمر المالكُ ألّا يُنقض.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import DriverDebtStatus
from tests.helpers import (
    completed_ride,
    pay_ride,
    set_commission,
    topup_wallet,
    wallet_of,
)
from tests.helpers import OTHER_RIDER
from tests.test_payments import _only, _online_driver, _rider

pytestmark = pytest.mark.asyncio

#: أجرةُ الرحلة في هذه المجموعة 8.000، والعمولة 15% ⇒ 1.200
COMMISSION = Decimal("1.200")


async def _cash_ride_settled(client: AsyncClient, session_factory) -> tuple[dict, dict]:
    """رحلةُ كاشٍ مؤكَّدةٌ من الكبتن — **والتأكيدُ هو ما كان يسقط**."""
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider["headers"], driver)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())
    confirmed = await client.post(
        f"/payments/{payment['id']}/confirm", headers=driver["headers"]
    )
    assert confirmed.status_code == 200, (
        "**الطريقُ المسدود**: تسويةُ رحلةِ كاشٍ سقطت — وهذا نصُّها: "
        f"{confirmed.text}"
    )
    return driver, payment


async def _debt_rows(session_factory, driver_id) -> list[DriverDebt]:
    async with session_factory() as session:
        return list(
            (
                await session.scalars(
                    select(DriverDebt).where(DriverDebt.driver_id == driver_id)
                )
            ).all()
        )


async def test_a_cash_ride_settles_with_an_empty_wallet_and_writes_a_debt(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الاتجاهُ الأول** — رصيدٌ صفرٌ لم يعد يمنع الكبتنَ من إنهاء رحلته.

    وقبل اليوم كان `confirm` يُرمى بـ«اشحن المحفظة ثم أكّد» **وبابُ الشحن
    مُلغى** — فالحلقةُ مغلقةٌ على الكبتن.
    """
    await set_commission(session_factory, "15")
    driver, _payment = await _cash_ride_settled(client, session_factory)

    # **ولا رصيدَ سالب** — الحارسُ في موضعه ولم يُنقض
    assert (await wallet_of(client, driver["headers"]))["balance"] == "0.000"

    rows = await _debt_rows(session_factory, driver["driver_id"])
    assert len(rows) == 1, "العمولةُ لم تُكتب في جدول الدَّين"
    assert rows[0].amount == COMMISSION
    assert rows[0].collected == Decimal("0.000")
    assert rows[0].status is DriverDebtStatus.OUTSTANDING


async def test_a_wallet_that_covers_the_commission_still_pays_it_at_once(
    client: AsyncClient,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
    admin_headers: dict,
) -> None:
    """**الاتجاهُ الثاني** — من يملك يُخصم منه في المعاملة نفسِها، بلا فرق.

    **وهذا ما يمنع الإصلاحَ من أن يصير تأجيلاً للجميع**: الدَّينُ يُكتب ثم
    يُحصَّل فوراً إن غطّاه الرصيد، فلا يرى صاحبُ الرصيد تغيُّراً في سلوكه.
    """
    await set_commission(session_factory, "15")
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "5.000")

    ride = await completed_ride(client, rider["headers"], driver)
    payment = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())
    assert (
        await client.post(
            f"/payments/{payment['id']}/confirm", headers=driver["headers"]
        )
    ).status_code == 200

    assert (await wallet_of(client, driver["headers"]))["balance"] == "3.800", (
        "الرصيدُ الكافي لم يُخصم منه لحظتَه — الإصلاحُ أجّل تحصيلَ من يملك"
    )
    rows = await _debt_rows(session_factory, driver["driver_id"])
    assert len(rows) == 1 and rows[0].status is DriverDebtStatus.SETTLED, (
        "الصفُّ لم يُقفل بعد تحصيله"
    )


async def test_the_debt_is_collected_from_a_later_cashless_earning(
    client: AsyncClient,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
    admin_headers: dict,
) -> None:
    """**الدَّينُ يُحصَّل لحظةَ أن يدخل المال** — ومن رحلةٍ لاحقةٍ تمرّ بنا."""
    await set_commission(session_factory, "15")
    driver, _payment = await _cash_ride_settled(client, session_factory)
    assert (await _debt_rows(session_factory, driver["driver_id"]))[
        0
    ].status is DriverDebtStatus.OUTSTANDING

    # **راكبٌ ثانٍ**: الأول مسجَّلٌ بالفعل داخل `_cash_ride_settled`
    # رحلةٌ ثانيةٌ بالمحفظة: أجرتُها تدخل محفظةَ الكبتن ⇒ الدَّينُ يُقتطع
    rider = await _rider(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, rider["user_id"], "20.000")
    ride = await completed_ride(client, rider["headers"], driver)
    # **ومفتاحُ تفرُّدٍ ثانٍ**: الافتراضيُّ استُهلك في دفعة الكاش قبله
    payment = _only(
        (
            await pay_ride(
                client, rider["headers"], ride["id"], "wallet", key="second-pay-0002"
            )
        ).json()
    )
    assert payment["status"] in {"confirmed", "pending"}

    rows = await _debt_rows(session_factory, driver["driver_id"])
    settled = [row for row in rows if row.status is DriverDebtStatus.SETTLED]
    assert settled, "الدَّينُ لم يُحصَّل رغم دخول أجرةٍ إلى المحفظة"

    entries = (
        await client.get("/wallet/me/transactions", headers=driver["headers"])
    ).json()
    collected = [
        entry
        for entry in entries
        if entry["type"] == "commission"
        and entry.get("reference") == "تحصيل عمولة رحلة سابقة قُبضت نقداً"
    ]
    assert collected, "لا قيدَ يشرح النقص — والسببُ يجب أن يسافر مع القيد"


async def test_a_partial_settlement_reduces_the_debt_but_does_not_lift_the_block(
    client: AsyncClient, jordan_settings: None, jordan_wallet: None, session_factory
) -> None:
    """**الجزئيُّ يُقبل ويُنقص، والمنعُ يُرفع عند الصفر لا قبله** (قرارُ المالك)."""
    from app.services import debts as debts_service
    from app.models.enums import CountryCode

    await set_commission(session_factory, "15")
    driver, _payment = await _cash_ride_settled(client, session_factory)

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        # يُشعل المنعُ يدوياً: السقفُ فارغٌ بقرار المالك، فلا يُشعله شيءٌ اليوم
        row.debt_blocked = True
        await session.commit()

        applied = await debts_service.apply_settlement(
            session,
            driver=await session.get(Driver, driver["driver_id"]),
            country=CountryCode.JO,
            amount=Decimal("0.500"),
        )
        await session.commit()
        assert applied == Decimal("0.500")

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        assert row.debt_blocked is True, "نصفُ سدادٍ رفع المنع — والشرطُ الصفر"
        assert await debts_service.outstanding_of(session, row.id) == Decimal("0.700")

        await debts_service.apply_settlement(
            session, driver=row, country=CountryCode.JO, amount=Decimal("0.700")
        )
        await session.commit()

    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        assert row.debt_blocked is False, "بلغ الصفرَ ولم يُرفع المنع"


async def test_a_blocked_driver_is_not_offered_rides(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """**العَلَمُ الثالثُ يُقرأ حيث يُقرأ أخواه** — وإلا كان منعاً لا يمنع."""
    from app.models.enums import VehicleCategory
    from app.services import dispatch

    driver = await _online_driver(client, session_factory)
    async with session_factory() as session:
        eligible = await dispatch.eligible_driver_ids(
            session, [driver["driver_id"]], VehicleCategory.ECONOMY
        )
        assert driver["driver_id"] in eligible

        row = await session.get(Driver, driver["driver_id"])
        row.debt_blocked = True
        await session.commit()

    async with session_factory() as session:
        eligible = await dispatch.eligible_driver_ids(
            session, [driver["driver_id"]], VehicleCategory.ECONOMY
        )
        assert driver["driver_id"] not in eligible, (
            "الممنوعُ لدَينٍ ما زال يُعرض عليه — العَلَمُ لا يُقرأ في التوزيع"
        )
