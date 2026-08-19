from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy import inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user_role_grant import UserRoleGrant  # noqa: F401
from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, Gender, GenderPreference, UserRole

if TYPE_CHECKING:
    from app.models.driver import Driver


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # الهاتف هو مُعرّف الدخول — مخزّن بصيغة E.164
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), nullable=False, default=UserRole.RIDER
    )
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # تجميد المحفظة وحدها دون حظر الحساب (SPEC القسم 7/13.3): محفظة مشبوهة
    # تُوقَف حركتها بينما يبقى صاحبها قادراً على الركوب والدفع نقداً
    wallet_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # كلمة المرور هي طريقة الدخول **دائماً** (المرحلة 8-ب). تبقى nullable
    # لحساباتٍ أُنشئت قبل ذلك بـ OTP وحده، ولحسابٍ يُنشئه مسارٌ إداري ثم يضع
    # صاحبه كلمته — ولا يُفتح حسابٌ بلا كلمة مرور بكلمةٍ يخترعها أحد
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # لحظةُ إثبات ملكية الرقم (Firebase أو رمز SMS). **فارغة تعني رقماً غير
    # محقق**: يُنشأ الحساب هكذا فقط حين يُطفئ المشرف مفتاح
    # `otp_verification_enabled` للطوارئ، ويبقى موسوماً في اللوحة ويُطالَب
    # بالتحقق. ولا تُعتمد وثائق كبتنٍ قبل ملئها مهما كان المفتاح: رقمُ الكبتن
    # هو ما يستلم عليه حوالات كليك (SPEC القسم 6/9)
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def phone_verified(self) -> bool:
        return self.phone_verified_at is not None

    # إشعارات الحملات التسويقية وحدها (المرحلة 8). **لا أثر له على
    # المعاملاتي**: أحداث الرحلة وعرض الطلب وتنبيه الاشتراك جزءٌ من الخدمة
    # لا إعلان، فمن أطفأ الإعلانات لم يطفئ «وصل الكبتن». مفتوحٌ افتراضياً
    # وإطفاؤه بيد صاحبه من التطبيق
    marketing_push_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    # ---------------------------------------------------- الخدمة النسائية

    # جنسُ صاحب الحساب (المرحلة 10-ج). `NULL` = غير معلن، وهو الحال الطبيعي
    # لكل حسابٍ أُنشئ قبل الميزة. **تُعلنه الراكبة عن نفسها عند التسجيل**،
    # **ويضبطه المشرف للكبتن من هويته** — ولا يكتبه مسارُ تسجيل الكبتن أبداً
    gender: Mapped[Gender | None] = mapped_column(
        pg_enum(Gender, "gender"), nullable=True, index=True
    )
    # لحظةُ ختم المشرف على جنس الكبتن من الهوية. **المطابقةُ تقرأ المختوم
    # وحده** في جانب الكبتن: بغير هذا الشرط يصير الحقلُ ادّعاءً، ويصير
    # «سائقة للنساء» شيئاً يكتبه المرء عن نفسه. ويبقى فارغاً للركاب: إعلانُ
    # الراكبة يقيّد رحلتَها هي، فلا معنى لختمه
    # **رمزُ الإحالة — على الحساب لا على الكبتن** (تعميمُ 12-ح): الإحالةُ
    # علاقةٌ بين حسابين، والدورُ يقرّر **البرنامج** لا **الأهلية للرمز**.
    # وكان عموداً على `drivers`، فنُقل بترحيلةٍ **تحمل الرموز القائمة كما هي** —
    # كبتنٌ نشر رمزَه في مجموعةٍ لا يجوز أن يُبطل رمزُه بترحيلةٍ داخلية.
    #
    # **وفريدٌ عالمياً لا per-country**: الرمزُ يُقال في مكالمة، وواحدٌ في
    # الأردن يطابق واحداً في ليبيا هو رمزٌ يذهب لصاحب الحساب الخطأ.
    # و`nullable` لأن الحسابات القائمة قبل الترحيلة تأخذه فيها.
    referral_code: Mapped[str | None] = mapped_column(
        String(16), nullable=True, unique=True, index=True
    )

    gender_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # تفضيلُ الراكبة الافتراضي — يُنسخ إلى الرحلة عند الطلب ولا يُقرأ بعده
    # (نفس منطق `commission_percent_at_ride`): تغييرُ التفضيل يحكم ما يأتي
    # لا رحلةً جاريةً الآن
    ride_gender_preference: Mapped[GenderPreference] = mapped_column(
        pg_enum(GenderPreference, "gender_preference"),
        nullable=False,
        default=GenderPreference.ANY,
        server_default=GenderPreference.ANY.value,
    )
    # عددُ بلاغات «الطرف ليس بالجنس المعلَن» على هذا الحساب. عدّادٌ لا راية:
    # الوسمُ سؤالٌ عن العدد (`services/rides.GENDER_MISMATCH_FLAG_THRESHOLD`)،
    # فتغييرُ الحدّ لا يترك حساباتٍ موسومةً بحدٍّ قديم
    gender_mismatch_reports: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # **الأدوارُ تُحمَّل مع الحساب** (`selectin`): `deps` يقرؤها في كل طلب،
    # وتحميلٌ كسولٌ هناك يعني استعلاماً في كل نداءٍ أو `MissingGreenlet` خارج
    # السياق. و`role` العمودُ باقٍ للتوافق ويُقرأ منه **الدورُ الأساسي** وحدَه.
    role_grants: Mapped[list["UserRoleGrant"]] = relationship(
        "UserRoleGrant",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def roles(self) -> frozenset[UserRole]:
        """كلُّ ما يملكه من أدوار — **والعمودُ يُضمَّن حتى تُنقل كلُّ القراءات**.

        الترحيلةُ تنقل كلَّ حسابٍ بدوره، فالمجموعةُ والعمودُ متطابقان يومَها.
        وتضمينُ العمود يجعل صفّاً كُتب قبل الترحيلة أو في اختبارٍ قديم يظلّ
        مفهوماً بدل أن يصير بلا دورٍ أصلاً — وهو حارسٌ ضد الفقد لا مصدرٌ ثانٍ.
        """
        # **ولا IO هنا أبداً.** `role_grants` محمَّلةٌ مع كل استعلام
        # (`lazy="selectin"`)، فأيُّ حسابٍ جاء من القاعدة يحملها. والحالةُ
        # الوحيدةُ غيرُ المحمَّلة هي صفٌّ بُني في بايثون للتوّ — وهو لا يملك
        # منحاً غيرَ ما أُعطي في مُنشئه. وقراءةٌ كسولةٌ هنا تعني `MissingGreenlet`
        # في أيِّ مسارٍ يُنشئ حساباً ثم يسأل عن أدواره.
        state = inspect(self)
        granted = (
            ()
            if "role_grants" in state.unloaded
            else {grant.role for grant in self.role_grants}
        )
        return frozenset({self.role, *granted})

    @property
    def roles_list(self) -> list[UserRole]:
        """للتسلسل — **بترتيبٍ ثابت**: مجموعةٌ تُسلسَل بترتيبٍ يتبدّل بين طلبين
        تجعل كلَّ جوابٍ يبدو متغيّراً لمن يقارن."""
        return [role for role in UserRole if role in self.roles]

    def has_role(self, *roles: UserRole) -> bool:
        return bool(self.roles & frozenset(roles))

    driver: Mapped["Driver | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<User {self.phone} ({self.role})>"
