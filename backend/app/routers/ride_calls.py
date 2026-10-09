"""مكالمةُ الرحلة لطرفَيها (SPEC §٦٦-ج) — **البدءُ على الرحلة، والباقي على المكالمة نفسِها**.

`POST /rides/{id}/calls` يبدأ، و`/calls/{id}/…` يردّ ويرفض وينهي ويمرّر الإشارة. **والملكيةُ والنافذةُ والأقفالُ كلُّها في
`services/ride_calls.py`**؛ وهنا الالتزامُ ثمّ البثّ — **والبثُّ دائماً بعد الالتزام**: قبله قد تُعلن حالٌ تُلغى بعد لحظة.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile, status

from app.core.deps import CurrentUser, DbSession, RedisDep
from app.schemas.ride_call import (
    CallAnswerIn,
    CallAnswerOut,
    CallSignalIn,
    CallStartOut,
    IceServerOut,
    RideCallOut,
)
from app.services import ride_calls

router = APIRouter(prefix="", tags=["calls"])


def _ice(user_id: uuid.UUID) -> list[IceServerOut]:
    return [IceServerOut(**server) for server in ride_calls.ice_servers(user_id)]


@router.post("/rides/{ride_id}/calls", response_model=CallStartOut, status_code=status.HTTP_201_CREATED)
async def start_call(ride_id: uuid.UUID, user: CurrentUser, session: DbSession, redis: RedisDep) -> CallStartOut:
    """**اتصل بالطرف الآخر** — في النافذة وحدَها، **ومكالمةٌ حيّةٌ واحدةٌ لكلِّ رحلة** (`call_busy` على رنين؛ والجاريةُ تُغلق
    `failed` — من يتّصل ليس فيها). **ولا رقمَ في شيء**: ترنّ عند الطرف الآخر بجانب المتصل وحدَه. وبياناتُ المُرحِّل لك أنت، مؤقّتة."""
    started = await ride_calls.start(session, redis, ride_id=ride_id, user=user)
    await session.commit()
    for missed in started.missed:
        await ride_calls.publish_missed(session, redis, missed)
    # **الجاريةُ التي أغلقها الاتصالُ الجديد (`failed`) تُبلَّغ للطرفين** — فيُغلق الطرفُ الآخر ما بقي مفتوحاً عنده
    for dropped in started.dropped:
        await ride_calls.publish_ended(session, redis, dropped)
    # **والمسجَّلةُ لا ترنّ هنا** — ترنّ بعد إقرار المتصل بالتنبيه (`/recording-notice`): المتصلُ بعدُ أمام «متابعة / إلغاء»
    if not started.call.recorded:
        await ride_calls.publish_incoming(session, redis, started.call)
    return CallStartOut(
        call_id=started.call.id,
        ride_id=started.call.ride_id,
        ice_servers=_ice(user.id),
        recording=started.call.recorded,
        ring_timeout_seconds=ride_calls.RING_TIMEOUT_SECONDS,
    )


@router.get("/calls/{call_id}", response_model=RideCallOut)
async def get_call(call_id: uuid.UUID, user: CurrentUser, session: DbSession, redis: RedisDep) -> RideCallOut:
    """حالُ المكالمة لطرفَيها — **لتطبيقٍ فُتح من إشعار** فيعرف أترنّ أم فاتت. **ورنينٌ فاتت ثلاثونُه يُكتب فائتاً هنا.**"""
    found, missed = await ride_calls.read(session, call_id=call_id, user=user)
    if missed:
        await session.commit()
        await ride_calls.publish_missed(session, redis, found.call)
    return RideCallOut.of(found.call, user.id)


@router.post("/calls/{call_id}/answer", response_model=CallAnswerOut)
async def answer_call(
    call_id: uuid.UUID, payload: CallAnswerIn, user: CurrentUser, session: DbSession, redis: RedisDep
) -> CallAnswerOut:
    """**ردّ** — المتصَلُ به وحدَه، في النافذة وحدَها، **وفي مكالمةٍ مسجَّلةٍ بإقرارٍ بالتنبيه** (`call_recording_notice_required`)."""
    found = await ride_calls.answer(
        session, call_id=call_id, user=user, notice_ack=payload.recording_notice_ack
    )
    await session.commit()
    await ride_calls.publish_answered(session, redis, found.call)
    return CallAnswerOut(
        call_id=found.call.id,
        ride_id=found.call.ride_id,
        ice_servers=_ice(user.id),
        recording=found.call.recorded,
    )


@router.post("/calls/{call_id}/decline", response_model=RideCallOut)
async def decline_call(call_id: uuid.UUID, user: CurrentUser, session: DbSession, redis: RedisDep) -> RideCallOut:
    """**ارفض** — المتصَلُ به على رنينٍ وحدَه. والضغطةُ الثانيةُ على منتهيةٍ تعيدها كما هي ولا تُعيد الإبلاغ."""
    found, changed = await ride_calls.hang_up(session, call_id=call_id, user=user, decline=True)
    await session.commit()
    if changed:
        await ride_calls.publish_ended(session, redis, found.call)
    return RideCallOut.of(found.call, user.id)


@router.post("/calls/{call_id}/end", response_model=RideCallOut)
async def end_call(call_id: uuid.UUID, user: CurrentUser, session: DbSession, redis: RedisDep) -> RideCallOut:
    """**أنهِ** — أيُّ الطرفين وفي أيِّ حال؛ والسببُ يقول ما وقع (`completed` · `cancelled` · `declined` · `no_answer`)."""
    found, changed = await ride_calls.hang_up(session, call_id=call_id, user=user, decline=False)
    await session.commit()
    if changed:
        await ride_calls.publish_ended(session, redis, found.call)
    return RideCallOut.of(found.call, user.id)


@router.post("/calls/{call_id}/signal", status_code=status.HTTP_204_NO_CONTENT)
async def signal_call(
    call_id: uuid.UUID, payload: CallSignalIn, user: CurrentUser, session: DbSession, redis: RedisDep
) -> None:
    """**إشارةُ WebRTC إلى الطرف الآخر وحدَه** — في مكالمةٍ حيّةٍ وحدَها، **وفي المسجَّلة بعد الإقرار**. والخادمُ لا يقرؤها."""
    found = await ride_calls.signal(
        session, redis, call_id=call_id, user=user, kind=payload.kind, payload=payload.payload
    )
    # **القفلُ المشترَكُ يُحرَّر قبل البثّ** — إنهاءٌ ينتظره لا ينتظر شبكة
    await session.commit()
    await ride_calls.relay(redis, found, kind=payload.kind, payload=payload.payload)


@router.post("/calls/{call_id}/recording-notice", response_model=RideCallOut)
async def acknowledge_recording_notice(
    call_id: uuid.UUID, user: CurrentUser, session: DbSession, redis: RedisDep
) -> RideCallOut:
    """**المتصلُ أقرّ بأن المكالمةَ مسجَّلة** — وبغيره لا يُمرَّر عرضُه، **ولا ترنّ عند الطرف الآخر قبله**: الرنينُ يُبثّ هنا بعد
    الالتزام، مرّةً عند أوّل إقرار."""
    found, rings = await ride_calls.acknowledge_notice(session, call_id=call_id, user=user)
    await session.commit()
    if rings:
        await ride_calls.publish_incoming(session, redis, found.call)
    return RideCallOut.of(found.call, user.id)


@router.post("/calls/{call_id}/recording", response_model=RideCallOut)
async def upload_recording(
    call_id: uuid.UUID, user: CurrentUser, session: DbSession, file: UploadFile = File(...)
) -> RideCallOut:
    """**التسجيلُ من جهاز المتصل بعد المكالمة** — لمكالمةٍ أُعلنت مسجَّلة وحدَها، webm أو ogg، بسقف، ومرّةً واحدة."""
    found = await ride_calls.attach_recording(session, call_id=call_id, user=user, upload=file)
    await session.commit()
    return RideCallOut.of(found.call, user.id)
