"""**التقاطُ نشاط المستخدمين لإشعارات المالك** (SPEC §٨١، أمرُ المالك ٢٠٢٦-١٠-٢٠) — **بابٌ واحدٌ يرى كلَّ الأبواب**.

## لمَ مستمعٌ على الجلسة لا نداءٌ في كلِّ خدمة

**الحدثُ الواحدُ يقع من أبوابٍ كثيرة**: دفعةٌ تُؤكَّد من الكبتن ومن المشرف ومن خطّاف Chargily ومن الكنس الدوريّ، ورحلةٌ تُطلب من
التطبيق ومن الحجز المجدول ومن المشوار الثابت. **ونداءٌ يُكتب في كلِّ بابٍ ينساه البابُ القادم** — وهي «بابان ينشران الشيءَ نفسَه» بوجهٍ
آخر. فهنا **مستمعٌ بعد كلِّ `flush`** يقرأ ما أُدرج وما تغيّرت حالُه في الجداول المراقَبة، **ويحفظه في الجلسة**، **ثمّ يُسلَّم بعد
الالتزام وحدَه**: ما رُجع عنه لا يُشعِر بشيء. **ولا يمسّ منطقَ مالٍ ولا جدولَ مال** — يقرأ ما كُتب ولا يكتب.

## ولا يؤخّر رحلةً ولا دفعةً ولا تسجيلاً

**التسليمُ دفعٌ إلى قائمةٍ في Redis** بمهمّةٍ لا يُنتظر جوابُها (في التطبيق)، أو بنداءٍ مقطوعٍ بنصف ثانية (في العامل) — **وكلُّ استثناءٍ
يُبتلع ويُسجَّل**. ثمّ يقرؤها العاملُ كلَّ خمس ثوانٍ (`services/admin_alerts.drain`) فيكتب الإشعارَ ويرسله. **فإشعارٌ تعطّل لا يصل،
والرحلةُ تمضي.**

## وحدُّه مكتوب

* **يرى ما يمرّ بالـORM وحدَه**: `update(Model).values(status=…)` لا يمرّ بـ`flush`. **وقِيس ٢٠٢٦-١٠-٢١ أنْ لا بابَ يكتب حالاً مراقَبةً
  هكذا** (`update(Ride)` في ثلاثة مواضع، كلُّها أعمدةٌ أخرى) — **ويحرس ذلك `test_admin_alerts.py::test_no_core_update_writes_a_watched_status`**.
* **ولا يرى ما يكتبه سكربتُ خادمٍ بلا تطبيق** (`python -m scripts.…`) — تلك أعمالُ المشرف نفسِه لا نشاطُ مستخدمين.
* **ورحلاتُ وضع الضيف ودفعاتُه لا تُرى أصلاً**: لا صفوفَ لها (`services/guest.py` — «لا حسابَ ولا رحلةَ ولا مال»). **وملاحظةُ الضيف
  صفٌّ حقيقيّ** (`app_feedback.guest_session_id`) فتُرى بوسم «ضيف».
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: القائمةُ التي يقرؤها العامل — **وسقفُها** كي لا تكبر بلا حدٍّ إن توقّف العاملُ أيّاماً
QUEUE_KEY = "admin_alerts:inbox"
QUEUE_CAP = 5000
_BUFFER = "taxo.admin_alerts"

#: **في العامل يُدفع بنداءٍ مقطوع لا بمهمّة**: حلقتُه تقف بين مهمّةٍ وأخرى، فمهمّةٌ تُنشأ بعد آخر التزامٍ تنتظر المهمّةَ التالية
SYNC_SHIP = False
#: الاختباراتُ تطفئه لتقيس ما يُلتقط دون أن يُرسل
ENABLED = True

Event = dict[str, Any]
_PENDING: set[asyncio.Task[None]] = set()
_HANDLERS: dict[type, Callable[[Any, bool], Iterator[Event]]] = {}
_installed = False


def _event(kind: str, model: str, pk: Any, **extra: Any) -> Event:
    return {"k": kind, "m": model, "id": str(pk), "x": extra, "t": datetime.now(UTC).isoformat()}


def _change(obj: Any, attr: str) -> tuple[Any, Any] | None:
    """**ما تغيّر في هذا الـflush** — `(قبل، بعد)`، و`None` إن لم يتغيّر."""
    history = inspect(obj).attrs[attr].history
    if not history.added:
        return None
    after = history.added[0]
    before = history.deleted[0] if history.deleted else None
    return None if before == after else (before, after)


def _value(obj: Any, attr: str, new: bool) -> Any:
    """**الحالُ الجديدةُ لهذا الـflush** — للمُدرَج قيمتُه، وللمعدَّل ما تغيّر إليه وحدَه."""
    if new:
        return getattr(obj, attr)
    changed = _change(obj, attr)
    return changed[1] if changed else None


def _install_handlers() -> None:
    # **الاستيرادُ هنا لا في رأس الملف**: النماذجُ تستورد ما يستورد هذا الملفَّ في بعض المسارات
    from app.models.driver import Driver, DriverDocument
    from app.models.enums import (
        DocumentReviewStatus,
        PaymentMethod,
        PaymentStatus,
        ProviderOrderStatus,
        RideStatus,
        UserRole,
        WalletTransactionType,
        WithdrawalStatus,
    )
    from app.models.feedback import AppFeedback
    from app.models.payment import Payment
    from app.models.photo_report import UserPhotoReport
    from app.models.provider_order import ProviderOrder
    from app.models.rating import Rating
    from app.models.ride import Ride
    from app.models.rider_subscription import RiderSubscription
    from app.models.subscription import DriverSubscription
    from app.models.trip_chat import RideMessageReport
    from app.models.user import User
    from app.models.wallet import WalletTopupRequest, WalletTransaction, WithdrawalRequest

    def user(obj: User, new: bool) -> Iterator[Event]:
        # **الكبتنُ يُرى من صفِّ الكبتن** (`captain_signup`) — وحسابُه يُنشأ بدورِ كبتنٍ لا راكب، فلا يُعدّ مرّتين
        if new and obj.role == UserRole.RIDER:
            yield _event("rider_signup", "user", obj.id)

    def driver(obj: Driver, new: bool) -> Iterator[Event]:
        if new:
            yield _event("captain_signup", "driver", obj.id)
            return
        changed = _change(obj, "debt_blocked")
        if changed and changed[1] is True:
            yield _event("debt_cap_reached", "driver", obj.id)

    document_kinds = {
        DocumentReviewStatus.PENDING: "documents_submitted",
        DocumentReviewStatus.APPROVED: "documents_approved",
        DocumentReviewStatus.REJECTED: "documents_rejected",
    }

    def document(obj: DriverDocument, new: bool) -> Iterator[Event]:
        status = _value(obj, "review_status", new)
        if status in document_kinds:
            yield _event(document_kinds[status], "document", obj.id, driver_id=str(obj.driver_id))

    payment_kinds = {
        PaymentStatus.CONFIRMED: "payment_succeeded",
        PaymentStatus.FAILED: "payment_failed",
        PaymentStatus.VOIDED: "payment_cancelled",
        PaymentStatus.REFUNDED: "refund",
        PaymentStatus.DISPUTED: "complaint",
    }
    # **قنواتٌ لا يدفعها أحدٌ من جيبه** — خصمُ الكوبون والمشاركة ورصيدُ المشوار تُنشئها المنصّةُ وتؤكّدها بنفسها
    platform_methods = {PaymentMethod.PROMO, PaymentMethod.SHARE, PaymentMethod.COMMUTE}

    def payment(obj: Payment, new: bool) -> Iterator[Event]:
        if obj.method in platform_methods:
            return
        status = _value(obj, "status", new)
        if status in payment_kinds:
            yield _event(payment_kinds[status], "payment", obj.id, status=str(status))

    def order(obj: ProviderOrder, new: bool) -> Iterator[Event]:
        # **النجاحُ لا يُقرأ من هنا**: يقع معه صفُّه الحقيقيّ (دفعةٌ تُؤكَّد · قيدُ شحن · اشتراك) — فيُقرأ هناك مرّةً واحدة
        status = _value(obj, "status", new)
        if status is ProviderOrderStatus.FAILED:
            yield _event("payment_failed", "order", obj.id)
        elif status is ProviderOrderStatus.CANCELLED:
            yield _event("payment_cancelled", "order", obj.id)

    def ledger(obj: WalletTransaction, new: bool) -> Iterator[Event]:
        if not new:
            return
        if obj.type is WalletTransactionType.TOPUP:
            yield _event("wallet_topup", "ledger", obj.id)
        elif obj.type is WalletTransactionType.ADJUSTMENT:
            yield _event("manual_adjustment", "ledger", obj.id)

    def topup_request(obj: WalletTopupRequest, new: bool) -> Iterator[Event]:
        if new:
            yield _event("topup_requested", "topup_request", obj.id)

    withdrawal_kinds = {
        WithdrawalStatus.PAID: "withdrawal_paid",
        WithdrawalStatus.REJECTED: "withdrawal_rejected",
    }

    def withdrawal(obj: WithdrawalRequest, new: bool) -> Iterator[Event]:
        if new:
            yield _event("withdrawal_requested", "withdrawal", obj.id)
            return
        status = _value(obj, "status", False)
        if status in withdrawal_kinds:
            yield _event(withdrawal_kinds[status], "withdrawal", obj.id)

    def subscription(obj: DriverSubscription, new: bool) -> Iterator[Event]:
        # **صفُّ الاشتراك لا يوجد إلا بعد وصول ماله** (CLAUDE.md) — فإدراجُه هو الدفعُ نفسُه
        if new:
            yield _event("subscription_purchased", "subscription", obj.id)

    def rider_subscription(obj: RiderSubscription, new: bool) -> Iterator[Event]:
        if new:
            yield _event("subscription_purchased", "rider_subscription", obj.id)

    ride_kinds = {
        RideStatus.ACCEPTED: ("ride_accepted", None),
        RideStatus.COMPLETED: ("ride_completed", None),
        RideStatus.CANCELLED_BY_RIDER: ("ride_cancelled", "rider"),
        RideStatus.CANCELLED_BY_DRIVER: ("ride_cancelled", "driver"),
        RideStatus.NO_DRIVER_FOUND: ("ride_cancelled", "no_driver"),
    }

    def ride(obj: Ride, new: bool) -> Iterator[Event]:
        if new:
            yield _event("ride_requested", "ride", obj.id)
            return
        status = _value(obj, "status", False)
        if status in ride_kinds:
            kind, by = ride_kinds[status]
            yield _event(kind, "ride", obj.id, by=by) if by else _event(kind, "ride", obj.id)

    def rating(obj: Rating, new: bool) -> Iterator[Event]:
        if new and obj.stars <= 2:
            yield _event("low_rating", "rating", obj.id)

    def feedback(obj: AppFeedback, new: bool) -> Iterator[Event]:
        if new:
            yield _event("feedback", "feedback", obj.id)

    def message_report(obj: RideMessageReport, new: bool) -> Iterator[Event]:
        if new:
            yield _event("complaint", "message_report", obj.id)

    def photo_report(obj: UserPhotoReport, new: bool) -> Iterator[Event]:
        if new:
            yield _event("complaint", "photo_report", obj.id)

    _HANDLERS.update(
        {
            User: user,
            Driver: driver,
            DriverDocument: document,
            Payment: payment,
            ProviderOrder: order,
            WalletTransaction: ledger,
            WalletTopupRequest: topup_request,
            WithdrawalRequest: withdrawal,
            DriverSubscription: subscription,
            RiderSubscription: rider_subscription,
            Ride: ride,
            Rating: rating,
            AppFeedback: feedback,
            RideMessageReport: message_report,
            UserPhotoReport: photo_report,
        }
    )


def watched_models() -> tuple[type, ...]:
    """**الجداولُ المراقَبة** — يقرؤها الحارسُ الذي يمنع `update()` على حالٍ مراقَبة."""
    install()
    return tuple(_HANDLERS)


def collect(session: Session) -> list[Event]:
    """ما في هذا الـflush من أحداث — **منفصلٌ عن المستمع** ليُقاس وحدَه."""
    found: list[Event] = []
    for obj in list(session.new):
        handler = _HANDLERS.get(type(obj))
        if handler is not None:
            found.extend(handler(obj, True))
    for obj in list(session.dirty):
        handler = _HANDLERS.get(type(obj))
        if handler is not None and session.is_modified(obj, include_collections=False):
            found.extend(handler(obj, False))
    return found


def _after_flush(session: Session, _context: Any) -> None:
    try:
        found = collect(session)
    except Exception:  # pragma: no cover - لا يُسقط التقاطٌ معاملةً
        logger.exception("تعذّر التقاطُ نشاطٍ لإشعارات المالك")
        return
    if found:
        session.info.setdefault(_BUFFER, []).extend(found)


def _after_commit(session: Session) -> None:
    events = session.info.pop(_BUFFER, None)
    if not events or not ENABLED:
        return
    # **استثناءٌ هنا يصل من نادى `commit()`** — فرحلةٌ التزمت تُرَدّ خطأً لأن إشعاراً تعطّل. فيُبتلع
    try:
        ship(events)
    except Exception:
        logger.exception("تعذّر تسليمُ نشاطٍ لإشعارات المالك")


def _after_rollback(session: Session) -> None:
    session.info.pop(_BUFFER, None)


def ship(events: list[Event]) -> None:
    """**يُسلَّم ولا يُنتظر**: مهمّةٌ في حلقة التطبيق، أو نداءٌ مقطوعٌ في العامل — وفشلُهما سطرُ سجلٍّ لا غير."""
    payload = [json.dumps(item, ensure_ascii=False, separators=(",", ":")) for item in events]
    if not SYNC_SHIP:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            task = loop.create_task(_push_async(payload))
            _PENDING.add(task)
            task.add_done_callback(_PENDING.discard)
            return
    _push_sync(payload)


async def _push_async(payload: list[str]) -> None:
    from app.core.redis_client import get_redis_client

    try:
        redis = get_redis_client()
        async with redis.pipeline(transaction=False) as pipe:
            pipe.rpush(QUEUE_KEY, *payload)
            pipe.ltrim(QUEUE_KEY, -QUEUE_CAP, -1)
            await asyncio.wait_for(pipe.execute(), timeout=2)
    except Exception:
        logger.warning("تعذّر تسليمُ %d حدثاً لإشعارات المالك", len(payload), exc_info=True)


async def settle() -> None:
    """**ينتظر ما سُلِّم ولم يصل بعد** — للاختبارات وحدَها: التسليمُ لا يُنتظر في التطبيق، والاختبارُ يقرأ القائمةَ بعده."""
    while _PENDING:
        await asyncio.gather(*list(_PENDING), return_exceptions=True)


_sync_client: Any = None


def _push_sync(payload: list[str]) -> None:
    global _sync_client
    try:
        if _sync_client is None:
            import redis as redis_sync

            from app.core.config import settings

            _sync_client = redis_sync.Redis.from_url(
                settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5
            )
        pipe = _sync_client.pipeline(transaction=False)
        pipe.rpush(QUEUE_KEY, *payload)
        pipe.ltrim(QUEUE_KEY, -QUEUE_CAP, -1)
        pipe.execute()
    except Exception:
        logger.warning("تعذّر تسليمُ %d حدثاً لإشعارات المالك", len(payload), exc_info=True)


def install() -> None:
    """**يُنادى مرّةً لكلِّ عمليّة** — من `main.py` ومن العامل. وتكرارُه لا يُضاعف المستمع."""
    global _installed
    if _installed:
        return
    _install_handlers()
    event.listen(Session, "after_flush", _after_flush)
    event.listen(Session, "after_commit", _after_commit)
    event.listen(Session, "after_rollback", _after_rollback)
    _installed = True
