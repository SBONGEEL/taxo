"""المرحلة 13: **السيناريو كاملاً من أبوابه الحقيقية**، ثم يُجمع الدفتر.

`SPEC` §16/13: «اختبارات + تشغيل تجريبي كامل لسيناريو: تسجيل كبتن → موافقة →
اشتراك → طلب رحلة → تتبع → دفع → سحب».

**وما يميّزه عن كلِّ اختبارٍ قبله أنه لا يختصر شيئاً.** بقيةُ الملفات تستعمل
`helpers.approved_driver` — وهو يكتب `approved` في القاعدة ويكتب صفَّ اشتراكٍ
مباشرة، وذلك **تهيئةٌ صحيحةٌ لاختبار ميزة**: من يقيس التوزيعَ لا يعيد بناءَ
الاعتماد. لكنّ مرحلةً تسأل «هل يعمل النظامُ من أوّله إلى آخره» لا يجوز أن تجيب
عن نظامٍ نصفُ حالاته كُتب بيدها.

فهنا: تسجيلٌ بمسار التسجيل، ومركبةٌ بمسارها، وثلاثةُ مستنداتٍ تُرفع وتُراجَع،
واعتمادٌ من بابه الإداريِّ الوحيد، واشتراكٌ يُشترى بمالٍ في محفظةٍ شُحنت، ورحلةٌ
تمرّ بالتوزيع الحقيقيِّ وبالعرض والقبول، وبثُّ مواقعَ يترك نقاطَ مسار، ودفعٌ
مختلط، وتقييم، ثم سحبٌ يُوافَق عليه ويُدفع.

**والحكمُ في آخره ليس «٢٠٠ لكلِّ نداء» بل أن يُجمع الدفتر**: رصيدُ كلِّ محفظةٍ
يساوي مجموعَ قيودها، وما دخل جيبَ الكبتن نقداً ليس في محفظته، والعمولةُ خرجت
منها، ولا قيدَ برصيدٍ سالب. فذلك وحدَه ما يجعل «يعمل» قابلاً للقياس.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.driver import Driver
from app.models.enums import DriverStatus, WalletTransactionType
from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    RIDER,
    SUBSCRIPTION_PLAN_PRICE,
    approve_all_documents,
    auth,
    broadcast_location,
    ensure_plan,
    register,
    rider_session,
    topup_wallet,
    wait_for_offer,
)

RIDER_TOPUP = "6.000"
# **الحدُّ الأدنى للسحب سياسةُ سوقٍ يضبطها المشرف**، وضبطُه جزءٌ من الرحلة لا
# التفافٌ عليها: كبتنٌ في يومه الأول لا يبلغ عشرةَ دنانير، والسوقُ الذي يفتح
# اليوم يفتح بحدٍّ يناسبه. فيُخفَّض من بابه الإداري ثم يُسحب فوقه
MIN_WITHDRAWAL_FOR_MARKET = "1.000"
WITHDRAWAL = "1.000"


async def _ledger(session_factory, owner_id) -> list[WalletTransaction]:
    async with session_factory() as session:
        rows = await session.scalars(
            select(WalletTransaction)
            .where(WalletTransaction.owner_id == uuid.UUID(str(owner_id)))
            .order_by(WalletTransaction.created_at)
        )
        return list(rows)


def _sum(entries: list[WalletTransaction]) -> Decimal:
    return sum((entry.amount for entry in entries), Decimal("0"))


async def test_the_whole_journey_from_signup_to_withdrawal(
    client: AsyncClient,
    session_factory,
    admin_headers: dict,
    jordan_settings,
    jordan_wallet,
) -> None:
    """كبتنٌ من الصفر إلى سحبِ ما كسبه، وراكبٌ يدفع من محفظته وجيبه."""

    # ── ١. تسجيلُ الكبتن ومركبتِه ─────────────────────────────────────────
    driver_body = await register(client, DRIVER)
    driver_headers = auth(driver_body)
    driver_user_id = driver_body["user"]["id"]

    vehicle = await client.post(
        "/drivers/me/vehicles",
        json={
            "make": "Toyota",
            "model": "Corolla",
            "year": 2022,
            "color": "أبيض",
            "plate_number": "AMM-1313",
            "category": "economy",
        },
        headers=driver_headers,
    )
    assert vehicle.status_code == 201, vehicle.text

    async with session_factory() as session:
        driver = await session.scalar(
            select(Driver).where(Driver.user_id == uuid.UUID(driver_user_id))
        )
        driver_id = driver.id
        # **يبدأ `pending` لا `approved`** — وهذا ما تختصره بقيةُ الاختبارات
        assert driver.status is DriverStatus.PENDING

    # ── ٢. المستنداتُ الثلاثة تُرفع وتُراجَع، ثم الاعتماد ────────────────
    # كبتنٌ بلا مستنداتٍ معتمدة لا يُعتمد (9-ب)، و`approve` بابُه الوحيد
    refused = await client.post(
        f"/admin/drivers/{driver_id}/approve", headers=admin_headers
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "documents_incomplete", refused.text

    await approve_all_documents(
        client, driver_headers, admin_headers, driver_id=driver_id
    )
    activated = await client.post(
        f"/admin/drivers/{driver_id}/approve", headers=admin_headers
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "approved"

    # ── ٣. الاشتراك: مالٌ يدخل محفظتَه ثم يخرج ثمناً لخطة ────────────────
    plan_id = await ensure_plan(session_factory)
    await topup_wallet(
        client, admin_headers, driver_user_id, SUBSCRIPTION_PLAN_PRICE
    )
    bought = await client.post(
        "/subscriptions",
        json={"plan_id": str(plan_id), "idempotency_key": f"sub:{driver_id}"},
        headers=driver_headers,
    )
    assert bought.status_code == 201, bought.text
    assert bought.json()["status"] == "active"

    # **العمولةُ تُشعَل قبل الرحلة**: نسبتُها تُجمَّد لحظةَ الإنشاء، فإشعالُها
    # بعدها لا يمسّ رحلةً قائمة (SPEC §8) — وترتيبُ الخطوتين هنا هو القاعدةُ
    # نفسُها مرئيةً: ما لم يُقرَّر قبل الطلب لا يُحاسَب عليه
    commission = await client.patch(
        "/admin/settings/commission/JO",
        json={"commission_enabled": True, "commission_percent": "12.00"},
        headers=admin_headers,
    )
    assert commission.status_code == 200, commission.text

    # ── ٤. أونلاين + أوّلُ بثِّ موقع = داخل دائرة التوزيع ────────────────
    online = await client.post("/drivers/me/online", headers=driver_headers)
    assert online.status_code == 200, online.text
    await broadcast_location(client, {"headers": driver_headers}, 31.9539, 35.9106)

    # ── ٥. الراكبُ يطلب، والتوزيعُ يعرض، والكبتنُ يقبل ───────────────────
    rider = await rider_session(client, RIDER)
    await topup_wallet(client, admin_headers, rider["user"]["id"], RIDER_TOPUP)

    requested = await client.post(
        "/rides",
        json={
            "pickup": {"lat": 31.9539, "lng": 35.9106},
            "dropoff": {"lat": 31.98, "lng": 35.86},
            "vehicle_category": "economy",
        },
        headers=rider["headers"],
    )
    assert requested.status_code == 201, requested.text
    ride_id = requested.json()["id"]

    await wait_for_offer(ride_id, driver_id)
    for step in ("accept", "arrive", "start"):
        moved = await client.post(
            f"/rides/{ride_id}/{step}", headers=driver_headers
        )
        assert moved.status_code == 200, moved.text

    # ── ٦. التتبّع: بثٌّ أثناء الرحلة يترك أثراً في المسار ───────────────
    await broadcast_location(client, {"headers": driver_headers}, 31.965, 35.895)
    await broadcast_location(client, {"headers": driver_headers}, 31.975, 35.875)

    completed = await client.post(
        f"/rides/{ride_id}/complete", headers=driver_headers
    )
    assert completed.status_code == 200, completed.text
    fare = Decimal(completed.json()["final_fare"])
    assert fare > 0

    # ── ٧. الدفع: المحفظةُ لا تغطّي، فالباقي نقداً بيد الكبتن ────────────
    paid = await client.post(
        f"/rides/{ride_id}/payments",
        json={"method": "wallet", "idempotency_key": f"pay:{ride_id}"},
        headers=rider["headers"],
    )
    assert paid.status_code == 201, paid.text

    payments = (
        await client.get(f"/rides/{ride_id}/payments", headers=rider["headers"])
    ).json()
    methods = {row["method"]: row for row in payments["payments"]}
    assert "wallet" in methods, payments
    cash = methods.get("cash")
    assert cash is not None, "الرصيدُ أقلُّ من الأجرة فيُكتب الباقي نقداً"

    confirmed = await client.post(
        f"/payments/{cash['id']}/confirm", headers=driver_headers
    )
    assert confirmed.status_code == 200, confirmed.text

    # ── ٨. التقييم بعد الدفع، كما في تدفق القسم 5 ────────────────────────
    rated = await client.post(
        f"/rides/{ride_id}/ratings",
        json={"stars": 5, "comment": "رحلة موفقة"},
        headers=rider["headers"],
    )
    assert rated.status_code == 201, rated.text

    # ── ٩. السحب: طلبٌ ثم موافقةٌ ثم دفع ─────────────────────────────────
    await client.patch(
        "/drivers/me", json={"cliq_alias": "zaid.taxo"}, headers=driver_headers
    )
    lowered = await client.patch(
        "/admin/settings/wallet/JO",
        json={"min_withdrawal_amount": MIN_WITHDRAWAL_FOR_MARKET},
        headers=admin_headers,
    )
    assert lowered.status_code == 200, lowered.text

    withdrawal = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": WITHDRAWAL, "method": "cliq"},
        headers=driver_headers,
    )
    assert withdrawal.status_code == 201, withdrawal.text
    request_id = withdrawal.json()["id"]

    approved = await client.post(
        f"/admin/withdrawals/{request_id}/approve", headers=admin_headers
    )
    assert approved.status_code == 200, approved.text
    settled = await client.post(
        f"/admin/withdrawals/{request_id}/paid",
        json={"reference": "CLIQ-13-001"},
        headers=admin_headers,
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["status"] == "paid"

    # ── ١٠. الحكم: هل يُجمع الدفتر؟ ──────────────────────────────────────
    driver_entries = await _ledger(session_factory, driver_user_id)
    rider_entries = await _ledger(session_factory, rider["user"]["id"])

    kinds = [entry.type for entry in driver_entries]
    assert WalletTransactionType.SUBSCRIPTION_PAYMENT in kinds
    assert WalletTransactionType.RIDE_EARNING in kinds
    assert WalletTransactionType.COMMISSION in kinds
    assert WalletTransactionType.WITHDRAWAL in kinds

    # **الرصيدُ مجموعُ قيوده** — لا عمودَ رصيدٍ في هذا النظام
    driver_wallet = (
        await client.get("/wallet/me", headers=driver_headers)
    ).json()
    assert Decimal(driver_wallet["balance"]) == _sum(driver_entries)

    rider_wallet = (await client.get("/wallet/me", headers=rider["headers"])).json()
    assert Decimal(rider_wallet["balance"]) == _sum(rider_entries)

    # **ولا قيدَ برصيدٍ سالب** في أيِّ لحظةٍ من الرحلة كلِّها
    assert all(entry.balance_after >= 0 for entry in driver_entries + rider_entries)

    # **والنقدُ لا يمرّ بالمحفظة** (SPEC §9): ما قُبض باليد ليس قيداً
    earning = _sum(
        [e for e in driver_entries if e.type is WalletTransactionType.RIDE_EARNING]
    )
    assert earning == Decimal(methods["wallet"]["amount"]), (
        "ما دخل المحفظةَ هو ما مرّ بالمنصة وحدَه، لا الأجرةُ كاملة"
    )
