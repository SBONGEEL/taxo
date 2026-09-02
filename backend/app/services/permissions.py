"""مصفوفةُ صلاحيات المشرفين — **بيتُ السؤال الواحد** (البند ٥، §39٫٥).

## الافتراضُ يوافق ما يقع اليوم — **وهو شرطُ المالك**

> «والافتراضُ كما اقترحتَه وقبلتُه: `support` يقرأ ويحسم النزاعات لا أكثر —
> **لأنه ما يقع اليوم حرفاً**، فالمصفوفةُ لا تبدّل سلوكاً قائماً في يومها
> الأول».

**و`admin` يملك الكلَّ**: وهو أيضاً ما يقع اليوم — `AdminUser` يفتح له كلَّ
باب. **فاستبدالُ `AdminUser` بـ`require_permission` لا يغيّر جواباً واحداً
يومَ نُشر**، والمجموعةُ الخضراء هي البرهان.

## والغيابُ «افتراضُ الدور» لا «ممنوع»

**وأوّلُ صفٍّ يُمنح يحكم**: من مُنح صلاحيةً واحدةً صارت مجموعتُه **تلك
وحدَها**، لا «تلك فوق افتراضه». **وإلا صار نزعُ صلاحيةٍ مستحيلاً** — لأن
الافتراضَ يعيدها في كلِّ قراءة.

## والثلاثةُ المحروسة — **في الخلفية لا في الشاشة**

1. **`is_break_glass` لا يُمسّ** — ولا بابَ يكتبه أصلاً، **ويقيس ذلك اختبارٌ
   يمسح الشجرة** لا تعليقٌ يَعِد.
2. **ولا يرفع مشرفٌ صلاحيةَ نفسه** — وإلا فكلُّ من ملك `permissions.manage`
   ملك كلَّ شيءٍ بضغطة، **فتصير المصفوفةُ زينة**.
3. **ولا يُنزع آخرُ `permissions.manage`** — وإلا أُغلق البابُ على الجميع
   **ولا أحدَ يفتحه من داخل النظام**.

**وإخفاءُ الواجهة راحةٌ لا حماية** (§21): الثلاثةُ تُفحص هنا، وما تخفيه الشاشةُ
لا يمنع طلباً.
"""

from __future__ import annotations

import uuid

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, PermissionDenied
from app.models.admin_permission import AdminPermissionGrant
from app.models.enums import AdminPermission, UserRole
from app.models.user import User

#: كلُّ الصلاحيات — **مشتقّةٌ من التعداد لا مكتوبةٌ بيد**، فعضوٌ يُضاف يصلها
ALL: frozenset[AdminPermission] = frozenset(AdminPermission)

#: **ما يقع اليومَ حرفاً**، لا ما نتمنّاه: `support` يقرأ ويحسم النزاعات.
SUPPORT_DEFAULT: frozenset[AdminPermission] = frozenset(
    {AdminPermission.READ_ONLY, AdminPermission.PAYMENTS_RESOLVE}
)

DEFAULTS: dict[UserRole, frozenset[AdminPermission]] = {
    UserRole.ADMIN: ALL,
    UserRole.SUPPORT: SUPPORT_DEFAULT,
}


def default_for(user: User) -> frozenset[AdminPermission]:
    """افتراضُ الدور — **وأوسعُ دورٍ يملكه يغلب**.

    **وحسابٌ بدورين** (نموذجُ الأدوار مجموعةٌ لا عمود، §21) **يأخذ اتحادَهما**
    لا أوّلَهما: من يملك `admin` و`support` معاً مشرفٌ، **وقراءةُ أوّلِ دورٍ في
    القائمة تجعل الجوابَ يتبع ترتيباً لا معنى له**.
    """
    granted: frozenset[AdminPermission] = frozenset()
    for role in user.roles:
        granted |= DEFAULTS.get(role, frozenset())
    return granted


async def for_user(session: AsyncSession, user: User) -> frozenset[AdminPermission]:
    """ما يملكه هذا المشرفُ فعلاً — **الصفوفُ إن وُجدت، وإلا افتراضُ دوره**."""
    rows = set(
        await session.scalars(
            select(AdminPermissionGrant.permission).where(
                AdminPermissionGrant.user_id == user.id
            )
        )
    )
    if rows:
        return frozenset(rows)
    return default_for(user)


async def holds(
    session: AsyncSession, user: User, permission: AdminPermission
) -> bool:
    return permission in await for_user(session, user)


# ═════════════════════════ الثلاثةُ المحروسة


class LastPermissionsManager(InvalidInput):
    """**آخرُ من يملك المنحَ لا يُنزع منه** — وإلا أُغلق البابُ على الجميع."""

    code = "last_permissions_manager"
    message = (
        "لا يُنزع آخرُ من يملك «إدارة الصلاحيات» — "
        "ولا أحدَ يفتح البابَ بعدها من داخل النظام"
    )


