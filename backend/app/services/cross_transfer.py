"""**التحويلُ بين الدول** (أمرُ المالك ٢٠٢٦-١١-٢٢، `design/OWNER-2026-11-22-CROSS-TRANSFER.md`).

راكبٌ في دولةٍ يحوّل إلى راكبٍ في دولةٍ أخرى: **يُخصم من المرسل بعملته، ويصل المستلمَ بعملته بسعرٍ يضبطه المشرف**، ورسمٌ اختياريٌّ
نسبةً من المبلغ (الافتراضُ صفر). **والحسابُ كلُّه هنا** (§14) — الواجهةُ تعرض ما يُرسل إليها (`quote`) ولا تضرب سعراً.

**ثلاثةُ أبوابٍ تُغلقه، وكلُّها افتراضاً مغلقة**:
1. مفتاحُ `cross_country_transfer_enabled` **في دولتَي المرسل والمستلم معاً** — ومعه `wallet_transfer_enabled` في دولة المرسل؛
2. **سعرٌ مكتوبٌ لهذا الاتّجاه** في `fx_rates` — ولا سعرَ يُبذر؛
3. **حدّان غيرُ صفريّين** لدولة المرسل في `cross_transfer_limits`.

**والتحويلُ داخل الدولة لا يمرّ من هنا ولا يتغيّر** (`wallet.transfer` كما هو): أنواعُ قيوده غيرُ هذه، وحدودُه تُجمع من `transfer_out` وحدَه.

**ترتيبُ الأقفال**: قفلا المحفظتين الاستشاريّان مرتَّبين (`wallet.lock_wallets`) — آخرُ الترتيب المعتمد، ولا صفَّ يُقفل قبلهما.
**والحدُّ يُفحص بعد القفل**: تحويلان متزامنان من مرسلٍ واحدٍ يتسلسلان عليه، فلا يقرأ الثاني مجموعاً قبل أن يُكتب الأوّل.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.currency import amount_text, currency_for_country, round_to_currency, step_of
from app.core.exceptions import (
    Conflict,
    FeatureDisabled,
    InvalidInput,
    NotFound,
    PermissionDenied,
    WalletFrozen,
    WalletLimitExceeded,
)
from app.models.cross_transfer import CrossTransfer, CrossTransferLimit, FxRate
from app.models.enums import (
    AuditAction,
    CountryCode,
    Currency,
    FeatureKey,
    UserRole,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import audit, settings_service, wallet
from app.services.pricing import as_money

#: **أقصى رسم** — قيدُ القاعدة نفسُه (`fx_fee_percent_range`)
MAX_FEE_PERCENT = Decimal("20")


@dataclass(frozen=True)
class Quote:
    """ما يدفعه المرسلُ وما يصل المستلم — **محسوبٌ هنا ويُعرض كما هو**."""

    from_currency: Currency
    to_currency: Currency
    amount: Decimal
    fee: Decimal
    total: Decimal
    received: Decimal
    rate: Decimal
    fee_percent: Decimal
    rate_set_at: datetime


def is_cross(sender: User, recipient: User) -> bool:
    return CountryCode(sender.country_code) != CountryCode(recipient.country_code)


def mask_name(name: str | None) -> str:
    """**الاسمُ مخفيٌّ جزئيّاً** (أمرُ المالك): الاسمُ الأوّلُ كاملاً، **وما بعده حرفُه الأوّل ونقطة** — «محمد ع.».

    **ولمَ هنا لا في الواجهة**: الاسمُ الكاملُ لراكبٍ في دولةٍ أخرى لا يُرسل إلى من يجرّب أرقاماً من بلدٍ غير بلده — فإخفاؤه في
    المتصفّح يُبقيه في الردّ."""
    parts = (name or "").split()
    if not parts:
        return "—"
    return " ".join([parts[0], *(f"{part[0]}." for part in parts[1:])])


async def cross_enabled(session: AsyncSession, country_code: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(session, country_code, FeatureKey.CROSS_COUNTRY_TRANSFER)


async def require_cross_enabled(session: AsyncSession, sender: User, recipient_country: CountryCode) -> None:
    """**المفتاحُ في الدولتين معاً** — ورسالةٌ واحدةٌ لا تقول أيُّهما أُطفئ: دولةُ المستلم ليست ما يُكشف لمن يجرّب أرقاماً."""
    await wallet.require_transfer_enabled(session, sender.country_code)
    if not (await cross_enabled(session, sender.country_code) and await cross_enabled(session, recipient_country)):
        raise FeatureDisabled("التحويل إلى دولةٍ أخرى غير متاحٍ الآن")


async def get_rate(session: AsyncSession, source: Currency, target: Currency) -> FxRate | None:
    return await session.scalar(select(FxRate).where(FxRate.from_currency == source, FxRate.to_currency == target))


def _convert(amount: Decimal, rate: Decimal, target: Currency) -> Decimal:
    """**ما يصل مقرَّباً للأسفل إلى أصغر وحدةٍ في عملة المستلم** — لا يصل أكثرُ ممّا يغطّيه السعر، والفرقُ أصغرُ من وحدة."""
    return (amount * rate).quantize(step_of(target), rounding=ROUND_DOWN).quantize(Decimal("0.001"))


async def quote(session: AsyncSession, *, sender: User, recipient: User, amount: Decimal) -> Quote:
    """**عرضُ التحويل** — يفحص ما يفحصه التنفيذ (عدا الحدِّ والرصيد اللذين يُفحصان تحت القفل) ويحسب المبالغ."""
    _require_parties(sender, recipient)
    await require_cross_enabled(session, sender, CountryCode(recipient.country_code))

    amount = as_money(amount)
    if amount <= 0:
        raise InvalidInput("مبلغ التحويل يجب أن يكون أكبر من صفر", field="amount")
    from app.services import rounding

    await rounding.require_multiple_in(session, sender.country_code, amount)

    source = currency_for_country(sender.country_code)
    target = currency_for_country(recipient.country_code)
    rate_row = await get_rate(session, source, target)
    if rate_row is None:
        raise InvalidInput("سعرُ الصرف لهذه الدولة لم يُضبط بعد — حاول لاحقاً", field="amount")

    fee_percent = Decimal(rate_row.fee_percent)
    fee = round_to_currency(amount * fee_percent / Decimal(100), source) if fee_percent > 0 else Decimal("0.000")
    received = _convert(amount, Decimal(rate_row.rate), target)
    if received <= 0:
        raise InvalidInput("المبلغُ أصغرُ من أن يصل شيءٌ بعد التحويل — زِد المبلغ", field="amount")
    return Quote(
        from_currency=source,
        to_currency=target,
        amount=amount,
        fee=as_money(fee),
        total=as_money(amount + fee),
        received=received,
        rate=Decimal(rate_row.rate),
        fee_percent=fee_percent,
        rate_set_at=rate_row.set_at,
    )


def _require_parties(sender: User, recipient: User) -> None:
    """**شروطُ التحويل داخل الدولة نفسُها حرفاً** (`wallet.transfer`) — لا يرخو شيءٌ منها لأن المستلمَ في بلدٍ آخر."""
    from app.services import test_accounts, verification

    verification.require_usable_account(sender)
    verification.require_usable_account(recipient)
    test_accounts.require_real_money(sender, "حسابُ التجربة لا يحوّل رصيداً — رصيدُه «تصحيحُ تجربة» لا مالٌ حقيقيّ")
    test_accounts.require_real_money(recipient, "لا يُحوَّل رصيدٌ إلى حساب تجربة")
    if sender.id == recipient.id:
        raise InvalidInput("لا يمكن التحويل إلى نفسك")
    if not sender.has_role(UserRole.RIDER) or not recipient.has_role(UserRole.RIDER):
        raise PermissionDenied("التحويل متاح بين محافظ الركاب فقط")
    if not is_cross(sender, recipient):
        raise InvalidInput("هذا تحويلٌ داخل دولتك — يمرّ بالتحويل العاديّ")
    wallet.require_not_frozen(sender, WalletOwnerType.RIDER)
    if wallet.is_frozen(recipient, WalletOwnerType.RIDER):
        raise WalletFrozen("محفظة المستلم مجمّدة")
    if recipient.is_blocked:
        raise PermissionDenied("حساب المستلم محظور")


async def _sent_since(session: AsyncSession, sender: User, since: datetime) -> Decimal:
    total = await session.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
            WalletTransaction.owner_id == sender.id,
            WalletTransaction.type == WalletTransactionType.CROSS_TRANSFER_OUT,
            WalletTransaction.created_at >= since,
        )
    )
    return abs(as_money(Decimal(total)))


async def _check_limits(session: AsyncSession, sender: User, amount: Decimal) -> None:
    """**حدّا المرسل للتحويل بين الدول** — بعملته، على المبلغ المرسَل (بلا الرسم). **وصفرٌ = لم يُضبط فيُردّ**."""
    limits = await session.scalar(
        select(CrossTransferLimit).where(CrossTransferLimit.country_code == CountryCode(sender.country_code))
    )
    if limits is None or limits.daily_limit <= 0 or limits.monthly_limit <= 0:
        raise WalletLimitExceeded("حدود التحويل إلى دولةٍ أخرى لم تُضبط بعد")
    currency = currency_for_country(sender.country_code)
    now = datetime.now(UTC)
    if await _sent_since(session, sender, now - wallet.TRANSFER_DAILY_WINDOW) + amount > limits.daily_limit:
        raise WalletLimitExceeded(
            f"تجاوزت حدَّ التحويل اليوميّ إلى دولةٍ أخرى ({amount_text(limits.daily_limit, currency)})"
        )
    if await _sent_since(session, sender, now - wallet.TRANSFER_MONTHLY_WINDOW) + amount > limits.monthly_limit:
        raise WalletLimitExceeded(
            f"تجاوزت حدَّ التحويل الشهريّ إلى دولةٍ أخرى ({amount_text(limits.monthly_limit, currency)})"
        )


async def transfer(
    session: AsyncSession,
    *,
    sender: User,
    recipient: User,
    amount: Decimal,
    idempotency_key: str,
    expected_received: Decimal | None = None,
) -> tuple[WalletTransaction, CrossTransfer]:
    """**التنفيذ** — ثلاثةُ قيودٍ في معاملةٍ واحدة (المرسَل، والرسمُ إن وُجد، والواصل)، وصفُّ `cross_transfers`، وقيدُ تدقيق.

    **`expected_received`** ما عرضته ورقةُ التأكيد: إن تغيّر السعرُ بين العرض والضغط يُردّ ٤٠٩ — **فلا يصل المستلمَ غيرُ ما رآه المرسل**.
    """
    await quote(session, sender=sender, recipient=recipient, amount=amount)  # الفحوصُ كلُّها قبل القفل

    await wallet.lock_wallets(session, sender.id, recipient.id)
    existing = await wallet.find_by_idempotency_key(session, sender.id, idempotency_key)
    if existing is not None:
        record = await session.scalar(select(CrossTransfer).where(CrossTransfer.out_transaction_id == existing.id))
        if record is None:
            raise Conflict("هذا المفتاحُ استُعمل لعمليةٍ أخرى")
        return existing, record

    # **السعرُ يُقرأ ثانيةً تحت القفل** — ما يُكتب في الدفتر هو ما يُقرأ الآن، لا ما قُرئ قبل الانتظار
    offer = await quote(session, sender=sender, recipient=recipient, amount=amount)
    if expected_received is not None and as_money(expected_received) != offer.received:
        raise Conflict("تغيّر سعرُ الصرف — راجعِ المبلغَ الواصلَ وأكِّد من جديد")
    await _check_limits(session, sender, offer.amount)

    reference_out = f"{recipient.phone} @{offer.rate.normalize()}"[:120]
    out_entry = await wallet.record(
        session,
        owner=sender,
        owner_type=WalletOwnerType.RIDER,
        tx_type=WalletTransactionType.CROSS_TRANSFER_OUT,
        amount=-offer.amount,
        reference=reference_out,
        created_by=sender.id,
        idempotency_key=idempotency_key,
    )
    fee_entry = None
    if offer.fee > 0:
        fee_entry = await wallet.record(
            session,
            owner=sender,
            owner_type=WalletOwnerType.RIDER,
            tx_type=WalletTransactionType.CROSS_TRANSFER_FEE,
            amount=-offer.fee,
            reference=f"{offer.fee_percent.normalize()}%",
            created_by=sender.id,
        )
    in_entry = await wallet.record(
        session,
        owner=recipient,
        owner_type=WalletOwnerType.RIDER,
        tx_type=WalletTransactionType.CROSS_TRANSFER_IN,
        amount=offer.received,
        reference=f"{sender.phone} @{offer.rate.normalize()}"[:120],
        created_by=sender.id,
    )
    row = CrossTransfer(
        sender_id=sender.id,
        recipient_id=recipient.id,
        from_currency=offer.from_currency,
        to_currency=offer.to_currency,
        amount=offer.amount,
        fee=offer.fee,
        received=offer.received,
        rate=offer.rate,
        fee_percent=offer.fee_percent,
        rate_set_at=offer.rate_set_at,
        out_transaction_id=out_entry.id,
        in_transaction_id=in_entry.id,
        fee_transaction_id=fee_entry.id if fee_entry is not None else None,
    )
    session.add(row)
    await session.flush()
    await audit.record(
        session,
        actor=sender,
        action=AuditAction.CREATE,
        entity_type="cross_transfer",
        entity_id=row.id,
        details={
            "from_country": CountryCode(sender.country_code).value,
            "to_country": CountryCode(recipient.country_code).value,
            "amount": str(offer.amount),
            "fee": str(offer.fee),
            "received": str(offer.received),
            "rate": str(offer.rate),
            "fee_percent": str(offer.fee_percent),
            "rate_set_at": offer.rate_set_at.isoformat(),
        },
    )
    return out_entry, row


# --------------------------------------------------------------- اللوحة


def all_pairs() -> list[tuple[Currency, Currency]]:
    """**الاتّجاهاتُ الستّة** — كلُّ عملتين بالاتّجاهين، بترتيبٍ ثابت."""
    currencies = [Currency.LYD, Currency.JOD, Currency.DZD]
    return [(a, b) for a in currencies for b in currencies if a is not b]


async def set_rate(
    session: AsyncSession, *, actor: User, source: Currency, target: Currency, rate: Decimal, fee_percent: Decimal
) -> FxRate:
    """**يضبطه المشرفُ وحدَه من اللوحة** — بتاريخ ضبطه ومن ضبطه، وقيدُ تدقيقٍ بما كان وما صار."""
    if source is target:
        raise InvalidInput("العملتان متطابقتان", field="to_currency")
    if rate <= 0:
        raise InvalidInput("السعرُ أكبرُ من صفر", field="rate")
    if fee_percent < 0 or fee_percent > MAX_FEE_PERCENT:
        raise InvalidInput(f"الرسمُ بين 0 و{MAX_FEE_PERCENT.normalize()}٪", field="fee_percent")
    rate = rate.quantize(Decimal("0.00000001"))
    fee_percent = fee_percent.quantize(Decimal("0.01"))
    row = await get_rate(session, source, target)
    before = None if row is None else {"rate": str(row.rate), "fee_percent": str(row.fee_percent)}
    now = datetime.now(UTC)
    if row is None:
        row = FxRate(from_currency=source, to_currency=target, rate=rate, fee_percent=fee_percent, set_at=now, set_by=actor.id)
        session.add(row)
    else:
        row.rate, row.fee_percent, row.set_at, row.set_by = rate, fee_percent, now, actor.id
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.CREATE if before is None else AuditAction.UPDATE,
        entity_type="fx_rate",
        entity_id=row.id,
        details={"pair": f"{source.value}->{target.value}"},
        changes={"before": before or {}, "after": {"rate": str(rate), "fee_percent": str(fee_percent)}},
    )
    return row


async def list_limits(session: AsyncSession) -> list[CrossTransferLimit]:
    return list((await session.scalars(select(CrossTransferLimit).order_by(CrossTransferLimit.country_code))).all())


async def set_limits(
    session: AsyncSession, *, actor: User, country_code: CountryCode, daily: Decimal, monthly: Decimal
) -> CrossTransferLimit:
    daily, monthly = as_money(daily), as_money(monthly)
    if daily < 0 or monthly < 0:
        raise InvalidInput("الحدُّ لا يكون سالباً", field="daily_limit")
    if daily > 0 and monthly > 0 and daily > monthly:
        raise InvalidInput("الحدُّ اليوميّ لا يتجاوز الشهريّ", field="daily_limit")
    row = await session.scalar(select(CrossTransferLimit).where(CrossTransferLimit.country_code == country_code))
    before = None if row is None else {"daily_limit": str(row.daily_limit), "monthly_limit": str(row.monthly_limit)}
    if row is None:
        row = CrossTransferLimit(country_code=country_code, daily_limit=daily, monthly_limit=monthly)
        session.add(row)
    else:
        row.daily_limit, row.monthly_limit = daily, monthly
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.CREATE if before is None else AuditAction.UPDATE,
        entity_type="cross_transfer_limit",
        entity_id=row.id,
        details={"country_code": country_code.value},
        changes={"before": before or {}, "after": {"daily_limit": str(daily), "monthly_limit": str(monthly)}},
    )
    return row


async def find_recipient_anywhere(session: AsyncSession, normalized_phone: str) -> User:
    """راكبٌ بحساب `taxo` برقمٍ مُطبَّع — **أيّاً كانت دولتُه**؛ و٤٠٤ واحدةٌ لكلِّ غياب (قاعدةُ `_resolve_rider`)."""
    from app.models.enums import AccountKind

    recipient = await session.scalar(
        select(User).where(User.phone == normalized_phone, User.account_kind == AccountKind.TAXO)
    )
    if recipient is None or not recipient.has_role(UserRole.RIDER):
        raise NotFound("لا يوجد حساب بهذا الرقم")
    return recipient
