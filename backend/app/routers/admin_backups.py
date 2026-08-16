"""النسخُ الاحتياطي في اللوحة — `admin` حصراً (الخطة §٦).

**ولا `StaffUser`**: هذا ملفٌ فيه **كلُّ أرقام المستخدمين ودفترُ المحافظ**،
و`support` لا يحتاجه لحلّ نزاع.

**وقيدُ تدقيقٍ لكلِّ فعل** — ومنه **تسجيلُ التنزيل** (`AuditAction.READ` على
`backup`)، وهي السابقةُ الثانيةُ في هذا المشروع لتسجيل قراءةٍ بعد `live_map`:
تُسجَّل القراءةُ حيث تكون هي نفسُها فعلاً يُسأل عنه.
"""

from __future__ import annotations

import secrets
import uuid
from pathlib import Path

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse

from app.core.deps import AdminUser, DbSession, RedisDep
from app.core.exceptions import InvalidInput, NotFound, PermissionDenied
from app.core.security import verify_password
from app.models.enums import AuditAction
from app.schemas.backup import (
    BackupDownloadIn,
    BackupDownloadOut,
    BackupRowOut,
    BackupSettingsIn,
    BackupSettingsOut,
    BackupStateOut,
)
from app.services import audit, backups

router = APIRouter(prefix="/admin/backups", tags=["admin"])

# **خمسُ دقائقَ ولمرةٍ واحدة** (قرارُ المالك ٥): رابطٌ يعيش ساعةً يعيش في تاريخ
# المتصفح وفي سجلّ الوكيل — والمفتاحُ يُحذف عند أوّل استعمال
TOKEN_TTL_SECONDS = 300
TOKEN_KEY = "backup:download:{token}"


def _row(path: Path) -> BackupRowOut:
    import json

    manifest = {}
    manifest_file = path / "manifest.json"
    if manifest_file.exists():
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except ValueError:  # pragma: no cover - بيانٌ تالف
            manifest = {}
    return BackupRowOut(
        name=path.name,
        taken_at=manifest.get("taken_at"),
        alembic_revision=manifest.get("alembic_revision"),
        encrypted=bool(manifest.get("encrypted")),
        size_bytes=sum(item.stat().st_size for item in path.rglob("*") if item.is_file()),
        # **تُقرأ من القرص لا من عمود** (الخطة §٥): السحبُ يقع عبر SSH بلا مرورٍ
        # بالتطبيق، فعمودٌ ينتظر نداءً لن يأتي يكذب دائماً
        pulled=backups.is_pulled(path),
    )


@router.get("", response_model=BackupStateOut)
async def state(admin: AdminUser, session: DbSession) -> BackupStateOut:
    setting = await backups.get_settings(session)
    await session.commit()
    alerts = await backups.alerts(session)
    return BackupStateOut(
        settings=BackupSettingsOut.model_validate(setting, from_attributes=True),
        backups=[_row(item) for item in backups.existing()],
        last_success_at=await backups.last_success(session),
        stale_hours=alerts.stale_hours,
        unpulled=alerts.unpulled,
        disk_percent=alerts.disk_percent,
        total_bytes=backups.total_bytes(),
    )


@router.post("/run", response_model=BackupRowOut, status_code=201)
async def run_now(admin: AdminUser, session: DbSession, redis: RedisDep) -> BackupRowOut:
    """«نسخةٌ احتياطية الآن» — **وقفلٌ يمنع نسختين معاً**.

    دمبان متزامنان يملآن القرصَ ويتنازعان I/O في أسوأ لحظة؛ والقفلُ نفسُه الذي
    تأخذه المهمّةُ الدورية، فالزرُّ والجدولةُ لا يتسابقان.
    """
    got = await redis.set(
        backups.LOCK_KEY, "1", nx=True, ex=backups.LOCK_TTL_SECONDS
    )
    if not got:
        raise backups.BackupAlreadyRunning()
    try:
        run = await backups.take(session, requested_by=admin.phone)
    finally:
        await redis.delete(backups.LOCK_KEY)

    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="backup",
        entity_id=run.id,
        details={"name": run.name, "status": run.status},
    )
    await session.commit()

    if run.status != "succeeded":
        # **الفشلُ يُقال لا يُبتلع**: صفُّه مكتوبٌ بنصِّ خطئه، والشاشةُ تعرضه
        raise InvalidInput(f"فشلت النسخة: {run.error or 'سببٌ غير معروف'}")
    return _row(backups.BACKUP_ROOT / run.name)


