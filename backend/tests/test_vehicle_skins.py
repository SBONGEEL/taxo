"""مركباتُ الكراج والمتجر — الخدمةُ وأبوابُها (2026-08-22).

**وما يُحرس هنا ثلاثةٌ لا واحد**: أن المال يُخصم من الدفتر لا من عمود، وأن
**سببَ المنع واحدٌ بترتيب العقد**، وأن **الندرةَ لا تُنشر قبل القبول** —
وهي الوحيدةُ التي لو سقطت لَما ظهر شيءٌ على شاشة، بل صار غيابُ المركبة
بطاقةَ تعريفٍ لصاحبها (الشكلُ الثالثَ عشر).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.driver import Driver
from app.models.enums import CountryCode, WalletOwnerType, WalletTransactionType
from app.models.vehicle_skin import (
    RARITY_COMMON,
    RARITY_LEGENDARY,
    RARITY_PREMIUM,
    DriverVehicleSkin,
    VehicleSkin,
    VehicleSkinPrice,
)
from app.models.wallet import WalletTransaction
from tests.helpers import (
    approved_driver,
    ensure_plan,
    bring_online,
    enable_features,
    rider_session,
    topup_wallet,
)

SKINS = "/vehicle-skins"


# ------------------------------------------------------------------- تجهيز


async def make_skin(
    session_factory,
    *,
    name: str,
    rarity: str = RARITY_PREMIUM,
    price: str | None = "5.000",
    country: CountryCode = CountryCode.JO,
    **fields,
) -> uuid.UUID:
    """صفُّ كتالوجٍ للاختبار — **يُكتب مباشرةً لأن الكاتبَ هو اللوحة**.

    ولا يخالف قاعدةَ «لا مساعدَ يختصر مساراً حقيقياً»: مسارُ الإنشاء بابُ
    مشرفٍ يبنيه وكيلٌ آخر، وما يُقاس هنا **قراءةُ الكتالوج وشراؤه** لا كتابتُه.
    """
    async with session_factory() as session:
        skin = VehicleSkin(name=name, rarity=rarity, asset_key=name, **fields)
        session.add(skin)
        await session.flush()
        if price is not None:
            session.add(
                VehicleSkinPrice(
                    skin_id=skin.id, country_code=country, price=Decimal(price)
                )
            )
        await session.commit()
        return skin.id


@pytest.fixture
async def ready(client: AsyncClient, admin_headers: dict, session_factory) -> dict:
    """كبتنٌ معتمدٌ برصيدٍ، والمفتاحُ مُشعَل."""
    await enable_features(session_factory, "wallet_enabled", "vehicle_skins_enabled")
    driver = await approved_driver(client, session_factory)
    await topup_wallet(client, admin_headers, driver["user_id"], "20.000")
    return driver


# --------------------------------------------------------------- المتجرُ والكراج


async def test_the_store_lists_only_what_this_market_prices(
    client: AsyncClient, session_factory, ready
):
    """**بطاقةٌ بلا سعرٍ زرُّها لا يفعل شيئاً** — فلا تُعرض أصلاً."""
    priced = await make_skin(session_factory, name="مسعّرة", price="5.000")
    await make_skin(session_factory, name="بلا-سعر", price=None)
    await make_skin(
        session_factory, name="سعرٌ-ليبي", price="9.000", country=CountryCode.LY
    )

    response = await client.get(f"{SKINS}/store", headers=ready["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert [row["id"] for row in body["skins"]] == [str(priced)]
    assert body["balance"] == "20.000"
    assert body["currency"] == "JOD"


async def test_the_store_is_ordered_by_rarity_then_name(
    client: AsyncClient, session_factory, ready
):
    """**الترتيبُ عقدٌ لا ذوق**: شاشتان ترتّبانه اختلافاً تعنيان بـ«الثالثة»
    مركبتين."""
    await make_skin(session_factory, name="ياء", rarity=RARITY_COMMON)
    await make_skin(session_factory, name="ألف", rarity=RARITY_LEGENDARY)
    await make_skin(session_factory, name="باء", rarity=RARITY_COMMON)

    body = (await client.get(f"{SKINS}/store", headers=ready["headers"])).json()
    assert [row["name"] for row in body["skins"]] == ["باء", "ياء", "ألف"]


async def test_remaining_is_counted_not_stored(
    client: AsyncClient, session_factory, ready
):
    """«المتبقّي» = السقفُ ناقص المالكين — **ولا عمودَ عدّاد**."""
    skin = await make_skin(session_factory, name="محدودة", max_supply=3)

    body = (await client.get(f"{SKINS}/store", headers=ready["headers"])).json()
    assert body["skins"][0]["remaining"] == 3
    assert body["skins"][0]["owners_count"] == 0

    bought = await client.post(f"{SKINS}/{skin}/buy", headers=ready["headers"])
    assert bought.status_code == 200, bought.text

    body = (await client.get(f"{SKINS}/store", headers=ready["headers"])).json()
    assert body["skins"][0]["remaining"] == 2
    assert body["skins"][0]["owners_count"] == 1
    # **وبلا سقفٍ لا حدَّ** — و`null` ليست صفراً
    unlimited = (
        await client.get(f"{SKINS}/store", headers=ready["headers"])
    ).json()
    assert unlimited["skins"][0]["remaining"] == 2

    await make_skin(session_factory, name="بلا-حدّ")
    body = (await client.get(f"{SKINS}/store", headers=ready["headers"])).json()
    rows = {row["name"]: row for row in body["skins"]}
    assert rows["بلا-حدّ"]["remaining"] is None


# --------------------------------------------------------------- سببُ المنع


async def test_the_blocked_reason_follows_the_contract_order(
    client: AsyncClient, session_factory, ready
):
    """**سببٌ واحدٌ لا أكثر، وأولُ ما ينطبق** — والترتيبُ من العقد نفسِه.

    ولو أُعيد ترتيبُها لقال بابان لكبتنٍ واحدٍ سببين لرفضٍ واحد.
    """
    past = datetime.now(UTC) - timedelta(days=1)
    cases = {
        # نفدت **ومقفولةٌ بالمستوى معاً** — والنفادُ يسبق
        "نفدت": dict(max_supply=1, level_required=9),
        # مقفولةٌ **وخارج الموسم معاً** — والمستوى يسبق
        "مقفولة": dict(level_required=9, valid_until=past),
        "موسم": dict(valid_until=past),
        "رصيد": dict(price="99.000"),
        "متاحة": dict(),
    }
    ids = {}
    for name, fields in cases.items():
        price = fields.pop("price", "5.000")
        ids[name] = await make_skin(session_factory, name=name, price=price, **fields)

    # يُستنفد سقفُ «نفدت» بمالكٍ آخر
    other = await approved_driver(
        client,
        session_factory,
        {
            "phone": "+962791700009",
            "password": "Driver12345",
            "name": "كبتنٌ آخر",
            "country_code": "JO",
            "role": "driver",
        },
        plate_number="AMM-9191",
    )
    async with session_factory() as session:
        session.add(
            DriverVehicleSkin(
                driver_id=other["driver_id"], skin_id=ids["نفدت"], source="grant"
            )
        )
        await session.commit()

    body = (await client.get(f"{SKINS}/store", headers=ready["headers"])).json()
    rows = {row["name"]: row["blocked_reason"] for row in body["skins"]}
    assert rows == {
        "نفدت": "sold_out",
        "مقفولة": "level_locked",
        "موسم": "out_of_season",
        "رصيد": "insufficient_balance",
        "متاحة": None,
    }


async def test_an_owned_skin_reads_owned_before_anything_else(
    client: AsyncClient, session_factory, ready
):
    """«مملوكة» تسبق الجميع — ومن يملك ما نفد لا يُقال له «نفدت»."""
    skin = await make_skin(session_factory, name="مملوكة", max_supply=1)
    bought = await client.post(f"{SKINS}/{skin}/buy", headers=ready["headers"])
    assert bought.status_code == 200, bought.text

    body = (await client.get(f"{SKINS}/store", headers=ready["headers"])).json()
    row = body["skins"][0]
    assert row["remaining"] == 0
    assert row["owned"] is True
    assert row["blocked_reason"] == "owned"


# ------------------------------------------------------------------- الشراء


async def test_buying_writes_a_ledger_entry_and_freezes_the_price(
    client: AsyncClient, session_factory, ready
):
    """**المالُ قيدٌ في الدفتر**، والسعرُ يُجمَّد على صفِّ المِلكيّة."""
    skin = await make_skin(session_factory, name="زرقاء", price="7.500")

    response = await client.post(f"{SKINS}/{skin}/buy", headers=ready["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["balance_after"] == "12.500"
    assert body["currency"] == "JOD"
    assert body["skin"]["owned"] is True

    async with session_factory() as session:
        entry = await session.scalar(
            select(WalletTransaction).where(
                WalletTransaction.owner_id == uuid.UUID(ready["user_id"]),
                WalletTransaction.type == WalletTransactionType.SKIN_PURCHASE,
            )
        )
        row = await session.scalar(
            select(DriverVehicleSkin).where(DriverVehicleSkin.skin_id == skin)
        )
    assert entry is not None, "لا قيدَ للشراء في الدفتر"
    assert entry.owner_type is WalletOwnerType.DRIVER
    assert entry.amount == Decimal("-7.500")
    assert entry.balance_after == Decimal("12.500")
    assert row.source == "purchase"
    assert row.price_paid == Decimal("7.500")
    assert row.currency == "JOD"

    # **تعديلُ السعر لا يحرّك ما دُفع أمس**
    async with session_factory() as session:
        price = await session.get(VehicleSkinPrice, (skin, CountryCode.JO))
        price.price = Decimal("20.000")
        await session.commit()
        frozen = await session.scalar(
            select(DriverVehicleSkin.price_paid).where(
                DriverVehicleSkin.skin_id == skin
            )
        )
    assert frozen == Decimal("7.500")


async def test_an_empty_wallet_is_refused_and_writes_nothing(
    client: AsyncClient, session_factory, ready
):
    """**رصيدٌ لا يكفي يُرفض ولا يترك صفَّ مِلكيّة** — والمعاملةُ ترتدّ كاملة."""
    skin = await make_skin(session_factory, name="غالية", price="99.000")

    response = await client.post(f"{SKINS}/{skin}/buy", headers=ready["headers"])
    # **الرمزُ لا الرقمُ هو العقد** — و409 هو ما يردّه `InsufficientBalance`
    # في هذا المشروع، مقيساً لا مفترضاً
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "insufficient_balance"

    async with session_factory() as session:
        owned = await session.scalar(
            select(func.count()).select_from(DriverVehicleSkin)
        )
        entries = await session.scalar(
            select(func.count())
            .select_from(WalletTransaction)
            .where(WalletTransaction.type == WalletTransactionType.SKIN_PURCHASE)
        )
    assert owned == 0, "صفُّ مِلكيّةٍ بقي بعد رفضِ الدفع"
    assert entries == 0


async def test_the_named_refusals(client: AsyncClient, session_factory, ready):
    """**أربعةُ رفضٍ بأربعة رموز** — رسالةٌ واحدةٌ تجعله يعيد المحاولة بلا سبب."""
    owned = await make_skin(session_factory, name="مكرّرة")
    assert (
        await client.post(f"{SKINS}/{owned}/buy", headers=ready["headers"])
    ).status_code == 200
    again = await client.post(f"{SKINS}/{owned}/buy", headers=ready["headers"])
    assert again.status_code == 409
    assert again.json()["code"] == "skin_already_owned"

    locked = await make_skin(session_factory, name="مستوى", level_required=5)
    response = await client.post(f"{SKINS}/{locked}/buy", headers=ready["headers"])
    assert response.status_code == 403
    assert response.json()["code"] == "skin_level_locked"

    past = datetime.now(UTC) - timedelta(days=1)
    gone = await make_skin(session_factory, name="منتهية", valid_until=past)
    response = await client.post(f"{SKINS}/{gone}/buy", headers=ready["headers"])
    assert response.status_code == 409
    assert response.json()["code"] == "skin_unavailable"

    free = await make_skin(session_factory, name="بلا-ثمن", price=None)
    response = await client.post(f"{SKINS}/{free}/buy", headers=ready["headers"])
    assert response.status_code == 409
    assert response.json()["code"] == "skin_unavailable"


# ------------------------------------------------------- التفعيلُ والورقة


async def test_activating_requires_owning(
    client: AsyncClient, session_factory, ready
):
    skin = await make_skin(session_factory, name="غيرُ-مملوكة")
    response = await client.put(
        f"{SKINS}/active", json={"skin_id": str(skin)}, headers=ready["headers"]
    )
    assert response.status_code == 403
    assert response.json()["code"] == "skin_not_owned"

    assert (
        await client.post(f"{SKINS}/{skin}/buy", headers=ready["headers"])
    ).status_code == 200
    response = await client.put(
        f"{SKINS}/active", json={"skin_id": str(skin)}, headers=ready["headers"]
    )
    assert response.status_code == 204, response.text

    garage = (await client.get(f"{SKINS}/garage", headers=ready["headers"])).json()
    assert garage["active_skin_id"] == str(skin)
    assert garage["skins"][0]["active"] is True


async def test_the_celebration_sheet_is_shown_once(
    client: AsyncClient, session_factory, ready
):
    """**تُعرض مرةً ثم تُختم** — و`seen_at` هو الختم، لا حقلٌ في التطبيق."""
    skin = await make_skin(session_factory, name="احتفال")
    assert (
        await client.post(f"{SKINS}/{skin}/buy", headers=ready["headers"])
    ).status_code == 200

    garage = (await client.get(f"{SKINS}/garage", headers=ready["headers"])).json()
    assert garage["celebrate"] is not None
    assert garage["celebrate"]["id"] == str(skin)

    seen = await client.post(f"{SKINS}/{skin}/seen", headers=ready["headers"])
    assert seen.status_code == 204, seen.text

    garage = (await client.get(f"{SKINS}/garage", headers=ready["headers"])).json()
    assert garage["celebrate"] is None


# ------------------------------------------------------------------- الهدية


async def test_the_first_subscription_grants_the_gift_once(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
):
    """**مرةً في عمر الحساب** — والتجديدُ لا يعيدها.

    **والشراءُ يمرّ بالباب الحقيقيّ** (`POST /subscriptions`) لا بمساعدٍ
    يكتب صفَّ اشتراكٍ بيده: الهديةُ معلَّقةٌ بـ`_create`، ومساعدٌ يختصره
    يقيس عالماً لا وجودَ له — وهو البند ٨ بعينه.
    """
    await enable_features(session_factory, "wallet_enabled")
    gift = await make_skin(session_factory, name="الهدية", price=None, is_gift=True)
    plan_id = await ensure_plan(session_factory)

    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")

    bought = await client.post(
        "/subscriptions",
        json={"plan_id": str(plan_id), "idempotency_key": "skin-gift-first"},
        headers=driver["headers"],
    )
    assert bought.status_code == 201, bought.text

    async with session_factory() as session:
        rows = list(
            await session.scalars(
                select(DriverVehicleSkin).where(
                    DriverVehicleSkin.driver_id == driver["driver_id"]
                )
            )
        )
        row = await session.get(Driver, driver["driver_id"])
        active = row.active_skin_id
    assert [r.skin_id for r in rows] == [gift], "هديةٌ واحدةٌ لا أكثر"
    assert rows[0].source == "gift"
    assert rows[0].price_paid is None, "الهديةُ بلا سعرٍ مجمَّد — لم يدفع أحد"
    assert active == gift, "تُفعَّل لمن لا مركبةَ نشطةً له"

    renewed = await client.post(
        "/subscriptions",
        json={"plan_id": str(plan_id), "idempotency_key": "skin-gift-renew"},
        headers=driver["headers"],
    )
    assert renewed.status_code == 201, renewed.text
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(DriverVehicleSkin)
            .where(DriverVehicleSkin.driver_id == driver["driver_id"])
        )
    assert count == 1, "التجديدُ أعاد الهدية"


async def test_a_free_month_offer_grants_the_gift_too(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
):
    """**الهديةُ على حدث التفعيل لا على المبلغ المدفوع**.

    ولا شرطَ إضافيَّ لها: موضعُها `_create` — البابُ الوحيدُ الذي يكتب صفَّ
    اشتراكٍ في القنوات الأربع — فيشملها **عرضُ الشهر المجاني** بلا سطر.
    والمقيسُ هنا اشتراكٌ دُفع فيه صفر.
    """
    await enable_features(session_factory, "wallet_enabled")
    gift = await make_skin(session_factory, name="الهدية", price=None, is_gift=True)
    plan_id = await ensure_plan(session_factory, name="مجانية", price="0.000")

    driver = await approved_driver(client, session_factory, subscribed=False)
    bought = await client.post(
        "/subscriptions",
        json={"plan_id": str(plan_id), "idempotency_key": "skin-gift-free-month"},
        headers=driver["headers"],
    )
    assert bought.status_code == 201, bought.text
    assert bought.json()["amount_paid"] == "0.000"

    async with session_factory() as session:
        owned = list(
            await session.scalars(
                select(DriverVehicleSkin.skin_id).where(
                    DriverVehicleSkin.driver_id == driver["driver_id"]
                )
            )
        )
    assert owned == [gift], "اشتراكٌ بلا مالٍ لم يمنح الهدية"


async def test_a_catalogue_with_no_gift_does_not_break_a_purchase(
    client: AsyncClient, admin_headers: dict, session_factory, jordan_settings
):
    """**لا تُفشل شراءَ اشتراكٍ أبداً** — ولا هديةَ في الكتالوج هنا أصلاً."""
    await enable_features(session_factory, "wallet_enabled")
    plan_id = await ensure_plan(session_factory)
    driver = await approved_driver(client, session_factory, subscribed=False)
    await topup_wallet(client, admin_headers, driver["user_id"], "100.000")

    bought = await client.post(
        "/subscriptions",
        json={"plan_id": str(plan_id), "idempotency_key": "skin-no-gift-here"},
        headers=driver["headers"],
    )
    assert bought.status_code == 201, bought.text

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(DriverVehicleSkin)
        )
        row = await session.get(Driver, driver["driver_id"])
    assert count == 0
    assert row.active_skin_id is None


# --------------------------------------------------- ما يُنشر قبل القبول


async def test_a_rare_skin_is_not_published_on_the_free_map(
    client: AsyncClient, session_factory, jordan_settings
):
    """**صاحبُ النادرةِ وصاحبُ العاديةِ يتطابقان في الشكل** على خريطة الراكب.

    وهو الشكلُ الثالثَ عشر بعينه: امتيازٌ يُرى غيابُه — أو يُرى **اختلافُه** —
    يصير علامةً على صاحبه. فلو نُشرت النادرةُ لَعرف من يعدّ السياراتِ من في
    أيّها، ولو نُشرت `null` لَقال غيابُها الشيءَ نفسَه.

    **والقياسُ على شكل الحمولة لا على قيمةٍ واحدة**: الحقولُ نفسُها،
    والمركبةُ المنشورةُ **هي هي** — رسمةُ البديل.
    """
    fallback = await make_skin(
        session_factory,
        name="البديل",
        rarity=RARITY_COMMON,
        price=None,
        is_public_default=True,
        visible_before_accept=True,
    )
    rare = await make_skin(
        session_factory,
        name="الأسطورية",
        rarity=RARITY_LEGENDARY,
        price=None,
        visible_before_accept=False,
    )
    # **وصاحبُ العاديةِ يملك البديلَ نفسَه** — وهذا شرطُ الحماية لا تبسيطُ
    # اختبار: لو كان البديلُ رسماً لا يملكه أحدٌ لَقال ظهورُه «صاحبُ هذه
    # نادرتُه مخفيّة». وهو سببُ بذر **مركبةٍ واحدةٍ هديةً وبديلاً معاً**.
    ordinary = fallback

    with_rare = await approved_driver(
        client,
        session_factory,
        {
            "phone": "+962791700011",
            "password": "Driver12345",
            "name": "صاحبُ النادرة",
            "country_code": "JO",
            "role": "driver",
        },
        plate_number="AMM-1111",
    )
    with_common = await approved_driver(
        client,
        session_factory,
        {
            "phone": "+962791700012",
            "password": "Driver12345",
            "name": "صاحبُ العادية",
            "country_code": "JO",
            "role": "driver",
        },
        plate_number="AMM-2222",
    )
    async with session_factory() as session:
        for driver_id, skin_id in (
            (with_rare["driver_id"], rare),
            (with_common["driver_id"], ordinary),
        ):
            row = await session.get(Driver, driver_id)
            row.active_skin_id = skin_id
            session.add(
                DriverVehicleSkin(
                    driver_id=driver_id, skin_id=skin_id, source="grant"
                )
            )
        await session.commit()

    await bring_online(client, with_rare)
    await bring_online(client, with_common)

    rider = await rider_session(client)
    response = await client.get(
        "/drivers/nearby",
        params={"lat": 31.9539, "lng": 35.9106},
        headers=rider["headers"],
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 2, rows

    shapes = {tuple(sorted(row.keys())) for row in rows}
    assert len(shapes) == 1, "شكلان مختلفان للحمولة يفرّقان بين الكبتنين"
    published = {row["skin"]["skin_id"] for row in rows}
    assert published == {str(fallback)}, "النادرةُ نُشرت — أو غاب حقلُها"
    assert all(row["skin"]["image_url"].endswith("/art/map") for row in rows)


async def test_the_ride_card_carries_the_real_skin_after_acceptance(
    client: AsyncClient, session_factory, jordan_settings, jordan_wallet
):
    """**بعد القبول تصل النادرةُ كما هي** — لا بديلَ ولا إخفاء.

    والفرقُ هو كلُّ الميزة: قبل القبول يعدّ الفضوليُّ سياراتٍ لا يعرف
    أصحابَها، وبعده يعرف الراكبُ اسمَ الكبتن ولوحتَه أصلاً.
    """
    from tests.helpers import accepted_ride

    rare = await make_skin(
        session_factory,
        name="الأسطورية",
        rarity=RARITY_LEGENDARY,
        price=None,
        visible_before_accept=False,
        map_scale_percent=115,
        map_rotates=False,
    )
    driver = await approved_driver(client, session_factory)
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        row.active_skin_id = rare
        session.add(
            DriverVehicleSkin(
                driver_id=driver["driver_id"], skin_id=rare, source="grant"
            )
        )
        await session.commit()

    rider = await rider_session(client)
    await bring_online(client, driver)
    ride = await accepted_ride(client, rider["headers"], driver)
    response = await client.get(f"/rides/{ride['id']}", headers=rider["headers"])
    assert response.status_code == 200, response.text
    skin = response.json()["driver"]["skin"]
    assert skin is not None, "بطاقةُ الكبتن بلا مركبة"
    assert skin["skin_id"] == str(rare)
    assert skin["scale_percent"] == 115
    assert skin["rotates"] is False


# ------------------------------------------------------------------ المفتاح


async def test_the_flag_closes_the_store_with_a_named_error(
    client: AsyncClient, session_factory
):
    """**مطفأً يردّ خطأً مسمّى لا قائمةً فارغة** — الفارغةُ تُقرأ «لا مركبات بعد»."""
    driver = await approved_driver(client, session_factory)
    for path in (f"{SKINS}/store", f"{SKINS}/garage"):
        response = await client.get(path, headers=driver["headers"])
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "feature_disabled"


async def test_the_flag_does_not_erase_a_skin_already_owned(
    client: AsyncClient, session_factory, jordan_settings
):
    """**من دفع لا يفقد ما اشتراه بقرارِ تشغيل** — ولا تُفرَّغ الخريطةُ منه."""
    await make_skin(
        session_factory,
        name="البديل",
        price=None,
        is_public_default=True,
    )
    skin = await make_skin(
        session_factory, name="مملوكة", price=None, visible_before_accept=True
    )
    driver = await approved_driver(client, session_factory)
    async with session_factory() as session:
        row = await session.get(Driver, driver["driver_id"])
        row.active_skin_id = skin
        session.add(
            DriverVehicleSkin(
                driver_id=driver["driver_id"], skin_id=skin, source="grant"
            )
        )
        await session.commit()

    # المفتاحُ مطفأ — ومع ذلك تُنشر مركبتُه
    await bring_online(client, driver)
    rider = await rider_session(client)
    rows = (
        await client.get(
            "/drivers/nearby",
            params={"lat": 31.9539, "lng": 35.9106},
            headers=rider["headers"],
        )
    ).json()
    assert rows, "الخريطةُ فرغت بإطفاء مفتاح زينة"
    assert rows[0]["skin"]["skin_id"] == str(skin)


async def test_the_artwork_door_needs_no_session(
    client: AsyncClient, session_factory, ready
):
    """رسمةُ الكتالوج **ليست وثيقةَ هوية** — وحارسُ الجلسة يفرّغ خريطةَ الراكب.

    والمقيسُ هنا أن البابَ يصل بلا ترويسةِ إذنٍ ويردّ ٤٠٤ لأن الرسمةَ غيرُ
    مولَّدةٍ بعد — **لا ٤٠١**. والفرقُ بينهما هو الميزة.
    """
    skin = await make_skin(session_factory, name="بلا-رسمة")
    response = await client.get(f"{SKINS}/{skin}/art/map")
    assert response.status_code == 404, response.status_code
    assert response.json()["code"] == "not_found"
