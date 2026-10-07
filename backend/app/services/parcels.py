"""الطرد (SPEC §٦٣-ج/٤، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأٌ لكلِّ سوقٍ حتى يُشعله المالك**.

**رحلةٌ اقتصاديّةٌ تحمل غرضاً بدل راكب**، وثلاثةُ أشياءَ تزيد عليها:

1. **رسمٌ للكبتن** (`fee_for`، من `service_settings.parcel_fee`) — يُحسب في `pricing.estimate` كرسم المطار: سطرٌ داخل الأجرة **خارجَ العمولة
   والخصم**.
2. **الشروطُ قبل الطلب ويُقرّ بها المرسل** (`TERMS` — الواجهةُ تعرضها، والخلفيةُ ترفض طلباً بلا إقرار): الممنوعاتُ والحجمُ وحقُّ الكبتن في
   الرفض ولا تعويضَ عن المحتوى.
3. **المستلمُ ومن يدفع**: اسمٌ وعنوانٌ ورقمٌ يُمحى بعد ٣٠ يوماً بكنس `ride_for_other.purge_passengers` نفسِه، **والدافعُ المرسلُ أو المستلمُ
   نقداً** — ودفعةُ المستلم يفتحها الإنهاءُ كدفعة الراكب الفعليّ.

**ورفضُ الكبتن عند الاستلام** إلغاءٌ منه في طور «وصل» بسببٍ مصنَّف — **بلا مالٍ على أحد** (§٦٣-د/٦، توصيتي حتى جوابه).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.digits import latin_digits
from app.core.exceptions import FeatureDisabled, InvalidInput
from app.core.phone import InvalidPhoneNumber
from app.models.enums import CountryCode, FeatureKey, RidePayer, VehicleCategory
from app.models.service_setting import ServiceSetting
from app.models.user import User
from app.services import settings_service
from app.services.pricing import round_money

#: **الشروطُ كما يقرؤها المرسلُ قبل أن يطلب** — نصُّ المالك بلفظه، **ومصدرُها هنا** فتنشرها الخلفيةُ ولا تكتبها الواجهة
TERMS: tuple[str, ...] = (
    "ممنوع: النقود والمجوهرات والأدوية والسوائل القابلة للاشتعال وكلُّ ما يخالف القانون.",
    "الحجم: ما يسعه صندوقُ السيارة.",
    "للكبتن أن يرفض الطرد عند الاستلام إن شكّ فيه.",
    "لا تعويضَ عن محتوى الطرد في هذه المرحلة.",
)


class ParcelUnavailable(FeatureDisabled):
    code = "parcel_unavailable"
    message = "الطرد غيرُ مفعّلٍ في بلدك"


@dataclass(frozen=True, slots=True)
class ParcelRequest:
    recipient_name: str
    recipient_phone: str
    recipient_address: str
    payer: RidePayer
    accepted_terms: bool


@dataclass(frozen=True, slots=True)
class PreparedParcel:
    recipient_name: str
    recipient_phone: str
    recipient_address: str
    payer: RidePayer


async def fee_for(session: AsyncSession, country: CountryCode) -> Decimal:
    """**الرسمُ إن كانت الخدمةُ متاحة، وإلا صفر** — المفتاحُ مشتعلٌ والرسمُ موجب (صفرٌ يُخفيها)."""
    if not await settings_service.is_feature_enabled(session, country, FeatureKey.PARCEL_ENABLED):
        return Decimal("0.000")
    row = await session.get(ServiceSetting, country)
    return round_money(row.parcel_fee) if row is not None else Decimal("0.000")


async def prepare(
    session: AsyncSession, *, rider: User, parcel: ParcelRequest, vehicle_category: VehicleCategory
) -> PreparedParcel:
    from app.services.ride_for_other import _normalize_any

    if await fee_for(session, rider.country_code) <= 0:
        raise ParcelUnavailable()
    if not parcel.accepted_terms:
        raise InvalidInput("اقرأ شروطَ الطرد ووافق عليها قبل الطلب")
    if vehicle_category is not VehicleCategory.ECONOMY:
        raise InvalidInput("الطردُ بسعر الاقتصادي وحدَه")
    if parcel.payer is RidePayer.PASSENGER_CASH:
        raise InvalidInput("في الطرد يدفع المرسلُ أو المستلمُ نقداً")
    name = latin_digits(" ".join(parcel.recipient_name.split()))
    address = latin_digits(" ".join(parcel.recipient_address.split()))
    if len(name) < 2 or len(address) < 3:
        raise InvalidInput("اكتب اسمَ المستلم وعنوانَه")
    try:
        phone = _normalize_any(parcel.recipient_phone, rider.country_code)
    except InvalidPhoneNumber as exc:
        raise InvalidInput(f"رقمُ المستلم: {exc}") from exc
    return PreparedParcel(recipient_name=name, recipient_phone=phone, recipient_address=address, payer=parcel.payer)
