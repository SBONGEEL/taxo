"""رحلةٌ لشخصٍ آخر (SPEC §٦٣-ج/١، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأةٌ لكلِّ سوقٍ حتى يُشعلها المالك**.

**ثلاثةُ أشياءَ وحدَها تختلف عن رحلةٍ عاديّة**، وما عداها الرحلةُ نفسُها بأبوابها:

1. **من يركب ومن يدفع** على صفِّ الرحلة (`for_other` · `passenger_*` · `payer`) — يكتبها `rides.request_ride` بعد `prepare`،
   ويقرؤها `payments` (قناةُ الدفع تتبع الدافع، **ودفعةُ نقد الراكب الفعليّ تُفتح عند الإنهاء**).
2. **رابطُ تتبّعٍ يرسله الطالبُ بنفسه** (`track_link`) ويفتحه أيُّ متصفّحٍ بلا دخول (`public_view`): اسمُ الكبتن وسيارتُه
   ولوحتُها وموقعُه **حتى تنتهي الرحلة** — ولا رقمَ الطالب ولا محفظتَه.
3. **محوُ الاسم والرقم بعد ٣٠ يوماً** من انتهاء الرحلة (`purge_passengers`، كنسٌ يوميّ).

**ورسمُ الإلغاء على الطالب** وإن كان الراكبُ الفعليُّ يدفع نقداً — **وهو كذلك بالبناء**: الطالبُ صاحبُ الحساب الوحيد في
الرحلة، فرسمُ `cancellation.charge_for` يقع عليه بلا سطرٍ هنا (والاختبارُ يثبته).

**والخدمةُ النسائيةُ كما هي**: خيارُها لمن يملكه حسابُه — **ولا يفتحها طلبٌ لغيره ولا يغلقها**.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    InvalidInput,
    NotFound,
    RideForOtherUnavailable,
    TrackLinkUnavailable,
)
from app.core.digits import latin_digits
from app.core.phone import InvalidPhoneNumber, normalize_phone
from app.models.driver import Driver
from app.models.enums import CountryCode, FeatureKey, RidePayer, RideStatus
from app.models.ride import ACTIVE_RIDER_STATUSES, Ride
from app.models.ride_track import RideTrackToken
from app.models.user import User
from app.services import geo, settings_service

#: **ثلاثون يوماً من انتهاء الرحلة** ثمّ يُمحى الاسمُ والرقم — قرارُ المالك بلفظه، **لا إعدادٌ يُضبط**: مدّةٌ في سطر سياسة
#: الخصوصية (§٦٣-هـ)، وتغييرُها تغييرُ وعدٍ مكتوبٍ للناس لا رقمٍ في اللوحة
PASSENGER_RETENTION_DAYS = 30

#: أطوارٌ يعمل فيها الرابط — **ما بعد الطلب وقبل الانتهاء**. وقبل القبول لا كبتنَ يُرى، فيقول الرابطُ «نبحث عن كبتن»
TRACKABLE = frozenset(ACTIVE_RIDER_STATUSES)


@dataclass(frozen=True, slots=True)
class PassengerRequest:
    """ما يكتبه الطالبُ عن الراكب الفعليّ — يمرّ بـ`prepare` قبل أن يصير أعمدة."""

    name: str
    phone: str
    payer: RidePayer


@dataclass(frozen=True, slots=True)
class PreparedPassenger:
    name: str
    phone: str
    payer: RidePayer


def _normalize_any(raw: str, country: CountryCode) -> str:
    """**سوقُ الطالب أولاً ثمّ الآخر** — الراكبُ الفعليُّ قد يحمل رقماً من السوق الثاني (+962 · +218)، **والصيغةُ المحلّيةُ
    تُقرأ بسوق الطالب** فلا يُخمَّن بلدُ «079…»."""
    order = [country, *(c for c in CountryCode if c != country)]
    last: InvalidPhoneNumber | None = None
    for code in order:
        try:
            return normalize_phone(raw, code)
        except InvalidPhoneNumber as exc:
            last = exc
    assert last is not None
    raise last


async def prepare(
    session: AsyncSession, *, rider: User, passenger: PassengerRequest
) -> PreparedPassenger:
    """يُفحص المفتاحُ **عند الإنشاء لا عند العرض** (قاعدةُ المحطات): واجهةٌ تخفي الخيارَ لا تمنع طلباً مصنوعاً بيد."""
    if not await settings_service.is_feature_enabled(
        session, rider.country_code, FeatureKey.RIDE_FOR_OTHER_ENABLED
    ):
        raise RideForOtherUnavailable()
    name = latin_digits(" ".join(passenger.name.split()))
    if len(name) < 2:
        raise InvalidInput("اكتب اسمَ الراكب")
    try:
        phone = _normalize_any(passenger.phone, rider.country_code)
    except InvalidPhoneNumber as exc:
        raise InvalidInput(f"رقمُ الراكب: {exc}") from exc
    # **رقمُ الطالب نفسِه ليس «شخصاً آخر»**: رحلةٌ لنفسه بأعمدة غيره تفتح دفعةَ نقدٍ لا يقف عندها أحدٌ غيرُه
    if rider.phone and phone == rider.phone:
        raise InvalidInput("هذا رقمُك — اطلب الرحلةَ لنفسك")
    return PreparedPassenger(name=name, phone=phone, payer=passenger.payer)


# ------------------------------------------------------------------ رابطُ التتبّع


async def track_link(session: AsyncSession, *, ride_id: uuid.UUID, rider: User) -> str:
    """رمزُ رابط التتبّع لرحلةٍ يطلبها الطالبُ لغيره — **الرمزُ نفسُه في كلِّ ضغطة**.

    **فريدٌ على الرحلة في القاعدة**: ضغطتان معاً تُدخلان صفّين فيسقط الثاني على القيد، **فيُقرأ الأولُ ويُعاد** — رابطان
    لرحلةٍ واحدةٍ يجعلان «أوقِف الرابط» يوماً سؤالاً عن أيِّهما. **وفي نقطة حفظٍ** (`begin_nested`) كي لا يُسقط الاصطدامُ
    معاملةَ الطلب كلَّها.
    """
    ride = await session.get(Ride, ride_id)
    # 404 لا 403: وجودُ الرحلة ليس معلومةً يستحقها غيرُ أطرافها
    if ride is None or ride.rider_id != rider.id:
        raise NotFound("الرحلة غير موجودة")
    if not ride.for_other or ride.status not in TRACKABLE:
        raise TrackLinkUnavailable()
    if not await settings_service.is_feature_enabled(
        session, ride.country_code, FeatureKey.RIDE_FOR_OTHER_ENABLED
    ):
        raise RideForOtherUnavailable()

    existing = await session.scalar(
        select(RideTrackToken.token).where(RideTrackToken.ride_id == ride.id)
    )
    if existing is not None:
        return existing
    token = secrets.token_urlsafe(16)
    try:
        async with session.begin_nested():
            session.add(RideTrackToken(ride_id=ride.id, token=token))
    except IntegrityError:
        # الاصطدامُ على الفريد: ضغطةٌ أخرى كتبت رمزَها قبل هذه — **فرمزُها هو الجواب**
        winner = await session.scalar(
            select(RideTrackToken.token).where(RideTrackToken.ride_id == ride.id)
        )
        if winner is None:
            raise
        return winner
    return token


@dataclass(frozen=True, slots=True)
class PublicTrack:
    """ما يراه من يفتح الرابط — **أقلُّ ما يكفي**: لا معرّفُ رحلةٍ ولا كبتنٍ ولا عنوانٌ ولا أجرة."""

    state: str  # searching · coming · arrived · riding · ended
    captain_name: str | None
    vehicle: dict[str, str] | None
    position: dict[str, float] | None


_STATE = {
    RideStatus.REQUESTED: "searching",
    RideStatus.SEARCHING: "searching",
    RideStatus.ACCEPTED: "coming",
    RideStatus.ARRIVED: "arrived",
    RideStatus.IN_PROGRESS: "riding",
    RideStatus.AT_STOP: "riding",
}


async def public_view(session: AsyncSession, redis: Redis, *, token: str) -> PublicTrack:
    """**رمزٌ لا يُعرف = 404**، **ورحلةٌ انتهت = «انتهت» بلا كبتنٍ ولا موقع** — فالرابطُ يتوقّف بانتهائها لا بعمودٍ ثانٍ.

    **ومفتاحٌ أُطفئ بعد إرسال الرابط يُوقفه أيضاً**: الإطفاءُ قرارٌ بأن الخدمةَ لا تعمل، ورابطٌ يُفتح بعده يقول غيرَ ذلك.
    """
    row = await session.scalar(select(RideTrackToken).where(RideTrackToken.token == token))
    if row is None:
        raise NotFound("الرابط غير موجود")
    ride = await session.scalar(
        select(Ride)
        .where(Ride.id == row.ride_id)
        .options(
            selectinload(Ride.driver).selectinload(Driver.user),
            selectinload(Ride.driver).selectinload(Driver.vehicles),
        )
    )
    if ride is None:
        raise NotFound("الرابط غير موجود")
    state = _STATE.get(ride.status)
    if state is None or not await settings_service.is_feature_enabled(
        session, ride.country_code, FeatureKey.RIDE_FOR_OTHER_ENABLED
    ):
        return PublicTrack(state="ended", captain_name=None, vehicle=None, position=None)
    if ride.driver is None:
        return PublicTrack(state=state, captain_name=None, vehicle=None, position=None)

    vehicles = ride.driver.vehicles
    vehicle = (
        {
            "make": vehicles[0].make,
            "model": vehicles[0].model,
            "color": vehicles[0].color,
            "plate_number": vehicles[0].plate_number,
        }
        if vehicles
        else None
    )
    spot = await geo.last_position(redis, driver_id=ride.driver.id, country_code=ride.country_code)
    return PublicTrack(
        state=state,
        # **الاسمُ كما يراه الراكبُ في بطاقة الكبتن** (`RideDriverOut.name`) — لا أكثر
        captain_name=ride.driver.user.name,
        vehicle=vehicle,
        position={"lat": spot.lat, "lng": spot.lng} if spot is not None else None,
    )


# ------------------------------------------------------------------ المحو


async def purge_passengers(session: AsyncSession, *, now: datetime | None = None) -> int:
    """يمحو اسمَ الراكب الفعليّ ورقمَه **بعد ٣٠ يوماً من انتهاء الرحلة**، ويكتب متى — ويعيد كم رحلةً مُحيت.

    **«انتهاء الرحلة» آخرُ زمنَي الإنهاء والإلغاء**، ورحلةٌ لم تنتهِ لا تُمسّ مهما طالت. **وتحديثٌ واحدٌ لا حلقة**: الشرطُ كلُّه
    في القاعدة، فلا صفَّ يُقرأ ثمّ يُكتب بقيمةٍ قديمة. **ورموزُ تتبّعها تُحذف معها**: رابطٌ لرحلةٍ مُحي راكبُها لا يقول شيئاً.
    """
    moment = now or datetime.now(UTC)
    cutoff = moment - timedelta(days=PASSENGER_RETENTION_DAYS)
    ended_at = Ride.completed_at.is_not(None) & (Ride.completed_at < cutoff)
    cancelled_at = Ride.cancelled_at.is_not(None) & (Ride.cancelled_at < cutoff)
    result = await session.execute(
        update(Ride)
        .where(
            Ride.for_other.is_(True) | (Ride.ride_type == "parcel"),
            Ride.passenger_erased_at.is_(None),
            ended_at | cancelled_at,
        )
        .values(
            passenger_name=None,
            passenger_phone=None,
            # **ومستلمُ الطرد بالكنس نفسِه** (§٦٣-ج/٤)
            recipient_name=None,
            recipient_phone=None,
            recipient_address=None,
            # **ووصفُ غرض «أحضر غرضي» معهم** (§٧٢-ج/١) — ومن يسلّمه في حقول المستلم نفسِها
            parcel_item=None,
            passenger_erased_at=moment,
        )
        .returning(Ride.id)
        .execution_options(synchronize_session=False)
    )
    erased = [row[0] for row in result]
    if erased:
        await session.execute(
            RideTrackToken.__table__.delete().where(RideTrackToken.ride_id.in_(erased))
        )
    return len(erased)
