"""لوحةُ الإصدارات والتحديثُ الإلزاميّ — **البند ٨ (§39٫٨، §43)**.

**و`settings.write` لا `fleet.manage`**: هذا إعدادُ منصّةٍ يقرّر **من يفتح
التطبيق**، لا إدارةُ أسطول. **ورقمٌ خاطئٌ هنا يوقف كلَّ المستخدمين دفعةً
واحدة** — وهو أوسعُ أثراً من أيِّ صفٍّ في هذه اللوحة، بما فيها المال: خطأُ
مالٍ يمسّ حساباً، **وخطأُ حدٍّ يمسّ كلَّ من حمّل التطبيق**.

**وثلاثةُ حرّاسٍ قبل أن يُكتب حدٌّ يقفل أحداً**، وكلُّها في الخلفية:

1. **الرابطُ يُطرق** قبل الحفظ — §39٫٨ بحرفها: «ولا يُقفَل أحدٌ خارج التطبيق
   بلا رابط تحميلٍ صالحٍ يُفحص قبل الحفظ».
2. **والحدُّ لا يتجاوز الإصدارَ نفسَه** — قيدٌ في القاعدة كذلك، فلا يُقفل
   صاحبُ أحدث حزمةٍ بلا شيءٍ يحمّله.
3. **ويُستأذن مرّتين حين يرتفع الحدُّ** — والثانيةُ **في العقد**: رقمٌ يُعاد
   كتابتُه. **وورقةٌ في الشاشة وحدَها راحةٌ لا حماية.**
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.app_release import AppRelease
from app.models.enums import AuditAction, ClientApp
from app.schemas.app_release import AppReleaseIn, AppReleaseOut
from app.services import audit, releases as releases_service

router = APIRouter(prefix="/admin/releases", tags=["admin"])


async def _row(
    session: AsyncSession,
    release: AppRelease,
    *,
    current_id: uuid.UUID | None = None,
) -> AppReleaseOut:
    if current_id is None:
        live = await releases_service.current(session, release.app)
        current_id = None if live is None else live.id
    return AppReleaseOut(
        id=release.id,
        app=release.app,
        build=release.build,
        min_supported_build=release.min_supported_build,
        download_url=release.download_url,
        release_notes=release.release_notes,
        reminder_hours=release.reminder_hours,
        is_current=release.id == current_id,
        created_at=release.created_at,
        updated_at=release.updated_at,
    )


@router.get("", response_model=list[AppReleaseOut])
async def list_releases(
    _staff: StaffUser, session: DbSession, app: ClientApp | None = None
) -> list[AppReleaseOut]:
    """سجلُّ الإصدارات — **والحاكمُ منها مُعلَّمٌ في الخلفية**.

    **ولا تحسبه اللوحةُ بفرزها**: صفحةٌ مقصوصةٌ تجعل «الأخير» أعلى ما وصلها لا
    أعلى ما في الجدول — وهي قاعدةُ «التجميعُ في الخلفية» بعينها.
    """
    stmt = select(AppRelease).order_by(
        AppRelease.app, AppRelease.build.desc()
    )
    if app is not None:
        stmt = stmt.where(AppRelease.app == app)
    rows = (await session.scalars(stmt)).all()

    current_ids = set()
    for one in ClientApp if app is None else (app,):
        live = await releases_service.current(session, one)
        if live is not None:
            current_ids.add(live.id)

    return [
        AppReleaseOut(
            id=row.id,
            app=row.app,
            build=row.build,
            min_supported_build=row.min_supported_build,
            download_url=row.download_url,
            release_notes=row.release_notes,
            reminder_hours=row.reminder_hours,
            is_current=row.id in current_ids,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.post("", response_model=AppReleaseOut, status_code=status.HTTP_201_CREATED)
async def create_release(
    payload: AppReleaseIn, admin: SettingsWriter, session: DbSession
) -> AppReleaseOut:
    """يسجّل إصداراً — **بعد طرق رابطه، وبإذنين إن رفع الحدّ**."""
    release = await releases_service.create(
        session,
        app=payload.app,
        build=payload.build,
        min_supported_build=payload.min_supported_build,
        download_url=str(payload.download_url),
        release_notes=payload.release_notes,
        reminder_hours=payload.reminder_hours,
        confirmation=payload.confirm_min_supported_build,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="app_release",
        entity_id=release.id,
        details={
            "app": release.app.value,
            "build": release.build,
            "min_supported_build": release.min_supported_build,
        },
    )
    await session.commit()
    await session.refresh(release)
    return await _row(session, release)


@router.put("/{release_id}", response_model=AppReleaseOut)
async def update_release(
    release_id: uuid.UUID,
    payload: AppReleaseIn,
    admin: SettingsWriter,
    session: DbSession,
) -> AppReleaseOut:
    """يعدّل صفّاً — **ولا يمسّ رقمَ الإصدار ولا تطبيقَه**.

    **والقيمةُ قبل وبعد في التدقيق** (§40٫١): «غيّر الحدّ» لا تقول شيئاً بعد
    شهر، **و«من ٣٩٠ إلى ٤٠١» تقول كلَّ شيء**.
    """
    release = await releases_service.get(session, release_id)
    changes = await releases_service.update(
        session,
        release,
        min_supported_build=payload.min_supported_build,
        download_url=str(payload.download_url),
        release_notes=payload.release_notes,
        reminder_hours=payload.reminder_hours,
        confirmation=payload.confirm_min_supported_build,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="app_release",
        entity_id=release.id,
        details={"app": release.app.value, "build": release.build},
        changes=changes,
    )
    await session.commit()
    await session.refresh(release)
    return await _row(session, release)


@router.delete("/{release_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_release(
    release_id: uuid.UUID, admin: SettingsWriter, session: DbSession
) -> None:
    """يحذف صفّ إصدار — **ويُبقي أثرَه في التدقيق بقيمته قبل الحذف**."""
    release = await releases_service.get(session, release_id)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="app_release",
        entity_id=release.id,
        details={
            "app": release.app.value,
            "build": release.build,
            "min_supported_build": release.min_supported_build,
            "download_url": release.download_url,
        },
    )
    await releases_service.delete(session, release)
    await session.commit()
