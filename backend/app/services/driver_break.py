"""**الاستراحةُ المؤقّتة** (أمرُ المالك ٢٠٢٦-١١-٢٠ الرابع، البند ٤٤، SPEC §١١٠) — «توقّف 15 / 30 دقيقة» من الفقاعة.

* **متّصلٌ ولا عروض**: `drivers.break_until`، **والتوزيعُ يقارنه بالساعة** (`available_clause`) — فيعود وحدَه لحظةَ انتهائها **بلا مهمّةٍ
  دوريّةٍ تُطفئها**، ولا شيءَ يُنسى. الحضورُ والموقعُ كما هما، فلا يسقط من الخريطة ولا يُعاد الاتّصال.
* **لا تبدأ إلا متّصلاً بلا رحلة** — استراحةٌ فوق رحلةٍ جاريةٍ لا معنى لها، وعرضٌ مقبولٌ قبلها يكمل كما هو.
* **يمحوها الاتّصالُ والخروجُ** (`drivers.go_online/go_offline`) والإنهاءُ المبكر — فاستراحةُ الأمس لا تحجب اليوم.
* **وصفُّ الكبتن يُقفل قبل الفحص** كلِّ تغيير حال (`CLAUDE.md`): خروجٌ واستراحةٌ معاً لا يكتب أحدُهما فوق الآخر بقراءةٍ قديمة.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.core.exceptions import BreakNotAllowed, InvalidInput
from app.models.driver import Driver

#: **نصُّ الأمر**: «توقّف 15 / 30 دقيقة» — مدّتان لا حقلٌ حرّ
MINUTES = (15, 30)


def available_clause():
    """**ليس في استراحة الآن** — شرطٌ في التوزيع (`dispatch._eligible_levels`). بساعة القاعدة لا ساعة العامل."""
    return or_(Driver.break_until.is_(None), Driver.break_until <= func.now())


def on_break(driver: Driver, now: datetime) -> bool:
    return driver.break_until is not None and driver.break_until > now


async def _locked(session: AsyncSession, driver: Driver) -> Driver:
    await session.refresh(driver, with_for_update=True)
    return driver


async def start(session: AsyncSession, driver: Driver, *, minutes: int, now: datetime) -> datetime:
    if minutes not in MINUTES:
        raise InvalidInput("الاستراحةُ 15 أو 30 دقيقة", field="minutes")
    driver = await _locked(session, driver)
    if not driver.is_online or driver.current_ride_id is not None:
        raise BreakNotAllowed()
    driver.break_until = now + timedelta(minutes=minutes)
    return driver.break_until


async def end(session: AsyncSession, driver: Driver) -> None:
    driver = await _locked(session, driver)
    driver.break_until = None
