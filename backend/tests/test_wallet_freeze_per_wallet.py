"""التجميدُ صفةُ محفظةٍ لا صفةُ حساب — 1-أ/6 (`SPEC-DELIVERY.md` §D6 و§D9.1).

**العطب**: `users.wallet_frozen` عمودٌ واحدٌ على الحساب، وللحساب محفظتان. فتجميدُ
محفظةِ كبتنٍ مشبوهةٍ كان **يمنع صاحبَها من دفع رحلته راكباً**، وتجميدُ محفظةِ
راكبٍ يوقف **سحبَ أرباحه كبتناً**. **وهو تجميدٌ لم يقرّره أحد.**

**وكلُّ اختبارٍ هنا يقيس الاتجاهين معاً، عشرةَ مواضعَ بعشرةِ اختبارات**:
المحفظةُ المجمَّدةُ تُمنع، **والأخرى تعمل**. واتجاهٌ واحدٌ وحدَه لا يكفي:
«تُمنع» يخضرّ بتجميدٍ يعمّ الحساب كلَّه (وهو العطب)، و«تعمل» يخضرّ بحارسٍ
مشطوب. **فالخُضرةُ لا تقع إلا بالفصل.**

**ويُقاس كلٌّ منها بحذف الحارس** (كما تُقاس الأقفال): شطبُ `require_not_frozen`
من موضعٍ يُحمِّر شطرَ «تُمنع» فيه، وإرجاعُ `is_frozen` إلى «أمجمَّدٌ الحسابُ؟»
يُحمِّر شطرَ «تعمل» في العشرة كلِّها.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

from app.models.enums import UserRole, WalletOwnerType
from app.models.user_role_grant import UserRoleGrant
from tests.helpers import (
    DRIVER,
    OTHER_RIDER,
    RIDER,
    approved_driver,
    bring_online,
    completed_ride,
    enable_card_provider,
    enable_cliq_provider,
    enable_features,
    ensure_plan,
    pay_ride,
    rider_session,
    topup_wallet,
)

OTHER_DRIVER = DRIVER | {"phone": "0794444444", "name": "كبتن آخر", "plate": "AMM-7777"}


# --------------------------------------------------------------- أدواتٌ صغيرة


async def _grant(session_factory, user_id: str, role: UserRole) -> None:
    """صفُّ الدور يُكتب مباشرةً — **لا بابَ يمنح دوراً ثانياً** في الشجرة.

    (`test_no_route_grants_a_role` يحرس ذلك، و`SPEC-DELIVERY` §D11-Q44.)
    """
    async with session_factory() as session:
        session.add(UserRoleGrant(user_id=uuid.UUID(user_id), role=role))
        await session.commit()


async def _dual_rider(
    client: AsyncClient,
    session_factory,
    payload: dict = RIDER,
    *,
    admin_headers: dict | None = None,
    balance: str | None = None,
):
    """راكبٌ يحمل **دورَ الكبتن أيضاً** — فله محفظتان تُجمَّد إحداهما.

    **والشحنُ قبل منح الدور الثاني بقصد**: بابُ الشحن الإداريّ
    (`POST /admin/wallets/{id}/topups`) **لا يقبل إعلانَ محفظة** حتى اليوم،
    فيرتدّ ٤٠٩ لحاملِ الدورين — عطبٌ قائمٌ من عائلة «بابٌ لا يُعلن»، مكتوبٌ
    في `SPEC-DELIVERY` §D6 **ولا يُصلح هنا**: لا تغييرَ في منطقٍ قائمٍ خارج
    ما تصفه الخطة.
    """
    session = await rider_session(client, payload)
    session["user_id"] = session["user"]["id"]
    if balance is not None:
        assert admin_headers is not None
        await topup_wallet(client, admin_headers, session["user_id"], balance)
    await _grant(session_factory, session["user_id"], UserRole.DRIVER)
    return session


async def _dual_driver(
    client: AsyncClient,
    session_factory,
    payload: dict = DRIVER,
    *,
    admin_headers: dict | None = None,
    balance: str | None = None,
):
    """كبتنٌ معتمدٌ يحمل **دورَ الراكب أيضاً** — والشحنُ قبل المنح كما فوق."""
    driver = await approved_driver(client, session_factory, payload)
    if balance is not None:
        assert admin_headers is not None
        await topup_wallet(client, admin_headers, driver["user_id"], balance)
    await _grant(session_factory, driver["user_id"], UserRole.RIDER)
    return driver


async def _freeze(
    client: AsyncClient, admin_headers: dict, user_id: str, wallet: str
) -> None:
    response = await client.post(
        f"/admin/wallets/{user_id}/freeze",
        params={"wallet": wallet},
        json={"reason": "اشتباه"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["frozen"] is True
    assert response.json()["owner_type"] == wallet


def _transfer(phone: str, key: str, amount: str = "5.000") -> dict:
    return {"recipient_phone": phone, "amount": amount, "idempotency_key": key}


def _refused(response) -> None:
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "wallet_frozen", response.text


def _not_refused(response) -> None:
    """**لم يمنعه التجميد** — وما يمنعه غيرُه ليس من شأن هذا الاختبار."""
    code = response.json().get("code") if response.status_code >= 400 else None
    assert code != "wallet_frozen", response.text


# ------------------------------------------------------- 1) دفعُ رحلةٍ بالمحفظة


async def test_payments_read_the_rider_wallet_freeze_alone(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """`payments._pay_from_wallet` — **وهو العطبُ في أظهر صوره**: كبتنٌ مجمَّدةٌ
    محفظتُه كان لا يستطيع دفعَ أجرة رحلةٍ ركبها بنفسه."""
    rider = await _dual_rider(
        client, session_factory, admin_headers=admin_headers, balance="50.000"
    )
    driver = await approved_driver(client, session_factory, OTHER_DRIVER)

    await _freeze(client, admin_headers, rider["user_id"], "driver")
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)
    paid = await pay_ride(client, rider["headers"], ride["id"], "wallet")
    assert paid.status_code == 201, paid.text

    await _freeze(client, admin_headers, rider["user_id"], "rider")
    await bring_online(client, driver)
    second = await completed_ride(client, rider["headers"], driver)
    _refused(
        await pay_ride(
            client, rider["headers"], second["id"], "wallet", key="pay-key-0002"
        )
    )


# -------------------------------------------------------------- 2) البقشيش


async def test_tips_read_the_rider_wallet_freeze_alone(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """`tips.create` — البقشيشُ يخرج من محفظة الراكب، فهي المعنيّة."""
    # **والمحفظةُ مشتعلةٌ من `jordan_wallet`** — وإشعالُها ثانيةً يصطدم بقيدها
    await enable_features(session_factory, "tips_enabled")
    amounts = await client.patch(
        "/admin/settings/payments/JO",
        json={
            "tip_preset_small": "0.500",
            "tip_preset_medium": "1.000",
            "tip_max": "5.000",
        },
        headers=admin_headers,
    )
    assert amounts.status_code == 200, amounts.text
    rider = await _dual_rider(
        client, session_factory, admin_headers=admin_headers, balance="50.000"
    )
    driver = await approved_driver(client, session_factory, OTHER_DRIVER)

    await _freeze(client, admin_headers, rider["user_id"], "driver")
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)
    tipped = await client.post(
        f"/rides/{ride['id']}/tip",
        json={"amount": "2.000"},
        headers=rider["headers"],
    )
    _not_refused(tipped)

    await _freeze(client, admin_headers, rider["user_id"], "rider")
    await bring_online(client, driver)
    second = await completed_ride(client, rider["headers"], driver)
    _refused(
        await client.post(
            f"/rides/{second['id']}/tip",
            json={"amount": "2.000"},
            headers=rider["headers"],
        )
    )


# ------------------------------------------------------- 3) شراءُ الاشتراك


async def test_subscription_purchase_reads_the_driver_wallet_freeze_alone(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """`subscriptions.purchase_with_wallet` — الشراءُ من رصيد الكبتن."""
    await enable_features(session_factory, "wallet_enabled")
    driver = await _dual_driver(
        client, session_factory, admin_headers=admin_headers, balance="90.000"
    )
    plan_id = await ensure_plan(session_factory)

    await _freeze(client, admin_headers, driver["user_id"], "rider")
    bought = await client.post(
        "/subscriptions",
        json={
            "plan_id": str(plan_id),
            "payment_method": "wallet",
            "idempotency_key": "sub-thawed",
        },
        headers=driver["headers"],
    )
    _not_refused(bought)

    await _freeze(client, admin_headers, driver["user_id"], "driver")
    _refused(
        await client.post(
            "/subscriptions",
            json={
                "plan_id": str(plan_id),
                "payment_method": "wallet",
                "idempotency_key": "sub-frozen",
            },
            headers=driver["headers"],
        )
    )


# ------------------------------------------------------------- 4) طلبُ السحب


async def test_withdrawal_reads_the_driver_wallet_freeze_alone(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """`withdrawals.create_request` — ولا سحبَ من محفظة راكبٍ أصلاً (SPEC §7)."""
    driver = await _dual_driver(
        client, session_factory, admin_headers=admin_headers, balance="90.000"
    )

    await _freeze(client, admin_headers, driver["user_id"], "rider")
    asked = await client.post(
        "/wallet/me/withdrawals",
        json={"amount": "10.000", "method": "bank"},
        headers=driver["headers"],
    )
    _not_refused(asked)

    await _freeze(client, admin_headers, driver["user_id"], "driver")
    _refused(
        await client.post(
            "/wallet/me/withdrawals",
            json={"amount": "10.000", "method": "bank"},
            headers=driver["headers"],
        )
    )


# --------------------------------------------------- 5) فتحُ طلبِ شحنٍ يدويّ


async def test_topup_request_reads_the_declared_wallet_freeze_alone(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """`topups.create_request` — **والمحفظةُ المعلَنةُ هي المعنيّة**، وهي التي
    تُختم على الطلب فتُقرأ عند التأكيد."""
    rider = await _dual_rider(client, session_factory)

    await _freeze(client, admin_headers, rider["user_id"], "driver")
    opened = await client.post(
        "/wallet/me/topups",
        params={"wallet": "rider"},
        json={"method": "cliq", "amount": "5.000", "reference": "CLQ-1"},
        headers=rider["headers"],
    )
    _not_refused(opened)

    await _freeze(client, admin_headers, rider["user_id"], "rider")
    _refused(
        await client.post(
            "/wallet/me/topups",
            params={"wallet": "rider"},
            json={"method": "cliq", "amount": "5.000", "reference": "CLQ-2"},
            headers=rider["headers"],
        )
    )


# ------------------------------------------------ 6) تأكيدُ الإدارة لطلبِ شحن


async def test_topup_confirmation_reads_the_wallet_stamped_on_the_request(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """`topups.confirm` — **من الصفِّ لا من الدور**: الطلبُ يحمل محفظتَه منذ
    إنشائه، فتجميدُ الأخرى لا يمنع تأكيدَه."""
    rider = await _dual_rider(client, session_factory)
    first = await client.post(
        "/wallet/me/topups",
        params={"wallet": "rider"},
        json={"method": "cliq", "amount": "5.000", "reference": "CLQ-A"},
        headers=rider["headers"],
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        "/wallet/me/topups",
        params={"wallet": "rider"},
        json={"method": "cliq", "amount": "5.000", "reference": "CLQ-B"},
        headers=rider["headers"],
    )
    assert second.status_code == 201, second.text

    await _freeze(client, admin_headers, rider["user_id"], "driver")
    confirmed = await client.post(
        f"/admin/topups/{first.json()['id']}/confirm",
        json={"amount": "5.000"},
        headers=admin_headers,
    )
    _not_refused(confirmed)

    await _freeze(client, admin_headers, rider["user_id"], "rider")
    _refused(
        await client.post(
            f"/admin/topups/{second.json()['id']}/confirm",
            json={"amount": "5.000"},
            headers=admin_headers,
        )
    )


# ---------------------------------------------------- 7) شحنُ محفظةٍ ببطاقة


async def test_card_topup_reads_the_declared_wallet_freeze_alone(
    client: AsyncClient,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
    session_factory,
) -> None:
    """`card_payments.start_wallet_topup`."""
    await enable_card_provider(session_factory)
    rider = await _dual_rider(client, session_factory)

    await _freeze(client, admin_headers, rider["user_id"], "driver")
    opened = await client.post(
        "/wallet/me/topups/card",
        params={"wallet": "rider"},
        json={"amount": "25.000"},
        headers=rider["headers"],
    )
    _not_refused(opened)

    await _freeze(client, admin_headers, rider["user_id"], "rider")
    _refused(
        await client.post(
            "/wallet/me/topups/card",
            params={"wallet": "rider"},
            json={"amount": "25.000"},
            headers=rider["headers"],
        )
    )


# ------------------------------------------------------ 8) شحنُ محفظةٍ بكليك


async def test_cliq_topup_reads_the_declared_wallet_freeze_alone(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """`cliq_topups.start_topup`."""
    await enable_features(session_factory, "wallet_enabled")
    await enable_cliq_provider(session_factory)
    rider = await _dual_rider(client, session_factory)

    await _freeze(client, admin_headers, rider["user_id"], "driver")
    opened = await client.post(
        "/wallet/me/topups/cliq",
        params={"wallet": "rider"},
        json={"amount": "10.000"},
        headers=rider["headers"],
    )
    _not_refused(opened)

    await _freeze(client, admin_headers, rider["user_id"], "rider")
    _refused(
        await client.post(
            "/wallet/me/topups/cliq",
            params={"wallet": "rider"},
            json={"amount": "10.000"},
            headers=rider["headers"],
        )
    )


# ------------------------------------------------------- 9) المرسِل في تحويل


async def test_transfer_sender_reads_the_rider_wallet_freeze_alone(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """`wallet.transfer` — التحويلُ بين محفظتَي راكبين، فمحفظةُ الراكب المعنيّة."""
    sender = await _dual_rider(
        client, session_factory, admin_headers=admin_headers, balance="30.000"
    )
    await rider_session(client, OTHER_RIDER)

    await _freeze(client, admin_headers, sender["user_id"], "driver")
    sent = await client.post(
        "/wallet/me/transfers",
        json=_transfer(OTHER_RIDER["phone"], "tr-thawed"),
        headers=sender["headers"],
    )
    _not_refused(sent)

    await _freeze(client, admin_headers, sender["user_id"], "rider")
    _refused(
        await client.post(
            "/wallet/me/transfers",
            json=_transfer(OTHER_RIDER["phone"], "tr-frozen"),
            headers=sender["headers"],
        )
    )


# ------------------------------------------------------ 10) المستلِم في تحويل


async def test_transfer_recipient_reads_the_rider_wallet_freeze_alone(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """**الطرفان يُسألان** (قرارُ المالك 2026-08-31) — وكلٌّ عن محفظته هو.

    وهذا الموضعُ كان يقرأ العمودَ مباشرةً لا من خلال الحارس: **بابان للفحص
    أحدُهما يُنسى**، فصارا باباً واحداً.
    """
    sender = await rider_session(client)
    sender["user_id"] = sender["user"]["id"]
    recipient = await _dual_rider(client, session_factory, OTHER_RIDER)
    await topup_wallet(client, admin_headers, sender["user_id"], "30.000")

    await _freeze(client, admin_headers, recipient["user_id"], "driver")
    sent = await client.post(
        "/wallet/me/transfers",
        json=_transfer(OTHER_RIDER["phone"], "in-thawed"),
        headers=sender["headers"],
    )
    _not_refused(sent)

    await _freeze(client, admin_headers, recipient["user_id"], "rider")
    _refused(
        await client.post(
            "/wallet/me/transfers",
            json=_transfer(OTHER_RIDER["phone"], "in-frozen"),
            headers=sender["headers"],
        )
    )


# ------------------------------------------------- الترحيلُ نفسُه، وما يحرسه


async def test_a_freeze_row_is_one_per_wallet_and_lifting_removes_it(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**وجودُ الصفِّ هو التجميد**: تجميدٌ على تجميدٍ لا يُنشئ صفّاً ثانياً،
    ورفعُه يحذفه — والأخرى لا تتأثّر."""
    from sqlalchemy import select

    from app.models.wallet_freeze import WalletFreeze

    rider = await _dual_rider(client, session_factory)
    await _freeze(client, admin_headers, rider["user_id"], "rider")
    await _freeze(client, admin_headers, rider["user_id"], "rider")
    await _freeze(client, admin_headers, rider["user_id"], "driver")

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(WalletFreeze).where(
                    WalletFreeze.user_id == uuid.UUID(rider["user_id"])
                )
            )
        ).all()
    assert sorted(row.owner_type.value for row in rows) == ["driver", "rider"]

    lifted = await client.post(
        f"/admin/wallets/{rider['user_id']}/unfreeze",
        params={"wallet": "rider"},
        json={"reason": "زال الاشتباه"},
        headers=admin_headers,
    )
    assert lifted.status_code == 200, lifted.text
    assert lifted.json()["frozen"] is False

    async with session_factory() as session:
        remaining = (
            await session.scalars(
                select(WalletFreeze).where(
                    WalletFreeze.user_id == uuid.UUID(rider["user_id"])
                )
            )
        ).all()
    assert [row.owner_type for row in remaining] == [WalletOwnerType.DRIVER]


