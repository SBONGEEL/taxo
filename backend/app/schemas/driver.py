from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings
from app.models.enums import (
    AdvanceStatus,
    CountryCode,
    DeactivationStatus,
    DocumentReviewStatus,
    DocumentType,
    DriverStatus,
    Gender,
    GenderPreference,
    VehicleCategory,
)
from app.schemas.auth import UserOut

if TYPE_CHECKING:  # حضورُ الكبتن نوعُ خدمةٍ لا نوعُ مخطَّط — يُستورد للتلميح وحده
    from app.models.vehicle_skin import VehicleSkin
    from app.services.geo import DriverPresence, MapSkin


class VehicleCreate(BaseModel):
    make: str = Field(min_length=1, max_length=60)
    model: str = Field(min_length=1, max_length=60)
    year: int = Field(ge=1990, le=2100)
    color: str = Field(min_length=1, max_length=40)
    plate_number: str = Field(min_length=2, max_length=32)
    category: VehicleCategory = VehicleCategory.ECONOMY


class VehicleUpdate(BaseModel):
    """تعديلٌ جزئي لبيانات المركبة (`FUTURE-FEATURES` بند 43).

    **وحقولُ الهوية منها تُسقط الاعتماد** — انظر `services/vehicles.py`.
    """

    make: str | None = Field(default=None, min_length=1, max_length=60)
    model: str | None = Field(default=None, min_length=1, max_length=60)
    year: int | None = Field(default=None, ge=1990, le=2100)
    color: str | None = Field(default=None, min_length=1, max_length=40)
    plate_number: str | None = Field(default=None, min_length=2, max_length=32)
    category: VehicleCategory | None = None


class VehicleUpdateResultOut(BaseModel):
    """المركبةُ بعد التعديل **ومعها ما وقع للاعتماد**.

    يقولها الجوابُ صراحةً كجواب رفع المستند (المرحلة 9-ب): بغيرها يكتشف
    الكبتن أنه خرج من التوزيع حين لا تصله طلبات، لا حين فعلَ ما أخرجه.
    """

    vehicle: "VehicleOut"
    approval_reverted: bool
    driver_status: DriverStatus


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_id: uuid.UUID
    make: str
    model: str
    year: int
    color: str
    plate_number: str
    category: VehicleCategory
    created_at: datetime


