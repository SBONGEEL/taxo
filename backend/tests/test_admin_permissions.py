"""مصفوفةُ صلاحيات المشرفين — البند ٥ (§39٫٥، قرارُ المالك 2026-09-02).

**وأهمُّ ما يقيسه هذا الملفُّ ليس المنعَ بل عدمَه**: «**المصفوفةُ لا تبدّل
سلوكاً قائماً في يومها الأول**» — فالجدولُ فارغٌ، وكلُّ مشرفٍ يُقرأ بافتراض
دوره، **و`admin` يملك الكلَّ كما كان `AdminUser` يفتح له**.

**والثلاثةُ المحروسة تُقاس بالنقض**: كلُّ واحدةٍ **تُجرَّب فتُرفض** (شرطُ
المالك) — لا تُوصف في تعليق.
"""

from __future__ import annotations

import ast
import pathlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import AdminPermission, UserRole
from app.models.user import User
from app.services import permissions as permissions_service

pytestmark = pytest.mark.usefixtures("jordan_settings")


# ═════════════════════════ الافتراضُ يوافق ما يقع اليوم


async def test_the_matrix_changes_nothing_on_its_first_day(
    client: AsyncClient, admin_headers: dict, support_headers: dict
) -> None:
    """**والجدولُ فارغ** — فكلُّ مشرفٍ يبقى على ما كان عليه بالضبط.

    **ويُقاس على أبوابٍ حقيقيةٍ من نطاقاتٍ مختلفة**، لا على الدالّة وحدَها:
    `admin` يمرّ من الإعدادات والمالية والنمو، **و`support` يُردّ منها ويقرأ
    القوائم** — وهو ما كان `AdminUser` يفعله حرفاً.
    """
    for path in (
        "/admin/settings/feature-flags",
        "/admin/withdrawals",
        "/admin/campaigns",
    ):
        assert (await client.get(path, headers=admin_headers)).status_code == 200, path

    # **القراءةُ تبقى للاثنين** — `read.only` في افتراض `support`
    assert (
        await client.get("/admin/users", headers=support_headers)
    ).status_code == 200

    # **والكتابةُ تُردّ عنه كما كانت** — لا يملك `users.manage`
    refused = await client.post(
        "/admin/users/00000000-0000-0000-0000-000000000000/block",
        json={"reason": "محاولةٌ من دعم"},
        headers=support_headers,
    )
    assert refused.status_code == 403, refused.text


async def test_the_eleven_are_declared_and_admin_holds_them_all() -> None:
    """**إحدى عشرةَ لا أكثر ولا أقلّ** — والقائمةُ هي التي أقرّها المالك."""
    assert {p.value for p in AdminPermission} == {
        "settings.write",
        "users.manage",
        "finance.manage",
        "growth.manage",
        "fleet.manage",
        "providers.manage",
        "backups.manage",
        "payments.resolve",
        "read.only",
        "security.manage",
        "permissions.manage",
    }
    assert permissions_service.DEFAULTS[UserRole.ADMIN] == permissions_service.ALL
    assert permissions_service.DEFAULTS[UserRole.SUPPORT] == {
        AdminPermission.READ_ONLY,
        AdminPermission.PAYMENTS_RESOLVE,
    }


# ═════════════════════════ والمصفوفةُ تحكم فعلاً حين تُكتب


