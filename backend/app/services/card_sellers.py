"""بائعو البطاقات في المحلّات — والبيعُ لحظةَ الطلب (SPEC §١٠٠-ب/٤–٥، أمرُ المالك ٢٠٢٦-١١-١٢).

* **الحسابُ** ينشئه المالكُ من اللوحة: دورُ `card_seller` وحدَه، ومربوطٌ بمحلٍّ واحد (`card_shop_staff`)، والكلمةُ تتغيّر عند
  أوّل دخول، والعاملُ الثاني إلزاميّ.
* **البيع**: بطاقةٌ واحدةٌ تُولَّد لحظةَ الطلب (دفعةٌ `kind = pos`، رقمُها `<السوق>-P<الدفعة>-000001`) **باسم محلّ البائع من ربطه
  لا من الطلب** — والرمزُ في الردِّ مرّةً واحدةً للإيصال، **ولا يُخزَّن إلا بصمتُه** كسائر البطاقات.
* **مطفأٌ حتى يفتحه المالك** (`taxo_card_settings.pos_enabled`)، وسقفٌ يوميٌّ لكلِّ بائعٍ **عددُ بطاقاتٍ لا مال**.
* **ولا مالَ يُضبط هنا**: رصيدُ المحلّ وحدُّ ائتمانه وعمولتُه وتسويتُه قيمُ المالك وتنتظره. والخصمُ ونمطُ الدفع يُجمَّدان على
  الدفعة كما يُجمَّدان في كلِّ دفعةٍ لمحلّ — **فما يستحقّه المحلُّ يُقرأ في تقرير المحلّات القائم**.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, InvalidInput, NotFound
from app.models.enums import AuditAction, CountryCode, UserRole
from app.models.taxo_card import CardBatch, CardShopStaff, TaxoCard, TaxoCardSetting
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.services import admin_credentials, audit, taxo_cards


class SellingClosed(AppError):
    status_code = 409
    code = "card_selling_closed"
    message = "البيعُ في المحلّات غيرُ مفتوحٍ في هذا السوق بعد"


class SellerNotBound(AppError):
    status_code = 403
    code = "card_seller_not_bound"
    message = "هذا الحسابُ غيرُ مربوطٍ بمحلٍّ فعّال — تواصل مع الإدارة"


class DailyCapReached(AppError):
    status_code = 429
    code = "card_seller_daily_cap"
    message = "بلغتَ سقفَ البيع لهذا اليوم"


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class PosSettings:
    enabled: bool
    daily_cap: int
    validity_days: int


async def pos_settings(session: AsyncSession, country: CountryCode) -> PosSettings:
    row = await session.scalar(select(TaxoCardSetting).where(TaxoCardSetting.country_code == country))
    if row is None:
        return PosSettings(enabled=False, daily_cap=20, validity_days=365)
    return PosSettings(enabled=row.pos_enabled, daily_cap=row.pos_daily_cap, validity_days=row.pos_validity_days)


async def save_pos_settings(
    session: AsyncSession, *, actor: User, country: CountryCode, changes: dict[str, object]
) -> PosSettings:
    if "pos_daily_cap" in changes and not 1 <= int(changes["pos_daily_cap"]) <= 500:  # type: ignore[arg-type]
        raise InvalidInput("سقفُ البيع اليوميّ بين 1 و500", field="pos_daily_cap")
    if "pos_validity_days" in changes and not 30 <= int(changes["pos_validity_days"]) <= 1095:  # type: ignore[arg-type]
        raise InvalidInput("الصلاحيةُ بين 30 و1095 يوماً", field="pos_validity_days")
    row = await session.scalar(select(TaxoCardSetting).where(TaxoCardSetting.country_code == country).with_for_update())
    if row is None:
        row = TaxoCardSetting(country_code=country, max_wrong_per_account=5, max_wrong_per_ip=20, window_minutes=60)
        session.add(row)
    recorded = audit.apply_changes(row, changes)
    await session.flush()
    if recorded:
        await audit.record(
            session, actor=actor, action=AuditAction.UPDATE, entity_type="taxo_card_settings",
            details={"country_code": country.value, "part": "pos"}, changes=recorded,
        )
    return PosSettings(enabled=row.pos_enabled, daily_cap=row.pos_daily_cap, validity_days=row.pos_validity_days)


# ------------------------------------------------------------------ الحسابات


async def sellers(session: AsyncSession, country: CountryCode) -> list[tuple[CardShopStaff, User]]:
    rows = await session.execute(
        select(CardShopStaff, User)
        .join(User, User.id == CardShopStaff.user_id)
        .where(User.country_code == country)
        .order_by(CardShopStaff.created_at)
    )
    return [(staff, user) for staff, user in rows.all()]


async def create_seller(
    session: AsyncSession, redis: Redis, *, actor: User, shop_id: uuid.UUID, name: str, username: str, password: str
) -> tuple[CardShopStaff, User, str]:
    """**ينشئه المالكُ من اللوحة** — دورُ البائع وحدَه، ومحلٌّ واحد، **والكلمةُ يضعها المالكُ وتتغيّر عند أوّل دخول**.
    **ولا هاتفَ ولا بريد**: الحسابُ للّوحة وحدَها."""
    from app.services.auth.password import set_password

    clean = name.strip()
    if len(clean) < 2:
        raise InvalidInput("اكتب اسمَ البائع", field="name")
    shop = await taxo_cards.get_shop(session, shop_id)
    if not shop.is_active:
        raise InvalidInput("المحلُّ موقوف", field="shop_id")
    user = User(
        phone=None,
        name=clean[:120],
        role=UserRole.CARD_SELLER,
        country_code=shop.country_code,
        role_grants=[UserRoleGrant(role=UserRole.CARD_SELLER)],
    )
    session.add(user)
    await session.flush()
    await set_password(session, redis, user=user, new_password=password)
    credential = await admin_credentials.create(session, user=user, username=username, must_change_password=True)
    staff = CardShopStaff(user_id=user.id, shop_id=shop.id, is_active=True, created_by=actor.id)
    session.add(staff)
    await session.flush()
    await audit.record(
        session, actor=actor, action=AuditAction.CREATE, entity_type="user", entity_id=user.id,
        details={
            "role": UserRole.CARD_SELLER.value, "username": credential.username, "shop_id": str(shop.id),
            "country": shop.country_code.value,
        },
    )
    return staff, user, credential.username


async def set_seller_active(session: AsyncSession, *, actor: User, staff_id: uuid.UUID, active: bool) -> CardShopStaff:
    staff = await session.scalar(
        select(CardShopStaff)
        .where(CardShopStaff.id == staff_id)
        .with_for_update(of=CardShopStaff)
        .execution_options(populate_existing=True)
    )
    if staff is None:
        raise NotFound("البائعُ غيرُ موجود")
    if staff.is_active != active:
        staff.is_active = active
        await session.flush()
        await audit.record(
            session, actor=actor, action=AuditAction.UPDATE, entity_type="card_shop_staff", entity_id=staff.id,
            changes={"is_active": {"old": not active, "new": active}},
        )
    return staff


async def binding(session: AsyncSession, user: User) -> CardShopStaff:
    staff = await session.scalar(select(CardShopStaff).where(CardShopStaff.user_id == user.id))
    if staff is None or not staff.is_active or not staff.shop.is_active:
        raise SellerNotBound()
    return staff


def _day_start(now: datetime) -> datetime:
    return now - timedelta(hours=24)


async def sold_today(session: AsyncSession, user: User) -> int:
    """**آخرُ أربعٍ وعشرين ساعة** — نافذةٌ متدحرجةٌ لا يومُ تقويم: سقفٌ أمنيٌّ لا تقريرٌ محاسبيّ."""
    return int(
        await session.scalar(
            select(func.count()).select_from(CardBatch).where(
                CardBatch.kind == "pos", CardBatch.created_by == user.id, CardBatch.created_at >= _day_start(_now())
            )
        )
        or 0
    )


@dataclass(frozen=True)
class Sale:
    batch: CardBatch
    serial: str
    code: str


async def sell(session: AsyncSession, *, seller: User, denomination_id: uuid.UUID) -> Sale:
    """**بطاقةٌ واحدةٌ لحظةَ البيع** — باسم محلّ البائع من ربطه. **وقفلُ صفِّ الربط يسبق عدَّ اليوم**، فلا يتجاوز طلبان
    متزامنان السقف."""
    staff = await binding(session, seller)
    shop = staff.shop
    settings = await pos_settings(session, shop.country_code)
    if not settings.enabled:
        raise SellingClosed()
    await session.execute(
        select(CardShopStaff.id).where(CardShopStaff.id == staff.id).with_for_update()
    )
    if await sold_today(session, seller) >= settings.daily_cap:
        raise DailyCapReached()
    now = _now()
    batch, codes = await taxo_cards.create_batch(
        session, actor=seller, country=shop.country_code, denomination_id=denomination_id, quantity=1, shop_id=shop.id,
        valid_from=now - timedelta(seconds=5), expires_at=now + timedelta(days=settings.validity_days), kind="pos",
    )
    serial, code = codes[0]
    return Sale(batch=batch, serial=serial, code=code)


async def my_sales(session: AsyncSession, seller: User, *, limit: int = 50) -> list[tuple[TaxoCard, str]]:
    now = _now()
    rows = (
        await session.scalars(
            select(TaxoCard)
            .join(CardBatch, CardBatch.id == TaxoCard.batch_id)
            .where(CardBatch.kind == "pos", CardBatch.created_by == seller.id)
            .order_by(CardBatch.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [(card, taxo_cards.card_state(card, card.batch, now)) for card in rows]


@dataclass(frozen=True)
class SellerFigures:
    user_id: uuid.UUID
    sold: int
    redeemed: int
    cancelled: int
    sold_value: object
    redeemed_value: object


async def seller_figures(session: AsyncSession, country: CountryCode) -> dict[uuid.UUID, SellerFigures]:
    """**مبيعاتُ كلِّ بائع** — عددٌ وقيمةٌ اسميّة؛ **وما يستحقّه المحلُّ في تقرير المحلّات** (الخصمُ المجمَّد ونمطُ الدفع)."""
    from app.models.enums import TaxoCardStatus

    rows = await session.execute(
        select(
            CardBatch.created_by,
            func.count(TaxoCard.id),
            func.count(TaxoCard.id).filter(TaxoCard.status == TaxoCardStatus.REDEEMED),
            func.count(TaxoCard.id).filter(TaxoCard.status == TaxoCardStatus.CANCELLED),
            func.coalesce(func.sum(TaxoCard.amount), 0),
            func.coalesce(func.sum(TaxoCard.amount).filter(TaxoCard.status == TaxoCardStatus.REDEEMED), 0),
        )
        .join(TaxoCard, TaxoCard.batch_id == CardBatch.id)
        .where(CardBatch.kind == "pos", CardBatch.country_code == country, CardBatch.created_by.is_not(None))
        .group_by(CardBatch.created_by)
    )
    return {
        user_id: SellerFigures(user_id, int(sold), int(redeemed), int(cancelled), sold_value, redeemed_value)
        for user_id, sold, redeemed, cancelled, sold_value, redeemed_value in rows.all()
    }
