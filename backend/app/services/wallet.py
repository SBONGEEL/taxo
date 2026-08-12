"""دفتر المحفظة: الرصيد والقيود والتحويل (SPEC القسم 4/7/14).

**الرصيد يُحسب من القيود ولا يُخزَّن.** لا عمود رصيد في أي جدول، ولا كاش له:
مجموعُ عمودٍ في جدولٍ صغيرٍ مفهرس أرخص بكثير من احتمال أن يفترق رقمٌ مخزَّن
عن دفتره.

كل كتابة تمر بقفل استشاري على مستوى المعاملة لصاحب المحفظة. القراءة ثم الكتابة
لا يمكن أن تكونا ذرّيتين بغيره: `SELECT SUM(...)` لا يمنع قيداً متزامناً من
الدخول بين حسابِ الرصيد وكتابةِ الصف، فينتهي مسحوبان متزامنان برصيدٍ سالب أو
بـ `balance_after` كاذب. القفل يُحرَّر مع نهاية المعاملة تلقائياً (`xact`)،
فلا مسار خروج ينسى تحريره.

الـ commit مسؤولية الراوتر — تحويلٌ بقيدين لا يجوز أن يُثبَّت نصفه.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    FeatureDisabled,
    InsufficientBalance,
    InvalidInput,
    PermissionDenied,
    WalletFrozen,
    WalletLimitExceeded,
)
from app.models.enums import (
    CountryCode,
    FeatureKey,
    UserRole,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.user import User
from app.models.wallet import CREDIT_TYPES, DEBIT_TYPES, WalletTransaction
from app.services import settings_service
from app.services.pricing import round_money

# نوافذ منزلقة لا تقويمية: لا مِنطقة زمنية لكل دولة في النظام، ومنتصفُ ليلٍ
# بتوقيت UTC ليس منتصف ليل أحد. المنزلقة تحمي نفس المبلغ بلا هذا الالتباس.
TRANSFER_DAILY_WINDOW = timedelta(days=1)
TRANSFER_MONTHLY_WINDOW = timedelta(days=30)


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ المالك


def owner_type_for(user: User) -> WalletOwnerType:
    """أي المحفظتين هي — للركاب والكباتن وحدهم.

    لا محفظة لحساب admin أو support: هؤلاء يحرّكون محافظ غيرهم من اللوحة
    ولا محفظة لهم تُشحن أو يُسحب منها.
    """
    if user.role == UserRole.RIDER:
        return WalletOwnerType.RIDER
    if user.role == UserRole.DRIVER:
        return WalletOwnerType.DRIVER
    raise PermissionDenied("لا محفظة لهذا النوع من الحسابات")


def require_not_frozen(user: User) -> None:
    if user.wallet_frozen:
        raise WalletFrozen()


async def require_wallet_enabled(
    session: AsyncSession, country_code: CountryCode
) -> None:
    """شحنُ محفظةٍ لا يُدفع منها عبثٌ — والدفع منها خلف `wallet_enabled`.

    قراءةُ الرصيد والسجل لا تمر من هنا: رصيدٌ سابقٌ لإطفاء المفتاح يبقى
    مرئياً لصاحبه.
    """
    if not await settings_service.is_feature_enabled(
        session, country_code, FeatureKey.WALLET_ENABLED
    ):
        raise FeatureDisabled("المحفظة غير مفعّلة في بلدك")


async def require_transfer_enabled(
    session: AsyncSession, country_code: CountryCode
) -> None:
    if not await settings_service.is_feature_enabled(
        session, country_code, FeatureKey.WALLET_TRANSFER_ENABLED
    ):
        raise FeatureDisabled("التحويل بين المحافظ غير مفعّل في بلدك")


# ------------------------------------------------------------------- القفل


def _lock_key(owner_id: uuid.UUID) -> int:
    """مفتاح 64-bit مشتق من مُعرّف المالك.

    القفل الاستشاري يقبل عدداً صحيحاً لا UUID. الاشتقاق في بايثون لا عبر
    `hashtextextended` كي لا نعتمد على دالة داخلية في postgres. تصادمٌ
    نادرٌ بين محفظتين يعني انتظاراً زائداً لا خطأً.
    """
    digest = hashlib.blake2b(owner_id.bytes, digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


async def lock_wallet(session: AsyncSession, owner_id: uuid.UUID) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(_lock_key(owner_id))))


async def lock_wallets(session: AsyncSession, *owner_ids: uuid.UUID) -> None:
    """قفل عدة محافظ بترتيب ثابت — بغيره يتقابل تحويلان متعاكسان في جمود.

    **وعامٌّ لا خاصّ منذ المرحلة 12-و**: البقشيش عمليةٌ ثانية تمسّ محفظتين في
    معاملةٍ واحدة (راكبٌ وكبتن)، ودالةٌ خاصةٌ تُستدعى من خدمةٍ أخرى تُقرأ إذناً
    بتجاهل الترتيب — والترتيبُ هو كلُّ ما يمنع الجمود هنا.
    """
    for owner_id in sorted(set(owner_ids), key=lambda value: value.bytes):
        await lock_wallet(session, owner_id)


# اسمٌ قديم يبقى للمستدعين داخل هذا الملف
_lock_wallets = lock_wallets


# ------------------------------------------------------------------ القراءة


async def balance(
    session: AsyncSession, owner_id: uuid.UUID, owner_type: WalletOwnerType
) -> Decimal:
    """الرصيد = مجموع قيود المالك. لا مصدر آخر له."""
    total = await session.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
            WalletTransaction.owner_id == owner_id,
            WalletTransaction.owner_type == owner_type,
        )
    )
    return round_money(Decimal(total))


async def balance_of(session: AsyncSession, user: User) -> Decimal:
    return await balance(session, user.id, owner_type_for(user))


async def history(
    session: AsyncSession,
    owner_id: uuid.UUID,
    owner_type: WalletOwnerType,
    *,
    limit: int,
    offset: int,
    tx_type: WalletTransactionType | None = None,
) -> Sequence[WalletTransaction]:
    stmt = select(WalletTransaction).where(
        WalletTransaction.owner_id == owner_id,
        WalletTransaction.owner_type == owner_type,
    )
    if tx_type is not None:
        stmt = stmt.where(WalletTransaction.type == tx_type)

    # قيدا التحويل الواحد يحملان نفس `created_at` (زمن المعاملة)، فالمُعرّف
    # يكسر التعادل ليبقى الترتيب ثابتاً بين طلبين
    stmt = stmt.order_by(
        WalletTransaction.created_at.desc(), WalletTransaction.id.desc()
    )
    return (await session.scalars(stmt.limit(limit).offset(offset))).all()


async def find_by_idempotency_key(
    session: AsyncSession, owner_id: uuid.UUID, key: str
) -> WalletTransaction | None:
    return await session.scalar(
        select(WalletTransaction).where(
            WalletTransaction.owner_id == owner_id,
            WalletTransaction.idempotency_key == key,
        )
    )


# ------------------------------------------------------------------ الكتابة


def _validate_sign(tx_type: WalletTransactionType, amount: Decimal) -> None:
    """الإشارة يمليها النوع — قيد سحبٍ موجبٌ يزيد الرصيد بدل أن ينقصه."""
    if amount == 0:
        raise InvalidInput("مبلغ القيد لا يكون صفراً")
    if tx_type in CREDIT_TYPES and amount < 0:
        raise InvalidInput(f"القيد «{tx_type.value}» يجب أن يكون موجباً")
    if tx_type in DEBIT_TYPES and amount > 0:
        raise InvalidInput(f"القيد «{tx_type.value}» يجب أن يكون سالباً")


async def record(
    session: AsyncSession,
    *,
    owner: User,
    tx_type: WalletTransactionType,
    amount: Decimal,
    ride_id: uuid.UUID | None = None,
    reference: str | None = None,
    created_by: uuid.UUID | None = None,
    idempotency_key: str | None = None,
) -> WalletTransaction:
    """يضيف قيداً واحداً ويعيد الصف بعد flush.

    `amount` موقّعة: موجبة للإضافة وسالبة للخصم، ويُفحص توافقها مع النوع.
    """
    owner_type = owner_type_for(owner)
    amount = round_money(amount)
    _validate_sign(tx_type, amount)

    await lock_wallet(session, owner.id)

    if idempotency_key is not None:
        existing = await find_by_idempotency_key(session, owner.id, idempotency_key)
        if existing is not None:
            return existing

    balance_after = round_money(
        await balance(session, owner.id, owner_type) + amount
    )
    if balance_after < 0:
        raise InsufficientBalance()

    entry = WalletTransaction(
        owner_type=owner_type,
        owner_id=owner.id,
        type=tx_type,
        amount=amount,
        balance_after=balance_after,
        ride_id=ride_id,
        reference=reference,
        created_by=created_by,
        idempotency_key=idempotency_key,
    )
    session.add(entry)
    # الجلسة بلا autoflush: بدون هذا لا يرى مجموعُ القيد التالي هذا الصف
    await session.flush()
    return entry


# ---------------------------------------------------------------- التحويل


async def _transferred_since(
    session: AsyncSession, owner_id: uuid.UUID, since: datetime
) -> Decimal:
    """مجموع ما حوّله المرسل خلال نافذة — بالقيمة المطلقة (القيود سالبة)."""
    total = await session.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
            WalletTransaction.owner_id == owner_id,
            WalletTransaction.type == WalletTransactionType.TRANSFER_OUT,
            WalletTransaction.created_at >= since,
        )
    )
    return abs(round_money(Decimal(total)))


async def _check_transfer_limits(
    session: AsyncSession, sender: User, amount: Decimal
) -> None:
    limits = await settings_service.get_or_create_wallet_settings(
        session, sender.country_code
    )
    now = _now()

    # حدٌّ صفريٌّ يعني «لم تُضبط بعد» لا «ممنوع بمقدار صفر» — والفرق بينهما
    # هو الفرق بين رسالة مفهومة ورسالة تُحيّر المشرف الذي رفع المفتاح للتو
    if limits.transfer_daily_limit <= 0 or limits.transfer_monthly_limit <= 0:
        raise WalletLimitExceeded(
            "حدود التحويل لبلدك غير مضبوطة — راجع لوحة الإدارة"
        )

    daily = await _transferred_since(session, sender.id, now - TRANSFER_DAILY_WINDOW)
    if daily + amount > limits.transfer_daily_limit:
        raise WalletLimitExceeded(
            f"تجاوزت حد التحويل اليومي ({limits.transfer_daily_limit})"
        )

    monthly = await _transferred_since(
        session, sender.id, now - TRANSFER_MONTHLY_WINDOW
    )
    if monthly + amount > limits.transfer_monthly_limit:
        raise WalletLimitExceeded(
            f"تجاوزت حد التحويل الشهري ({limits.transfer_monthly_limit})"
        )


async def transfer(
    session: AsyncSession,
    *,
    sender: User,
    recipient: User,
    amount: Decimal,
    idempotency_key: str,
) -> WalletTransaction:
    """تحويل P2P بين محفظتي راكبين — قيدان في معاملة واحدة (SPEC القسم 7).

    يعيد قيد `transfer_out` للمرسل. راكب→راكب فقط في هذه المرحلة: محفظة
    الكبتن مصدرها أرباحه وسحبها يمر بالمحاسب، فلا تُغذّى ولا تُفرَّغ تحويلاً.
    """
    amount = round_money(amount)
    if amount <= 0:
        raise InvalidInput("مبلغ التحويل يجب أن يكون أكبر من صفر")
    if sender.id == recipient.id:
        raise InvalidInput("لا يمكن التحويل إلى نفسك")
    if sender.role != UserRole.RIDER or recipient.role != UserRole.RIDER:
        raise PermissionDenied("التحويل متاح بين محافظ الركاب فقط")
    if sender.country_code != recipient.country_code:
        # عملة كل دولة مختلفة، ولا سعر صرف في النظام
        raise InvalidInput("لا يمكن التحويل بين حسابين في دولتين مختلفتين")

    await require_transfer_enabled(session, sender.country_code)
    require_not_frozen(sender)
    if recipient.wallet_frozen:
        raise WalletFrozen("محفظة المستلم مجمّدة")
    if recipient.is_blocked:
        raise PermissionDenied("حساب المستلم محظور")

    # القفل قبل فحص التكرار: طلبان متزامنان بنفس المفتاح يتسلسلان هنا، فيجد
    # الثاني قيدَ الأول بدل أن يصطدم به عند القيد الفريد
    await _lock_wallets(session, sender.id, recipient.id)
    existing = await find_by_idempotency_key(session, sender.id, idempotency_key)
    if existing is not None:
        return existing

    await _check_transfer_limits(session, sender, amount)

    out_entry = await record(
        session,
        owner=sender,
        tx_type=WalletTransactionType.TRANSFER_OUT,
        amount=-amount,
        reference=recipient.phone,
        created_by=sender.id,
        idempotency_key=idempotency_key,
    )
    await record(
        session,
        owner=recipient,
        tx_type=WalletTransactionType.TRANSFER_IN,
        amount=amount,
        reference=sender.phone,
        created_by=sender.id,
    )
    return out_entry
