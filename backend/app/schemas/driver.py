from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import (
    CountryCode,
    DocumentReviewStatus,
    DocumentType,
    DriverStatus,
    Gender,
    GenderPreference,
    VehicleCategory,
)
from app.schemas.auth import UserOut


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

    @model_validator(mode="after")
    def _note_required_on_reject(self) -> "DocumentReviewIn":
        if not self.approved and not (self.note or "").strip():
            raise ValueError("سبب الرفض مطلوب")
        return self


class DriverDocumentsOut(BaseModel):
    """مستندات كبتنٍ ومعها ما ينقصه للاعتماد — سؤالٌ واحد بجوابٍ واحد."""

    documents: list[DriverDocumentOut]
    missing_required: list[DocumentType]


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
    is_online: bool
    current_ride_id: uuid.UUID | None
    created_at: datetime


class DriverProfileOut(BaseModel):
    driver: DriverOut
    user: UserOut
    vehicles: list[VehicleOut]
    documents: list[DriverDocumentOut]


class DriverGenderUpdate(BaseModel):
    """جنسُ الكبتن كما يقرؤه المشرف من هويته المرفوعة (المرحلة 10-ج).

    مسارٌ إداريٌّ مستقل لا حقلٌ في `DriverUpdate`، لأن الكاتب مختلف: هذا يكتبه
    المشرف عن غيره وله قيدُ تدقيق، وذاك يكتبه صاحبه عن نفسه. وضبطُه **لا يعيد
    دورة اعتماد**: الهوية مرفوعةٌ ومراجَعةٌ أصلاً، وإرجاعُ كبتنٍ معتمدٍ إلى
    الطابور لأجل حقلٍ واحد يجعل تفريغ المتراكم مستحيلاً عملياً.
    """

    gender: Gender


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


class DriverLocationIn(BaseModel):
    """بثّ موقع واحد من تطبيق الكبتن (SPEC القسم 10)."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    # اتجاه السير بالدرجات — تدور به أيقونة السيارة على خريطة الراكب
    heading: float | None = Field(default=None, ge=0, lt=360)


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
    created_at: datetime


class DriverStatusUpdate(BaseModel):
    """إيقافُ كبتنٍ أو إعادةُ تفعيله — بسببٍ يدخل سجل التدقيق.

    السببُ إلزاميٌّ في الإيقاف: «لماذا أُوقف؟» سؤالٌ يُسأل بعد شهر، وحالةٌ بلا
    سببٍ تجعل الجواب اجتهاداً. وهو اختياريٌّ في إعادة التفعيل.
    """

    reason: str | None = Field(default=None, max_length=255)
