"""مكالماتُ الرحلات في اللوحة (SPEC §٦٦-ج/١٦) — **السجلُّ بقراءة القوائم، والاستماعُ بصلاحيته المستقلّة**.

**سجلُّ المكالمة بياناتٌ وصفيّة** (من اتصل بمن ومتى وكم وكيف انتهت) — كسجلِّ الرحلة نفسِها، فيكفيه `read.only`. **والتسجيلُ صوتُ
إنسان**: صلاحيةٌ مستثناةٌ من افتراض المشرف (`call_recordings.listen`)، **وكلُّ استماعٍ سطرٌ في التدقيق** قبل أن يُبثّ الملف.
**والحذفُ قبل الموعد بالصلاحية نفسِها**: من يملك أن يسمع يملك أن يمحو ما سمع، بسببٍ مكتوب (§٧١-ب/٧).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core import storage
from app.core.deps import DbSession, ListReader, RecordingsListener
from app.schemas.ride_call import AdminCallOut, RecordingEraseIn
from app.services import ride_calls

router = APIRouter(prefix="/admin", tags=["admin"])

#: نوعُ المحتوى من الامتداد الذي كتبه الحفظُ نفسُه (`storage.sniff_audio`) — لا من ترويسةٍ أرسلها العميل
_MEDIA_TYPES = {".webm": "audio/webm", ".ogg": "audio/ogg"}


@router.get("/rides/{ride_id}/calls", response_model=list[AdminCallOut])
async def list_ride_calls(ride_id: uuid.UUID, _staff: ListReader, session: DbSession) -> list[AdminCallOut]:
    calls, names = await ride_calls.calls_of_ride(session, ride_id)
    return [
        AdminCallOut(
            id=call.id,
            caller_role=call.caller_role,
            caller_name=names.get(call.caller_id) if call.caller_id else None,
            callee_name=names.get(call.callee_id) if call.callee_id else None,
            status=call.status,
            started_at=call.started_at,
            answered_at=call.answered_at,
            ended_at=call.ended_at,
            duration_seconds=call.duration_seconds,
            end_reason=call.end_reason,
            recorded=call.recorded,
            # **الحكمُ نفسُه الذي يحرس الاستماع** — وتسجيلٌ حلّ موعدُه ولم يمرّ الكنسُ بعد لا يُعرض قابلاً للسماع
            has_recording=ride_calls.listenable(call),
            recording_expires_at=call.recording_expires_at,
        )
        for call in calls
    ]


@router.get("/calls/{call_id}/recording")
async def listen_to_recording(call_id: uuid.UUID, admin: RecordingsListener, session: DbSession) -> FileResponse:
    """**الاستماع** — والسطرُ في التدقيق يُلتزم **قبل** أن يُبثّ الملف: استماعٌ وقع بلا أثرٍ لا يقع."""
    call = await ride_calls.recording_for_listen(session, call_id=call_id, actor=admin)
    path = storage.resolve(call.recording_path or "")
    await session.commit()
    return FileResponse(path, media_type=_MEDIA_TYPES.get(path.suffix, "application/octet-stream"))


@router.post("/calls/{call_id}/recording/erase", status_code=204)
async def erase_recording(call_id: uuid.UUID, payload: RecordingEraseIn, admin: RecordingsListener, session: DbSession) -> None:
    """**حذفُ التسجيل قبل موعده** — السطرُ في التدقيق والصفُّ يُلتزمان **ثمّ** يُمحى الملفّ: صفٌّ يشير إلى ملفٍّ ممحوٍّ عطل."""
    path = await ride_calls.erase_recording(session, call_id=call_id, actor=admin, reason=payload.reason.strip())
    await session.commit()
    await storage.delete(path)
