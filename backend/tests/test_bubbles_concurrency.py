"""**الفقاعتان — التزامن** (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠؛ وقاعدةُ `CLAUDE.md`: كلُّ قفلٍ يسمّيه اختبارُ تزامن).

* **`driver_break`** يقفل صفَّ الكبتن قبل فحص «متّصلٌ بلا رحلة» ثمّ يكتب `break_until`: استراحتان معاً (١٥ و٣٠) تنجحان كلتاهما
  مرتّبتين، **والقيمةُ في القاعدة إحدى القيمتين اللتين رُدّتا** — لا ثالثةَ ولا قراءةٌ قديمةٌ تكتب فوق أحدث.
* **`quick_replies`** يضمن الصفَّ (`ON CONFLICT DO NOTHING`) ثمّ يقفله: حفظان أوّلان معاً لدولةٍ بلا صفّ **كلاهما ٢٠٠ وصفٌّ واحد** —
  ومن دون الإدراج الآمن كان أحدُهما يسقط بتصادم المفتاح (٥٠٠).
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.driver import Driver
from app.models.support import QuickReplySetting
from tests.helpers import approved_driver, bring_online, enable_features

pytestmark = pytest.mark.asyncio


async def test_two_breaks_at_once_leave_one_of_their_answers(client: AsyncClient, session_factory) -> None:
    await enable_features(session_factory, "driver_break")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    answers = await asyncio.wait_for(
        asyncio.gather(
            client.post("/drivers/me/break", json={"minutes": 15}, headers=driver["headers"]),
            client.post("/drivers/me/break", json={"minutes": 30}, headers=driver["headers"]),
        ),
        timeout=20,
    )
    assert Counter(a.status_code for a in answers) == Counter({200: 2}), [a.text for a in answers]
    returned = {datetime.fromisoformat(a.json()["break_until"]) for a in answers}
    async with session_factory() as session:
        stored = await session.scalar(select(Driver.break_until).where(Driver.id == uuid.UUID(str(driver["driver_id"]))))
    assert stored in returned


async def test_two_first_saves_of_quick_replies_at_once(
    client: AsyncClient, session_factory, admin_headers: dict[str, str]
) -> None:
    answers = await asyncio.wait_for(
        asyncio.gather(
            client.put("/admin/quick-replies/LY", json={"driver_texts": ["أنا قريب"], "rider_texts": []}, headers=admin_headers),
            client.put("/admin/quick-replies/LY", json={"driver_texts": ["انتظرني"], "rider_texts": []}, headers=admin_headers),
        ),
        timeout=20,
    )
    assert Counter(a.status_code for a in answers) == Counter({200: 2}), [a.text for a in answers]
    async with session_factory() as session:
        rows = await session.scalar(select(func.count()).select_from(QuickReplySetting))
        texts = await session.scalar(select(QuickReplySetting.driver_texts))
    assert rows == 1
    assert texts in (["أنا قريب"], ["انتظرني"])
