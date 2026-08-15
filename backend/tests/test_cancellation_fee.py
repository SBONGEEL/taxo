"""رسمُ الإلغاء بعد القبول (`design/CANCELLATION-FEE.md`، قراراتُ المالك 2026-08-15).

**والعطبُ الذي وُجد لأجله كان صامتاً تماماً**: يُحسب الرسمُ ويُجمَّد على الرحلة
ويُعرض للراكب — ولا صفَّ دفعةٍ ولا قيدَ في دفترٍ ولا شيءَ لمن تحرّك. فكلُّ
اختبارٍ هنا يسأل **الدفتر**، لا رمزَ الاستجابة: رحلةٌ تُلغى بـ200 وشاشةٌ تعرض
رقماً هو بالضبط ما كان يقع قبل هذا الملف.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.cancellation import CancellationSetting, RideCancellationCharge
from app.models.enums import (
    CancellationChargeStatus,
    CountryCode,
    WalletTransactionType,
)
from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    PICKUP,
    DROPOFF,
    accepted_ride,
    approved_driver,
    bring_online,
    broadcast_location,
    enable_features,
    rider_session,
    topup_wallet,
)

# نقطةٌ بعيدةٌ عن الالتقاء بما يتجاوز أيَّ عتبةِ إعفاءٍ معقولة (~5 كم)
FAR_AWAY = {"lat": 32.0060, "lng": 35.9106}


async def _policy(session_factory, **values) -> None:
    """سياسةُ الدولة — تُكتب صفّاً كما تكتبها اللوحة، لا تُحقن في الخدمة."""
    async with session_factory() as session:
        row = await session.get(CancellationSetting, CountryCode.JO)
        if row is None:
            row = CancellationSetting(country_code=CountryCode.JO)
            session.add(row)
        for key, value in values.items():
            setattr(row, key, value)
        await session.commit()


async def _charge_of(session_factory, ride_id: str) -> RideCancellationCharge | None:
    async with session_factory() as session:
        return await session.scalar(
            select(RideCancellationCharge).where(
                RideCancellationCharge.ride_id == uuid.UUID(ride_id)
            )
        )


async def _ledger(session_factory, tx_type: WalletTransactionType) -> Decimal:
    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.type == tx_type
            )
        )
    return Decimal(total or 0)


async def _cancel(client: AsyncClient, headers: dict, ride_id: str) -> int:
    response = await client.post(
        f"/rides/{ride_id}/cancel", json={"reason": "غيّرت رأيي"}, headers=headers
    )
    return response.status_code


async def _setup(
    client: AsyncClient, admin_headers: dict, session_factory, *, balance: str
) -> dict:
    await _policy(session_factory, exempt_within_meters=300)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    if balance != "0":
        await topup_wallet(client, admin_headers, rider["user"]["id"], balance)
    return {"rider": rider, "driver": driver}


async def test_the_money_actually_moves_between_the_two_parties(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """الراكبُ يُخصم والكبتنُ يُقيَّد — **والدفترُ هو الحكم، لا الشاشة**."""
    setup = await _setup(client, admin_headers, session_factory, balance="20.000")
    ride = await accepted_ride(client, setup["rider"]["headers"], setup["driver"])
    # كبتنٌ تحرّك فعلاً: بثٌّ من موقعٍ بعيدٍ عن نقطة الالتقاء
    await broadcast_location(client, setup["driver"], **FAR_AWAY)

    assert await _cancel(client, setup["rider"]["headers"], ride["id"]) == 200

    charge = await _charge_of(session_factory, ride["id"])
    assert charge is not None
    assert charge.status is CancellationChargeStatus.SETTLED
    assert charge.settled_at is not None

    # قيدان لا قيدٌ صافٍ: مدينٌ على الراكب ودائنٌ للكبتن بالقيمة نفسِها
    fee = await _ledger(session_factory, WalletTransactionType.CANCELLATION_FEE)
    paid = await _ledger(
        session_factory, WalletTransactionType.CANCELLATION_COMPENSATION
    )
    assert fee == -charge.amount
    assert paid == charge.amount


async def test_a_driver_who_never_moved_costs_the_rider_nothing(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """الإعفاءُ بالقرب: من لم يبرح مكانَه لم يُتعِب أحداً (§3).

    **والرحلةُ تُصفَّر أيضاً**: رقمٌ مجمَّدٌ بلا صفِّ تحصيلٍ هو العطبُ القديم
    بعينه — «مدينٌ بلا باب» يقرؤه الراكبُ في شاشة التفاصيل.
    """
    setup = await _setup(client, admin_headers, session_factory, balance="20.000")
    ride = await accepted_ride(client, setup["rider"]["headers"], setup["driver"])
    await broadcast_location(client, setup["driver"], **PICKUP)

    assert await _cancel(client, setup["rider"]["headers"], ride["id"]) == 200

    assert await _charge_of(session_factory, ride["id"]) is None
    detail = await client.get(
        f"/rides/{ride['id']}", headers=setup["rider"]["headers"]
    )
    assert Decimal(detail.json()["cancellation_fee"]) == Decimal("0.000")


async def test_a_silent_driver_leaves_the_doubt_with_the_rider(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """الفرعُ (أ) بنصِّ المالك: بلا موقعٍ مبثوثٍ لا دليلَ على تحرّك.

    ولا يُقاس البعدُ من نقطة الالتقاء عند الصمت: كبتنٌ انقطع اتصالُه قبل
    الإلغاء بدقيقةٍ لا موقعَ له، ومن تحرّك فعلاً يعترض في اللوحة.
    """
    setup = await _setup(client, admin_headers, session_factory, balance="20.000")
    ride = await accepted_ride(client, setup["rider"]["headers"], setup["driver"])
    # **يُمحى مفتاحُ الحضور**: الدخولُ إلى الخدمة يبثّ موقعاً بالضرورة (بلا
    # بثٍّ لا عرضَ أصلاً)، والحالُ المقصودةُ هي انقطاعُه **بعد** القبول —
    # ومفتاحُ الحضور عمرُه ٦٠ ثانية، فمحوُه هو انقضاؤه بعينه
    from app.core.redis_client import get_redis_client
    from app.services.geo import presence_key

    await get_redis_client().delete(presence_key(setup["driver"]["driver_id"]))

    assert await _cancel(client, setup["rider"]["headers"], ride["id"]) == 200
    assert await _charge_of(session_factory, ride["id"]) is None


async def test_an_empty_wallet_never_refuses_the_cancellation(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """**لا يُرفض الإلغاء لفراغ الرصيد أبداً** (نصُّ القرار) — يُسجَّل ديناً.

    راكبٌ لا يستطيع الإلغاءَ لخلوّ محفظته يبقى في سيارةٍ لا يريدها أو يترك
    كبتناً ينتظر بلا قرار، وكلاهما أسوأُ من دَينٍ مكتوب.
    """
    setup = await _setup(client, admin_headers, session_factory, balance="0")
    ride = await accepted_ride(client, setup["rider"]["headers"], setup["driver"])
    await broadcast_location(client, setup["driver"], **FAR_AWAY)

    assert await _cancel(client, setup["rider"]["headers"], ride["id"]) == 200

    charge = await _charge_of(session_factory, ride["id"])
    assert charge is not None
    assert charge.status is CancellationChargeStatus.PENDING
    assert charge.settled_at is None
    # ولا قيدَ في الدفتر: القيدُ يعني مالاً **وصل**
    assert await _ledger(
        session_factory, WalletTransactionType.CANCELLATION_COMPENSATION
    ) == Decimal("0")


async def test_an_unpaid_debt_blocks_a_new_ride_only_at_the_admins_threshold(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """التكرار يُوقف الطلب (§4) — **ومقارنةٌ حيّةٌ لا عمودٌ موسوم**.

    فرفعُ الحدِّ في اللوحة يُطلق سراحَ الجميع بلا لمس صف، وهي قاعدةُ «flagged»
    في تقارير عدم التطابق نفسُها.
    """
    setup = await _setup(client, admin_headers, session_factory, balance="0")
    ride = await accepted_ride(client, setup["rider"]["headers"], setup["driver"])
    await broadcast_location(client, setup["driver"], **FAR_AWAY)
    assert await _cancel(client, setup["rider"]["headers"], ride["id"]) == 200

    # الحدُّ صفرٌ ⇒ لا إيقاف، وهو الافتراضُ حتى يضبطه المالك
    again = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
        headers=setup["rider"]["headers"],
    )
    assert again.status_code == 201, again.text
    await _cancel(client, setup["rider"]["headers"], again.json()["id"])

    await _policy(session_factory, block_after_unpaid=1)
    blocked = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
        headers=setup["rider"]["headers"],
    )
    assert blocked.status_code == 402, blocked.text
    assert blocked.json()["code"] == "cancellation_debt_blocked"

    # ورفعُ الحدِّ يفتح البابَ في الحال — بلا تعديل أيِّ صفٍّ للراكب
    await _policy(session_factory, block_after_unpaid=5)
    reopened = await client.post(
        "/rides",
        json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy"},
        headers=setup["rider"]["headers"],
    )
    assert reopened.status_code == 201, reopened.text


async def test_a_gender_mismatch_cancellation_still_costs_nothing(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """الإعفاءُ القائمُ يبقى فوق هذا كلِّه (§3): لا رسمَ مهما قرب الكبتن."""
    await enable_features(session_factory, "women_service_enabled")
    setup = await _setup(client, admin_headers, session_factory, balance="20.000")
    rider = setup["rider"]
    await client.patch(
        "/users/me", json={"gender": "female"}, headers=rider["headers"]
    )
    # وكبتنةٌ مختومةٌ أنثى: الطلبُ المجنَّس لا يصل رجلاً أصلاً (المطابقةُ في
    # `dispatch.eligible_driver_ids`)، فالحالُ الواقعةُ أن تصلها هي ثم تُلغي
    # الراكبةُ بحجّة عدم التطابق — والحارسُ القائمُ يقبل السببَ لأن رحلتَها
    # **طلبت جنساً**، وهو بالضبط ما يمنعه عن رحلةٍ لم تطلب
    from datetime import UTC, datetime

    from app.models.driver import Driver
    from app.models.user import User

    async with session_factory() as session:
        row = await session.get(Driver, setup["driver"]["driver_id"])
        driver_user = await session.get(User, row.user_id)
        driver_user.gender = "female"
        driver_user.gender_verified_at = datetime.now(UTC)
        await session.commit()

    # **رحلةٌ مجنَّسةٌ فعلاً**: `gender_mismatch` يُرفض على رحلةٍ لم تطلب جنساً
    # — وهو حارسٌ قائمٌ منذ 10-ج يمنع «باباً مجانياً للإفلات من كل رسم»
    requested = await client.post(
        "/rides",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "gender_preference": "female",
        },
        headers=rider["headers"],
    )
    assert requested.status_code == 201, requested.text
    from tests.helpers import wait_for_offer

    await wait_for_offer(requested.json()["id"], setup["driver"]["driver_id"])
    accepted = await client.post(
        f"/rides/{requested.json()['id']}/accept", headers=setup["driver"]["headers"]
    )
    assert accepted.status_code == 200, accepted.text
    ride = accepted.json()
    await broadcast_location(client, setup["driver"], **FAR_AWAY)

    response = await client.post(
        f"/rides/{ride['id']}/cancel",
        json={"reason": "الكبتن ليس أنثى", "reason_code": "gender_mismatch"},
        headers=rider["headers"],
    )
    assert response.status_code == 200, response.text
    assert await _charge_of(session_factory, ride["id"]) is None
