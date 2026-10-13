"""مفاتيحُ الدفع في الجزائر (SPEC §٧٤-ط/٤) — **تُشعَل للجزائر وحدَها، والبطاقةُ للرحلة لا تُمسّ، وإعادتُها لا تكرّر**."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode, FeatureKey, PaymentProviderKind
from app.models.payment_request import PayMethod
from app.services import settings_service
from scripts import algeria_switches_74 as script

pytestmark = pytest.mark.asyncio


async def test_algeria_gets_wallet_and_payments_and_nothing_else_moves(session_factory) -> None:
    preview = await script.main_async(write=False, session_factory=session_factory)
    async with session_factory() as session:
        assert not await settings_service.is_feature_enabled(session, CountryCode.DZ, FeatureKey.WALLET_ENABLED)
    assert any("يُشعَل" in line for line in preview)

    await script.main_async(write=True, session_factory=session_factory)
    await script.main_async(write=True, session_factory=session_factory)
    async with session_factory() as session:
        for key in script.SWITCHED_ON:
            assert await settings_service.is_feature_enabled(session, CountryCode.DZ, key)
            assert not await settings_service.is_feature_enabled(session, CountryCode.LY, key)
        assert not await settings_service.is_feature_enabled(session, CountryCode.DZ, FeatureKey.CARD_ENABLED)
        cards = (await session.scalars(select(PayMethod).where(PayMethod.kind == PaymentProviderKind.PURCHASE_CODE))).all()
        assert [(c.country_code, c.enabled, c.for_topup, c.for_subscription) for c in cards] == [
            (CountryCode.DZ, True, True, False)
        ]
        flagged = await session.scalar(
            select(func.count()).select_from(AdminAuditLog).where(AdminAuditLog.entity_type == "feature_flag")
        )
        assert flagged == 2  # **مفتاحان أُشعلا مرّةً** — والإعادةُ لا تكتب سطراً
