"""التعديلُ والحذفُ في صفحات الإدارة — البند ٤ (§39٫٤، قرارُ المالك 2026-09-02).

**والقاعدةُ بنصِّه**: «يشمل كلَّ ما ليس مالاً … **وكلُّ تعديلٍ أو حذفٍ مختومٌ
في التدقيق: من ومتى والقيمةُ قبل وبعد** … والحذفُ حيث يُسمح **يستأذن مرّةً
بنصٍّ يسمّي ما سيُحذف وعددَه**».

**وما يقيسه هذا الملفّ ثلاثة:**

1. **أن السجلَّ صار يحمل القيمتين** — لا اسمَ الحقل وحدَه.
2. **وأن السرَّ لا يُكتب فيه** — والقاعدةُ القديمة كانت تمنع القيمَ كلَّها
   لأجله، **فتضييقُها لا نقضُها**.
3. **وأن الحذفَ يقف عند ما رآه الناسُ أو استعملوه** — لكلِّ كيانٍ بسؤاله.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.models.badge import Badge, DriverBadge
from app.models.enums import AuditAction
from app.models.mission import Mission
from app.services import audit
from tests.helpers import DRIVER, approved_driver

pytestmark = pytest.mark.usefixtures("jordan_settings")


async def _last_entry(session_factory, entity_type: str) -> AdminAuditLog:
    async with session_factory() as session:
        return await session.scalar(
            select(AdminAuditLog)
            .where(AdminAuditLog.entity_type == entity_type)
            .order_by(AdminAuditLog.created_at.desc())
            .limit(1)
        )


# ═════════════════════════ القيمةُ قبل وبعد


async def test_an_edit_records_the_value_before_and_after_not_just_the_field(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**«تغيّر السعر» بلا رقمين لا يجيب من يسأل بعد شهرٍ كم كان.**

    وهذا **نقضٌ صريحٌ** لقاعدةٍ كانت مكتوبة («أسماءُ الحقول لا قيمُها»)،
    بإذنٍ صريحٍ من المالك 2026-09-02.
    """
    created = await client.post(
        "/admin/settings/subscription-plans",
        json={
            "country_code": "JO",
            "name": "خطةُ قياس",
            "duration_type": "monthly",
            "price": "30.000",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert created.status_code in (200, 201), created.text
    plan_id = created.json()["id"]

    edited = await client.patch(
        f"/admin/settings/subscription-plans/{plan_id}",
        json={"price": "45.000"},
        headers=admin_headers,
    )
    assert edited.status_code == 200, edited.text

    entry = await _last_entry(session_factory, "subscription_plan")
    assert entry.action is AuditAction.UPDATE
    changes = entry.details["changes"]
    # **والمالُ نصٌّ لا عائم**: `NUMERIC(12,3)` لا يُمثَّل في العائم بلا خسارة،
    # **وسجلٌّ يقول `44.99999` عن `45.000` سجلٌّ يكذب**
    assert changes["price"] == {"before": "30.000", "after": "45.000"}


async def test_a_field_sent_unchanged_is_not_recorded_as_a_change(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**ما لم يتغيّر لا يُذكر** — وذكرُه يجعل السجلَّ يقول إن شيئاً وقع."""
    created = await client.post(
        "/admin/settings/subscription-plans",
        json={
            "country_code": "JO",
            "name": "خطةٌ ثابتة",
            "duration_type": "weekly",
            "price": "10.000",
            "is_active": True,
        },
        headers=admin_headers,
    )
    plan_id = created.json()["id"]
    await client.patch(
        f"/admin/settings/subscription-plans/{plan_id}",
        json={"price": "10.000"},
        headers=admin_headers,
    )
    entry = await _last_entry(session_factory, "subscription_plan")
    # **آخرُ قيدٍ هو قيدُ الإنشاء** — إذ التعديلُ لم يغيّر شيئاً فلا `changes`
    assert "changes" not in (entry.details or {})


def test_a_secret_field_is_recorded_as_changed_without_its_value() -> None:
    """**تضييقُ القاعدة لا نقضُها**: القيمةُ تُكتب **إلا حيث كان المنعُ حقّاً**.

    **ولا يُخمَّن من شكل الاسم**: القائمةُ بالاسم، ومعها ما يُعلنه سجلُّ
    المزوّدين `secret` — **وحقلٌ سرِّيٌّ باسمٍ جديدٍ يمرّ حتى يُضاف**، وهو
    مكتوبٌ في رأس الوحدة لا مسكوتٌ عنه.
    """

    class Row:
        api_key = "قديم"
        price = Decimal("5.000")

    row = Row()
    changes = audit.apply_changes(row, {"api_key": "جديد", "price": Decimal("7.500")})
    assert changes["api_key"] == {"before": audit.REDACTED, "after": audit.REDACTED}
    assert changes["price"] == {"before": "5.000", "after": "7.500"}
    # **والقيمةُ طُبِّقت فعلاً** — الحجبُ في السجلّ لا في الكتابة
    assert row.api_key == "جديد"


# ═════════════════════════ الحذفُ يقف عند ما رآه الناسُ أو استعملوه


async def test_a_granted_badge_is_not_deleted_and_says_how_many(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**شارةٌ مُنحت لأحدٍ لا تُحذف** — و`CASCADE` كان سيمحو المنحَ صامتاً.

    **والقياسُ بالنقض**: تُحذف قبل المنح، وتُرفض بعده — والاتجاهان معاً، وإلا
    قِيس المنعُ ولم يُقس أن الحذفَ يعمل أصلاً.
    """
    free = await client.post(
        "/admin/badges",
        json={"key": "unused_badge", "label": "شارةٌ بلا منحة"},
        headers=admin_headers,
    )
    assert free.status_code == 201, free.text
    gone = await client.delete(
        f"/admin/badges/{free.json()['id']}", headers=admin_headers
    )
    assert gone.status_code == 204, gone.text

    used = await client.post(
        "/admin/badges",
        json={"key": "granted_badge", "label": "شارةٌ مُنحت"},
        headers=admin_headers,
    )
    badge_id = used.json()["id"]
    driver = await approved_driver(client, session_factory, DRIVER)
    granted = await client.post(
        f"/admin/drivers/{driver['driver_id']}/badges",
        json={"badge_id": badge_id, "note": "منحةُ قياس"},
        headers=admin_headers,
    )
    assert granted.status_code == 201, granted.text

    refused = await client.delete(
        f"/admin/badges/{badge_id}", headers=admin_headers
    )
    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "row_in_use"
    # **والرسالةُ تقول العدد** — «لا تُحذف» وحدَها لا تقول لماذا
    assert "1" in refused.json()["message"]

    async with session_factory() as session:
        assert await session.get(Badge, badge_id) is not None
        assert (
            await session.scalar(
                select(DriverBadge).where(DriverBadge.badge_id == badge_id)
            )
        ) is not None


async def test_a_mission_whose_month_has_started_is_not_deleted(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**مهمّةٌ بدأ شهرُها يعمل عليها كباتن** — تُطفأ لا تُحذف.

    **ولا جدولَ تقدّمٍ يُسأل**: التقدّمُ يُحسب من الرحلات، **فالسؤالُ عن
    الشهر** — ومهمّةُ شهرٍ لم يبدأ لم يعمل عليها أحد.
    """
    this_month = date.today().replace(day=1)
    next_month = (this_month + timedelta(days=40)).replace(day=1)

    future = await client.post(
        "/admin/missions",
        params={"country_code": "JO"},
        json={
            "month": next_month.isoformat(),
            "metric": "completed_rides",
            "target": 50,
            "title": "مهمّةُ شهرٍ قادم",
        },
        headers=admin_headers,
    )
    assert future.status_code == 201, future.text
    assert (
        await client.delete(
            f"/admin/missions/{future.json()['id']}", headers=admin_headers
        )
    ).status_code == 204

    running = await client.post(
        "/admin/missions",
        params={"country_code": "JO"},
        json={
            "month": this_month.isoformat(),
            "metric": "completed_rides",
            "target": 40,
            "title": "مهمّةُ هذا الشهر",
        },
        headers=admin_headers,
    )
    assert running.status_code == 201, running.text
    refused = await client.delete(
        f"/admin/missions/{running.json()['id']}", headers=admin_headers
    )
    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "row_in_use"

    async with session_factory() as session:
        assert await session.get(Mission, running.json()["id"]) is not None


async def test_a_delete_records_what_was_deleted_not_only_its_id(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**المحذوفُ لا يُقرأ بعد حذفه** — فتُكتب لقطتُه في السجلّ.

    **وحذفٌ يسجّل معرّفاً وحدَه** يترك من يقرأ بعد شهرٍ أمام رقمٍ لا صفَّ له.
    """
    created = await client.post(
        "/admin/badges",
        json={"key": "snapshot_badge", "label": "شارةٌ تُحذف", "icon": "star"},
        headers=admin_headers,
    )
    badge_id = created.json()["id"]
    assert (
        await client.delete(f"/admin/badges/{badge_id}", headers=admin_headers)
    ).status_code == 204

    entry = await _last_entry(session_factory, "badge")
    assert entry.action is AuditAction.DELETE
    assert entry.details["deleted"]["key"] == "snapshot_badge"
    assert entry.details["deleted"]["label"] == "شارةٌ تُحذف"
