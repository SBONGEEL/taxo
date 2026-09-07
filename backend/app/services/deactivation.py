"""إلغاءُ تفعيل حساب الكبتن (البند ١٣، SPEC القسم 7).

**بابٌ لم يكن في المشروع**، وبه وحده يخرج الرصيدُ المحتجَز (`wallet_settings.
withdrawal_reserve_amount`). وقواعدُه أربعٌ، كلُّها عن **ما لا يُترك خلفه**:

- **رحلةٌ جارية**: من يغلق حسابَه وراكبٌ في سيارته يترك راكباً في الطريق.
- **نزاعٌ مفتوح**: النزاعُ سؤالٌ عن مالٍ لم يُحسم، وإغلاقُ الحساب قبل حسمه
  يجعل الحسمَ بلا طرف.
- **دَينٌ غيرُ مسدَّد** (البند ١٥): يُقتطع من المحتجَز أولاً — قرارُ المالك،
  والمحتجَزُ وُجد لهذه اللحظة بعينها. ولا سلفَ اليوم، فالشرطُ مكتوبٌ ومعطَّلٌ
  بلا جدولٍ يقرؤه: يُوصَل حين تُبنى، ولا يُخترع له عمودٌ الآن.
- **وطلبٌ قائمٌ واحد**: يحرسه فهرسٌ جزئيٌّ في القاعدة لا فحصٌ يُسبَق.

**والقرارُ لمشرفٍ لا لمفتاح**: يمسّ مالاً محجوزاً ومسؤوليةً قائمة، فيمرّ كما
يمرّ السحب. **والصرفُ بعده عبر مسار السحب نفسِه** — لا كتابةَ مالٍ من هنا.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, InvalidInput, NotFound
from app.models.deactivation import DeactivationRequest
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    DeactivationStatus,
    DriverStatus,
    PaymentStatus,
)
from app.models.cancellation import RideCancellationCharge
from app.models.enums import CancellationChargeStatus
from app.models.payment import Payment
from app.models.ride import ACTIVE_DRIVER_STATUSES, ACTIVE_RIDER_STATUSES, Ride
from app.models.user import User
from app.services import advances, audit


class DeactivationBlocked(Conflict):
    code = "deactivation_blocked"
    message = "لا يمكن إلغاء التفعيل الآن"


def _now() -> datetime:
    return datetime.now(UTC)


async def _has_active_ride(session: AsyncSession, driver_id: uuid.UUID) -> bool:
    return (
        await session.scalar(
            select(Ride.id)
            .where(
                Ride.driver_id == driver_id,
                Ride.status.in_(ACTIVE_DRIVER_STATUSES),
            )
            .limit(1)
        )
    ) is not None


async def _has_open_dispute(session: AsyncSession, driver_id: uuid.UUID) -> bool:
    """نزاعٌ على دفعةٍ في إحدى رحلاته لم يُحسم بعد."""
    return (
        await session.scalar(
            select(Payment.id)
            .join(Ride, Ride.id == Payment.ride_id)
            .where(
                Ride.driver_id == driver_id,
                Payment.status == PaymentStatus.DISPUTED,
            )
            .limit(1)
        )
    ) is not None


async def _rider_active_ride(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """رحلةٌ يركبها الآن — **ومن يُغلق حسابَه وهو في الطريق يُترك فيه**."""
    return (
        await session.scalar(
            select(Ride.id)
            .where(Ride.rider_id == user_id, Ride.status.in_(ACTIVE_RIDER_STATUSES))
            .limit(1)
        )
    ) is not None


async def _rider_open_dispute(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """نزاعٌ على دفعةٍ في إحدى رحلاته — **سؤالٌ عن مالٍ لم يُحسم**."""
    return (
        await session.scalar(
            select(Payment.id)
            .join(Ride, Ride.id == Payment.ride_id)
            .where(Ride.rider_id == user_id, Payment.status == PaymentStatus.DISPUTED)
            .limit(1)
        )
    ) is not None


async def _rider_unpaid_charge(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """رسمُ إلغاءٍ مستحقٌّ عليه — **دَينٌ يخرج من جيب غيره إن مضى**."""
    return (
        await session.scalar(
            select(RideCancellationCharge.id)
            .where(
                RideCancellationCharge.payer_user_id == user_id,
                RideCancellationCharge.status == CancellationChargeStatus.PENDING,
            )
            .limit(1)
        )
    ) is not None


async def _rider_wallet_balance(session: AsyncSession, user: User) -> bool:
    """رصيدٌ موجبٌ في محفظته.

    **والراكبُ لا يسحب** (§7) — **فلا مخرجَ لماله إلا أن ينفقه أو يحوّله**.
    **وإغلاقُ حسابٍ فيه رصيدٌ مصادرةٌ لا خدمة**، ولا يجوز أن يقع بضغطةٍ لا
    يعرف صاحبُها ما فقد. **والمانعُ قابلٌ للإزالة بيده** — وهو شرطُ كلِّ
    مانعٍ في هذا الباب: يُقال ويُفعل، لا يُقال ويُنتظر.
    """
    from app.services import wallet as wallet_service

    return await wallet_service.balance_of(session, user) > 0


async def blockers(session: AsyncSession, user: User) -> list[str]:
    """ما يمنع الإغلاق الآن — **قائمةٌ لا أوّلُ سبب**.

    الشاشةُ تعرضها كلَّها: من أُخبر بمانعٍ فأزاله ثم صُدم بثانٍ يقرأ الرفضَ
    مماطلة. وهي مقروءةٌ حيّةً في كل نداء، فلا تُخزَّن على الصف.

    **والموضوعُ حسابٌ لا دور** (٢٠٢٦-٠٩-٠٧): من يحمل الدورين تُجمع موانعُه
    كلُّها — **فحسابٌ واحدٌ يُغلق مرّةً واحدة**، ولو قُرئ بدورٍ واحدٍ لَخرج من
    بابٍ وتَرك خلفه ما يمنع الآخر.

    **والرموزُ لا الجملُ** (قاعدةُ هذا الباب): الخلفيةُ لا تعرف من يقرأ،
    والنصُّ في السجلّ المركزيِّ لكلِّ تطبيق.
    """
    found: list[str] = []
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))

    # ── ما يخصّ الحسابَ نفسَه، كان صاحبُه كبتناً أو لا
    if await _rider_active_ride(session, user.id):
        found.append("active_ride")
    if await _rider_open_dispute(session, user.id):
        found.append("open_dispute")
    if await _rider_unpaid_charge(session, user.id):
        found.append("unpaid_charge")

    # **ومانعُ الرصيد لمن لا مخرجَ لماله وحدَه** — عطبٌ التُقط قبل تشغيله:
    # **الكبتنُ له مسارُ سحب**، **وهذا البابُ نفسُه هو ما يُطلق محتجَزَه**
    # (`withdrawal_reserve_amount`). فمنعُه برصيدٍ موجبٍ **يُبطل البابَ الذي
    # بُني له**: يُقال له «أفرغ رصيدَك» وهو لا يستطيع إفراغَه حتى يُغلق حسابَه.
    #
    # **والراكبُ حالٌ أخرى**: **لا يسحب البتّة** (§7)، ومخرجُه الإنفاقُ أو
    # التحويل — **فالمانعُ عنده قابلٌ للإزالة بيده**، وهو شرطُ كلِّ مانعٍ هنا.
    if driver is None and await _rider_wallet_balance(session, user):
        found.append("wallet_balance")

    if driver is None:
        return found

    # ── وما يخصّ الكبتنَ فوقها
    if await _has_active_ride(session, driver.id) and "active_ride" not in found:
        found.append("active_ride")
    if await _has_open_dispute(session, driver.id) and "open_dispute" not in found:
        found.append("open_dispute")
    # **دَينُ السلفة** (البند ١٥) — وُصل حين بُني جدولُه. وهو ما يجعل قرارَ
    # المالك في المحتجَز يعمل بلا سطرٍ واحد: **الاحتجازُ شرطٌ على السحب لا
    # قيدٌ في الدفتر**، والاقتطاعُ ليس سحباً — فالدَّينُ يُستوفى من الرصيد
    # كلِّه ثم يُصرف الباقي، وهو نصُّ «يُقتطع للدَّين أولاً»
    if await advances.outstanding_for(session, driver.id) is not None:
        found.append("unpaid_advance")
    return found


#: **جملةُ كلِّ مانعٍ للرسالة وحدَها** — والشاشةُ تقرأ الرمز.
#:
#: **ولمَ هنا أيضاً وقد قيل «الرموزُ لا الجمل»**: هذه جملةُ **الاستثناء** حين
#: يُرفض الطلب، لا نصُّ الشاشة. **ومن نادى البابَ من خارج التطبيق** — أداةٌ،
#: أو شاشةٌ لم تحدَّث — يستحقّ جواباً مفهوماً لا رمزاً عارياً.
_BLOCKER_TEXT = {
    "active_ride": "رحلةٌ جارية",
    "open_dispute": "نزاعٌ مفتوح",
    "unpaid_advance": "سلفةٌ غيرُ مسدَّدة",
    "unpaid_charge": "رسمُ إلغاءٍ مستحقّ",
    "wallet_balance": "رصيدٌ في المحفظة",
}


async def pending_for(
    session: AsyncSession, user_id: uuid.UUID
) -> DeactivationRequest | None:
    return await session.scalar(
        select(DeactivationRequest).where(
            DeactivationRequest.user_id == user_id,
            DeactivationRequest.status == DeactivationStatus.PENDING,
        )
    )


async def request(
    session: AsyncSession, *, user: User, reason: str | None = None
) -> DeactivationRequest:
    """يفتح طلبَ إغلاقٍ للحساب — الـcommit للمستدعي."""
    if user.deactivated_at is not None:
        raise DeactivationBlocked("الحساب مُغلقٌ أصلاً")

    # **وحالُ الكبتن تُقرأ أيضاً**: أثرُ الموافقة عنده `drivers.status` لا
    # `deactivated_at` (انظر `decide`) — **فالسؤالُ عن العمود الخطأ يفتح
    # طلبَ إغلاقٍ ثانياً لمن أُطفئت كبتنتُه سلفاً**.
    existing_driver = await session.scalar(
        select(Driver).where(Driver.user_id == user.id)
    )
    if (
        existing_driver is not None
        and existing_driver.status is DriverStatus.DEACTIVATED
    ):
        raise DeactivationBlocked("الحساب مُلغى التفعيل أصلاً")

    found = await blockers(session, user)
    if found:
        raise DeactivationBlocked(
            "أنهِ ما عليك أولاً: "
            + "، ".join(_BLOCKER_TEXT[item] for item in found)
        )

    row = DeactivationRequest(user_id=user.id, reason=(reason or "").strip() or None)
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        # الفهرسُ الجزئي: طلبٌ قائمٌ واحدٌ لكل حساب — والحارسُ في القاعدة لا في
        # فحصٍ سابقٍ يمكن أن تسبقه ضغطةٌ ثانية
        await session.rollback()
        raise DeactivationBlocked("لديك طلبٌ قائمٌ بالفعل") from exc
    return row


async def cancel(session: AsyncSession, *, user: User) -> DeactivationRequest:
    """يعدل صاحبُ الحساب عن طلبه — ما دام معلّقاً."""
    row = await _locked_pending(session, user.id)
    row.status = DeactivationStatus.CANCELLED
    row.resolved_at = _now()
    await session.flush()
    return row


async def _locked_pending(
    session: AsyncSession, user_id: uuid.UUID
) -> DeactivationRequest:
    """الطلبُ المعلّق **مقفولاً** قبل فحص حالته.

    قراران متزامنان (مشرفٌ يوافق وصاحبُ الحساب يلغي) يقرآن `pending` كلاهما
    ويكتبان حالتين — فيُغلق حسابٌ أُلغي طلبُه. والقفلُ هو ما يتسلسلهما.
    """
    row = await session.scalar(
        select(DeactivationRequest)
        .where(
            DeactivationRequest.user_id == user_id,
            DeactivationRequest.status == DeactivationStatus.PENDING,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFound("لا طلبَ قائم")
    return row


async def purge_personal_data(session: AsyncSession, user: User) -> dict[str, int]:
    """يمحو ما **يجوز** محوُه، ويترك ما **لا يجوز** — ويعيد ما مُحي بعدده.

    ## القسمةُ ليست ذوقاً — نصفُها قاعدةٌ ونصفُها قانون

    **يبقى**: الدفترُ (`wallet_transactions`) وشواهدُ الرحلات والدفعات.
    **والقاعدةُ تمنع محوَهما أصلاً** — «لا حذفَ صفٍّ على الإنتاج إطلاقاً»،
    **ولأنها مالُ ناسٍ آخرين أيضاً**: رحلةٌ فيها كبتنٌ قبض، ودفعةٌ فيها عمولةٌ
    حُسبت، **ومحوُ طرفٍ يُفقد الطرفَ الآخرَ حقَّه في إثبات ما جرى**.

    **ويُمحى**: ما هو شخصيٌّ محضٌ ولا يشهد على معاملة — **رموزُ البطاقات**
    (وهي ما يُشترى به)، **ورموزُ الأجهزة** (وهي ما يُرسل به إشعارٌ باسم TAXO
    إلى هاتف)، **والأماكنُ المحفوظة** (بيتُه وعملُه بإحداثيّاتهما).

    **وهذه الثلاثةُ محوٌ حقيقيٌّ لا إخفاء** — وهو ما يجعل «حذفَ الحساب»
    حذفاً لا تسميةً: **من بقيت بطاقتُه ورمزُ جهازه محفوظَين لم يُحذف حسابُه،
    وإنّما مُنع من الدخول**.

    **ولا تُلمس `name` و`phone`**: الأولى تظهر في شاهد الرحلة عند الكبتن،
    **والثاني هويّةُ الصفِّ في الدفتر** — ومحوُه يجعل قيداً ماليّاً بلا صاحبٍ
    يُعرف. **وأثرُه مكتوبٌ في نصِّ التأكيد** فلا يُفاجأ به أحد.
    """
    from app.models.device import DeviceToken
    from app.models.payment import SavedCard
    from app.models.place import SavedPlace

    removed: dict[str, int] = {}
    for label, model in (
        ("saved_cards", SavedCard),
        ("device_tokens", DeviceToken),
        ("saved_places", SavedPlace),
    ):
        rows = (
            await session.scalars(select(model).where(model.user_id == user.id))
        ).all()
        for row in rows:
            await session.delete(row)
        removed[label] = len(rows)
    await session.flush()
    return removed


async def decide(
    session: AsyncSession,
    *,
    request_id: uuid.UUID,
    admin: User,
    approved: bool,
    note: str | None = None,
) -> DeactivationRequest:
    """قرارُ المشرف — والرفضُ يحتاج سبباً مكتوباً كرفض المستند."""
    row = await session.get(DeactivationRequest, request_id)
    if row is None:
        raise NotFound("الطلب غير موجود")
    locked = await _locked_pending(session, row.user_id)

    if not approved and not (note or "").strip():
        raise InvalidInput("سبب الرفض مطلوب")

    subject = await session.get(User, locked.user_id)
    assert subject is not None  # مفتاحٌ أجنبيٌّ بـ CASCADE
    driver = await session.scalar(select(Driver).where(Driver.user_id == subject.id))

    if approved:
        # **الشروطُ تُعاد قراءتُها لحظةَ القرار**: رحلةٌ بدأت بعد الطلب، أو
        # نزاعٌ فُتح عليه — والقرارُ يُتخذ على الحال الآن لا على حالٍ مضى
        found = await blockers(session, subject)
        if found:
            raise DeactivationBlocked("تغيّر حالُ الحساب — راجع الطلب من جديد")
        # ## ومن له صفٌّ في `drivers` **لا يُغلق حسابُه، تُطفأ كبتنتُه**
        #
        # **عطبٌ أمسكه الاختبارُ قبل أن يُشحن** (٢٠٢٦-٠٩-٠٧): أوّلُ نسخةٍ كتبت
        # `deactivated_at` للجميع، **فردَّ البابُ الكبتنَ بـ`account_closed`
        # حين ذهب يسحب رصيدَه المحتجَز** — **وهو الرصيدُ الذي يُطلقه هذا
        # القرارُ بعينه**. فأُغلق البابُ الذي وُجدت الميزةُ لتفتحه.
        #
        # **وهو الشكلُ نفسُه الذي سُجّل في §56٫1**: فعلٌ يفترض مخرجاً لا يملكه
        # صاحبُه — وقع هنا **مرّتين في بابٍ واحد**، مرّةً في مانعِ الرصيد
        # ومرّةً في أثر القرار. **فيُقاس أثرُ كلِّ إغلاقٍ على ما بعده.**
        #
        # **والحالان ليستا واحدةً بحقّ**: للكبتن **ما يُقبض بعد الإغلاق**،
        # فحالُه `drivers.status = deactivated` — تُوقف التوزيعَ وتُبقي بابَ
        # السحب، **وهو ما كان قائماً قبل هذا البناء ولم يتغيّر**. والراكبُ لا
        # شيءَ له يُقبض — **ومانعُ الرصيد يمنع طلبَه أصلاً ما دام فيه فلس**.
        #
        # **وأثرُه بندٌ مفتوح** (§56٫3): حسابُ الكبتن **لا يُغلق بهذا الباب**،
        # فشرطُ المتجر في تطبيقه يبقى غيرَ مستوفى — **ويُقال ولا يُسكت عنه**.
        if driver is not None:
            driver.status = DriverStatus.DEACTIVATED
        else:
            subject.deactivated_at = _now()
        await purge_personal_data(session, subject)

    locked.status = (
        DeactivationStatus.APPROVED if approved else DeactivationStatus.REJECTED
    )
    locked.review_note = (note or "").strip() or None
    locked.resolved_by = admin.id
    locked.resolved_at = _now()

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="deactivation_request",
        entity_id=locked.id,
        details={"status": locked.status.value},
    )
    await session.flush()
    return locked