class DriverDocumentOut(BaseModel):
    """مستندٌ كما يراه صاحبه واللوحة.

    **بلا `file_path`**: المسار تفصيلُ تخزينٍ داخلي، وكشفُه يغري ببناء رابطٍ
    منه — والملف لا يُقرأ إلا من مسارٍ يتحقق من الملكية أولاً (القسم 14).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doc_type: DocumentType
    content_type: str
    size_bytes: int
    review_status: DocumentReviewStatus
    review_note: str | None
    # **تاريخُ الانتهاء ومصدرُه** (البند ب) — `None` يعني «لا تاريخَ لهذا النوع»
    expires_on: date | None
    expiry_source: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentReviewIn(BaseModel):
    """قرارُ مراجعةٍ واحد. الملاحظة **إلزامية عند الرفض**.

    رفضٌ بلا سبب يترك الكبتن يعيد رفع الصورة نفسها ثم ينتظر النتيجة نفسها —
    فيبقى «قيد المراجعة» بلا نهاية. والقبول لا يحتاج شرحاً.
    """

    approved: bool
    note: str | None = Field(default=None, max_length=500)
    # **تصحيحُ المشرف للتاريخ — يُرسَل أو لا يُرسَل** (البند ب): غيابُ الحقل
    # يعني «لا تُغيّره»، وإرسالُه فارغاً يعني «امْحُه». والتمييزُ بينهما لازم،
    # وإلا مَحَت كلُّ مراجعةٍ لا تذكر التاريخَ ما أقرّه الكبتن.
    expires_on: date | None = None

    @model_validator(mode="after")
    def _note_required_on_reject(self) -> "DocumentReviewIn":
        if not self.approved and not (self.note or "").strip():
            raise ValueError("سبب الرفض مطلوب")
        return self


class DriverDocumentsOut(BaseModel):
    """مستندات كبتنٍ ومعها ما ينقصه للاعتماد — سؤالٌ واحد بجوابٍ واحد.

    **و`required` كاملةً لا `missing` وحدها** (البند ١١): صار من المستندات ما
    هو اختياريٌّ يُرفع ويُراجَع ولا يحبس اعتماداً، والناقصُ لا يفرّق بينه وبين
    المرفوع — فمن رفع صورةً اختياريةً يظهر كمن رفع مطلوباً. والقائمةُ من
    الخلفية لا من نسخةٍ في التطبيق: نسختان لشرطِ اعتمادٍ تفترقان يومَ يتغيّر.
    """

    documents: list[DriverDocumentOut]
    missing_required: list[DocumentType]
    # **ما على الكبتن أن يرفعه** — غيرُ ما ينقص الحارسَ: المرفوعُ المنتظِرُ
    # مراجعةً ليس على صاحبه فيه شيء (البند: المرحلة ١٣)
    awaiting_upload: list[DocumentType]
    required: list[DocumentType]


class DocumentUploadOut(BaseModel):
    """جوابُ الرفع — ومعه أثرُه على حالة الكبتن.

    `approval_reverted` ليس تفصيلاً: استبدالُ مستندٍ مطلوبٍ يُسقط الاعتماد
    (سياسة 9-ب)، فبغير هذا الحقل يكتشف الكبتن أنه خرج من التوزيع حين لا
    تصله طلبات — لا حين فعلَ ما أخرجه.
    """

    document: DriverDocumentOut
    driver_status: DriverStatus
    approval_reverted: bool


class DriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: DriverStatus
    cliq_alias: str | None
    # تفضيلُه الدائم لجنس الركاب (المرحلة 10-ج) — يقرؤه تطبيقه ليرسم المفتاح
    gender_preference: GenderPreference
    rating_avg: Decimal
    # مفتاحُ التجديد التلقائي (البند ١٤) — يقرؤه تطبيقُه ليرسم المفتاح
    auto_renew: bool
    is_online: bool
    current_ride_id: uuid.UUID | None
    created_at: datetime


class DriverProfileOut(BaseModel):
    driver: DriverOut
    user: UserOut
    vehicles: list[VehicleOut]
    documents: list[DriverDocumentOut]

    # **نسبتُه هو لا نسبةُ السوق** (البند ٦٥): الرئيسيةُ تعرض «عمولة TAXO»،
    # **ورقمٌ مخبوزٌ في شاشة مالٍ يمنعه §14**. ومن اشترى اشتراكاً بوعدِ صفرٍ
    # يرى صفراً ولو رفع السوقُ نسبتَه — قاعدةُ الوعد المجمَّد نفسُها.
    #
    # **ومحسوبةٌ لا عمود**: `settings_service.commission_percent_of_driver`
    # هي الموضعُ الواحد، **وهي حرفاً ما يفعله `rides.accept`** — فلا يفترق
    # ما يُعرَض عمّا يُقتطَع.
    #
    # **وهنا لا في `DriverOut`**: بابُ «ملفّي» يعرف صاحبَه، **وصفُّ كبتنٍ في
    # جدول اللوحة لا يحمل هذا السؤال**. ونشرُه على كلِّ `DriverOut` يفرض
    # استعلاماً في خمسةِ مساراتٍ إداريّةٍ لا تقرؤه — **وحقلٌ لا يقرؤه أحدٌ هو
    # ما يمسكه `check:readers`**.
    commission_percent: Decimal


class DriverGenderUpdate(BaseModel):
    """جنسُ الكبتن كما يقرؤه المشرف من هويته المرفوعة (المرحلة 10-ج).

    مسارٌ إداريٌّ مستقل لا حقلٌ في `DriverUpdate`، لأن الكاتب مختلف: هذا يكتبه
    المشرف عن غيره وله قيدُ تدقيق، وذاك يكتبه صاحبه عن نفسه. وضبطُه **لا يعيد
    دورة اعتماد**: الهوية مرفوعةٌ ومراجَعةٌ أصلاً، وإرجاعُ كبتنٍ معتمدٍ إلى
    الطابور لأجل حقلٍ واحد يجعل تفريغ المتراكم مستحيلاً عملياً.
    """

    gender: Gender

    # **سببٌ يُطلب حين يخالف المثبَّتُ ما أقرّته** (2026-08-13): ذلك يُلغي
    # الوضعَ النسائيَّ عن الحساب، والسببُ **هو** فائدةُ قيد التدقيق حينها — لا
    # اسمُ الحقل. وهو نفسُ استثناء «سببٌ مكتوب» في الإيقاف وحظرِ الحساب وإطفاءِ
    # حارس (`services/audit.py`). ويبقى اختيارياً في حالة التطابق: سببٌ يُطلب
    # على كل ختمٍ يصير حقلاً يُملأ بأي شيءٍ ليمرّ الطلب
    reason: str | None = Field(default=None, min_length=3, max_length=255)


class DriverUpdate(BaseModel):
    """ما يملك الكبتن تغييره في ملفه — و`cliq_alias` وحده اليوم.

    عليه تصل حوالاتُ السحب (SPEC القسم 9)، فهو حقلُ الكبتن لا حقلُ الإدارة:
    من يملك الحساب البنكي هو من يكتب اسمه. وما عداه (الحالة، التقييم،
    الاتصال) يُكتب من مساراتٍ تملك قواعدَه.
    """

    cliq_alias: str | None = Field(default=None, max_length=64)
    # تفضيلُ جنس الركاب — يملكه الكبتن لا الإدارة، بخلاف **جنسه هو** الذي
    # يضبطه المشرف من الهوية (المرحلة 10-ج)
    gender_preference: GenderPreference | None = None
    # **إذنُ التجديد التلقائي** (البند ١٤): مالٌ يخرج من محفظته بلا ضغطةٍ منه،
    # فالمفتاحُ بيده وحدَه — لا بيد الإدارة ولا بحكم الافتراض
    auto_renew: bool | None = None


class DriverLocationIn(BaseModel):
    """بثّ موقع واحد من تطبيق الكبتن (SPEC القسم 10)."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    # اتجاه السير بالدرجات — تدور به أيقونة السيارة على خريطة الراكب
    heading: float | None = Field(default=None, ge=0, lt=360)


