"""حذفُ الحساب حذفاً حقيقياً بعد مهلة — **البابُ الوحيدُ الذي يكتب حالَه** (SPEC §59).

قرارُ المالك (٢٠٢٦-٠٩-٢٩): طلبٌ ← مهلةُ ٣٠ يوماً يُتراجع فيها بالدخول ← تجهيلٌ
**يمحو كلَّ ما يعرّف الشخص ويُبقي سجلّاتِ الرحلات والمال بلا اسمه**.

## ثلاثةُ أبواب، وترتيبُ أقفالها واحد

    صفُّ `users`  ←  صفُّ `drivers`  ←  قفلُ المحفظة الاستشاريّ

**يُدرج في الترتيب القائم ولا يُخترع** (`CLAUDE.md`): الطلبُ والاستعادةُ
والتجهيلُ كلُّها تأخذه بهذا التتابع، **ولا بابَ منها يأخذ قفلَ رحلةٍ أو دفعة**.

## والمالُ لا يُمسّ — **يُقرأ تحت القفل ويُؤجِّل**

- **الدفترُ لا يُعدَّل**: رصيدٌ أقرّ صاحبُه بضياعه يبقى في الدفتر لصفٍّ مجهول.
- **وحسابٌ عليه مالٌ أو مانعٌ لا يُجهَّل**: يُؤجَّل، ويُكتب السبب، ويُنبَّه
  المشرف مرّةً عند تغيّر السبب لا كلَّ ساعة.
- **وما يدخل بعد التجهيل يُرفض في `wallet.record`** نفسِه تحت قفل المحفظة —
  فالشحنُ الذي يسابق التجهيلَ إمّا يسبقه فيؤجّله، وإمّا يلحقه فيُرفض.

## وما لا يفعله — يُقال

**لوحةُ المركبة لا تُمسّ** (قرارُ المالك في §59-ز رقم ٢، ومقيسٌ ٢٠٢٦-٠٩-٢٩):
الرحلةُ **لا تحفظ نسخةً منها** — سجلُّ الراكب يقرؤها حيّةً من صفِّ المركبة
(`ride_log.plate_of`) — فمحوُها من الصفِّ الحيِّ يمحوها من سجلِّ الركّاب،
**والقرارُ أن تبقى هناك كما هي**. فتبقى حتى يُقرَّر حفظُ نسخةٍ على الرحلة.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.currency import currency_for_country
from app.core.exceptions import (
    AccountClosed,
    Conflict,
    DeletionBalanceUnacknowledged,
    DeletionBlocked,
    NotFound,
    PermissionDenied,
)
from app.core.security import hash_password
from app.models.booking import RideBooking
from app.models.deactivation import DeactivationRequest
from app.models.device import DeviceToken
from app.models.driver import Driver, DriverDocument
from app.models.enums import (
    BookingStatus,
    DriverStatus,
    FeatureKey,
    ProviderOrderStatus,
    TopupRequestStatus,
    UserRole,
    WalletOwnerType,
    WithdrawalStatus,
)
from app.models.notification import NotificationDelivery, UserNotification
from app.models.payment import SavedCard
from app.models.photo_report import UserPhotoReport
from app.models.place import SavedPlace
from app.models.provider_order import ProviderOrder
from app.models.rating import Rating
from app.models.totp import UserRecoveryCode, UserTotp
from app.models.user import User
from app.models.wallet import WalletTopupRequest, WithdrawalRequest
from app.services import deactivation, settings_service, wallet
from app.services.pricing import round_money

logger = logging.getLogger(__name__)

#: **المهلة** — قرارُ المالك، ومكتوبةٌ في النصِّ الذي يقرؤه صاحبُ الحساب
GRACE = timedelta(days=30)

#: الاسمُ بعد التجهيل — يظهر في شاهد رحلة الطرف الآخر مكانَ الاسم
DELETED_NAME = "حساب محذوف"

#: **أسبابُ التأجيل رموزاً** — والنصُّ في اللوحة. وموانعُ الطلب منها أيضاً.
DEFER_RIDER_BALANCE = "rider_balance_changed"
DEFER_DRIVER_BALANCE = "driver_balance"
DEFER_PENDING_MONEY = "pending_money"

_STAFF = frozenset({UserRole.ADMIN, UserRole.SUPPORT})


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ القراءة


async def balances(session: AsyncSession, user_id: uuid.UUID) -> tuple[Decimal, Decimal]:
    """(رصيدُ محفظة الراكب، رصيدُ محفظة الكبتن) — **من الدفتر وحدَه**."""
    return (
        await wallet.balance(session, user_id, WalletOwnerType.RIDER),
        await wallet.balance(session, user_id, WalletOwnerType.DRIVER),
    )


async def _pending_money(
    session: AsyncSession, user_id: uuid.UUID, driver: Driver | None
) -> bool:
    """شحنٌ أو سحبٌ أو طلبُ مزوّدٍ لم يُحسم — **مالٌ في الطريق لا يُترك بلا صاحب**."""
    if await session.scalar(
        select(WalletTopupRequest.id)
        .where(
            WalletTopupRequest.owner_id == user_id,
            WalletTopupRequest.status == TopupRequestStatus.PENDING,
        )
        .limit(1)
    ):
        return True
    if await session.scalar(
        select(ProviderOrder.id)
        .where(
            ProviderOrder.user_id == user_id,
            ProviderOrder.status == ProviderOrderStatus.CREATED,
        )
        .limit(1)
    ):
        return True
    if driver is not None and await session.scalar(
        select(WithdrawalRequest.id)
        .where(
            WithdrawalRequest.driver_id == driver.id,
            WithdrawalRequest.status.in_(
                (WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED)
            ),
        )
        .limit(1)
    ):
        return True
    return False


async def state(session: AsyncSession, user: User) -> dict:
    """ما تعرضه شاشةُ الحذف — **سؤالٌ واحدٌ بجوابٍ واحد**."""
    rider_balance, driver_balance = await balances(session, user.id)
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    return {
        "requested_at": user.deletion_requested_at,
        "due_at": user.deletion_due_at,
        "deferred_reason": user.deletion_deferred_reason,
        "blockers": await deactivation.blockers(
            session, user, rider_balance_blocks=False
        ),
        "rider_balance": rider_balance,
        "driver_balance": driver_balance,
        "forfeit_amount": user.deletion_forfeit_amount,
        "currency": currency_for_country(user.country_code).value,
        "is_driver": driver is not None,
        # **يظهر خيارُ التحويل حين يكون مفعّلاً في دولته وحدَه** (قرارُ المالك)
        "transfer_enabled": await settings_service.is_feature_enabled(
            session, user.country_code, FeatureKey.WALLET_TRANSFER_ENABLED
        ),
    }


# ------------------------------------------------------------------ الأقفال
#
# **`FOR NO KEY UPDATE` لا `FOR UPDATE`** — وُجد بالاختبار لا بالقراءة (٢٠٢٦-٠٩-٢٩):
# كلُّ قيدٍ في الدفتر يشير إلى `users` بمفتاحٍ أجنبيّ، **وإدراجُه يأخذ `KEY SHARE`
# على صفِّ المستخدم**. و`FOR UPDATE` يتعارض معه، فكان الشحنُ الذي يمسك قفلَ المحفظة
# وينتظر صفَّ المستخدم يقابل طلبَ الحذف الذي يمسك صفَّ المستخدم وينتظر قفلَ المحفظة
# — **جمود**، وكانت المهمّةُ تتخطّى الصفَّ بـ`SKIP LOCKED` كلّما أُدرج له قيد.
# **ولا نغيّر مفتاحاً قطّ**، فالأضعفُ هو الصحيح: يمنع كاتباً ثانياً ولا يمنع إدراجاً
# يشير إلى الصفّ. والشيءُ نفسُه لصفِّ الكبتن (`withdrawal_requests` تشير إليه).


async def _locked_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    if user is None:
        raise NotFound("الحساب غير موجود")
    return user


async def _locked_driver(session: AsyncSession, user_id: uuid.UUID) -> Driver | None:
    return await session.scalar(
        select(Driver)
        .where(Driver.user_id == user_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )


# ------------------------------------------------------------------ الطلب


async def request(
    session: AsyncSession,
    redis: Redis,
    *,
    user: User,
    forfeit_amount: Decimal | None,
) -> User:
    """يجدول الحذفَ بعد المهلة — والـcommit للمستدعي، **وإلغاءُ الجلسات بعده**.

    **والرصيدُ يُقرأ تحت قفل المحفظة**: إقرارٌ بمبلغٍ قُرئ قبل شحنٍ لم يُثبَّت
    بعد إقرارٌ بغير ما في المحفظة.
    """
    if user.has_role(*_STAFF):
        raise PermissionDenied("حسابات الإدارة لا تُحذف من التطبيق")

    locked = await _locked_user(session, user.id)
    if locked.deleted_at is not None or locked.deactivated_at is not None:
        raise AccountClosed()
    if locked.deletion_due_at is not None:
        raise Conflict("طلبُ الحذف قائمٌ بالفعل")
    driver = await _locked_driver(session, locked.id)

    found = await deactivation.blockers(session, locked, rider_balance_blocks=False)
    if found:
        raise DeletionBlocked(blockers=found)

    # **الحجوزاتُ القادمةُ تُلغى بلا رسم — ومن بابها نفسِه**، وقبل قفل المحفظة:
    # **قفلُ المحفظة آخرُ الأقفال دائماً**. ورفضٌ بعدها يُرجع المعاملةَ كلَّها.
    from app.services import bookings

    upcoming = (
        await session.scalars(
            select(RideBooking).where(
                RideBooking.rider_id == locked.id,
                RideBooking.status == BookingStatus.PENDING,
            )
        )
    ).all()
    for booking in upcoming:
        await bookings.cancel(session, booking=booking, actor=locked)

    # **ولا إشعارَ في المهلة**: رموزُ الأجهزة تُمحى الآن لا يومَ التجهيل
    await session.execute(delete(DeviceToken).where(DeviceToken.user_id == locked.id))

    await wallet.lock_wallet(session, locked.id)
    rider_balance, _ = await balances(session, locked.id)
    acknowledged: Decimal | None = None
    if rider_balance > 0:
        # **المبلغُ كما هو لا أقلّ ولا أكثر** — والموافقةُ على غير ما في
        # المحفظة ليست موافقة
        if forfeit_amount is None or round_money(forfeit_amount) != rider_balance:
            raise DeletionBalanceUnacknowledged(balance=str(rider_balance))
        acknowledged = rider_balance

    now = _now()
    locked.deletion_requested_at = now
    locked.deletion_due_at = now + GRACE
    locked.deletion_forfeit_amount = acknowledged
    locked.deletion_deferred_reason = None
    locked.deletion_deferred_at = None

    if driver is not None:
        # **يخرج من التوزيع لحظةَ الطلب** — وحالُه قبلها تُحفظ فتعود إليها
        # الاستعادةُ لا إلى «معتمَد»: من كان موقوفاً يعود موقوفاً
        locked.deletion_driver_status = driver.status.value
        if driver.is_online:
            from app.services import drivers as drivers_service

            await drivers_service.go_offline(session, redis, driver)
        driver.status = DriverStatus.DEACTIVATED

    await session.flush()
    return locked


async def restore(session: AsyncSession, *, user: User) -> User:
    """**التراجعُ بالدخول** — فعلٌ صريحٌ لا أثرٌ جانبيٌّ لتسجيل الدخول."""
    locked = await _locked_user(session, user.id)
    if locked.deleted_at is not None:
        raise AccountClosed()
    if locked.deletion_due_at is None:
        raise NotFound("لا طلبَ حذفٍ قائم")
    driver = await _locked_driver(session, locked.id)

    # **يعود إلى ما كان عليه لا إلى «معتمَد»** — وإن غيّر مشرفٌ حالَه في
    # المهلة فقرارُه يبقى ولا تدهسه الاستعادة
    if (
        driver is not None
        and driver.status is DriverStatus.DEACTIVATED
        and locked.deletion_driver_status
    ):
        driver.status = DriverStatus(locked.deletion_driver_status)

    locked.deletion_requested_at = None
    locked.deletion_due_at = None
    locked.deletion_forfeit_amount = None
    locked.deletion_driver_status = None
    locked.deletion_deferred_reason = None
    locked.deletion_deferred_at = None
    await session.flush()
    return locked


# ------------------------------------------------------------------ التجهيل


@dataclass
class Outcome:
    user_id: uuid.UUID
    anonymized: bool
    deferred_reason: str | None = None
    #: السببُ تغيّر في هذه الدورة — **فيُنبَّه المشرف مرّةً لا كلَّ ساعة**
    newly_deferred: bool = False
    #: ملفّاتٌ تُحذف **بعد الالتزام** لا قبله
    files: list[str] = field(default_factory=list)
    name: str = ""


async def _defer_reason(
    session: AsyncSession, user: User, driver: Driver | None
) -> str | None:
    """أوّلُ ما يمنع التجهيلَ الآن — **تحت الأقفال كلِّها**."""
    found = await deactivation.blockers(session, user, rider_balance_blocks=False)
    if found:
        return found[0]
    if await _pending_money(session, user.id, driver):
        return DEFER_PENDING_MONEY
    rider_balance, driver_balance = await balances(session, user.id)
    if rider_balance != (user.deletion_forfeit_amount or Decimal("0.000")):
        return DEFER_RIDER_BALANCE
    if driver_balance != 0:
        return DEFER_DRIVER_BALANCE
    return None


async def process_one(
    session: AsyncSession, user_id: uuid.UUID, *, now: datetime | None = None
) -> Outcome | None:
    """يأخذ حساباً حلّ موعدُه **ويجهّله أو يؤجّله — ولا يُثبّت**.

    `None` حين لم يعد مستحقاً أو يمسكه عاملٌ آخر (`SKIP LOCKED`): عاملان لا
    يعالجان صفّاً واحداً مرّتين.
    """
    now = now or _now()
    user = await session.scalar(
        select(User)
        .where(
            User.id == user_id,
            User.deletion_due_at.is_not(None),
            User.deletion_due_at <= now,
            User.deleted_at.is_(None),
        )
        .with_for_update(skip_locked=True, key_share=True)
        .execution_options(populate_existing=True)
    )
    if user is None:
        return None
    driver = await _locked_driver(session, user.id)
    await wallet.lock_wallet(session, user.id)

    reason = await _defer_reason(session, user, driver)
    if reason is not None:
        changed = reason != user.deletion_deferred_reason
        if changed:
            user.deletion_deferred_reason = reason
            user.deletion_deferred_at = now
        await session.flush()
        return Outcome(
            user_id=user.id,
            anonymized=False,
            deferred_reason=reason,
            newly_deferred=changed,
            name=user.name,
        )

    files = await _anonymize(session, user, driver, now)
    return Outcome(user_id=user.id, anonymized=True, files=files, name=DELETED_NAME)


async def _anonymize(
    session: AsyncSession, user: User, driver: Driver | None, now: datetime
) -> list[str]:
    """**التجهيلُ جدولاً جدولاً كما في §59-هـ** — ويعيد الملفّاتِ لتُحذف بعد الالتزام.

    **ولا يمسّ**: `wallet_transactions` · `payments` · `tips` · `provider_orders` ·
    `driver_subscriptions` · `referrals` · `ride_cancellation_charges` ·
    `driver_advances` · `driver_debts` · `wallet_topup_requests` ·
    `withdrawal_requests` · `admin_audit_logs` · `user_policy_consents` ·
    **و`vehicles`** — قراراتُ المالك الثلاثة (المال كما هو، واللوحةُ حتى يُقرَّر).
    """
    files: list[str] = []
    uid = user.id

    # ── الكبتن: ما يعرّفه على صفِّه، ووثائقُه وملفّاتُها
    if driver is not None:
        documents = (
            await session.scalars(
                select(DriverDocument).where(DriverDocument.driver_id == driver.id)
            )
        ).all()
        files.extend(document.file_path for document in documents)
        await session.execute(
            delete(DriverDocument).where(DriverDocument.driver_id == driver.id)
        )
        driver.cliq_alias = None

    # ── شخصيٌّ محضٌ لا يشهد على معاملة: يُحذف
    for model, column in (
        (DeviceToken, DeviceToken.user_id),
        (SavedCard, SavedCard.user_id),
        (SavedPlace, SavedPlace.user_id),
        (UserTotp, UserTotp.user_id),
        (UserRecoveryCode, UserRecoveryCode.user_id),
        (UserNotification, UserNotification.user_id),
        (NotificationDelivery, NotificationDelivery.user_id),
        (UserPhotoReport, UserPhotoReport.subject_id),
    ):
        await session.execute(delete(model).where(column == uid))

    # ── محادثةُ الرحلة ومكالمتُها (SPEC §٦٦، `design/APPROVALS-DATA.md` §١ «وحذفُ الحساب»): **رسائلُه تُحذف** — إلا ما كان تحت
    # بلاغٍ مفتوحٍ فيبقى حتى يُعالَج ثمّ يحذفه الكنس · **وسطرُه في بلاغاته يُمحى** · **وصوتُه في كلِّ تسجيلٍ كان طرفاً فيه يُمحى**
    # (والملفّاتُ بعد الالتزام كالوثائق). **وسطرُ المكالمة يبقى** — من اتصل بمن ومتى، بلا اسمه بعد التجهيل — حتى يحلّ موعدُه
    from app.services import ride_calls, trip_chat

    await trip_chat.erase_for_account(session, uid)
    files.extend(await ride_calls.erase_recordings_for_account(session, uid))

    # ── نصٌّ حرٌّ كتبه: يُمحى، **والدرجةُ تبقى** — منها متوسّطُ كبتنٍ آخر
    await session.execute(
        update(Rating).where(Rating.rater_id == uid).values(comment=None)
    )
    await session.execute(
        update(DeactivationRequest)
        .where(DeactivationRequest.user_id == uid)
        .values(reason=None)
    )

    # ── رحلاتُه **راكباً**: عنوانُ بيته وعمله ومسارُ حركته
    #
    # **والنقاطُ تُقرَّب لا تُمحى**: `NOT NULL`، والدقيقُ مع الوقت يعيد التعريف
    # — ومنزلتان (~١ كم) لا تدلّان على باب. **ورحلاتُه كبتناً تبقى هندستُها**:
    # هي رحلةُ راكبٍ آخرَ وسجلُّه.
    params = {"uid": uid}
    await session.execute(
        text(
            "UPDATE rides SET pickup_address = NULL, dropoff_address = NULL, "
            "route_polyline = NULL, route_steps = NULL, "
            "pickup_point = ST_SnapToGrid(pickup_point::geometry, 0.01)::geography, "
            "dropoff_point = ST_SnapToGrid(dropoff_point::geometry, 0.01)::geography "
            "WHERE rider_id = :uid"
        ),
        params,
    )
    await session.execute(
        text(
            "UPDATE ride_stops SET address = NULL, "
            "point = ST_SnapToGrid(point::geometry, 0.01)::geography "
            "WHERE ride_id IN (SELECT id FROM rides WHERE rider_id = :uid)"
        ),
        params,
    )
    await session.execute(
        text(
            "DELETE FROM ride_route_points "
            "WHERE ride_id IN (SELECT id FROM rides WHERE rider_id = :uid)"
        ),
        params,
    )
    await session.execute(
        text(
            "UPDATE ride_bookings SET pickup_address = NULL, dropoff_address = NULL, "
            "pickup_point = ST_SnapToGrid(pickup_point::geometry, 0.01)::geography, "
            "dropoff_point = ST_SnapToGrid(dropoff_point::geometry, 0.01)::geography "
            "WHERE rider_id = :uid"
        ),
        params,
    )

    # ── الصفُّ نفسُه: يبقى (`rides` و`wallet_transactions` تشير إليه) ويسقط ما يعرّفه
    if user.photo_path:
        files.append(user.photo_path)
    user.name = DELETED_NAME
    user.phone = None
    user.email = None
    user.phone_verified_at = None
    user.email_verified_at = None
    user.photo_path = None
    user.photo_hidden_at = None
    user.gender = None
    user.gender_verified_at = None
    user.referral_code = None
    user.gender_mismatch_reports = 0
    # **لا دخولَ بعدها** — كلمةٌ لا يعرفها أحد، لا فراغٌ يُقرأ «بلا كلمة»
    user.password_hash = hash_password(secrets.token_urlsafe(48))
    user.deletion_deferred_reason = None
    user.deletion_deferred_at = None
    # **ومعه `deactivated_at`**: فتردّه كلُّ الأبواب القائمة بلا سطرٍ جديد —
    # التجديدُ والتبديلُ والمقبسُ والتحقّقُ الثنائيّ
    user.deactivated_at = now
    user.deleted_at = now
    await session.flush()
    return files


async def anonymize_due(
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis,
    *,
    now: datetime | None = None,
    limit: int = 200,
) -> dict[str, int]:
    """**المهمّةُ الدورية** — معاملةٌ لكلِّ حساب، والملفّاتُ بعد الالتزام.

    **والتنبيهُ بعد الالتزام**: إشعارٌ عن تأجيلٍ لم يُثبَّت يقول ما لم يقع.
    """
    from app.core import storage
    from app.services import notifications

    now = now or _now()
    async with session_factory() as session:
        ids = (
            await session.scalars(
                select(User.id)
                .where(
                    User.deletion_due_at.is_not(None),
                    User.deletion_due_at <= now,
                    User.deleted_at.is_(None),
                )
                .order_by(User.deletion_due_at)
                .limit(limit)
            )
        ).all()

    counts = {"anonymized": 0, "deferred": 0, "skipped": 0}
    for user_id in ids:
        async with session_factory() as session:
            outcome = await process_one(session, user_id, now=now)
            if outcome is None:
                counts["skipped"] += 1
                continue
            await session.commit()

        if outcome.anonymized:
            counts["anonymized"] += 1
            for relative_path in outcome.files:
                await storage.delete(relative_path)
            logger.info("جُهِّل حسابٌ بعد مهلة الحذف: %s", user_id)
            continue

        counts["deferred"] += 1
        if outcome.newly_deferred:
            async with session_factory() as session:
                await notifications.publish_deletion_deferred(
                    session,
                    redis,
                    subject_user_id=outcome.user_id,
                    subject_name=outcome.name,
                    reason=outcome.deferred_reason or "",
                )
                await session.commit()
    return counts


# ------------------------------------------------------------------ اللوحة


async def pending_accounts(session: AsyncSession) -> list[User]:
    """الحساباتُ في المهلة ومواعيدُها — **والمؤجَّلةُ أوّلاً** لأنها تنتظر مشرفاً."""
    return list(
        (
            await session.scalars(
                select(User)
                .where(User.deletion_due_at.is_not(None), User.deleted_at.is_(None))
                .order_by(
                    User.deletion_deferred_reason.is_(None),
                    User.deletion_due_at,
                )
            )
        ).all()
    )
