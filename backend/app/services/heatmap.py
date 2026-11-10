"""**خريطةُ الطلب الحراريّة** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٨) — أين يكثر الطلبُ الآن، وأين لم يجد الطلبُ كبتناً.

**والأمرُ يعلو قرارَ «عدٌّ لا خريطة»** (`demand.py`، §٦٢-ج/٤٣) بشرطه: **«مجمَّعة»**. فلا نقطةَ راكبٍ تخرج من الباب:

* **شبكةُ خلايا بنحو كيلومتر** (`CELL_DEG` = ٠٫٠١ درجة) — مركزُ الخلية لا موضعُ الطلب.
* **آخرُ نصف ساعة** (`WINDOW_MINUTES`) بطلبات الرحلات في سوق السائل وعالمِه (§٦٥-ج: التجربةُ لا تُعدّ للحقيقيّ ولا العكس).
* **للكبتن مستوىً لا عدد** (١…٣ من أكبر خليةٍ في السوق)، **ولا خليةَ دون `MIN_FOR_DRIVER` طلبات** — خليةٌ بطلبٍ واحدٍ موضعُ راكبٍ
  واحدٍ بتقريب كيلومتر.
* **وللّوحة العددُ و«غيرُ المخدوم»**: ما انتهى «لم يُعثر على كبتن» أو ما زال يبحث منذ أكثر من ثلاث دقائق — **المناطقُ غيرُ المغطّاة**.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import CountryCode, RideStatus
from app.models.ride import Ride, _latitude, _longitude
from app.models.user import User

CELL_DEG = 0.01
WINDOW_MINUTES = 30
MIN_FOR_DRIVER = 3
#: بحثٌ أطولُ من هذا بلا كبتنٍ يُعدّ «غيرَ مخدوم» وإن لم ينتهِ بعد
SEARCH_STALE = timedelta(minutes=3)
MAX_CELLS = 400


@dataclass(frozen=True, slots=True)
class Cell:
    lat: float
    lng: float
    requests: int
    unserved: int


async def cells(
    session: AsyncSession, *, country: CountryCode, now: datetime, minutes: int = WINDOW_MINUTES, test: bool = False
) -> list[Cell]:
    since = now - timedelta(minutes=minutes)
    lat_cell = func.round(_latitude(Ride.pickup_point) / CELL_DEG)
    lng_cell = func.round(_longitude(Ride.pickup_point) / CELL_DEG)
    unserved = func.sum(
        case(
            (
                or_(
                    Ride.status == RideStatus.NO_DRIVER_FOUND,
                    and_(
                        Ride.status.in_((RideStatus.REQUESTED, RideStatus.SEARCHING)),
                        Ride.created_at <= now - SEARCH_STALE,
                    ),
                ),
                1,
            ),
            else_=0,
        )
    )
    rows = (
        await session.execute(
            select(lat_cell.label("la"), lng_cell.label("lo"), func.count().label("n"), unserved.label("u"))
            .join(User, User.id == Ride.rider_id)
            .where(Ride.country_code == country, Ride.created_at >= since, User.is_test.is_(test))
            .group_by("la", "lo")
            .order_by(func.count().desc())
            .limit(MAX_CELLS)
        )
    ).all()
    return [
        Cell(lat=round(float(la) * CELL_DEG, 4), lng=round(float(lo) * CELL_DEG, 4), requests=int(n), unserved=int(u or 0))
        for la, lo, n, u in rows
    ]


def levels_for_driver(found: list[Cell]) -> list[tuple[float, float, int]]:
    """**مستوىً لا عدد** — ١ خفيف · ٢ متوسّط · ٣ مرتفع، نسبةً إلى أكبر خليةٍ في السوق؛ وما دون الحدّ لا يُرسم."""
    shown = [cell for cell in found if cell.requests >= MIN_FOR_DRIVER]
    if not shown:
        return []
    peak = max(cell.requests for cell in shown)
    out = []
    for cell in shown:
        share = cell.requests / peak
        out.append((cell.lat, cell.lng, 3 if share >= 0.66 else 2 if share >= 0.33 else 1))
    return out