#: **بيتُ رابط الرسمة الواحد** — تقرؤه الخدمةُ (`vehicle_skins.art_url`)
#: ويقرؤه بانِي بطاقةِ الكبتن في `schemas/ride.py`. **وقالبٌ في موضعين
#: يفترق أوّلَ إعادةِ تسميةٍ للمسار**، فيرسم أحدُ البابين رابطاً ميّتاً.
#:
#: **والمفتاحُ مُعرّفُ المركبة لا `asset_key`**: العميلُ لا يعرف أيَّ
#: المصدرين وراءها — مولَّدةٌ في `app/assets/skins/` أو مرفوعةٌ إلى التخزين —
#: ورابطٌ يفصح عن ذلك يتغيّر يومَ تُستبدل إحداهما بالأخرى.
ART_STORE = "store"
ART_MAP = "map"


def skin_art_url(skin_id: uuid.UUID, kind: str) -> str:
    """**مع سابقة الـAPI** — لا بدونها.

    الرسمةُ تُحمَّل بوسم صورةٍ في المتصفّح، و`<img src="/…">` يُبنى على
    **أصلِ الصفحة** لا على أصل الـAPI — وهما مضيفان مختلفان في هذا المشروع
    (`app.tajora.ly` و`api.tajora.ly`). فمسارٌ بلا سابقةٍ يجعل التطبيقَ إمّا
    يطرق مضيفَه هو، وإمّا يلصق السابقةَ بيده — **وبيتٌ ثانٍ للسابقة يفترق
    عن `settings.api_v1_prefix` أوّلَ تغييرٍ فيها**.
    """
    return f"{settings.api_v1_prefix}/vehicle-skins/{skin_id}/art/{kind}"


