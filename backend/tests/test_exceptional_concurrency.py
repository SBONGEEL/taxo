"""**تزامنُ الاعتماد الاستثنائيّ والتجميد** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١) — `services/exceptional_approval`.

**ما يملكه القفل**: `freeze` و`unfreeze` يقفلان صفَّ الكبتن (`drivers.lock`) **قبل** أن يقرآ حالَه. وبلا القفل يقرأ تجميدان متزامنان
«معتمد» معاً فينجحان معاً: سطرا تدقيقٍ لقرارٍ واحد، ورسالتا «جُمِّد حسابك» — **والأسوأ تجميدٌ وإلغاؤه متزامنين**: إلغاءٌ قرأ «مجمَّد»
قبل أن يُكتب يعيد كبتناً جمّده مشرفٌ للتوّ. **فالثابتُ**: من تجميدين متزامنين ينجح واحدٌ ويُردّ الآخرُ بـ«مجمَّدٌ أصلاً»، وسطرُ
تدقيقٍ واحد. والمهلةُ تُغلَّف بـ`wait_for` لأن الجمود يعلق ولا يرفع.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.audit import AdminAuditLog
from app.models.driver import Driver
from app.models.enums import DriverStatus
from tests.test_exceptional_approval import _approve, _manager, _pending_driver

pytestmark = pytest.mark.asyncio


async def test_a_second_freeze_waits_for_the_first_and_then_sees_it(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """**ترتيبٌ مقصودٌ لا صدفة**: الأوّلُ يجمّد ويُبقي معاملتَه مفتوحة، والثاني يبدأ. **بالقفل** ينتظر ثم يقرأ «مجمَّد» فيُردّ؛
    **وبحذفه** يقرأ «معتمد» من صفٍّ لم يُلتزم بعد فينجح هو أيضاً — وهذا ما يسقط هنا."""
    from app.core.exceptions import InvalidInput
    from app.models.user import User
    from app.services import exceptional_approval

    manager = await _manager(client, admin_headers)
    driver = await _pending_driver(client, session_factory)
    assert (await _approve(client, manager, driver["driver_id"])).status_code == 200

    async with session_factory() as first, session_factory() as second:
        row_a = await first.get(Driver, driver["driver_id"])
        actor_a = await first.get(User, uuid.UUID(manager["id"]))
        await exceptional_approval.freeze(first, driver=row_a, actor=actor_a, reason="شكوى أولى قيد التحقيق")

        row_b = await second.get(Driver, driver["driver_id"])
        actor_b = await second.get(User, uuid.UUID(manager["id"]))
        assert row_b.status is DriverStatus.APPROVED, "الثاني يبدأ وهو يرى «معتمد» — لم يُلتزم الأوّلُ بعد"
        late = asyncio.create_task(
            exceptional_approval.freeze(second, driver=row_b, actor=actor_b, reason="شكوى ثانية قيد التحقيق")
        )
        await asyncio.sleep(0.5)
        assert not late.done(), "الثاني لم ينتظر قفلَ الأوّل — قرأ حالاً لم تُلتزم بعد"
        await first.commit()
        with pytest.raises(InvalidInput):
            await asyncio.wait_for(late, timeout=10)
        await second.rollback()

    async with session_factory() as session:
        audits = await session.scalar(
            select(func.count()).select_from(AdminAuditLog).where(
                AdminAuditLog.entity_type == "driver_freeze", AdminAuditLog.entity_id == driver["driver_id"]
            )
        )
    assert audits == 1, "قرارٌ واحدٌ بسطرٍ واحد"
