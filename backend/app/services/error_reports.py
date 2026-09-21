"""تجميعُ الأعطال وتقييدُها — **البصمةُ هي التي تقول «هذا هو هو»** (2026-09-20).

## البصمةُ: ستّةٌ فيها، واثنان خارجها بقصد

فيها: التطبيقُ، والباب، وصنفُ الاستثناء، **ورسالةٌ مُطبَّعة**، **وثلاثةُ
إطاراتٍ عُليا مُطبَّعة**.

**وخارجها الإصدار** — وهو أدقُّ ما في هذا الملفّ: لو دخل لانقسمت المجموعةُ عند
كلِّ نشرة، **فيضيع أنّ العطبَ يعيش منذ ثلاث نسخ**، وهو الخبرُ الذي يُبنى عليه
القرار. ويبقى مقروءاً في `first_seen_release` و`last_seen_release`.

**وخارجها المسارُ الخام**: `/rides/<مُعرِّف>/pay` يجعل كلَّ رحلةٍ مجموعةً.
والقالبُ داخلُ الرسالةِ المُطبَّعة حين يظهر فيها.

## والتطبيعُ يمحو ما يتغيّر بلا أن يتغيّر العطب

أرقامُ الأسطر تزحف بتعديلِ سطرٍ فوقها، وبصماتُ الحزم تتبدّل كلَّ بناء،
والمُعرِّفاتُ تختلف بكلِّ طلب. **وما يفرّق مجموعتين يجب أن يكون فرقاً حقيقيّاً**
— وإلا صار الجدولُ سجلَّ أحداثٍ بلا تجميع، وهو ما بُني ليمنعه.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from sqlalchemy import case, func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import scrub
from app.models.enums import ErrorStatus
from app.models.error_report import ErrorEvent, ErrorGroup, ErrorGroupDevice
from app.schemas.error_report import ErrorReportIn

#: ما يُمحى قبل البصمة — **كلُّها أشياءُ تتغيّر والعطبُ واحد**
_DIGITS = re.compile(r"\d+")
_QUOTED = re.compile(r"""(['"`])(?:\\.|(?!\1).)*\1""")
#: بصمةُ المحتوى في اسم الحزمة — `index-BFvAlehF.js` تتبدّل كلَّ بناء
_CHUNK_HASH = re.compile(r"-[A-Za-z0-9_-]{6,}(?=\.(?:js|css|mjs)\b)")


def _normalize_message(message: str) -> str:
    """رسالةٌ صالحةٌ للبصمة — بلا أرقامٍ ولا نصوصٍ مقتبسة.

    «Cannot read x of undefined at ride 3f2c» و«… at ride 9b1d» عطبٌ واحد.
    """
    text = _QUOTED.sub("''", message)
    text = _CHUNK_HASH.sub("", text)
    return _DIGITS.sub("#", text).strip()[:300]


def _top_frames(stack: str | None, *, count: int = 3) -> str:
    """أعلى إطاراتِ المكدَّس مُطبَّعةً — **وهي التي تقول أين وقع**.

    والأرقامُ تُمحى: سطرٌ يُضاف فوق الدالّة يزحف بكلِّ ما تحته، **فيصير العطبُ
    نفسُه مجموعةً جديدةً بلا أن يتغيّر شيء**.
    """
    if not stack:
        return ""
    frames = [line.strip() for line in stack.splitlines() if line.strip()]
    normalized = [
        _DIGITS.sub("#", _CHUNK_HASH.sub("", frame))[:160] for frame in frames[:count]
    ]
    return "\n".join(normalized)


def culprit_of(stack: str | None) -> str | None:
    """أعلى إطارٍ في الأثر — **كما هو، بأرقامه**.

    **ولا يُطبَّع هنا**: التطبيعُ للبصمة وحدَها، وهذا **يُعرض لإنسان** —
    و`Payment.tsx:#` لا تدلّه على شيء. فرقمُ السطر هو نصفُ الفائدة.

    **ولا يُحذف إطارُ مكتبةٍ منه**: قد يكون العطبُ داخلها بوسيطٍ أرسلناه،
    **وحذفُه يقطع الخيط** — والشاشةُ تقول إنها لا تفرّق الاثنين.
    """
    if not stack:
        return None
    for line in stack.splitlines():
        frame = line.strip()
        if not frame:
            continue
        # يُسقَط سطرُ العنوان (`TypeError: …`) ويُؤخذ أوّلُ إطارٍ بحقّ
        if frame.startswith("at "):
            return frame[3:][:200]
        if "(" in frame or ":" in frame.rsplit("/", 1)[-1]:
            return frame[:200]
    return None


def fingerprint_of(payload: ErrorReportIn, *, message: str, stack: str | None) -> str:
    """البصمةُ — **تُحسب بعد التنظيف لا قبله**.

    وبغير ذلك تدخل فيها قيمةٌ محجوبةٌ في موضعٍ وظاهرةٌ في آخر، **فينقسم العطبُ
    الواحدُ بحسب ما حُجب منه** — وهو أسوأُ من ألّا يُجمَّع أصلاً لأنه يُقرأ
    مُجمَّعاً.
    """
    parts = (
        payload.app.value,
        payload.kind.value,
        payload.name,
        _normalize_message(message),
        _top_frames(stack),
    )
    return hashlib.sha256("\u0000".join(parts).encode("utf-8")).hexdigest()


async def record(session: AsyncSession, payload: ErrorReportIn) -> ErrorEvent:
    """يُنظِّف ثمّ يُجمِّع ثمّ يُقيِّد — **بهذا الترتيب**.

    **ولا قفلَ صفٍّ هنا**، وهو قرارٌ لا سهو: `ON CONFLICT` يجعل الإدراجَ
    والزيادةَ فعلاً ذرّيّاً واحداً في القاعدة، **وهو أقوى من قفلٍ نأخذه نحن**
    لأنه لا يحتاج أن يكون الصفُّ موجوداً أصلاً — والحالةُ المتسابقةُ هنا هي
    **أوّلُ حدثين لعطبٍ جديد** بالضبط.

    **ولا يدخل هذا المسارُ ترتيبَ الأقفال** (`CLAUDE.md`): لا يمسّ رحلةً ولا
    دفعةً ولا محفظة، **ولا يُستدعى من داخل معاملةٍ تمسك أحدَها** — تقريرُ عطبٍ
    لا يجوز أن يُطيل قفلاً على مالِ أحد.
    """
    now = datetime.now(UTC)

    message = scrub.scrub_text(payload.message)
    stack = scrub.scrub_stack(payload.stack)
    component_stack = scrub.scrub_stack(payload.component_stack)
    route = scrub.safe_route(payload.route)
    breadcrumbs = scrub.scrub_breadcrumbs(payload.breadcrumbs)
    note = scrub.scrub_note(payload.note) if payload.note else None
    device_hash = scrub.hash_device(payload.device_hash)

    fingerprint = fingerprint_of(payload, message=message, stack=stack)

    group_stmt = (
        pg_insert(ErrorGroup)
        .values(
            fingerprint=fingerprint,
            app=payload.app,
            kind=payload.kind,
            name=payload.name[:200],
            title=message[:500],
            culprit=culprit_of(stack),
            event_count=payload.repeat,
            user_count=0,
            first_seen_at=now,
            last_seen_at=now,
            first_seen_release=payload.release,
            last_seen_release=payload.release,
        )
        .on_conflict_do_update(
            index_elements=[ErrorGroup.fingerprint],
            set_={
                "event_count": ErrorGroup.event_count + payload.repeat,
                "last_seen_at": now,
                "last_seen_release": payload.release,
                # **الأوّلُ يبقى**: حدثٌ بلا أثرٍ لا يمحو متَّهَماً عُرف،
                # وحدثٌ بأثرٍ يملأ الفراغَ إن كان أوّلُه بلا أثر.
                "culprit": func.coalesce(ErrorGroup.culprit, culprit_of(stack)),
                # **الارتداد**: محسومةٌ عادت تقع تُفتح من نفسها وتُوسَم.
                #
                # **ولا تُفتح المكتومة**: الكتمُ قرارٌ قائمٌ بأن لا تُرى، وفتحُها
                # بكلِّ حدثٍ يُفرِّغه من معناه — **والحسمُ دعوى أنه أُصلح، فعودتُه
                # تكذيبٌ لها**. وهما حالان لا حالٌ واحدةٌ بدرجتين.
                "status": case(
                    (ErrorGroup.status == ErrorStatus.RESOLVED, ErrorStatus.OPEN),
                    else_=ErrorGroup.status,
                ),
                "regressed_at": case(
                    (ErrorGroup.status == ErrorStatus.RESOLVED, now),
                    else_=ErrorGroup.regressed_at,
                ),
            },
        )
        .returning(ErrorGroup.id)
    )
    group_id = (await session.execute(group_stmt)).scalar_one()

    # **والجهازُ يُعدّ مرّةً واحدة**: القيدُ الفريدُ يردّ الثانيةَ، و`returning`
    # يقول **أأُدرج صفٌّ فعلاً** — فيزيد العدّادُ على إدراجٍ وقع لا على محاولة.
    device_stmt = (
        pg_insert(ErrorGroupDevice)
        .values(group_id=group_id, device_hash=device_hash, first_seen_at=now)
        .on_conflict_do_nothing(constraint="uq_error_group_devices_pair")
        .returning(ErrorGroupDevice.id)
    )
    if (await session.execute(device_stmt)).scalar_one_or_none() is not None:
        await session.execute(
            update(ErrorGroup)
            .where(ErrorGroup.id == group_id)
            .values(user_count=ErrorGroup.user_count + 1)
        )

    event = ErrorEvent(
        group_id=group_id,
        app=payload.app,
        kind=payload.kind,
        platform=payload.platform,
        os_version=payload.os_version,
        release=payload.release,
        channel=payload.channel,
        route=route,
        name=payload.name[:200],
        message=message,
        stack=stack,
        component_stack=component_stack,
        breadcrumbs=breadcrumbs,
        device_hash=device_hash,
        online=payload.online,
        repeat=payload.repeat,
        request_id=payload.request_id,
        user_reported=payload.kind.value == "user_report",
        note=note,
        occurred_at=payload.occurred_at,
        received_at=now,
    )
    session.add(event)
    await session.commit()
    return event


# ------------------------------------------------------------- الاحتفاظ

#: **الأحداثُ تُكنَس والمجموعاتُ تبقى** — العدّادُ تاريخٌ، والحدثُ تفصيلٌ يبلى
EVENT_RETENTION_DAYS = 30
#: **وما كتبه إنسانٌ يبقى أطول**: أندرُ ما يصلنا، ويُقرأ بعد شهرين
REPORTED_RETENTION_DAYS = 90
#: مجموعةٌ محسومةٌ بلا حدثٍ باقٍ — لا يبقى منها إلا سطرٌ لا يُقرأ
GROUP_RETENTION_DAYS = 90


async def sweep_retention(session: AsyncSession) -> tuple[int, int]:
    """يحذف ما مضى وقتُه — ويعيد (أحداثٌ، مجموعاتٌ).

    **ولا يُحذف شيءٌ يُقرأ**: المجموعةُ تبقى ما دام فيها حدثٌ واحد، **وعدّاداتُها
    لا تُنقص** — «وقع ٤٠ مرّةً لـ١٢ جهازاً» خبرٌ عن الماضي لا يبطل بكنس تفاصيله.
    """
    from datetime import timedelta

    from sqlalchemy import and_, delete, exists, or_

    now = datetime.now(UTC)

    events = await session.execute(
        delete(ErrorEvent).where(
            or_(
                and_(
                    ErrorEvent.user_reported.is_(False),
                    ErrorEvent.received_at
                    < now - timedelta(days=EVENT_RETENTION_DAYS),
                ),
                and_(
                    ErrorEvent.user_reported.is_(True),
                    ErrorEvent.received_at
                    < now - timedelta(days=REPORTED_RETENTION_DAYS),
                ),
            )
        )
    )

    groups = await session.execute(
        delete(ErrorGroup).where(
            ErrorGroup.status != ErrorStatus.OPEN,
            ErrorGroup.last_seen_at < now - timedelta(days=GROUP_RETENTION_DAYS),
            ~exists().where(ErrorEvent.group_id == ErrorGroup.id),
        )
    )

    await session.commit()
    return events.rowcount or 0, groups.rowcount or 0