class MapSkinOut(BaseModel):
    """مركبةُ الكبتن كما تُرسم على خريطة — **رسمٌ لا هوية** (2026-08-22).

    أربعةُ حقولٍ لا أكثر: مسارُ الرسمة ونسبةُ عرضها وهل تدور مع الاتجاه،
    ومُعرّفُها ليُميّز التطبيقُ بين رسمتين بلا أن يقارن نصوصَ مسارات.

    **ولا اسمَ ولا ندرةَ هنا**: على الخريطة الحرّة تكفي الرسمةُ للرسم،
    و«أسطورية» كلمةٌ تجعل من يعدّ السياراتِ يعرف من في أيّها.
    """

    skin_id: uuid.UUID
    image_url: str
    scale_percent: int
    rotates: bool

    @classmethod
    def of(cls, skin: "MapSkin | None") -> "MapSkinOut | None":
        """من حمولة الحضور (Redis) — مقروءةً لا مستعلَمة."""
        if skin is None:
            return None
        return cls(
            skin_id=skin.skin_id,
            image_url=skin.image_url,
            scale_percent=skin.scale_percent,
            rotates=skin.rotates,
        )

    @classmethod
    def for_skin(cls, skin: "VehicleSkin | None") -> "MapSkinOut | None":
        """من صفِّ الكتالوج — يستعمله بانِي بطاقة الكبتن بعد القبول."""
        if skin is None or not skin.is_active:
            return None
        return cls(
            skin_id=skin.id,
            image_url=skin_art_url(skin.id, ART_MAP),
            scale_percent=skin.map_scale_percent,
            rotates=skin.map_rotates,
        )


class NearbyDriverOut(BaseModel):
    """سيارة على خريطة الراكب قبل الطلب — مجهّلة بالكامل (SPEC القسم 10).

    لا هوية ولا لوحة ولا معرّف حقيقي: إحداثيات واتجاه وفئة، و`ref` بديل
    مؤقت لا يُستدل منه على كبتن (انظر `services/drivers.py::anonymous_ref`).
    """

    ref: str
    lat: float
    lng: float
    heading: float | None
    vehicle_category: VehicleCategory
    #: **مركبتُه المنشورة** — النادرةُ لا تصل هنا أبداً
    #: (`vehicle_skins.publishable_skin_for`)، وغيابُها لا يقع إلا حين لا
    #: بديلَ منشورٌ في الكتالوج فتغيب عن الجميع سواءً
    skin: MapSkinOut | None = None

    @classmethod
    def of(cls, presence: "DriverPresence", *, ref: str) -> "NearbyDriverOut":
        """**بانٍ واحدٌ لثلاثة أبواب** — REST مرتين والمقبس مرة.

        وهي القاعدةُ لا الترتيب: ثلاثةُ مواضعَ تبني الحمولةَ نفسَها بيدها
        تفترق أوّلَ حقلٍ يُضاف — وهو الشكلُ الثامن، وقد وقع في هذا المشروع
        (`commission_percent` مُلئ في بابٍ ونُسي في أخيه).
        """
        return cls(
            ref=ref,
            lat=presence.lat,
            lng=presence.lng,
            heading=presence.heading,
            vehicle_category=presence.vehicle_category,
            skin=MapSkinOut.of(presence.skin),
        )


class AdminDriverRow(BaseModel):
    """صفٌّ في قائمة الكباتن باللوحة (SPEC القسم 13/2).

    يجمع ما يقرؤه المشرف في سطرٍ واحد ليقرر: من هو، وحاله، وهل رقمُه مُثبت،
    وكم مستنداً ينتظر مراجعته. **وعدُّ المستندات هنا لا في نداءٍ لكل صف**:
    صفحةٌ من خمسين كبتناً تصير خمسين نداءً، وقرارُ «من أراجع الآن» يُتخذ من
    القائمة لا من فتح كل ملف.
    """

    driver_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    phone: str
    country_code: CountryCode
    status: DriverStatus
    phone_verified: bool
    rating_avg: Decimal
    # **ولا `auto_renew` هنا**: مفتاحٌ يملكه الكبتن على محفظته هو، ولا يقرأ منه
    # المشرفُ قراراً في قائمةٍ يفرز بها من يراجع. أُقحم مرةً بتعديلٍ أصاب
    # المخطّطين معاً، فسقط صفُّ اللوحة كلُّه بحقلٍ لا يرسله الاستعلام
    is_online: bool
    documents_pending: int
    documents_rejected: int
    missing_required: list[DocumentType]
    # جنسُ الكبتن ومعه هل خُتم (المرحلة 10-ج). تقرؤهما اللوحة لتُظهر **من
    # يعمل بلا جنسٍ مثبت**: بغير هذا الفرز يبقى المتراكم غير مرئي، ولا يُطلب
    # أحدٌ لخدمةٍ نسائية لأن أحداً لا يعرف من هي السائقة
    gender: Gender | None
    gender_verified: bool
    gender_preference: GenderPreference
    # **سقفُ السلفة الخاصُّ به** (وُصل له زرٌّ 2026-08-19): `null` لا تخصيص،
    # وصفرٌ منعٌ — وهما حالتان لا يحملهما رقمٌ واحد. ويُنشر لأن زرَّ التعديل
    # بلا القيمة الحالية زرٌّ يكتب فوق ما لا يراه صاحبُه
    advance_cap_override: Decimal | None
    created_at: datetime


