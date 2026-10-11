"""بطاقاتُ شحن TAXO في اللوحة — الفئاتُ والمحلّاتُ والدفعاتُ والبطاقاتُ والتقريرُ وتنبيهاتُ التخمين (SPEC §٧٣-هـ المرحلة ٢).

**والصلاحيات**: **الفئاتُ وسقوفُ التخمين `settings.write`** (قيمٌ يضعها المالك وحدودٌ أمنيّة)، **والمحلّاتُ والدفعاتُ والإلغاءُ `finance.manage`**
(مالٌ يُسلَّم لمحلٍّ ويُحاسَب عليه)، **والقراءةُ `read.only`**. وكلُّ كتابةٍ تُدقَّق.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.core.currency import currency_for_country
from app.core.deps import DbSession, FinanceManager, ListReader, SettingsWriter
from app.core.exceptions import NotFound
from app.models.enums import AuditAction, CountryCode
from app.models.taxo_card import CardDenomination, CardShop
from app.models.user import User
from app.schemas.payment_request import PaymentReasonIn
from app.schemas.taxo_card import (
    CardBatchCreatedOut,
    CardBatchIn,
    CardBatchOut,
    CardCodeOut,
    CardDenominationActiveIn,
    CardDenominationIn,
    CardDenominationOut,
    CardGuessAlertOut,
    CardShopIn,
    CardShopOut,
    CardShopReportOut,
    CardShopUpdate,
    TaxoCardLimitsIn,
    TaxoCardLimitsOut,
    TaxoCardOut,
)
from app.services import audit, taxo_cards

router = APIRouter(prefix="/admin/taxo-cards", tags=["admin"])


def _denomination_out(row: CardDenomination) -> CardDenominationOut:
    return CardDenominationOut(
        id=row.id, amount=row.amount, currency=currency_for_country(row.country_code), is_active=row.is_active
    )


def _batch_out(row: taxo_cards.BatchFigures) -> CardBatchOut:
    batch = row.batch
    return CardBatchOut(
        id=batch.id, number=batch.number, amount=batch.amount, currency=batch.currency, quantity=batch.quantity,
        shop_id=batch.shop_id, shop_name=batch.shop.name if batch.shop else None,
        discount_percent_at_issue=batch.discount_percent_at_issue, payment_mode_at_issue=batch.payment_mode_at_issue,
        valid_from=batch.valid_from, expires_at=batch.expires_at, status=batch.status, cancel_reason=batch.cancel_reason,
        created_at=batch.created_at, active=row.active, redeemed=row.redeemed, cancelled=row.cancelled,
        redeemed_amount=row.redeemed_value, live_amount=row.live_value, due_amount=row.due_from_shop,
    )


async def _one_batch(session, country: CountryCode, batch_id: uuid.UUID) -> CardBatchOut:
    for row in await taxo_cards.batch_figures(session, country):
        if row.batch.id == batch_id:
            return _batch_out(row)
    raise NotFound("الدفعةُ غيرُ موجودة")  # pragma: no cover


# ------------------------------------------------------------------ الفئات


@router.get("/denominations", response_model=list[CardDenominationOut])
async def list_denominations(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> list[CardDenominationOut]:
    return [_denomination_out(row) for row in await taxo_cards.denominations(session, country)]


@router.post("/denominations", response_model=CardDenominationOut, status_code=status.HTTP_201_CREATED)
async def add_denomination(payload: CardDenominationIn, admin: SettingsWriter, session: DbSession) -> CardDenominationOut:
    row = await taxo_cards.add_denomination(session, actor=admin, country=payload.country_code, amount=payload.amount)
    await session.commit()
    return _denomination_out(row)


@router.patch("/denominations/{denomination_id}", response_model=CardDenominationOut)
async def toggle_denomination(
    denomination_id: uuid.UUID, payload: CardDenominationActiveIn, admin: SettingsWriter, session: DbSession
) -> CardDenominationOut:
    row = await taxo_cards.set_denomination_active(session, actor=admin, denomination_id=denomination_id, active=payload.is_active)
    await session.commit()
    return _denomination_out(row)


# ------------------------------------------------------------------ المحلّات


@router.get("/shops", response_model=list[CardShopOut])
async def list_shops(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> list[CardShopOut]:
    return [CardShopOut.model_validate(row) for row in await taxo_cards.shops(session, country)]


@router.post("/shops", response_model=CardShopOut, status_code=status.HTTP_201_CREATED)
async def create_shop(payload: CardShopIn, admin: FinanceManager, session: DbSession) -> CardShopOut:
    row = CardShop(**payload.model_dump(), is_active=True)
    session.add(row)
    await session.flush()
    await audit.record(
        session, actor=admin, action=AuditAction.CREATE, entity_type="card_shop", entity_id=row.id,
        details=payload.model_dump(mode="json"),
    )
    await session.commit()
    return CardShopOut.model_validate(row)


@router.patch("/shops/{shop_id}", response_model=CardShopOut)
async def update_shop(shop_id: uuid.UUID, payload: CardShopUpdate, admin: FinanceManager, session: DbSession) -> CardShopOut:
    """**تعديلُ المحلّ لا يمسّ دفعةً صدرت** — خصمُها ونمطُها مجمَّدان عليها لحظةَ الإصدار."""
    row = await taxo_cards.get_shop(session, shop_id, for_update=True)
    changes = audit.apply_changes(row, payload.model_dump(exclude_unset=True))
    if changes:
        await audit.record(
            session, actor=admin, action=AuditAction.UPDATE, entity_type="card_shop", entity_id=row.id, changes=changes
        )
    await session.commit()
    return CardShopOut.model_validate(row)


# ------------------------------------------------------------------ الدفعات


@router.get("/batches", response_model=list[CardBatchOut])
async def list_batches(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> list[CardBatchOut]:
    return [_batch_out(row) for row in await taxo_cards.batch_figures(session, country)]


@router.post("/batches", response_model=CardBatchCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_batch(payload: CardBatchIn, admin: FinanceManager, session: DbSession) -> CardBatchCreatedOut:
    """**الرموزُ في هذا الردّ مرّةً واحدة** — تُحفظ ملفاً للطباعة الآن؛ ولا بابَ يعيدها بعده."""
    batch, codes = await taxo_cards.create_batch(
        session, actor=admin, country=payload.country_code, denomination_id=payload.denomination_id,
        quantity=payload.quantity, shop_id=payload.shop_id, valid_from=payload.valid_from, expires_at=payload.expires_at,
    )
    await session.commit()
    return CardBatchCreatedOut(
        batch=await _one_batch(session, payload.country_code, batch.id),
        codes=[CardCodeOut(serial=serial, code=code) for serial, code in codes],
    )


@router.post("/batches/{batch_id}/cancel", response_model=CardBatchOut)
async def cancel_batch(batch_id: uuid.UUID, payload: PaymentReasonIn, admin: FinanceManager, session: DbSession) -> CardBatchOut:
    batch = await taxo_cards.get_batch(session, batch_id, for_update=True)
    await taxo_cards.cancel_batch(session, batch=batch, actor=admin, reason=payload.reason)
    await session.commit()
    return await _one_batch(session, batch.country_code, batch.id)


# ------------------------------------------------------------------ البطاقات


@router.get("/cards", response_model=list[TaxoCardOut])
async def find_cards(
    _r: ListReader, session: DbSession, country: CountryCode = Query(), serial: str = Query(min_length=3, max_length=32)
) -> list[TaxoCardOut]:
    rows = await taxo_cards.find_cards(session, country, serial)
    names = {
        user.id: user.name
        for user in (await session.scalars(select(User).where(User.id.in_({r.redeemed_by for r in rows if r.redeemed_by})))).all()
    } if rows else {}
    return [
        TaxoCardOut(
            id=row.id, serial=row.serial, amount=row.amount, currency=row.currency, status=row.status,
            batch_number=row.batch.number, redeemed_at=row.redeemed_at,
            redeemed_by_name=names.get(row.redeemed_by) if row.redeemed_by else None, cancel_reason=row.cancel_reason,
        )
        for row in rows
    ]


@router.post("/cards/{card_id}/cancel", response_model=TaxoCardOut)
async def cancel_card(card_id: uuid.UUID, payload: PaymentReasonIn, admin: FinanceManager, session: DbSession) -> TaxoCardOut:
    card = await taxo_cards.get_card(session, card_id, for_update=True)
    card = await taxo_cards.cancel_card(session, card=card, actor=admin, reason=payload.reason)
    await session.commit()
    return TaxoCardOut(
        id=card.id, serial=card.serial, amount=card.amount, currency=card.currency, status=card.status,
        batch_number=card.batch.number, redeemed_at=card.redeemed_at, redeemed_by_name=None, cancel_reason=card.cancel_reason,
    )


# ------------------------------------------------------------------ التقريرُ لكلِّ محلّ


@router.get("/report/shops", response_model=list[CardShopReportOut])
async def shop_report(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> list[CardShopReportOut]:
    figures = await taxo_cards.batch_figures(session, country)
    totals = taxo_cards.shop_totals(figures)
    names = {shop.id: shop.name for shop in await taxo_cards.shops(session, country)}
    currency = currency_for_country(country)
    return [
        CardShopReportOut(
            shop_id=shop_id, shop_name=names.get(shop_id, "—"), currency=currency,
            batches=int(t["batches"]), cards=int(t["cards"]), redeemed=int(t["redeemed"]), cancelled=int(t["cancelled"]),
            redeemed_amount=t["redeemed_value"], live_amount=t["live_value"], due_amount=t["due_from_shop"],
        )
        for shop_id, t in totals.items()
    ]


# ------------------------------------------------------------------ التخمين


@router.get("/alerts", response_model=list[CardGuessAlertOut])
async def list_alerts(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> list[CardGuessAlertOut]:
    rows = await taxo_cards.alerts(session, country)
    users = {
        user.id: user
        for user in (await session.scalars(select(User).where(User.id.in_({r.user_id for r in rows if r.user_id})))).all()
    } if rows else {}
    return [
        CardGuessAlertOut(
            id=row.id, scope=row.scope, user_name=users[row.user_id].name if row.user_id in users else None,
            user_phone=users[row.user_id].phone if row.user_id in users else None, ip=row.ip, attempts=row.attempts,
            created_at=row.created_at, reviewed_at=row.reviewed_at,
        )
        for row in rows
    ]


@router.post("/alerts/{alert_id}/review", response_model=CardGuessAlertOut)
async def review_alert(alert_id: uuid.UUID, admin: FinanceManager, session: DbSession) -> CardGuessAlertOut:
    row = await taxo_cards.review_alert(session, alert_id=alert_id, actor=admin)
    await session.commit()
    owner = await session.get(User, row.user_id) if row.user_id else None
    return CardGuessAlertOut(
        id=row.id, scope=row.scope, user_name=owner.name if owner else None, user_phone=owner.phone if owner else None,
        ip=row.ip, attempts=row.attempts, created_at=row.created_at, reviewed_at=row.reviewed_at,
    )


@router.get("/limits", response_model=TaxoCardLimitsOut)
async def get_limits(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> TaxoCardLimitsOut:
    row = await taxo_cards.limits_for(session, country)
    return TaxoCardLimitsOut(
        max_wrong_per_account=row.max_wrong_per_account, max_wrong_per_ip=row.max_wrong_per_ip, window_minutes=row.window_minutes
    )


@router.put("/limits", response_model=TaxoCardLimitsOut)
async def save_limits(payload: TaxoCardLimitsIn, admin: SettingsWriter, session: DbSession) -> TaxoCardLimitsOut:
    changes = payload.model_dump(exclude_unset=True, exclude={"country_code"}, exclude_none=True)
    row = await taxo_cards.save_limits(session, actor=admin, country=payload.country_code, changes=changes)
    await session.commit()
    return TaxoCardLimitsOut(
        max_wrong_per_account=row.max_wrong_per_account, max_wrong_per_ip=row.max_wrong_per_ip, window_minutes=row.window_minutes
    )
