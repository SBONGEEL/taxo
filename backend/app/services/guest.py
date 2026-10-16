"""وضعُ الضيف (SPEC §٧٦-ن/أ) — **البدءُ والحدُّ والرمزُ والمفتاحُ والمحو، في موضعٍ واحد**.

* **لا حسابَ ولا رحلةَ ولا مال**: الخادمُ يكتب صفّاً في `guest_sessions` ويعطي رمزاً من نوع `guest` — وكلُّ ما يراه الضيفُ بعدها محاكاةٌ في
  تطبيقه. والبابُ الوحيدُ الذي يقبل هذا الرمز «أرسل ملاحظة» (`routers/guest.py`).
* **الحدُّ قبل الكتابة، لكلِّ جهازٍ ولكلِّ عنوان** — دلوان باسميهما لا يشاركان الدخولَ ولا الملاحظات.
* **ولا يصير الضيفُ حساباً**: لا بابَ يحوّله — التسجيلُ هو التسجيلُ المعتاد بالتحقّق من الرقم، ولا يأخذ من الضيف شيئاً.
* **ويُمحى بعد ٣٠ يوماً** ومعه ملاحظاتُه (القيدُ `CASCADE`)، وصورُها بعد الالتزام — في دورة التقليم اليوميّة.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import settings
from app.core.exceptions import InvalidToken, NotFound, RateLimited
from app.core.security import TokenError, _create_token, decode_token
from app.models.feedback import AppFeedback
from app.models.guest import GuestModeSetting, GuestSession

APPS = ("rider", "driver")
#: **ثلاثون يوماً** — بنصِّ أمر المالك، وهي المكتوبةُ في سياسة الخصوصية
RETENTION_DAYS = 30
TOKEN_LIFETIME = timedelta(days=RETENTION_DAYS)
#: **حدّا الإنشاء** — جهازٌ يبدأ عرضاً بضعَ مرّاتٍ في اليوم لا أكثر، وعنوانٌ واحدٌ قد يجمع مكتباً أو مقهى فيتّسع
PER_DEVICE_PER_DAY = 6
PER_IP_PER_HOUR = 30


def fingerprint(value: str) -> str:
    """**مُجزَّأٌ بمفتاح الخادم** — يكفي للحدّ، ولا يُعاد منه جهازٌ ولا عنوان."""
    return hmac.new(settings.jwt_secret.encode(), f"guest:{value}".encode(), hashlib.sha256).hexdigest()


async def setting(session: AsyncSession) -> GuestModeSetting | None:
    return await session.scalar(select(GuestModeSetting))


async def enabled(session: AsyncSession) -> dict[str, bool]:
    row = await setting(session)
    return {"rider": bool(row and row.rider_enabled), "driver": bool(row and row.driver_enabled)}


async def update(
    session: AsyncSession, *, rider: bool | None = None, driver: bool | None = None
) -> tuple[GuestModeSetting, list[str]]:
    """يكتب المفتاحين ويعيد ما تغيّر — **والصفُّ يُقفل قبل القراءة** (قاعدةُ «القفلُ قبل الفحص»)."""
    row = await session.scalar(
        select(GuestModeSetting).with_for_update().execution_options(populate_existing=True)
    )
    if row is None:
        row = GuestModeSetting()
        session.add(row)
        await session.flush()
    changed: list[str] = []
    if rider is not None and rider != row.rider_enabled:
        row.rider_enabled = rider
        changed.append("rider_enabled")
    if driver is not None and driver != row.driver_enabled:
        row.driver_enabled = driver
        changed.append("driver_enabled")
    await session.flush()
    return row, changed


async def start(
    session: AsyncSession,
    redis: Redis,
    *,
    app: str,
    device_id: str,
    ip: str,
    language: str | None,
    region: str | None,
) -> tuple[GuestSession, str]:
    """يبدأ جلسةَ عرض — **والمفتاحُ ثمّ الحدُّ ثمّ الكتابة**: تطبيقٌ مطفأُ الضيف لا يكتب شيئاً، ومن تجاوز نصيبَه لا يُكتب له صفّ."""
    if app not in APPS or not (await enabled(session))[app]:
        raise NotFound("وضعُ الضيف غيرُ متاحٍ الآن")
    device = fingerprint(f"device:{device_id}")
    address = fingerprint(f"ip:{ip}")
    for key, limit, window in (
        (f"guest:device:{device}", PER_DEVICE_PER_DAY, 86400),
        (f"guest:ip:{address}", PER_IP_PER_HOUR, 3600),
    ):
        result = await rate_limit.hit(redis, key, limit=limit, window_seconds=window)
        if not result.allowed:
            raise RateLimited(retry_after=result.retry_after)
    row = GuestSession(
        app=app,
        device_hash=device,
        ip_hash=address,
        language=(language or None) and language[:8],
        network_region=(region or None) and region[:2].upper(),
    )
    session.add(row)
    await session.flush()
    token, _, _ = _create_token(str(row.id), "guest", TOKEN_LIFETIME, {"app": app})
    return row, token


async def authenticate(session: AsyncSession, token: str) -> GuestSession:
    """رمزُ `guest` وحدَه، **وجلستُه حيّة** — جلسةٌ مُحيت بعد ثلاثين يوماً لا تكتب بعدها."""
    try:
        payload = decode_token(token, "guest")
        guest_id = uuid.UUID(payload["sub"])
    except (TokenError, ValueError) as exc:
        raise InvalidToken() from exc
    row = await session.get(GuestSession, guest_id)
    if row is None:
        raise InvalidToken("انتهت جلسةُ التجربة — ابدأ من جديد")
    row.last_seen_at = datetime.now(UTC)
    return row


async def expired(session: AsyncSession, *, now: datetime | None = None) -> list[str]:
    """**ما مضت عليه ثلاثون يوماً** — الجلساتُ ومعها ملاحظاتُها؛ يعيد مساراتِ الصور لتُمحى بعد الالتزام."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=RETENTION_DAYS)
    old = select(GuestSession.id).where(GuestSession.created_at < cutoff)
    paths = [
        path
        for path in (
            await session.scalars(select(AppFeedback.screenshot_path).where(AppFeedback.guest_session_id.in_(old)))
        ).all()
        if path
    ]
    await session.execute(delete(AppFeedback).where(AppFeedback.guest_session_id.in_(old)))
    await session.execute(delete(GuestSession).where(GuestSession.created_at < cutoff))
    await session.flush()
    return paths

