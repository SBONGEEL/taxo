"""بطاقاتُ TAXO يبيعها الكباتن (أمرُ المالك ٢٠٢٦-١١-٢٣، `design/CAPTAIN-CARDS-2026-11-23.md`، الترحيلة `0189`).

* **الكبتنُ يشتري دفعةً من محفظته بخصمٍ يضبطه المالك** (`taxo_card_settings.captain_discount_percent`)، ويبيع كلَّ بطاقةٍ للراكب
  **بقيمتها الاسميّة نقداً خارج المنصّة**؛ والفرقُ خصمُه. **ولا يُفتح البيعُ إلا بشرطين**: مفتاحُ الدولة `taxo_cards_captain_sales`
  **و**الخصمُ مضبوط — وإلا `409 captain_card_sales_closed`.
* **السقفُ اليوميُّ والصلاحيةُ من إعدادات البيع القائمة** (`pos_daily_cap` · `pos_validity_days`) — لا إعدادَ ثانٍ لشيءٍ واحد.
  والسقفُ **عددُ بطاقاتٍ في آخر ٢٤ ساعة** لكلِّ كبتن.
* **ترتيبُ الأقفال**: صفُّ الكبتن (`drivers_service.lock`) ⇐ قفلُ السوق لرقم الدفعة ⇐ قفلُ المحفظة الاستشاريّ آخراً (في `wallet.record`).
  **وما يملكه قفلُ الكبتن وحدَه هو السقف**: بلا قفلٍ يقرأ شراءان متزامنان العدَّ نفسَه فيتجاوزانه معاً؛ **والرصيدُ يحرسه قفلُ المحفظة**.
* **الكلفةُ في الخلفية وحدَها** (§14): العدد × الفئة × (١ − الخصم/١٠٠)، مقرَّبةً بخانات العملة، **والخصمُ مجمَّدٌ على الدفعة**.
* **مفتاحُ التكرار من العميل يصنع معرّفَ الدفعة** (`uuid5`)، فالإعادةُ تجد دفعتَها ولا تُنشئ ثانية، **وقيدُ الدفتر `cardbuy:<الدفعة>`**.
* **الرموزُ معمّاةٌ** (`code_envelope`، Fernet كالهدايا) ليعرضها الكبتنُ حين يبيع، **وتُمحى عند الشحن**؛ ولا رمزَ في تدقيقٍ ولا سجلّ.
* **وبطاقةُ الكبتن لمحفظة الراكب** ولا يشحن بها بائعُها (`taxo_cards.redeem`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import get_cipher
from app.core.currency import currency_for_country, round_to_currency
from app.core.exceptions import AppError, InsufficientBalance, InvalidInput, NotFound
from app.models.driver import Driver
from app.models.enums import (
    AuditAction,
    CountryCode,
    DriverStatus,
    FeatureKey,
    TaxoCardBatchStatus,
    TaxoCardStatus,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.taxo_card import CardBatch, CardDenomination, TaxoCard, TaxoCardSetting
from app.models.user import User
from app.services import audit, card_sellers, settings_service, taxo_cards, test_accounts, wallet
from app.services import drivers as drivers_service

KIND = "captain"
#: **أكبرُ دفعةٍ في طلبٍ واحد** — والسقفُ اليوميُّ يحكم فوقها
MAX_PER_PURCHASE = 100
_KEY_SPACE = uuid.UUID("6f1d3c2a-3b7e-4c51-9a0e-1f2b3c4d5e6f")


class CaptainSalesClosed(AppError):
    status_code = 409
    code = "captain_card_sales_closed"
    message = "بيعُ بطاقات TAXO للكباتن غيرُ مفتوحٍ في بلدك الآن"


class CaptainDailyCap(AppError):
    status_code = 429
    code = "captain_card_daily_cap"
    message = "بلغتَ سقفَ شراء البطاقات لهذا اليوم"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SalesState:
    open: bool
    discount_percent: Decimal | None
    daily_cap: int
    validity_days: int


async def state(session: AsyncSession, country: CountryCode) -> SalesState:
    pos = await card_sellers.pos_settings(session, country)
    discount = await session.scalar(
        select(TaxoCardSetting.captain_discount_percent).where(TaxoCardSetting.country_code == country)
    )
    flag = await settings_service.is_feature_enabled(session, country, FeatureKey.TAXO_CARDS_CAPTAIN_SALES)
    return SalesState(
        open=bool(flag) and discount is not None, discount_percent=discount, daily_cap=pos.daily_cap,
        validity_days=pos.validity_days,
    )


async def save_discount(
    session: AsyncSession, *, actor: User, country: CountryCode, discount: Decimal | None
) -> Decimal | None:
    """**المالكُ وحدَه** (الراوتر بـ`OwnerUser`) — فارغٌ يُغلق البيعَ ولو اشتعل المفتاح."""
    if discount is not None and not Decimal(0) <= discount <= Decimal(50):
        raise InvalidInput("خصمُ الكباتن بين 0 و50 بالمئة", field="captain_discount_percent")
    row = await session.scalar(select(TaxoCardSetting).where(TaxoCardSetting.country_code == country).with_for_update())
    if row is None:
        row = TaxoCardSetting(country_code=country, max_wrong_per_account=5, max_wrong_per_ip=20, window_minutes=60)
        session.add(row)
    recorded = audit.apply_changes(row, {"captain_discount_percent": discount})
    await session.flush()
    if recorded:
        await audit.record(
            session, actor=actor, action=AuditAction.UPDATE, entity_type="taxo_card_settings",
            details={"country_code": country.value, "part": "captain_discount"}, changes=recorded,
        )
    return row.captain_discount_percent


def unit_cost(amount: Decimal, discount: Decimal, country: CountryCode) -> Decimal:
    return round_to_currency(amount * (Decimal(100) - discount) / Decimal(100), currency_for_country(country))


def total_cost(amount: Decimal, quantity: int, discount: Decimal, country: CountryCode) -> Decimal:
    """**الكلفةُ على الدفعة كلِّها ثمّ تُقرَّب** — لا مجموعُ تقريبات البطاقات."""
    return round_to_currency(amount * quantity * (Decimal(100) - discount) / Decimal(100), currency_for_country(country))


async def bought_today(session: AsyncSession, driver_id: uuid.UUID) -> int:
    """**بطاقاتٌ في آخر ٢٤ ساعة** — نافذةٌ متدحرجةٌ كسقف المحلّ: سقفٌ أمنيٌّ لا تقرير."""
    return int(
        await session.scalar(
            select(func.coalesce(func.sum(CardBatch.quantity), 0)).where(
                CardBatch.kind == KIND, CardBatch.seller_driver_id == driver_id,
                CardBatch.created_at >= _now() - timedelta(hours=24),
            )
        )
        or 0
    )


async def denominations(session: AsyncSession, country: CountryCode) -> list[CardDenomination]:
    return [row for row in await taxo_cards.denominations(session, country) if row.is_active]


@dataclass(frozen=True)
class Purchase:
    batch: CardBatch
    cost: Decimal
    balance_after: Decimal
    replayed: bool


def batch_id_for(driver_id: uuid.UUID, key: str) -> uuid.UUID:
    return uuid.uuid5(_KEY_SPACE, f"{driver_id}:{key}")


async def purchase(
    session: AsyncSession, *, driver: Driver, user: User, denomination_id: uuid.UUID, quantity: int, idempotency_key: str
) -> Purchase:
    country = user.country_code
    key = (idempotency_key or "").strip()
    if not 8 <= len(key) <= 80:
        raise InvalidInput("مفتاحُ التكرار مطلوب", field="idempotency_key")
    if not 1 <= quantity <= MAX_PER_PURCHASE:
        raise InvalidInput(f"العددُ بين 1 و{MAX_PER_PURCHASE}", field="quantity")
    test_accounts.require_real_money(user, "حسابُ التجربة لا يشتري بطاقاتٍ حقيقيّة")

    # **صفُّ الكبتن أوّلاً** — يسبق قراءةَ السقف والإعادة، **والحالُ تُقرأ تحته** (كبتنٌ موقوفٌ لا يبيع باسم TAXO)
    await drivers_service.lock(session, driver)
    if driver.status is not DriverStatus.APPROVED:
        raise CaptainSalesClosed("بيعُ البطاقات للكباتن المعتمَدين وحدَهم")
    batch_id = batch_id_for(driver.id, key)
    existing = await session.get(CardBatch, batch_id)
    if existing is not None:
        if existing.seller_driver_id != driver.id:  # pragma: no cover — uuid5 بمعرّف الكبتن لا يتصادم
            raise InvalidInput("مفتاحُ التكرار مستعمَل", field="idempotency_key")
        entry = await wallet.find_by_idempotency_key(session, user.id, f"cardbuy:{existing.id}")
        after = await wallet.balance(session, user.id, WalletOwnerType.DRIVER)
        return Purchase(batch=existing, cost=-(entry.amount if entry else Decimal(0)), balance_after=after, replayed=True)

    sales = await state(session, country)
    if not sales.open or sales.discount_percent is None:
        raise CaptainSalesClosed()
    await wallet.require_wallet_enabled(session, country)
    wallet.require_not_frozen(user, WalletOwnerType.DRIVER)
    if await bought_today(session, driver.id) + quantity > sales.daily_cap:
        raise CaptainDailyCap()
    denomination = await session.get(CardDenomination, denomination_id)
    if denomination is None or denomination.country_code != country or not denomination.is_active:
        raise InvalidInput("الفئةُ غيرُ متاحةٍ في هذا السوق", field="denomination_id")
    cost = total_cost(denomination.amount, quantity, sales.discount_percent, country)
    # **رصيدٌ ناقصٌ يُردّ قبل أيِّ صفّ** — و`wallet.record` يعيد الفحصَ تحت قفل المحفظة
    if await wallet.balance(session, user.id, WalletOwnerType.DRIVER) < cost:
        raise InsufficientBalance()

    now = _now()
    batch, codes = await taxo_cards.create_batch(
        session, actor=user, country=country, denomination_id=denomination.id, quantity=quantity, shop_id=None,
        valid_from=now - timedelta(seconds=5), expires_at=now + timedelta(days=sales.validity_days), kind=KIND,
        batch_id=batch_id, seller_driver_id=driver.id, discount_percent=sales.discount_percent,
    )
    cipher = get_cipher()
    by_serial = dict(codes)
    cards = (await session.scalars(select(TaxoCard).where(TaxoCard.batch_id == batch.id))).all()
    for card in cards:
        card.code_envelope = cipher.encrypt({"code": taxo_cards.normalize_code(by_serial[card.serial])})
    await wallet.record(
        session, owner=user, owner_type=WalletOwnerType.DRIVER, tx_type=WalletTransactionType.CARD_PURCHASE,
        amount=-cost, reference=f"شراء بطاقات TAXO {batch.number}"[:120], created_by=user.id,
        idempotency_key=f"cardbuy:{batch.id}",
    )
    await session.flush()
    await audit.record(
        session, actor=user, action=AuditAction.CREATE, entity_type="taxo_card.captain_purchase", entity_id=batch.id,
        details={
            "country_code": country.value, "driver_id": str(driver.id), "quantity": quantity,
            "amount": str(denomination.amount), "discount_percent": str(sales.discount_percent), "cost": str(cost),
        },
    )
    after = await wallet.balance(session, user.id, WalletOwnerType.DRIVER)
    return Purchase(batch=batch, cost=cost, balance_after=after, replayed=False)


async def my_cards(session: AsyncSession, driver: Driver, *, limit: int = 200) -> list[tuple[TaxoCard, str]]:
    now = _now()
    rows = (
        await session.scalars(
            select(TaxoCard)
            .join(CardBatch, CardBatch.id == TaxoCard.batch_id)
            .where(CardBatch.kind == KIND, CardBatch.seller_driver_id == driver.id)
            .order_by(CardBatch.created_at.desc(), TaxoCard.serial)
            .limit(limit)
        )
    ).all()
    return [(card, taxo_cards.card_state(card, card.batch, now)) for card in rows]


async def reveal(session: AsyncSession, *, driver: Driver, card_id: uuid.UUID) -> tuple[TaxoCard, str]:
    """**الرمزُ لبائعه وحدَه** (لا IDOR) — ولبطاقةٍ تعمل لم تُستعمل؛ **ولا يُكتب في تدقيقٍ ولا سجلّ**."""
    card = await session.get(TaxoCard, card_id)
    if card is None or card.batch.kind != KIND or card.batch.seller_driver_id != driver.id:
        raise NotFound("البطاقةُ غيرُ موجودة")
    if (
        card.status is not TaxoCardStatus.ACTIVE
        or card.batch.status is TaxoCardBatchStatus.CANCELLED
        or card.code_envelope is None
    ):
        raise NotFound("لا رمزَ لهذه البطاقة — استُعملت أو أُلغيت")
    code = get_cipher().decrypt(card.code_envelope)["code"]
    return card, taxo_cards.printed(code)


@dataclass(frozen=True)
class CaptainFigures:
    driver_id: uuid.UUID
    name: str | None
    phone: str | None
    batches: int
    cards: int
    redeemed: int
    cancelled: int
    unused: int
    expired: int
    face_value: Decimal
    paid: Decimal


async def seller_report(session: AsyncSession, country: CountryCode) -> list[CaptainFigures]:
    """**المبيعاتُ بحسب الكبتن** — من الدفعات والدفتر في الخلفية (§14)، لا من حسابٍ في الواجهة."""
    figures = [row for row in await taxo_cards.batch_figures(session, country) if row.batch.kind == KIND]
    if not figures:
        return []
    ids = {row.batch.seller_driver_id for row in figures}
    people = {
        driver_id: (name, phone)
        for driver_id, name, phone in (
            await session.execute(
                select(Driver.id, User.name, User.phone).join(User, User.id == Driver.user_id).where(Driver.id.in_(ids))
            )
        ).all()
    }
    keys = [f"cardbuy:{row.batch.id}" for row in figures]
    from app.models.wallet import WalletTransaction

    paid_by_key = dict(
        (
            await session.execute(
                select(WalletTransaction.idempotency_key, WalletTransaction.amount).where(
                    WalletTransaction.idempotency_key.in_(keys)
                )
            )
        ).all()
    )
    out: dict[uuid.UUID, dict] = {}
    for row in figures:
        driver_id = row.batch.seller_driver_id
        bucket = out.setdefault(driver_id, {"batches": 0, "cards": 0, "redeemed": 0, "cancelled": 0, "unused": 0,
                                            "expired": 0, "face_value": Decimal(0), "paid": Decimal(0)})
        bucket["batches"] += 1
        bucket["cards"] += row.active + row.redeemed + row.cancelled
        bucket["redeemed"] += row.redeemed
        bucket["cancelled"] += row.cancelled
        bucket["unused"] += row.unused
        bucket["expired"] += row.expired
        bucket["face_value"] += row.batch.amount * row.batch.quantity
        bucket["paid"] += -paid_by_key.get(f"cardbuy:{row.batch.id}", Decimal(0))
    return [
        CaptainFigures(driver_id=driver_id, name=people.get(driver_id, (None, None))[0],
                       phone=people.get(driver_id, (None, None))[1], **values)
        for driver_id, values in out.items()
    ]
