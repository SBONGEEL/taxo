"""التحكّمُ بالمستخدمين والتواصلُ الفرديّ — **البند ١١ (§39٫١١، §46)**.

**وما يُختبر هنا حدودُ البابين قبل عملهما**:

1. **حقلان لا أكثر** — والهاتفُ والسوقُ والأدوارُ لا تُمسّ من هذا الباب.
2. **وكتابةُ بريدٍ تُسقط إثباتَه** — فبريدٌ يكتبه مشرفٌ ويبقى مُثبَتاً بابُ
   استيلاءٍ على حساب (§31 والفهرسُ الجزئيُّ على المُثبَت).
3. **والرسالةُ تمرّ بمسار FCM القائم** — صفٌّ في صندوق الوارد، **ونصُّها في
   التدقيق كاملاً**.
4. **ولا تُرسل إلى موظّف** — اللوحةُ ليست صندوقَ بريدٍ داخلياً.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.models.notification import UserNotification
from app.models.user import User
from tests.helpers import RIDER, rider_session


async def test_the_door_edits_a_name_and_stamps_before_and_after(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**القيمةُ قبل وبعد** (§40٫١) — «عُدِّل الاسم» لا تقول شيئاً بعد شهر."""
    rider = await rider_session(client)
    user_id = rider["user"]["id"]

    edited = await client.patch(
        f"/admin/users/{user_id}",
        json={"name": "راكبٌ صُحّح اسمُه"},
        headers=admin_headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["name"] == "راكبٌ صُحّح اسمُه"

    async with session_factory() as session:
        entry = await session.scalar(
            select(AdminAuditLog).where(AdminAuditLog.entity_type == "user")
        )
    assert entry.details["changes"]["name"] == {
        "before": RIDER["name"],
        "after": "راكبٌ صُحّح اسمُه",
    }


async def test_writing_an_email_drops_its_proof(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**المُثبَتُ وحدَه يحجز ويصلح قناةَ استرجاع** (§31) — فبريدٌ يكتبه مشرفٌ
    ويبقى مُثبَتاً بابُ استيلاءٍ على حساب."""
    rider = await rider_session(client)
    user_id = rider["user"]["id"]

    async with session_factory() as session:
        someone = await session.get(User, uuid.UUID(user_id))
        someone.email = "old@example.com"
        someone.email_verified_at = datetime.now(UTC)
        await session.commit()

    edited = await client.patch(
        f"/admin/users/{user_id}",
        json={"email": "new@example.com"},
        headers=admin_headers,
    )
    assert edited.status_code == 200, edited.text

    async with session_factory() as session:
        after = await session.get(User, uuid.UUID(user_id))
        assert after.email == "new@example.com"
        assert after.email_verified_at is None, "الإثباتُ يسقط مع كلِّ كتابةٍ من اللوحة"


async def test_the_door_refuses_to_empty_a_name(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**ولا يُمحى اسمُ حساب** — وهو ما يظهر للكبتن في بطاقة الرحلة."""
    rider = await rider_session(client)
    refused = await client.patch(
        f"/admin/users/{rider['user']['id']}",
        json={"name": "   "},
        headers=admin_headers,
    )
    assert refused.status_code == 422, refused.text


async def test_phone_and_country_are_not_editable_from_this_door(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**الهاتفُ مُعرِّفُ الدخول، والسوقُ مختومٌ على كلِّ رحلةٍ ودفعة** —
    والعقدُ يرفض ما ليس فيه (`extra` غيرُ مسموحٍ في التغيير الفعليّ)."""
    rider = await rider_session(client)
    user_id = rider["user"]["id"]
    before_phone = rider["user"]["phone"]

    sent = await client.patch(
        f"/admin/users/{user_id}",
        json={"phone": "+962790909090", "country_code": "LY"},
        headers=admin_headers,
    )
    assert sent.status_code == 200, sent.text

    async with session_factory() as session:
        after = await session.get(User, uuid.UUID(user_id))
    assert after.phone == before_phone, "الرقمُ لا يُحرَّر من هذا الباب"
    assert after.country_code.value == "JO", "والسوقُ كذلك"


async def test_a_message_lands_in_the_inbox_and_in_the_audit(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**بمسار FCM القائم**: صفٌّ في صندوق الوارد ولو بلا عقدِ إشعارات،
    **ونصُّها في التدقيق كاملاً** — «أُرسلت رسالة» لا تقول شيئاً بعد شهر."""
    rider = await rider_session(client)
    user_id = rider["user"]["id"]

    sent = await client.post(
        f"/admin/users/{user_id}/notify",
        json={"title": "بخصوص رحلتك", "body": "راجعنا شكواك وأُعيد المبلغ."},
        headers=admin_headers,
    )
    assert sent.status_code == 204, sent.text

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(UserNotification).where(
                    UserNotification.user_id == uuid.UUID(user_id)
                )
            )
        ).all()
        entry = await session.scalar(
            select(AdminAuditLog).where(
                AdminAuditLog.entity_type == "user_message"
            )
        )

    assert [row.kind for row in rows] == ["admin_message"]
    assert rows[0].title == "بخصوص رحلتك"
    assert rows[0].body == "راجعنا شكواك وأُعيد المبلغ."
    # **و`data` بلا جملةٍ مؤلَّفة** — القاعدةُ التي يحرسها `test_notification_data`
    assert rows[0].data == {"type": "admin_message"}
    assert entry.details == {
        "title": "بخصوص رحلتك",
        "body": "راجعنا شكواك وأُعيد المبلغ.",
    }


async def test_a_message_is_never_sent_to_a_staff_account(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**اللوحةُ ليست صندوقَ بريدٍ داخلياً** — ورسالةُ عملاءَ إلى مشرفٍ تخلط
    قناةَ العملاء بقناة العمل."""
    async with session_factory() as session:
        staff = await session.scalar(
            select(User).where(User.role.in_(("admin", "support")))
        )

    refused = await client.post(
        f"/admin/users/{staff.id}/notify",
        json={"title": "عنوان", "body": "نص"},
        headers=admin_headers,
    )
    assert refused.status_code == 422, refused.text


async def test_support_may_not_edit_or_message(
    client: AsyncClient, support_headers: dict
) -> None:
    """**`users.manage` لا `read.only`** — والدعمُ يقرأ ويحسم النزاعات."""
    rider = await rider_session(client)
    user_id = rider["user"]["id"]

    assert (
        await client.patch(
            f"/admin/users/{user_id}", json={"name": "اسمٌ آخر"}, headers=support_headers
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/admin/users/{user_id}/notify",
            json={"title": "عنوان", "body": "نص"},
            headers=support_headers,
        )
    ).status_code == 403
