"""كنسُ طلبات المزودين المعلّقة (المرحلة 12، الصيانة).

**ما يخلّفه هذا الجدولُ بلا كنس ليس نفاياتٍ بل راكباً محبوساً.** طلبٌ يبقى
`created` لأن الراكب أغلق صفحة الدفع يترك خلفه **دفعةً `pending`**، و`pending`
داخلةٌ في `OWING_PAYMENT_STATUSES` — وهي مجموعُ «لا تُدفع الرحلةُ مرتين». فتُقرأ
الرحلةُ مدفوعةً بدفعةٍ لن تُؤكَّد أبداً، ولا يستطيع صاحبُها الدفعَ بقناةٍ أخرى.
هذا هو نصُّ `card_payments._mark_failed` نفسِه، وهذه المهمةُ هي ما يُشغّله حين
لا يعود أحدٌ إلى الصفحة ليُشغّله.

**والقاعدةُ الحاكمة: لا تُكتب حالةٌ نهائيةٌ لم يقلها المزود.** `apply_state` في
القناتين يرفض ما ليس `created`، فمعناه أن كتابةَ `cancelled` محلياً على طلبٍ قد
يُسوّيه المزودُ لاحقاً **تجعل إشعارَه المتأخّرَ يُهمَل بصمت** — بطاقةٌ خُصمت
ومحفظةٌ لم تُشحن. فالكنسُ هنا يسأل ولا يخمّن:

1. **ما له مرجعُ مزودٍ** → `reconcile`: نداءٌ إلى المزود ثم تطبيقُ جوابه، عبر
   بابِ قناته وحده. ومن قال المزودُ إنه ما زال معلّقاً **يُترك معلّقاً** ويُسأل
   في الدورة التالية.
2. **ما لا مرجعَ له** → لم يصل المزودَ أصلاً (نداءُ الفتح نفسُه فشل)، فلا مالَ
   يمكن أن يكون تحرّك، ويُسقَط من بابِ قناته لتُحرَّر دفعتُه معه. **والخطرُ
   المتبقّي مكتوبٌ لا مُنكَر**: نداءُ فتحٍ انقطع **بعد** أن أنشأ المزودُ طلبَه
   يترك مرجعاً عندنا فارغاً وطلباً عنده حيّاً — فإشعارُه المتأخّر يجد طلبَنا
   ساقطاً فيُهمَل. ولذلك مهلةُ الإسقاط **نصفُ ساعة** لا دقائق: إشعارُ فتحٍ
   منقطعٍ يصل في ثوانٍ، ومن يصل بعد نصف ساعةٍ حالةٌ يفصلها المشرف بالمزود
   وبقيدِ `adjustment`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentProvider
from app.models.provider_order import OPEN_ORDER_STATUSES, ProviderOrder
from app.services import card_payments, cliq_topups

logger = logging.getLogger(__name__)

# **أصغرُ من هذا يعني «العميلُ ما زال على الصفحة»**: صفحةُ الدفع المستضافة
# تُملأ في دقائق، وسؤالُ المزود عن طلبٍ عمرُه دقيقتان يستهلك نداءً ويُجيب
# «معلّق». والعشرون دقيقةً أطولُ من أي جلسةِ دفعٍ معقولة وأقصرُ من أن تحبس أحداً.
RECHECK_AFTER_MINUTES = 20

# مهلةُ إسقاطِ ما لا مرجعَ له — انظر الخطرَ المتبقّي في مقدمة الملف.
UNOPENED_AFTER_MINUTES = 30

# سقفُ الطلبات في الدورة الواحدة. كلُّ واحدٍ منها **نداءٌ عبر الشبكة**، فدورةٌ
# بلا سقفٍ على جدولٍ متراكم تصير مئاتَ النداءات في دقيقة — وهي تبدو للمزود
# هجوماً لا صيانة. والأقدمُ أولاً كي لا يتأخّر أحدٌ خلف زحمةٍ جديدة.
SWEEP_LIMIT = 40


def _now() -> datetime:
    return datetime.now(UTC)


async def stale_orders(
    session: AsyncSession, *, limit: int = SWEEP_LIMIT
) -> list[ProviderOrder]:
    """الطلباتُ المفتوحةُ التي مضى عليها ما يكفي — الأقدمُ أولاً."""
    cutoff = _now() - timedelta(minutes=RECHECK_AFTER_MINUTES)
    rows = await session.scalars(
        select(ProviderOrder)
        .where(
            ProviderOrder.status.in_(OPEN_ORDER_STATUSES),
            ProviderOrder.created_at < cutoff,
        )
        .order_by(ProviderOrder.created_at)
        .limit(limit)
    )
    return list(rows)


async def _resolve(session: AsyncSession, order: ProviderOrder) -> str:
    """يسوّي طلباً واحداً ويعيد ما جرى له: `settled` أو `dropped` أو `open`."""
    unopened_cutoff = _now() - timedelta(minutes=UNOPENED_AFTER_MINUTES)

    if order.provider_order_ref is None:
        if order.created_at >= unopened_cutoff:
            return "open"
        # بابُ القناة لا كتابةٌ هنا: قناةُ البطاقة تُحرّر دفعتَها معه، وقناةُ
        # الشحن لا دفعةَ لها — والفرقُ يعرفه كلٌّ منهما لا هذا الملف
        if order.provider is PaymentProvider.TELR:
            await card_payments.drop_unopened(session, order)
        else:
            await cliq_topups.drop_unopened(session, order)
        return "dropped"

    if order.provider is PaymentProvider.TELR:
        settled = await card_payments.reconcile(session, order)
    else:
        settled = await cliq_topups.reconcile(session, order)
    return "open" if settled.status in OPEN_ORDER_STATUSES else "settled"


async def sweep(session: AsyncSession, *, limit: int = SWEEP_LIMIT) -> dict[str, int]:
    """يمرّ على المعلّق ويسوّي ما يُسوّى. **الـcommit لكلِّ طلبٍ على حِدة.**

    ولو جُمعت الدورةُ في معاملةٍ واحدة لأسقط طلبٌ واحدٌ فاشلٌ ما سُوّي قبله،
    ولحمل قفلَ صفوفِها كلَّها طولَ نداءاتٍ متتابعةٍ عبر الشبكة — نفسُ ما تفعله
    `tasks/stops.py` بكل محطةٍ في معاملتها.
    """
    tally = {"settled": 0, "dropped": 0, "open": 0, "failed": 0}
    for order in await stale_orders(session, limit=limit):
        try:
            tally[await _resolve(session, order)] += 1
            await session.commit()
        except Exception:  # noqa: BLE001 - انقطاعُ مزودٍ لا يُسقط الدورة
            await session.rollback()
            tally["failed"] += 1
            logger.warning(
                "تعذّر كنسُ الطلب %s (%s)", order.cart_id, order.provider.value,
                exc_info=True,
            )
    return tally
