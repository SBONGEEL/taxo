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
from app.models.payment import Payment
from app.models.ride import ACTIVE_DRIVER_STATUSES, Ride
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


async def blockers(session: AsyncSession, driver: Driver) -> list[str]:
    """ما يمنع الإغلاق الآن — **قائمةٌ لا أوّلُ سبب**.

    الشاشةُ تعرضها كلَّها: من أُخبر بمانعٍ فأزاله ثم صُدم بثانٍ يقرأ الرفضَ
    مماطلة. وهي مقروءةٌ حيّةً في كل نداء، فلا تُخزَّن على الصف.
    """
    found: list[str] = []
    if await _has_active_ride(session, driver.id):
        found.append("active_ride")
    if await _has_open_dispute(session, driver.id):
        found.append("open_dispute")
    # **دَينُ السلفة** (البند ١٥) — وُصل حين بُني جدولُه. وهو ما يجعل قرارَ
    # المالك في المحتجَز يعمل بلا سطرٍ واحد: **الاحتجازُ شرطٌ على السحب لا
    # قيدٌ في الدفتر**، والاقتطاعُ ليس سحباً — فالدَّينُ يُستوفى من الرصيد
    # كلِّه ثم يُصرف الباقي، وهو نصُّ «يُقتطع للدَّين أولاً»
    if await advances.outstanding_for(session, driver.id) is not None:
        found.append("unpaid_advance")
    return found


async def pending_for(
    session: AsyncSession, driver_id: uuid.UUID
) -> DeactivationRequest | None:
    return await session.scalar(
        select(DeactivationRequest).where(
            DeactivationRequest.driver_id == driver_id,
            DeactivationRequest.status == DeactivationStatus.PENDING,
        )
    )


async def request(
    session: AsyncSession, *, driver: Driver, reason: str | None = None
) -> DeactivationRequest:
    """يفتح طلبَ إلغاءٍ — الـcommit للمستدعي."""
    if driver.status is DriverStatus.DEACTIVATED:
        raise DeactivationBlocked("الحساب مُلغى التفعيل أصلاً")

    found = await blockers(session, driver)
    if found:
        raise DeactivationBlocked(
            "أنهِ ما عليك أولاً: "
            + "، ".join(
                {
                    "active_ride": "رحلةٌ جارية",
                    "open_dispute": "نزاعٌ مفتوح",
                    "unpaid_advance": "سلفةٌ غيرُ مسدَّدة",
                }[item]
                for item in found
            )
        )

    row = DeactivationRequest(
        driver_id=driver.id, reason=(reason or "").strip() or None
    )
    session.add(row)
    try:
        await session.flush()
    except IntegrityError as exc:
        # الفهرسُ الجزئي: طلبٌ قائمٌ واحدٌ لكل كبتن — والحارسُ في القاعدة لا في
        # فحصٍ سابقٍ يمكن أن تسبقه ضغطةٌ ثانية
        await session.rollback()
        raise DeactivationBlocked("لديك طلبٌ قائمٌ بالفعل") from exc
    return row


async def cancel(session: AsyncSession, *, driver: Driver) -> DeactivationRequest:
    """يعدل الكبتنُ عن طلبه — ما دام معلّقاً."""
    row = await _locked_pending(session, driver.id)
    row.status = DeactivationStatus.CANCELLED
    row.resolved_at = _now()
    await session.flush()
    return row


async def _locked_pending(
    session: AsyncSession, driver_id: uuid.UUID
) -> DeactivationRequest:
    """الطلبُ المعلّق **مقفولاً** قبل فحص حالته.

    قراران متزامنان (مشرفٌ يوافق وكبتنٌ يلغي) يقرآن `pending` كلاهما ويكتبان
    حالتين — فيُغلق حسابٌ أُلغي طلبُه. والقفلُ هو ما يتسلسلهما.
    """
    row = await session.scalar(
        select(DeactivationRequest)
        .where(
            DeactivationRequest.driver_id == driver_id,
            DeactivationRequest.status == DeactivationStatus.PENDING,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFound("لا طلبَ قائم")
    return row


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
    locked = await _locked_pending(session, row.driver_id)

    if not approved and not (note or "").strip():
        raise InvalidInput("سبب الرفض مطلوب")

    driver = await session.get(Driver, locked.driver_id)
    assert driver is not None  # مفتاحٌ أجنبيٌّ بـ CASCADE

    if approved:
        # **الشروطُ تُعاد قراءتُها لحظةَ القرار**: رحلةٌ بدأت بعد الطلب، أو
        # نزاعٌ فُتح عليه — والقرارُ يُتخذ على الحال الآن لا على حالٍ مضى
        found = await blockers(session, driver)
        if found:
            raise DeactivationBlocked("تغيّر حالُ الكبتن — راجع الطلب من جديد")
        driver.status = DriverStatus.DEACTIVATED

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
