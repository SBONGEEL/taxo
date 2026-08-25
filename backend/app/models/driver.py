from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    DocumentReviewStatus,
    DocumentType,
    DriverStatus,
    GenderPreference,
)

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.vehicle import Vehicle
    from app.models.vehicle_skin import VehicleSkin


class Driver(UUIDMixin, TimestampMixin, Base):
    """امتداد لـ users لحساب الكبتن."""

    __tablename__ = "drivers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[DriverStatus] = mapped_column(
        pg_enum(DriverStatus, "driver_status"),
        nullable=False,
        default=DriverStatus.PENDING,
        index=True,
    )
    cliq_alias: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rating_avg: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0.00")
    )
    is_online: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    # `use_alter`: بين الجدولين مرجع متبادل (rides.driver_id هنا وهناك)،
    # فيُنشأ هذا القيد بعد الجدولين لا معهما
    current_ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    # تفضيلُ الكبتن **دائم** لا لكل رحلة (المرحلة 10-ج): الراكبة تختار لرحلةٍ
    # بعينها، والكبتن يقرر لعمله كلِّه — ولذلك مكانُه هنا لا على الرحلة
    gender_preference: Mapped[GenderPreference] = mapped_column(
        pg_enum(GenderPreference, "gender_preference"),
        nullable=False,
        default=GenderPreference.ANY,
        server_default=GenderPreference.ANY.value,
    )

    # رمزُ الإحالة (المرحلة 12-ح). **فريدٌ عالمياً لا per-country**: الرمزُ
    # يُقال في مكالمة، وواحدٌ في الأردن يطابق واحداً في ليبيا هو رمزٌ يذهب
    # لصاحب الحساب الخطأ. ويُولَّد عند إنشاء الكبتن — لا عند أول فتحةٍ للشاشة:
    # توليدٌ عند القراءة يحتاج قفلاً على صفٍّ لا يُكتب فيه شيءٌ آخر، وبغيره
    # تُنتج ضغطتان رمزين. و`nullable` لأن القائمين قبل الترحيلة يأخذونه فيها
    # **التجديدُ التلقائي إذنٌ صريحٌ لا افتراض** (البند ١٤): مالٌ يخرج من محفظته
    # بلا ضغطةٍ منه يحتاج مفتاحاً يرفعه هو — والافتراضُ مطفأ، كبقيةِ ما يمسّ مالاً.
    auto_renew: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    # **سقفُ السلفة لهذا الكبتن وحدَه** (البند ١٥) — تكتبه الإدارةُ بسببٍ
    # مسجَّلٍ في التدقيق. و**`NULL` يعني «لا تخصيص»** فيُحسب سقفُه من السياسة،
    # **وصفرٌ يعني «ممنوعٌ من السلف»**: حالتان لا يجوز أن يحملهما رقمٌ واحد
    advance_cap_override: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    # **عمودٌ محضَّرٌ يقرؤه التوزيع** (البند ١٥): «موقوفٌ لدَينٍ تجاوز مهلته».
    # وموضعُه هنا لا استعلامٌ في `eligible_driver_ids` مقصود: تلك الدالةُ تُنادى
    # لكل طلبٍ ولخريطة كل راكب، وجمعُ دفترٍ داخلها يضع حساباً ماليّاً في المسار
    # الحرج. **ويُطفأ في مسار السداد نفسِه لا بدورةٍ تالية**: من سدَّد وبقي
    # ممنوعاً عشر دقائق يقرأ السدادَ بلا أثر
    # **المستوى: حاصلُ حسابٍ مادّيٍّ له كاتبٌ واحد** (البند ٥٣، §٣) — لا حكمٌ
    # مجمَّد. وسابقتُه هنا `rating_avg`: يُعاد بناؤه كاملاً من مصدره، ويُقرأ في
    # التوزيع بلا استعلام. والفرقُ بينه وبين `qualified_at` المرفوض ليس التخزينَ
    # بل **من يكتب ومتى**: هذا كاتبُه `tasks/levels.py` وحدَه ويُعاد بناؤه، وذاك
    # ختمٌ يُكتب مرةً ويبقى يحكم بمعيارٍ زال.
    #
    # **ولا يُحدَّث في مسار إنهاء الرحلة ولا في مسار التقييم** — كاتبٌ واحدٌ كما
    # لـ`current_leg` في 12-ب. و`level_computed_at` تجعل «متى حُسب؟» له جوابٌ
    # واحدٌ بدل تخمين
    # **نسبةُ العمولة السارية عليه الآن** — عمودٌ محضَّرٌ كـ`advance_blocked`
    # و`level`، يكتبه **شراءُ الاشتراك وحدَه** ومعه المهمّةُ التي تُنهي المنتهية.
    #
    # **ولمَ عمودٌ لا استعلام؟** §٥-ج يمنع استعلاماً إضافياً في مسار طلب الرحلة،
    # وقراءةُ «اشتراكِه السارِي» هناك ضمٌّ ثانٍ على كلِّ طلب. والسابقةُ قائمة:
    # `rating_avg` يُبنى من مصدره ويُقرأ في التوزيع بلا استعلام.
    #
    # **و`NULL` تعني «لا اشتراكَ ساري»** — فتُقرأ نسبةُ الدولة، وهي الحالُ
    # الطبيعيةُ لمن لم يشترِ بعد. وصفرٌ يعني **اشتراكاً اشتُري على صفر**، وهما
    # حالان لا يحملهما رقمٌ واحد (درسُ أصفار `wallet_settings`).
    commission_percent_from_subscription: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # **المركبةُ النشطةُ للحساب لا للسيارة** (قرارُ المالك 2026-08-22): كبتنٌ
    # يملك سيارتين يملك شكلاً واحداً يظهر مهما قاد اليوم. **و`SET NULL` لا
    # `RESTRICT`**: إخفاءُ مركبةٍ من المتجر لا يحذف صفَّها أصلاً، وحذفُها
    # ممنوعٌ بـ`RESTRICT` على المِلكيّة — فهذا المسارُ لا يقع إلا في تنظيفٍ
    # إداريٍّ لمركبةٍ لا مالكَ لها، وحينها **العلامةُ تعود إلى الباهتة**
    # لا يبقى الكبتنُ بإشارةٍ إلى صفٍّ غير موجود
    active_skin_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vehicle_skins.id", ondelete="SET NULL"),
        nullable=True,
    )

    level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default=text("0")
    )
    level_computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    advance_blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # **وعمودٌ ثانٍ بنفس الشكل ولدَينٍ آخر** (`CANCELLATION-FEE.md` §6-أ):
    # «قبض رسمَ إلغاءٍ نقداً لكبتنٍ آخر ولم يحوّله حتى انقضت مهلتُه». وهو
    # **ليس `advance_blocked`** وإن تشابها: دَينان لمُقرِضَين مختلفَين، وعمودٌ
    # واحدٌ يحملهما يجعل سدادَ أحدهما يرفع منعَ الآخر
    cancellation_carry_blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    user: Mapped["User"] = relationship(back_populates="driver")
    vehicles: Mapped[list["Vehicle"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    documents: Mapped[list["DriverDocument"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    # **`selectin` لا `joined`، وهذا قِيس لا رُئي** (2026-08-22): بطاقةُ الكبتن
    # التي يراها الراكب بعد القبول ترسم مركبتَه، و`RideOut.from_ride` بانٍ
    # **متزامن** فلا يستطيع استعلاماً — فلا بدّ من تحميلٍ مسبق.
    #
    # **و`joined` أسقط كلَّ قفلٍ على صفِّ الكبتن**: الضمُّ الخارجيُّ يجعل
    # `SELECT … FOR UPDATE` يفشل بـ«FOR UPDATE cannot be applied to the
    # nullable side of an outer join» — أي أن شراءَ الاشتراك ورفعَ المستند
    # وتعديلَ المركبة تسقط كلُّها. وقعت مقيسةً في أول تشغيل، ولا يراها بناءٌ
    # ولا نوع.
    #
    # **وثمنُ `selectin` ليس في مسار التوزيع**: `dispatch` لا يحمّل كائنَ
    # كبتنٍ داخل نافذة العرض — يقرأ أعمدةً (`Driver.id`, `Driver.level`) —
    # فلا استعلامَ زائدٌ حيث يمنعه §٥-ج.
    active_skin: Mapped["VehicleSkin | None"] = relationship(lazy="selectin")

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<Driver {self.id} ({self.status})>"


class DriverDocument(UUIDMixin, TimestampMixin, Base):
    """مستندات الكبتن: مسار الملف + حالة مراجعة مستقلة لكل مستند.

    **صفٌّ واحد لكل نوع** يفرضه الفريد `(driver_id, doc_type)`: رفعُ نفس
    النوع مرةً أخرى **يستبدل** سابقه ويعود `pending`. البديل — تراكمُ صفوفٍ
    لنفس النوع — يجعل سؤال «هل رخصتُه مقبولة؟» بلا جواب واحد، ويجعل شاشة
    المراجعة تعرض ثلاث رخصٍ لا يُعرف أيُّها السارية. ورفعُ بديلٍ عن مستندٍ
    مرفوض هو الحالة المقصودة أصلاً.

    ولا يُلغي الاستبدالُ اعتمادَ الكبتن: تغييرُ حالته يمر من
    `services/drivers.set_status` وحدها (SPEC القسم 13/2)، والمستند الجديد
    يظهر `pending` في اللوحة لتراه المراجعة.
    """

    __tablename__ = "driver_documents"
    __table_args__ = (
        UniqueConstraint(
            "driver_id", "doc_type", name="uq_driver_documents_driver_doc_type"
        ),
        # **يُصرَّح في النموذج كما هو في الترحيلة** — وإلا رآه `autogenerate`
        # فهرساً زائداً واقترح حذفَه، **و`test_migrations_match_models` يمسك
        # ذلك بالضبط** (وقد أمسكه اليوم).
        Index(
            "ix_driver_documents_expires_on",
            "expires_on",
            postgresql_where=text("expires_on IS NOT NULL"),
        ),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[DocumentType] = mapped_column(
        pg_enum(DocumentType, "document_type"), nullable=False
    )
    # مسارٌ **نسبي** إلى `settings.document_storage_root` — انظر
    # `core/storage.py`. لا يُعرض لأحد ولا يُبنى منه رابط: الملف يُقرأ من
    # مسارٍ يتحقق من الملكية أولاً
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    # نوع المحتوى **المستنتج من بايتات الملف** لا المُعلن من العميل — به
    # تُخدَم القراءة بلا استنتاجٍ ثانٍ في كل طلب
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    review_status: Mapped[DocumentReviewStatus] = mapped_column(
        pg_enum(DocumentReviewStatus, "document_review_status"),
        nullable=False,
        default=DocumentReviewStatus.PENDING,
    )
    # **تاريخُ انتهاء الصلاحية — يومٌ لا لحظة** (البند ب).
    #
    # `Date` لا `DateTime` لأن الصلاحيةَ مطبوعةٌ على البطاقة بيومٍ لا بساعة،
    # وتخزينُها لحظةً يجعل «أانتهت اليوم؟» جواباً يختلف بين عمّان وطرابلس على
    # الصفِّ نفسِه.
    #
    # **والفراغُ يعني «لا تاريخَ لهذا النوع»** — صورةُ المركبة لا تنتهي —
    # **لا «تاريخٌ نُسي»**. وكلُّ ما يقرؤه يتجاهل الفارغَ صراحةً، فلا يُعلَّق
    # حسابٌ لأن حقلاً لم يُملأ.
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # **من كتبه آخِراً**: `driver` أو `admin`. فتصحيحُ المشرف لا يُقرأ إقراراً
    # من الكبتن، ولا إقرارُ الكبتن يُقرأ تحقّقاً من المشرف.
    expiry_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    driver: Mapped["Driver"] = relationship(back_populates="documents")

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<DriverDocument {self.doc_type} ({self.review_status})>"


# المستندات التي لا يُعتمد كبتنٌ قبل قبولها كلها (SPEC القسم 12/1 و13/2).
#
# **وثلاثٌ من صور المركبة الستّ داخلها** (البند ١١، قرارُ المالك 2026-08-14):
# الأمام والخلف واللوحة — «الثلاثةُ تكفي للتحقق، والباقي يزيد الثقة ولا يمنع
# كبتناً من العمل». فالجانبان والداخل يُرفعان ويُراجَعان ولا يحبسان اعتماداً.
#
# **والاستبدالُ يُسقط الاعتماد لهذه الستّ كما لغيرها** (قاعدةُ 9-ب): ما دام
# النوعُ مطلوباً فتبديلُ ما يشهد عليه يعيده إلى المراجعة — ومن بدّل لوحتَه
# بصورةِ لوحةٍ أخرى بدّل ما اعتُمد عليه.
REQUIRED_DOCUMENT_TYPES: tuple[DocumentType, ...] = (
    DocumentType.DRIVING_LICENSE,
    DocumentType.NATIONAL_ID,
    DocumentType.VEHICLE_REGISTRATION,
    DocumentType.VEHICLE_FRONT,
    DocumentType.VEHICLE_BACK,
    DocumentType.VEHICLE_PLATE,
)

def required_document_types(
    *, gender_verified_female: bool
) -> tuple[DocumentType, ...]:
    """المستنداتُ المطلوبةُ **لهذا الكبتن بعينه** — لا جدولٌ ثابتٌ للجميع.

    **والصورةُ الشخصية هي سببُ وجود هذه الدالة** (البند ٥٢): شرطٌ على الجميع
    **إلا على من ثبَّتت الإدارةُ جنسَها أنثى** — فنشرُ وجه امرأةٍ على كل من
    يطلب رحلةً كلفةٌ أمنيةٌ لا يقابلها في حالتها ما يقابلها في حاله، وهي
    الكلفةُ نفسُها التي بُنيت الخدمةُ النسائية (10-ج) لأجلها.

    **والاستثناءُ يقرأ الوسمَ لا الإقرار** (`gender_verified_at IS NOT NULL`):
    الإقرارُ يقيّد رحلةَ صاحبته وحدها فيكفيه أن يُكتب، وهذا **يُسقط شرطاً** —
    فلو قُرئ `users.gender` وحدَه لسقط شرطُ التعرّف بكلمةٍ يكتبها أيُّ أحدٍ عن
    نفسه. وهي قراءةُ التوفيق في 10-ج ومكافأةِ الإحالة في 12-ح نفسُها.

    **ولا تُقرأ هذه الدالةُ بأثرٍ رجعيّ** (قرارُ المالك 2026-08-16): الشرطُ
    يسري على **من يُعتمد بعده**، ومن اعتُمد قبله يصير متراكماً يُلاحَق واحداً
    واحداً من شاشة السائقين — لأن `drivers.approve` لا تُنادى إلا عند اعتمادٍ
    جديد. وإسقاطُ اعتمادِ من يعمل اليوم بشرطٍ أُضيف اليوم يوقف سوقاً بأكمله
    لأجل صورة.
    """
    if gender_verified_female:
        return REQUIRED_DOCUMENT_TYPES
    return (*REQUIRED_DOCUMENT_TYPES, DocumentType.PROFILE_PHOTO)


# صورُ المركبة كلُّها — ما يعرضه التطبيق في قسمٍ واحد، بترتيب العرض.
# **والاختياريُّ منها ليس أقلَّ مراجعةً**: يُقبل أو يُرفض كغيره، ولا يحبس
# اعتماداً — فرقُهما في `REQUIRED_DOCUMENT_TYPES` وحدَه
VEHICLE_PHOTO_TYPES: tuple[DocumentType, ...] = (
    DocumentType.VEHICLE_FRONT,
    DocumentType.VEHICLE_BACK,
    DocumentType.VEHICLE_SIDE_RIGHT,
    DocumentType.VEHICLE_SIDE_LEFT,
    DocumentType.VEHICLE_INTERIOR,
    DocumentType.VEHICLE_PLATE,
)