class DriverStatusUpdate(BaseModel):
    """إيقافُ كبتنٍ أو إعادةُ تفعيله — بسببٍ يدخل سجل التدقيق.

    السببُ إلزاميٌّ في الإيقاف: «لماذا أُوقف؟» سؤالٌ يُسأل بعد شهر، وحالةٌ بلا
    سببٍ تجعل الجواب اجتهاداً. وهو اختياريٌّ في إعادة التفعيل.
    """

    reason: str | None = Field(default=None, max_length=255)


class DeactivationRequestIn(BaseModel):
    """طلبُ الكبتن إغلاقَ حسابه (البند ١٣) — والسببُ اختياريٌّ ونصٌّ حرّ.

    من يترك يقول لماذا إن شاء، ولا يُحبس خروجُه على قائمةٍ نختارها له.
    """

    reason: str | None = Field(default=None, max_length=300)


class DeactivationDecisionIn(BaseModel):
    """قرارُ المشرف — والرفضُ بسببٍ مكتوبٍ كرفض المستند."""

    approved: bool
    note: str | None = Field(default=None, max_length=300)


class DeactivationRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_id: uuid.UUID
    status: DeactivationStatus
    reason: str | None
    review_note: str | None
    resolved_at: datetime | None
    created_at: datetime


class DeactivationStateOut(BaseModel):
    """ما تحتاجه شاشةُ الكبتن في نداءٍ واحد.

    **والموانعُ قائمةٌ لا أوّلُ سبب**: من أُخبر بمانعٍ فأزاله ثم صُدم بثانٍ
    يقرأ الرفضَ مماطلة. **والمحتجَزُ يُقال برقمه** لا بجملةٍ عامة: من يرى
    رصيداً لا يستطيع سحبَه كلَّه يستحق أن يعرف كم منه ولماذا.
    """

    request: DeactivationRequestOut | None
    blockers: list[str]
    reserve_amount: Decimal
    currency: str


# --------------------------------------------------- سلفُ الكباتن (البند ١٥)


class AdvanceRequirementOut(BaseModel):
    """شرطٌ **باسمه ورقمه وحاله** — القرار ١ في شكله النهائي.

    لا «نقاطَ مصداقية»: من مُنع بسبب «مصداقيتك ٣٫٢» لا يعرف ماذا يفعل، ومن
    قرأ «رحلاتٌ مكتملة ٣١ من ٥٠» يعرف. **والنصُّ في التطبيق والرمزُ هنا**،
    كرموز موانع إلغاء التفعيل: الخلفيةُ لا تعرف من يقرأ.
    """

    key: str
    met: bool
    value: Decimal | None = None
    needed: Decimal | None = None


class AdvanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    driver_id: uuid.UUID
    amount: Decimal
    currency: str
    status: AdvanceStatus
    due_at: datetime
    settled_at: datetime | None
    created_at: datetime


class AdvanceDebtOut(BaseModel):
    """السلفةُ القائمة ومتبقّيها — **والمتبقّي محسوبٌ من الدفتر لا عمودٌ**."""

    advance: AdvanceOut
    remaining: Decimal
    overdue: bool


