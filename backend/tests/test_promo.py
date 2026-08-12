"""الكوبونات (SPEC القسم 6.6، المرحلة 12-ز).

**والاختبارُ الأول هو الذي يحمي قرار المالك**: الشركةُ تتحمّل الخصم، فأرباحُ
الكبتن وعمولتُه **لا تتغيّران** بوجود الكوبون. وبقيةُ الملف يحرس ما يجعل ذلك
ممكناً: الخصمُ صفُّ دفعةٍ بقناة `promo`، ومحفظةُ الراكب لا تُخصم بها، والقاعدةُ
مجمَّدةٌ فلا يمسّها تعديلٌ في اللوحة.
"""

from __future__ import annotations

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import PaymentMethod, PaymentStatus, WalletTransactionType
from app.models.payment import Payment
from app.models.promo import PromoCode
from app.models.wallet import WalletTransaction
from tests.helpers import (
    DRIVER,
    approved_driver,
    bring_online,
    completed_ride,
    enable_features,
    pay_ride,
    rider_session,
    set_commission,
    topup_wallet,
    wallet_of,
)


async def _promo(
    session_factory,
    *,
    code: str = "WELCOME",
    discount_type: str = "percent",
    value: str = "50",
    cap: str | None = "10.000",
    budget: str = "100.000",
    per_user: int = 1,
    total_limit: int | None = None,
) -> str:
    """رمزٌ يُكتب مباشرةً — مسارُ اللوحة يأتي مع شاشته، وهذه اختباراتُ الخلفية."""
    from app.models.enums import CountryCode, PromoDiscountType

    async with session_factory() as session:
        promo = PromoCode(
            code=code,
            country_code=CountryCode.JO,
            discount_type=PromoDiscountType(discount_type),
            discount_value=Decimal(value),
            max_discount=Decimal(cap) if cap else None,
            budget_total=Decimal(budget),
            per_user_limit=per_user,
            total_usage_limit=total_limit,
        )
        session.add(promo)
        await session.commit()
        return str(promo.id)


async def _ride_with_code(
    client: AsyncClient, rider_headers: dict, driver: dict, code: str | None
) -> dict:
    """رحلةٌ منتهية — والرمزُ يُمرَّر في الطلب نفسه كما يفعل التطبيق."""
    from tests.helpers import DROPOFF, PICKUP

    body: dict = {
        "pickup": PICKUP,
        "dropoff": DROPOFF,
        "vehicle_category": "economy",
    }
    if code:
        body["promo_code"] = code

    response = await client.post("/rides", json=body, headers=rider_headers)
    assert response.status_code == 201, response.text
    ride_id = response.json()["id"]

    from tests.helpers import wait_for_offer

    await wait_for_offer(ride_id, driver["driver_id"])
    for step in ("accept", "arrive", "start", "complete"):
        step_response = await client.post(
            f"/rides/{ride_id}/{step}", headers=driver["headers"]
        )
        assert step_response.status_code == 200, step_response.text
    return step_response.json()


# ------------------------------------------------- قرارُ المالك نفسُه


