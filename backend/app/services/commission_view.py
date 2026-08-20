"""ما يراه الكبتنُ عن عمولة TAXO — **الرقمُ المجمَّد، والمجموعُ الشهريّ**.

**والوعدُ الذي يحرسه هذا الملف مكتوبٌ في §25.11**: «صفر عمولة **ما دام اشتراكك
سارياً**» — لا «صفر عمولة» مطلقة. فالكبتنُ يستحق أن يرى، على كلِّ رحلة، **بأيِّ
نسبةٍ حُوسب** لا مبلغاً بلا سبب.

**والنسبةُ تُقرأ من الرحلة لا من الإعدادات.** `rides.commission_percent_at_ride`
مجمَّدةٌ لحظةَ القبول (§25.11)، وقراءةُ الإعدادات اليومَ عن رحلةٍ وقعت الشهرَ
الماضي تعرض رقماً لم يُحاسَب به أحد — وهو نفسُ سببِ تجميدها أصلاً.

**واستعلامٌ ثانٍ على الصفحة لا ضمٌّ إلى الأول** (قاعدةُ `services/ride_log.py`):
الضمُّ يضاعف الصفَّ حين تحمل الرحلةُ أكثرَ من قيد، فتسقط قيودٌ من صفحةٍ مسقوفة.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode, WalletOwnerType, WalletTransactionType
from app.models.ride import Ride
from app.models.wallet import WalletTransaction
from app.schemas.wallet import WalletTransactionOut
from app.services import pricing
from app.services.stats import _zone


async def percent_by_ride(
    session: AsyncSession, entries: list[WalletTransaction]
) -> dict[uuid.UUID, Decimal]:
    """النسبةُ المجمَّدة لكلِّ رحلةٍ في هذه الصفحة — لقيود العمولة وحدَها.

    **ولا يُستعلَم حين لا عمولةَ في الصفحة**: صفحةُ شحنٍ وسحبٍ لا تحتاج
    استعلاماً ثانياً، والشرطُ هنا لا في المُنادي كي لا يُنسى في بابٍ ثانٍ.
    """
    ride_ids = {
        entry.ride_id
        for entry in entries
        if entry.ride_id is not None
        and entry.type == WalletTransactionType.COMMISSION
    }
    if not ride_ids:
        return {}

    rows = await session.execute(
        select(Ride.id, Ride.commission_percent_at_ride).where(Ride.id.in_(ride_ids))
    )
    return {
        ride_id: percent
        for ride_id, percent in rows.all()
        if percent is not None
    }


def _month_start(zone, now: datetime) -> datetime:
    """أولُ الشهر **بمِنطقة الدولة**، مُعاداً بـUTC للاستعلام.

    **والشهرُ تقويميٌّ لا ثلاثون يوماً متدحرجة** — وهذا انحرافٌ مقصودٌ عن
    `stats.PERIOD_DAYS["month"]` ويُقرأ هكذا: تلك نافذةُ **لوحةٍ** يقارن بها
    المشرفُ فترةً بفترة، وهذه رقمٌ **يقرؤه صاحبُه** تحت كلمة «هذا الشهر».
    ومن يقرأ «هذا الشهر» يعدّ من أوّله، فرقمٌ متدحرجٌ تحت هذا العنوان لا يطابق
    ما يحسبه بيده — **ولا يُخطئ فيه أحدٌ إلا نحن**.
    """
    local_now = now.astimezone(zone)
    start_local = datetime.combine(
        local_now.date().replace(day=1), time.min, tzinfo=zone
    )
    return start_local.astimezone(now.tzinfo or zone)


async def this_month(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    country: CountryCode,
    now: datetime,
) -> Decimal:
    """مجموعُ عمولة الشهر الجاري — **مجموعٌ في القاعدة** (§14).

    **وبالقيمة المطلقة**: العمولةُ قيدٌ سالبٌ بحكم قيدِ الفحص، والرأسُ يقول
    «كم اقتُطع» لا «سالب كم» — والطرحُ يقع هنا مرةً واحدة، كما في
    `earnings._ledger_sum`.
    """
    zone = await _zone(session, country)
    total = await session.scalar(
        select(func.coalesce(func.sum(func.abs(WalletTransaction.amount)), 0)).where(
            WalletTransaction.owner_id == user_id,
            WalletTransaction.owner_type == WalletOwnerType.DRIVER,
            WalletTransaction.type == WalletTransactionType.COMMISSION,
            WalletTransaction.created_at >= _month_start(zone, now),
            WalletTransaction.created_at <= now,
        )
    )
    # **ثلاثُ منازلَ دائماً** — الشكلُ السابع: `Decimal(0)` يُسلسَل «0» بينما
    # كلُّ مالٍ آخر «0.000»، فيقرأ الكبتنُ «0» في عمودٍ كلُّه بثلاث منازل
    return pricing.round_money(Decimal(total or 0))


async def rows_with_percent(
    session: AsyncSession, entries: Sequence[WalletTransaction]
) -> list[WalletTransactionOut]:
    """صفوفُ الكشف جاهزةً — **بانٍ واحدٌ يناديه البابان** (الشكلُ الثامن).

    **والعلّةُ وقعت في هذا الحقل نفسِه يومَ وُلد** (2026-08-20): `commission_percent`
    مُلئ في `GET /wallet/me/transactions` ونُسي في
    `GET /admin/wallets/{id}/transactions` — فيقرأ الكبتنُ «عمولة TAXO ١٠٪»
    ويقرأ المشرفُ في كشفِ الكبتن نفسِه مبلغاً بلا نسبة. **وكلُّ بابٍ صادقٌ
    وحدَه**، ولا شيءَ يقارنهما.

    **والعلاجُ الأول لا الثاني**: بانٍ واحدٌ لا اختبارُ مقارنة — فبابٌ ثالثٌ
    يُضاف غداً لا يجد ما ينساه.
    """
    percents = await percent_by_ride(session, list(entries))
    rows: list[WalletTransactionOut] = []
    for entry in entries:
        row = WalletTransactionOut.model_validate(entry)
        if entry.ride_id is not None:
            row.commission_percent = percents.get(entry.ride_id)
        rows.append(row)
    return rows