async def test_a_granted_set_replaces_the_role_default_and_is_enforced(
    client: AsyncClient, session_factory, admin_headers: dict, support_headers: dict
) -> None:
    """**أوّلُ صفٍّ يُمنح يحكم** — لا «فوق الافتراض»، وإلا استحال النزع.

    **ويُقاس على بابٍ حقيقيّ**: `support` لا يملك `growth.manage` بالافتراض،
    **فإن مُنحها فتح بابَ الحملات** — وهو ما تعنيه المصفوفة.
    """
    listed = await client.get("/admin/permissions", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    support = next(row for row in listed.json() if "support" in row["roles"])
    assert support["explicit"] is False
    assert sorted(support["permissions"]) == ["payments.resolve", "read.only"]

    # **قبل المنح: البابُ مغلق**
    before = await client.post(
        "/admin/campaigns",
        json={"title": "قياس", "body": "نصّ", "audience": "all_riders"},
        headers=support_headers,
    )
    assert before.status_code == 403, before.text

    granted = await client.put(
        f"/admin/permissions/{support['user_id']}",
        json={"permissions": ["read.only", "payments.resolve", "growth.manage"]},
        headers=admin_headers,
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["explicit"] is True

    # **وبعده: يُفتح** — والمصفوفةُ تحكم أبواباً لا جدولاً في شاشة
    after = await client.post(
        "/admin/campaigns",
        json={"title": "قياس", "body": "نصّ", "audience": "all_riders"},
        headers=support_headers,
    )
    assert after.status_code in (200, 201), after.text

    # **والنزعُ يُغلقه ثانيةً** — وهو ما يجعل الاستبدالَ لا الإضافة
    await client.put(
        f"/admin/permissions/{support['user_id']}",
        json={"permissions": ["read.only"]},
        headers=admin_headers,
    )
    closed = await client.post(
        "/admin/campaigns",
        json={"title": "قياس", "body": "نصّ", "audience": "all_riders"},
        headers=support_headers,
    )
    assert closed.status_code == 403, closed.text


# ═════════════════════════ الثلاثةُ المحروسة — تُجرَّب فتُرفض


async def test_an_admin_may_not_change_his_own_permissions(
    client: AsyncClient, admin_headers: dict
) -> None:
    """**ولا يرفع مشرفٌ صلاحيةَ نفسه** — وإلا صارت المصفوفةُ زينة.

    **ولا يقتصر المنعُ على الرفع**: من يملك أن ينزع عن نفسه يملك أن يعيد،
    **فالبابُ مغلقٌ على النفس في الاتجاهين** — ويفعلها مشرفٌ آخر.
    """
    listed = (await client.get("/admin/permissions", headers=admin_headers)).json()
    me = next(row for row in listed if "admin" in row["roles"])
    refused = await client.put(
        f"/admin/permissions/{me['user_id']}",
        json={"permissions": ["read.only"]},
        headers=admin_headers,
    )
    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "self_elevation"


async def test_the_last_permissions_manager_is_not_stripped(
    client: AsyncClient,
    session_factory,
    admin_headers: dict,
    support_headers: dict,
) -> None:
    """**ولا يُنزع آخرُ من يملك المنح** — وإلا أُغلق البابُ على الجميع.

    ## ⚠ والبابُ لا يبلغ هذا الحارسَ اليوم — **وهذا مقيسٌ لا مُرجَّح**

    **الفاعلُ يجب أن يملك `permissions.manage` ليصل الباب**، **ولا يعدّل نفسَه**
    (الحارسُ الثاني) — **فهو محسوبٌ في العدّ دائماً وليس هو الهدف**، فالعددُ
    اثنان فأكثر كلَّما وقع نزعٌ. **والحارسُ الثالثُ إذاً مضمونٌ بالثاني** على
    هذا الباب.

    **ولا يُترك بلا قياسٍ لذلك**: «شرطٌ لا يتحقّق أبداً يُقرأ حراسةً وهو
    تعطيل» — **فيُقاس على الخدمة مباشرةً** بحالٍ لا يبلغها الباب: فاعلٌ لا
    يملك المنحَ وهدفٌ هو آخرُ من يملكه. **وهو ما يحرسه يومَ يُفتح بابٌ ثانٍ**
    (منحٌ آليّ، أو مسارٌ يُسقط حساباً) **يبلغ هذه الدالّةَ من غير هذا الطريق**.
    """
    assert support_headers
    listed = (await client.get("/admin/permissions", headers=admin_headers)).json()
    support = next(row for row in listed if "support" in row["roles"])
    admin_row = next(row for row in listed if "admin" in row["roles"])

    # **يُصرَّح للمشرف بمجموعةٍ بلا منح** — فيبقى الدعمُ آخرَ من يملكه
    await client.put(
        f"/admin/permissions/{support['user_id']}",
        json={"permissions": ["read.only", "permissions.manage"]},
        headers=admin_headers,
    )

    async with session_factory() as session:
        actor = await session.get(User, uuid.UUID(admin_row["user_id"]))
        target = await session.get(User, uuid.UUID(support["user_id"]))
        # **الفاعلُ يُنزع منه المنحُ** — حالٌ لا يبلغها الباب، وتبلغها الخدمة
        await permissions_service.set_for_user(
            session,
            target=actor,
            actor=target,
            permissions={AdminPermission.READ_ONLY},
        )
        await session.commit()

    async with session_factory() as session:
        actor = await session.get(User, uuid.UUID(admin_row["user_id"]))
        target = await session.get(User, uuid.UUID(support["user_id"]))
        assert await permissions_service._managers_count(session) == 1
        with pytest.raises(permissions_service.LastPermissionsManager):
            await permissions_service.set_for_user(
                session,
                target=target,
                actor=actor,
                permissions={AdminPermission.READ_ONLY},
            )


def test_no_path_writes_is_break_glass() -> None:
    """**`is_break_glass` لا يُمسّ** (شرطُ المالك) — **ويُقاس بمسح الشجرة**.

    **وتعليقٌ يَعِد بأنه لا يُمسّ ليس ضماناً**: هذا الاختبارُ يقرأ كلَّ ملفٍّ
    في `app/` بمُحلِّل بايثون **ويشترط ألّا يُسنَد إليه في أيِّ مسار**.

    **والترحيلاتُ والبذرةُ خارجَه بعلّتهما**: الأولى تُنشئ العمود، والثانية
    تكتب حسابَ الطوارئ نفسَه — **وكلاهما ليس «مساراً» يفتحه طلبٌ**.
    """
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders: list[str] = []
    scanned = 0
    for path in sorted(root.rglob("*.py")):
        scanned += 1
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AugAssign):
                targets = [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr == "is_break_glass"
                ):
                    offenders.append(f"{path.name}:{node.lineno}")

    # **إثباتُ الصمت**: مسحٌ لا يقرأ شيئاً يصمت بلا معنى
    assert scanned >= 80, f"لم يُقرأ إلا {scanned} ملفّاً — المسحُ أعمى"
    assert not offenders, (
        "مسارٌ يكتب `is_break_glass` — وهو لا يُمسّ (§39٫٥):\n  "
        + "\n  ".join(offenders)
    )
