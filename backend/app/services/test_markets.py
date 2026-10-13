"""وصولُ حسابات التجربة إلى كلِّ سوق، ومالُ التجربة (SPEC §٧٤-أ/١٠) — **البيتُ الواحد**.

**التوأمُ لا السوقُ المتبدِّل**: لكلِّ سوقٍ حسابُ تجربةٍ بمحفظته وعملته واشتراكه، **والإخوةُ يجمعهم `users.test_twin_of`** (يشير إلى الأوّل). فمُختارُ
السوق — **الذي لا يراه إلا حسابُ التجربة** — **دخولٌ إلى الأخ** بجلسةٍ جديدة (`switch`)، وكلُّ دخولٍ سطرٌ في التدقيق. **والسوقُ يحدّد** العملةَ
والأسعارَ والتقريبَ والخدماتِ وطرقَ الدفع — لأنه سوقُ الحساب نفسِه، لا طبقةٌ فوقه.

**ومالُ التجربة** (`TEST_FUNDS`): قيدُ تصحيحٍ موسومٌ **«رصيد تجريبي»** في محفظة كلِّ حساب تجربةٍ بعملة سوقه — **وإعادةُ الملء تكمّل إلى المبلغ ولا
تتجاوزه** (قيدٌ واحدٌ بالفرق، ولا شيءَ إن بلغه). **ولا يغادر المنصّة**: السحبُ والتحويلُ وكلُّ بابِ مالٍ حقيقيٍّ مغلقٌ على حساب التجربة
(`test_accounts.require_real_money`)، **ومالُه مستثنًى من كلِّ صفحةٍ ماليّة** (الاستثناءُ بالوسم في بانيها).

**ولا قفلَ هنا سوى قفل المحفظة** في `wallet.record` — في موضعه من الترتيب.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, NotFound, PermissionDenied
from app.models.enums import AuditAction, CountryCode, WalletTransactionType
from app.models.user import User
from app.services import audit, wallet

#: **علامةُ مال التجربة** بنصّ المالك — تتقدّم مرجعَ القيد
TEST_FUNDS_MARK = "رصيد تجريبي"

#: **المبلغُ لكلِّ حساب تجربةٍ في سوقه** — بنصّ المالك (§٧٤-أ/١٠): الأردن 100.000 د.أ · ليبيا 500.000 د.ل · الجزائر 20,000 د.ج
TEST_FUNDS: dict[CountryCode, Decimal] = {
    CountryCode.JO: Decimal("100.000"),
    CountryCode.LY: Decimal("500.000"),
    CountryCode.DZ: Decimal("20000"),
}


def _primary_id(user: User) -> uuid.UUID:
    return user.test_twin_of or user.id


async def family(session: AsyncSession, user: User) -> list[User]:
    """**الحسابُ وإخوتُه في الأسواق** — بدوره نفسِه (راكبٌ لراكب، وكبتنٌ لكبتن)."""
    if not user.is_test:
        return []
    primary = _primary_id(user)
    rows = await session.scalars(
        select(User).where(
            or_(User.id == primary, User.test_twin_of == primary),
            User.is_test.is_(True),
            User.role == user.role,
            User.deleted_at.is_(None),
        )
    )
    return sorted(rows.all(), key=lambda member: CountryCode(member.country_code).value)


async def switch(session: AsyncSession, *, user: User, country: CountryCode) -> User:
    """**الدخولُ إلى أخ الحساب في سوقٍ آخر** — لحساب التجربة وحدَه، وسطرٌ في التدقيق."""
    if not user.is_test:
        raise PermissionDenied("مُختارُ السوق لحسابات التجربة وحدَها")
    target = next((member for member in await family(session, user) if member.country_code == country), None)
    if target is None:
        raise NotFound("لا حسابَ تجربةٍ لهذا السوق")
    await audit.record(
        session,
        actor=user,
        action=AuditAction.READ,
        entity_type="test_market_switch",
        entity_id=target.id,
        details={"from": CountryCode(user.country_code).value, "to": country.value},
    )
    return target


async def refill(session: AsyncSession, *, user: User, actor: User | None) -> Decimal:
    """**يكمّل رصيدَ التجربة إلى مبلغ سوقه** — قيدُ تصحيحٍ موسومٌ «رصيد تجريبي» بالفرق؛ وصفرٌ إن بلغه. يعيد ما أُضيف."""
    if not user.is_test:
        raise InvalidInput("رصيدُ التجربة لحسابات التجربة وحدَها")
    target = TEST_FUNDS[CountryCode(user.country_code)]
    owner_type = wallet.owner_type_for(user)
    current = await wallet.balance(session, user.id, owner_type)
    missing = target - current
    if missing <= 0:
        return Decimal(0)
    await wallet.record(
        session,
        owner=user,
        owner_type=owner_type,
        tx_type=WalletTransactionType.ADJUSTMENT,
        amount=missing,
        reference=f"{TEST_FUNDS_MARK} — إلى {target}",
        created_by=actor.id if actor else None,
    )
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.CREATE,
        entity_type="test_funds",
        entity_id=user.id,
        details={"country_code": CountryCode(user.country_code).value, "type": WalletTransactionType.ADJUSTMENT.value},
    )
    return missing


async def all_test_accounts(session: AsyncSession) -> list[User]:
    rows = await session.scalars(select(User).where(User.is_test.is_(True), User.deleted_at.is_(None)).order_by(User.created_at))
    return list(rows.all())
