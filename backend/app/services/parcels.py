"""الطرد (SPEC §٦٣-ج/٤، قرارُ المالك ٢٠٢٦-١٠-٠٧) — **مطفأٌ لكلِّ سوقٍ حتى يُشعله المالك**.

**رحلةٌ اقتصاديّةٌ تحمل غرضاً بدل راكب**، وثلاثةُ أشياءَ تزيد عليها:

1. **رسمٌ للكبتن** (`fee_for`، من `service_settings.parcel_fee`) — يُحسب في `pricing.estimate` كرسم المطار: سطرٌ داخل الأجرة **خارجَ العمولة
   والخصم**.
2. **الشروطُ قبل الطلب ويُقرّ بها المرسل** (`TERMS` — الواجهةُ تعرضها، والخلفيةُ ترفض طلباً بلا إقرار): الممنوعاتُ والحجمُ وحقُّ الكبتن في
   الرفض ولا تعويضَ عن المحتوى.
3. **المستلمُ ومن يدفع**: اسمٌ وعنوانٌ ورقمٌ يُمحى بعد ٣٠ يوماً بكنس `ride_for_other.purge_passengers` نفسِه، **والدافعُ المرسلُ أو المستلمُ
   نقداً** — ودفعةُ المستلم يفتحها الإنهاءُ كدفعة الراكب الفعليّ.

**ورفضُ الكبتن عند الاستلام** إلغاءٌ منه في طور «وصل» بسببٍ مصنَّف — **بلا مالٍ على أحد** (§٦٣-د/٦، توصيتي حتى جوابه).

## «أحضر غرضي» (§٧٢-ج/١) — **الطردُ نفسُه معكوساً**

راكبٌ في عمله نسي شاحنَه في البيت: **الانطلاقُ مكانُ الغرض والوجهةُ مكانُه هو** (أو عنوانٌ يختاره). **وحقولُ المستلم الثلاثة تحمل من
يسلّم الغرضَ للكبتن** — اسمُه ورقمُه وعنوانُ الاستلام — فيمحوها الكنسُ نفسُه بعد ٣٠ يوماً، **ومعها وصفُ الغرض** (`parcel_item`).
**والشروطُ هي هي** (`TERMS`)، **والدافعُ صاحبُ الطلب وحدَه** — بمحفظته أو بطاقته أو نقداً عند التسليم إليه. **ومفتاحُه ورسمُه مستقلّان**
(`parcel_fetch_enabled` · `parcel_fetch_fee`)، فيُشعَل وحدَه، **ولا يحتاج مفتاحَ الطرد**.
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


class ParcelFetchUnavailable(FeatureDisabled):
    code = "parcel_fetch_unavailable"
    message = "«أحضر غرضي» غيرُ مفعّلةٍ في بلدك"


@dataclass(frozen=True, slots=True)
class ParcelRequest:
    recipient_name: str
    recipient_phone: str
    recipient_address: str
    payer: RidePayer
    accepted_terms: bool
    #: **«أحضر غرضي»** — والحقولُ الثلاثةُ أعلاه حينها لمن يسلّم الغرض، و`item` وصفُه
    fetch: bool = False
    item: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedParcel:
    recipient_name: str
    recipient_phone: str
    recipient_address: str
    payer: RidePayer
    fetch: bool = False
    item: str | None = None


async def fee_for(session: AsyncSession, country: CountryCode, *, fetch: bool = False) -> Decimal:
    """**الرسمُ إن كانت الخدمةُ متاحة، وإلا صفر** — المفتاحُ مشتعلٌ والرسمُ موجب (صفرٌ يُخفيها). **و«أحضر غرضي» بمفتاحه ورسمه هو**."""
    key = FeatureKey.PARCEL_FETCH_ENABLED if fetch else FeatureKey.PARCEL_ENABLED
    if not await settings_service.is_feature_enabled(session, country, key):
        return Decimal("0.000")
    row = await session.get(ServiceSetting, country)
    if row is None:
        return Decimal("0.000")
    return round_money(row.parcel_fetch_fee if fetch else row.parcel_fee)


async def prepare(
    session: AsyncSession, *, rider: User, parcel: ParcelRequest, vehicle_category: VehicleCategory
) -> PreparedParcel:
    from app.services.ride_for_other import _normalize_any

    if await fee_for(session, rider.country_code, fetch=parcel.fetch) <= 0:
        raise ParcelFetchUnavailable() if parcel.fetch else ParcelUnavailable()
    if not parcel.accepted_terms:
        raise InvalidInput("اقرأ الشروطَ ووافق عليها قبل الطلب" if parcel.fetch else "اقرأ شروطَ الطرد ووافق عليها قبل الطلب")
    if vehicle_category is not VehicleCategory.ECONOMY:
        raise InvalidInput("«أحضر غرضي» بسعر الاقتصادي وحدَه" if parcel.fetch else "الطردُ بسعر الاقتصادي وحدَه")
    # **«أحضر غرضي» يدفعه صاحبُه وحدَه** — هو من يستلم، فلا «مستلمُ نقداً» غيرُه (القيدُ `ride_parcel_fetch` يحرسه في القاعدة أيضاً)
    if parcel.fetch and parcel.payer is not RidePayer.REQUESTER:
        raise InvalidInput("في «أحضر غرضي» تدفع أنت — بالمحفظة أو البطاقة أو نقداً عند التسليم")
    if parcel.payer is RidePayer.PASSENGER_CASH:
        raise InvalidInput("في الطرد يدفع المرسلُ أو المستلمُ نقداً")
    name = latin_digits(" ".join(parcel.recipient_name.split()))
    address = latin_digits(" ".join(parcel.recipient_address.split()))
    who = "من يسلّم الغرض" if parcel.fetch else "المستلم"
    if len(name) < 2 or len(address) < 3:
        raise InvalidInput(f"اكتب اسمَ {who} وعنوانَ الاستلام" if parcel.fetch else "اكتب اسمَ المستلم وعنوانَه")
    item = None
    if parcel.fetch:
        item = latin_digits(" ".join((parcel.item or "").split()))
        if len(item) < 2:
            raise InvalidInput("صِف الغرضَ بكلماتٍ قليلة — ليعرفه الكبتنُ عند الاستلام")
    try:
        phone = _normalize_any(parcel.recipient_phone, rider.country_code)
    except InvalidPhoneNumber as exc:
        raise InvalidInput(f"رقمُ {who}: {exc}") from exc
    return PreparedParcel(
        recipient_name=name, recipient_phone=phone, recipient_address=address, payer=parcel.payer,
        fetch=parcel.fetch, item=item,
    )
