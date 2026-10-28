"""**تثبيتُ سعر الرحلة عشرَ دقائق** (SPEC §٨٨/١، أمرُ المالك ٢٠٢٦-١٠-٢٨، الجزء B) — «اشحن مبلغ الرحلة الآن» ثمّ يكمل الطلبُ نفسُه.

**المشكلة**: راكبٌ رصيدُه أقلُّ من الأجرة يشحن، **وحين يعود قد تغيّر السعر** (زحامٌ أو منطقةُ تسعير) — فيشحن مبلغاً لا يغطّي ما يُطلب منه.
**فالتقديرُ نفسُه يُحفظ** — كما حسبته الخلفيةُ لا كما يرسله التطبيق — **في Redis عشرَ دقائق**، مقيَّداً بالراكب وبتفاصيل الرحلة (الفئة ·
النقطتان · المحطات · الطرد · الساعات): **طلبٌ بالمعرّف نفسِه وبالتفاصيل نفسِها يأخذ السعرَ المحفوظ**، وما خالفها أو انتهت مهلتُه يُسعَّر
من جديد كما كان. **فلا سعرَ يأتي من التطبيق أبداً** (§١٤): المعرّفُ مفتاحٌ لا مبلغ.

**والمحفوظُ موقَّعٌ** (`HMAC-SHA256` بمفتاح التطبيق) فلا يُقرأ ما لم تكتبه الخلفية؛ **ويُستهلك مرّةً واحدة** عند إنشاء الرحلة.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import pickle
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.config import settings
from app.core.currency import STORAGE_STEP

#: **عشرُ دقائق بنصِّ المالك** — «the price is locked for about 10 minutes»
LOCK_SECONDS = 600
_KEY = "ride:quote:{rider}:{quote}"


def _secret() -> bytes:
    return settings.jwt_secret.encode()


def digest(
    *,
    vehicle_category: str,
    pickup: tuple[float, float],
    dropoff: tuple[float, float],
    stops: Sequence[tuple[float, float]] = (),
    parcel: bool = False,
    parcel_fetch: bool = False,
    hourly_hours: int | None = None,
) -> str:
    """**بصمةُ تفاصيل الرحلة** — ستُّ خاناتٍ عشريّةٍ للإحداثيّة (نحو عشرة سنتيمترات): نقطةٌ تحرّكت رحلةٌ أخرى."""
    body = {
        "c": vehicle_category,
        "p": [round(pickup[0], 6), round(pickup[1], 6)],
        "d": [round(dropoff[0], 6), round(dropoff[1], 6)],
        "s": [[round(a, 6), round(b, 6)] for a, b in stops],
        "parcel": bool(parcel),
        "fetch": bool(parcel_fetch),
        "h": hourly_hours or 0,
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def _sign(blob: bytes) -> bytes:
    return hmac.new(_secret(), blob, hashlib.sha256).digest() + blob


def _verify(raw: bytes) -> bytes | None:
    mac, blob = raw[:32], raw[32:]
    if not hmac.compare_digest(mac, hmac.new(_secret(), blob, hashlib.sha256).digest()):
        return None
    return blob


async def lock(redis, *, rider_id, params: str, quote) -> tuple[str, datetime]:
    """**يحفظ التقديرَ عشرَ دقائق** ويعيد معرّفَه ونهايةَ المهلة."""
    quote_id = secrets.token_urlsafe(12)
    blob = pickle.dumps({"params": params, "quote": quote})
    # **نصٌّ لا بايتات** — عميلُ Redis يفكّ الأجوبةَ نصوصاً (`decode_responses`)
    await redis.set(_KEY.format(rider=rider_id, quote=quote_id), base64.b64encode(_sign(blob)).decode(), ex=LOCK_SECONDS)
    return quote_id, datetime.now(UTC) + timedelta(seconds=LOCK_SECONDS)


async def take(redis, *, rider_id, quote_id: str | None, params: str):
    """**التقديرُ المحفوظ إن طابق** — للراكب نفسِه وبتفاصيل الرحلة نفسِها وفي مهلته؛ وإلا `None` فيُسعَّر من جديد."""
    if not quote_id:
        return None
    try:
        raw = await redis.get(_KEY.format(rider=rider_id, quote=quote_id))
    except Exception:  # noqa: BLE001 - Redis معطّلٌ ⇐ سعرٌ جديدٌ كما كان، لا رفضُ رحلة
        return None
    if not raw:
        return None
    try:
        blob = _verify(base64.b64decode(raw))
    except ValueError:
        return None
    if blob is None:
        return None
    stored = pickle.loads(blob)  # noqa: S301 - موقَّعٌ بمفتاح الخلفية: لا يُقرأ إلا ما كتبته هي
    if stored.get("params") != params:
        return None
    return stored.get("quote")


async def release(redis, *, rider_id, quote_id: str | None) -> None:
    """**يُستهلك مرّةً واحدة** — بعد إنشاء الرحلة."""
    if not quote_id:
        return
    try:
        await redis.delete(_KEY.format(rider=rider_id, quote=quote_id))
    except Exception:  # noqa: BLE001
        return


def shortfall(fare: Decimal, balance: Decimal, unit: Decimal | None, minimum: Decimal | None) -> Decimal:
    """**ما ينقص المحفظةَ لتغطّي الأجرة** — مقرَّباً إلى أعلى بوحدة السوق، ولا أقلَّ من أصغر شحن. **صفرٌ حين يكفي الرصيد.**"""
    need = fare - balance
    if need <= 0:
        return Decimal("0.000")
    if unit is not None and unit > 0:
        steps = (need / unit).to_integral_value(rounding="ROUND_CEILING")
        need = steps * unit
    if minimum is not None and need < minimum:
        need = minimum
    return need.quantize(STORAGE_STEP)
