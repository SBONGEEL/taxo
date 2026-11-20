"""**أقربُ منطقةٍ مزدحمة** (أمرُ المالك ٢٠٢٦-١١-٢٠ الرابع، البند ٤٥، SPEC §١١٠) — «اذهب إليها» من الفقاعة والودجة.

**من خلايا خريطة الطلب نفسِها** (`heatmap.cells` · `levels_for_driver`) لا من حسابٍ ثانٍ — فما تقوله الفقاعةُ هو ما ترسمه الخريطة:

* **مجمَّعةٌ مجهولة**: مركزُ خليةٍ بنحو كيلومتر، آخرَ نصف ساعة، **ولا خليةَ دون ثلاث طلبات** (`MIN_FOR_DRIVER`) — فلا يخرج موضعُ راكب.
* **«كثيرةُ الطلبات» = المستوى ٢ فما فوق** من أعلى خليةٍ في السوق؛ وإن لم يكن إلا الخفيفُ فلا منطقة — **لا يُقال «مزدحمة» عن خفيفة**.
* **الأقربُ إلى موقعه المبثوث** (لا إلى ما يرسله التطبيق)، وبلا موقعٍ مبثوثٍ لا جواب — «لا نعرف» لا «لا شيء».
* **والمسافةُ خطٌّ مستقيمٌ ويقال كذلك** («تقريباً» في الواجهة) — لا وقتَ قيادةٍ مخترَع.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.services import heatmap

#: «كثيرةُ الطلبات» — المتوسّطُ فما فوق
MIN_LEVEL = 2


@dataclass(frozen=True, slots=True)
class BusyArea:
    lat: float
    lng: float
    level: int
    distance_km: float


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest(found: list[heatmap.Cell], *, lat: float, lng: float) -> BusyArea | None:
    """خالصة: أقربُ خليةٍ بالمستوى ٢ فما فوق — والأعلى مستوىً عند التساوي في المسافة."""
    best: BusyArea | None = None
    for c_lat, c_lng, level in heatmap.levels_for_driver(found):
        if level < MIN_LEVEL:
            continue
        km = _km(lat, lng, c_lat, c_lng)
        if best is None or km < best.distance_km - 1e-9 or (abs(km - best.distance_km) < 1e-9 and level > best.level):
            best = BusyArea(lat=c_lat, lng=c_lng, level=level, distance_km=km)
    if best is None:
        return None
    return BusyArea(lat=best.lat, lng=best.lng, level=best.level, distance_km=round(best.distance_km, 1))
