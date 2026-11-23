"""يومُ اشتراكٍ لكبتن التجربة (إذنُ المالك ٢٠٢٦-١١-٢٣) — **بصفرٍ، يوماً واحداً، لحساب التجربة وحدَه، ومرّةً لا تتكرّر فوق غطاء**."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.models.audit import AdminAuditLog
from app.models.subscription import DriverSubscription
from app.models.user import User
from app.models.wallet import WalletTransaction
from scripts import test_captain_day as script
from tests.helpers import approved_driver, ensure_plan

pytestmark = pytest.mark.asyncio


async def _captain(client: AsyncClient, session_factory, *, is_test: bool) -> tuple[uuid.UUID, str]:
    await ensure_plan(session_factory, country="JO", name="TAXO X1 — يوميّ", price="3", duration="daily")
    driver = await approved_driver(client, session_factory, subscribed=False)
    user_id = uuid.UUID(str(driver["user_id"]))
    async with session_factory() as session:
        if is_test:
            await session.execute(update(User).where(User.id == user_id).values(is_test=True))
            await session.commit()
        phone = await session.scalar(select(User.phone).where(User.id == user_id))
    return driver["driver_id"], phone


def _accounts(tmp_path: Path, phone: str) -> Path:
    path = tmp_path / "test-accounts.env"
    path.write_text(f"TAXO_TEST_CAPTAIN_PHONE={phone}\n", encoding="utf-8")
    return path


async def test_one_free_day_for_the_test_captain_through_the_panel_door(client: AsyncClient, session_factory, tmp_path: Path) -> None:
    driver_id, phone = await _captain(client, session_factory, is_test=True)
    accounts = _accounts(tmp_path, phone)

    await script.main_async(test_accounts=accounts, write=False, session_factory=session_factory)
    async with session_factory() as session:
        assert (await session.scalars(select(DriverSubscription).where(DriverSubscription.driver_id == driver_id))).all() == []

    await script.main_async(test_accounts=accounts, write=True, session_factory=session_factory)
    async with session_factory() as session:
        rows = (await session.scalars(select(DriverSubscription).where(DriverSubscription.driver_id == driver_id))).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.amount_paid == Decimal("0.000") and row.reference == script.REFERENCE
        assert timedelta(hours=23) < row.expires_at - row.starts_at <= timedelta(days=1)
        # **ولا قيدَ في الدفتر** — لا مالَ دخل ولا خرج
        assert (await session.scalars(select(WalletTransaction))).all() == []
        assert await session.scalar(select(AdminAuditLog).where(AdminAuditLog.entity_id == row.id)) is not None

    # **ولا يومَ ثانياً فوق غطاءٍ قائم**
    with pytest.raises(script.DayRefused):
        await script.main_async(test_accounts=accounts, write=True, session_factory=session_factory)


async def test_a_real_account_is_never_granted(client: AsyncClient, session_factory, tmp_path: Path) -> None:
    driver_id, phone = await _captain(client, session_factory, is_test=False)
    with pytest.raises(script.DayRefused):
        await script.main_async(test_accounts=_accounts(tmp_path, phone), write=True, session_factory=session_factory)
    async with session_factory() as session:
        assert (await session.scalars(select(DriverSubscription).where(DriverSubscription.driver_id == driver_id))).all() == []