class SelfElevation(InvalidInput):
    """**ولا يرفع مشرفٌ صلاحيةَ نفسه** — وإلا صارت المصفوفةُ زينة."""

    code = "self_elevation"
    message = "لا تُعدَّل صلاحياتُك بيدك — يفعلها مشرفٌ آخر"


async def _managers_count(session: AsyncSession) -> int:
    """**من يملك المنحَ فعلاً**: أصحابُ الصفوف، ومعهم من يقرؤه افتراضُ دوره.

    **ولا يُعدُّ أصحابُ الصفوف وحدَهم**: الجدولُ فارغٌ اليوم، **فعدٌّ عليه
    يقول صفراً** ويمنع أوّلَ منحٍ يقع.
    """
    with_rows = set(
        await session.scalars(
            select(AdminPermissionGrant.user_id).where(
                AdminPermissionGrant.permission == AdminPermission.PERMISSIONS_MANAGE
            )
        )
    )
    # ومن لا صفَّ له يُقرأ بافتراض دوره — و`admin` يملك الكلّ
    from app.models.user_role_grant import has_role_clause

    admins = set(
        await session.scalars(
            select(User.id).where(has_role_clause(UserRole.ADMIN), ~User.is_blocked)
        )
    )
    without_rows = set(
        await session.scalars(
            select(User.id).where(
                User.id.in_(admins),
                ~select(AdminPermissionGrant.id)
                .where(AdminPermissionGrant.user_id == User.id)
                .exists(),
            )
        )
    )
    return len(with_rows | without_rows)


async def set_for_user(
    session: AsyncSession,
    *,
    target: User,
    actor: User,
    permissions: set[AdminPermission],
) -> frozenset[AdminPermission]:
    """يكتب مجموعةَ المشرف كاملةً — **استبدالٌ لا إضافة**.

    **والاستبدالُ هو ما يجعل النزعَ ممكناً**: إضافةٌ فقط تعني أن ما مُنح لا
    يُسحب أبداً.
    """
    if target.id == actor.id:
        raise SelfElevation()

    before = await for_user(session, target)
    losing_manager = (
        AdminPermission.PERMISSIONS_MANAGE in before
        and AdminPermission.PERMISSIONS_MANAGE not in permissions
    )
    if losing_manager and await _managers_count(session) <= 1:
        raise LastPermissionsManager()

    existing = list(
        await session.scalars(
            select(AdminPermissionGrant).where(
                AdminPermissionGrant.user_id == target.id
            )
        )
    )
    for row in existing:
        await session.delete(row)
    # **الحذفُ يُدفع قبل الإدراج** — وإلا رتّبت الوحدةُ الإدراجَ أوّلاً فسقط
    # على `uq_admin_permissions_user_permission` حين تبقى صلاحيةٌ كما كانت
    # (قِيس 2026-09-02: `read.only` موجودةٌ قبلُ وبعدُ)
    await session.flush()
    for permission in sorted(permissions, key=lambda p: p.value):
        session.add(
            AdminPermissionGrant(
                user_id=target.id, permission=permission, granted_by=actor.id
            )
        )
    return frozenset(permissions)


# ═════════════════════════ الحارسُ على الأبواب


def require_permission(permission: AdminPermission):
    """حارسُ بابٍ بصلاحيةٍ مسمّاة — **بديلُ `AdminUser` لا إضافةٌ فوقه**.

    **ويومَ نُشر لم يغيّر جواباً**: `admin` يملك الكلَّ فيمرّ كما كان، و
    `support` لا يملك إلا القراءةَ وفصلَ النزاع **فيُردّ كما كان يُردّ**.
    """
    from app.core.db import get_session
    from app.core.deps import require_roles

    # **يُبنى الاعتمادُ لا يُشار إليه بالاسم**: هذا الملفُّ فيه
    # `from __future__ import annotations`، **فالتعليقاتُ نصوصٌ** يحلّها
    # FastAPI في فضاء الوحدة — واسمٌ مستوردٌ داخل دالّةٍ لا وجودَ له هناك،
    # **فيُقرأ `user` حقلاً مطلوباً في الجسم ويرتدّ الطلبُ ٤٢٢**.
    # (وقع مقيساً 2026-09-02: خمسةُ اختباراتٍ قالت «حقلٌ مطلوبٌ ناقص: user»).
    staff_guard = require_roles(UserRole.ADMIN, UserRole.SUPPORT)

    async def guard(
        user: User = Depends(staff_guard),
        session: AsyncSession = Depends(get_session),
    ) -> User:
        if permission not in await for_user(session, user):
            # **ولا يُقال أيُّ صلاحيةٍ تنقص لمن ليس طاقماً** — الحارسُ فوقَه
            # (`StaffUser`) ردّ من ليس مشرفاً أصلاً، فالتسميةُ هنا تفيد ولا تكشف
            raise PermissionDenied(
                f"هذا الإجراء يحتاج صلاحية «{permission.value}»"
            )
        return user

    return guard
