"""بطاقاتُ شحن TAXO في اللوحة — الفئاتُ والمحلّاتُ والدفعاتُ والبطاقاتُ والتقريرُ وتنبيهاتُ التخمين (SPEC §٧٣-هـ المرحلة ٢).

**والصلاحيات**: **الفئاتُ وسقوفُ التخمين `settings.write`** (قيمٌ يضعها المالك وحدودٌ أمنيّة)، **والمحلّاتُ والدفعاتُ والإلغاءُ `finance.manage`**
(مالٌ يُسلَّم لمحلٍّ ويُحاسَب عليه)، **والقراءةُ `read.only`**. وكلُّ كتابةٍ تُدقَّق.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from fastapi.responses import Response
from sqlalchemy import select

from app.core.currency import currency_for_country
from app.core.deps import DbSession, FinanceManager, ListReader, OwnerUser, RedisDep, SettingsWriter
from app.core.exceptions import NotFound
from app.models.enums import AuditAction, CountryCode
from app.models.taxo_card import CardDenomination, CardShop
from app.models.user import User
from app.schemas.payment_request import PaymentReasonIn
from app.schemas.taxo_card import (
    CardBatchExtendIn,
    CardKindReportOut,
    InvoiceSettingsIn,
    InvoiceSettingsOut,
    PosSettingsIn,
    PosSettingsOut,
    SellerActiveIn,
    SellerCreateIn,
    SellerOut,
    BatchCardsOut,
    CardExportIn,
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
    GiftCreatedOut,
    GiftCreateIn,
    GiftLinkOut,
    GiftSentIn,
    TaxoCardLimitsIn,
    TaxoCardLimitsOut,
    TaxoCardOut,
)
from app.services import audit, card_gifts, card_sellers, taxo_cards

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
        unused=row.unused, expired=row.expired,
        redeemed_amount=row.redeemed_value, live_amount=row.live_value, due_amount=row.due_from_shop, kind=batch.kind,
        buyer_company=batch.buyer_company, buyer_tax_number=batch.buyer_tax_number,
        invoice_number=(
            f"INV-{batch.country_code.value}-{batch.invoice_number:06d}" if batch.invoice_number is not None else None
        ),
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
        buyer_company=payload.buyer_company, buyer_tax_number=payload.buyer_tax_number,
    )
    await session.commit()
    return CardBatchCreatedOut(
        batch=await _one_batch(session, payload.country_code, batch.id),
        codes=[CardCodeOut(serial=serial, code=code) for serial, code in codes],
    )


@router.post("/batches/{batch_id}/export")
async def export_batch(batch_id: uuid.UUID, payload: CardExportIn, admin: FinanceManager, session: DbSession) -> Response:
    """**ملفُّ الدفعة لحظةَ إنشائها وحدَها** (SPEC §١٠٠-أ/١) — Excel أو PDF أو ورقةُ المطبعة، كلُّها بكلمة سرّ؛ **ولا يُعاد بعد ذلك**."""
    batch = await taxo_cards.get_batch(session, batch_id)
    content, media, name = await taxo_cards.export_batch(
        session, batch=batch, actor=admin, fmt=payload.format, password=payload.password,
        codes=[(row.serial, row.code) for row in payload.codes], design=payload.design,
    )
    await session.commit()
    return Response(
        content=content, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "private, no-store"},
    )


@router.post("/batches/{batch_id}/cancel", response_model=CardBatchOut)
async def cancel_batch(batch_id: uuid.UUID, payload: PaymentReasonIn, admin: FinanceManager, session: DbSession) -> CardBatchOut:
    batch = await taxo_cards.get_batch(session, batch_id, for_update=True)
    await taxo_cards.cancel_batch(session, batch=batch, actor=admin, reason=payload.reason)
    await session.commit()
    return await _one_batch(session, batch.country_code, batch.id)


# ------------------------------------------------------------------ البطاقات


async def _origins(session, batches) -> dict:
    """**من باع البطاقةَ ومتى** (§١٠٠-ب/٤) — من دفعتها: المحلُّ ونوعُها، ومن أصدرها ووقتُ إصدارها."""
    ids = {b.created_by for b in batches if b.created_by}
    names = (
        {u.id: u.name for u in (await session.scalars(select(User).where(User.id.in_(ids)))).all()} if ids else {}
    )
    return {
        b.id: {
            "batch_kind": b.kind, "shop_name": b.shop.name if b.shop else None,
            "issued_by_name": names.get(b.created_by) if b.created_by else None, "issued_at": b.created_at,
        }
        for b in batches
    }


@router.get("/batches/{batch_id}/cards", response_model=BatchCardsOut)
async def batch_cards(
    batch_id: uuid.UUID,
    _r: ListReader,
    session: DbSession,
    q: str | None = Query(None, max_length=64),
    state: str | None = Query(None, pattern="^(unused|redeemed|expired|cancelled|not_started)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> BatchCardsOut:
    """**صفحةُ «دفعات البطاقات»** (SPEC §١٠٠-أ/٢) — بطاقاتُ دفعةٍ بالتسلسل والحال ومن استعملها ومتى؛ **ولا رمزَ ولا زرَّ كشف**."""
    batch = await taxo_cards.get_batch(session, batch_id)
    rows, total = await taxo_cards.batch_cards(session, batch=batch, query=q, state=state, offset=offset, limit=limit)
    origin = (await _origins(session, [batch]))[batch.id]
    return BatchCardsOut(
        total=total,
        cards=[
            TaxoCardOut(
                id=card.id, serial=card.serial, amount=card.amount, currency=card.currency, status=card.status,
                batch_number=batch.number, redeemed_at=card.redeemed_at, redeemed_by_name=name,
                cancel_reason=card.cancel_reason, state=card_state, **origin,
            )
            for card, card_state, name in rows
        ],
    )


@router.get("/cards", response_model=list[TaxoCardOut])
async def find_cards(
    _r: ListReader, session: DbSession, country: CountryCode = Query(), serial: str = Query(min_length=3, max_length=32)
) -> list[TaxoCardOut]:
    rows = await taxo_cards.find_cards(session, country, serial)
    names = {
        user.id: user.name
        for user in (await session.scalars(select(User).where(User.id.in_({r.redeemed_by for r in rows if r.redeemed_by})))).all()
    } if rows else {}
    origins = await _origins(session, [row.batch for row in rows])
    return [
        TaxoCardOut(
            id=row.id, serial=row.serial, amount=row.amount, currency=row.currency, status=row.status,
            batch_number=row.batch.number, redeemed_at=row.redeemed_at,
            redeemed_by_name=names.get(row.redeemed_by) if row.redeemed_by else None, cancel_reason=row.cancel_reason,
            **origins[row.batch_id],
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


# ------------------------------------------------------------------ بطاقاتُ الهدية (§١٠٠-أ/٣)


def gift_out(link, card) -> GiftLinkOut:
    from datetime import UTC, datetime

    return GiftLinkOut(
        id=link.id, card_id=card.id, serial=card.serial, amount=card.amount, currency=card.currency, design=link.design,
        recipient_name=link.recipient_name, message=link.message, state=card_gifts.state(link, card, datetime.now(UTC)),
        sent_channel=link.sent_channel, created_at=link.created_at, sent_at=link.sent_at, opened_at=link.opened_at,
        open_count=link.open_count, scratched_at=link.scratched_at, redeemed_at=card.redeemed_at,
        expires_at=card.batch.expires_at, cancelled_at=link.cancelled_at, cancel_reason=link.cancel_reason,
    )


@router.get("/gifts", response_model=list[GiftLinkOut])
async def list_gifts(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> list[GiftLinkOut]:
    """**الهدايا بحالها**: أُنشئت، أُرسلت، فُتحت، كُشطت، استُعملت، أُلغيت. بلا رمزٍ ولا رابط."""
    return [gift_out(link, link.card) for link in await card_gifts.list_links(session, country)]


@router.post("/gifts", response_model=GiftCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_gift(payload: GiftCreateIn, admin: FinanceManager, session: DbSession) -> GiftCreatedOut:
    """**هديةٌ تُولَّد الآن**: الرابطُ (أو الرمزُ للمطبوعة) في هذا الردّ مرّةً واحدة."""
    made = await card_gifts.create_gift(
        session, actor=admin, country=payload.country_code, denomination_id=payload.denomination_id, design=payload.design,
        delivery=payload.delivery, expires_at=payload.expires_at, recipient_name=payload.recipient_name, message=payload.message,
    )
    await session.commit()
    card = await taxo_cards.get_card(session, made.card.id)
    gift = None
    if made.link is not None:
        gift = gift_out(await card_gifts.get_link(session, made.link.id), card)
    return GiftCreatedOut(
        gift=gift, batch_id=card.batch_id, serial=card.serial, url=made.url,
        code=CardCodeOut(serial=card.serial, code=made.code) if made.code else None,
    )


@router.post("/gifts/{link_id}/sent", response_model=GiftLinkOut)
async def gift_sent(link_id: uuid.UUID, payload: GiftSentIn, admin: FinanceManager, session: DbSession) -> GiftLinkOut:
    link = await card_gifts.get_link(session, link_id, for_update=True)
    await card_gifts.mark_sent(session, link=link, channel=payload.channel, actor=admin)
    await session.commit()
    link = await card_gifts.get_link(session, link_id)
    return gift_out(link, link.card)


@router.post("/gifts/{link_id}/cancel", response_model=GiftLinkOut)
async def cancel_gift(link_id: uuid.UUID, payload: PaymentReasonIn, admin: FinanceManager, session: DbSession) -> GiftLinkOut:
    """**إلغاءُ الهدية بسببٍ مكتوب**: يُلغى الرابطُ وبطاقتُه، ويُمحى الرمزُ المعمّى."""
    await card_gifts.cancel_link(session, link_id=link_id, actor=admin, reason=payload.reason)
    await session.commit()
    link = await card_gifts.get_link(session, link_id)
    await session.refresh(link.card)
    return gift_out(link, link.card)


# ------------------------------------------------------------------ البائعون والبيعُ لحظةَ الطلب (§١٠٠-ب/٤–٥)


@router.get("/pos-settings", response_model=PosSettingsOut)
async def get_pos_settings(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> PosSettingsOut:
    row = await card_sellers.pos_settings(session, country)
    return PosSettingsOut(pos_enabled=row.enabled, pos_daily_cap=row.daily_cap, pos_validity_days=row.validity_days)


@router.put("/pos-settings", response_model=PosSettingsOut)
async def save_pos_settings(payload: PosSettingsIn, owner: OwnerUser, session: DbSession) -> PosSettingsOut:
    """**فتحُ البيع في المحلّات للمالك وحدَه** (§١٠٠-ب/٥) — كلُّ بيعٍ يولّد رمزاً يشحن محفظة."""
    changes = payload.model_dump(exclude_unset=True, exclude={"country_code"}, exclude_none=True)
    row = await card_sellers.save_pos_settings(session, actor=owner, country=payload.country_code, changes=changes)
    await session.commit()
    return PosSettingsOut(pos_enabled=row.enabled, pos_daily_cap=row.daily_cap, pos_validity_days=row.validity_days)


async def _seller_out(session, staff, user, figures=None) -> SellerOut:
    from app.models.admin_credential import AdminCredential
    from app.services import totp

    # **بعد الإيداع تنتهي صلاحيةُ الصفّين** — والتحميلُ الكسولُ لا يعمل في جلسةٍ غيرِ متزامنة
    await session.refresh(staff)
    await session.refresh(user)
    credential = await session.scalar(select(AdminCredential).where(AdminCredential.user_id == user.id))
    f = figures.get(user.id) if figures else None
    return SellerOut(
        id=staff.id, user_id=user.id, name=user.name, username=credential.username if credential else None,
        shop_id=staff.shop_id, shop_name=staff.shop.name, is_active=staff.is_active, is_blocked=user.is_blocked,
        has_factor=await totp.has_confirmed_factor(session, user.id),
        must_change_password=bool(credential and credential.must_change_password), created_at=staff.created_at,
        currency=currency_for_country(staff.shop.country_code),
        sold=f.sold if f else 0, redeemed=f.redeemed if f else 0, cancelled=f.cancelled if f else 0,
        sold_amount=f.sold_value if f else 0, redeemed_amount=f.redeemed_value if f else 0,
    )


@router.get("/sellers", response_model=list[SellerOut])
async def list_sellers(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> list[SellerOut]:
    """**البائعون ومبيعاتُ كلٍّ منهم** (§١٠٠-ب/٥) — عددٌ وقيمةٌ اسميّة؛ وما يستحقّه المحلُّ في «تقرير المحلّات»."""
    figures = await card_sellers.seller_figures(session, country)
    return [await _seller_out(session, staff, user, figures) for staff, user in await card_sellers.sellers(session, country)]


@router.post("/sellers", response_model=SellerOut, status_code=status.HTTP_201_CREATED)
async def create_seller(payload: SellerCreateIn, owner: OwnerUser, session: DbSession, redis: RedisDep) -> SellerOut:
    """**ينشئه المالكُ بيده** — الاسمُ واسمُ الدخول وكلمةٌ مؤقّتة؛ والعاملُ الثاني يُسجَّل عند أوّل دخول قبل أيِّ صفحة."""
    staff, user, _username = await card_sellers.create_seller(
        session, redis, actor=owner, shop_id=payload.shop_id, name=payload.name, username=payload.username,
        password=payload.password,
    )
    await session.commit()
    return await _seller_out(session, staff, user)


@router.post("/sellers/{staff_id}/active", response_model=SellerOut)
async def set_seller_active(staff_id: uuid.UUID, payload: SellerActiveIn, owner: OwnerUser, session: DbSession) -> SellerOut:
    staff = await card_sellers.set_seller_active(session, actor=owner, staff_id=staff_id, active=payload.is_active)
    user_id = staff.user_id
    await session.commit()
    user = await session.get(User, user_id)
    return await _seller_out(session, staff, user)


# ------------------------------------------------------------------ بطاقاتُ الشركات بفاتورة (§١٠٠-ب/٧)


@router.get("/batches/{batch_id}/invoice")
async def batch_invoice(batch_id: uuid.UUID, _r: ListReader, session: DbSession) -> Response:
    """**فاتورةُ دفعةٍ بيعت لشركة** — بلا رمزٍ واحد، فتُنزَّل متى طُلبت."""
    batch = await taxo_cards.get_batch(session, batch_id)
    content, name = await taxo_cards.batch_invoice(session, batch=batch)
    return Response(
        content=content, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "private, no-store"},
    )


@router.get("/invoice-settings", response_model=InvoiceSettingsOut)
async def get_invoice_settings(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> InvoiceSettingsOut:
    from app.models.taxo_card import TaxoCardSetting

    row = await session.scalar(select(TaxoCardSetting).where(TaxoCardSetting.country_code == country))
    return InvoiceSettingsOut(
        invoice_seller_name=row.invoice_seller_name if row else None,
        invoice_seller_tax_number=row.invoice_seller_tax_number if row else None,
    )


@router.put("/invoice-settings", response_model=InvoiceSettingsOut)
async def save_invoice_settings(payload: InvoiceSettingsIn, owner: OwnerUser, session: DbSession) -> InvoiceSettingsOut:
    """**بياناتُ الشركة على الفاتورة يكتبها المالك وحدَه** — لا تُخترع."""
    changes = {
        key: (value.strip() or None) if isinstance(value, str) else value
        for key, value in payload.model_dump(exclude_unset=True, exclude={"country_code"}).items()
    }
    row = await card_sellers.save_pos_settings(session, actor=owner, country=payload.country_code, changes=changes)
    del row
    await session.commit()
    return await get_invoice_settings(owner, session, payload.country_code)


# ------------------------------------------------------------------ الصلاحية والتقرير (§١٠٠-ب/١٢ و١٤)


@router.get("/expiring", response_model=list[CardBatchOut])
async def expiring_batches(
    _r: ListReader, session: DbSession, country: CountryCode = Query(), days: int = Query(30, ge=1, le=365)
) -> list[CardBatchOut]:
    """**تذكيرُ الصلاحية في اللوحة** — دفعاتٌ وهدايا وبطاقاتُ بيعٍ تنتهي خلال `days` يوماً وفيها ما لم يُستعمل."""
    from datetime import timedelta

    figures = await taxo_cards.batch_figures(session, country)
    return [_batch_out(row) for row in taxo_cards.expiring(figures, within=timedelta(days=days))]


@router.post("/batches/{batch_id}/extend", response_model=CardBatchOut)
async def extend_batch(batch_id: uuid.UUID, payload: CardBatchExtendIn, admin: FinanceManager, session: DbSession) -> CardBatchOut:
    batch = await taxo_cards.get_batch(session, batch_id, for_update=True)
    country = batch.country_code
    await taxo_cards.extend_batch(session, batch=batch, actor=admin, expires_at=payload.expires_at, reason=payload.reason)
    await session.commit()
    return await _one_batch(session, country, batch_id)


@router.get("/report/kinds", response_model=list[CardKindReportOut])
async def kind_report(_r: ListReader, session: DbSession, country: CountryCode = Query()) -> list[CardKindReportOut]:
    """**تقريرُ البطاقات بالنوع** (§١٠٠-ب/١٤) — والمحلّاتُ في `report/shops`، والبائعون في `sellers`، والدفعةُ في قائمتها."""
    from decimal import ROUND_HALF_UP, Decimal

    totals = taxo_cards.kind_totals(await taxo_cards.batch_figures(session, country))
    currency = currency_for_country(country)
    out = []
    for kind, t in totals.items():
        live = int(t["cards"]) - int(t["cancelled"])
        rate = (Decimal(int(t["redeemed"]) * 100) / Decimal(live)).quantize(Decimal("0.1"), ROUND_HALF_UP) if live else Decimal("0")
        out.append(CardKindReportOut(
            kind=kind, currency=currency, batches=int(t["batches"]), cards=int(t["cards"]), redeemed=int(t["redeemed"]),
            cancelled=int(t["cancelled"]), unused=int(t["unused"]), expired=int(t["expired"]), redemption_rate=str(rate),
            issued_amount=t["issued_value"], redeemed_amount=t["redeemed_value"], outstanding_amount=t["outstanding_value"],
            expired_amount=t["expired_value"],
        ))
    return out
