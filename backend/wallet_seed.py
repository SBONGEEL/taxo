# -*- coding: utf-8 -*-
"""يملأ محفظةَ الراكبة على التطوير بالمسار الحقيقيّ — طبقةُ الخدمة نفسُها.

شحنُ نقطةٍ معتمدة ثم تحويلٌ إلى صديق: قيودٌ في الدفتر بأقفاله، لا SQL.
"""
import asyncio
import sys
import uuid
from decimal import Decimal

import sqlalchemy as sa

sys.path.insert(0, "/app")
from app.core.db import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.models.enums import TopupMethod  # noqa: E402
from app.services import topups, wallet  # noqa: E402

RIDER = "+962799000001"
FRIEND = "+962799000002"
ADMIN = "+962790000000"


async def one(session, phone):
    row = await session.execute(sa.select(User).where(User.phone == phone))
    u = row.scalar_one_or_none()
    if u is None:
        raise SystemExit(f"لا مستخدمَ بالرقم {phone}")
    return u


async def main() -> None:
    async with SessionLocal() as session:
        rider = await one(session, RIDER)
        friend = await one(session, FRIEND)
        admin = await one(session, ADMIN)
        before = await wallet.balance_of(session, rider)
        print("  الرصيد قبل :", before)
        await topups.create_confirmed(
            session,
            owner=rider,
            actor=admin,
            method=TopupMethod.CASH,
            amount=Decimal("25.000"),
            reference="نقطة الشميساني 4417",
        )
        await session.commit()
        await wallet.transfer(
            session,
            sender=rider,
            recipient=friend,
            amount=Decimal("3.500"),
            idempotency_key=str(uuid.uuid4()),
        )
        await session.commit()
        after = await wallet.balance_of(session, rider)
        print("  الرصيد بعد :", after)


asyncio.run(main())
