"""البقشيش (SPEC القسم 6.5، المرحلة 12-و).

قواعدُ المالك الثلاث تُختبر هنا حرفياً: **الراكبُ يموّله**، و**الكبتنُ يقبضه
كاملاً بلا عمولة**، و**القناةُ المحفظةُ وحدها**. ومعها القواعدُ التي تجعل
الميزةَ لا تكذب: ثلاثةُ شروطٍ لعرضها، وبقشيشٌ واحدٌ لكل رحلة، ونافذةٌ زمنية،
و«أربعُ نجومٍ» **في الواجهة لا في الخلفية**.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.enums import WalletTransactionType
from app.models.tip import Tip
from app.models.wallet import WalletTransaction
from tests.helpers import (
    approved_driver,
    bring_online,
    completed_ride,
    enable_features,
    rider_session,
    set_commission,
    topup_wallet,
    wallet_of,
)

JO_PRESETS = {"tip_preset_small": "0.500", "tip_preset_medium": "1.000", "tip_max": "5.000"}


async def _set_tip_amounts(
    client: AsyncClient, admin_headers: dict, **overrides: str
) -> None:
    """المبالغُ من نفس الباب الذي يضغطه المشرف — لا كتابةً في القاعدة."""
    response = await client.patch(
        "/admin/settings/payments/JO",
        json=JO_PRESETS | overrides,
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


async def _ready(client: AsyncClient, admin_headers: dict, session_factory) -> dict:
    """راكبٌ برصيد، وكبتنٌ معتمد، ورحلةٌ منتهية، والميزةُ مشتعلة."""
    await enable_features(session_factory, "wallet_enabled", "tips_enabled")
    await _set_tip_amounts(client, admin_headers)

    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    await topup_wallet(client, admin_headers, rider["user"]["id"], "20.000")
    ride = await completed_ride(client, rider["headers"], driver)
    return {"rider": rider, "driver": driver, "ride": ride}


# ------------------------------------------------------ ثلاثةُ شروطٍ للعرض


async def test_the_flag_alone_does_not_offer_tips(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    """مفتاحٌ مشتعلٌ ومبالغُ صفرٌ — فلا أزرار.

    والصفرُ «لم يُضبط» لا «بقشيشاً مقداره صفر» (قاعدةُ `wallet_settings`).
    """
    await enable_features(session_factory, "wallet_enabled", "tips_enabled")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await completed_ride(client, rider["headers"], driver)

    options = await client.get(f"/rides/{ride['id']}/tip", headers=rider["headers"])
    assert options.status_code == 200, options.text
    assert options.json()["offered"] is False
    assert options.json()["presets"] == []


async def test_amounts_alone_do_not_offer_tips(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    """مبالغُ مضبوطةٌ ومفتاحٌ مطفأ — والنداءُ مرفوضٌ لا مسكوتٌ عنه."""
    await enable_features(session_factory, "wallet_enabled")
    await _set_tip_amounts(client, admin_headers)

    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await completed_ride(client, rider["headers"], driver)

    assert (
        await client.get(f"/rides/{ride['id']}/tip", headers=rider["headers"])
    ).json()["offered"] is False

    refused = await client.post(
        f"/rides/{ride['id']}/tip", json={"amount": "0.500"}, headers=rider["headers"]
    )
    assert refused.status_code == 403
    assert refused.json()["code"] == "tips_unavailable"


async def test_a_disabled_wallet_hides_tips_since_it_is_the_only_channel(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    """المحفظةُ هي القناة، فإطفاؤها يُخفي الميزة — لا يعطّل زرّاً."""
    await enable_features(session_factory, "tips_enabled")
    await _set_tip_amounts(client, admin_headers)

    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)
    ride = await completed_ride(client, rider["headers"], driver)

    assert (
        await client.get(f"/rides/{ride['id']}/tip", headers=rider["headers"])
    ).json()["offered"] is False


async def test_all_three_together_offer_the_presets(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    ready = await _ready(client, admin_headers, session_factory)

    options = await client.get(
        f"/rides/{ready['ride']['id']}/tip", headers=ready["rider"]["headers"]
    )
    body = options.json()
    assert body["offered"] is True
    assert body["presets"] == ["0.500", "1.000"]
    assert body["max_amount"] == "5.000"
    assert body["currency"] == "JOD"
    assert body["given"] is None


# ------------------------------------------------------------- المال


async def test_the_rider_pays_and_the_driver_keeps_all_of_it(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    """**بلا عمولةٍ عليه** — ولو كانت العمولةُ على كل الرحلات.

    وهو الاختبارُ الذي يفشل لو أُضيف البقشيشُ إلى وعاء العمولة يوماً.
    """
    await set_commission(session_factory, "20", applies_to="all_rides")
    ready = await _ready(client, admin_headers, session_factory)
    rider, driver, ride = ready["rider"], ready["driver"], ready["ride"]

    before_rider = Decimal((await wallet_of(client, rider["headers"]))["balance"])
    before_driver = Decimal((await wallet_of(client, driver["headers"]))["balance"])

    given = await client.post(
        f"/rides/{ride['id']}/tip", json={"amount": "1.000"}, headers=rider["headers"]
    )
    assert given.status_code == 201, given.text
    assert given.json()["amount"] == "1.000"
    assert given.json()["currency"] == "JOD"

    after_rider = Decimal((await wallet_of(client, rider["headers"]))["balance"])
    after_driver = Decimal((await wallet_of(client, driver["headers"]))["balance"])
    assert before_rider - after_rider == Decimal("1.000")
    # **كاملاً**: لا نصفَ دينارٍ يذهب عمولةً ولو كان النطاق `all_rides`
    assert after_driver - before_driver == Decimal("1.000")

    async with session_factory() as session:
        kinds = (
            await session.scalars(
                select(WalletTransaction.type).where(
                    WalletTransaction.ride_id == ride["id"],
                    WalletTransaction.type.in_(
                        [
                            WalletTransactionType.TIP,
                            WalletTransactionType.TIP_PAYMENT,
                            WalletTransactionType.COMMISSION,
                        ]
                    ),
                )
            )
        ).all()
        assert sorted(k.value for k in kinds) == ["tip", "tip_payment"]


async def test_the_tip_shows_as_its_own_line_in_earnings(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    """سطرٌ مستقل — فما دخل المحفظة وما خرج عمولةً يتّسقان لمن يجمعهما بيده."""
    ready = await _ready(client, admin_headers, session_factory)
    await client.post(
        f"/rides/{ready['ride']['id']}/tip",
        json={"amount": "1.000"},
        headers=ready["rider"]["headers"],
    )

    earnings = await client.get(
        "/drivers/me/earnings", params={"period": "today"}, headers=ready["driver"]["headers"]
    )
    assert earnings.status_code == 200, earnings.text
    body = earnings.json()
    assert body["tips"] == "1.000"
    # وداخلٌ في الصافي: مالٌ وصل المحفظةَ فعلاً
    assert Decimal(body["net"]) == Decimal(body["wallet_earnings"]) + Decimal(
        "1.000"
    ) - Decimal(body["commission"])


async def test_an_empty_wallet_is_refused_not_overdrawn(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    await enable_features(session_factory, "wallet_enabled", "tips_enabled")
    await _set_tip_amounts(client, admin_headers)
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = await rider_session(client)  # بلا شحن
    ride = await completed_ride(client, rider["headers"], driver)

    refused = await client.post(
        f"/rides/{ride['id']}/tip", json={"amount": "1.000"}, headers=rider["headers"]
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "insufficient_balance"

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Tip)) == 0


async def test_the_cap_is_enforced(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    """سقفٌ يحرس من إصبعٍ تزلّ على شاشةٍ في سيارة."""
    ready = await _ready(client, admin_headers, session_factory)
    refused = await client.post(
        f"/rides/{ready['ride']['id']}/tip",
        json={"amount": "9.000"},
        headers=ready["rider"]["headers"],
    )
    assert refused.status_code == 422
    assert "5.000" in refused.json()["message"]


# --------------------------------------------------------- من ومتى


async def test_one_tip_per_ride(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    ready = await _ready(client, admin_headers, session_factory)
    ride, rider = ready["ride"], ready["rider"]

    first = await client.post(
        f"/rides/{ride['id']}/tip", json={"amount": "0.500"}, headers=rider["headers"]
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        f"/rides/{ride['id']}/tip", json={"amount": "0.500"}, headers=rider["headers"]
    )
    assert second.status_code == 409
    assert second.json()["code"] == "tip_already_given"

    # والشاشةُ تعرض ما أُعطي بدل أزرارٍ تُرفض عند الضغط
    options = await client.get(f"/rides/{ride['id']}/tip", headers=rider["headers"])
    assert options.json()["given"]["amount"] == "0.500"


async def test_a_stranger_cannot_tip_someone_elses_ride(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    ready = await _ready(client, admin_headers, session_factory)
    other = await rider_session(
        client,
        {
            "phone": "0795550001",
            "name": "راكبٌ آخر",
            "password": "SuperSecret123",
            "country_code": "JO",
            "role": "rider",
        },
    )
    refused = await client.post(
        f"/rides/{ready['ride']['id']}/tip",
        json={"amount": "0.500"},
        headers=other["headers"],
    )
    assert refused.status_code == 404


async def test_an_old_ride_is_outside_the_window(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    """اثنتان وسبعون ساعة — وخصمٌ بعد ثلاثة أسابيع يفاجئ صاحبَه."""
    from app.models.ride import Ride
    from app.services import tips as tips_service

    ready = await _ready(client, admin_headers, session_factory)
    async with session_factory() as session:
        ride = await session.get(Ride, ready["ride"]["id"])
        ride.completed_at = datetime.now(UTC) - timedelta(
            hours=tips_service.TIP_WINDOW_HOURS + 1
        )
        await session.commit()

    refused = await client.post(
        f"/rides/{ready['ride']['id']}/tip",
        json={"amount": "0.500"},
        headers=ready["rider"]["headers"],
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "tip_not_allowed"


async def test_a_low_rating_does_not_block_a_tip(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    """**«أربعُ نجوم» تضييقٌ في الواجهة لا قيدٌ في الخلفية.**

    من قيّم ثلاثاً وأراد أن يشكر الكبتن على حمل حقيبةٍ لا يُردّ بقاعدةٍ وُضعت
    لكي لا نسأل في لحظةٍ سيئة — وربطُ المال بتقييمٍ يُعدَّل يجعله تابعاً لرأيٍ
    متغيّر. وهذا الاختبار هو ما يمنع «إكمالاً» يضيف الشرطَ إلى الخلفية.
    """
    ready = await _ready(client, admin_headers, session_factory)
    rated = await client.post(
        f"/rides/{ready['ride']['id']}/ratings",
        json={"stars": 3},
        headers=ready["rider"]["headers"],
    )
    assert rated.status_code == 201, rated.text

    given = await client.post(
        f"/rides/{ready['ride']['id']}/tip",
        json={"amount": "0.500"},
        headers=ready["rider"]["headers"],
    )
    assert given.status_code == 201, given.text


async def test_the_driver_is_told(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
) -> None:
    """إشعارٌ بقيمٍ خام — لا جملةٌ مصوغة ولا رقمٌ منسَّق (القسم 10)."""
    from app.models.notification import UserNotification

    ready = await _ready(client, admin_headers, session_factory)
    await client.post(
        f"/rides/{ready['ride']['id']}/tip",
        json={"amount": "1.000"},
        headers=ready["rider"]["headers"],
    )

    async with session_factory() as session:
        row = await session.scalar(
            select(UserNotification).where(UserNotification.kind == "tip_received")
        )
        assert row is not None
        assert row.data["amount"] == "1.000"
        assert row.data["currency"] == "JOD"
        assert row.data["ride_id"] == ready["ride"]["id"]
