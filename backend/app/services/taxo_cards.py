"""بطاقاتُ شحن TAXO (SPEC §٧٣-أ/٧، §٧٣-هـ المرحلة ٢) — التوليدُ والإلغاءُ والاستعمالُ والتقرير.

**الرمزُ لا يُخزَّن** (§٧٣-هـ/٢-١): تُخزَّن بصمتُه `HMAC-SHA256` بسرِّ `TAXO_CARD_CODE_PEPPER`، ويُعاد نصُّه **مرّةً لحظةَ التوليد** ثمّ لا يملكه
أحد. **وغيابُ السرّ يوقف التوليدَ والاستعمالَ معاً** (`503`) — لا احتياطَ صامتٌ لسرّ.

**والاستعمالُ مرّةً واحدةً بحارسين مستقلّين** (§٧٣-هـ/٢-٧): قفلُ صفِّ البطاقة قبل فحص حالها، **والفهرسُ الفريدُ لمرجع الدفعة** في نظام الدفع
(الرقمُ التسلسليُّ مرجعُها) — ومفتاحُ الدفتر ثالثٌ لصاحبه. **وترتيبُ الأقفال**: صفُّ البطاقة ← قفلُ المحفظة.

**والتخمين** (§٧٣-هـ/٢-٨): يُعدّ الخطأُ وحدَه لكلِّ حسابٍ ولكلِّ عنوان، **وبلوغُ السقف يكتب تنبيهاً تراه اللوحة** ويوقف المحاولاتِ حتى تنقضي النافذة.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import settings
from app.core.currency import currency_for_country, round_to_currency
from app.core.exceptions import (
    AppError,
    Conflict,
    FeatureDisabled,
    InvalidInput,
    InvalidStatusTransition,
    NotFound,
    RateLimited,
)
from app.models.enums import (
    AuditAction,
    CardShopPaymentMode,
    CountryCode,
    PaymentProviderKind,
    PaymentRequestPurpose,
    PaymentRequestStatus,
    TaxoCardBatchStatus,
    TaxoCardStatus,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.taxo_card import (
    CardBatch,
    CardDenomination,
    CardGuessAlert,
    CardShop,
    TaxoCard,
    TaxoCardSetting,
)
from app.models.user import User
from app.services import audit, cancellation, payment_requests, rounding, test_accounts, verification, wallet

#: **أبجديّةٌ بلا لَبس** — لا `0/O` ولا `1/I/L`: رمزٌ يُقرأ من ورقةٍ ويُكتب بإصبع
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 16
#: أكبرُ دفعةٍ في مرّة — ملفُّ طباعةٍ يُقرأ، وحدٌّ لما يُولَّد في معاملةٍ واحدة
MAX_QUANTITY = 5000


class CardsNotConfigured(AppError):
    """**لا سرَّ لبصمة الرموز** — لا تُصدر بطاقةٌ ولا تُستعمل (`503`): الميزةُ مبنيّةٌ والإعدادُ غائب، والمستخدمُ لا ذنبَ له."""

    status_code = 503
    code = "taxo_cards_not_configured"
    message = "بطاقاتُ الشحن غيرُ متاحةٍ الآن."


class CardCodeRejected(AppError):
    """**رمزٌ لا يشحن** — خطأٌ يُعدّ في سقف التخمين: غيرُ صحيح، أو مستعمَل، أو ملغًى."""

    status_code = 422
    code = "taxo_card_rejected"
    message = "الرمزُ غيرُ صحيح"


class CardNotUsableNow(Conflict):
    """**رمزٌ صحيحٌ في غير نافذته** — لم تبدأ بعد أو انتهت؛ **لا يُعدّ خطأً** فصاحبُه يملك بطاقةً حقيقيّة."""

    code = "taxo_card_not_usable_now"
    message = "لا تعمل هذه البطاقة الآن"


def _now() -> datetime:
    return datetime.now(UTC)


def _pepper() -> bytes:
    if not settings.taxo_card_code_pepper:
        raise CardsNotConfigured()
    return settings.taxo_card_code_pepper.encode()


def normalize_code(raw: str | None) -> str | None:
    """**الرمزُ كما يُقارن** — بلا مسافاتٍ ولا شرطاتٍ وبحروفٍ كبيرة؛ و`None` لما لا يكون رمزاً أصلاً."""
    if raw is None:
        return None
    code = "".join(ch for ch in raw.upper() if ch not in " -_\t")
    if len(code) != CODE_LENGTH or any(ch not in ALPHABET for ch in code):
        return None
    return code


def code_hash(code: str) -> str:
    return hmac.new(_pepper(), code.encode(), hashlib.sha256).hexdigest()


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def printed(code: str) -> str:
    """الرمزُ كما يُطبع — أربعاً أربعاً."""
    return "-".join(code[i : i + 4] for i in range(0, CODE_LENGTH, 4))


# ------------------------------------------------------------------ الإعدادات


@dataclass(frozen=True, slots=True)
class Limits:
    """**سقوفُ التخمين قيماً لا صفّاً** — تُقرأ قبل المحاولة وتُستعمل بعد التراجع عنها؛ وصفٌّ في جلسةٍ تراجعت يُقرأ منتهياً."""

    max_wrong_per_account: int
    max_wrong_per_ip: int
    window_minutes: int


async def limits_for(session: AsyncSession, country: CountryCode) -> Limits:
    """**سقوفُ التخمين** — من صفِّ السوق، وغيابُه افتراضُ الجدول نفسِه."""
    row = await session.scalar(select(TaxoCardSetting).where(TaxoCardSetting.country_code == country))
    if row is None:
        return Limits(max_wrong_per_account=5, max_wrong_per_ip=20, window_minutes=60)
    return Limits(row.max_wrong_per_account, row.max_wrong_per_ip, row.window_minutes)


async def save_limits(
    session: AsyncSession, *, actor: User, country: CountryCode, changes: dict[str, int]
) -> TaxoCardSetting:
    row = await session.scalar(
        select(TaxoCardSetting).where(TaxoCardSetting.country_code == country).with_for_update()
    )
    if row is None:
        row = TaxoCardSetting(country_code=country, max_wrong_per_account=5, max_wrong_per_ip=20, window_minutes=60)
        session.add(row)
    recorded = audit.apply_changes(row, changes)
    await session.flush()
    if recorded:
        await audit.record(
            session, actor=actor, action=AuditAction.UPDATE, entity_type="taxo_card_settings",
            details={"country_code": country.value}, changes=recorded,
        )
    return row


# ------------------------------------------------------------------ الفئاتُ والمحلّات


async def denominations(session: AsyncSession, country: CountryCode) -> list[CardDenomination]:
    stmt = select(CardDenomination).where(CardDenomination.country_code == country).order_by(CardDenomination.amount)
    return list((await session.scalars(stmt)).all())


async def add_denomination(
    session: AsyncSession, *, actor: User, country: CountryCode, amount: Decimal
) -> CardDenomination:
    """**فئةٌ يضعها المالك** — بخانات عملة سوقها (الدينارُ الجزائريُّ صحيح)، ولا تتكرّر."""
    amount = Decimal(amount)
    if amount <= 0:
        raise InvalidInput("قيمةُ الفئة أكبرُ من صفر", field="amount")
    rounding.require_precise(amount, currency_for_country(country), field="amount")
    exists = await session.scalar(
        select(CardDenomination.id).where(CardDenomination.country_code == country, CardDenomination.amount == amount)
    )
    if exists is not None:
        raise Conflict("هذه الفئةُ موجودةٌ في السوق")
    row = CardDenomination(country_code=country, amount=amount, is_active=True)
    session.add(row)
    await session.flush()
    await audit.record(
        session, actor=actor, action=AuditAction.CREATE, entity_type="card_denomination", entity_id=row.id,
        details={"country_code": country.value, "amount": str(amount)},
    )
    return row


async def set_denomination_active(
    session: AsyncSession, *, actor: User, denomination_id: uuid.UUID, active: bool
) -> CardDenomination:
    row = await session.get(CardDenomination, denomination_id, with_for_update=True)
    if row is None:
        raise NotFound("الفئةُ غيرُ موجودة")
    changes = audit.apply_changes(row, {"is_active": active})
    if changes:
        await audit.record(
            session, actor=actor, action=AuditAction.UPDATE, entity_type="card_denomination", entity_id=row.id,
            changes=changes,
        )
    return row


async def shops(session: AsyncSession, country: CountryCode) -> list[CardShop]:
    stmt = select(CardShop).where(CardShop.country_code == country).order_by(CardShop.is_active.desc(), CardShop.name)
    return list((await session.scalars(stmt)).all())


async def get_shop(session: AsyncSession, shop_id: uuid.UUID, *, for_update: bool = False) -> CardShop:
    row = await session.get(CardShop, shop_id, with_for_update=for_update)
    if row is None:
        raise NotFound("المحلُّ غيرُ موجود")
    return row


# ------------------------------------------------------------------ الدفعات


async def get_batch(session: AsyncSession, batch_id: uuid.UUID, *, for_update: bool = False) -> CardBatch:
    stmt = select(CardBatch).where(CardBatch.id == batch_id)
    if for_update:
        stmt = stmt.with_for_update(of=CardBatch).execution_options(populate_existing=True)
    row = await session.scalar(stmt)
    if row is None:
        raise NotFound("الدفعةُ غيرُ موجودة")
    return row


async def create_batch(
    session: AsyncSession,
    *,
    actor: User,
    country: CountryCode,
    denomination_id: uuid.UUID,
    quantity: int,
    shop_id: uuid.UUID | None,
    valid_from: datetime,
    expires_at: datetime,
) -> tuple[CardBatch, list[tuple[str, str]]]:
    """**دفعةٌ تُولَّد معاً** — وتعود رموزُها **مرّةً واحدةً** (`(الرقم، الرمز)`) لملفّ الطباعة، ولا تُخزَّن إلا بصماتُها.

    **وتجمّد الدفعةُ** فئتَها وخصمَ المحلّ ونمطَ دفعه لحظةَ الإصدار — فتعديلُ المحلّ بعدها لا يغيّر حسابَ ما سُلِّم له.
    """
    _pepper()  # **قبل كلِّ شيء**: لا دفعةَ تُكتب ثمّ تتعذّر بصماتُها
    if not 1 <= quantity <= MAX_QUANTITY:
        raise InvalidInput(f"عددُ البطاقات بين 1 و{MAX_QUANTITY}", field="quantity")
    if expires_at <= valid_from:
        raise InvalidInput("انتهاءُ الصلاحية بعد بدء العمل", field="expires_at")
    if expires_at <= _now():
        raise InvalidInput("تاريخُ الانتهاء مضى", field="expires_at")

    denomination = await session.get(CardDenomination, denomination_id)
    if denomination is None or denomination.country_code != country or not denomination.is_active:
        raise InvalidInput("الفئةُ غيرُ متاحةٍ في هذا السوق", field="denomination_id")
    shop: CardShop | None = None
    if shop_id is not None:
        shop = await get_shop(session, shop_id)
        if shop.country_code != country or not shop.is_active:
            raise InvalidInput("المحلُّ غيرُ متاحٍ في هذا السوق", field="shop_id")

    # **رقمُ الدفعة متتابعٌ في سوقها** — قفلٌ استشاريٌّ للسوق فلا تأخذ دفعتان متزامنتان الرقمَ نفسَه
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"card_batch:{country.value}"})
    number = (await session.scalar(
        select(func.coalesce(func.max(CardBatch.number), 0)).where(CardBatch.country_code == country)
    )) + 1

    currency = currency_for_country(country)
    batch = CardBatch(
        country_code=country,
        currency=currency,
        number=number,
        shop_id=shop.id if shop else None,
        amount=denomination.amount,
        quantity=quantity,
        discount_percent_at_issue=shop.discount_percent if shop else Decimal("0"),
        payment_mode_at_issue=shop.payment_mode if shop else None,
        valid_from=valid_from,
        expires_at=expires_at,
        status=TaxoCardBatchStatus.ACTIVE,
        created_by=actor.id,
    )
    session.add(batch)
    await session.flush()

    codes: list[tuple[str, str]] = []
    seen: set[str] = set()
    cards = []
    for index in range(1, quantity + 1):
        code = new_code()
        while code in seen:  # pragma: no cover — ٢^٧٩ لا يتصادم في خمسة آلاف
            code = new_code()
        seen.add(code)
        serial = f"{country.value}-B{number:04d}-{index:06d}"
        cards.append(
            TaxoCard(
                batch_id=batch.id, country_code=country, currency=currency, serial=serial,
                code_hash=code_hash(code), amount=denomination.amount, status=TaxoCardStatus.ACTIVE,
            )
        )
        codes.append((serial, printed(code)))
    session.add_all(cards)
    await session.flush()

    # **لا رمزَ في التدقيق** — العددُ والفئةُ والمحلُّ والنافذة
    await audit.record(
        session, actor=actor, action=AuditAction.CREATE, entity_type="card_batch", entity_id=batch.id,
        details={
            "country_code": country.value, "number": number, "quantity": quantity, "amount": str(denomination.amount),
            "shop_id": str(shop.id) if shop else None, "valid_from": valid_from.isoformat(), "expires_at": expires_at.isoformat(),
        },
    )
    return batch, codes


async def cancel_batch(session: AsyncSession, *, batch: CardBatch, actor: User, reason: str | None) -> int:
    """**إلغاءُ دفعةٍ كاملة بسببٍ مكتوب** — وكلُّ بطاقةٍ قائمةٍ فيها تُلغى معها؛ **والمستعمَلةُ تبقى مستعمَلة** (مالُها في محفظة صاحبها)."""
    if batch.status is not TaxoCardBatchStatus.ACTIVE:
        raise InvalidStatusTransition()
    clean = payment_requests.written_reason(reason, field="reason")
    now = _now()
    batch.status = TaxoCardBatchStatus.CANCELLED
    batch.cancel_reason = clean
    batch.cancelled_by = actor.id
    batch.cancelled_at = now
    result = await session.execute(
        update(TaxoCard)
        .where(TaxoCard.batch_id == batch.id, TaxoCard.status == TaxoCardStatus.ACTIVE)
        .values(status=TaxoCardStatus.CANCELLED, cancel_reason=clean, cancelled_by=actor.id, cancelled_at=now)
        .execution_options(synchronize_session=False)
    )
    await audit.record(
        session, actor=actor, action=AuditAction.UPDATE, entity_type="card_batch", entity_id=batch.id,
        details={"action": "cancel", "reason": clean, "cards_cancelled": result.rowcount},
    )
    return result.rowcount


async def get_card(session: AsyncSession, card_id: uuid.UUID, *, for_update: bool = False) -> TaxoCard:
    stmt = select(TaxoCard).where(TaxoCard.id == card_id)
    if for_update:
        stmt = stmt.with_for_update(of=TaxoCard).execution_options(populate_existing=True)
    row = await session.scalar(stmt)
    if row is None:
        raise NotFound("البطاقةُ غيرُ موجودة")
    return row


async def find_cards(session: AsyncSession, country: CountryCode, serial: str, *, limit: int = 50) -> list[TaxoCard]:
    term = serial.strip().upper()
    stmt = (
        select(TaxoCard)
        .where(TaxoCard.country_code == country, TaxoCard.serial.like(f"%{term}%"))
        .order_by(TaxoCard.serial)
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


CARD_STATES = ("unused", "redeemed", "expired", "cancelled", "not_started")


def card_state(card: TaxoCard, batch: CardBatch, now: datetime) -> str:
    """**حالُ البطاقة كما تُقرأ** — المخزَّنةُ ثلاث، و«منتهية» و«لم تبدأ» من نافذة الدفعة لحظةَ القراءة (§٧٣-هـ/٥)."""
    if card.status is TaxoCardStatus.REDEEMED:
        return "redeemed"
    if card.status is TaxoCardStatus.CANCELLED:
        return "cancelled"
    if batch.expires_at <= now:
        return "expired"
    if batch.valid_from > now:
        return "not_started"
    return "unused"


async def batch_cards(
    session: AsyncSession, *, batch: CardBatch, query: str | None, state: str | None, offset: int, limit: int
) -> tuple[list[tuple[TaxoCard, str, str | None]], int]:
    """**بطاقاتُ دفعةٍ واحدة** (SPEC §١٠٠-أ/٢) — التسلسلُ والحالُ ومن استعملها ومتى؛ **ولا رمز**: البصمةُ وحدَها مخزَّنة.

    **والبحثُ** بجزءٍ من التسلسل أو من اسم من استعملها؛ **والحالُ المشتقّة** تُرشَّح في الاستعلام نفسِه فلا تُقرأ الدفعةُ كلُّها."""
    now = _now()
    stmt = select(TaxoCard, User.name).outerjoin(User, User.id == TaxoCard.redeemed_by).where(TaxoCard.batch_id == batch.id)
    term = (query or "").strip()
    if term:
        stmt = stmt.where(TaxoCard.serial.ilike(f"%{term}%") | User.name.ilike(f"%{term}%"))
    if state == "redeemed":
        stmt = stmt.where(TaxoCard.status == TaxoCardStatus.REDEEMED)
    elif state == "cancelled":
        stmt = stmt.where(TaxoCard.status == TaxoCardStatus.CANCELLED)
    elif state in ("unused", "expired", "not_started"):
        wanted = "expired" if batch.expires_at <= now else "not_started" if batch.valid_from > now else "unused"
        stmt = stmt.where(TaxoCard.status == TaxoCardStatus.ACTIVE)
        if wanted != state:
            stmt = stmt.where(False)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (await session.execute(stmt.order_by(TaxoCard.serial).offset(offset).limit(limit))).all()
    return [(card, card_state(card, batch, now), name) for card, name in rows], int(total or 0)


async def cancel_card(session: AsyncSession, *, card: TaxoCard, actor: User, reason: str | None) -> TaxoCard:
    """**إلغاءُ بطاقةٍ واحدة بسببٍ مكتوب** — قائمةٌ وحدَها: المستعمَلةُ مالُها في محفظة صاحبها ولا يُلغى بإلغاء ورقتها."""
    if card.status is not TaxoCardStatus.ACTIVE:
        raise InvalidStatusTransition()
    card.status = TaxoCardStatus.CANCELLED
    card.cancel_reason = payment_requests.written_reason(reason, field="reason")
    card.cancelled_by = actor.id
    card.cancelled_at = _now()
    await audit.record(
        session, actor=actor, action=AuditAction.UPDATE, entity_type="taxo_card", entity_id=card.id,
        details={"action": "cancel", "serial": card.serial, "reason": card.cancel_reason},
    )
    return card


# ------------------------------------------------------------------ التخمين


def _keys(user_id: uuid.UUID, ip: str) -> tuple[tuple[str, str], tuple[str, str]]:
    return (("account", f"taxo_card_wrong:user:{user_id}"), ("ip", f"taxo_card_wrong:ip:{ip}"))


async def require_not_locked(redis: Redis, limits: Limits, *, user_id: uuid.UUID, ip: str) -> None:
    """**من بلغ السقفَ لا يحاول حتى تنقضي النافذة** — يُسأل قبل قراءة الرمز، فلا يُعرف صوابُه من خطئه وهو مقفول."""
    for scope, key in _keys(user_id, ip):
        limit = limits.max_wrong_per_account if scope == "account" else limits.max_wrong_per_ip
        full = f"ratelimit:{key}"
        count = int(await redis.get(full) or 0)
        if count >= limit:
            ttl = await redis.ttl(full)
            raise RateLimited("محاولاتٌ خاطئةٌ كثيرة — حاول بعد قليل", retry_after=max(1, int(ttl or 1)))


async def record_wrong(
    session: AsyncSession, redis: Redis, *, user_id: uuid.UUID, country: CountryCode, ip: str, limits: Limits
) -> None:
    """**يُعدّ الخطأُ لكلِّ حسابٍ ولكلِّ عنوان** — وبلوغُ السقف بالضبط يكتب تنبيهاً واحداً للّوحة (لا تنبيهاً لكلِّ محاولةٍ بعده)."""
    window = limits.window_minutes * 60
    for scope, key in _keys(user_id, ip):
        limit = limits.max_wrong_per_account if scope == "account" else limits.max_wrong_per_ip
        await rate_limit.hit(redis, key, limit=limit, window_seconds=window)
        count = int(await redis.get(f"ratelimit:{key}") or 0)
        if count == limit:
            session.add(
                CardGuessAlert(
                    country_code=country,
                    scope=scope,
                    user_id=user_id if scope == "account" else None,
                    ip=ip,
                    attempts=count,
                )
            )
    await session.flush()


async def alerts(session: AsyncSession, country: CountryCode, *, limit: int = 100) -> list[CardGuessAlert]:
    stmt = (
        select(CardGuessAlert)
        .where(CardGuessAlert.country_code == country)
        .order_by(CardGuessAlert.reviewed_at.is_not(None), CardGuessAlert.created_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def review_alert(session: AsyncSession, *, alert_id: uuid.UUID, actor: User) -> CardGuessAlert:
    row = await session.get(CardGuessAlert, alert_id, with_for_update=True)
    if row is None:
        raise NotFound("التنبيهُ غيرُ موجود")
    if row.reviewed_at is None:
        row.reviewed_by = actor.id
        row.reviewed_at = _now()
    return row


# ------------------------------------------------------------------ الاستعمال


@dataclass(slots=True)
class Redeemed:
    card: TaxoCard
    request: PaymentRequest


async def _card_provider(session: AsyncSession, country: CountryCode) -> PayMethod:
    """**طريقةُ «بطاقات TAXO» المفعَّلةُ في السوق** — موقوفةً لا يشحن رمز (§٧٣-هـ/٢-٩)."""
    provider = await session.scalar(
        select(PayMethod)
        .where(
            PayMethod.country_code == country,
            PayMethod.kind == PaymentProviderKind.PURCHASE_CODE,
            PayMethod.enabled.is_(True),
        )
        .order_by(PayMethod.sort_order)
        .limit(1)
    )
    if provider is None:
        raise FeatureDisabled("الشحنُ ببطاقات TAXO غيرُ متاحٍ في بلدك الآن")
    return provider


async def redeem(
    session: AsyncSession, *, user: User, code_raw: str | None, declared: WalletOwnerType | None = None
) -> Redeemed:
    """**رمزٌ يشحن مرّةً واحدة** — دفعةٌ معتمدةٌ في نظام الدفع وقيدُ «شحن ببطاقة TAXO» في المعاملة نفسِها.

    **وما يُعدّ خطأً** (`CardCodeRejected`): غيرُ صحيح، أو من سوقٍ آخر، أو مستعمَل، أو ملغًى. **وما لا يُعدّ**: صحيحٌ في غير نافذته.
    """
    _pepper()
    code = normalize_code(code_raw)
    if code is None:
        raise CardCodeRejected("الرمزُ غيرُ صحيح — ستّةَ عشرَ حرفاً كما في البطاقة")

    card = await session.scalar(
        select(TaxoCard)
        .where(TaxoCard.code_hash == code_hash(code))
        .with_for_update(of=TaxoCard)
        .execution_options(populate_existing=True)
    )
    if card is None or card.country_code != user.country_code:
        raise CardCodeRejected()
    if card.status is TaxoCardStatus.REDEEMED:
        raise CardCodeRejected("استُعملت هذه البطاقة من قبل")
    if card.status is TaxoCardStatus.CANCELLED or card.batch.status is TaxoCardBatchStatus.CANCELLED:
        raise CardCodeRejected("هذه البطاقةُ ملغاة")
    now = _now()
    if now < card.batch.valid_from:
        raise CardNotUsableNow(f"لا تعمل هذه البطاقةُ قبل {card.batch.valid_from.date().isoformat()}")
    if now >= card.batch.expires_at:
        raise CardNotUsableNow("انتهت صلاحيةُ هذه البطاقة")

    test_accounts.require_real_money(user, "حسابُ التجربة لا يُشحن ببطاقةٍ حقيقيّة")
    await payment_requests.require_enabled(session, user.country_code)
    provider = await _card_provider(session, user.country_code)
    verification.require_usable_account(user)
    await wallet.require_wallet_enabled(session, user.country_code)
    owner_type = wallet.owner_type_for(user, declared=declared)
    wallet.require_not_frozen(user, owner_type)

    request = PaymentRequest(
        user_id=user.id,
        owner_type=owner_type,
        country_code=user.country_code,
        currency=card.currency,
        provider_id=provider.id,
        kind=PaymentProviderKind.PURCHASE_CODE,
        purpose=PaymentRequestPurpose.WALLET_TOPUP,
        amount=card.amount,
        credited_amount=card.amount,
        status=PaymentRequestStatus.APPROVED,
        # **الرقمُ التسلسليُّ مرجعُ الدفعة** — والفهرسُ الفريدُ للمرجع حارسٌ ثانٍ على «مرّةً واحدة»
        reference=card.serial,
        reference_key=card.serial.casefold(),
        reviewed_at=now,
    )
    session.add(request)
    await session.flush()

    entry = await wallet.record(
        session,
        owner=user,
        owner_type=owner_type,
        tx_type=WalletTransactionType.TAXO_CARD,
        amount=card.amount,
        reference=f"بطاقة TAXO {card.serial}"[:120],
        created_by=user.id,
        idempotency_key=f"taxo_card:{card.id}",
    )
    request.transaction_id = entry.id
    card.status = TaxoCardStatus.REDEEMED
    card.redeemed_by = user.id
    card.redeemed_owner_type = owner_type
    card.redeemed_at = now
    card.transaction_id = entry.id
    card.payment_request_id = request.id
    # **ودَينُ إلغاءٍ يُسدَّد لحظةَ اكتمال الشحن** — كالشحن القائم حرفاً
    await cancellation.on_wallet_funded(session, user=user)
    return Redeemed(card=card, request=request)


# ------------------------------------------------------------------ التقرير


@dataclass(slots=True)
class BatchFigures:
    batch: CardBatch
    active: int
    redeemed: int
    cancelled: int
    #: **غيرُ مستعملةٍ وما زالت تعمل** و**منتهيةٌ لم تُستعمل** — تُشتقّان من نافذة الدفعة لحظةَ القراءة (لا كنس)، **ومجموعُهما `active`**
    unused: int
    expired: int
    redeemed_value: Decimal
    #: **قيمةُ ما سُلِّم ولم يُلغَ** — وجهُ البطاقات بسعرها
    live_value: Decimal
    #: **المستحقُّ من المحلّ بشرطه المجمَّد** — قبل الاستلام: ما سُلِّم ولم يُلغَ ناقصاً خصمَه؛ بعد البيع: ما استُعمل ناقصاً خصمَه
    due_from_shop: Decimal


def _due(batch: CardBatch, live: int, redeemed: int) -> Decimal:
    """**الخصمُ في الخلفية وحدَها** (§14) — مقرَّباً بخانات العملة."""
    if batch.shop_id is None:
        return Decimal("0")
    basis = live if batch.payment_mode_at_issue is CardShopPaymentMode.BEFORE_RECEIPT else redeemed
    gross = batch.amount * basis
    return round_to_currency(gross * (Decimal(100) - batch.discount_percent_at_issue) / Decimal(100), batch.currency)


async def batch_figures(session: AsyncSession, country: CountryCode) -> list[BatchFigures]:
    batches = list(
        (await session.scalars(
            select(CardBatch).where(CardBatch.country_code == country).order_by(CardBatch.number.desc())
        )).all()
    )
    counts: dict[tuple[uuid.UUID, TaxoCardStatus], int] = {}
    if batches:
        rows = await session.execute(
            select(TaxoCard.batch_id, TaxoCard.status, func.count())
            .where(TaxoCard.batch_id.in_([b.id for b in batches]))
            .group_by(TaxoCard.batch_id, TaxoCard.status)
        )
        counts = {(batch_id, status): count for batch_id, status, count in rows.all()}
    out = []
    now = _now()
    for batch in batches:
        active = counts.get((batch.id, TaxoCardStatus.ACTIVE), 0)
        redeemed = counts.get((batch.id, TaxoCardStatus.REDEEMED), 0)
        cancelled = counts.get((batch.id, TaxoCardStatus.CANCELLED), 0)
        live = active + redeemed
        lapsed = batch.expires_at <= now
        out.append(
            BatchFigures(
                batch=batch, active=active, redeemed=redeemed, cancelled=cancelled,
                unused=0 if lapsed else active, expired=active if lapsed else 0,
                redeemed_value=batch.amount * redeemed, live_value=batch.amount * live,
                due_from_shop=_due(batch, live, redeemed),
            )
        )
    return out


def shop_totals(figures: list[BatchFigures]) -> dict[uuid.UUID, dict[str, Decimal | int]]:
    """**مجموعُ كلِّ محلٍّ من دفعاته** — جمعُ ما حُسب لكلِّ دفعة، لا حسابٌ ثانٍ يفترق عنه."""
    totals: dict[uuid.UUID, dict[str, Decimal | int]] = {}
    for row in figures:
        if row.batch.shop_id is None:
            continue
        bucket = totals.setdefault(
            row.batch.shop_id,
            {"batches": 0, "cards": 0, "redeemed": 0, "cancelled": 0, "redeemed_value": Decimal(0),
             "live_value": Decimal(0), "due_from_shop": Decimal(0)},
        )
        bucket["batches"] += 1
        bucket["cards"] += row.batch.quantity
        bucket["redeemed"] += row.redeemed
        bucket["cancelled"] += row.cancelled
        bucket["redeemed_value"] += row.redeemed_value
        bucket["live_value"] += row.live_value
        bucket["due_from_shop"] += row.due_from_shop
    return totals



# ------------------------------------------------------------------ ملفّاتُ الدفعة (SPEC §١٠٠-أ/١)

#: **«لحظةَ الإنشاء»** — بعدها لا ملفّ: الرموزُ لا تُستعاد، ومن أغلق النافذةَ بلا تنزيلٍ يُلغي الدفعةَ ويُصدر غيرَها
EXPORT_WINDOW = timedelta(minutes=30)
EXPORT_FORMATS = ("xlsx", "pdf", "sheet")


async def export_batch(
    session: AsyncSession, *, batch: CardBatch, actor: User, fmt: str, password: str, codes: list[tuple[str, str]]
) -> tuple[bytes, str, str]:
    """**ملفُّ الدفعة من رموزٍ في يد اللوحة** — كلُّ رمزٍ يُطابَق ببصمة بطاقته في الدفعة، **ولا يُخزَّن شيء**.

    **وصفُّ التدقيق بلا رمزٍ ولا كلمة سرّ**: الصيغةُ والعددُ ومن نزّل."""
    from app.services import card_exports
    from app.services.stats import _zone

    if fmt not in EXPORT_FORMATS:
        raise InvalidInput("صيغةُ الملفّ غيرُ معروفة", field="format")
    card_exports.check_password(password)
    if _now() - batch.created_at > EXPORT_WINDOW:
        raise InvalidInput("ملفّاتُ الدفعة تُنزَّل عند إنشائها وحدَه — الرموزُ لا تُستعاد", field="batch_id")
    if not codes:
        raise InvalidInput("لا رموزَ في الطلب", field="codes")
    by_serial = {
        row.serial: row
        for row in (await session.scalars(select(TaxoCard).where(TaxoCard.batch_id == batch.id))).all()
    }
    rows: list[card_exports.CardRow] = []
    seen: set[str] = set()
    for serial, raw in codes:
        card = by_serial.get(serial)
        code = normalize_code(raw)
        # **رمزٌ لا تطابق بصمتُه بطاقتَه لا يدخل ملفّاً** — فلا يُطبع رمزٌ مخترعٌ باسم TAXO
        if card is None or code is None or serial in seen or not hmac.compare_digest(code_hash(code), card.code_hash):
            raise InvalidInput("رمزٌ لا يطابق بطاقتَه في هذه الدفعة", field="codes")
        seen.add(serial)
        rows.append(card_exports.CardRow(serial=serial, code=printed(code), amount=card.amount, status=card.status.value))
    rows.sort(key=lambda row: row.serial)
    shop = await session.get(CardShop, batch.shop_id) if batch.shop_id else None
    meta = card_exports.BatchMeta(
        title=f"دفعة {batch.country_code.value}-B{batch.number:04d}", country=batch.country_code.value,
        currency=batch.currency.value, amount=batch.amount, valid_from=batch.valid_from, expires_at=batch.expires_at,
        created_at=batch.created_at, shop=shop.name if shop else None, zone=await _zone(session, batch.country_code),
    )
    stem = f"taxo-cards-{batch.country_code.value}-B{batch.number:04d}"
    if fmt == "xlsx":
        content, media, name = card_exports.batch_xlsx(meta, rows, password=password), card_exports.XLSX_MEDIA_TYPE, f"{stem}.xlsx"
    elif fmt == "pdf":
        content, media, name = card_exports.batch_pdf(meta, rows, password=password), card_exports.PDF_MEDIA_TYPE, f"{stem}.pdf"
    else:
        content, media, name = card_exports.print_sheet_pdf(meta, rows, password=password), card_exports.PDF_MEDIA_TYPE, f"{stem}-print.pdf"
    await audit.record(
        session, actor=actor, action=AuditAction.READ, entity_type="card_batch_export", entity_id=batch.id,
        details={"format": fmt, "cards": len(rows)},
    )
    return content, media, name
