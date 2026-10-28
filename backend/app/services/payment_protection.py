"""**حمايةُ الدفع** (SPEC §٨٧، أمرُ المالك ٢٠٢٦-١٠-٢٨) — صحّةُ كلِّ طريقةٍ في كلِّ سوق، والمطابقةُ اليوميّة، ومراقبةُ SofizPay الحيّة.

**ثلاثةُ أبوابٍ كلُّها قراءة** — لا يكتب واحدٌ منها في الدفتر ولا يغيّر حالَ دفعةٍ بنفسه:

1. **`health`** — نسبةُ النجاح لكلِّ طريقةٍ لليوم (بيوم البلد) والأسبوع والشهر، ومعها الحالُ الآن: مفعَّلةٌ أم مخفيّةٌ ولماذا، والوسيطُ
   متوقّفٌ أم قائم، والإخفاقاتُ المتتالية.
2. **`reconcile_daily`** — **تقريرٌ لا تصحيح**: كلُّ دفعةٍ عند وسيطٍ في آخر ٤٨ ساعة يُسأل عنها الوسيطُ ويُقارن جوابُه بما عندنا. والافتراقُ
   يُكتب بتفصيله ويُشعَر المالك؛ **والتصحيحُ يمرّ بأبوابه المبنيّة** (التسويةُ الدوريّةُ تقيِّد ما دُفع ولم يُقيَّد مرّةً واحدة).
3. **`watch_sofizpay`** — **التأكيدُ أسرع**: كلَّ عشرين ثانيةً يُسأل Stellar عمّا وصل حسابَ SofizPay بعد آخر مؤشّر (كـ`setup_transaction_stream`
   في الـSDK، وهو نفسُه سؤالٌ دوريّ)؛ **وصولُ دفعةٍ يوقظ حسمَ الطلبات المعلّقة بفحصها المباشر** — فالحقيقةُ جوابُ الوسيط لا المراقبة،
   والتسويةُ كلَّ دقيقتين شبكةُ الأمان كما هي.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode, PaymentRequestStatus, ProviderKey
from app.models.gateway_reconciliation import GatewayReconciliation
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.provider_credential import ProviderCredential
from app.services import gateway_health, payment_breaker, payment_gateways

logger = logging.getLogger(__name__)

WINDOWS = ("today", "week", "month")
#: **نافذةُ المطابقة** — يومان: دفعةُ أمسِ الليلِ تُرى في تقرير اليوم ولو حُسمت بعد منتصفه
RECONCILE_HOURS = 48
#: **ما فُتح في آخر نصف ساعةٍ لا يُطابَق** — ما زال صاحبُه في صفحة الوسيط
RECONCILE_SETTLE_MINUTES = 30
RECONCILE_LIMIT = 500


def _now() -> datetime:
    return datetime.now(UTC)


# ═════════════════════════ ١ — الصحّة


async def health(session: AsyncSession, country: CountryCode) -> dict[str, Any]:
    from app.services import stats

    zone = await stats._zone(session, country)
    now = _now()
    providers = (
        await session.scalars(
            select(PayMethod).where(PayMethod.country_code == country).order_by(PayMethod.sort_order, PayMethod.name)
        )
    ).all()
    counts: dict[str, dict[uuid.UUID, dict[str, int]]] = {}
    for window in WINDOWS:
        start, _ = stats._window(zone, window, now)
        rows = (
            await session.execute(
                select(
                    PaymentRequest.provider_id,
                    PaymentRequest.status,
                    PaymentRequest.gateway_paid_at.is_not(None),
                    func.count(),
                )
                .where(PaymentRequest.country_code == country, PaymentRequest.created_at >= start)
                .group_by(PaymentRequest.provider_id, PaymentRequest.status, PaymentRequest.gateway_paid_at.is_not(None))
            )
        ).all()
        per: dict[uuid.UUID, dict[str, int]] = {}
        for provider_id, status, paid_at_gateway, n in rows:
            bucket = per.setdefault(provider_id, {"opened": 0, "paid": 0, "failed": 0, "cancelled": 0, "pending": 0, "processing": 0})
            bucket["opened"] += n
            if status in (PaymentRequestStatus.APPROVED, PaymentRequestStatus.REFUNDED):
                bucket["paid"] += n
            elif status is PaymentRequestStatus.REJECTED:
                bucket["failed"] += n
            elif status is PaymentRequestStatus.CANCELLED:
                bucket["cancelled"] += n
            elif paid_at_gateway:
                bucket["processing"] += n
            else:
                bucket["pending"] += n
        counts[window] = per
    methods = []
    for provider in providers:
        stats_by_window = {}
        for window in WINDOWS:
            bucket = counts[window].get(provider.id) or {"opened": 0, "paid": 0, "failed": 0, "cancelled": 0, "pending": 0, "processing": 0}
            decided = bucket["paid"] + bucket["failed"]
            # **النسبةُ من المحسوم** (دُفع أو رُفض) — من عاد ولم يُكمل لا يُحسب على الطريقة؛ ولا محسومَ ⇐ لا نسبة
            bucket["success_rate"] = round(bucket["paid"] * 100 / decided) if decided else None
            stats_by_window[window] = bucket
        methods.append(
            {
                "id": provider.id,
                "name": provider.name,
                "code": provider.code,
                "integration": provider.integration,
                "enabled": provider.enabled,
                "hidden_reason": provider.hidden_reason,
                "hidden_at": provider.hidden_at,
                "hidden_auto": provider.hidden_auto,
                "gateway_down": bool(provider.integration) and await gateway_health.is_down(provider.integration or "", country),
                "failure_streak": await payment_breaker.failure_streak(session, provider.id) if provider.integration else 0,
                "windows": stats_by_window,
            }
        )
    return {"country_code": country, "streak_limit": payment_breaker.FAILURE_STREAK, "methods": methods}


# ═════════════════════════ ٢ — المطابقةُ اليوميّة


async def _contracts(session: AsyncSession) -> list[tuple[str, CountryCode]]:
    found = []
    for integration, key in payment_gateways.PROVIDER_KEYS.items():
        rows = (
            await session.scalars(
                select(ProviderCredential.country_code).where(
                    ProviderCredential.provider_key == key, ProviderCredential.is_active.is_(True)
                )
            )
        ).all()
        found.extend((integration, CountryCode(code)) for code in rows if code is not None)
    return found


def _classify(row: PaymentRequest, event) -> tuple[str | None, str]:
    """**ما عندنا مقابلَ ما يقوله الوسيط** ⇐ (نوعُ الافتراق أو `None`، وما قاله الوسيط بكلمة)."""
    ours_paid = row.status in (PaymentRequestStatus.APPROVED, PaymentRequestStatus.REFUNDED)
    theirs = "pending" if event is None else event.outcome.value
    theirs_paid = event is not None and event.outcome is PaymentRequestStatus.APPROVED
    if ours_paid and not theirs_paid:
        # **أخطرُ الافتراقين**: قُيِّد عندنا ولا يقول الوسيطُ «دُفع»
        return "credited_not_paid", theirs
    if theirs_paid and not ours_paid:
        return ("processing" if row.gateway_paid_at is not None else "paid_not_credited"), theirs
    if ours_paid and theirs_paid and event.amount is not None and row.credited_amount is not None:
        if Decimal(event.amount).quantize(Decimal("0.001")) != row.credited_amount:
            return "amount", theirs
    return None, theirs


async def reconcile_one(
    session: AsyncSession, integration: str, country: CountryCode, *, trigger: str = "daily", now: datetime | None = None
) -> GatewayReconciliation:
    moment = now or _now()
    start = moment - timedelta(hours=RECONCILE_HOURS)
    end = moment - timedelta(minutes=RECONCILE_SETTLE_MINUTES)
    report = GatewayReconciliation(
        integration=integration, country_code=country, window_start=start, window_end=end, trigger=trigger, details={},
        checked=0, matched=0, mismatched=0, unreachable=0,
    )
    items: list[dict[str, Any]] = []
    try:
        gateway = await payment_gateways.gateway_for(session, integration, country)
    except payment_gateways.GatewayUnavailable:
        report.details = {"error": "no_contract"}
        session.add(report)
        await session.commit()
        return report
    rows = (
        await session.scalars(
            select(PaymentRequest)
            .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
            .where(
                PayMethod.integration == integration,
                PaymentRequest.country_code == country,
                PaymentRequest.external_id.is_not(None),
                PaymentRequest.created_at >= start,
                PaymentRequest.created_at < end,
            )
            .order_by(PaymentRequest.created_at)
            .limit(RECONCILE_LIMIT)
        )
    ).all()
    ours_total = Decimal("0.000")
    ours_count = 0
    from app.services import payment_requests

    for row in rows:
        report.checked += 1
        if row.status in (PaymentRequestStatus.APPROVED, PaymentRequestStatus.REFUNDED):
            ours_total += row.credited_amount or row.amount
            ours_count += 1
        try:
            event = await gateway.check(row.external_id or "")
        except (payment_gateways.GatewayError, payment_gateways.GatewayUnavailable):
            report.unreachable += 1
            continue
        kind, theirs = _classify(row, event)
        if kind is None:
            report.matched += 1
            continue
        report.mismatched += 1
        items.append(
            {
                "kind": kind,
                "request_id": str(row.id),
                "ref": payment_requests.public_ref(row.id),
                "ours": row.status.value,
                "theirs": theirs,
                "amount": str(row.amount),
                "gateway_amount": str(event.amount) if event is not None and event.amount is not None else None,
                "created_at": row.created_at.isoformat(),
            }
        )
    details: dict[str, Any] = {"items": items, "ours": {"paid_count": ours_count, "paid_total": str(ours_total)}}
    if integration == "sofizpay":
        details["ledger"] = await _sofizpay_ledger_totals(session, country, start, end)
    report.details = details
    session.add(report)
    await session.flush()
    if report.mismatched:
        from app.services import alert_capture

        alert_capture.ship_after_commit(
            session, "reconciliation_mismatch", "gateway_reconciliation", report.id,
            country=country.value, gateway=integration, mismatched=report.mismatched,
        )
    await session.commit()
    return report


async def _sofizpay_ledger_totals(
    session: AsyncSession, country: CountryCode, start: datetime, end: datetime
) -> dict[str, Any]:
    """**ما وصل حسابَ SofizPay على Stellar في النافذة** — للمقارنة بمجموع ما قُيِّد عندنا؛ وتعذّرُه يُكتب ولا يُسقط التقرير."""
    from app.services import sofizpay_ledger

    try:
        account = await sofizpay_ledger.account_for(session, country)
        found, more = await sofizpay_ledger.entries(account, since=start, until=end, direction="in")
    except Exception as exc:  # noqa: BLE001 - التقريرُ يكتب ما تعذّر ولا يسقط به
        return {"error": type(exc).__name__}
    total = sum((e.amount for e in found), Decimal("0.000"))
    return {"incoming_count": len(found), "incoming_total": str(total), "truncated": more}


async def reconcile_daily(session: AsyncSession, *, trigger: str = "daily") -> list[GatewayReconciliation]:
    reports = []
    for integration, country in await _contracts(session):
        try:
            reports.append(await reconcile_one(session, integration, country, trigger=trigger))
        except Exception:  # pragma: no cover - عقدٌ يتعذّر لا يُسقط تقريرَ غيره
            await session.rollback()
            logger.exception("تعذّرت مطابقةُ %s/%s", integration, country.value)
    return reports


async def reconciliations(session: AsyncSession, country: CountryCode | None, limit: int = 60) -> list[GatewayReconciliation]:
    stmt = select(GatewayReconciliation).order_by(GatewayReconciliation.created_at.desc()).limit(limit)
    if country is not None:
        stmt = stmt.where(GatewayReconciliation.country_code == country)
    return list((await session.scalars(stmt)).all())


# ═════════════════════════ ٣ — مراقبةُ SofizPay الحيّة

_CURSOR = "sofizpay:cursor:{}"


async def watch_sofizpay(session: AsyncSession) -> int:
    """**دورةٌ واحدة**: لكلِّ سوقٍ بعقد SofizPay مفعَّلٍ وطريقةٍ مفعَّلة — ما وصل الحسابَ بعد المؤشّر؟ فإن وصل شيءٌ حُسمت المعلّقة."""
    from app.core.redis_client import get_redis_client
    from app.services import payment_requests, sofizpay_ledger

    redis = get_redis_client()
    woke = 0
    countries = (
        await session.scalars(
            select(ProviderCredential.country_code).where(
                ProviderCredential.provider_key == ProviderKey.SOFIZPAY, ProviderCredential.is_active.is_(True)
            )
        )
    ).all()
    for code in countries:
        if code is None:
            continue
        country = CountryCode(code)
        live = await session.scalar(
            select(func.count()).select_from(PayMethod).where(
                PayMethod.country_code == country, PayMethod.integration == "sofizpay", PayMethod.enabled.is_(True)
            )
        )
        if not live:
            continue
        try:
            account = await sofizpay_ledger.account_for(session, country)
            key = _CURSOR.format(country.value)
            cursor = await redis.get(key)
            cursor = cursor.decode() if isinstance(cursor, bytes) else cursor
            if not cursor:
                await redis.set(key, await sofizpay_ledger.latest_cursor(account))
                continue
            arrived, newest = await sofizpay_ledger.incoming_since(account, cursor)
            await redis.set(key, newest)
        except Exception:  # noqa: BLE001 - المراقبةُ تسريعٌ لا شرط: التسويةُ الدوريّةُ تحسم ما فاتها
            logger.warning("تعذّرت مراقبةُ SofizPay في %s", country.value, exc_info=True)
            continue
        if not arrived:
            continue
        pending = (
            await session.scalars(
                select(PaymentRequest.id)
                .join(PayMethod, PayMethod.id == PaymentRequest.provider_id)
                .where(
                    PayMethod.integration == "sofizpay",
                    PaymentRequest.country_code == country,
                    PaymentRequest.status == PaymentRequestStatus.PENDING,
                    PaymentRequest.external_id.is_not(None),
                    PaymentRequest.created_at > _now() - timedelta(hours=payment_requests.CHECKOUT_TTL_HOURS),
                )
                .limit(50)
            )
        ).all()
        for request_id in pending:
            try:
                await payment_requests.settle_from_gateway(session, request_id=request_id)
                await session.commit()
                woke += 1
            except Exception:  # noqa: BLE001 - طلبٌ يتعذّر لا يوقف غيرَه، والتسويةُ تعيده
                await session.rollback()
                logger.warning("تعذّر حسمُ طلب SofizPay %s", request_id, exc_info=True)
    return woke
