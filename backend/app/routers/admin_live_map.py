"""الخريطة الحيّة (SPEC القسم 13/1).

**`AdminUser` لا `StaffUser`** — وهو الفرق الوحيد عن بقية شاشات القراءة في
اللوحة. «نظرة عامة» أرقامٌ مجمّعة يقرأها الدعم لأنه يعالج ما تشير إليه؛ وهذه
أسماءُ أشخاصٍ وأرقامُ هواتفهم ومواقعُهم الآنية، ومعالجةُ نزاعٍ لا تحتاج شيئاً
منها. ولو فُتحت للدعم لصارت أوسعَ صلاحيةٍ في النظام يملكها أقلُّ دورٍ فيه.

وقيدُ التدقيق يُكتب هنا **قبل** القراءة لا بعدها، ومخنوقاً بنافذةٍ في
`live_map.record_access` كي لا تبتلع جلسةُ مراقبةٍ واحدة سجلَّ القرارات.

**وأبوابُ هذا الملفّ وحدَها بقيت على `AdminUser` بعد مصفوفة الصلاحيات**
(البند ٥، §39٫٥) — **بقرارٍ مكتوبٍ لا بسهو**: القسم 13/1 يجعل الخريطةَ
**لـ`admin` حصراً**. **وإدخالُها في المصفوفة يجعلها قابلةً للمنح** لمن ليس
مشرفاً — وذاك ما يمنعه القسمُ نفسُه. **فالحصرُ هنا صفةُ الدور لا صلاحيةٌ
تُمنح.**

**وصارا بابين منذ البند ٦** (2026-09-03، §39٫٦): الخريطةُ للدولة كلِّها،
و`GET /admin/live/drivers/{driver_id}/ride` لكبتنٍ بعينه في ملفِّه. **وكلاهما
يقرن هويةً بموقع، فبيتُهما واحدٌ وقاعدتُهما واحدة** — ومن أضاف ثالثاً يضيفه
هنا، لا في موجّهِ الشاشة التي تعرضه. **ومن جعل أحدَهما لـ`support` فتح
الآخرَ**: تتبُّعُ كبتنٍ واحدٍ بمعرِّفه، مكرَّراً، هو الخريطةُ نفسُها.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.deps import AdminUser, DbSession, RedisDep
from app.core.exceptions import NotFound
from app.models.driver import Driver
from app.models.enums import CountryCode
from app.models.ride import Ride
from app.schemas.live_map import (
    DriverLivePositionOut,
    DriverLiveRideOut,
    LiveDriverOut,
    LiveMapOut,
    PendingRideOut,
)
from app.schemas.admin_ride import RidePointOut
from app.services import live_map as live_map_service, ride_log

router = APIRouter(prefix="/admin/live", tags=["admin"])


@router.get("/map", response_model=LiveMapOut)
async def live_map(
    admin: AdminUser,
    session: DbSession,
    redis: RedisDep,
    country_code: CountryCode,
) -> LiveMapOut:
    """السائقون الحاضرون بهويّاتهم، والطلبات التي لم يقبلها أحد بعد."""
    await live_map_service.record_access(
        session, redis, admin=admin, country=country_code
    )
    drivers = await live_map_service.drivers_now(redis, session, country=country_code)
    pending = await live_map_service.pending_rides(session, country=country_code)
    return LiveMapOut(
        drivers=[LiveDriverOut.model_validate(row) for row in drivers],
        pending_rides=[PendingRideOut.model_validate(row) for row in pending],
    )


@router.get("/drivers/{driver_id}/ride", response_model=DriverLiveRideOut | None)
async def driver_live_ride(
    driver_id: uuid.UUID,
    admin: AdminUser,
    session: DbSession,
    redis: RedisDep,
) -> DriverLiveRideOut | None:
    """رحلةُ الكبتن الجارية ومسارُها وموضعُه — **البند ٦ (§39٫٦)**.

    **وهو البابُ الثاني في المنصة الذي يقرن هويةً بموقع**، فيحمل قيودَ الأول
    نفسَها: `AdminUser` لا `StaffUser`، وقيدُ تدقيقٍ مخنوقٌ بنافذة. **ولمَ
    ليس للدعم**: من ملك أن يتتبّع كبتناً واحداً بمعرِّفه ملك أن يتتبّعهم
    واحداً واحداً — فبابٌ أضيقُ في الشكل لا يكون أضيقَ في الأثر، **وحصرُ
    الخريطة على `admin` كان يُلتفّ عليه من هنا**.

    **ولا رحلةَ نشطة = `null`، فيصمت القسمُ** بدل خريطةٍ فارغة تُقرأ عطباً.

    **والمرجعُ `drivers.current_ride_id` لا استعلامٌ بالحالة**: هو نفسُه ما
    تقرؤه الخريطةُ الحيّة في `on_ride` وما يقرؤه التوزيعُ ليعرف من هو متفرّغ
    (`dispatch.eligible`) — **فمصدرٌ ثانٍ للسؤال نفسِه يفترق عنه أوّلَ ما
    يتغيّر أحدُهما**، ويرى المشرفُ في الملفِّ غيرَ ما ترى الخريطة. وحالُ
    الرحلة تُنشر كما هي ولا تُصفّى: لو تخالف العمودُ والحالةُ يوماً فالأولى
    أن يُرى ذلك لا أن يُخفى.

    **والقيدُ يُكتب حين يخرج موضعٌ فعلاً**: أن هذا الكبتن في رحلةٍ خبرٌ يقرؤه
    الدعمُ من سجلِّ الرحلات أصلاً، **والمسجَّلُ هو الاقتران** — فقيدٌ عن
    قراءةٍ لم تكشف موضعاً يصف أكثرَ ممّا جرى.
    """
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise NotFound("الكبتن غير موجود")
    if driver.current_ride_id is None:
        return None

    ride = await session.get(Ride, driver.current_ride_id)
    if ride is None:  # pragma: no cover - `SET NULL` يمنعه
        return None

    route, truncated = await ride_log.route_of(session, ride.id)
    position = await live_map_service.position_of(
        redis, driver_id=driver.id, country=ride.country_code
    )
    if position is not None:
        await live_map_service.record_driver_access(
            session, redis, admin=admin, driver_id=driver.id
        )

    return DriverLiveRideOut(
        ride_id=ride.id,
        status=ride.status,
        pickup_lat=ride.pickup_lat,
        pickup_lng=ride.pickup_lng,
        pickup_address=ride.pickup_address,
        dropoff_lat=ride.dropoff_lat,
        dropoff_lng=ride.dropoff_lng,
        dropoff_address=ride.dropoff_address,
        accepted_at=ride.accepted_at,
        started_at=ride.started_at,
        route=[
            RidePointOut(lat=point.lat, lng=point.lng, created_at=point.created_at)
            for point in route
        ],
        route_truncated=truncated,
        position=(
            None
            if position is None
            else DriverLivePositionOut.model_validate(position)
        ),
    )
