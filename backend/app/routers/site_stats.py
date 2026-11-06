"""«الإحصاءات» — العدُّ العامُّ من الموقع وتقريرُ اللوحة (`design/SITE-STATS.md`).

**العدُّ العامّ** بلا جلسة: الصفحةُ تنادي `hit` و`click`، ونجينكس ينادي `download` بطلبٍ داخليٍّ حين تُطلب حزمةٌ كاملة. **ولا يُقرأ عنوانُ
IP في أيٍّ منها** — البلدُ من `CF-IPCountry`. **وحدٌّ لكلِّ بلدٍ ودقيقة** في Redis يمنع إغراقَ العدّاد؛ وما فوقه يُرمى بصمت (`204`)
لأن العدَّ ليس شيئاً يُعاد.

**وحدُّه مكتوب**: الأبوابُ العامّةُ يناديها من شاء، فرقمٌ مزوَّرٌ ممكنٌ بقدر الحدّ — **إحصاءٌ لا مال**، ولا يقرّر شيئاً.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, Field

from app.core import rate_limit
from app.core.deps import DbSession, RedisDep, StatsViewer
from app.core.exceptions import AppError
from app.services import play_reports, site_stats

# **`router` أوّلاً**: `check:contract` يقرأ أوّلَ بادئةٍ في الملفّ لأبواب `@router` — والعامُّ لا تناديه اللوحة
router = APIRouter(prefix="/admin/stats", tags=["admin"])
public = APIRouter(prefix="/public/site", tags=["public"])

#: حدُّ العدِّ لكلِّ بلدٍ في الدقيقة — فوقه يُرمى
PER_MINUTE = 600


class HitIn(BaseModel):
    path: str = Field("/", max_length=200)
    ref: str | None = Field(None, max_length=200, description="اسمُ نطاق المُحيل وحدَه")
    d: bool = False
    w: bool = False
    m: bool = False


class ClickIn(BaseModel):
    app: Literal["rider", "driver"]


async def _allowed(redis, country: str, kind: str) -> bool:
    return (await rate_limit.hit(redis, f"site-stats:{kind}:{country}", limit=PER_MINUTE, window_seconds=60)).allowed


@public.post("/hit", status_code=204)
async def hit(body: HitIn, session: DbSession, redis: RedisDep,
              cf_country: str | None = Header(None, alias="CF-IPCountry")) -> Response:
    country = site_stats.country_of(cf_country)
    if await _allowed(redis, country, "hit"):
        await site_stats.count_view(session, path=body.path, referrer_host=body.ref, country=country,
                                    new_day=body.d, new_week=body.w, new_month=body.m)
        await session.commit()
    return Response(status_code=204)


@public.post("/click", status_code=204)
async def click(body: ClickIn, session: DbSession, redis: RedisDep,
                cf_country: str | None = Header(None, alias="CF-IPCountry")) -> Response:
    country = site_stats.country_of(cf_country)
    if await _allowed(redis, country, "click"):
        await site_stats.count_download(session, app=body.app, country=country, kind="click")
        await session.commit()
    return Response(status_code=204)


@public.post("/download/{app}", status_code=204)
async def download(app: Literal["rider", "driver"], session: DbSession, redis: RedisDep,
                   cf_country: str | None = Header(None, alias="CF-IPCountry")) -> Response:
    """**ينادى من نجينكس** (`mirror`) حين تُطلب الحزمةُ كاملةً — لا من الصفحة."""
    country = site_stats.country_of(cf_country)
    if await _allowed(redis, country, "download"):
        await site_stats.count_download(session, app=app, country=country, kind="download")
        await session.commit()
    return Response(status_code=204)


@router.get("/report")
async def report(session: DbSession, viewer: StatsViewer, days: int = 30) -> dict:
    return await site_stats.report(session, days=max(7, min(days, 120)))


@router.post("/import-play")
async def import_play(session: DbSession, viewer: StatsViewer) -> dict:
    """استيرادٌ الآن بدل انتظار المهمّة اليوميّة — **ويُسجَّل كما تُسجَّل هي**."""
    try:
        rows = await play_reports.run(session)
    except play_reports.PlayReportsNotConfigured:
        raise AppError("عقدُ «Google Play — تقاريرُ التثبيت» غيرُ مُدخَل في «عقود مزوّدي API»") from None
    except (play_reports.PlayReportsError, Exception) as exc:  # noqa: BLE001 — يُسجَّل ويُقال
        await session.rollback()
        await site_stats.record_import(session, "play", 0, str(exc)[:500] or type(exc).__name__)
        await session.commit()
        raise AppError(f"تعذّر الاستيراد: {exc}") from None
    await site_stats.record_import(session, "play", rows, None)
    await session.commit()
    return {"rows": rows}
