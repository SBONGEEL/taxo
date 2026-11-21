"""**«عدد أيام» و«سفير TAXO»** (أمرُ المالك ٢٠٢٦-١١-٢١ الخامس، البند ٣؛ SPEC §١١١-د/٤).

**ما يُقاس، وكلٌّ يسقط بحذف ما يحرسه:**
١) الأيّامُ تبدأ **بعد** الاشتراك القائم (لا يضيع يوم)، وتنتهي بعد عددها بالضبط، والمبلغُ ما كتبه المشرف (صفرٌ للهديّة ومرجعُها «هديّة»).
٢) المبلغُ إلزاميٌّ صراحةً مع الأيّام والدائم — المقترَحُ تلميحٌ لا يُفرض — والأيّامُ بين ١ و٣٦٥، ولا الاثنان معاً.
٣) الدائمُ للمالك وحدَه؛ لا يبلغه تذكيرٌ ولا تجديد، وشارةُ «سفير TAXO» في `/subscriptions/me` وفي قائمة الكباتن.
٤) **لا شراءَ فوق الدائم**، ومنحان دائمان معاً يكتبان صفّاً واحداً (القفلُ والفهرسُ الفريد).
٥) النزعُ إلغاءٌ للصفّ الدائم وحدَه بسببٍ (لا حذف)، وما قبله يبقى يغطّي، والكبتنُ يُشعَر.
٦) المفتاحُ مطفأً يردّ البابَ.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.crypto import get_cipher
from app.models.audit import AdminAuditLog
from app.models.enums import (
    CountryCode,
    Currency,
    FeatureKey,
    SubscriptionDurationType,
    SubscriptionStatus,
    UserRole,
)
from app.models.feature_flag import FeatureFlag
from app.models.notification import UserNotification
from app.models.subscription import DriverSubscription, SubscriptionPlan
from app.models.totp import UserTotp
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.services import subscriptions, token_service
from tests.helpers import DRIVER, approved_driver

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("jordan_settings", "jordan_wallet")]


async def _plan(session_factory) -> SubscriptionPlan:
    async with session_factory() as session:
        plan = await session.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == CountryCode.JO,
                SubscriptionPlan.duration_type == SubscriptionDurationType.MONTHLY,
            )
        )
        if plan is None:
            plan = SubscriptionPlan(
                name="شهري", duration_type=SubscriptionDurationType.MONTHLY, price=Decimal("30.000"),
                currency=Currency.JOD, country_code=CountryCode.JO,
            )
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
        return plan


async def _gifts_on(session_factory) -> None:
    async with session_factory() as session:
        session.add(FeatureFlag(country_code=CountryCode.JO, feature_key=FeatureKey.SUBSCRIPTION_GIFTS.value, enabled=True))
        await session.commit()


async def _owner(session_factory) -> dict:
    """**مالكٌ بعاملٍ ثانٍ مؤكَّد** — كما يُلزَم (§٨٢-ب/٥)."""
    async with session_factory() as session:
        user = User(
            phone=None, name="مالك الاختبار", role=UserRole.ADMIN, country_code=CountryCode.JO,
            role_grants=[UserRoleGrant(role=UserRole.ADMIN), UserRoleGrant(role=UserRole.OWNER)],
        )
        session.add(user)
        await session.flush()
        session.add(UserTotp(
            user_id=user.id, secret_encrypted=get_cipher().encrypt({"secret": "JBSWY3DPEHPK3PXP"}),
            confirmed_at=datetime.now(UTC),
        ))
        await session.commit()
        tokens = await token_service.issue_token_pair(session, user)
        return {"Authorization": f"Bearer {tokens.access_token}"}


async def _rows(session_factory, driver_id) -> list[DriverSubscription]:
    async with session_factory() as session:
        return list((await session.scalars(
            select(DriverSubscription).where(DriverSubscription.driver_id == driver_id).order_by(DriverSubscription.starts_at)
        )).all())


async def _gift_kinds(session_factory, user_id) -> list[str]:
    async with session_factory() as session:
        data = (await session.scalars(select(UserNotification.data).where(
            UserNotification.user_id == user_id, UserNotification.kind == "subscription_gift"
        ))).all()
        return sorted(d["kind"] for d in data)


# ═════════════════════════ «عدد أيام»


async def test_custom_days_start_after_the_current_subscription_and_last_exactly(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _gifts_on(session_factory)
    plan = await _plan(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    base = {"driver_id": str(driver["driver_id"]), "plan_id": str(plan.id)}
    first = await client.post("/admin/subscriptions", json=base | {"method": "cash"}, headers=admin_headers)
    assert first.status_code == 201, first.text

    preview = await client.post("/admin/subscriptions/preview", json=base | {"days": 10}, headers=admin_headers)
    assert preview.status_code == 200, preview.text
    # **المقترَحُ متناسبٌ بالأيّام** — ٣٠ ÷ ٣٠ × ١٠ — **والمعاينةُ قراءةٌ لا تكتب**
    assert Decimal(preview.json()["suggested_amount"]) == Decimal("10.000")
    assert len(await _rows(session_factory, driver["driver_id"])) == 1

    gift = await client.post("/admin/subscriptions", json=base | {"method": "cash", "days": 10, "amount_paid": "0"},
                             headers=admin_headers)
    assert gift.status_code == 201, gift.text
    body = gift.json()
    assert body["custom_days"] == 10 and body["is_permanent"] is False
    assert Decimal(body["amount_paid"]) == 0 and body["reference"] == "هديّة"

    month, days = await _rows(session_factory, driver["driver_id"])
    # **لا يضيع يوم**: يبدأ حيث ينتهي القائم، وينتهي بعد عشرة أيّامٍ بالضبط — وهو ما وعدت به المعاينة
    assert days.starts_at == month.expires_at
    assert days.expires_at - days.starts_at == timedelta(days=10)
    assert datetime.fromisoformat(preview.json()["starts_at"]) == days.starts_at
    assert days.list_price == Decimal("10.000")

    async with session_factory() as session:
        audit = (await session.scalars(
            select(AdminAuditLog).where(AdminAuditLog.entity_id == days.id)
        )).one()
        assert audit.details["days"] == 10
    assert await _gift_kinds(session_factory, driver["user_id"]) == ["days"]


async def test_the_amount_must_be_written_and_days_are_bounded(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _gifts_on(session_factory)
    plan = await _plan(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    base = {"driver_id": str(driver["driver_id"]), "plan_id": str(plan.id), "method": "cash"}

    missing = await client.post("/admin/subscriptions", json=base | {"days": 5}, headers=admin_headers)
    assert missing.status_code == 422, missing.text
    assert missing.json()["field"] == "amount_paid"
    too_many = await client.post("/admin/subscriptions", json=base | {"days": 366, "amount_paid": "0"}, headers=admin_headers)
    assert too_many.status_code == 422
    both = await client.post("/admin/subscriptions", json=base | {"days": 5, "permanent": True, "amount_paid": "0"},
                             headers=await _owner(session_factory))
    assert both.status_code == 422
    assert await _rows(session_factory, driver["driver_id"]) == []


async def test_the_switch_off_refuses_days(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    plan = await _plan(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    refused = await client.post("/admin/subscriptions", json={
        "driver_id": str(driver["driver_id"]), "plan_id": str(plan.id), "method": "cash", "days": 3, "amount_paid": "0",
    }, headers=admin_headers)
    assert refused.status_code == 403, refused.text
    assert await _rows(session_factory, driver["driver_id"]) == []


# ═════════════════════════ «سفير TAXO»


async def test_permanent_is_owner_only_never_expires_and_blocks_buying(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _gifts_on(session_factory)
    plan = await _plan(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    grant = {"driver_id": str(driver["driver_id"]), "plan_id": str(plan.id), "method": "cash",
             "permanent": True, "amount_paid": "0"}

    by_admin = await client.post("/admin/subscriptions", json=grant, headers=admin_headers)
    assert by_admin.status_code == 403, by_admin.text
    assert await _rows(session_factory, driver["driver_id"]) == []

    done = await client.post("/admin/subscriptions", json=grant, headers=await _owner(session_factory))
    assert done.status_code == 201, done.text
    assert done.json()["is_permanent"] is True

    (row,) = await _rows(session_factory, driver["driver_id"])
    assert row.expires_at - row.starts_at == subscriptions.PERMANENT_SPAN
    assert row.custom_days is None

    # **لا تذكيرَ يبلغه**
    async with session_factory() as session:
        assert [n for n in await subscriptions.expiring_soon(session, within=timedelta(days=3))
                if str(n.driver_id) == str(driver["driver_id"])] == []

    me = await client.get("/subscriptions/me", headers=driver["headers"])
    assert me.status_code == 200, me.text
    assert me.json()["ambassador"] is True and me.json()["is_active"] is True

    listed = await client.get("/admin/drivers", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    assert next(r for r in listed.json() if r["driver_id"] == str(driver["driver_id"]))["ambassador"] is True

    # **لا شراءَ فوق الدائم** — ولا صفَّ يُكتب
    again = await client.post("/admin/subscriptions", json={
        "driver_id": str(driver["driver_id"]), "plan_id": str(plan.id), "method": "cash",
    }, headers=admin_headers)
    assert again.status_code == 409, again.text
    assert len(await _rows(session_factory, driver["driver_id"])) == 1
    assert await _gift_kinds(session_factory, driver["user_id"]) == ["permanent"]


async def test_two_permanent_grants_at_once_write_one_row(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**القفلُ يملك «دائمٌ واحد»** — بلا قفل صفِّ الكبتن يقرأ الطلبان «لا دائم» معاً، والفهرسُ الفريدُ وحدَه يبقى."""
    await _gifts_on(session_factory)
    plan = await _plan(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    owner = await _owner(session_factory)
    grant = {"driver_id": str(driver["driver_id"]), "plan_id": str(plan.id), "method": "cash",
             "permanent": True, "amount_paid": "0"}

    responses = await asyncio.wait_for(
        asyncio.gather(*(client.post("/admin/subscriptions", json=grant, headers=owner) for _ in range(2))),
        timeout=30,
    )
    assert Counter(r.status_code for r in responses) == Counter({201: 1, 409: 1}), [r.text for r in responses]
    assert len(await _rows(session_factory, driver["driver_id"])) == 1


async def test_revoking_cancels_only_the_permanent_row_and_keeps_paid_days(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _gifts_on(session_factory)
    plan = await _plan(session_factory)
    driver = await approved_driver(client, session_factory, DRIVER, subscribed=False)
    paid = await client.post("/admin/subscriptions", json={
        "driver_id": str(driver["driver_id"]), "plan_id": str(plan.id), "method": "cash",
    }, headers=admin_headers)
    assert paid.status_code == 201, paid.text
    owner = await _owner(session_factory)
    granted = await client.post("/admin/subscriptions", json={
        "driver_id": str(driver["driver_id"]), "plan_id": str(plan.id), "method": "cash", "permanent": True, "amount_paid": "0",
    }, headers=owner)
    assert granted.status_code == 201, granted.text

    gifts = await client.get("/admin/subscriptions/gifts", headers=admin_headers)
    assert gifts.status_code == 200, gifts.text
    assert [r["is_permanent"] for r in gifts.json()] == [True]
    assert Decimal(gifts.json()[0]["revoke_refund"]) == 0

    revoke = f"/admin/subscriptions/ambassadors/{driver['driver_id']}/revoke"
    assert (await client.post(revoke, json={"reason": ""}, headers=owner)).status_code == 422
    assert (await client.post(revoke, json={"reason": "انتهى الاتّفاق"}, headers=admin_headers)).status_code == 403

    revoked = await client.post(revoke, json={"reason": "انتهى الاتّفاق"}, headers=owner)
    assert revoked.status_code == 200, revoked.text
    assert Decimal(revoked.json()["refund"]) == 0

    rows = await _rows(session_factory, driver["driver_id"])
    assert len(rows) == 2  # **لا حذف**
    permanent = next(r for r in rows if r.is_permanent)
    month = next(r for r in rows if not r.is_permanent)
    assert permanent.status is SubscriptionStatus.CANCELLED and permanent.cancel_reason == "انتهى الاتّفاق"
    assert permanent.cancelled_by is not None
    # **ما دُفع يبقى يغطّي** — النزعُ لا يمسّه
    assert month.status is SubscriptionStatus.ACTIVE
    me = await client.get("/subscriptions/me", headers=driver["headers"])
    assert me.json()["ambassador"] is False and me.json()["is_active"] is True

    again = await client.post(revoke, json={"reason": "مرّةً ثانية"}, headers=owner)
    assert again.status_code == 404, again.text
    assert await _gift_kinds(session_factory, driver["user_id"]) == ["permanent", "revoked"]