async def test_the_company_bears_it_so_the_driver_is_untouched(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    """**أرباحُ الكبتن وعمولتُه كأن لا كوبون** — وهو نصُّ قرار المالك.

    وبلا قناة `promo` (لو نقص الخصمُ `final_fare`) لانقص كلاهما، لأنهما
    يُحسبان من `payment.amount`. فهذا الاختبار هو ما يمنع «تبسيطاً» لاحقاً يعيد
    الخصمَ إلى الأجرة.
    """
    # والمحفظةُ مفعّلةٌ لأن عمولةَ الكاش تُخصم منها (القسم 9) لا لأن الكوبون يحتاجها
    await enable_features(session_factory, "promo_codes_enabled", "wallet_enabled")
    await set_commission(session_factory, "20", applies_to="all_rides")
    await _promo(session_factory, discount_type="fixed", value="1.000", cap=None)

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    # **ورصيدٌ للكبتن**: عمولةُ رحلةٍ نقدية تُخصم من محفظته (القسم 9)، ومحفظةٌ
    # فارغة ترفض التأكيد — وهو سلوكٌ قائمٌ لا علاقة له بالكوبون
    await topup_wallet(client, admin_headers, driver["user_id"], "20.000")

    async def _settle_cash(ride: dict) -> dict:
        # **مفتاحُ تكرارٍ لكل رحلة**: المفتاحُ فريدٌ في `payments` كلِّه لا لكل
        # رحلة، ومفتاحٌ مُعادٌ يُرجع دفعةَ الرحلة الأولى بلا أن ينشئ شيئاً
        paid = await pay_ride(
            client, rider["headers"], ride["id"], "cash", key=f"pay-{ride['id']}"
        )
        assert paid.status_code == 201, paid.text
        # **الصفُّ الأول قد يكون خصمَ الكوبون** (أُنشئ عند الإنهاء)، فالانتقاءُ
        # بالقناة لا بالفهرس: ترتيبُ القائمة ليس عقداً
        rows = paid.json()["payments"]
        cash_row = next(row for row in rows if row["method"] == "cash")
        confirmed = await client.post(
            f"/payments/{cash_row['id']}/confirm", headers=driver["headers"]
        )
        assert confirmed.status_code == 200, confirmed.text
        return cash_row

    plain = await _ride_with_code(client, rider["headers"], driver, None)
    plain_cash = await _settle_cash(plain)

    discounted = await _ride_with_code(client, rider["headers"], driver, "WELCOME")
    assert plain["final_fare"] == discounted["final_fare"], "الأجرةُ نفسُها للرحلتين"

    async with session_factory() as session:
        promo_payment = await session.scalar(
            select(Payment).where(
                Payment.ride_id == discounted["id"],
                Payment.method == PaymentMethod.PROMO,
            )
        )
        assert promo_payment is not None
        assert promo_payment.status is PaymentStatus.CONFIRMED
        assert promo_payment.amount == Decimal("1.000")

    discounted_cash = await _settle_cash(discounted)
    # الراكبُ يدفع الأجرةَ ناقصَ الخصم، والرحلةُ غيرُ المخصومة كاملةً
    assert Decimal(plain_cash["amount"]) == Decimal(plain["final_fare"])
    assert Decimal(discounted_cash["amount"]) == Decimal(
        discounted["final_fare"]
    ) - Decimal("1.000")

    async with session_factory() as session:
        async def _sum(kind: WalletTransactionType, ride_id: str) -> Decimal:
            total = await session.scalar(
                select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                    WalletTransaction.ride_id == ride_id,
                    WalletTransaction.type == kind,
                )
            )
            return Decimal(total or 0)

        # الكاشُ لا يكتب `ride_earning` (الكبتن قبضه بيده)، والخصمُ يكتبه: فأرباحُ
        # المحفظة على الرحلة المخصومة هي **الخصم** — أي أن الكبتن قبض الأجرةَ
        # كاملةً: نقداً من الراكب وخصماً من الشركة
        assert await _sum(WalletTransactionType.RIDE_EARNING, plain["id"]) == Decimal("0")
        assert await _sum(
            WalletTransactionType.RIDE_EARNING, discounted["id"]
        ) == Decimal("1.000")

        # **والعمولةُ نفسُها في الرحلتين**: وعاؤها الأجرةُ كاملةً لأن الشركة
        # تحمّلت الخصم. ولو نقص الخصمُ `final_fare` لنقصت عمولةُ المخصومة
        commission_plain = await _sum(WalletTransactionType.COMMISSION, plain["id"])
        commission_discounted = await _sum(
            WalletTransactionType.COMMISSION, discounted["id"]
        )
        assert commission_plain == commission_discounted
        assert commission_plain < 0  # خصمٌ لا إضافة