class AdvanceStateOut(BaseModel):
    """ما تحتاجه شاشةُ السلف في نداءٍ واحد.

    **و`offered=false` تعني «لا سلفَ في هذا السوق»** لا «رُفضتَ»: المفتاحُ
    مطفأٌ أو لا خطةَ يوميةً يُبنى عليها سقف. والفرقُ بينهما وبين شرطٍ لم
    يتحقق هو الفرقُ بين بابٍ غير موجودٍ وبابٍ يُفتح بعملٍ يقوم به.
    """

    offered: bool
    eligible: bool
    requirements: list[AdvanceRequirementOut]
    cap: Decimal
    currency: str
    debt: AdvanceDebtOut | None
    # شرطُ السداد — يُعرض قبل الموافقة لا بعدها
    deduction_percent: int = 0
    min_kept_amount: Decimal = Decimal("0.000")
    term_days: int = 0


class AdvanceRequestIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=3)


class AdminAdvanceIn(BaseModel):
    """صرفُ مشرفٍ سلفةً — **الطريقُ الوحيد لما يتجاوز السقف** (القرار ٢)."""

    driver_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=3)


class AdvanceWriteOffIn(BaseModel):
    """شطبٌ بقرارٍ إداريٍّ مسجَّل (القرار ٧) — والسببُ مطلوبٌ لا اختياري.

    خسارةٌ تُعترف بها بلا اسمٍ ولا سببٍ خسارةٌ لا يملكها أحد.
    """

    reason: str = Field(min_length=3, max_length=300)


class AdvanceCapIn(BaseModel):
    """سقفُ كبتنٍ بعينه — **`null` لا تخصيص، وصفرٌ منعٌ من السلف**."""

    cap: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    reason: str = Field(min_length=3, max_length=300)


class AdminAdvanceOut(AdvanceOut):
    """صفُّ اللوحة: السلفةُ ومتبقّيها وهل تجاوزت مهلتها، **ومعها صاحبُها**.

    **والمتبقّي يُحسب في الخلفية** كبقية المجاميع (`services/stats.py`): طرحٌ
    في المتصفح على صفحةٍ محدودةٍ رقمٌ يخالف القاعدة.

    **والاسمُ والرقمُ يُنشران كما ينشرهما `AdminDebtOut`** (أُضيفا 2026-09-02):
    كان الصفُّ يحمل `driver_id` وحدَه **فكانت اللوحةُ تعرض ثماني خاناتٍ من
    UUID** في عمودٍ عنوانُه «الكبتن» — ومشرفٌ يقرأ `3f2a91b8` لا يعرف من هو،
    فيفتح قائمةً أخرى ليترجمه. **وبابان ينشران الشيءَ نفسَه ويفترقان** هو
    الشكلُ الثامن بعينه: الدَّينُ يحمل الاسم والسلفةُ لا تحمله، وهما صفّان عن
    الكبتن نفسِه في الشاشة نفسِها.
    """

    driver_name: str
    driver_phone: str | None
    remaining: Decimal
    overdue: bool


class AdvanceSettingOut(BaseModel):
    """سياسةُ السلف لدولة (البند ١٥)."""

    model_config = ConfigDict(from_attributes=True)

    country_code: CountryCode
    deduction_percent: int
    min_kept_amount: Decimal
    term_days: int
    min_completed_rides: int
    min_rating: Decimal
    growth_percent_per_repaid: int
    max_multiplier_percent: int


class AdvanceSettingUpdate(BaseModel):
    """**ولا حقلَ لقيمة السلفة**: أساسُ السقف سعرُ الخطة اليومية نفسُه."""

    deduction_percent: int | None = Field(default=None, gt=0, le=100)
    min_kept_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    term_days: int | None = Field(default=None, gt=0, le=365)
    min_completed_rides: int | None = Field(default=None, ge=0)
    min_rating: Decimal | None = Field(default=None, ge=0, le=5, max_digits=3, decimal_places=2)
    growth_percent_per_repaid: int | None = Field(default=None, ge=0, le=500)
    max_multiplier_percent: int | None = Field(default=None, ge=100, le=1000)

class PresenceTokenOut(BaseModel):
    """رمزُ الحضور — **قيمةٌ لبابٍ واحد، لا جلسة** (§23.4).

    **ولا يُسجَّل ولا يُطبع**: هو ما تحمله الخدمةُ الأمامية في ترويسة
    `X-Presence-Token`. و`expires_in` تُنشر ليعرف العميلُ متى يطلب غيرَه،
    **لا ليحسب انتهاءَه بنفسه**: كلُّ استعمالٍ صحيحٍ يمدّده.
    """

    token: str
    expires_in: int
