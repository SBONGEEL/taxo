"""مكالمةُ الرحلة — صوتٌ داخل التطبيق بـWebRTC بين طرفَي الرحلة وحدهما (SPEC §٦٦-ج، §٦٦-د/٢–٦).

## الإشارةُ بـREST، والتمريرُ بالمقبس القائم — **ولمَ لا إطاراتٌ على المقبس**

العرضُ والجوابُ ومرشّحو ICE **تُرسل `POST /calls/{id}/signal`** ويمرّرها الخادمُ إلى الطرف الآخر على قناته في المقبس القائم
(`ws:user:{id}`). **وكان ممكناً أن تُقرأ إطاراتٍ على المقبس نفسِه** — يقرأ مقبسا الراكب والكبتن إطاراتٍ اليوم (الموقع والظهور) —
**لكنّ مقبسَ الكبتن هو مفتاحُ «متصل»** (فتحُه يرفعه إلى التوزيع وإغلاقُه ينزله)، **فحمّلُه منطقَ مكالمةٍ يجعل عطباً فيها يُسقط
الكبتنَ من التوزيع**. والبابُ يمرّ بالحرّاس القائمين كلِّها (الجلسة، والحظر، والملكية) بلا نسخة، **ويُقاس باختبارٍ يرسل ويقرأ**.

## النافذة — **ولا تصير مكالمةٌ جاريةً بعد خروج الرحلة منها**

**البدءُ والردُّ يقفلان صفَّ الرحلة أولاً** ثمّ صفَّ المكالمة. **وإنهاءُ الرحلة وإلغاؤها يُغلقان المكالمةَ الحيّة في معاملتهما**
(`end_for_ride`، وصفُّ الرحلة مقفول) **بسبب `ride_ended`** — فردٌّ يسابق الإنهاءَ ينتظر قفلَ الرحلة ثمّ يجد النافذةَ مغلقة.

**وترتيبُ الأقفال**: **صفُّ الرحلة ← صفوفُ مكالمتها ← الدفعة ← … ← المحفظة** (ترتيبُ `CLAUDE.md` بعدها كما هو). **فالمكالمةُ
ليست آخرَ الأقفال**: `complete_ride`/`cancel_ride` يقفلان بعد `end_for_ride` الدفعةَ والحجزَ والحسابَ (`_record_gender_mismatch`)
ورسمَ الإلغاء والمحفظة. **والقاعدةُ: لا يأخذ مسارٌ صفَّ مكالمةٍ حيّةٍ بعد أيِّ قفلٍ يلي الرحلة** — الإنهاءُ والرفضُ والإشارةُ والإقرارُ
والرفعُ يقفلون صفَّ المكالمة وحدَه ولا شيءَ بعده. **والاستثناءُ الوحيدُ مكتوب**: حذفُ الحساب (`erase_recordings_for_account`) يكتب
بعد قفلَي الحساب والمحفظة صفوفَ مكالماتٍ **منتهيةٍ تحمل تسجيلاً** — والتسجيلُ لا يُرفع إلا لمنتهية، **فهي غيرُ الصفوف الحيّة التي
يقفلها مسارُ الرحلة**، ولا دائرةَ بينهما.

## الرنينُ ثلاثون ثانية — **يُقرأ كسولاً، ويُكنس كلَّ دقيقة**

مكالمةٌ ترنّ أكثرَ من ثلاثين ثانيةً **فائتةٌ في كلِّ قراءة** (`_stale`): لا يُردّ عليها، **ولا تحجب مكالمةً جديدة** (البدءُ يُغلقها
`no_answer` في معاملته). **وقراءةٌ كسولةٌ وحدَها لا تكفي**: مكالمةٌ لا يلمسها أحدٌ تبقى «ترنّ» في السجلّ، **ولا يُرسل إشعارُ
«مكالمةٌ فائتة»** (§٦٦-د/٤) — فمهمّةٌ صغيرةٌ كلَّ دقيقة (`expire_ringing`) تُغلقها وتُخبر. **والكسولُ هو الحكم، والمهمّةُ تُنظّف.**

**والتطبيقُ مغلقٌ يرنّ بخدمته الأصليّة** (§٦٦-ج/١٧، الحزمةُ «2.0»): الرنينُ يصلها بياناتٍ وحدَها بعمره، **وكلُّ ما يُسكته يُسكتها**
— الردُّ والرفضُ وقطعُ المتصل والفواتُ وانتهاءُ الرحلة (`publish_answered`/`publish_ended` ← `_silence`). **ومن فتح مقبسَه
ورنينٌ قائمٌ له يصله إطارُه** (`ringing_frame`): الخدمةُ تطوي رنينَها حين يظهر التطبيق، فالشاشةُ هي من يرنّ بعدها.

## المُرحِّلُ — coturn على خادمنا، وبياناتُ دخولٍ مؤقّتة

`use-auth-secret`: اسمُ المستخدم `"{انتهاء}:{معرّف}"` وكلمتُه `base64(hmac_sha1(السرّ، الاسم))` بعمر ساعتين (أطولُ من أطول مكالمة:
تجديدُ الحجز أثناءها يحمل الختمَ نفسَه — `core/config.py`) — **لطرفَي الرحلة
وحدهما وفي النافذة وحدَها** (تُصدر مع البدء والردّ فقط). **وبلا سرٍّ أو عناوين** (التطوير والاختبار) تخرج القائمةُ فارغةً ويتّصل
الطرفان بمرشّحي الشبكة المحلّية. **ولا STUN/TURN لغيرنا أبداً** (قرارُ المالك).

## التسجيل — **مطفأٌ افتراضاً، والتنبيهُ يسبق دائماً بحكم الخادم**

حين يُشعله المالكُ لسوق (`service_settings.call_recording_enabled`): البدءُ يردّ `recording: true` · **عرضُ المتصل لا يُمرَّر حتى
يُقِرّ** (`recording-notice`) **ولا ترنّ عند الطرف الآخر حتى يُقِرّ** (الرنينُ يُبثّ من الإقرار، وثلاثونُه منه) · **وردُّ المتصَل به يُرفض بلا `recording_notice_ack`** (`call_recording_notice_required`) · والتسجيلُ
يُرفع بعد المكالمة من جهاز المتصل بسقفٍ وصيغتين (webm/ogg) وتاريخِ حذف · **والاستماعُ صلاحيةٌ مستقلّةٌ وكلُّ استماعٍ سطرٌ في التدقيق**.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import delete, func, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit, storage
from app.core.config import settings
from app.core.exceptions import Conflict, FeatureDisabled, InvalidInput, NotFound, RateLimited
from app.models.enums import (
    AuditAction,
    CountryCode,
    FeatureKey,
    RatingRaterType,
    RideCallEndReason,
    RideCallStatus,
)
from app.models.ride import Ride
from app.models.ride_call import LIVE_STATUSES, RideCall
from app.models.service_setting import ServiceSetting
from app.models.user import User
from app.services import audit, settings_service, trip_chat
from app.services import rides as rides_service

#: **الرنينُ ثلاثون ثانية** — بعدها «لم يُردّ» (`no_answer`)
RING_TIMEOUT_SECONDS = 30

#: **ستُّ مكالماتٍ في عشر دقائق لكلِّ متصلٍ في رحلة** — إعادةُ الاتصال بعد شبكةٍ ضعيفةٍ لا تبلغها، **ورنينٌ متكرّرٌ لإزعاج الطرف
#: الآخر يقف عندها** (المكالمةُ بابُ مضايقةٍ كما الرسالة)
START_LIMIT = 6
START_WINDOW_SECONDS = 600

#: **مرشّحو ICE دفعاتٌ قصيرة** — مكالمةٌ واحدةٌ نحو عشراتٍ منها مع العرض والجواب، فثلاثمئةٌ في الدقيقة لا يبلغها اتصالٌ سليم
SIGNAL_LIMIT = 300
SIGNAL_WINDOW_SECONDS = 60
#: **أكبرُ إشارة** — عرضُ SDP لصوتٍ وحدَه بضعةُ كيلوبايتات، فستّةَ عشرَ تتّسع ولا تجعل البابَ ممرَّ ملفّات
MAX_SIGNAL_BYTES = 16 * 1024


def _now() -> datetime:
    return datetime.now(UTC)


# ═════════════════════════ الأخطاء


class RideCallsDisabled(FeatureDisabled):
    code = "ride_calls_disabled"
    message = "المكالمةُ داخل التطبيق غيرُ مفعّلةٍ في بلدك."


class CallWindowClosed(Conflict):
    """**لا مكالمةَ خارج نافذة الرحلة** — قبل قبول الكبتن أو بعد انتهائها (§٦٦-أ/١)."""

    code = "call_window_closed"
    message = "المكالمةُ متاحةٌ من قبول الكبتن حتى انتهاء الرحلة."


class CallBusy(Conflict):
    code = "call_busy"
    message = "مكالمةٌ جاريةٌ على هذه الرحلة الآن."


class CallStartRaced(Conflict):
    """**بدءان معاً تجاوزا قفلَ الرحلة فأمسكهما الفهرسُ الفريد** — رمزٌ غيرُ `call_busy` عمداً: قفلُ الرحلة يجعل الثاني يجد الأوّلَ
    فيُردّ `call_busy`، **وهذا الرمزُ لا يظهر إلا إن سقط القفل** — فاختبارُ التزامن يميّز «القفلُ عمل» من «الفهرسُ ستر غيابَه»."""

    code = "call_start_raced"
    message = "بدأت مكالمةٌ على هذه الرحلة في اللحظة نفسِها."


class CallNotRinging(Conflict):
    code = "call_not_ringing"
    message = "لم تعد هذه المكالمةُ ترنّ."


class CallNotLive(Conflict):
    code = "call_not_active"
    message = "انتهت هذه المكالمة."


class CallRecordingNoticeRequired(Conflict):
    """**التنبيهُ يسبق دائماً** (§٦٦-ج/١٦، §٦٦-د/٣) — والخادمُ هو من يرفض، فلا يُتجاوز بتطبيقٍ قديمٍ أو بنداءٍ مباشر."""

    code = "call_recording_notice_required"
    message = "هذه المكالمةُ مسجَّلة — يجب الإقرارُ بالتنبيه قبل المتابعة."


class CallSignalRefused(Conflict):
    code = "call_signal_refused"
    message = "لا تُقبل هذه الإشارةُ في حال المكالمة الآن."


class CallSignalTooLarge(InvalidInput):
    code = "call_signal_too_large"
    message = "الإشارةُ أكبرُ من المسموح."


class CallRecordingRefused(Conflict):
    code = "call_recording_refused"
    message = "لا يُرفع تسجيلٌ لهذه المكالمة."


# ═════════════════════════ المفتاحُ والمُرحِّل


async def calls_enabled(session: AsyncSession, country: CountryCode) -> bool:
    return await settings_service.is_feature_enabled(session, country, FeatureKey.RIDE_CALLS_ENABLED)


def ice_servers(user_id: uuid.UUID, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """**بياناتُ دخولٍ مؤقّتةٌ لمُرحِّلنا** (TURN REST: `use-auth-secret`) — أو قائمةٌ فارغةٌ بلا سرٍّ أو عناوين.

    **والمعرّفُ في الاسم معرّفُ الحساب لا رقمُه**: coturn يسجّل الاسمَ في سجلّه، **ورقمُ هاتفٍ هناك يكشف ما تمنعه المكالمةُ نفسُها**.
    """
    secret = settings.turn_shared_secret
    urls = [url.strip() for url in settings.turn_urls.split(",") if url.strip()]
    if not secret or not urls:
        return []
    expiry = int((now or _now()).timestamp()) + settings.turn_credential_ttl_seconds
    username = f"{expiry}:{user_id}"
    digest = hmac.new(secret.encode(), username.encode(), hashlib.sha1).digest()
    return [{"urls": urls, "username": username, "credential": base64.b64encode(digest).decode()}]


# ═════════════════════════ القراءة والأقفال


def _stale(call: RideCall, now: datetime) -> bool:
    """**ترنّ منذ أكثر من ثلاثين ثانية** — فائتةٌ وإن لم يكتبها أحدٌ بعد. **و`started_at` بدءُ الرنين**: في المسجَّلة لحظةُ إقرار
    المتصل (`acknowledge_notice`)، وقبله ثلاثون ثانيةً من الضغط على «اتصال» يقرأ فيها التنبيه."""
    return call.status is RideCallStatus.RINGING and call.started_at <= now - timedelta(seconds=RING_TIMEOUT_SECONDS)


def _rang(call: RideCall) -> bool:
    """**أرنّت عند المتصَل به؟** — المسجَّلةُ لا ترنّ قبل إقرار المتصل بالتنبيه (`acknowledge_notice`)، **فما انتهى قبله لم يَفُت
    أحداً**: لا يُكتب «لم يُجب» ولا يُرسل «مكالمةٌ فائتة» عن مكالمةٍ لم يعلم بها الطرفُ الآخر."""
    return not call.recorded or call.caller_notice_at is not None


def _lapsed(call: RideCall) -> RideCallEndReason:
    """**سببُ رنينٍ فاتت ثلاثونُه** — `no_answer` لما رنّ، و`cancelled` لمسجَّلةٍ تركها متصلُها على التنبيه."""
    return RideCallEndReason.NO_ANSWER if _rang(call) else RideCallEndReason.CANCELLED


def _finish(call: RideCall, reason: RideCallEndReason, now: datetime) -> None:
    """**الانتهاءُ بسببه** — والمدّةُ من الردّ إلى الانتهاء لما رُدّ عليه وحدَه."""
    call.status = RideCallStatus.ENDED
    call.ended_at = now
    call.end_reason = reason
    if call.answered_at is not None:
        call.duration_seconds = max(0, int((now - call.answered_at).total_seconds()))


@dataclass(frozen=True, slots=True)
class CallParty:
    call: RideCall
    ride: Ride
    side: RatingRaterType
    other_user_id: uuid.UUID | None


async def _for_party(session: AsyncSession, call_id: uuid.UUID, user: User) -> CallParty:
    """**المكالمةُ لطرفَيها وحدهما — وغيرُهما ٤٠٤** (لا IDOR): وجودُ مكالمةٍ ليس معلومةً يستحقّها غيرُهما."""
    call = await session.get(RideCall, call_id)
    if call is None or user.id not in (call.caller_id, call.callee_id):
        raise NotFound("المكالمة غير موجودة")
    ride = await rides_service.get_ride(session, call.ride_id)
    side = call.caller_role if user.id == call.caller_id else _other(call.caller_role)
    other = call.callee_id if user.id == call.caller_id else call.caller_id
    return CallParty(call=call, ride=ride, side=side, other_user_id=other)


def _other(side: RatingRaterType) -> RatingRaterType:
    return RatingRaterType.DRIVER if side is RatingRaterType.RIDER else RatingRaterType.RIDER


async def _lock_call(session: AsyncSession, call_id: uuid.UUID, *, share: bool = False) -> RideCall:
    """**صفُّ المكالمة مقفولاً قبل فحص حاله** (`CLAUDE.md`) — و`share` للإشارة وحدَها: لا تغيّر حالاً، فتتوازى ولا تسابق انتهاءً."""
    call = await session.scalar(
        select(RideCall)
        .where(RideCall.id == call_id)
        .with_for_update(read=share)
        .execution_options(populate_existing=True)
    )
    if call is None:  # pragma: no cover - لا تُحذف مكالمةٌ حيّة
        raise NotFound("المكالمة غير موجودة")
    return call


async def read(session: AsyncSession, *, call_id: uuid.UUID, user: User) -> tuple[CallParty, bool]:
    """**حالُ المكالمة لطرفها — والفائتةُ تُكتب فائتةً هنا** (الحكمُ الكسول): يعيد `True` حين كتبها، فيُبلَّغ بعد الالتزام."""
    found = await _for_party(session, call_id, user)
    now = _now()
    if not _stale(found.call, now):
        return found, False
    call = await _lock_call(session, call_id)
    if not _stale(call, now):  # pragma: no cover - سبقه غيرُه إليها
        return found, False
    _finish(call, _lapsed(call), now)
    await session.flush()
    return CallParty(call=call, ride=found.ride, side=found.side, other_user_id=found.other_user_id), True


async def current_for_ride(session: AsyncSession, ride_id: uuid.UUID) -> RideCall | None:
    """المكالمةُ الحيّةُ على الرحلة إن وُجدت — **والفائتةُ ليست حيّةً** وإن لم تُكتب بعد."""
    call = await session.scalar(
        select(RideCall).where(RideCall.ride_id == ride_id, RideCall.status.in_(LIVE_STATUSES))
    )
    if call is None or _stale(call, _now()):
        return None
    return call


# ═════════════════════════ البدء والردّ والرفض والإنهاء


@dataclass(slots=True)
class Started:
    call: RideCall
    party: trip_chat.Party
    missed: list[RideCall]
    #: **جاريةٌ أُغلقت لأن أحدَ طرفيها يتصل من جديد** (`failed`) — تُبلَّغ بعد الالتزام كأيِّ انتهاء
    dropped: list[RideCall]


async def start(session: AsyncSession, redis: Redis, *, ride_id: uuid.UUID, user: User) -> Started:
    """**اتصلْ** — الرحلةُ مقفولةٌ أوّلاً، ثمّ النافذةُ والمفتاحُ والطرف، **ولا مكالمتان حيّتان على رحلة**. الـcommit للراوتر.

    **والتسجيلُ يُجمَّد هنا** من إعداد السوق: مكالمةٌ أُعلنت مسجَّلةً تبقى كذلك ولو أُطفئ بعدها، والعكس.

    **وما يجده حيّاً على الرحلة**:

    - **رنينٌ فاتت ثلاثونُه** ⇒ `no_answer` ويمضي.
    - **رنينٌ لم تفُت ثلاثونُه** ⇒ `call_busy`: الطرفُ الآخر يتّصل الآن.
    - **جاريةٌ** ⇒ تُغلق `failed` ويمضي (قِيس ٢٠٢٦-١٠-٠٨). **ولا شيءَ غيرُه يكتب `failed`**: تطبيقٌ سقط أو شبكةٌ انقطعت تتركها
      «جاريةً» بلا من ينهيها، **فكانت كلُّ مكالمةٍ بعدها تُردّ `call_busy` حتى تنتهي الرحلة**. **ومن يتّصل طرفٌ فيها** (الملكيةُ
      مفحوصةٌ أعلاه) **وهو بالتعريف ليس فيها الآن** — فاتصالُه هو الشاهدُ أنها سقطت. **ومدّتُها حتى هذه اللحظة** لا حتى السقوط:
      لا يعرف الخادمُ متى انقطع الصوت، فتُقرأ «حدٌّ أعلى».
    """
    ride = await rides_service.get_ride_for_party(session, ride_id, user)
    party = trip_chat.party_of(ride, user)
    if not await calls_enabled(session, ride.country_code):
        raise RideCallsDisabled()
    if ride.status not in trip_chat.CHAT_WINDOW or party.other_user_id is None:
        raise CallWindowClosed()

    limit = await rate_limit.hit(
        redis, f"ride-call:{ride.id}:{user.id}", limit=START_LIMIT, window_seconds=START_WINDOW_SECONDS
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    if await trip_chat.lock_ride(session, ride.id) not in trip_chat.CHAT_WINDOW:
        raise CallWindowClosed()

    now = _now()
    live = (
        await session.scalars(
            select(RideCall)
            .where(RideCall.ride_id == ride.id, RideCall.status.in_(LIVE_STATUSES))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).all()
    missed: list[RideCall] = []
    dropped: list[RideCall] = []
    for call in live:
        if call.status is RideCallStatus.ACTIVE:
            _finish(call, RideCallEndReason.FAILED, now)
            dropped.append(call)
        elif _stale(call, now):
            _finish(call, _lapsed(call), now)
            missed.append(call)
        else:
            raise CallBusy()
    if missed or dropped:
        await session.flush()

    recorded = (await trip_chat.settings_for(session, ride.country_code)).call_recording_enabled
    call = RideCall(
        ride_id=ride.id,
        caller_id=user.id,
        callee_id=party.other_user_id,
        caller_role=party.side,
        status=RideCallStatus.RINGING,
        started_at=now,
        recorded=recorded,
    )
    session.add(call)
    try:
        await session.flush()
    except IntegrityError as exc:  # pragma: no cover - القفلُ يسبقه؛ والفهرسُ الجزئيُّ خلفه
        # **رمزٌ غيرُ `call_busy`** — انظر `CallStartRaced`: لو ردّ هذا الفرعُ `call_busy` لبقي اختبارُ التزامن أخضرَ بلا قفل
        raise CallStartRaced() from exc
    return Started(call=call, party=party, missed=missed, dropped=dropped)


async def answer(session: AsyncSession, *, call_id: uuid.UUID, user: User, notice_ack: bool) -> CallParty:
    """**ردّ** — المتصَلُ به وحدَه، والرحلةُ مقفولةٌ قبل المكالمة. **ولا تصير مكالمةٌ جاريةً بعد خروج الرحلة من نافذتها.**

    **وفي مكالمةٍ مسجَّلة لا ردَّ بلا إقرار** (`recording_notice_ack`) — ويُكتب وقتُه.
    """
    found = await _for_party(session, call_id, user)
    if user.id != found.call.callee_id:
        raise CallNotRinging()
    ride_status = await trip_chat.lock_ride(session, found.call.ride_id)
    call = await _lock_call(session, call_id)
    now = _now()
    if ride_status not in trip_chat.CHAT_WINDOW:
        raise CallWindowClosed()
    if call.status is not RideCallStatus.RINGING or _stale(call, now):
        raise CallNotRinging()
    if call.recorded and not notice_ack:
        raise CallRecordingNoticeRequired()
    call.status = RideCallStatus.ACTIVE
    call.answered_at = now
    if call.recorded:
        call.callee_notice_at = now
    await session.flush()
    return CallParty(call=call, ride=found.ride, side=found.side, other_user_id=found.other_user_id)


async def hang_up(
    session: AsyncSession, *, call_id: uuid.UUID, user: User, decline: bool
) -> tuple[CallParty, bool]:
    """**ارفضْ أو أنهِ** — بسببٍ يقول ما وقع، **ومنتهيةٌ تبقى كما هي** (الضغطةُ الثانية لا تكتب شيئاً).

    رنينٌ يرفضه المتصَلُ به ⇒ `declined` · رنينٌ يقطعه المتصلُ ⇒ `cancelled` · رنينٌ فاتت ثلاثونُه ⇒ `no_answer` · جاريةٌ ⇒
    `completed` بمدّتها. **و«ارفض» للمتصَل به وعلى رنينٍ وحدَه**: مكالمةٌ رُدّ عليها تُنهى ولا تُرفض. **والقفلُ على صفّ المكالمة
    وحدَه** — الإنهاءُ مسموحٌ في كلِّ حال، فلا يحتاج الرحلة. **والثاني في العائد «أكتب شيئاً؟»** — فلا يُعاد إبلاغُ انتهاءٍ وقع.
    """
    found = await _for_party(session, call_id, user)
    if decline and user.id != found.call.callee_id:
        raise CallNotRinging()
    call = await _lock_call(session, call_id)
    now = _now()
    done = CallParty(call=call, ride=found.ride, side=found.side, other_user_id=found.other_user_id)
    if call.status is RideCallStatus.ENDED:
        return done, False
    if decline and call.status is not RideCallStatus.RINGING:
        raise CallNotRinging()
    if call.status is RideCallStatus.ACTIVE:
        reason = RideCallEndReason.COMPLETED
    elif _stale(call, now):
        reason = _lapsed(call)
    elif user.id == call.callee_id:
        reason = RideCallEndReason.DECLINED
    else:
        reason = RideCallEndReason.CANCELLED
    _finish(call, reason, now)
    await session.flush()
    return done, True


async def acknowledge_notice(
    session: AsyncSession, *, call_id: uuid.UUID, user: User
) -> tuple[CallParty, bool]:
    """**المتصلُ يُقِرّ بتنبيه التسجيل** — وبغيره لا يُمرَّر عرضُه (`signal`) **ولا ترنّ عند الطرف الآخر**. ولمكالمةٍ غيرِ مسجَّلةٍ لا
    شيءَ يُكتب.

    **والثاني في العائد «أترنّ الآن؟»** — الإقرارُ الأوّلُ على مسجَّلةٍ ترنّ، **فيبثّ الراوترُ الرنينَ بعده لا مع البدء** (قِيس
    ٢٠٢٦-١٠-٠٨): كان يُبثّ مع `POST /rides/{id}/calls`، **فيرنّ هاتفُ الطرف الآخر والمتصلُ بعدُ أمام «متابعة / إلغاء»**، و«إلغاء»
    يتركه بـ«مكالمةٌ فائتة» عن مكالمةٍ لم تُجرَ. **و`started_at` يصير لحظةَ الإقرار**: الرنينُ يبدأ منها، فثلاثونُه (`_stale`
    والكنس) تُحسب منها لا من الضغط على «اتصال» — **وتلك باقيةٌ في `created_at`**. **ومسجَّلةٌ فاتت ثلاثونُها على التنبيه لا تُقَرّ**
    (`call_not_active`): لم ترنّ، ويكتبها الكنسُ `cancelled` بلا إشعار (`_lapsed`).
    """
    found = await _for_party(session, call_id, user)
    call = await _lock_call(session, call_id)
    now = _now()
    if call.status not in LIVE_STATUSES or _stale(call, now):
        raise CallNotLive()
    rings = False
    if call.recorded and user.id == call.caller_id and call.caller_notice_at is None:
        call.caller_notice_at = now
        if call.status is RideCallStatus.RINGING:
            call.started_at = now
            rings = True
        await session.flush()
    return CallParty(call=call, ride=found.ride, side=found.side, other_user_id=found.other_user_id), rings


async def signal(
    session: AsyncSession, redis: Redis, *, call_id: uuid.UUID, user: User, kind: str, payload: dict[str, Any]
) -> CallParty:
    """**إشارةٌ من طرفٍ إلى الآخر** — والخادمُ لا يقرؤها، **ويحرس متى تُمرَّر**:

    - في مكالمةٍ حيّةٍ وحدَها (`ringing`/`active`) — **فلا إشارةَ بعد انتهاء الرحلة**: إنهاؤها أغلق المكالمة.
    - `answer` من المتصَل به وبعد ردِّه وحدَه — جوابٌ قبل «ردّ» يُسمع صوتاً لم يُقبل.
    - **وفي مكالمةٍ مسجَّلة لا يُمرَّر عرضٌ ولا جوابٌ من طرفٍ لم يُقِرّ بالتنبيه** — «التنبيهُ يسبق دائماً» بحكم الخادم.

    **وقفلٌ مشترَكٌ لا حصريّ**: الإشاراتُ تتوازى، وإنهاءٌ يسابقها ينتظرها أو تنتظره فتجد المكالمةَ منتهية.
    """
    if len(json.dumps(payload, ensure_ascii=False).encode()) > MAX_SIGNAL_BYTES:
        raise CallSignalTooLarge()
    found = await _for_party(session, call_id, user)
    limit = await rate_limit.hit(
        redis, f"ride-call-signal:{call_id}:{user.id}", limit=SIGNAL_LIMIT, window_seconds=SIGNAL_WINDOW_SECONDS
    )
    if not limit.allowed:
        raise RateLimited(retry_after=limit.retry_after)

    call = await _lock_call(session, call_id, share=True)
    if call.status not in LIVE_STATUSES or _stale(call, _now()):
        raise CallNotLive()
    is_caller = user.id == call.caller_id
    if kind == "answer" and (is_caller or call.status is not RideCallStatus.ACTIVE):
        raise CallSignalRefused()
    if kind in ("offer", "answer") and call.recorded:
        acknowledged = call.caller_notice_at if is_caller else call.callee_notice_at
        if acknowledged is None:
            raise CallRecordingNoticeRequired()
    return CallParty(call=call, ride=found.ride, side=found.side, other_user_id=found.other_user_id)


# ═════════════════════════ انتهاءُ الرحلة والرنينُ الفائت


async def end_for_ride(session: AsyncSession, ride: Ride) -> list[RideCall]:
    """**الرحلةُ انتهت أو أُلغيت ⇒ تُغلق مكالمتُها الحيّة** (`ride_ended`) — يُنادى من `rides.complete_ride`/`cancel_ride`
    **وصفُّ الرحلة مقفول**، فصفوفُ المكالمة بعده مباشرةً — **ثمّ يقفل المُنادي ما بعدها** (الدفعة … المحفظة؛ انظر رأسَ الملف).
    **ولا يُسقط إنهاءَ الرحلة**: بلا مكالمةٍ لا يكتب شيئاً.

    **و`FOR UPDATE` هنا ليس زينة**: إنهاءٌ من أحد الطرفين يمسك صفَّ المكالمة (`hang_up` لا يقفل الرحلة) — **وبلا القفل يقرأ هذا
    «جارية» ويكتب `ride_ended` فوق `completed` بعد أن يلتزم الإنهاء**. وبه ينتظره ثمّ يجدها منتهيةً فلا يلمسها
    (`test_ride_calls_concurrency.py`).
    """
    calls = list(
        (
            await session.scalars(
                select(RideCall)
                .where(RideCall.ride_id == ride.id, RideCall.status.in_(LIVE_STATUSES))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    now = _now()
    for call in calls:
        _finish(call, RideCallEndReason.RIDE_ENDED, now)
    return calls


async def announce_ended_by_ride(session: AsyncSession, redis: Redis, ride: Ride) -> None:
    """**بعد التزام نهاية الرحلة**: ما أغلقه `end_for_ride` يُبلَّغ للطرفين — `call_ended` بسببه."""
    calls = (
        await session.scalars(
            select(RideCall).where(
                RideCall.ride_id == ride.id, RideCall.end_reason == RideCallEndReason.RIDE_ENDED
            )
        )
    ).all()
    for call in calls:
        await publish_ended(session, redis, call)


async def expire_ringing(session: AsyncSession, *, now: datetime | None = None, limit: int = 200) -> list[RideCall]:
    """**الرنينُ الفائت يُكتب `no_answer`** — دفعةٌ يأخذها هذا العاملُ وحدَه (`SKIP LOCKED`). الـcommit للمستدعي. **ومسجَّلةٌ تركها
    متصلُها على التنبيه تُكتب `cancelled`** (`_lapsed`): لم ترنّ عند أحد."""
    now = now or _now()
    calls = list(
        (
            await session.scalars(
                select(RideCall)
                .where(
                    RideCall.status == RideCallStatus.RINGING,
                    RideCall.started_at <= now - timedelta(seconds=RING_TIMEOUT_SECONDS),
                )
                .order_by(RideCall.started_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    for call in calls:
        _finish(call, _lapsed(call), now)
    return calls


# ═════════════════════════ البثّ — **معرّفاتٌ وجوانبُ لا أرقامٌ ولا أسماء**


def call_payload(call: RideCall) -> dict[str, Any]:
    return {
        "ride_id": str(call.ride_id),
        "call_id": str(call.id),
        "caller_role": call.caller_role.value,
        "status": call.status.value,
        "end_reason": call.end_reason.value if call.end_reason else None,
        "recording": call.recorded,
    }


def seconds_left(call: RideCall, now: datetime | None = None) -> int:
    """**ما بقي من ثلاثين الرنين** — بالثانية مقرَّبةً إلى أعلى، **ولا أقلَّ من واحدة**: ما يُرسل به رنينٌ لم يفُت بعد (`_stale`
    حكمُه)، وصفرٌ يُقرأ «بلا عمر» عند من يعدّ (`fcm._lifetime`)."""
    elapsed = ((now or _now()) - call.started_at).total_seconds()
    return max(1, math.ceil(RING_TIMEOUT_SECONDS - elapsed))


async def ringing_frame(session: AsyncSession, ride: Ride | None, user_id: uuid.UUID) -> dict[str, Any] | None:
    """**رنينٌ قائمٌ لمن يفتح مقبسَه الآن** (§٦٦-ج/١٧) — إطارُ `incoming_call` نفسُه **بما بقي من ثلاثينه**، أو `None`.

    **والعلّةُ**: الحدثُ يُبثّ مرّةً على القناة، **ومقبسٌ فُتح بعده لا يصله** — فمن فتح التطبيقَ من أيقونته وهاتفُه يرنّ (لا من
    الإشعار) **كان يرى شاشةً بلا مكالمة**، والخدمةُ الأصليّةُ تطوي رنينَها حين يظهر التطبيق. **وهو ما يفعله المقبسُ بالعرض المعلَّق**
    (`dispatch.pending_offer_frame`). **وللمتصَل به وحدَه، وإن رنّت عنده** (`_rang`): مسجَّلةٌ متصلُها بعدُ أمام التنبيه لم ترنّ.
    """
    if ride is None:
        return None
    call = await current_for_ride(session, ride.id)
    if call is None or call.status is not RideCallStatus.RINGING or call.callee_id != user_id or not _rang(call):
        return None
    from app.ws import events

    return {
        "type": events.TripCommsEvent.INCOMING_CALL.value,
        **call_payload(call),
        "ring_timeout_seconds": seconds_left(call),
    }


async def publish_incoming(session: AsyncSession, redis: Redis, call: RideCall) -> None:
    """**ترنّ عند المتصَل به**: الحدثُ على المقبس (التطبيقُ مفتوح)، وإشعارٌ لمن ليس أمامَ تطبيقه — **بياناتٌ وحدَها لما يرنّ
    بخدمته الأصليّة** (`notifications.publish_incoming_call`)."""
    from app.services import notifications
    from app.ws import events

    await events.publish_trip_comms(
        redis,
        [call.callee_id],
        event=events.TripCommsEvent.INCOMING_CALL,
        payload=call_payload(call) | {"ring_timeout_seconds": RING_TIMEOUT_SECONDS},
    )
    if call.callee_id is not None:
        await notifications.publish_incoming_call(
            session,
            redis,
            callee_id=call.callee_id,
            ride_id=call.ride_id,
            call_id=call.id,
            caller_role=call.caller_role.value,
            recording=call.recorded,
            seconds_left=seconds_left(call),
        )


async def _silence(session: AsyncSession, redis: Redis, call: RideCall) -> None:
    """**كفّت عن الرنين ⇒ يُسكَت رنينُها الأصليّ** عند المتصَل به (§٦٦-ج/١٧) — لما رنّ عنده وحدَه (`_rang`)."""
    from app.services import notifications

    if call.callee_id is None or not _rang(call):
        return
    await notifications.publish_call_ring_stopped(
        session,
        redis,
        callee_id=call.callee_id,
        ride_id=call.ride_id,
        call_id=call.id,
        ring_seconds=RING_TIMEOUT_SECONDS,
    )


async def publish_answered(session: AsyncSession, redis: Redis, call: RideCall) -> None:
    """**رُدّ عليها** — الطرفان على المقبس، **وأجهزةُ المتصَل به الأخرى تكفّ عن الرنين**: ردٌّ من هاتفٍ لا يُسكت لوحاً بجانبه."""
    from app.ws import events

    await events.publish_trip_comms(
        redis, [call.caller_id, call.callee_id], event=events.TripCommsEvent.CALL_ANSWERED, payload=call_payload(call)
    )
    await _silence(session, redis, call)


async def publish_ended(session: AsyncSession, redis: Redis, call: RideCall) -> None:
    """**انتهت** — الطرفان على المقبس، **وما انتهى قبل أن يُردّ عليه يُسكَت رنينُه** (رفضٌ، أو قطعه المتصل، أو فات، أو انتهت
    الرحلة). **وما رُدّ عليه سكت رنينُه عند الردّ** (`publish_answered`) — فلا أمرَ ثانٍ."""
    from app.ws import events

    await events.publish_trip_comms(
        redis, [call.caller_id, call.callee_id], event=events.TripCommsEvent.CALL_ENDED, payload=call_payload(call)
    )
    if call.answered_at is None:
        await _silence(session, redis, call)


async def publish_missed(session: AsyncSession, redis: Redis, call: RideCall) -> None:
    """**فاتت**: الطرفان على المقبس، **والمتصَلُ به في إشعارٍ عاديٍّ يبقى في صندوقه** (§٦٦-د/٤) — **إن رنّت عنده** (`_rang`):
    مسجَّلةٌ تركها متصلُها على التنبيه لم يعلم بها، فلا «فائتةَ» تُقال له."""
    from app.services import notifications

    await publish_ended(session, redis, call)
    if call.callee_id is not None and _rang(call):
        await notifications.publish_missed_call(
            session,
            redis,
            callee_id=call.callee_id,
            ride_id=call.ride_id,
            call_id=call.id,
            caller_role=call.caller_role.value,
        )


async def relay(redis: Redis, found: CallParty, *, kind: str, payload: dict[str, Any]) -> None:
    """**يمرّر الإشارةَ إلى الطرف الآخر وحدَه** — والمرسِلُ لا تصله إشارتُه."""
    from app.ws import events

    await events.publish_trip_comms(
        redis,
        [found.other_user_id],
        event=events.TripCommsEvent.CALL_SIGNAL,
        payload={
            "ride_id": str(found.call.ride_id),
            "call_id": str(found.call.id),
            "from_role": found.side.value,
            "kind": kind,
            "payload": payload,
        },
    )


# ═════════════════════════ التسجيل


async def attach_recording(
    session: AsyncSession, *, call_id: uuid.UUID, user: User, upload: storage.AsyncReader
) -> CallParty:
    """**يُرفع التسجيلُ بعد المكالمة من جهاز المتصل** — لمكالمةٍ أُعلنت مسجَّلةً ورُدّ عليها وانتهت، ومرّةً واحدة.

    **والملفُّ يُكتب قبل القفل لا تحته** (سابقةُ `documents.upload`): طولُ الرفع يقرّره العميل، فلا يُمسك صفٌّ طوالَه. **ثمّ يُعاد
    الفحصُ تحت القفل**، وما لم يُقبل يُمحى ملفُّه. **وتاريخُ الحذف يُجمَّد لحظةَ الرفع** من مدّة السوق.
    """
    found = await _for_party(session, call_id, user)
    _require_recordable(found.call, user)
    stored = await storage.save(
        upload,
        folder=str(found.call.id),
        sniffer=storage.sniff_audio,
        max_bytes=settings.call_recording_max_bytes,
    )
    try:
        call = await _lock_call(session, call_id)
        _require_recordable(call, user)
        days = (await trip_chat.settings_for(session, found.ride.country_code)).call_recording_retention_days
        call.recording_path = stored.relative_path
        call.recording_expires_at = _now() + timedelta(days=days)
        await session.flush()
    except BaseException:
        await storage.delete(stored.relative_path)
        raise
    return CallParty(call=call, ride=found.ride, side=found.side, other_user_id=found.other_user_id)


def _require_recordable(call: RideCall, user: User) -> None:
    """**ما يُقبل تسجيلُه**: مكالمةٌ أُعلنت مسجَّلة، من متصلها، انتهت بعد ردّ، ولم يُرفع لها شيء — **وأقرّ طرفاها كلاهما بالتنبيه**.

    **والإقراران شرطٌ هنا لا في الإشارة وحدَها** (قِيس ٢٠٢٦-١٠-٠٨): الإشارةُ تحرس متى يُمرَّر العرض، **والرفعُ بابٌ مستقلٌّ يُنادى
    مباشرةً** — فصوتُ من لم يُقرّ لا يُحفظ ولو وصل الملفّ.
    """
    if not (
        call.recorded
        and user.id == call.caller_id
        and call.status is RideCallStatus.ENDED
        and call.answered_at is not None
        and call.caller_notice_at is not None
        and call.callee_notice_at is not None
        and call.recording_path is None
    ):
        raise CallRecordingRefused()


def listenable(call: RideCall, now: datetime | None = None) -> bool:
    """**تسجيلٌ يُسمع**: ملفُّه قائمٌ وموعدُ حذفه لم يحلّ. **وحكمٌ واحدٌ للاستماع ولعلامته في سجلّ اللوحة** (`has_recording`):
    «فيه تسجيل» على صفٍّ يُردّ استماعُه ٤٠٤ زرٌّ بلا باب."""
    return (
        call.recording_path is not None
        and call.recording_expires_at is not None
        and call.recording_expires_at > (now or _now())
    )


async def recording_for_listen(session: AsyncSession, *, call_id: uuid.UUID, actor: User) -> RideCall:
    """**الاستماعُ — صلاحيةٌ مستقلّة، وكلُّ استماعٍ سطرٌ في التدقيق** (§٦٦-ج/١٦). الـcommit للراوتر قبل أن يُبثّ الملف.

    **وما حلّ موعدُ حذفه لا يُسمع** وإن لم يمرّ الكنسُ بعد (يمرّ مرّةً في اليوم): مدّةُ الاحتفاظ وعدٌ في السياسة، **والكنسُ أداتُه لا
    حدُّه** — فالحدُّ يُفحص هنا. وتسجيلٌ بلا تاريخِ حذفٍ لا يُسمع أيضاً: لا يُعرف أنه في مدّته.
    """
    call = await session.get(RideCall, call_id)
    if call is None or not listenable(call):
        raise NotFound("لا تسجيلَ لهذه المكالمة")
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.READ,
        entity_type="call_recording",
        entity_id=call.id,
        details={"call_id": str(call.id), "ride_id": str(call.ride_id)},
    )
    return call


async def erase_recording(session: AsyncSession, *, call_id: uuid.UUID, actor: User | None, reason: str) -> str:
    """**حذفُ تسجيلٍ قبل موعده** (SPEC §٧١-ب/٧) — بصلاحية الاستماع نفسِها، **وبسببٍ مكتوبٍ وسطرٍ في التدقيق**. يعيد مسارَ الملفّ
    ليُمحى **بعد الالتزام** كالكنس (`purge_expired`). **وسطرُ المكالمة يبقى** (من اتصل بمن ومتى) حتى يحلّ موعدُه كسائر سجلّ الرحلة.

    **ويُقفل صفُّ المكالمة قبل أن يُفحص** (قاعدةُ كلِّ تغيير حال): حذفان معاً لا يكتبان سطرين لملفٍّ واحد، وحذفٌ مع رفعٍ متأخّرٍ لا
    يترك ملفّاً بلا صفّ. **ولا قفلَ بعده** — كسائر أبواب المكالمة. و`actor=None` لسكربتٍ بأمر المالك، وسببُه في القيد.
    """
    call = (
        await session.scalars(
            select(RideCall)
            .where(RideCall.id == call_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).first()
    if call is None or call.recording_path is None:
        raise NotFound("لا تسجيلَ لهذه المكالمة")
    path = call.recording_path
    expired_at = call.recording_expires_at
    call.recording_path = None
    call.recording_expires_at = None
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.DELETE,
        entity_type="call_recording",
        entity_id=call.id,
        details={
            "call_id": str(call.id),
            "ride_id": str(call.ride_id),
            "reason": reason,
            "was_due": None if expired_at is None else expired_at.isoformat(),
        },
    )
    await session.flush()
    return path


async def calls_of_ride(session: AsyncSession, ride_id: uuid.UUID) -> tuple[list[RideCall], dict[uuid.UUID, str]]:
    """**سجلُّ مكالمات رحلةٍ للّوحة** — من اتصل بمن ومتى وكم وكيف انتهت وهل سُجّلت. **بياناتٌ وصفيّةٌ وحدَها، ولا صوت.**"""
    ride = await rides_service.get_ride(session, ride_id)
    calls = list(
        (await session.scalars(select(RideCall).where(RideCall.ride_id == ride.id).order_by(RideCall.started_at))).all()
    )
    ids = {value for call in calls for value in (call.caller_id, call.callee_id) if value is not None}
    names: dict[uuid.UUID, str] = {}
    if ids:
        names = {row.id: row.name for row in await session.execute(select(User.id, User.name).where(User.id.in_(ids)))}
    return calls, names


# ═════════════════════════ الحذفُ في موعده — ومع الحساب


async def purge_expired(
    session: AsyncSession, *, now: datetime | None = None, batch: int = trip_chat.PURGE_BATCH
) -> tuple[int, list[str]]:
    """**دفعةٌ من الحذف**: سجلُّ مكالماتِ رحلةٍ انتهت قبل مدّة سوقها، **والتسجيلاتُ التي حلّ موعدُها** — ملفّاتُها تُعاد لتُمحى
    **بعد الالتزام** (`storage.delete`: صفٌّ يشير إلى ملفٍّ ممحوٍّ عطل، وملفٌّ بلا صفٍّ نفاية).

    **ومكالمةٌ لها تسجيلٌ لم يحلّ موعدُه لا يُحذف سطرُها**: يبقى حتى يُحذف التسجيلُ ثمّ يلحقه — فلا يصير ملفٌّ بلا سطرٍ يدلّ عليه.
    """
    now = now or _now()
    expired_recordings = list(
        (
            await session.scalars(
                select(RideCall)
                .where(RideCall.recording_path.is_not(None), RideCall.recording_expires_at <= now)
                .limit(batch)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    files = [call.recording_path for call in expired_recordings if call.recording_path]
    for call in expired_recordings:
        call.recording_path = None
    await session.flush()

    days = func.coalesce(ServiceSetting.chat_retention_days, trip_chat.DEFAULT_RETENTION_DAYS)
    ended = func.coalesce(Ride.completed_at, Ride.cancelled_at)
    doomed = (
        await session.scalars(
            select(RideCall.id)
            .join(Ride, Ride.id == RideCall.ride_id)
            .outerjoin(ServiceSetting, ServiceSetting.country_code == Ride.country_code)
            .where(
                RideCall.status == RideCallStatus.ENDED,
                RideCall.recording_path.is_(None),
                ended.is_not(None),
                ended < literal(now) - func.make_interval(0, 0, 0, days),
            )
            .limit(batch)
        )
    ).all()
    if doomed:
        await session.execute(delete(RideCall).where(RideCall.id.in_(doomed)))
    return len(doomed), files


async def erase_recordings_for_account(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """**حذفُ الحساب يمحو صوتَ صاحبه** — كلُّ تسجيلٍ كان طرفاً فيه. **وسطرُ المكالمة يبقى** (من اتصل بمن ومتى — بلا اسمه بعد التجهيل)
    حتى يحلّ موعدُه كسائر سجلّ الرحلة. والملفّاتُ تُعاد لتُمحى بعد الالتزام."""
    calls = list(
        (
            await session.scalars(
                select(RideCall).where(
                    RideCall.recording_path.is_not(None),
                    (RideCall.caller_id == user_id) | (RideCall.callee_id == user_id),
                )
            )
        ).all()
    )
    files = [call.recording_path for call in calls if call.recording_path]
    for call in calls:
        call.recording_path = None
        call.recording_expires_at = None
    return files
