"""**اقتراحاتُ الأماكن وبلاغاتُ الطريق** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّتان ٢-٣ و٣-٣) — `models/map_community.py`.

**الاقتراح**: يُحفظ «قيدَ المراجعة» ولا يُرى؛ والمشرفُ يوافق ⇐ صفٌّ في `map_places` بمصدر `community` (يُرسم فوق أسماء الخريطة ويُبحث)،
أو يرفض بسبب. **وعشرةُ اقتراحاتٍ قيدَ المراجعة لكلِّ مستخدمٍ حدٌّ** — فلا يُغرق أحدٌ الطابور.

**البلاغ**: كبتنٌ يلمس مرّةً ⇐ بلاغٌ جديد، أو **تأكيدٌ** لبلاغٍ من نوعه نفسه على بُعد `MERGE_M` منه. **ولا يُرى** إلا بتأكيد `SHOW_AT`
كباتن مختلفين أو موافقة المشرف، **وينتهي وحدَه** بعمرِ نوعه (والتأكيدُ يمدّه). والمشرفُ يزيله — حالٌ لا محو.

**وكلُّ تغيير حالٍ يقفل صفَّه قبل أن يقرأ الحال** (قاعدةُ CLAUDE.md) — فموافقتان متزامنتان لا تُولّدان مكانين.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidInput, NotFound
from app.models.enums import AuditAction, CountryCode, FeatureKey
from app.models.map_community import PlaceSuggestion, RoadReport, RoadReportVote
from app.models.map_place import SOURCE_COMMUNITY, MapPlace
from app.models.user import User
from app.services import audit, settings_service

PENDING_CAP = 10
MERGE_M = 150.0
SHOW_AT = 2
LIFETIME = {"works": timedelta(hours=12), "closed": timedelta(hours=6), "accident": timedelta(hours=2), "jam": timedelta(hours=1)}


def _metres(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dx = (lng2 - lng1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * 110_540
    return math.hypot(dx, dy)


async def _require(session: AsyncSession, country: CountryCode, key: FeatureKey) -> None:
    if not await settings_service.is_feature_enabled(session, country, key):
        raise InvalidInput("هذه الميزةُ غيرُ مفعّلةٍ في بلدك بعد", field="feature")


# ─────────────────────────────────────────────────────────── الاقتراحات


async def suggest(
    session: AsyncSession,
    user: User,
    *,
    kind: str,
    name_ar: str,
    name_en: str | None,
    category: str,
    lat: float,
    lng: float,
    current_name: str | None,
    note: str | None,
) -> PlaceSuggestion:
    await _require(session, user.country_code, FeatureKey.MAP_PLACE_SUGGESTIONS)
    pending = await session.scalar(
        select(func.count()).select_from(PlaceSuggestion).where(PlaceSuggestion.user_id == user.id, PlaceSuggestion.status == "pending")
    )
    if (pending or 0) >= PENDING_CAP:
        raise InvalidInput("لديك اقتراحاتٌ كثيرةٌ قيدَ المراجعة — انتظر حتى تُراجَع", field="name_ar")
    row = PlaceSuggestion(
        country_code=user.country_code,
        user_id=user.id,
        kind=kind,
        name_ar=name_ar.strip(),
        name_en=(name_en or "").strip() or None,
        category=category,
        lat=lat,
        lng=lng,
        current_name=(current_name or "").strip()[:120] or None,
        note=(note or "").strip()[:300] or None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def suggestions(session: AsyncSession, *, status: str, country: CountryCode | None) -> list[PlaceSuggestion]:
    query = select(PlaceSuggestion).where(PlaceSuggestion.status == status).order_by(PlaceSuggestion.created_at.desc()).limit(200)
    if country is not None:
        query = query.where(PlaceSuggestion.country_code == country)
    return list(await session.scalars(query))


async def _locked_suggestion(session: AsyncSession, suggestion_id: uuid.UUID) -> PlaceSuggestion:
    row = await session.get(PlaceSuggestion, suggestion_id, with_for_update=True, populate_existing=True)
    if row is None:
        raise NotFound("الاقتراح غير موجود")
    if row.status != "pending":
        raise InvalidInput("رُوجع هذا الاقتراحُ من قبل", field="status")
    return row


async def approve(
    session: AsyncSession, suggestion_id: uuid.UUID, admin: User, *, name_ar: str | None, category: str | None
) -> PlaceSuggestion:
    """**الموافقةُ تُولِّد مكاناً** بمصدر `community` — بالاسم والفئة كما عدّلهما المشرفُ إن عدّل."""
    row = await _locked_suggestion(session, suggestion_id)
    place = MapPlace(
        country_code=row.country_code,
        name_ar=(name_ar or row.name_ar).strip(),
        name_en=row.name_en,
        category=category or row.category,
        lat=row.lat,
        lng=row.lng,
        source=SOURCE_COMMUNITY,
    )
    session.add(place)
    await session.flush()
    row.status = "approved"
    row.reviewed_by = admin.id
    row.reviewed_at = datetime.now(UTC)
    row.map_place_id = place.id
    await audit.record(
        session, actor=admin, action=AuditAction.UPDATE, entity_type="place_suggestion", entity_id=row.id,
        details={"status": "approved", "map_place_id": str(place.id), "name_ar": place.name_ar, "category": place.category},
    )
    await session.commit()
    await session.refresh(row)
    return row


async def reject(session: AsyncSession, suggestion_id: uuid.UUID, admin: User, *, reason: str) -> PlaceSuggestion:
    row = await _locked_suggestion(session, suggestion_id)
    row.status = "rejected"
    row.reviewed_by = admin.id
    row.reviewed_at = datetime.now(UTC)
    row.review_note = reason.strip()[:300]
    await audit.record(
        session, actor=admin, action=AuditAction.UPDATE, entity_type="place_suggestion", entity_id=row.id,
        details={"status": "rejected", "reason": row.review_note},
    )
    await session.commit()
    await session.refresh(row)
    return row


# ─────────────────────────────────────────────────────────── بلاغاتُ الطريق


@dataclass(frozen=True, slots=True)
class ReportResult:
    report: RoadReport
    created: bool
    counted: bool


async def report(session: AsyncSession, user: User, *, kind: str, lat: float, lng: float) -> ReportResult:
    """**لمسةٌ واحدة** — بلاغٌ جديدٌ أو تأكيدٌ لأقرب بلاغٍ من نوعه نفسه (`MERGE_M`). **والكبتنُ لا يؤكّد بلاغَه مرّتين.**"""
    await _require(session, user.country_code, FeatureKey.MAP_ROAD_REPORTS)
    now = datetime.now(UTC)
    nearby = await session.scalars(
        select(RoadReport).where(
            RoadReport.country_code == user.country_code,
            RoadReport.kind == kind,
            RoadReport.status == "active",
            RoadReport.expires_at > now,
            RoadReport.lat.between(lat - 0.003, lat + 0.003),
            RoadReport.lng.between(lng - 0.004, lng + 0.004),
        )
    )
    best = min(
        (row for row in nearby if _metres(row.lat, row.lng, lat, lng) <= MERGE_M),
        key=lambda row: _metres(row.lat, row.lng, lat, lng),
        default=None,
    )
    if best is None:
        row = RoadReport(country_code=user.country_code, kind=kind, lat=lat, lng=lng, expires_at=now + LIFETIME[kind])
        session.add(row)
        await session.flush()
        session.add(RoadReportVote(report_id=row.id, user_id=user.id))
        await session.commit()
        await session.refresh(row)
        return ReportResult(row, created=True, counted=True)
    row = await session.get(RoadReport, best.id, with_for_update=True, populate_existing=True)
    assert row is not None
    voted = await session.get(RoadReportVote, (row.id, user.id))
    if voted is not None:
        await session.commit()
        return ReportResult(row, created=False, counted=False)
    session.add(RoadReportVote(report_id=row.id, user_id=user.id))
    row.confirmations += 1
    row.expires_at = max(row.expires_at, now + LIFETIME[kind])
    await session.commit()
    await session.refresh(row)
    return ReportResult(row, created=False, counted=True)


async def visible_reports(session: AsyncSession, country: CountryCode) -> list[RoadReport]:
    """**ما يُرسم للراكب والكبتن** — نشطٌ لم ينتهِ، **مؤكَّدٌ من `SHOW_AT` كباتن أو وافق عليه المشرف**. وفارغٌ والمفتاحُ مطفأ."""
    if not await settings_service.is_feature_enabled(session, country, FeatureKey.MAP_ROAD_REPORTS):
        return []
    rows = await session.scalars(
        select(RoadReport).where(
            RoadReport.country_code == country,
            RoadReport.status == "active",
            RoadReport.expires_at > datetime.now(UTC),
            (RoadReport.confirmations >= SHOW_AT) | RoadReport.approved.is_(True),
        )
    )
    return list(rows)


async def admin_reports(session: AsyncSession, country: CountryCode | None) -> list[RoadReport]:
    query = (
        select(RoadReport)
        .where(RoadReport.status == "active", RoadReport.expires_at > datetime.now(UTC))
        .order_by(RoadReport.created_at.desc())
        .limit(300)
    )
    if country is not None:
        query = query.where(RoadReport.country_code == country)
    return list(await session.scalars(query))


async def review_report(session: AsyncSession, report_id: uuid.UUID, admin: User, *, action: str) -> RoadReport:
    """`approve` يُظهره بلا انتظار التأكيد، و`remove` يزيله — **حالٌ لا محو**."""
    row = await session.get(RoadReport, report_id, with_for_update=True, populate_existing=True)
    if row is None:
        raise NotFound("البلاغ غير موجود")
    if row.status != "active":
        raise InvalidInput("أُزيل هذا البلاغُ من قبل", field="status")
    if action == "approve":
        row.approved = True
    else:
        row.status = "removed"
    row.reviewed_by = admin.id
    await audit.record(
        session, actor=admin, action=AuditAction.UPDATE, entity_type="road_report", entity_id=row.id, details={"action": action}
    )
    await session.commit()
    await session.refresh(row)
    return row