@router.put("/settings", response_model=BackupSettingsOut)
async def update_settings(
    payload: BackupSettingsIn, admin: AdminUser, session: DbSession
) -> BackupSettingsOut:
    setting = await backups.get_settings(session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(setting, field, value)
    await session.flush()
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="backup_settings",
        entity_id=setting.id,
        details={"fields": sorted(payload.model_dump(exclude_unset=True))},
    )
    await session.commit()
    return BackupSettingsOut.model_validate(setting, from_attributes=True)


@router.post("/{name}/download-token", response_model=BackupDownloadOut)
async def download_token(
    name: str,
    payload: BackupDownloadIn,
    admin: AdminUser,
    session: DbSession,
    redis: RedisDep,
) -> BackupDownloadOut:
    """يولّد رابطاً بعد **إعادة إدخال كلمة المرور** (الخطة §٦).

    وملفٌ واحدٌ فيه كلُّ شيء يستحقّ باباً ثانياً: جلسةٌ مفتوحةٌ على مكتبٍ لا
    يجلس إليه أحدٌ لا تكفي لتسليمه.
    """
    if not verify_password(payload.password, admin.password_hash):
        raise PermissionDenied("كلمة المرور غير صحيحة")

    path = backups.BACKUP_ROOT / name
    if not path.is_dir() or name.startswith("."):
        raise NotFound("لا توجد نسخة بهذا الاسم")
    target = path / payload.file
    # **ولا يخرج المسارُ من مجلد النسخة**: اسمُ ملفٍ يحمل `..` يقرأ ما شاء من
    # القرص — قاعدةُ `core/storage.resolve` نفسُها
    if not target.is_file() or target.parent.resolve() != path.resolve():
        raise NotFound("لا يوجد ملفٌّ بهذا الاسم في النسخة")

    # **والمفتاحُ يحمل هويةَ من طلبه**: الرابطُ يُفتح بتنقّلِ متصفّحٍ لا يحمل
    # ترويسةَ المصادقة، فلو حُرس المنفذُ بـ`AdminUser` لما فُتح أصلاً. والرمزُ
    # **هو** الصلاحية (خمسُ دقائقَ، مرةٌ واحدة، ويُحذف عند أوّل استعمال) —
    # وحملُه للهوية هو ما يُبقي قيدَ التدقيق يقول **من** نزّل، لا «أحدٌ ما»
    token = secrets.token_urlsafe(32)
    await redis.set(
        TOKEN_KEY.format(token=token),
        f"{admin.id}|{name}/{payload.file}",
        ex=TOKEN_TTL_SECONDS,
    )
    return BackupDownloadOut(token=token, expires_in=TOKEN_TTL_SECONDS)


@router.get("/download/{token}")
async def download(token: str, session: DbSession, redis: RedisDep) -> Response:
    """**يُحذف المفتاحُ ويُسجَّل التنزيلُ قبل بدء البثّ** لا بعده.

    من قطع الاتصالَ في منتصف ملفٍ ضخمٍ يكون قد أخذ ما أخذ — فتسجيلٌ بعد الاكتمال
    يسجّل نصفَ ما وقع.
    """
    key = TOKEN_KEY.format(token=token)
    value = await redis.get(key)
    if not value:
        raise NotFound("انتهت صلاحية الرابط أو استُعمل")
    await redis.delete(key)

    actor_id, _, rest = value.partition("|")
    name, _, filename = rest.partition("/")
    target = backups.BACKUP_ROOT / name / filename
    if not target.is_file():  # pragma: no cover - حُذفت بين الأمرين
        raise NotFound("لم يعد الملفُّ موجوداً")

    from app.models.user import User

    actor = await session.get(User, uuid.UUID(actor_id))
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.READ,
        entity_type="backup",
        entity_id=None,
        details={"name": name, "file": filename},
    )
    await session.commit()

    return FileResponse(
        target,
        media_type="application/octet-stream",
        filename=f"{name}-{filename}",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
