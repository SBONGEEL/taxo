"""دَينُ الكبتن — نشأتُه، وتحصيلُه، ومنعُه، ورفعُ منعِه (الترحيلة `0061`).

## المسدودُ الذي فتحه هذا الملف

**قِيس 2026-08-30**: عمولةُ رحلةِ الكاش كانت تُخصم من محفظة الكبتن قيداً
سالباً، و`wallet.record` يرفض السالب — فكانت التسويةُ **تُرمى** بجملةٍ تقول
«اشحن المحفظة»، **وبابُ شحن محفظة الكبتن أُلغي**. فكبتنٌ رصيدُه دون العمولة
**لا يُنهي رحلتَه أصلاً**.

**والعلاجُ ليس إرخاءَ الحارس**: `balance_after < 0` يبقى مرفوضاً (قرارُ المالك
القائم: «لا رصيد سالب في المحفظة إطلاقاً»). العلاجُ أن **المستحقَّ يخرج من
الدفتر إلى جدولِه** — وهو ما فعلته السلفةُ ورسمُ الإلغاء قبله.

## ولمَ يُحصَّل **قبل** السلفة

**السلفةُ مالٌ أعطيناه، والدَّينُ مالٌ يحمله عنّا.** أجرةُ الكاش كلُّها دخلت
جيبَه ومنها عمولتُنا — فهو **قابضٌ لا مَدين**. ولذلك يتقدّم، وهو نصُّ
«الأولوية: الدَّينُ أوّلاً» (قرارُ المالك 2026-08-30): «فرصيدٌ يكبر ودَينٌ
قائمٌ يريه مالاً لا يملكه».

## وصفٌّ كاملٌ لا كسرٌ منه في التحصيل الآليّ

**كلُّ صفٍّ عمولةُ رحلةٍ بعينها**، وقيدُه في الدفتر يحمل `ride_id` **تلك
الرحلة** لا رحلةَ اليوم — فمن سأل «لماذا نقص هذا المبلغ؟» وجد الرحلة. ولو
حُصِّل نصفُ صفٍّ لَلزم قيدان لرحلةٍ واحدةٍ بمفتاحَي تفرُّدٍ مختلفين، **ولَنُسب
نصفُ عمولةٍ إلى رحلةٍ لا تخصّها**.

**والجزئيُّ حيث أراده المالك**: في **سداده هو** — `apply_settlement` تقبل أيَّ
مبلغٍ وتوزّعه على الصفوف من أقدمها، والمنعُ يُرفع عند **الصفر** لا قبله.

## والسقفُ فارغٌ عمداً

`payment_settings.driver_debt_ceiling` **`None` تعني «لا سقف»** لا «صفراً»
(«ولا تضعه حتى أقرّه»). فالمسارُ كاملٌ ولا يُحجب أحدٌ اليوم — **وصفرٌ كان
سيحجب كلَّ كبتنٍ عليه فلسٌ واحد**.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientBalance, InvalidInput
from app.models.debt import DriverDebt
from app.models.driver import Driver
from app.models.enums import (
    CountryCode,
    DriverDebtSource,
    DriverDebtStatus,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.payment import Payment
from app.models.ride import Ride
from app.models.user import User
from app.services import settings_service, wallet
from app.services.pricing import round_money

logger = logging.getLogger(__name__)

#: **السببُ يسافر مع القيد** ولا تخترعه الشاشة — قاعدةُ `advances` نفسُها
_COLLECT_NOTE = "تحصيل عمولة رحلة سابقة قُبضت نقداً"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def outstanding_rows(
    session: AsyncSession, driver_id: uuid.UUID, *, for_update: bool = False
) -> list[DriverDebt]:
    """الصفوفُ القائمة **من أقدمها** — والترتيبُ جزءٌ من القاعدة لا زينة."""
    query = (
        select(DriverDebt)
        .where(
            DriverDebt.driver_id == driver_id,
            DriverDebt.status == DriverDebtStatus.OUTSTANDING,
        )
        .order_by(DriverDebt.created_at)
    )
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return list((await session.scalars(query)).all())


async def outstanding_of(session: AsyncSession, driver_id: uuid.UUID) -> Decimal:
    """مجموعُ ما بقي — **`amount - collected`** لا `amount`."""
    total = await session.scalar(
        select(
            func.coalesce(func.sum(DriverDebt.amount - DriverDebt.collected), 0)
        ).where(
            DriverDebt.driver_id == driver_id,
            DriverDebt.status == DriverDebtStatus.OUTSTANDING,
        )
    )
    return round_money(Decimal(total or 0))


async def ceiling_for(session: AsyncSession, country: CountryCode) -> Decimal | None:
    """سقفُ اللوحة — **و`None` لا سقفَ**، فلا يُحجب أحد."""
    setting = await settings_service.get_payment_settings(session, country)
    if setting is None:
        return None
    return setting.driver_debt_ceiling


async def record_from_ride(
    session: AsyncSession,
    *,
    driver: Driver,
    ride: Ride,
    payment: Payment,
    amount: Decimal,
) -> DriverDebt | None:
    """يكتب مستحقّاً على كبتنٍ قبض أجرتَه بيده — **ولا يُفشل التسوية أبداً**.

    **والتفرُّدُ في القاعدة** (`driver_debt_once_per_payment`): تسويةٌ تُعاد لا
    تكتب دَيناً ثانياً. ويُقرأ الصفُّ القائمُ قبل الإدراج فلا استثناءَ يُبتلع.
    """
    amount = round_money(amount)
    if amount <= 0:
        return None

    existing = await session.scalar(
        select(DriverDebt).where(
            DriverDebt.payment_id == payment.id,
            DriverDebt.source == DriverDebtSource.RIDE_COMMISSION,
        )
    )
    if existing is not None:
        return existing

    debt = DriverDebt(
        driver_id=driver.id,
        country_code=ride.country_code,
        source=DriverDebtSource.RIDE_COMMISSION,
        amount=amount,
        collected=Decimal("0"),
        currency=payment.currency,
        ride_id=ride.id,
        payment_id=payment.id,
        status=DriverDebtStatus.OUTSTANDING,
    )
    session.add(debt)
    await session.flush()
    return debt


async def _close(session: AsyncSession, debt: DriverDebt) -> None:
    debt.collected = debt.amount
    debt.status = DriverDebtStatus.SETTLED
    debt.settled_at = _now()
    await session.flush()


async def collect_from_balance(
    session: AsyncSession, *, driver: Driver, user: User
) -> Decimal:
    """يحصّل ما يغطّيه رصيدُه **لحظةَ أن يدخل المال** — صفّاً كاملاً فأكمل.

    **يُنادى من تسوية كلِّ رحلةٍ يدخل مالُها المحفظة**، قبل اقتطاع السلفة.
    **ولا يُفشل التسويةَ أبداً**: ما لم يغطِّه الرصيدُ يبقى في جدوله.

    **ويقرأ الرصيدَ كلَّه لا أجرَ هذه الرحلة وحدَها**: رصيدٌ قائمٌ ودَينٌ قائم
    «يريه مالاً لا يملكه» (قرارُ المالك) — فما دام الرصيدُ يغطّي صفّاً حُصِّل.
    """
    rows = await outstanding_rows(session, driver.id, for_update=True)
    if not rows:
        return Decimal("0")

    taken = Decimal("0")
    for debt in rows:
        remaining = round_money(debt.amount - debt.collected)
        if remaining <= 0:  # pragma: no cover - يحرسه قيدُ القاعدة
            await _close(session, debt)
            continue
        available = await wallet.balance_of(
            session, user, declared=WalletOwnerType.DRIVER
        )
        if available < remaining:
            # **يتوقّف عند أول صفٍّ لا يغطّيه** — والأقدمُ أوّلاً، فلا يُقفز
            # فوق دَينٍ قديمٍ إلى أصغرَ منه
            break
        try:
            await wallet.record(
                session,
                owner=user,
                owner_type=WalletOwnerType.DRIVER,
                tx_type=WalletTransactionType.COMMISSION,
                amount=-remaining,
                # **رحلةُ الدَّين لا رحلةُ اليوم** — فمن سأل عن النقص وجدها
                ride_id=debt.ride_id,
                reference=_COLLECT_NOTE,
                idempotency_key=f"debt_collect:{debt.id}",
            )
        except InsufficientBalance:  # pragma: no cover - سباقٌ نادر
            logger.warning("تعذّر تحصيل دَين الكبتن %s — الرصيد لا يكفي", driver.id)
            break
        await _close(session, debt)
        taken += remaining

    if taken > 0:
        await refresh_block(session, driver=driver, country=user.country_code)
    return round_money(taken)


async def apply_settlement(
    session: AsyncSession,
    *,
    driver: Driver,
    country: CountryCode,
    amount: Decimal,
) -> Decimal:
    """يوزّع مبلغاً سدّده الكبتن **خارج المحفظة** على صفوفه من أقدمها.

    **والجزئيُّ مقبولٌ ويُنقص الدَّين** (قرارُ المالك 2026-08-30) — ويُكتب في
    `collected` لا في جدولٍ رابع. **ولا قيدَ في الدفتر**: مالُه خرج من يده لا
    من محفظته، كالاشتراك بالبطاقة تماماً.

    **والمنعُ يُرفع عند الصفر لا قبله** — فمن سدَّد نصفَه يبقى ممنوعاً.
    """
    amount = round_money(amount)
    if amount <= 0:
        raise InvalidInput("مبلغ السداد يجب أن يكون أكبر من صفر")

    left = amount
    for debt in await outstanding_rows(session, driver.id, for_update=True):
        if left <= 0:
            break
        remaining = round_money(debt.amount - debt.collected)
        if remaining <= 0:  # pragma: no cover
            await _close(session, debt)
            continue
        take = min(left, remaining)
        debt.collected = round_money(debt.collected + take)
        if debt.collected >= debt.amount:
            debt.status = DriverDebtStatus.SETTLED
            debt.settled_at = _now()
        left -= take
    await session.flush()

    await refresh_block(session, driver=driver, country=country)
    # **ما زاد عن الدَّين لا يُبتلع ولا يُقيَّد** — يُعاد رقماً ليقوله المشرف
    return round_money(amount - left)


async def refresh_block(
    session: AsyncSession, *, driver: Driver, country: CountryCode
) -> bool:
    """يُشعل المنعَ فوق السقف، ويُطفئه عند **الصفر** — في المسار نفسِه.

    **لا بالدورة التالية**: «من سدَّد وبقي ممنوعاً عشر دقائق يقرأ السدادَ بلا
    أثر» — قاعدةُ `advances._settle_if_clear`
    و`cancellation.collect_from_carrier` نفسُها.

    **والإطفاءُ شرطُه الصفرُ لا النزولُ تحت السقف** (قرارُ المالك): من سدَّد
    نصفَه بقي ممنوعاً — وإلا صار السقفُ باباً يُفتح ويُغلق كلَّ رحلة.
    """
    total = await outstanding_of(session, driver.id)
    if total <= 0:
        if driver.debt_blocked:
            driver.debt_blocked = False
            await session.flush()
        return False

    if driver.debt_blocked:
        return True

    # **الدولةُ تأتي من صاحبها لا من صفِّ الكبتن**: `drivers` بلا عمودِ دولة
    # (قِيس 2026-08-30) — والسوقُ في `users.country_code`.
    ceiling = await ceiling_for(session, country)
    if ceiling is not None and total > ceiling:
        driver.debt_blocked = True
        await session.flush()
        return True
    return False


async def write_off(
    session: AsyncSession,
    *,
    debt: DriverDebt,
    actor: User,
    reason: str,
) -> DriverDebt:
    """شطبُ مستحقٍّ بقرارٍ إداريّ — **بسببٍ مكتوبٍ لا بلا سبب**."""
    if debt.status is not DriverDebtStatus.OUTSTANDING:
        raise InvalidInput("هذا المستحقّ ليس قائماً")
    debt.status = DriverDebtStatus.WRITTEN_OFF
    debt.written_off_at = _now()
    debt.written_off_by = actor.id
    debt.writeoff_reason = reason
    await session.flush()
    return debt
