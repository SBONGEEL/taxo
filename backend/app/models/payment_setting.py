from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

# ما يبدأ به صفُّ دولةٍ جديد. ليس افتراضاً سخياً كأصفار `wallet_settings`:
# الصفر هنا يعني «لا مهلة» أي نزاعٌ فوري، وهو أسوأ ما يمكن أن يقع بالسكوت.
DEFAULT_CLIQ_CONFIRMATION_HOURS = 24

# **أصفارٌ كأصفار `wallet_settings` لا كمهلة كليك**: البقشيش ميزةٌ تُفتح لا
# حارسٌ يُطفأ، والصفرُ فيها يعني «لم يُضبط» فتُخفى الأزرارُ كلُّها — لا
# «بقشيشاً مقداره صفر». وقيمُ الدولتين يكتبها البذرُ ويعدّلها المشرف
# (SPEC القسم 6.5).
DEFAULT_TIP_PRESET = Decimal("0")
DEFAULT_TIP_MAX = Decimal("0")


class PaymentSetting(UUIDMixin, TimestampMixin, Base):
    """سياساتُ الدفع لكل دولة — تُدار من اللوحة (SPEC القسم 6.2/13.6).

    اليوم حقلٌ واحد: **مهلةُ تأكيد حوالة كليك**. القسم 6.2/6 يقول «عند الرفض
    أو انقضاء مهلة التأكيد → `disputed`»، والرقمُ سياسةٌ لا قاعدة: مهلةٌ قصيرة
    تفتح نزاعاً على كبتنٍ نائم، وطويلةٌ تترك مال الراكب معلّقاً — ويختلف
    المناسبُ بين سوقٍ وسوق، فمكانُه جدولُ إعداداتٍ لا ثابتٌ في الكود.

    وهو **جدولٌ مستقل عن `wallet_settings`** لأنه ليس حدَّ محفظة: خلطُ
    السياستين في جدولٍ واحد يجعل اسمَه لا يصف محتواه، ويجرّ كلَّ سياسة دفعٍ
    قادمة إلى جدول المحفظة.
    """

    __tablename__ = "payment_settings"
    __table_args__ = (
        CheckConstraint(
            "cliq_confirmation_hours > 0",
            name="payment_cliq_confirmation_positive",
        ),
        # لا مبالغَ سالبة، والسقفُ حارسٌ في القاعدة أيضاً: مبلغٌ يمرّ من طبقةٍ
        # عليا لا يجوز أن يجد الجدولَ مفتوحاً بعدها (نفس منهج قيود الدفتر)
        CheckConstraint(
            "tip_preset_small >= 0 AND tip_preset_medium >= 0 AND tip_max >= 0",
            name="payment_tip_amounts_not_negative",
        ),
        # **قيدُ `0059` كان في الترحيلة ولم يكن في النموذج** (صُحِّح
        # 2026-08-30): `test_migrations_match_models` يقرأ الفرقَ انحرافاً،
        # **ولم تُشغَّل عليه المجموعةُ يومَ كُتب**.
        CheckConstraint(
            "cliq_review_min_minutes > 0 "
            "AND cliq_review_max_minutes >= cliq_review_min_minutes",
            name="payment_cliq_review_window",
        ),
        # **و`NULL` مسموحة**: «لا سقفَ» حالٌ لا رقمٌ — والقيدُ يحرس الموجبَ وحده
        CheckConstraint(
            "driver_debt_ceiling IS NULL OR driver_debt_ceiling > 0",
            name="payment_debt_ceiling_positive",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, unique=True, index=True
    )
    #: **حسابُ كليك المستقبِل لهذا السوق** — يُضبط من اللوحة (قرارُ المالك
    #: 2026-08-29). **و`None` تعني «لم يُضبط» فتُخفى القناةُ كلُّها**: شاشةٌ
    #: تطلب تحويلاً ولا تقول إلى أين تُنتج حوالةً ضائعة، وذاك أسوأُ من غياب
    #: القناة. **ولكلِّ سوقٍ حسابُه** — كليكُ أردنيّ، وليبيا شيءٌ آخرُ أو لا شيء.
    cliq_alias: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: **صورةُ رمز كليك لهذا السوق** — يرفعها المالكُ من اللوحة.
    #: **ولا تُولَّد من الـalias**: رمزُ كليك يصدره القابضُ بحقوله المعيارية
    #: (قِيس 2026-08-29)، **وباركودٌ لا يعمل أسوأُ من غيابه**.
    cliq_qr_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    #: **مدّةُ المراجعة الموعودة** — «خلال ٣ إلى ٥ دقائق». **وعدٌ لمن يدفع**،
    #: فيُعدَّل من اللوحة يومَ تكثر الطلباتُ ولا تلحق المراجعة — **بلا نشر**.
    cliq_review_min_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("3")
    )
    cliq_review_max_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("5")
    )

    #: **سقفُ دَينِ الكبتن** — فوقه يُمنع من استقبال الطلبات (الترحيلة `0061`).
    #:
    #: **و`None` تعني «لا سقف» لا «صفراً»** (قرارُ المالك 2026-08-30: «ولا
    #: تضعه حتى أقرّه»). **والفرقُ ماليٌّ لا شكليّ**: صفرٌ يحجب كلَّ كبتنٍ
    #: عليه فلسٌ واحد — فالمسارُ مبنيٌّ كاملاً و**معطَّلٌ حتى يُكتب الرقم**.
    driver_debt_ceiling: Mapped[Decimal | None] = mapped_column(
        MONEY, nullable=True
    )

    cliq_confirmation_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_CLIQ_CONFIRMATION_HOURS
    )

    # مبلغا زرَّي البقشيش وسقفُه (المرحلة 12-و). **per-country** لأن نصفَ
    # دينارٍ أردنيٍّ ليس نصفَ دينارٍ ليبيّ، ورقمٌ مكتوبٌ في التطبيق يخالف
    # السوقَ الآخر يومَ إطلاقه
    tip_preset_small: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, server_default=text("0"), default=DEFAULT_TIP_PRESET
    )
    tip_preset_medium: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, server_default=text("0"), default=DEFAULT_TIP_PRESET
    )
    # سقفٌ يحرس من إصبعٍ تزلّ على شاشةٍ في سيارة — وصفرُه يعني «لم يُضبط»
    tip_max: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, server_default=text("0"), default=DEFAULT_TIP_MAX
    )

    @property
    def tips_configured(self) -> bool:
        """هل ضُبطت مبالغُ البقشيش؟ صفرٌ في السقف يعني «لا» فتُخفى الميزة."""
        return self.tip_max > 0 and (
            self.tip_preset_small > 0 or self.tip_preset_medium > 0
        )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<PaymentSetting {self.country_code}>"
