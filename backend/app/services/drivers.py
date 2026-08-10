"""حضور الكبتن: الاتصال والانفصال وبث الموقع (SPEC القسم 10/12).

الطبقة التي فوق `services/geo.py`: تلك تعرف Redis وحده، وهذه تعرف من يحق له
أن يظهر على الخريطة أصلاً. يستعملها الراوتر ومقبس WebSocket معاً.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, DocumentsIncomplete, PermissionDenied
from app.models.driver import Driver
from app.models.enums import CountryCode, DriverStatus, VehicleCategory
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services import geo, route
from app.ws import events


@dataclass(frozen=True, slots=True)
class PresenceContext:
    """ما يلزم لكتابة موقع الكبتن، مقروءاً من القاعدة مرة واحدة.

    مقبس الكبتن يستقبل موقعاً كل ثلاث ثوانٍ؛ لولا هذا لسأل القاعدة عن دولته
    وفئة مركبته مع كل رسالة.
    """

    driver_id: uuid.UUID
    country_code: CountryCode
    vehicle_category: VehicleCategory


async def presence_context(session: AsyncSession, driver: Driver) -> PresenceContext:
    """يتحقق من أهلية الظهور ويجمع ثوابتها."""
    if driver.status != DriverStatus.APPROVED:
        raise PermissionDenied("حساب الكبتن غير معتمد بعد")

    country_code = await session.scalar(
        select(User.country_code).where(User.id == driver.user_id)
    )
    category = await session.scalar(
        select(Vehicle.category)
        .where(Vehicle.driver_id == driver.id)
        .order_by(Vehicle.created_at)
        .limit(1)
    )
    if category is None:
        # الراكب يختار الفئة عند الطلب، فكبتن بلا مركبة مسجّلة لا يقابل أي طلب
        raise Conflict("سجّل مركبتك قبل الاتصال")

    return PresenceContext(
        driver_id=driver.id, country_code=country_code, vehicle_category=category
    )


async def go_online(
    session: AsyncSession, driver: Driver
) -> PresenceContext:
    """يرفع `is_online`. الـ commit مسؤولية المستدعي.

    لا يدخل الكبتنُ الفهرسَ الجغرافي هنا: لا موقع له بعد. أول بث موقع هو ما
    يجعله مرئياً للتوزيع فعلاً.
    """
    context = await presence_context(session, driver)
    driver.is_online = True
    return context


async def go_offline(session: AsyncSession, redis: Redis, driver: Driver) -> None:
    """خروج صريح: يسقط من الفهرس فوراً بلا انتظار انقضاء الحضور."""
    country_code = await session.scalar(
        select(User.country_code).where(User.id == driver.user_id)
    )
    driver.is_online = False
    await geo.go_offline(redis, driver_id=driver.id, country_code=country_code)


async def report_location(
    redis: Redis,
    context: PresenceContext,
    *,
    lat: float,
    lng: float,
    heading: float | None,
) -> None:
    """بث موقع واحد: يحدّث Redis GEO ويصل راكبَه المُسنَد إن كان في رحلة.

    البث غير مشروط برحلة جارية لأن قناة الموقع خاصة بالكبتن، ولا يشترك فيها
    إلا راكبٌ أسندت له القاعدة هذا الكبتن — فلا تسريب.

    ومن هنا وحده يُلتقط مسار الرحلة (SPEC القسم 5.7): البثّ هو مصدر النقاط،
    فوضعُ الالتقاط في مسارٍ آخر يعني مساراً ناقصاً لكبتنٍ يبث من القناة
    الأخرى. `route.capture` يعرف بنفسه متى لا يكتب شيئاً.
    """
    await geo.update_location(
        redis,
        driver_id=context.driver_id,
        country_code=context.country_code,
        lat=lat,
        lng=lng,
        heading=heading,
        vehicle_category=context.vehicle_category,
    )
    await route.capture(
        redis, driver_id=context.driver_id, lat=lat, lng=lng, heading=heading
    )
    await events.publish_driver_location(
        redis, driver_id=context.driver_id, lat=lat, lng=lng, heading=heading
    )


async def nearby_available(
    redis: Redis,
    session: AsyncSession,
    *,
    country_code: CountryCode,
    lat: float,
    lng: float,
    radius_km: float = geo.SEARCH_RADIUS_KM,
) -> list[geo.DriverPresence]:
    """الكباتن المتاحون حول الراكب لعرضهم على خريطته (SPEC القسم 10).

    «المتاحون فقط»: أونلاين + معتمد + اشتراك ساري + بلا رحلة — بنفس استدعاء
    `dispatch.eligible_driver_ids`، فمن لا يصلح للإسناد لا يُعرض سيارةً متاحة.
    """
    from app.services import dispatch

    presences = await geo.nearby(
        redis, country_code=country_code, lat=lat, lng=lng, radius_km=radius_km
    )
    if not presences:
        return []

    available: list[geo.DriverPresence] = []
    for category in {presence.vehicle_category for presence in presences}:
        of_category = [p for p in presences if p.vehicle_category == category]
        eligible = await dispatch.eligible_driver_ids(
            session, [p.driver_id for p in of_category], category
        )
        available.extend(p for p in of_category if p.driver_id in eligible)

    available.sort(key=lambda presence: presence.distance_km)
    return available


def anonymous_ref(driver_id: uuid.UUID, salt: str) -> str:
    """بديل مجهول لهوية الكبتن على خريطة الراكب.

    SPEC القسم 10 يوجب تجهيل هذه المواقع تماماً، لكن تنعيم حركة الأيقونات في
    الواجهة يحتاج مفتاحاً يربط السيارة بين تحديث وآخر. الحل بديلٌ مشتق بمِلح
    خاص بكل اتصال/طلب: ثابت داخل الجلسة الواحدة، مختلف في التالية — فلا
    يُتتبع كبتن عبر الزمن ولا يُستدل على هويته.
    """
    return hashlib.blake2s(
        str(driver_id).encode(), key=salt.encode()[:32], digest_size=8
    ).hexdigest()


# ------------------------------------------------- اعتماد الكبتن (8-ب)


async def set_status(
    session: AsyncSession,
    *,
    driver: Driver,
    status: DriverStatus,
    actor: User | None,
    reason: str | None = None,
) -> Driver:
    """يغيّر حالة الكبتن ويسجّلها في التدقيق. الـ commit مسؤولية الراوتر.

    `actor` يقبل `None` لتغييرٍ لم يقرره مشرف: استبدالُ الكبتن لمستندٍ مطلوب
    يعيده `pending` من تلقاء الفعل لا من قرار أحد (المرحلة 9-ب). والقيدُ
    يُكتب في الحالتين — سؤال «لماذا سقط اعتمادُه؟» يُسأل بعد شهر.
    """
    from app.models.enums import AuditAction
    from app.services import audit

    driver.status = status
    details: dict[str, str] = {"status": status.value}
    if reason is not None:
        details["reason"] = reason

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.UPDATE,
        entity_type="driver",
        entity_id=driver.id,
        details=details,
    )
    await session.flush()
    return driver


async def approve(session: AsyncSession, *, driver: Driver, actor: User) -> Driver:
    """اعتماد الكبتن — **بحارسين لا واحد**.

    **الأول: رقمٌ مُثبت مهما كان مفتاح التحقق.** رقمُ الكبتن هو ما يستلم عليه
    حوالات كليك (SPEC القسم 6/9) وما تصله عليه تنبيهاتُ الاشتراك؛ فاعتمادُ من
    لا نعرف أنه يملكه إرسالُ مالٍ إلى رقمٍ مجهول. ولذلك لا يعفيه إطفاء
    `otp_verification_enabled`: ذاك يعفي **التسجيل** ليمر الناس، لا الاعتماد
    ليمر المال.

    **والثاني (المرحلة 9-ب): مستنداتٌ مطلوبةٌ مقبولةٌ كلها.** SPEC القسم 12/1
    يقول «لا يُعتمد الكبتن قبل مراجعة الإدارة للمستندات»، والقسم 13/2 يجعل
    المراجعة قبولاً أو رفضاً لكل مستند. وبغير هذا الحارس تصير المراجعة
    عادةً لا شرطاً: زرُّ «اعتماد» يعمل والمستنداتُ فارغة، وهو ما كان يقع
    فعلاً قبل هذه المرحلة.

    وليس بينهما ترتيبٌ ذو معنى فيُفحص الأرخص أولاً.
    """
    from app.services import documents, verification

    owner = await session.get(User, driver.user_id)
    verification.require_verified(owner)

    missing = await documents.missing_required(session, driver.id)
    if missing:
        names = "، ".join(documents.label_for(item) for item in missing)
        raise DocumentsIncomplete(f"مستندات لم تُعتمد بعد: {names}")

    return await set_status(
        session, driver=driver, status=DriverStatus.APPROVED, actor=actor
    )
