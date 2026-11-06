"""«الإحصاءات»: عدُّ الزيارات والتحميلات، واستيرادُ أرقام Play، وتقريرُ الشاشة (`design/SITE-STATS.md`).

## الخصوصيّةُ بالبناء

- **لا عنوانَ IP يُقرأ**: البلدُ من ترويسة Cloudflare (`CF-IPCountry`) وحدَها، وغيرُ المعروف `??`.
- **لا معرّف**: الفريدُ علمٌ يرسله متصفّحُ الزائر نفسُه («أوّلُ زيارةٍ لي اليوم/الأسبوع/الشهر») من تاريخٍ في `localStorage`.
- **المُحيلُ يُصنَّف ثمّ يُرمى** — اسمُ النطاق يصير `facebook`/`google`/`direct`/`other`، ولا يُحفظ رابط.
- **والمسارُ من قائمةٍ مغلقة** (`PATHS`) — ما عداها `other`، فلا يُحفظ استعلامٌ أو مسارٌ قد يحمل معرّفاً.

## «اليوم» يومُ الجزائر

السوقُ الأوّلُ للصفحة، والجزائرُ UTC+1 طوالَ السنة. **والعدُّ ذرّيٌّ في القاعدة** (`ON CONFLICT … SET n = n + 1`).
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site_stats import PlayStatsDaily, SiteDaily, SiteDownloadDaily, StatsImport

logger = logging.getLogger(__name__)

ZONE = ZoneInfo("Africa/Algiers")
PACKAGES = {"ly.tajora.rider": "rider", "ly.tajora.driver": "driver"}

#: صفحاتُ الموقع التي تُعدّ بأسمائها — **وما عداها `other`**
PATHS = (
    "/", "/download", "/privacy", "/terms", "/driver-privacy", "/driver-terms", "/delete-account",
    "/dz", "/dz/download", "/fr", "/en",
)
#: بلادٌ لا تُعرض في الشاشة — **تُعدّ ولا تُذكر** (قرارُ المالك: ليبيا لا تُذكر ولا تُعرض)
HIDDEN_COUNTRIES = frozenset({"LY"})
_COUNTRY = re.compile(r"^[A-Z]{2}$")


def today() -> date:
    return datetime.now(ZONE).date()


def country_of(header: str | None) -> str:
    """ترويسةُ Cloudflare حرفان؛ وما سواها (`XX` · `T1` · غياب) يصير `??`."""
    value = (header or "").strip().upper()
    return value if _COUNTRY.match(value) and value not in ("XX", "T1") else "??"


def source_of(referrer_host: str | None) -> str:
    host = (referrer_host or "").strip().lower()
    if not host:
        return "direct"
    if re.search(r"(^|\.)(facebook\.com|fb\.com|fb\.me|messenger\.com|instagram\.com)$", host) or host.startswith("l.facebook."):
        return "facebook"
    if re.search(r"(^|\.)google\.[a-z.]+$", host):
        return "google"
    if host.endswith("tajora.ly"):
        return "direct"
    return "other"


def path_of(raw: str | None) -> str:
    path = (raw or "/").split("?")[0].split("#")[0].rstrip("/") or "/"
    path = re.sub(r"\.html$", "", path)
    return path if path in PATHS else "other"


async def count_view(session: AsyncSession, *, path: str, referrer_host: str | None, country: str,
                     new_day: bool, new_week: bool, new_month: bool) -> None:
    row = {"day": today(), "path": path_of(path), "source": source_of(referrer_host), "country": country,
           "views": 1, "uniques_day": int(new_day), "uniques_week": int(new_week), "uniques_month": int(new_month)}
    stmt = insert(SiteDaily).values(**row)
    t = SiteDaily.__table__.c
    await session.execute(stmt.on_conflict_do_update(
        index_elements=["day", "path", "source", "country"],
        set_={"views": t.views + 1, "uniques_day": t.uniques_day + row["uniques_day"],
              "uniques_week": t.uniques_week + row["uniques_week"], "uniques_month": t.uniques_month + row["uniques_month"]},
    ))


async def count_download(session: AsyncSession, *, app: str, country: str, kind: str) -> None:
    """`kind`: `download` (الملفُّ طُلب كاملاً، من نجينكس) أو `click` (ضغطُ الزرّ، من الصفحة)."""
    column = "downloads" if kind == "download" else "clicks"
    stmt = insert(SiteDownloadDaily).values(day=today(), app=app, country=country, **{column: 1})
    t = SiteDownloadDaily.__table__.c
    await session.execute(stmt.on_conflict_do_update(
        index_elements=["day", "app", "country"], set_={column: t[column] + 1},
    ))


# ───────────────────────── Play

def parse_play_country_csv(raw: bytes) -> list[dict]:
    """تقريرُ Play الشهريّ بالبلد — UTF-16 بعلامة، أو UTF-8."""
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    text = text.lstrip("﻿")
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            rows.append({
                "day": date.fromisoformat(r["Date"]), "package": r["Package name"], "country": country_of(r.get("Country")),
                "installs": int(r.get("Daily Device Installs") or 0), "uninstalls": int(r.get("Daily Device Uninstalls") or 0),
                "active_devices": int(r.get("Active Device Installs") or 0),
            })
        except (KeyError, ValueError):
            continue
    return rows


async def store_play_rows(session: AsyncSession, rows: list[dict]) -> int:
    """يكتب صفوفَ التقرير **ويستبدل** ما سبق لليوم نفسِه — Play يصحّح أيّامَه الأخيرة في النسخة التالية."""
    if not rows:
        return 0
    now = datetime.now(UTC)
    stmt = insert(PlayStatsDaily).values([{**r, "imported_at": now} for r in rows])
    await session.execute(stmt.on_conflict_do_update(
        index_elements=["day", "package", "country"],
        set_={"installs": stmt.excluded.installs, "uninstalls": stmt.excluded.uninstalls,
              "active_devices": stmt.excluded.active_devices, "imported_at": stmt.excluded.imported_at},
    ))
    return len(rows)


async def record_import(session: AsyncSession, source: str, rows: int, error: str | None) -> None:
    session.add(StatsImport(source=source, rows=rows, status="failed" if error else "ok", error=error))


# ───────────────────────── التقرير

def _windows(now_day: date) -> dict[str, date]:
    return {"today": now_day, "week": now_day - timedelta(days=now_day.weekday()), "month": now_day.replace(day=1)}


async def report(session: AsyncSession, days: int = 30) -> dict:
    now_day = today()
    since = now_day - timedelta(days=days - 1)
    win = _windows(now_day)
    hidden = list(HIDDEN_COUNTRIES)

    async def site_sum(start: date | None, column):
        stmt = select(func.coalesce(func.sum(column), 0)).where(SiteDaily.country.not_in(hidden))
        if start:
            stmt = stmt.where(SiteDaily.day >= start)
        return int(await session.scalar(stmt) or 0)

    visits = {k: {"views": await site_sum(v, SiteDaily.views),
                  "uniques": await site_sum(v, {"today": SiteDaily.uniques_day, "week": SiteDaily.uniques_week,
                                                "month": SiteDaily.uniques_month}[k])}
              for k, v in win.items()}
    visits["all"] = {"views": await site_sum(None, SiteDaily.views), "uniques": None}

    async def grouped(model, key, value, start=since, limit=10):
        rows = (await session.execute(
            select(key, func.sum(value)).where(model.day >= start, model.country.not_in(hidden))
            .group_by(key).order_by(func.sum(value).desc()).limit(limit)
        )).all()
        return [{"key": k, "count": int(n or 0)} for k, n in rows]

    daily_site = (await session.execute(
        select(SiteDaily.day, func.sum(SiteDaily.views), func.sum(SiteDaily.uniques_day))
        .where(SiteDaily.day >= since, SiteDaily.country.not_in(hidden)).group_by(SiteDaily.day).order_by(SiteDaily.day)
    )).all()

    # ── التحميلات: الموقع + Play لكلِّ تطبيق
    async def site_dl(app: str, start: date | None, column) -> int:
        stmt = select(func.coalesce(func.sum(column), 0)).where(SiteDownloadDaily.app == app,
                                                               SiteDownloadDaily.country.not_in(hidden))
        if start:
            stmt = stmt.where(SiteDownloadDaily.day >= start)
        return int(await session.scalar(stmt) or 0)

    async def play_sum(package: str, start: date | None, column) -> int:
        stmt = select(func.coalesce(func.sum(column), 0)).where(PlayStatsDaily.package == package,
                                                               PlayStatsDaily.country.not_in(hidden))
        if start:
            stmt = stmt.where(PlayStatsDaily.day >= start)
        return int(await session.scalar(stmt) or 0)

    summary = {}
    for package, app in PACKAGES.items():
        per = {}
        for k, start in [*win.items(), ("all", None)]:
            site = await site_dl(app, start, SiteDownloadDaily.downloads)
            play = await play_sum(package, start, PlayStatsDaily.installs)
            per[k] = {"site": site, "play": play, "total": site + play}
        summary[app] = per

    daily_dl = (await session.execute(
        select(SiteDownloadDaily.day, SiteDownloadDaily.app, func.sum(SiteDownloadDaily.downloads),
               func.sum(SiteDownloadDaily.clicks))
        .where(SiteDownloadDaily.day >= since, SiteDownloadDaily.country.not_in(hidden))
        .group_by(SiteDownloadDaily.day, SiteDownloadDaily.app).order_by(SiteDownloadDaily.day)
    )).all()

    daily_play = (await session.execute(
        select(PlayStatsDaily.day, PlayStatsDaily.package, func.sum(PlayStatsDaily.installs),
               func.sum(PlayStatsDaily.uninstalls), func.sum(PlayStatsDaily.active_devices))
        .where(PlayStatsDaily.day >= since, PlayStatsDaily.country.not_in(hidden))
        .group_by(PlayStatsDaily.day, PlayStatsDaily.package).order_by(PlayStatsDaily.day)
    )).all()

    last = await session.scalar(select(StatsImport).where(StatsImport.source == "play").order_by(StatsImport.ran_at.desc()).limit(1))
    first_site = await session.scalar(select(func.min(SiteDaily.day)))
    first_dl = await session.scalar(select(func.min(SiteDownloadDaily.day)))
    first_play = await session.scalar(select(func.min(PlayStatsDaily.day)))
    last_play_day = await session.scalar(select(func.max(PlayStatsDaily.day)))

    return {
        "today": now_day.isoformat(),
        "summary": summary,
        "visits": visits,
        "site_daily": [{"day": d.isoformat(), "views": int(v or 0), "uniques": int(u or 0)} for d, v, u in daily_site],
        "top_pages": await grouped(SiteDaily, SiteDaily.path, SiteDaily.views),
        "top_sources": await grouped(SiteDaily, SiteDaily.source, SiteDaily.views),
        "site_countries": await grouped(SiteDaily, SiteDaily.country, SiteDaily.views),
        "downloads_daily": [{"day": d.isoformat(), "app": a, "downloads": int(n or 0), "clicks": int(c or 0)}
                            for d, a, n, c in daily_dl],
        "download_countries": await grouped(SiteDownloadDaily, SiteDownloadDaily.country, SiteDownloadDaily.downloads),
        "play_daily": [{"day": d.isoformat(), "app": PACKAGES.get(p, p), "installs": int(i or 0), "uninstalls": int(u or 0),
                        "active_devices": int(a or 0)} for d, p, i, u, a in daily_play],
        "play_countries": await grouped(PlayStatsDaily, PlayStatsDaily.country, PlayStatsDaily.installs),
        "play_last_import": None if last is None else {
            "ran_at": last.ran_at.isoformat(), "status": last.status, "rows": last.rows, "error": last.error,
        },
        "play_last_day": last_play_day.isoformat() if last_play_day else None,
        "since": {"site": first_site.isoformat() if first_site else None,
                  "downloads": first_dl.isoformat() if first_dl else None,
                  "play": first_play.isoformat() if first_play else None},
    }
