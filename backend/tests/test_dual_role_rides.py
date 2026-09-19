"""حسابٌ بدورَي الراكب والكبتن — **الإلغاءُ برسمٍ والدفعُ من المحفظة** (عطبُ رحلاتٍ قائم).

**العطب** (مقيسٌ 2026-09-19، `SPEC-DELIVERY.md` §D6): قراءتا رصيدٍ بلا إعلان —
`payments.pay_with_wallet` و`cancellation._move` — فحسابٌ يحمل الدورين يرتدّ
`409 wallet_owner_undecided` **والسياقُ يعرف الجواب**: أجرةُ رحلته يدفعها راكباً،
ورسمُ الإلغاء يُحصَّل من المحفظة التي يكتب عليها القيدُ نفسُه. قائمٌ منذ `7bea224`
(2026-08-19) وفي كلِّ وسمٍ من `v0.1.0` إلى `v0.2.2`. **وليس عملَ توصيل.**

**والإصلاحُ إعلانٌ في المسارين لا تخمينٌ في الدالّة** (أمرُ المالك): `owner_type_for`
تبقى ترفض عند الالتباس، والمسارُ هو من يقول أيَّ محفظةٍ يقصد.
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
    UserRole,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.user_role_grant import UserRoleGrant
from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    accepted_ride,
    approved_driver,
    bring_online,
    broadcast_location,
    completed_ride,
    pay_ride,
    rider_session,
    topup_wallet,
)
from tests.test_cancellation_collection import SECOND_DRIVER, _charge, _owe

# نقطةٌ بعيدةٌ عن الالتقاء بما يتجاوز عتبةَ الإعفاء (~5 كم) — كبتنٌ تحرّك فعلاً
FAR_AWAY = {"lat": 32.0060, "lng": 35.9106}


async def _grant(session_factory, user_id: str, role: UserRole) -> None:
    """صفُّ الدور يُكتب مباشرةً — لا بابَ يمنح دوراً (`test_no_route_grants_a_role`)."""
    async with session_factory() as session:
        session.add(UserRoleGrant(user_id=uuid.UUID(user_id), role=role))
        await session.commit()


async def _exempt_within_300m(session_factory) -> None:
    async with session_factory() as session:
        row = await session.get(CancellationSetting, CountryCode.JO)
        if row is None:
            row = CancellationSetting(country_code=CountryCode.JO)
            session.add(row)
        row.exempt_within_meters = 300
        await session.commit()


async def _rider_ledger(session_factory, user_id: str, tx: WalletTransactionType) -> Decimal:
    async with session_factory() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.owner_id == uuid.UUID(user_id),
                WalletTransaction.owner_type == WalletOwnerType.RIDER,
                WalletTransaction.type == tx,
            )
        )
    return Decimal(total)


async def _cancel_a_fee_bearing_ride(
    client: AsyncClient, admin_headers: dict, session_factory, *, dual: bool
) -> tuple[object, RideCancellationCharge | None, dict, dict]:
    """المسارُ الأول: إلغاءُ رحلةٍ مقبولةٍ عليها رسم (كبتنٌ تحرّك فعلاً)."""
    await _exempt_within_300m(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "50.000")
    if dual:
        await _grant(session_factory, rider["user"]["id"], UserRole.DRIVER)

    ride = await accepted_ride(client, rider["headers"], driver)
    await broadcast_location(client, driver, **FAR_AWAY)
    cancelled = await client.post(
        f"/rides/{ride['id']}/cancel",
        json={"reason": "غيّرت رأيي"},
        headers=rider["headers"],
    )
    async with session_factory() as session:
        charge = await session.scalar(
            select(RideCancellationCharge).where(
                RideCancellationCharge.ride_id == uuid.UUID(ride["id"])
            )
        )
    return cancelled, charge, rider, driver


async def _pay_a_ride_by_wallet(client: AsyncClient, rider: dict, driver: dict):
    """المسارُ الثاني: دفعُ أجرة رحلةٍ مكتملةٍ من المحفظة."""
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)
    return await pay_ride(client, rider["headers"], ride["id"], "wallet")


# ------------------------------------------------------ الحالُ المعطوبة


async def test_a_dual_role_account_cancels_a_fee_bearing_ride_and_pays_from_its_wallet(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """**يحمرّ على الشيفرة قبل الإصلاح**: الإلغاءُ ٤٠٩ والدفعُ ٤٠٩ (`wallet_owner_undecided`)."""
    cancelled, charge, rider, driver = await _cancel_a_fee_bearing_ride(
        client, admin_headers, session_factory, dual=True
    )
    assert cancelled.status_code == 200, cancelled.text
    assert charge is not None
    assert charge.status is CancellationChargeStatus.SETTLED
    assert await _rider_ledger(
        session_factory, rider["user"]["id"], WalletTransactionType.CANCELLATION_FEE
    ) == -charge.amount

    paid = await _pay_a_ride_by_wallet(client, rider, driver)
    assert paid.status_code == 201, paid.text
    assert await _rider_ledger(
        session_factory, rider["user"]["id"], WalletTransactionType.RIDE_PAYMENT
    ) < 0


# ------------------------------------------- ذو الدور الواحد: لم يتغيّر


async def test_a_rider_only_account_behaves_as_before_on_both_paths(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """**يخضرّ قبل الإصلاح وبعده** — وهو ما يثبت أن الإعلانَ لم يغيّر جوابَ ذي الدور الواحد."""
    cancelled, charge, rider, driver = await _cancel_a_fee_bearing_ride(
        client, admin_headers, session_factory, dual=False
    )
    assert cancelled.status_code == 200, cancelled.text
    assert charge is not None
    assert charge.status is CancellationChargeStatus.SETTLED
    assert await _rider_ledger(
        session_factory, rider["user"]["id"], WalletTransactionType.CANCELLATION_FEE
    ) == -charge.amount

    paid = await _pay_a_ride_by_wallet(client, rider, driver)
    assert paid.status_code == 201, paid.text


async def test_a_driver_only_carrier_is_still_collected_from_the_driver_wallet(
    client: AsyncClient,
    admin_headers: dict,
    session_factory,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """**الكبتنُ وحدَه في مسار الإلغاء**: حاملُ رسمٍ قبضه نقداً يُحصَّل منه عند الشحن.

    وهو المسارُ الذي تقرأ فيه القراءةُ المُصلَحةُ محفظةَ **الكبتن** (`carrier_driver_id`
    مختوم) — فيخضرّ قبل الإصلاح وبعده. ومسارُ الدفع لا يبلغه كبتنٌ وحدَه: `RiderUser`
    يرفضه عند الباب قبل أيِّ قراءة، ويُختبر أنه ما زال يرفضه.
    """
    setup = await _owe(client, admin_headers, session_factory)
    rider = setup["rider"]

    carrier = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7777"
    )
    await bring_online(client, carrier)
    ride = await completed_ride(client, rider["headers"], carrier)
    paid = await pay_ride(client, rider["headers"], ride["id"], "cash")
    payment_id = paid.json()["payments"][0]["id"]
    await client.post(f"/payments/{payment_id}/confirm", headers=carrier["headers"])

    await topup_wallet(client, admin_headers, carrier["user_id"], "20.000")
    charge = await _charge(session_factory, str(setup["charge"].ride_id))
    assert charge.status is CancellationChargeStatus.SETTLED

    refused = await pay_ride(client, carrier["headers"], ride["id"], "wallet")
    assert refused.status_code == 403, refused.text
