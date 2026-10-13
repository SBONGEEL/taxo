"""«قيد التحويل» — متى تُسحب أجرةُ رحلةٍ دُفعت عبر المنصّة (SPEC §٧٤-ي، أمرُ المالك §٧٤-ط/٦).

**الأجرةُ تدخل محفظةَ الكبتن فوراً كما كانت** (`payments._distribute`: أجرٌ كاملٌ ثمّ عمولتُه) — **ولا يتغيّر قيدٌ ولا يُكتب قيد**.
الذي يتغيّر **متى تُسحب**: `wallet_settings.earnings_hold_days` لكلِّ سوق — صفرٌ «فوري»، وغيرُه «بعد مدّة» بعدد أيّامه.

**وما هو «قيد التحويل»**: لكلِّ رحلةٍ قُيِّد أجرُها (`ride_earning`) في محفظة الكبتن منذ أقلَّ من المدّة — **صافيها**: الأجرُ ناقصاً عمولتَها
المقيَّدة على الرحلة نفسِها في المحفظة نفسِها. **ويصير متاحاً لحظةَ يكمل قيدُ أجرها المدّة** (`created_at + الأيّام`) — لا بعد منتصف ليل.
**والنقدُ لا يدخل هنا أصلاً**: رحلةُ النقد لا قيدَ أجرٍ لها (المالُ في يده)، فلا شيءَ منها «قيد التحويل».

**وحدودُه مكتوبة**:
- **المدّةُ تُقرأ الآن لا يومَ الرحلة** — فتغييرُها في اللوحة يسري على ما هو «قيد التحويل» الآن أيضاً، وتتحرّك تواريخُه معه (§٧٤-ي/٣).
- **ولا يزيد «قيد التحويل» على الرصيد**: ما خرج من المحفظة بعد الأجر (سلفةٌ اقتُطعت، اشتراكٌ اشتُري منها) خرج — فيُعدّ الأحدثُ هو
  الباقي، ويُقصّ «قيد التحويل» من أقدمه حتى لا يتجاوز الرصيد.
- **وبابان يحسبانه بقاعدةٍ واحدة**: هذا لكبتنٍ واحد (`withdrawals.available_balance` وبطاقةُ محفظته)، و`finance_summary` لكلِّ الكباتن
  في SQL — **ويُقارَنان باختبار** (`test_earnings_hold.py`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode, WalletOwnerType, WalletTransactionType
from app.models.wallet import WalletTransaction
from app.models.wallet_setting import WalletSetting
from app.services.pricing import as_money

#: **ما يُحسب صافياً لكلِّ رحلة** — الأجرُ وعمولتُه في محفظة الكبتن
NET_TYPES = (WalletTransactionType.RIDE_EARNING, WalletTransactionType.COMMISSION)

ZERO = Decimal("0.000")


@dataclass(frozen=True, slots=True)
class Release:
    """**مبلغٌ يصير متاحاً للسحب في ساعته** — والساعةُ مقرَّبةٌ للأعلى، فلا يُقال «متاحٌ» قبل أن يكون."""

    available_at: datetime
    amount: Decimal


@dataclass(frozen=True, slots=True)
class InTransit:
    days: int
    total: Decimal = ZERO
    releases: list[Release] = field(default_factory=list)


async def hold_days(session: AsyncSession, country: CountryCode) -> int:
    """**المدّةُ من إعداد السوق قراءةً** — وغيابُ الصفّ «فوري»، **ولا يُنشأ صفٌّ** (هذه قراءة)."""
    value = await session.scalar(select(WalletSetting.earnings_hold_days).where(WalletSetting.country_code == country))
    return int(value or 0)


def _now() -> datetime:
    """ساعةُ الحساب — **دالّةٌ لا نداءٌ مدفون**: الدفترُ لا يُعدَّل حتى في الاختبار (`append-only`)، فيُقدَّم الزمنُ لا القيد."""
    return datetime.now(UTC)


def _ceil_hour(moment: datetime) -> datetime:
    floored = moment.replace(minute=0, second=0, microsecond=0)
    return floored if floored == moment else floored + timedelta(hours=1)


async def in_transit(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    country: CountryCode,
    balance: Decimal,
    now: datetime | None = None,
) -> InTransit:
    """**«قيد التحويل» لكبتنٍ واحد** — مجموعُه وتواريخُ إتاحته، **مقصوصاً إلى رصيده** (`balance`)."""
    days = await hold_days(session, country)
    if days <= 0:
        return InTransit(days=0)
    moment = now or _now()
    cutoff = moment - timedelta(days=days)
    tx = WalletTransaction
    recent = (
        select(tx.ride_id)
        .where(
            tx.owner_id == user_id,
            tx.owner_type == WalletOwnerType.DRIVER,
            tx.type == WalletTransactionType.RIDE_EARNING,
            tx.created_at > cutoff,
            tx.ride_id.is_not(None),
        )
        .scalar_subquery()
    )
    earned_at = func.min(tx.created_at).filter(tx.type == WalletTransactionType.RIDE_EARNING)
    rows = (
        await session.execute(
            select(earned_at, func.sum(tx.amount))
            .where(
                tx.owner_id == user_id,
                tx.owner_type == WalletOwnerType.DRIVER,
                tx.type.in_(NET_TYPES),
                tx.ride_id.in_(recent),
            )
            .group_by(tx.ride_id)
        )
    ).all()

    # **الأحدثُ هو الباقي في المحفظة**: يُعدّ من الأحدث إلى الأقدم حتى يبلغ الرصيد
    room = max(ZERO, as_money(balance))
    kept: dict[datetime, Decimal] = {}
    for when, net in sorted(rows, key=lambda row: row[0], reverse=True):
        amount = min(max(ZERO, as_money(net)), room)
        if amount <= 0:
            continue
        room -= amount
        release = _ceil_hour(when + timedelta(days=days))
        kept[release] = kept.get(release, ZERO) + amount
    releases = [Release(available_at=when, amount=as_money(amount)) for when, amount in sorted(kept.items())]
    return InTransit(days=days, total=as_money(sum((r.amount for r in releases), ZERO)), releases=releases)
