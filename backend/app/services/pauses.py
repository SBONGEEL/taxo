"""الوقفةُ غير المخطَّطة وانتظارُ الوصول (SPEC §5.10-ب).

**حالتان بمصدرين مختلفين وحسابٍ واحد:**

1. **وقفةٌ في منتصف الرحلة** — «الراكبُ ينزل عند محلٍّ ويعود». يضغط الكبتنُ
   «نقطة توقف» فيبدأ عدّادٌ **لصالحه** بلا مهلةٍ مجانية: الوقفةُ لم تدخل
   التقدير أصلاً، فالمهلةُ فيها تعني وقتاً يقفه بلا مقابلٍ على شيءٍ لم يُحسب له.
2. **انتظارٌ عند الوصول** — بعد «وصلتُ إلى الراكب»، **بمهلةٍ مجانيةٍ** تحدّدها
   الإدارة: من تأخّر دقيقتين لا يُحاسَب، ومن تأخّر عشرين يُحاسَب.

**والمبلغُ يُحسب هنا والعدّادُ يمشي في التطبيقين** (§14): الوقتُ حسابُ وقت
والمالُ حسابُ مال. وهي القسمةُ نفسُها التي جعلت عدّادَ المحطات يُرسم محلياً بعد
أن كان الكبتنُ يقرأ «٠ دقيقة» طوال وقوفه.

**وقرارُ المالك في الفرع (هـ) هو أهمُّ ما في هذا الملف**: عدّادُ الوصول **لا
يبدأ خارج نطاق الالتقاء** — «وإلا صار «وصلت» الكاذبُ باباً للكسب». فالضغطةُ هي
ما يبدأ العدّاد (الفرع د)، **والنطاقُ شرطُ صحّتها** لا دليلَ نزاعٍ بعدها.

**ولا سقفَ على المحتسَب** (الفرع أ): السقفُ حدُّ صبرٍ يُنبَّه عنده الطرفان
**ولا تُنهى به رحلة** — الإنهاءُ فعلُ الكبتن. وهو سلوكُ سقف المحطات نفسُه.

**ولا حدَّ لعدد الوقفات** (الفرع ج): السقفُ الزمنيُّ يكفي، وحدٌّ عدديٌّ يعاقب
رحلةً طويلةً بطبيعتها.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.pause import (
    PAUSE_KIND_ARRIVAL,
    PAUSE_KIND_PAUSE,
    RidePause,
)
from app.models.ride import Ride
from app.services import pricing

# **نطاقُ الالتقاء الذي يصحّ عنده «وصلت»** — مئتا متر. أضيقُ منه يمنع كبتناً
# واقفاً خلف تقاطعٍ لا يستطيع الدخول إليه، وأوسعُ يجعل «وصلت» من الشارع
# المجاور بابَ كسبٍ — وهو ما نصَّ عليه الفرع (هـ).
ARRIVAL_RADIUS_METERS = 200


class NoOpenPause(NotFound):
    code = "no_open_pause"
    message = "لا توجد وقفةٌ مفتوحة"


class PauseAlreadyOpen(Conflict):
    code = "pause_already_open"
    message = "ثمّة وقفةٌ مفتوحةٌ بالفعل"


def _now() -> datetime:
    return datetime.now(UTC)


def minutes_of(pause: RidePause, now: datetime) -> Decimal:
    """دقائقُ وقفةٍ **بالثانية** — كما تُقاس المحطات (3.411 دقيقة لا 3).

    ووقفةٌ لم تُغلق بعد تُقاس **حتى الآن**: منه يرى الطرفان الرقمَ وهو يمشي.
    """
    end = pause.ended_at or now
    seconds = (end - pause.started_at).total_seconds()
    if seconds <= 0:
        return Decimal("0.000")
    return (Decimal(seconds) / Decimal(60)).quantize(Decimal("0.001"))


def charge_of(pause: RidePause, now: datetime) -> Decimal:
    """رسمُ وقفةٍ واحدة — **بمعدلاتها هي** لا بمعدلات الرحلة.

    والمهلةُ المجانيةُ **لكل وقفةٍ على حدة**، كما هي لكل محطة: من وقف دقيقتين
    في اثنتين لم ينتظر أحداً أربعاً، وجمعُ المهل يعاقبه على تفريق وقفاته.
    """
    if pause.price_per_min_at_pause <= 0:
        return Decimal("0.000")
    billable = minutes_of(pause, now) - Decimal(pause.free_minutes_at_pause)
    if billable <= 0:
        return Decimal("0.000")
    return pricing.round_money(billable * pause.price_per_min_at_pause)


async def of_ride(session: AsyncSession, ride_id: uuid.UUID) -> list[RidePause]:
    return list(
        (
            await session.scalars(
                select(RidePause)
                .where(RidePause.ride_id == ride_id)
                .order_by(RidePause.started_at)
            )
        ).all()
    )


async def open_pause(
    session: AsyncSession, ride_id: uuid.UUID
) -> RidePause | None:
    return await session.scalar(
        select(RidePause).where(
            RidePause.ride_id == ride_id, RidePause.ended_at.is_(None)
        )
    )


async def charge_for(
    session: AsyncSession, ride: Ride, now: datetime | None = None
) -> Decimal:
    """رسمُ وقفاتِ هذه الرحلة حتى اللحظة.

    **يُقرأ أثناء الرحلة كما يُقرأ عند إنهائها**: منه يرى الراكبُ رقمَه الحالي
    وهو واقف، فلا مفاجأةَ في شاشة الدفع — **ومبلغٌ لم يُعلَن حين نشأ يُقرأ خطأً
    في الحساب** (نصُّ المواصفة).
    """
    moment = now or _now()
    return pricing.round_money(
        sum(
            (charge_of(pause, moment) for pause in await of_ride(session, ride.id)),
            Decimal("0.000"),
        )
    )


# ------------------------------------------------------------ الفتحُ والإغلاق


async def _start(
    session: AsyncSession, ride: Ride, kind: str, *, free_minutes: int
) -> RidePause:
    pause = RidePause(
        ride_id=ride.id,
        kind=kind,
        started_at=_now(),
        # **تُنسخ المعاملاتُ من الرحلة لا من الإعدادات** — والرحلةُ نفسُها
        # جمّدتها لحظةَ إنشائها. ونسخةٌ ثانيةٌ هنا كي لا يُعاد تسعيرُ وقفةٍ مضت
        price_per_min_at_pause=ride.pause_price_per_min_at_ride,
        free_minutes_at_pause=free_minutes,
        max_minutes_at_pause=ride.pause_max_minutes_at_ride,
    )
    session.add(pause)
    try:
        await session.flush()
    except IntegrityError as exc:
        # **الفهرسُ الجزئيُّ هو الحارس** لا فحصٌ سابقٌ يمكن أن يُسبَق: ضغطتان
        # متزامنتان كانتا ستفتحان وقفتين فيُحتسب الوقتُ مرتين على وقفةٍ واحدة
        await session.rollback()
        raise PauseAlreadyOpen() from exc
    return pause


async def begin_pause(session: AsyncSession, ride: Ride) -> RidePause:
    """«نقطة توقف» — يضغطها الكبتنُ أثناء الرحلة. الـcommit للمستدعي.

    **ولا مهلةَ مجانية هنا**: الوقفةُ لم تدخل التقدير، فالعدّادُ يبدأ بالضغطة.
    """
    if ride.status.value not in ("in_progress", "at_stop"):
        raise InvalidInput("الوقفة تكون أثناء الرحلة")
    return await _start(session, ride, PAUSE_KIND_PAUSE, free_minutes=0)


async def begin_arrival_wait(
    session: AsyncSession, ride: Ride, *, within_radius: bool
) -> RidePause | None:
    """عدّادُ الانتظار عند الوصول — **يبدأ بالضغطة، ولا يبدأ خارج النطاق**.

    قرارُ المالك (الفرع هـ) بتعليله: **وإلا صار «وصلت» الكاذبُ باباً للكسب**.
    فمن ضغط «وصلت» وهو في شارعٍ آخرَ لا عدّادَ له — ولا يُمنع من الضغط ولا
    تُرفض حالتُه: الرحلةُ تمضي، والذي لا يقع هو **المال**.

    ويعيد `None` حين لا يبدأ — وهي حالٌ عادية لا خطأ.
    """
    if not within_radius:
        return None
    if ride.pause_price_per_min_at_ride <= 0:
        # **ولا صفَّ بلا سعر**: وقفةٌ سعرُها صفرٌ صفٌّ يُكتب ولا يُحاسَب به،
        # ويجعل الشاشةَ تعرض عدّاداً يمشي إلى لا شيء
        return None
    return await _start(
        session,
        ride,
        PAUSE_KIND_ARRIVAL,
        free_minutes=ride.arrival_free_minutes_at_ride,
    )


async def end_open(session: AsyncSession, ride_id: uuid.UUID) -> RidePause | None:
    """يُغلق الوقفةَ المفتوحة إن وُجدت — ويعيدها. الـcommit للمستدعي.

    **ويُستدعى من ثلاثة مواضع**: «استئناف» بيد الكبتن، وبدءُ الرحلة (يُغلق
    انتظارَ الوصول)، وإنهاؤها (يُغلق ما بقي مفتوحاً). **وثلاثتُها بابٌ واحد**
    لأن وقفةً تبقى مفتوحةً بعد انتهاء الرحلة تُحاسَب **إلى الأبد**: `minutes_of`
    تقيس حتى الآن، فتكبر الفاتورةُ كلَّما فُتحت الشاشة.
    """
    pause = await open_pause(session, ride_id)
    if pause is None:
        return None
    pause.ended_at = _now()
    await session.flush()
    return pause


async def resume(session: AsyncSession, ride: Ride) -> RidePause:
    """«استئناف» — **بيد الكبتن وحدَه** (الفرع ب).

    وعدّادٌ توقفه الحركةُ يخطئ في الزحام، **وعدّادٌ لا يُصدَّق لا يُحتجّ به**.
    """
    pause = await end_open(session, ride.id)
    if pause is None:
        raise NoOpenPause()
    return pause