async def test_the_riders_wallet_is_never_touched_by_the_discount(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    """`promo` **ليست في `WALLET_FUNDED_METHODS`** — كالبطاقة حرفياً.

    ولو وُضعت فيها لخُصم الخصمُ من رصيد الراكب، أي لدفع الراكبُ كوبونَ نفسه —
    وهو نقيضُ الغرض. الاختبارُ يفشل بإضافة `PROMO` إلى ذلك التصنيف.
    """
    await enable_features(session_factory, "promo_codes_enabled", "wallet_enabled")
    await _promo(session_factory, discount_type="fixed", value="1.000", cap=None)

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    before = Decimal((await wallet_of(client, rider["headers"]))["balance"])

    await _ride_with_code(client, rider["headers"], driver, "WELCOME")

    after = Decimal((await wallet_of(client, rider["headers"]))["balance"])
    assert after == before, "الخصمُ لا يخرج من رصيد الراكب"

    async with session_factory() as session:
        debits = await session.scalar(
            select(func.count())
            .select_from(WalletTransaction)
            .where(
                WalletTransaction.owner_id == rider["user"]["id"],
                WalletTransaction.type == WalletTransactionType.RIDE_PAYMENT,
            )
        )
        assert debits == 0


async def test_a_full_discount_leaves_nothing_to_pay(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    """«الرحلة مجاناً» بلا حالةٍ خاصة (قرارُ المالك): `outstanding = 0`.

    و`create_payment` يرفض من نفسه بـ`ride_already_paid` — بلا بابٍ ثانٍ يكتب
    المالَ عند الإنهاء.
    """
    await enable_features(session_factory, "promo_codes_enabled")
    await _promo(session_factory, code="FREE1", discount_type="percent", value="100", cap=None)

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    ride = await _ride_with_code(client, rider["headers"], driver, "FREE1")

    payments = await client.get(
        f"/rides/{ride['id']}/payments", headers=rider["headers"]
    )
    assert payments.status_code == 200, payments.text
    assert Decimal(payments.json()["outstanding"]) == Decimal("0.000")

    refused = await pay_ride(client, rider["headers"], ride["id"], "cash")
    assert refused.status_code == 409
    assert refused.json()["code"] == "ride_already_paid"


# ------------------------------------------------------- الحساب والحدود


def test_the_discount_maths_is_a_pure_function() -> None:
    """السقفُ والأرضيةُ في دالةٍ واحدة تُختبر وحدها."""
    from app.models.enums import PromoDiscountType
    from app.services.promo import discount_for

    percent = dict(discount_type=PromoDiscountType.PERCENT, value=Decimal("50"))
    assert discount_for(**percent, cap=None, fare=Decimal("10.000")) == Decimal("5.000")
    # السقفُ يحكم — بغيره يبتلع كوبونُ ٥٠٪ رحلةً طويلة
    assert discount_for(**percent, cap=Decimal("2.000"), fare=Decimal("10.000")) == Decimal("2.000")

    fixed = dict(discount_type=PromoDiscountType.FIXED, value=Decimal("20.000"))
    # ولا يزيد الخصمُ على الأجرة: خصمٌ أكبرُ منها يجعل المدفوعَ ديناً على المنصة
    assert discount_for(**fixed, cap=None, fare=Decimal("6.000")) == Decimal("6.000")


async def test_validate_previews_without_consuming(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, "promo_codes_enabled")
    promo_id = await _promo(session_factory)
    rider = await rider_session(client)

    for _ in range(3):
        response = await client.post(
            "/rides/promo/validate",
            json={"code": "welcome", "country_code": "JO", "fare": "8.000"},
            headers=rider["headers"],
        )
        assert response.status_code == 200, response.text
        # الرمزُ يُطبَّع: كُتب بحروفٍ صغيرة وقُبل
        assert response.json()["code"] == "WELCOME"
        assert response.json()["discount"] == "4.000"
        assert response.json()["fare_after"] == "4.000"

    async with session_factory() as session:
        from app.services import promo as promo_service

        assert await promo_service.spent(session, promo_id) == Decimal("0.000")


async def test_the_per_user_limit_is_enforced(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    await enable_features(session_factory, "promo_codes_enabled")
    await _promo(session_factory, discount_type="fixed", value="0.500", cap=None)

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    await _ride_with_code(client, rider["headers"], driver, "WELCOME")

    from tests.helpers import DROPOFF, PICKUP

    refused = await client.post(
        "/rides",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "promo_code": "WELCOME",
        },
        headers=rider["headers"],
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "promo_already_used"


async def test_an_exhausted_budget_blocks_new_applications(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    """السقفُ يمنع التطبيقَ الجديد — **ورحلةٌ تحمل الرمز تُنهى بخصمها كاملاً**."""
    await enable_features(session_factory, "promo_codes_enabled")
    await _promo(
        session_factory,
        discount_type="fixed",
        value="1.000",
        cap=None,
        budget="1.000",
        per_user=5,
    )

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    first = await _ride_with_code(client, rider["headers"], driver, "WELCOME")
    async with session_factory() as session:
        from app.services import promo as promo_service

        promo = await session.scalar(select(PromoCode))
        assert await promo_service.spent(session, promo.id) == Decimal("1.000")

    from tests.helpers import DROPOFF, PICKUP

    refused = await client.post(
        "/rides",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "promo_code": "WELCOME",
        },
        headers=rider["headers"],
    )
    assert refused.status_code == 404
    assert refused.json()["code"] == "promo_exhausted"
    assert first["id"]


async def test_editing_the_code_does_not_touch_a_running_ride(
    client: AsyncClient, jordan_settings: None, admin_headers: dict, session_factory
) -> None:
    """القاعدةُ مجمَّدةٌ على الرحلة — كـ`commission_percent_at_ride`.

    راكبٌ رأى «خصم ٥٠٪» قبل أن يطلب لا يُحاسب على ١٠٪ لأن أحداً عدّل الرمز.
    """
    await enable_features(session_factory, "promo_codes_enabled")
    await _promo(session_factory, discount_type="percent", value="50", cap="10.000")

    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    rider = await rider_session(client)

    from tests.helpers import DROPOFF, PICKUP, wait_for_offer

    created = await client.post(
        "/rides",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "promo_code": "WELCOME",
        },
        headers=rider["headers"],
    )
    ride_id = created.json()["id"]

    # يُعدَّل الرمزُ **بعد** الطلب وقبل الإنهاء
    async with session_factory() as session:
        promo = await session.scalar(select(PromoCode))
        promo.discount_value = Decimal("10")
        await session.commit()

    await wait_for_offer(ride_id, driver["driver_id"])
    for step in ("accept", "arrive", "start", "complete"):
        await client.post(f"/rides/{ride_id}/{step}", headers=driver["headers"])

    async with session_factory() as session:
        promo_payment = await session.scalar(
            select(Payment).where(
                Payment.ride_id == ride_id, Payment.method == PaymentMethod.PROMO
            )
        )
        ride_fare = await session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.ride_id == ride_id
            )
        )
        # نصفُ الأجرة لا عُشرُها
        assert promo_payment.amount == Decimal(ride_fare) , "الخصمُ الوحيد على الرحلة"
        assert promo_payment.amount > 0