async def test_the_audit_trail_names_the_wallet(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**وسجلٌّ لا يقول أيَّ محفظةٍ جُمِّدت يُقرأ بجوابين** لحاملِ الدورين."""
    rider = await _dual_rider(client, session_factory)
    await _freeze(client, admin_headers, rider["user_id"], "driver")

    logs = await client.get(
        "/admin/settings/audit-logs",
        params={"entity_type": "wallet"},
        headers=admin_headers,
    )
    assert logs.status_code == 200, logs.text
    details = logs.json()[0]["details"]
    assert details["wallet_frozen"] is True
    assert details["wallet"] == "driver"


async def test_a_single_role_account_is_unchanged_in_silence(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """**والسكوتُ كما كان**: صاحبُ الدور الواحد يُجمَّد بلا إعلانٍ ويُمنع،
    فلا تُطالَب شاشةٌ قائمةٌ بما لا معنى له عندها."""
    rider = await rider_session(client)
    user_id = rider["user"]["id"]
    await rider_session(client, OTHER_RIDER)
    await topup_wallet(client, admin_headers, user_id, "30.000")

    frozen = await client.post(
        f"/admin/wallets/{user_id}/freeze",
        json={"reason": "اشتباه"},
        headers=admin_headers,
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["frozen"] is True

    _refused(
        await client.post(
            "/wallet/me/transfers",
            json=_transfer(OTHER_RIDER["phone"], "single-frozen"),
            headers=rider["headers"],
        )
    )
    assert (await client.get("/wallet/me", headers=rider["headers"])).json()[
        "frozen"
    ] is True


def test_the_freeze_is_read_without_a_query(session_factory) -> None:
    """**وصفرُ استعلامٍ إضافيٍّ في أيِّ مسار مال**: الفحصُ متزامنٌ يقرأ صفوفاً
    جاءت مع الحساب (`selectin`) — ودالّةٌ غيرُ متزامنةٍ يُنسى `await`ها تمرّ
    صامتة."""
    import inspect as py_inspect

    from app.services import wallet as wallet_service
    from app.models.user import User

    assert not py_inspect.iscoroutinefunction(wallet_service.require_not_frozen)
    assert not py_inspect.iscoroutinefunction(wallet_service.is_frozen)
    assert User.wallet_freezes.property.lazy == "selectin"
    assert not hasattr(User, "wallet_frozen")


async def test_a_user_loaded_without_its_freezes_is_not_read_as_thawed(
    client: AsyncClient, session_factory
) -> None:
    """**وحارسٌ لا يملك ما يقيسه يقول «لم يُقس» لا «سليم»**.

    حسابٌ جاء من القاعدة بتحميلٍ ضيّقٍ لا يحمل صفوفَه — **فلا يُقرأ غيابُها
    عدمَ تجميد**. وحسابٌ بُني في بايثون للتوّ لا صفوفَ له بحال، فيُقرأ.
    """
    import pytest
    from sqlalchemy import select

    from app.models.user import User
    from app.services import wallet as wallet_service

    assert wallet_service.is_frozen(User(), WalletOwnerType.RIDER) is False

    rider = await rider_session(client)
    async with session_factory() as session:
        loaded = await session.scalar(
            select(User).where(User.id == uuid.UUID(rider["user"]["id"]))
        )
        # **حقولٌ انتهت صلاحيتُها** — وهي الحالُ الواقعةُ بعد `commit` بإعدادٍ
        # يُبطلها. قراءةٌ كسولةٌ هنا `MissingGreenlet`، **وقراءةُ «غيرِ مجمَّد»
        # أسوأُ منها** لأنها تمرّ صامتة
        session.expire(loaded)
        with pytest.raises(RuntimeError):
            wallet_service.is_frozen(loaded, WalletOwnerType.RIDER)


def test_the_migration_carries_every_wallet_of_a_frozen_account() -> None:
    """**ومن جُمِّد قبل الترحيلة يبقى مجمَّداً على كلِّ محافظه** — والدورُ
    يُقرأ من المجموعة **والعمود** معاً كما يقرؤهما `User.roles`.

    **والمجمَّدون صفرٌ في القاعدتين يومَ كُتبت** (التطوير 0 من 43، والإنتاج
    0 من 10)، فالمكتوبُ لمن يأتي بعدُ لا لصفوفٍ قائمة.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0077_wallet_freezes.py"
    ).read_text(encoding="utf-8")
    assert "INSERT INTO wallet_freezes" in source
    assert "u.role::text = :role" in source
    assert "FROM user_roles g" in source
    # والرجوعُ يجمع ما فُرِّق — وبغيره يخرج المجمَّدُ من تجميده بترحيلةٍ عكسية
    assert "UPDATE users SET wallet_frozen = true" in source
