"""دخولُ اللوحة باسمِ مستخدم (2026-08-20، SPEC §25.9).

**وما يُقاس هنا ليس أن الدخولَ يعمل، بل أن أربعةَ شروطٍ لم تُمسّ**: الاسمُ
للمشرفين وحدَهم، ولا يفتح تطبيقَي الراكب والكبتن، ورسالةُ الفشل واحدة، والعاملُ
الثاني إلزاميٌّ كما كان.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

from app.models.admin_credential import AdminCredential
from app.models.enums import UserRole
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.services import admin_credentials
from app.services.auth.password import set_password

pytestmark = pytest.mark.asyncio

PASSWORD = "MudiirLohaTaxo!27"


async def _admin_with_username(
    session_factory, username: str, *, break_glass: bool = False
) -> uuid.UUID:
    from app.core.redis_client import get_redis_client

    async with session_factory() as session:
        user = User(
            phone=None,
            name="مشرفٌ بلا رقم",
            role=UserRole.ADMIN,
            country_code="JO",
            role_grants=[UserRoleGrant(role=UserRole.ADMIN)],
        )
        session.add(user)
        await session.flush()
        await set_password(
            session, get_redis_client(), user=user, new_password=PASSWORD
        )
        await admin_credentials.create(
            session, user=user, username=username, is_break_glass=break_glass
        )
        await session.commit()
        return user.id


async def test_an_admin_logs_in_with_a_username_and_no_phone(
    client, session_factory
) -> None:
    """**اللوحةُ تُدخَل باسمٍ لا برقم** — والحسابُ بلا رقمٍ أصلاً."""
    await _admin_with_username(session_factory, "muraqib.awwal")

    answer = await client.post(
        "/auth/login",
        json={"username": "muraqib.awwal", "password": PASSWORD, "app": "panel"},
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["user"]["phone"] is None
    assert body["tokens"]["access_token"]


async def test_the_username_is_case_insensitive(client, session_factory) -> None:
    """**إنسانٌ واحدٌ لا حسابان**.

    من يكتب اسمَه بحرفٍ كبيرٍ في هاتفه وصغيرٍ في حاسوبه هو هو — وفهرسٌ حسّاسٌ
    لحالة الأحرف يجعلهما اثنين.
    """
    await _admin_with_username(session_factory, "Muraqib.Thani")

    answer = await client.post(
        "/auth/login",
        json={"username": "MURAQIB.THANI", "password": PASSWORD, "app": "panel"},
    )
    assert answer.status_code == 200, answer.text


async def test_one_failure_message_for_both_causes(client, session_factory) -> None:
    """**الاستثناءُ الأمنيُّ باقٍ**: «لا وجودَ للاسم» و«كلمةٌ خاطئة» جوابٌ واحد.

    والتفريقُ بينهما يجعل مسارَ الدخول **عدّاداً للحسابات**.
    """
    await _admin_with_username(session_factory, "muraqib.thalith")

    missing = await client.post(
        "/auth/login",
        json={"username": "la.wujuda.lah", "password": PASSWORD, "app": "panel"},
    )
    wrong = await client.post(
        "/auth/login",
        json={
            "username": "muraqib.thalith",
            "password": "GhayrSahih!27",
            "app": "panel",
        },
    )
    assert missing.status_code == wrong.status_code == 401
    assert missing.json()["code"] == wrong.json()["code"]
    assert missing.json()["message"] == wrong.json()["message"]


async def test_a_username_does_not_open_the_rider_or_driver_app(
    client, session_factory
) -> None:
    """**ولا يصير الاسمُ مدخلاً بديلاً للتطبيقين** — و`app_scope` لم يُمسّ."""
    await _admin_with_username(session_factory, "muraqib.rabi")

    for app_name in ("rider", "driver"):
        refused = await client.post(
            "/auth/login",
            json={
                "username": "muraqib.rabi",
                "password": PASSWORD,
                "app": app_name,
            },
        )
        assert refused.status_code == 403, refused.text
        assert refused.json()["code"] == "wrong_app_for_role"


async def test_sending_both_identifiers_is_refused(client, session_factory) -> None:
    """**مُعرِّفٌ واحدٌ لا اثنان**: أيُّهما يُصدَّق لو تعارضا؟"""
    await _admin_with_username(session_factory, "muraqib.khamis")

    both = await client.post(
        "/auth/login",
        json={
            "username": "muraqib.khamis",
            "phone": "+962790000000",
            "password": PASSWORD,
            "app": "panel",
        },
    )
    assert both.status_code == 422, both.text

    neither = await client.post(
        "/auth/login", json={"password": PASSWORD, "app": "panel"}
    )
    assert neither.status_code == 422, neither.text


async def test_a_break_glass_login_is_written_to_the_audit_log(
    client, session_factory
) -> None:
    """**بابٌ نائمٌ يُعرف حين يُفتح** — لا بعد شهرٍ من قراءة سجلٍّ لا يميّزه."""
    from app.models.audit import AdminAuditLog

    await _admin_with_username(session_factory, "tawaari.wahid", break_glass=True)

    answer = await client.post(
        "/auth/login",
        json={"username": "tawaari.wahid", "password": PASSWORD, "app": "panel"},
    )
    assert answer.status_code == 200, answer.text

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_type == "admin_break_glass_login"
                )
            )
        ).all()
    assert rows, "دخولُ حسابِ الطوارئ بلا صفِّ تدقيق"
    assert rows[-1].details["username"] == "tawaari.wahid"


async def test_an_ordinary_admin_login_is_not_marked_break_glass(
    client, session_factory
) -> None:
    """ولا يُصاح على العاديّ — وإلا صار الصياحُ ضجيجاً يُقرأ ولا يُميَّز."""
    from app.models.audit import AdminAuditLog

    await _admin_with_username(session_factory, "muraqib.aadi")
    await client.post(
        "/auth/login",
        json={"username": "muraqib.aadi", "password": PASSWORD, "app": "panel"},
    )
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_type == "admin_break_glass_login"
                )
            )
        ).all()
    assert not rows


async def test_several_admins_may_have_no_phone_at_all(
    client, session_factory
) -> None:
    """**الفهرسُ الفريدُ يسمح بعدّة `NULL`** — قياسُ الترحيلة لا افتراضُها.

    Postgres يعدّ كلَّ `NULL` مختلفاً في الفهرس الفريد، فمشرفون بلا أرقامٍ لا
    يتزاحمون.
    """
    for name in ("bila.raqm.a", "bila.raqm.b", "bila.raqm.c"):
        await _admin_with_username(session_factory, name)

    async with session_factory() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM users WHERE phone IS NULL")
        )
    assert count >= 3, "الفهرسُ رفض عدّةَ NULL"


async def test_a_duplicate_real_phone_is_still_refused(session_factory) -> None:
    """**ورقمٌ حقيقيٌّ ما زال لا يتكرر** — النصفُ الآخر من القياس نفسِه."""
    from sqlalchemy.exc import IntegrityError

    async with session_factory() as session:
        session.add(
            User(
                phone="+962799111222",
                name="أول",
                role=UserRole.RIDER,
                country_code="JO",
            )
        )
        await session.commit()

    with pytest.raises(IntegrityError):
        async with session_factory() as session:
            session.add(
                User(
                    phone="+962799111222",
                    name="ثانٍ",
                    role=UserRole.RIDER,
                    country_code="JO",
                )
            )
            await session.commit()


async def test_a_forbidden_username_is_refused() -> None:
    """**لا `admin` ولا `taxo` ولا `root`** — أولُ ما يُجرَّب على أيِّ لوحة."""
    from app.core.exceptions import InvalidInput

    for name in ("admin", "TAXO", "root"):
        with pytest.raises(InvalidInput):
            admin_credentials.validate_username(name)


async def test_a_username_must_be_unique(client, session_factory) -> None:
    """اسمان متطابقان حسابان يتنازعان بابَ دخولٍ واحد."""
    from app.core.exceptions import Conflict

    await _admin_with_username(session_factory, "mukarrar")

    with pytest.raises(Conflict):
        await _admin_with_username(session_factory, "MUKARRAR")


async def test_renaming_records_both_names_in_the_audit_log(
    client, session_factory
) -> None:
    """**استثناءُ «لا قيمَ في التدقيق»**: القيمةُ هنا **هي الحدث**.

    ومن يقرأ السجلَّ بعد شهرٍ يسأل «من صار من؟» — واسمُ حقلٍ تغيّر لا يجيبه.
    """
    from app.models.audit import AdminAuditLog

    user_id = await _admin_with_username(session_factory, "ism.qadim")

    async with session_factory() as session:
        user = await session.get(User, user_id)
        await admin_credentials.rename(
            session, user=user, new_username="ism.jadid"
        )
        await session.commit()

    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_type == "admin_credential"
                )
            )
        ).all()
        row = await session.scalar(
            select(AdminCredential).where(AdminCredential.user_id == user_id)
        )

    assert row.username == "ism.jadid"
    assert rows[-1].details["from"] == "ism.qadim"
    assert rows[-1].details["to"] == "ism.jadid"
