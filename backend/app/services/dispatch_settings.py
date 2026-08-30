"""قواعدُ التوزيع — **صارت إعداداً بعد أن كانت ثابتاً** (قرارُ المالك 2026-08-30).

## وهذا انحرافٌ عن مواصفةٍ عُدِّلت معه لا بعده

كان في `dispatch.py` تعليقٌ صريح: «**ثوابت SPEC القسم 5.3 — لا إعدادات: هذه
قواعد التوزيع نفسها**». فنقلُها إلى اللوحة **يخالف §5.3 نصّاً**، وقد عُدِّل
النصُّ في الجلسة نفسِها قبل الإيداع — **ووثيقةٌ تخالف الشيفرة أسوأُ من وثيقةٍ
ناقصة** (نصُّ قراره).

## والقيمُ تُقرأ **مرّةً عند بدء توزيع الرحلة** لا في كلِّ دورة

**والسؤالُ الذي سأله المالك**: ما مصيرُ عرضٍ قائمٍ حين يُبدَّل النمطُ حيّاً؟
**الجواب: لا شيء** — الرحلةُ الجاريةُ تُكمل بما بدأت به، والتبديلُ يسري على
**الرحلة التالية**.

**ولمَ لا يسري فوراً**: رحلةٌ بدأت بثّاً فصارت تسلسليّةً في منتصفها تترك أربعةَ
كباتنَ يحملون بطاقةً لا يقرأ أحدٌ قبولَها، **ورحلةٌ بدأت تسلسليّةً فصارت بثّاً
تعرض على من هو في تبريده**. **والحالُ نصفُ المتغيّر أسوأُ من أيِّ الحالين**، وهي
«متغيّرٌ واحدٌ في كلِّ مرّة» بعينها.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dispatch_setting import DispatchSetting
from app.models.enums import CountryCode, DispatchMode


@dataclass(frozen=True)
class DispatchRules:
    """ما يحكم دورةَ توزيعٍ واحدة — **يُقرأ مرّةً ويُمرَّر**."""

    mode: DispatchMode
    offer_timeout_seconds: int
    max_attempts: int
    total_timeout_seconds: int
    cooldown_seconds: int
    broadcast_batch_size: int


#: **الافتراضيُّ يُقرأ من هنا لا من القاعدة**: سوقٌ بلا صفٍّ يوزّع كسوقٍ بصفّ.
#: والأرقامُ هي التي أمر بها المالك 2026-08-30 — ٧ للمهلة و٣٠ للتبريد.
DEFAULTS = DispatchRules(
    mode=DispatchMode.SEQUENTIAL,
    offer_timeout_seconds=7,
    max_attempts=5,
    total_timeout_seconds=120,
    cooldown_seconds=30,
    broadcast_batch_size=4,
)


async def rules_for(session: AsyncSession, country: CountryCode) -> DispatchRules:
    row = await session.scalar(
        select(DispatchSetting).where(DispatchSetting.country_code == country)
    )
    if row is None:
        return DEFAULTS
    return DispatchRules(
        mode=row.mode,
        offer_timeout_seconds=row.offer_timeout_seconds,
        max_attempts=row.max_attempts,
        total_timeout_seconds=row.total_timeout_seconds,
        cooldown_seconds=row.cooldown_seconds,
        broadcast_batch_size=row.broadcast_batch_size,
    )
