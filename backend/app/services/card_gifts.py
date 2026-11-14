"""**بطاقاتُ الهدية بالكشط** (SPEC §١٠٠-أ/٣، أمرُ المالك ٢٠٢٦-١١-١٣ البند ٣).

**بطاقةُ الهدية تُولَّد لحظةَ إنشائها**: دفعةٌ من بطاقةٍ واحدة (`kind = gift`) بالفئة التي وضعها المالك. **ويُخزَّن رمزُها وحدَه معمًّى**
(Fernet) **حتى يُكشط، ثمّ يُمحى** (قرارُ المالك ٢٠٢٦-١١-١٣). وللتسليم طريقان:

- **رابطٌ خاصّ** `https://taxo.tajora.ly/gift#<الرابط>`. **ما بعد `#` لا يبلغ خادماً**، والصفحةُ ترسله في جسم الطلب. **ولا يُخزَّن الرابط**
  بل بصمتُه، فيظهر نصُّه مرّةً واحدةً لحظةَ الإنشاء. يُرسَل بواتساب أو رسالةٍ أو بريدٍ من جهاز المشرف، **ولا تُستعمل خدمةٌ مدفوعة**.
- **نسخةٌ مطبوعةٌ بمنطقة كشط**: الرمزُ في ردّ الإنشاء مرّةً واحدةً للملفّ، كالدفعة حرفاً، **ولا يُخزَّن**.

**والرمزُ يُجلب من الخادم لحظةَ الكشط وحدَها، مرّةً واحدة**، ثمّ يُمحى المعمّى ويُكتب صفُّ تدقيقٍ **بلا رمز**.
**وترتيبُ الأقفال**: صفُّ الرابط ثمّ صفُّ البطاقة. والاستعمالُ (§٧٣-هـ) يقفل البطاقةَ وحدَها، فلا تنشأ دائرةُ انتظار.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import get_cipher
from app.core.exceptions import AppError, Conflict, InvalidInput, InvalidStatusTransition, NotFound
from app.models.enums import AuditAction, CountryCode, TaxoCardBatchStatus, TaxoCardStatus
from app.models.taxo_card import CardGiftLink, TaxoCard
from app.models.user import User
from app.services import audit, payment_requests, taxo_cards

#: **الرابطُ العامّ** — والرابطُ الخاصُّ بعد `#` فلا يقع في سجلِّ وصول
GIFT_URL = "https://taxo.tajora.ly/gift#{token}"
DESIGNS = ("night", "sunrise", "city")
CHANNELS = ("whatsapp", "sms", "email", "copy")
DELIVERIES = ("link", "print")
#: أقصى صلاحيةٍ لهديةٍ تُنشأ: سنتان، والافتراضُ في اللوحة سنة
MAX_LIFETIME = timedelta(days=731)


class GiftNotFound(NotFound):
    code = "gift_not_found"
    message = "الرابطُ غيرُ صحيح"


class GiftUnavailable(Conflict):
    """**رابطٌ صحيحٌ لا يُكشط الآن**: كُشط من قبل، أو استُعملت بطاقتُه، أو أُلغي، أو انتهت صلاحيتُه."""

    code = "gift_unavailable"
    message = "لا تُكشط هذه البطاقة الآن"


class GiftsNotConfigured(AppError):
    status_code = 503
    code = "gifts_not_configured"
    message = "بطاقاتُ الهدية غيرُ متاحةٍ الآن."


def _now() -> datetime:
    return datetime.now(UTC)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _clean(value: str | None, limit: int) -> str | None:
    text = (value or "").strip()
    return text[:limit] if text else None


def state(link: CardGiftLink | None, card: TaxoCard, now: datetime) -> str:
    """**حالُ الهدية من أوقاتها**، وأوّلُ ما يصدق يحكم: أُلغيت، استُعملت، انتهت، كُشطت، فُتحت، أُرسلت، أُنشئت."""
    if (link is not None and link.cancelled_at is not None) or card.status is TaxoCardStatus.CANCELLED or (
        card.batch.status is TaxoCardBatchStatus.CANCELLED
    ):
        return "cancelled"
    if card.status is TaxoCardStatus.REDEEMED:
        return "redeemed"
    if now >= card.batch.expires_at:
        return "expired"
    if link is None:
        return "printed"
    if link.scratched_at is not None:
        return "scratched"
    if link.opened_at is not None:
        return "opened"
    if link.sent_at is not None:
        return "sent"
    return "created"


@dataclass(slots=True)
class GiftCreated:
    card: TaxoCard
    link: CardGiftLink | None
    #: **الرابطُ مرّةً واحدة** — لطريقة `link` وحدَها
    url: str | None
    #: **الرمزُ مرّةً واحدة** — للنسخة المطبوعة وحدَها، ولا يُخزَّن
    code: str | None


async def create_gift(
    session: AsyncSession,
    *,
    actor: User,
    country: CountryCode,
    denomination_id: uuid.UUID,
    design: str,
    delivery: str,
    expires_at: datetime,
    recipient_name: str | None = None,
    message: str | None = None,
) -> GiftCreated:
    """**هديةٌ تُولَّد الآن**: بطاقةٌ واحدةٌ في دفعةٍ من نوع `gift`. **رمزُها معمًّى حتى يُكشط** للرابط، أو يأتي في الردّ مرّةً للمطبوعة."""
    if design not in DESIGNS:
        raise InvalidInput("التصميمُ غيرُ معروف", field="design")
    if delivery not in DELIVERIES:
        raise InvalidInput("طريقةُ التسليم غيرُ معروفة", field="delivery")
    now = _now()
    if expires_at - now > MAX_LIFETIME:
        raise InvalidInput("صلاحيةُ الهدية سنتان على الأكثر", field="expires_at")
    cipher = None
    if delivery == "link":
        try:
            cipher = get_cipher()
        except AppError as exc:  # **لا هديةَ تُكتب ثمّ يتعذّر تعميةُ رمزها**
            raise GiftsNotConfigured() from exc

    batch, codes = await taxo_cards.create_batch(
        session, actor=actor, country=country, denomination_id=denomination_id, quantity=1, shop_id=None,
        valid_from=now - timedelta(seconds=5), expires_at=expires_at, kind="gift",
    )
    card = await session.scalar(select(TaxoCard).where(TaxoCard.batch_id == batch.id))
    assert card is not None
    serial, code = codes[0]
    if delivery == "print":
        return GiftCreated(card=card, link=None, url=None, code=code)

    assert cipher is not None
    token = secrets.token_urlsafe(24)
    card.code_envelope = cipher.encrypt({"code": taxo_cards.normalize_code(code)})
    link = CardGiftLink(
        card_id=card.id, country_code=country, token_hash=token_hash(token), design=design,
        recipient_name=_clean(recipient_name, 80), message=_clean(message, 200), created_by=actor.id,
    )
    session.add(link)
    await session.flush()
    await audit.record(
        session, actor=actor, action=AuditAction.CREATE, entity_type="card_gift_link", entity_id=link.id,
        details={"serial": serial, "design": design},  # **لا رمزَ ولا رابط**
    )
    return GiftCreated(card=card, link=link, url=GIFT_URL.format(token=token), code=None)


async def get_link(session: AsyncSession, link_id: uuid.UUID, *, for_update: bool = False) -> CardGiftLink:
    stmt = select(CardGiftLink).where(CardGiftLink.id == link_id)
    if for_update:
        stmt = stmt.with_for_update(of=CardGiftLink).execution_options(populate_existing=True)
    link = await session.scalar(stmt)
    if link is None:
        raise NotFound("الهديةُ غيرُ موجودة")
    return link


async def _by_token(session: AsyncSession, token: str | None, *, for_update: bool) -> CardGiftLink:
    raw = (token or "").strip()
    if not 16 <= len(raw) <= 64:
        raise GiftNotFound()
    stmt = select(CardGiftLink).where(CardGiftLink.token_hash == token_hash(raw))
    if for_update:
        stmt = stmt.with_for_update(of=CardGiftLink).execution_options(populate_existing=True)
    link = await session.scalar(stmt)
    if link is None:
        raise GiftNotFound()
    return link


async def mark_sent(session: AsyncSession, *, link: CardGiftLink, channel: str, actor: User) -> CardGiftLink:
    """**أُرسلت**: المشرفُ ضغط زرَّ القناة في اللوحة، والإرسالُ نفسُه من جهازه، فلا خدمةَ مدفوعة."""
    if channel not in CHANNELS:
        raise InvalidInput("القناةُ غيرُ معروفة", field="channel")
    if state(link, link.card, _now()) in ("cancelled", "redeemed", "expired"):
        raise InvalidStatusTransition()
    link.sent_channel = channel
    link.sent_at = _now()
    await audit.record(
        session, actor=actor, action=AuditAction.UPDATE, entity_type="card_gift_link", entity_id=link.id,
        details={"action": "sent", "channel": channel},
    )
    return link


async def open_link(session: AsyncSession, token: str | None) -> tuple[CardGiftLink, str]:
    """**فتحُ الرابط**: يُعيد ما يُرسم (القيمةُ والتصميمُ والاسمُ والرسالة) **بلا رمز**، ويعدّ مرّاتِ الفتح."""
    link = await _by_token(session, token, for_update=True)
    now = _now()
    if link.opened_at is None:
        link.opened_at = now
    link.open_count += 1
    return link, state(link, link.card, now)


async def scratch(session: AsyncSession, token: str | None) -> tuple[CardGiftLink, str]:
    """**الكشطُ مرّةً واحدة**: يُفكّ الرمزُ ويُمحى معمّاه في المعاملة نفسِها، **وصفُّ تدقيقٍ بلا رمز**.

    **قفلُ صفِّ الرابط يسبق فحصَ حاله**: بلا القفل يقرأ كشطان متزامنان «لم يُكشط» معاً، فيخرج الرمزُ مرّتين."""
    link = await _by_token(session, token, for_update=True)
    card = await taxo_cards.get_card(session, link.card_id, for_update=True)
    now = _now()
    current = state(link, card, now)
    if current not in ("created", "sent", "opened"):
        raise GiftUnavailable({
            "scratched": "كُشطت هذه البطاقة من قبل",
            "redeemed": "استُعملت هذه البطاقة من قبل",
            "cancelled": "أُلغيت هذه البطاقة",
            "expired": "انتهت صلاحيةُ هذه البطاقة",
        }.get(current, GiftUnavailable.message))
    if card.code_envelope is None:  # pragma: no cover — بطاقةٌ بلا معمًّى لا تُكشط
        raise GiftUnavailable()
    code = get_cipher().decrypt(card.code_envelope)["code"]
    card.code_envelope = None
    link.scratched_at = now
    if link.opened_at is None:
        link.opened_at = now
    await audit.record(
        session, actor=None, action=AuditAction.READ, entity_type="card_gift_link", entity_id=link.id,
        details={"action": "scratch", "serial": card.serial},  # **لا رمز**
    )
    return link, taxo_cards.printed(code)


async def cancel_link(session: AsyncSession, *, link_id: uuid.UUID, actor: User, reason: str | None) -> CardGiftLink:
    """**إلغاءُ الهدية بسببٍ مكتوب**: تُلغى بطاقتُها ويُمحى معمّاها. **والمستعمَلةُ لا تُلغى**، فمالُها في محفظة صاحبها."""
    link = await get_link(session, link_id, for_update=True)
    card = await taxo_cards.get_card(session, link.card_id, for_update=True)
    if state(link, card, _now()) in ("cancelled", "redeemed"):
        raise InvalidStatusTransition()
    clean = payment_requests.written_reason(reason, field="reason")
    if card.status is TaxoCardStatus.ACTIVE:
        await taxo_cards.cancel_card(session, card=card, actor=actor, reason=clean)
    card.code_envelope = None
    link.cancelled_at = _now()
    link.cancel_reason = clean
    link.cancelled_by = actor.id
    await audit.record(
        session, actor=actor, action=AuditAction.UPDATE, entity_type="card_gift_link", entity_id=link.id,
        details={"action": "cancel", "reason": clean},
    )
    return link


async def list_links(session: AsyncSession, country: CountryCode, *, limit: int = 200) -> list[CardGiftLink]:
    rows = await session.scalars(
        select(CardGiftLink).where(CardGiftLink.country_code == country).order_by(CardGiftLink.created_at.desc()).limit(limit)
    )
    return list(rows.all())
