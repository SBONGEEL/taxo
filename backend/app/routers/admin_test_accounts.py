"""حساباتُ التجربة في اللوحة (SPEC §٧٤-أ/١٠) — **قائمتُها بأسواقها وأرصدتها، وزرُّ «إعادة ملء رصيد التجربة» للمالك وحدَه**.

**القراءةُ لطاقم اللوحة؛ وإعادةُ الملء `markets.manage`** (بنصّ المالك «للمالك وحده، مدقَّق») — قيدُ تصحيحٍ موسومٌ «رصيد تجريبي» يكمّل إلى مبلغ
السوق ولا يتجاوزه. **ولا يُنشئ هذا البابُ حساباً ولا يَسِم أحداً**: الوسمُ والتوأمةُ للسكربت وحدَه.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.currency import currency_for_country
from app.core.deps import DbSession, MarketsManager, StaffUser
from app.core.exceptions import NotFound
from app.models.enums import CountryCode, Currency, UserRole
from app.models.user import User
from app.services import markets, test_markets, wallet

router = APIRouter(prefix="/admin/test-accounts", tags=["admin"])


class TestAccountRow(BaseModel):
    id: uuid.UUID
    name: str | None
    phone: str | None
    role: UserRole
    country_code: CountryCode
    currency: Currency
    #: **رصيدُ التجربة الآن** بعملة سوقه
    balance: Decimal
    #: **مبلغُ السوق** الذي تكمّل إليه إعادةُ الملء
    target_amount: Decimal
    #: **دون مبلغ سوقه** — فيُرسم زرُّ إعادة الملء؛ والمقارنةُ هنا لا في الواجهة
    refillable: bool
    twin_of: uuid.UUID | None
    outside_allowed: bool


class TestAccountsOut(BaseModel):
    accounts: list[TestAccountRow]


async def _out(session) -> TestAccountsOut:
    rows = []
    for user in await test_markets.all_test_accounts(session):
        owner_type = wallet.owner_type_for(user)
        balance = await wallet.balance(session, user.id, owner_type)
        target = test_markets.TEST_FUNDS[CountryCode(user.country_code)]
        rows.append(
            TestAccountRow(
                id=user.id,
                name=user.name,
                phone=user.phone,
                role=user.role,
                country_code=user.country_code,
                currency=currency_for_country(user.country_code),
                balance=balance,
                target_amount=target,
                refillable=balance < target,
                twin_of=user.test_twin_of,
                outside_allowed=await markets.active_allowance(session, user.id) is not None,
            )
        )
    return TestAccountsOut(accounts=rows)


@router.get("", response_model=TestAccountsOut)
async def list_test_accounts(session: DbSession, _: StaffUser) -> TestAccountsOut:
    return await _out(session)


@router.post("/{user_id}/refill", response_model=TestAccountsOut)
async def refill_test_funds(user_id: uuid.UUID, session: DbSession, admin: MarketsManager) -> TestAccountsOut:
    """**يكمّل رصيدَ التجربة إلى مبلغ سوقه** — للمالك وحدَه، وسطرٌ في التدقيق."""
    user = await session.get(User, user_id)
    if user is None or not user.is_test:
        raise NotFound("لا حسابَ تجربةٍ بهذا المعرّف")
    await test_markets.refill(session, user=user, actor=admin)
    await session.commit()
    return await _out(session)
