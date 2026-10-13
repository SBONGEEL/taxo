"""أدواتُ اختبار الحمل (SPEC §٧٥) — **الدورةُ كلُّها في قاعدة الاختبار قبل الإنتاج**: بياناتٌ قائمة ← بصمة ← حساباتُ حملٍ ورحلاتُها
(أجرةٌ مقرَّبةٌ وعمولةٌ نقديّةٌ وإلغاء) ← تنظيف ← **بصمةٌ مطابقةٌ حرفاً**.

**والتنظيفُ مقيسٌ في الاتجاهين**: يحذف كلَّ ما يرجع إلى حسابات الحمل (ومنه `money_roundings` الذي لا يُحذف منه إلا داخل معاملته)،
**ولا يمسّ صفّاً قائماً** — والبصمةُ تقول ذلك لكلِّ جدول.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text

from app.models.enums import CountryCode
from app.models.payment_setting import PaymentSetting
from app.models.user import User
from scripts import provision_test_accounts, stress_cleanup, stress_fingerprint, stress_provision
from tests.helpers import completed_ride, pay_ride, set_commission
from tests.test_payments import _only, _online_driver, _rider

pytestmark = pytest.mark.asyncio


async def _round_jordan(session_factory) -> None:
    async with session_factory() as session:
        row = await session.scalar(select(PaymentSetting).where(PaymentSetting.country_code == CountryCode.JO))
        row.rounding_enabled = True
        row.rounding_unit = Decimal("3.000")  # **الأجرةُ 8.000 ⇒ 9.000**: فرقٌ يكتب صفّاً في السجلّ
        row.rounding_mode = "nearest"
        row.rounding_enabled_at = datetime.now(UTC)
        await session.commit()


async def _fp(session_factory) -> dict:
    async with session_factory() as session:
        return await stress_fingerprint.fingerprint(session)


def _who(row: dict) -> dict:
    return {"headers": {"Authorization": f"Bearer {row['access']}"}, "user_id": row["user_id"],
            "driver_id": uuid.UUID(row["driver_id"]) if row["driver_id"] else None, "token": row["access"]}


async def test_the_whole_cycle_leaves_every_existing_row_as_it_was(
    client: AsyncClient, session_factory, jordan_settings: None, jordan_wallet: None, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await set_commission(session_factory, "10")
    await _round_jordan(session_factory)
    # **بياناتٌ قائمةٌ حقيقيّة** — رحلةٌ نقديّةٌ منتهيةٌ مؤكَّدة
    rider = await _rider(client)
    driver = await _online_driver(client, session_factory)
    ride = await completed_ride(client, rider["headers"], driver)
    paid = _only((await pay_ride(client, rider["headers"], ride["id"], "cash")).json())
    assert (await client.post(f"/payments/{paid['id']}/confirm", headers=driver["headers"])).status_code == 200
    await client.post("/drivers/me/offline", headers=driver["headers"])
    before = await _fp(session_factory)

    monkeypatch.setattr(provision_test_accounts, "_EPHEMERAL_ROOTS", ())
    tokens = tmp_path / "stress-tokens.json"
    result = await stress_provision.provision(captains=2, riders=2, tokens_file=tokens, write=True, session_factory=session_factory)
    assert result == {"captains": 2, "riders": 2, "tokens": 4}
    rows = json.loads(tokens.read_text(encoding="utf-8"))
    captains = [_who(r) for r in rows if r["role"] == "driver"]
    riders = [_who(r) for r in rows if r["role"] == "rider"]

    # **رحلةُ حملٍ كاملة** (أجرةٌ مقرَّبةٌ وعمولةٌ نقديّة) **وإلغاءٌ قبل القبول**
    from tests.helpers import bring_online

    await bring_online(client, captains[0])
    stress_ride = await completed_ride(client, riders[0]["headers"], captains[0])
    cash = _only((await pay_ride(client, riders[0]["headers"], stress_ride["id"], "cash", key="stress-pay-0001")).json())
    assert (await client.post(f"/payments/{cash['id']}/confirm", headers=captains[0]["headers"])).status_code == 200
    from tests.helpers import DROPOFF, PICKUP

    requested = await client.post("/rides", json={"pickup": PICKUP, "dropoff": DROPOFF, "vehicle_category": "economy",
                                                  "payment_method": "cash"}, headers=riders[1]["headers"])
    assert requested.status_code == 201, requested.text
    cancelled = await client.post(f"/rides/{requested.json()['id']}/cancel", json={}, headers=riders[1]["headers"])
    assert cancelled.status_code == 200, cancelled.text
    async with session_factory() as session:
        assert await session.scalar(text("SELECT count(*) FROM money_roundings")) >= 2
        assert await session.scalar(text("SELECT count(*) FROM driver_debts")) >= 2

    preview = await stress_cleanup.run(write=False, session_factory=session_factory)
    assert preview["plan"]["users"] == 4 and preview["plan"].get("money_roundings")
    assert (await _fp(session_factory)) != before  # **المعاينةُ لا تحذف**
    await stress_cleanup.run(write=True, session_factory=session_factory)

    after = await _fp(session_factory)
    changed = sorted(t for t in before if before[t] != after.get(t))
    assert changed == [], f"تغيّر ما لم يكن للاختبار: {changed}"
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User).where(User.phone.like("+962719%"))) == 0
        # **والمشغّلُ عاد حارساً**: حذفُ صفٍّ من السجلّ يُرفض بعد التنظيف كما كان قبله
        with pytest.raises(Exception, match="append-only"):
            await session.execute(text("DELETE FROM money_roundings WHERE id IN (SELECT id FROM money_roundings LIMIT 1)"))