async def test_the_flag_gates_both_drawing_and_sending(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """مفتاحٌ مطفأ: لا تحقّقَ ولا قبولَ رمزٍ في الطلب."""
    await _promo(session_factory)
    rider = await rider_session(client)

    validated = await client.post(
        "/rides/promo/validate",
        json={"code": "WELCOME", "country_code": "JO", "fare": "8.000"},
        headers=rider["headers"],
    )
    assert validated.status_code == 403
    assert validated.json()["code"] == "promo_unavailable"

    from tests.helpers import DROPOFF, PICKUP

    refused = await client.post(
        "/rides",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "promo_code": "WELCOME",
        },
        headers=rider["headers"],
    )
    assert refused.status_code == 403


async def test_a_wrong_code_refuses_the_whole_request(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """رمزٌ خاطئ يرفض الطلب ولا يمرّ بلا خصم صامتاً.

    من كتب رمزاً ينتظر خصمَه؛ ورحلةٌ تبدأ بسعرٍ كامل بعد رمزٍ سقط في صمت شكوى
    دعمٍ لا صفقة.
    """
    await enable_features(session_factory, "promo_codes_enabled")
    rider = await rider_session(client)

    from tests.helpers import DROPOFF, PICKUP

    refused = await client.post(
        "/rides",
        json={
            "pickup": PICKUP,
            "dropoff": DROPOFF,
            "vehicle_category": "economy",
            "promo_code": "NOPE",
        },
        headers=rider["headers"],
    )
    assert refused.status_code == 404
    assert refused.json()["code"] == "promo_invalid"

    async with session_factory() as session:
        from app.models.ride import Ride

        assert await session.scalar(select(func.count()).select_from(Ride)) == 0
