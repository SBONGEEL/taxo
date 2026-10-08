"""محادثةُ الرحلة بين الراكب والكبتن (SPEC §٦٦-أ/ب، `design/APPROVALS-DATA.md` §١) — **البيتُ الواحد لكلِّ ما يُكتب فيها ويُقرأ منها**.

## النافذة — **الخادمُ هو من يرفض، لا الشاشة**

**تُفتح حين يقبل الكبتن، وتُغلق حين تنتهي الرحلة** مكتملةً أو ملغاة (§٦٦-أ/١). **والنافذةُ هي `ACTIVE_DRIVER_STATUSES` نفسُها**
(قَبِل · وصل · بدأت · واقفةٌ عند محطة) لا قائمةٌ ثانيةٌ تُكتب هنا: حالةٌ جديدةٌ داخل الرحلة تدخل المحادثةَ وحدَها، **ولا تفترق
«الكبتنُ مشغول» عن «المحادثةُ مفتوحة»**. **وبعد الإغلاق تبقى مقروءةً للطرفين ولا يُكتب فيها.**

## الإرسالُ يقفل صفَّ الرحلة — **أوّلاً في ترتيب الأقفال**

**قبل فحص النافذة لا بعده** (`CLAUDE.md`): إنهاءٌ وإرسالٌ في اللحظة نفسِها يقرآن `in_progress` معاً بغير القفل، فتُحفظ رسالةٌ
**بعد** أن أُغلقت المحادثة. **والقفلُ يجعل أحدَهما ينتظر الآخر**: إمّا تسبق الرسالةُ الإنهاءَ، وإمّا تُردّ بـ`chat_closed` —
**ويقيس ذلك `test_trip_chat_concurrency.py` ويسقط بحذف القفل**. وصفُّ الرحلة أوّلُ الأقفال في المشروع كلِّه، فلا ترتيبَ يُخترع.

## من يرى — **طرفا الرحلة وحدهما، وغيرُهما ٤٠٤**

`rides.get_ride_for_party`: **لا ٤٠٣** — وجودُ الرحلة ليس معلومةً يستحقّها غيرُ طرفَيها (لا IDOR). **والمشرفُ ليس طرفاً**: له
بابُه في اللوحة بصلاحيته المستقلّة، **وكلُّ فتحٍ منه سطرٌ في التدقيق** (`admin_thread`).

## ما يُرفض قبل أن يُحفظ

رقمُ الهاتف بأيِّ صيغةٍ والروابطُ (`chat_filter`) — **فلا يُحفظ رقمٌ ليُحذف بعدها**. **والخاناتُ تُطبَّع لاتينيةً عند الكتابة**
(`core/digits`): قرارُ المالك «الأرقامُ لاتينية في كلِّ مكان» يحكم النصَّ الحرَّ كما يحكم عنوانَ المستلم.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import delete, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core import rate_limit
from app.core.digits import latin_digits
from app.core.exceptions import (
    Conflict,
    FeatureDisabled,
    InvalidInput,
    NotFound,
    RateLimited,
)
from app.models.enums import (
    AuditAction,
    CountryCode,
    FeatureKey,
    PolicyApp,
    PolicyDocType,
    RatingRaterType,
    RideMessageReportReason,
    RideMessageReportStatus,
    RideStatus,
)
from app.models.ride import ACTIVE_DRIVER_STATUSES, Ride
from app.models.service_setting import ServiceSetting
from app.models.trip_chat import MAX_BODY_CHARS, RideMessage, RideMessageReport
from app.models.user import User
from app.services import audit, chat_filter, policies, ride_log, settings_service
from app.services import rides as rides_service

#: **النافذةُ — حالاتُ «الكبتنُ مشغولٌ بهذه الرحلة» نفسُها** (انظر رأسَ الملف)
CHAT_WINDOW: frozenset[RideStatus] = frozenset(ACTIVE_DRIVER_STATUSES)

#: **عشرون رسالةً في الدقيقة لكلِّ مُرسِلٍ في رحلة** — ردودٌ قصيرةٌ متتابعة («وصلت»، «عند الباب») لا تبلغ نصفَها، **ونصٌّ آليٌّ
#: يُغرق هاتفَ الطرف الآخر بالإشعارات يقف عندها**. والعدّادُ لكلِّ رحلة: لا يحجب محادثةً أخرى لصاحبه
SEND_LIMIT = 20
SEND_WINDOW_SECONDS = 60

#: **السطرُ داخل المحادثة — بحرف التصميم المُقَرّ** (§١، الصياغاتُ الأربع). **ويُرسل من هنا لا يُكتب في التطبيقين**: نصٌّ واحدٌ
#: لهما، فلا يفترق ما يقرؤه الراكبُ عمّا يقرؤه الكبتن
IN_CHAT_NOTICE = "قد يراجع فريقُ TAXO رسائلَ هذه المحادثة للسلامة والجودة. ولا تُرسَل فيها أرقامُ الهواتف."

#: **عنوانُ القسم في سياسة الخصوصية** الذي يشترطه إشعالُ المفتاحين (§٦٦-ب/١١ — «يُنشر السطرُ قبل أن تحفظ المحادثةُ شيئاً»)
CHAT_PRIVACY_MARKER = "محادثةُ الرحلة ومكالمتُها"
#: **وعنوانُ قسم التسجيل** — يشترطه إشعالُ التسجيل (§٦٦-ج/١٦ — «يُضاف سطرُ الخصوصية للتسجيل قبل أيِّ تسجيل»)
RECORDING_PRIVACY_MARKER = "تسجيلُ المكالمات"

#: **مدّةُ الاحتفاظ لسوقٍ بلا صفّ** — افتراضُ العمود نفسُه (`ServiceSetting.chat_retention_days`)
DEFAULT_RETENTION_DAYS = 90
DEFAULT_RECORDING_RETENTION_DAYS = 30

#: **دفعةُ الحذف** — لا `DELETE` مكشوفٌ بمئات الألوف في معاملةٍ واحدة (سابقةُ `inbox.trim`)
PURGE_BATCH = 1000


def _now() -> datetime:
    return datetime.now(UTC)


# ═════════════════════════ الأخطاءُ — برموزها، والنصُّ بحرف التصميم


class ChatClosed(Conflict):
    """**بعد الإغلاق لا يُكتب شيء** — ولو من تطبيقٍ قديمٍ أو بنداءٍ مباشر."""

    code = "chat_closed"
    message = "انتهت الرحلة، وأُغلقت المحادثة."


class ChatPhoneNumber(InvalidInput):
    code = "chat_phone_number"
    message = "لا تُرسَل أرقامُ الهواتف في المحادثة."


class ChatLink(InvalidInput):
    code = "chat_link"
    message = "لا تُرسَل الروابطُ في المحادثة."


class ChatEmpty(InvalidInput):
    code = "chat_empty"
    message = "اكتب رسالتك أولاً."


class TripChatDisabled(FeatureDisabled):
    code = "trip_chat_disabled"
    message = "المحادثةُ داخل الرحلة غيرُ مفعّلةٍ في بلدك."


class ChatReportOwnMessage(InvalidInput):
    """**البلاغُ على رسالة الطرف الآخر وحدَها** — ورسالتُك أنت لا يُبلَّغ عنها."""

    code = "chat_report_own_message"
    message = "يُبلَّغ عن رسالة الطرف الآخر وحدَها."


class ChatReportHandled(Conflict):
    code = "chat_report_already_handled"
    message = "عولج هذا البلاغُ من قبل."


class PrivacyLineUnpublished(Conflict):
    """**لا يُشعَل ما يحفظ بياناتٍ قبل نشر سطرها** (§٦٦-ب/١١ و§٦٦-ج/١٦) — والرسالةُ تقول للمشرف ماذا ينشر أولاً."""

    code = "privacy_line_unpublished"

    def __init__(self, marker: str, missing: list[str]) -> None:
        apps = " و".join(missing)
        super().__init__(
            f"انشر أولاً في سياسة الخصوصية لـ{apps} نسخةً فيها قسمُ «{marker}»، ثمّ أشعِل.",
            marker=marker,
            missing=missing,
        )


class PrivacyLineInUse(Conflict):
    """**ولا يُنزع السطرُ وما يحفظه مشتعل** — نشرُ نسخةٍ بلاه أو سحبُ المنشورة كان يُبطل الشرطَ بعد أن مرّ (قِيس ٢٠٢٦-١٠-٠٨)."""

    code = "privacy_line_in_use"

    def __init__(self, marker: str, app_label: str, *, withdrawing: bool) -> None:
        verb = "تُسحب" if withdrawing else "تُنشر نسخةٌ من"
        super().__init__(
            f"لا {verb} سياسةُ خصوصية {app_label} بلا قسم «{marker}» وما يحفظه مشعلٌ في هذا السوق — "
            "أطفئه أولاً، أو انشر نسخةً فيها القسم.",
            marker=marker,
            app=app_label,
        )


# ═════════════════════════ الإعداداتُ والمفتاحُ والنافذة


@dataclass(frozen=True, slots=True)
class CommsSettings:
    """إعداداتُ المحادثة والمكالمة لسوقٍ واحد — **وسوقٌ بلا صفٍّ يُقرأ بافتراض الأعمدة نفسِها** لا برقمٍ ثانٍ هنا."""

    chat_retention_days: int = DEFAULT_RETENTION_DAYS
    call_recording_enabled: bool = False
    call_recording_retention_days: int = DEFAULT_RECORDING_RETENTION_DAYS


async def settings_for(session: AsyncSession, country: CountryCode) -> CommsSettings:
    row = await session.get(ServiceSetting, country)
    if row is None:
        return CommsSettings()
    return CommsSettings(
        chat_retention_days=row.chat_retention_days,
        call_recording_enabled=row.call_recording_enabled,
        call_recording_retention_days=row.call_recording_retention_days,
    )


async def chat_enabled(session: AsyncSession, country: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(session, country, FeatureKey.TRIP_CHAT_ENABLED)


#: **التطبيقان اللذان يحملان السطر** وتسميتُهما في رسالة الردّ — محادثةٌ بين راكبٍ وكبتنٍ تحفظ ما كتبه الاثنان
_APP_LABELS = {PolicyApp.RIDER: "الراكب", PolicyApp.DRIVER: "الكبتن"}


async def require_published_line(session: AsyncSession, country: CountryCode, marker: str) -> None:
    """**سياستا الخصوصية المنشورتان الآن — للراكب وللكبتن — تحملان القسمَ**، وإلا يُردّ الإشعال.

    **«المنشورة» لا «أحدثُ نسخة»** (`policies.published`): مسوّدةٌ فيها السطرُ لم يقرأها أحد، **ونصٌّ لم يُنشر لا يُخبر أحداً**.
    **والسوقان كلاهما يُسأل عنهما**: محادثةٌ بين راكبٍ وكبتنٍ تحفظ ما كتبه الاثنان، فسطرٌ عند أحدهما وحدَه يُخبر نصفَ من نحفظ عنهم.
    """
    missing: list[str] = []
    for app, label in _APP_LABELS.items():
        policy = await policies.published(
            session, country=country, doc_type=PolicyDocType.PRIVACY_POLICY, app=app
        )
        if policy is None or marker not in policy.body_ar:
            missing.append(label)
    if missing:
        raise PrivacyLineUnpublished(marker, missing)


async def require_line_kept(
    session: AsyncSession, *, country: CountryCode, app: PolicyApp, body_after: str | None, withdrawing: bool
) -> None:
    """**الوجهُ الثاني للشرط نفسِه**: ما دام ما يحفظه السطرُ مشتعلاً في السوق، **لا تصير سياسةُ الخصوصية المنشورةُ بلاه**.

    `require_published_line` يُسأل لحظةَ الإشعال وحدَها، **ونشرُ نسخةٍ بلا القسم أو سحبُ المنشورة بعدها كان يُبقي المحادثةَ
    تحفظ والسطرُ غائب** — فيصير «يُنشر السطرُ قبل أن تحفظ المحادثةُ شيئاً» صحيحاً يوماً واحداً. **فالشرطُ قائمٌ ما دام المفتاح**:
    يُنادى من `policies.publish` (`body_after` نصُّ النسخة الجديدة) و`policies.withdraw` (`None`: لا منشورةَ بعدها).

    - «محادثةُ الرحلة ومكالمتُها» ما دام مفتاحُ المحادثة **أو** المكالمة مشتعلاً.
    - «تسجيلُ المكالمات» ما دام التسجيلُ مشتعلاً.

    **والإطفاءُ ثمّ النشرُ طريقُه** — ولا يُعدَّل السطرُ إلا بنسخةٍ تحمله.
    """
    label = _APP_LABELS.get(app)
    if label is None:
        return
    needed: list[str] = []
    if await chat_enabled(session, country) or await settings_service.is_feature_enabled(
        session, country, FeatureKey.RIDE_CALLS_ENABLED
    ):
        needed.append(CHAT_PRIVACY_MARKER)
    if (await settings_for(session, country)).call_recording_enabled:
        needed.append(RECORDING_PRIVACY_MARKER)
    for marker in needed:
        if body_after is None or marker not in body_after:
            raise PrivacyLineInUse(marker, label, withdrawing=withdrawing)


@dataclass(frozen=True, slots=True)
class Party:
    """**صاحبُ الطلب في هذه الرحلة** — جانبُه، والطرفُ الآخر. **ويُقرأ من الرحلة لا من أدوار الحساب** (§22)."""

    ride_id: uuid.UUID
    country_code: CountryCode
    side: RatingRaterType
    user_id: uuid.UUID
    other_user_id: uuid.UUID | None
    rider_user_id: uuid.UUID
    driver_user_id: uuid.UUID | None


def party_of(ride: Ride, user: User) -> Party:
    """جانبُ المستخدم في رحلةٍ مُحمَّلةِ الكبتن — **ولا يُنادى إلا بعد `get_ride_for_party`** فالطرفُ مضمونٌ هنا."""
    driver_user_id = ride.driver.user_id if ride.driver is not None else None
    if ride.rider_id == user.id:
        side, other = RatingRaterType.RIDER, driver_user_id
    elif driver_user_id == user.id:
        side, other = RatingRaterType.DRIVER, ride.rider_id
    else:  # pragma: no cover - `get_ride_for_party` يردّه قبل هذا السطر
        raise NotFound("الرحلة غير موجودة")
    return Party(
        ride_id=ride.id,
        country_code=ride.country_code,
        side=side,
        user_id=user.id,
        other_user_id=other,
        rider_user_id=ride.rider_id,
        driver_user_id=driver_user_id,
    )


async def lock_ride(session: AsyncSession, ride_id: uuid.UUID) -> RideStatus:
    """**يقفل صفَّ الرحلة ويعيد حالَها الملتزَمة** — أوّلُ الأقفال في ترتيب المشروع.

    **عمودٌ لا صفٌّ كامل**: `SELECT status … FOR UPDATE` يقرأ أحدثَ نسخةٍ ملتزَمةٍ بعد انتظار القفل (READ COMMITTED)، **فلا يُقرأ
    حالٌ قديمٌ من خريطة الهويّة** — وهو ما يحتاج `populate_existing` حين يُحمَّل الصفُّ كلُّه.
    """
    status = await session.scalar(select(Ride.status).where(Ride.id == ride_id).with_for_update())
    if status is None:  # pragma: no cover - الرحلةُ لا تُحذف
        raise NotFound("الرحلة غير موجودة")
    return status


# ═════════════════════════ الطرفان


def _clean(body: str) -> str:
    """النصُّ كما يُحفظ: **بلا فراغٍ في طرفيه، وبخاناتٍ لاتينية** — والفارغُ يُردّ برمزه."""
    text = latin_digits(body.strip())
    if not text:
        raise ChatEmpty()
    if len(text) > MAX_BODY_CHARS:  # pragma: no cover - المخطَّطُ يردّه قبل هنا
        raise InvalidInput(f"الرسالةُ أطولُ من {MAX_BODY_CHARS} حرف")
    return text


async def send(
    session: AsyncSession, redis: Redis, *, ride_id: uuid.UUID, user: User, body: str
) -> tuple[RideMessage, Party]:
    """**رسالةٌ من أحد الطرفين** — والترتيبُ هو الحماية: الملكيةُ ثمّ المفتاحُ ثمّ النصُّ ثمّ القفلُ والنافذة. الـcommit للراوتر.

    **الملكيةُ أوّلاً** فلا يصير فحصُ النصّ باباً يُسأل منه عن رحلةٍ لغيرك. **والنافذةُ تُفحص مرّتين**: بلا قفلٍ لتُردّ رحلةٌ منتهيةٌ
    بلا انتظار، **ثمّ تحت القفل** — وهي وحدَها الحكم.
    """
    ride = await rides_service.get_ride_for_party(session, ride_id, user)
    party = party_of(ride, user)
    if not await chat_enabled(session, ride.country_code):
        raise TripChatDisabled()
    if ride.status not in CHAT_WINDOW:
        raise ChatClosed()

    text = _clean(body)
    # **لوحةُ مركبة هذه الرحلة وحدَها تمرّ** — «13-12345» سبعُ خانات، وهي ما يكتبه الراكبُ والكبتنُ ليتعارفا عند الالتقاط، ويراها
    # الراكبُ أصلاً في بطاقة كبتنه (`ride_log.plate_of` — المركبةُ نفسُها). **ولا يُستثنى شكلُ اللوحة عامّةً**: ذلك يُمرّر كلَّ رقمٍ
    # يُكتب بشكل لوحة (`chat_filter.check`)
    plate = ride_log.plate_of(ride)
    violation = chat_filter.check(text, allowed=(plate,) if plate else ())
    if violation is chat_filter.Violation.PHONE:
        raise ChatPhoneNumber()
    if violation is chat_filter.Violation.LINK:
        raise ChatLink()

    limit = await rate_limit.hit(
        redis, f"trip-chat:{ride.id}:{user.id}", limit=SEND_LIMIT, window_seconds=SEND_WINDOW_SECONDS
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    if await lock_ride(session, ride.id) not in CHAT_WINDOW:
        raise ChatClosed()

    message = RideMessage(
        ride_id=ride.id, sender_id=user.id, sender_role=party.side, body=text, created_at=_now()
    )
    session.add(message)
    await session.flush()
    return message, party


async def deliver(session: AsyncSession, redis: Redis, message: RideMessage, party: Party) -> None:
    """**بعد الالتزام**: الحدثُ للطرفين على المقبس، **والإشعارُ للطرف الآخر بلا نصّ** إن لم يكن تطبيقُه أمامه."""
    from app.services import notifications
    from app.ws import events

    payload = {
        "ride_id": str(message.ride_id),
        "message": {
            "id": str(message.id),
            "sender_role": message.sender_role.value,
            "body": message.body,
            "created_at": message.created_at.isoformat(),
            "read_at": None,
        },
    }
    await events.publish_trip_comms(
        redis,
        [party.rider_user_id, party.driver_user_id],
        event=events.TripCommsEvent.CHAT_MESSAGE,
        payload=payload,
    )
    if party.other_user_id is not None:
        await notifications.publish_chat_push(
            session,
            redis,
            recipient_id=party.other_user_id,
            ride_id=message.ride_id,
            sender_role=message.sender_role.value,
        )


@dataclass(slots=True)
class Thread:
    ride: Ride
    party: Party
    messages: list[RideMessage]
    open: bool
    can_call: bool
    unread: int
    read_at: datetime | None


async def read_thread(session: AsyncSession, *, ride_id: uuid.UUID, user: User) -> Thread:
    """**المحادثةُ لطرفها** — **وفتحُها يعلّم رسائلَ الطرف الآخر مقروءة**. الـcommit للراوتر.

    **ومقروءةٌ بعد الإغلاق** ما دامت محفوظة (مفقوداتٌ، أو خلافٌ على دفعة) — `open` يقول هل يُكتب فيها. **و`unread` عددُ ما كان
    جديداً عند هذا الفتح** — وهو ما علّمه الفتحُ نفسُه مقروءاً.
    """
    from app.services import ride_calls

    ride = await rides_service.get_ride_for_party(session, ride_id, user)
    party = party_of(ride, user)
    now = _now()
    marked = (
        await session.scalars(
            update(RideMessage)
            .where(
                RideMessage.ride_id == ride.id,
                RideMessage.sender_role != party.side,
                RideMessage.read_at.is_(None),
            )
            .values(read_at=now)
            .returning(RideMessage.id)
        )
    ).all()
    messages = list(
        (
            await session.scalars(
                select(RideMessage)
                .where(RideMessage.ride_id == ride.id)
                .order_by(RideMessage.created_at, RideMessage.id)
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    in_window = ride.status in CHAT_WINDOW
    return Thread(
        ride=ride,
        party=party,
        messages=messages,
        open=in_window and await chat_enabled(session, ride.country_code),
        can_call=in_window and await ride_calls.calls_enabled(session, ride.country_code),
        unread=len(marked),
        read_at=now if marked else None,
    )


async def announce_read(redis: Redis, thread: Thread) -> None:
    """**«قُرئت»** للطرف الآخر بعد الالتزام — وقتُ القراءة وحدَه، فيعلّم تطبيقُه ما قبله."""
    from app.ws import events

    if thread.read_at is None or thread.party.other_user_id is None:
        return
    await events.publish_trip_comms(
        redis,
        [thread.party.other_user_id],
        event=events.TripCommsEvent.CHAT_READ,
        payload={"ride_id": str(thread.ride.id), "read_at": thread.read_at.isoformat()},
    )


async def report(
    session: AsyncSession,
    *,
    ride_id: uuid.UUID,
    message_id: uuid.UUID,
    user: User,
    reason: RideMessageReportReason,
    note: str | None,
) -> RideMessageReport:
    """**«أبلغ عن الرسالة»** — على رسالة الطرف الآخر وحدَها، **وبلاغٌ واحدٌ لكلِّ مُبلِّغ** (الضغطةُ الثانية تعيد الأوّل).

    **ومسموحٌ بعد الإغلاق**: الإساءةُ تُرى بعد أن تنتهي الرحلة. **ولا يمرّ بالقفل**: لا انتقالَ حالٍ هنا، والفريدُ في القاعدة
    يحرس التكرار (`ON CONFLICT DO NOTHING`).
    """
    ride = await rides_service.get_ride_for_party(session, ride_id, user)
    party = party_of(ride, user)
    message = await session.scalar(
        select(RideMessage).where(RideMessage.id == message_id, RideMessage.ride_id == ride.id)
    )
    if message is None:
        raise NotFound("الرسالة غير موجودة")
    if message.sender_role == party.side:
        raise ChatReportOwnMessage()

    cleaned = latin_digits(note.strip()) if note and note.strip() else None
    await session.execute(
        pg_insert(RideMessageReport)
        .values(
            id=uuid.uuid4(),
            message_id=message.id,
            reporter_id=user.id,
            reason=reason,
            note=cleaned,
            status=RideMessageReportStatus.OPEN,
            created_at=_now(),
        )
        .on_conflict_do_nothing(constraint="uq_ride_message_reports_message_id_reporter_id")
    )
    row = await session.scalar(
        select(RideMessageReport).where(
            RideMessageReport.message_id == message.id, RideMessageReport.reporter_id == user.id
        )
    )
    assert row is not None  # أُدرج للتوّ أو كان قائماً
    return row


# ═════════════════════════ اللوحة — **وكلُّ فتحٍ سطرٌ في التدقيق**


@dataclass(slots=True)
class AdminThread:
    ride: Ride
    messages: list[RideMessage]
    names: dict[uuid.UUID, str]
    open_reports: dict[uuid.UUID, int]


async def _names(session: AsyncSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {value for value in ids if value is not None}
    if not wanted:
        return {}
    rows = await session.execute(select(User.id, User.name).where(User.id.in_(wanted)))
    return {row.id: row.name for row in rows}


async def admin_thread(session: AsyncSession, *, ride_id: uuid.UUID, actor: User) -> AdminThread:
    """**محادثةُ رحلةٍ كما يقرؤها مشرفٌ مُنح الصلاحية** — **وقيدُ التدقيق في المعاملة نفسِها** (الـcommit للراوتر).

    **كلُّ فتحٍ سطر** — بلا نافذة الخمس عشرة دقيقة التي للخريطة الحيّة (§١ «من يرى»): من، وأيَّ محادثة، ومتى، وكم رسالة.
    **ولا نصَّ في السطر**: سجلُّ التدقيق يبقى بعد أن تُحذف الرسائل، فلا يصير هو نسختَها.
    **ولا تُعلَّم مقروءةً**: «قُرئت» تقول للطرف الآخر إن صاحبَه رآها، لا إن مشرفاً رآها.
    """
    ride = await rides_service.get_ride(session, ride_id)
    messages = list(
        (
            await session.scalars(
                select(RideMessage)
                .where(RideMessage.ride_id == ride.id)
                .order_by(RideMessage.created_at, RideMessage.id)
            )
        ).all()
    )
    counts: dict[uuid.UUID, int] = {}
    if messages:
        rows = await session.execute(
            select(RideMessageReport.message_id, func.count(RideMessageReport.id))
            .where(
                RideMessageReport.message_id.in_([message.id for message in messages]),
                RideMessageReport.status == RideMessageReportStatus.OPEN,
            )
            .group_by(RideMessageReport.message_id)
        )
        counts = {row[0]: int(row[1]) for row in rows}
    driver_user_id = ride.driver.user_id if ride.driver is not None else None
    names = await _names(session, {ride.rider_id, driver_user_id, *(message.sender_id for message in messages)})

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.READ,
        entity_type="ride_chat",
        entity_id=ride.id,
        details={"ride_id": str(ride.id), "message_count": len(messages)},
    )
    return AdminThread(ride=ride, messages=messages, names=names, open_reports=counts)


@dataclass(slots=True)
class ReportRow:
    report: RideMessageReport
    message: RideMessage
    ride_id: uuid.UUID
    country_code: CountryCode
    names: dict[uuid.UUID, str]
    reporter_role: RatingRaterType | None


async def _report_rows(session: AsyncSession, reports: list[RideMessageReport]) -> list[ReportRow]:
    """**البانِي الواحد** لصفوف البلاغات — يخدم القائمةَ وبابَ المعالجة، فلا يملأ أحدُهما حقلاً ينساه الآخر (الشكلُ الثامن)."""
    if not reports:
        return []
    messages = {
        message.id: message
        for message in (
            await session.scalars(
                select(RideMessage).where(RideMessage.id.in_([report.message_id for report in reports]))
            )
        ).all()
    }
    rides = {
        row.id: row
        for row in (
            await session.execute(
                select(Ride.id, Ride.country_code, Ride.rider_id).where(
                    Ride.id.in_({message.ride_id for message in messages.values()})
                )
            )
        ).all()
    }
    names = await _names(
        session,
        {
            *(report.reporter_id for report in reports),
            *(report.handled_by for report in reports),
            *(message.sender_id for message in messages.values()),
        },
    )
    rows: list[ReportRow] = []
    for report in reports:
        message = messages[report.message_id]
        ride = rides[message.ride_id]
        # **المُبلِّغُ هو الطرفُ الآخر بالتعريف** — والقيدُ في بابه (`ChatReportOwnMessage`)
        reporter_role = (
            RatingRaterType.DRIVER if message.sender_role is RatingRaterType.RIDER else RatingRaterType.RIDER
        )
        rows.append(
            ReportRow(
                report=report,
                message=message,
                ride_id=ride.id,
                country_code=ride.country_code,
                names=names,
                reporter_role=reporter_role if report.reporter_id is not None else None,
            )
        )
    return rows


async def list_reports(
    session: AsyncSession,
    *,
    actor: User,
    status: RideMessageReportStatus | None,
    country: CountryCode | None,
    limit: int,
    offset: int,
) -> list[ReportRow]:
    """**«الرسائلُ المبلَّغُ عنها»** — الرسالةُ ومرسلُها ومن أبلغ والسببُ والرحلةُ والحال. **وفتحُها يُدقَّق**: فيها نصُّ محادثات."""
    stmt = (
        select(RideMessageReport)
        .join(RideMessage, RideMessage.id == RideMessageReport.message_id)
        .join(Ride, Ride.id == RideMessage.ride_id)
        # **المفتوحُ أوّلاً** — هو ما ينتظر أحداً
        .order_by(
            (RideMessageReport.status == RideMessageReportStatus.OPEN).desc(),
            RideMessageReport.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(RideMessageReport.status == status)
    if country is not None:
        stmt = stmt.where(Ride.country_code == country)
    reports = list((await session.scalars(stmt)).all())

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.READ,
        entity_type="chat_reports",
        details={
            "status": status.value if status else None,
            "country_code": country.value if country else None,
            "count": len(reports),
        },
    )
    return await _report_rows(session, reports)


async def handle_report(
    session: AsyncSession, *, report_id: uuid.UUID, actor: User, note: str
) -> ReportRow:
    """**«عولج»** — والصفُّ يُقفل **قبل** فحص حاله (`CLAUDE.md`): معالجتان معاً تقرآن `open` بغيره فتكتبان معالِجين ووقتين.

    **ومعه يبدأ عدّادُ حذف المحادثة** (`handled_at`) — فالمعالجةُ تُطلق ما كان البلاغُ يُبقيه.
    """
    report = await session.scalar(
        select(RideMessageReport)
        .where(RideMessageReport.id == report_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if report is None:
        raise NotFound("البلاغ غير موجود")
    if report.status is not RideMessageReportStatus.OPEN:
        raise ChatReportHandled()

    report.status = RideMessageReportStatus.HANDLED
    report.handled_by = actor.id
    report.handled_at = _now()
    report.handled_note = note.strip() or None
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="ride_message_report",
        entity_id=report.id,
        changes={"status": {"before": "open", "after": "handled"}},
    )
    return (await _report_rows(session, [report]))[0]


# ═════════════════════════ الحذفُ في موعده — ومع الحساب


def _retention_cutoff(now: datetime):
    """**آخرُ لحظةٍ يبقى ما قبلها** لكلِّ سوقٍ بمدّته — والسوقُ بلا صفٍّ بافتراض العمود."""
    days = func.coalesce(ServiceSetting.chat_retention_days, DEFAULT_RETENTION_DAYS)
    return literal(now) - func.make_interval(0, 0, 0, days)


async def purge_expired(session: AsyncSession, *, now: datetime | None = None, batch: int = PURGE_BATCH) -> dict[str, int]:
    """**دفعةٌ واحدةٌ من الحذف** — والمهمّةُ تعيدها حتى تفرغ. الـcommit للمستدعي.

    **ما يُحذف**:

    ١) **رسائلُ رحلةٍ انتهت قبل مدّة سوقها** (`chat_retention_days`، ٩٠ افتراضاً) — **إلا محادثةً فيها بلاغٌ مفتوح**: تبقى كلُّها
       حتى يُعالَج، **ثمّ تجري المدّةُ من آخر معالجة**. **والمحادثةُ كلُّها لا الرسالةُ وحدَها** (§١ «إلا محادثةً فيها بلاغ»):
       من يعالج البلاغَ يقرأ الرسالةَ في سياقها، ورسالةٌ مبلَّغٌ عنها بلا ما قبلها لا يُحكم عليها.
    ٢) **رسائلُ صاحب حسابٍ حُذف** — ما بقي منها لأنه كان تحت بلاغٍ مفتوح، **حين يُعالَج** (§١ «وحذفُ الحساب»).

    **وسجلُّ المكالمات بالمدّة نفسِها** يحذفه `ride_calls.purge_expired` — والتسجيلاتُ بمدّتها هي.
    """
    now = now or _now()
    message = aliased(RideMessage)
    report = aliased(RideMessageReport)
    cutoff = _retention_cutoff(now)
    ended = func.coalesce(Ride.completed_at, Ride.cancelled_at)

    open_in_ride = (
        select(report.id)
        .join(message, message.id == report.message_id)
        .where(message.ride_id == Ride.id, report.status == RideMessageReportStatus.OPEN)
        .correlate(Ride)
        .exists()
    )
    last_handled = (
        select(func.max(report.handled_at))
        .join(message, message.id == report.message_id)
        .where(message.ride_id == Ride.id)
        .correlate(Ride)
        .scalar_subquery()
    )
    # **المعرّفاتُ تُقرأ ثمّ تُحذف** — لا `DELETE … IN (SELECT …)` تُقرّر مكتبةُ الاستعلام ربطَ جدوله بالخارجيّ أو لا
    expired_ids = (
        await session.scalars(
            select(RideMessage.id)
            .join(Ride, Ride.id == RideMessage.ride_id)
            .outerjoin(ServiceSetting, ServiceSetting.country_code == Ride.country_code)
            .where(
                ended.is_not(None),
                ended < cutoff,
                ~open_in_ride,
                or_(last_handled.is_(None), last_handled < cutoff),
            )
            .order_by(RideMessage.created_at)
            .limit(batch)
        )
    ).all()
    if expired_ids:
        await session.execute(delete(RideMessage).where(RideMessage.id.in_(expired_ids)))

    open_on_message = (
        select(report.id)
        .where(report.message_id == RideMessage.id, report.status == RideMessageReportStatus.OPEN)
        .correlate(RideMessage)
        .exists()
    )
    orphaned_ids = (
        await session.scalars(
            select(RideMessage.id)
            .join(User, User.id == RideMessage.sender_id)
            .where(User.deleted_at.is_not(None), ~open_on_message)
            .limit(batch)
        )
    ).all()
    if orphaned_ids:
        await session.execute(delete(RideMessage).where(RideMessage.id.in_(orphaned_ids)))
    return {"messages": len(expired_ids), "deleted_accounts": len(orphaned_ids)}


async def erase_for_account(session: AsyncSession, user_id: uuid.UUID) -> int:
    """**حذفُ الحساب يحذف رسائلَ صاحبه** (§١) — **إلا ما كان تحت بلاغٍ مفتوح**: يبقى حتى يُعالَج ثمّ يحذفه الكنس (`purge_expired`/٢).

    **وسطرُه الحرُّ في بلاغاته يُمحى** («نصٌّ حرٌّ كتبه» — كتعليق التقييم في `account_deletion`)، **والبلاغُ نفسُه يبقى**: هو
    أثرُ رسالة الطرف الآخر لا بياناتُ المُبلِّغ. يُنادى من `account_deletion._anonymize` وصفُّ الحساب مقفول.
    """
    report = aliased(RideMessageReport)
    open_on_message = (
        select(report.id)
        .where(report.message_id == RideMessage.id, report.status == RideMessageReportStatus.OPEN)
        .correlate(RideMessage)
        .exists()
    )
    doomed = (
        await session.scalars(
            select(RideMessage.id).where(RideMessage.sender_id == user_id, ~open_on_message)
        )
    ).all()
    if doomed:
        await session.execute(delete(RideMessage).where(RideMessage.id.in_(doomed)))
    await session.execute(
        update(RideMessageReport).where(RideMessageReport.reporter_id == user_id).values(note=None)
    )
    return len(doomed)
