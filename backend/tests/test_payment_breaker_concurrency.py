"""**قفلُ `payment_breaker`** (SPEC §٨٧/١) — إخفاقان يبلغان الحدَّ معاً إخفاءٌ واحد: سطرُ تدقيقٍ واحدٌ وإشعارٌ واحدٌ للمالك.

**ما يملكه القفلُ وحدَه**: كلا الإخفاقين يعدّ سلسلةً بلغت الحدّ (كلٌّ يرى رفضَه ورفضَين قبله)، **وبلا قفلٍ يقرأ كلاهما «مفعَّلة» ويكتب
إخفاءً** — سطرَي تدقيقٍ وإشعارَين. **ومع القفل** يجد الثاني صفَّ الطريقة مطفأً بعد التزام الأول فيعود بلا شيء.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from tests.helpers import rider_session
from tests.payment_fakes import add_gateway_method, install_transport
from tests.test_dz_payments_82 import _kinds, _queued
from tests.test_payment_protection_87 import _fail_once, _open
from tests.test_payment_requests import ALGERIAN_RIDER, algeria_market

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _every_tap_is_a_new_page(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import payment_requests

    monkeypatch.setattr(payment_requests, "DOUBLE_TAP_SECONDS", 0)


async def test_two_failures_reaching_the_limit_together_hide_once(
    client: AsyncClient, session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    await algeria_market(session_factory)
    chargily, _ = install_transport(monkeypatch)
    method_id = await add_gateway_method(session_factory, "chargily")
    rider = await rider_session(client, ALGERIAN_RIDER)
    await _fail_once(client, chargily, rider, method_id)
    await _fail_once(client, chargily, rider, method_id)
    third = await _open(client, rider["headers"], method_id)
    fourth = await _open(client, rider["headers"], method_id)
    chargily.status[third["reference"]] = "failed"
    chargily.status[fourth["reference"]] = "failed"
    await _queued()
    # **التداخلُ المقصود**: كلا الإخفاقين يعدّ سلسلتَه ثمّ ينتظر الآخرَ قبل أن يقرأ صفَّ الطريقة — فلا يلتزم أحدُهما قبل أن يقرأ الآخر
    from app.services import payment_breaker

    real = payment_breaker.failure_streak
    barrier = asyncio.Barrier(2)

    async def streak_then_meet(session, provider_id):
        found = await real(session, provider_id)
        try:
            await asyncio.wait_for(barrier.wait(), timeout=5)
        except TimeoutError:
            pass
        return found

    monkeypatch.setattr(payment_breaker, "failure_streak", streak_then_meet)

    results = await asyncio.wait_for(
        asyncio.gather(
            client.post(f"/payment-requests/{third['id']}/refresh", headers=rider["headers"]),
            client.post(f"/payment-requests/{fourth['id']}/refresh", headers=rider["headers"]),
        ),
        timeout=30,
    )
    assert [r.json()["status"] for r in results] == ["rejected", "rejected"]
    async with session_factory() as session:
        hides = await session.scalar(
            select(func.count()).select_from(AdminAuditLog).where(
                AdminAuditLog.entity_type == "payment_provider",
                AdminAuditLog.details["action"].astext == "auto_hide",
            )
        )
    assert hides == 1
    assert _kinds(await _queued()).count("payment_method_hidden") == 1
