"""أرقامُ شاشة الأعطال — **تُجمَّع في الخلفية، لا في الصفحة** (٢٠٢٦-٠٩-٢١).

**وهي قاعدةُ `services/stats.py` نفسُها**: لوحةٌ تجمع صفوفَها بنفسها تعرض رقماً
يخالف القاعدةَ أوّلَ ما تُقصَّ صفحة. **و«٣١٢ جهازاً» تعني الجميعَ لا الخمسين
المعروضين**، وهذا هو الفرقُ كلُّه.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Integer, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ErrorKind, ErrorStatus
from app.models.error_report import ErrorEvent, ErrorGroup

#: أطولُ نافذةٍ يقبلها المنحنى — **وسقفٌ لأنه مسحٌ على الأحداث**
MAX_TREND_HOURS = 24 * 30
#: أكثرُ ما يُسأل عنه في نداءٍ واحد — بقدر صفحةِ الجدول
MAX_TREND_GROUPS = 200


async def summary(session: AsyncSession) -> dict[str, object]:
    """أربعةُ أرقامٍ تُقرأ بنظرة — **وكلُّها من القاعدة**."""
    now = datetime.now(UTC)
    day = now - timedelta(hours=24)
    prev = now - timedelta(hours=48)

    open_count = await session.scalar(
        select(func.count())
        .select_from(ErrorGroup)
        .where(ErrorGroup.status == ErrorStatus.OPEN)
    )
    new_24h = await session.scalar(
        select(func.count())
        .select_from(ErrorGroup)
        .where(ErrorGroup.first_seen_at >= day)
    )
    regressed_24h = await session.scalar(
        select(func.count())
        .select_from(ErrorGroup)
        .where(ErrorGroup.regressed_at >= day)
    )
    # **أجهزةٌ متميّزةٌ لا أحداث**: «٤٠٠ حدثٍ من جهازين» ليست إصابةَ أسطول
    devices_24h = await session.scalar(
        select(func.count(distinct(ErrorEvent.device_hash))).where(
            ErrorEvent.received_at >= day
        )
    )
    devices_prev = await session.scalar(
        select(func.count(distinct(ErrorEvent.device_hash))).where(
            ErrorEvent.received_at >= prev, ErrorEvent.received_at < day
        )
    )
    reported_open = await session.scalar(
        select(func.count())
        .select_from(ErrorGroup)
        .where(
            ErrorGroup.status == ErrorStatus.OPEN,
            ErrorGroup.kind == ErrorKind.USER_REPORT,
        )
    )
    oldest_reported = await session.scalar(
        select(func.min(ErrorGroup.last_seen_at)).where(
            ErrorGroup.status == ErrorStatus.OPEN,
            ErrorGroup.kind == ErrorKind.USER_REPORT,
        )
    )

    return {
        "open": open_count or 0,
        "new_24h": new_24h or 0,
        "regressed_24h": regressed_24h or 0,
        "devices_24h": devices_24h or 0,
        "devices_prev_24h": devices_prev or 0,
        "reported_open": reported_open or 0,
        "oldest_reported_at": oldest_reported,
    }


async def trend(
    session: AsyncSession, group_ids: list[uuid.UUID], hours: int
) -> dict[uuid.UUID, list[int]]:
    """مرّاتُ كلِّ مجموعةٍ لكلِّ ساعة — **بترتيب الزمن، وبلا ثقوب**.

    **والساعاتُ الخاليةُ أصفارٌ لا فجوات**: رسمٌ يقفز فوق ساعةٍ صامتةٍ يكذب على
    من يقرؤه — يُريه تتابعاً حيث كان سكون.

    **و`sum(repeat)` لا `count(*)`**: الحدثُ الواحدُ يحمل تكرارَه في الجلسة،
    وعدُّ الصفوف يُنقص ما جُمِع في العميل.
    """
    if not group_ids:
        return {}

    now = datetime.now(UTC)
    # **الجَرفُ إلى رأس الساعة**: وإلا كان آخرُ دلوٍ جزئيّاً فيُقرأ هبوطاً
    top = now.replace(minute=0, second=0, microsecond=0)
    since = top - timedelta(hours=hours - 1)

    bucket = func.date_trunc("hour", ErrorEvent.received_at)
    rows = await session.execute(
        select(
            ErrorEvent.group_id,
            bucket.label("hour"),
            func.sum(ErrorEvent.repeat).cast(Integer).label("hits"),
        )
        .where(
            ErrorEvent.group_id.in_(group_ids[:MAX_TREND_GROUPS]),
            ErrorEvent.received_at >= since,
        )
        .group_by(ErrorEvent.group_id, bucket)
    )

    series: dict[uuid.UUID, list[int]] = {
        gid: [0] * hours for gid in group_ids[:MAX_TREND_GROUPS]
    }
    for group_id, hour, hits in rows:
        index = int((hour - since).total_seconds() // 3600)
        if 0 <= index < hours and group_id in series:
            series[group_id][index] = int(hits or 0)
    return series
