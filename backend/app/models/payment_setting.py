from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
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

# **عتباتُ المدفوعات غير المؤكَّدة — نصُّ `design/PAYMENTS-UNCONFIRMED.md` §٩**:
# عشرُ دقائق، ثمّ ساعتان، ثمّ اثنتا عشرة، ثمّ ثلاثٌ وعشرون — والرابعُ يسبق
# الحسمَ بساعة (§٣). والسقفُ عشرون ديناراً فوقها لا إتمامَ آليّ (§٢-٥)
DEFAULT_PAYMENT_REMINDER_MINUTES: tuple[int, ...] = (10, 120, 720, 1380)
DEFAULT_CASH_AUTO_CONFIRM_HOURS = 24
DEFAULT_CASH_AUTO_CONFIRM_MAX = Decimal("20.000")
DEFAULT_CLIQ_REFERENCE_MINUTES = 30
DEFAULT_DRIVER_UNCONFIRMED_BLOCK_COUNT = 3
DEFAULT_DRIVER_UNCONFIRMED_BLOCK_HOURS = 24
DEFAULT_RIDER_UNCONFIRMED_BLOCK_MINUTES = 30
DEFAULT_RIDER_UNPAID_RULINGS_CASH_OFF = 2
DEFAULT_RIDER_UNPAID_RULINGS_WINDOW_DAYS = 90
DEFAULT_DISPUTE_WINDOW_HOURS = 72
#: **وحدةُ التقريب الافتراضية** (SPEC §٧٠-أ/٦): «إلى أقرب نصف دينار» — والتقريبُ نفسُه مطفأٌ حتى يُشعَل
DEFAULT_ROUNDING_UNIT = Decimal("0.500")


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
        # **عتباتُ المدفوعات غير المؤكَّدة** (`design/PAYMENTS-UNCONFIRMED.md` §٩،
        # SPEC §٦٤-ج) — **موجبةٌ كلُّها**: صفرُ ساعاتٍ في الحجب يحجب كلَّ كبتنٍ
        # عليه دفعةٌ واحدة، وصفرٌ في المهلة إتمامٌ آليٌّ فوريّ — وهو أسوأُ ما يقع
        # بالسكوت (حجّةُ `cliq_confirmation_hours` نفسُها)
        CheckConstraint(
            "cash_auto_confirm_hours > 0 AND cash_auto_confirm_max_amount > 0 "
            "AND cliq_reference_minutes > 0 "
            "AND driver_unconfirmed_block_count > 0 AND driver_unconfirmed_block_hours > 0 "
            "AND rider_unconfirmed_block_minutes > 0 "
            "AND rider_unpaid_rulings_cash_off > 0 AND rider_unpaid_rulings_window_days > 0 "
            "AND dispute_window_hours > 0",
            name="payment_unconfirmed_thresholds_positive",
        ),
        # **أربعةُ مواعيدَ متصاعدة** — لكلِّ موعدٍ نصُّه (§٣)، فعددُها جزءٌ من
        # المعنى لا رقمٌ حرّ: الرابعُ هو «بعد ساعةٍ…» وليس بعده خامس
        CheckConstraint(
            "jsonb_typeof(payment_reminder_minutes) = 'array' "
            "AND jsonb_array_length(payment_reminder_minutes) = 4 "
            "AND (payment_reminder_minutes->>0)::int > 0 "
            "AND (payment_reminder_minutes->>0)::int < (payment_reminder_minutes->>1)::int "
            "AND (payment_reminder_minutes->>1)::int < (payment_reminder_minutes->>2)::int "
            "AND (payment_reminder_minutes->>2)::int < (payment_reminder_minutes->>3)::int",
            name="payment_reminder_minutes_valid",
        ),
        # **التقريب** (SPEC §٧٠-ج/٢، الترحيلة `0104`): وحدةٌ موجبةٌ — صفرٌ يقسم عليه الحسابُ — واتجاهٌ من ثلاثة
        CheckConstraint(
            "rounding_unit > 0 AND rounding_mode IN ('nearest', 'up', 'down')",
            name="payment_rounding_valid",
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

    # ------------------------------------- المدفوعاتُ غيرُ المؤكَّدة (§٦٤-ج)
    # `design/PAYMENTS-UNCONFIRMED.md` §٩ — **كلُّ رقمٍ من اللوحة لكلِّ سوق**
    # (المبدأ ٤)، والقيمُ الابتدائيةُ نصُّ التصميم. **ولا تعمل إلا والمفتاحُ
    # `unconfirmed_payments_enabled` مشتعلٌ لسوقها**.

    #: **مواعيدُ التذكير بالدقائق بعد نهاية الرحلة** (§٣) — أربعةٌ متصاعدة
    payment_reminder_minutes: Mapped[list[int]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: list(DEFAULT_PAYMENT_REMINDER_MINUTES),
        server_default=text("'[10, 120, 720, 1380]'::jsonb"),
    )
    #: **الإتمامُ الآليُّ للكاش بعد إقرار الراكب** (§٢-٥) — ساعاتٌ، وسقفٌ فوقه لا يُتمّ أبداً
    cash_auto_confirm_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_CASH_AUTO_CONFIRM_HOURS,
        server_default=text("24"),
    )
    cash_auto_confirm_max_amount: Mapped[Decimal] = mapped_column(
        MONEY,
        nullable=False,
        default=DEFAULT_CASH_AUTO_CONFIRM_MAX,
        server_default=text("20.000"),
    )
    #: **مهلةُ إدخال مرجع كليك قبل التذكير** (§٢-٤)
    cliq_reference_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_CLIQ_REFERENCE_MINUTES,
        server_default=text("30"),
    )
    #: **حجبُ العروض عن الكبتن** (§٧): عددُ ما ينتظره، أو عمرُ أقدمِه بالساعات
    driver_unconfirmed_block_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_DRIVER_UNCONFIRMED_BLOCK_COUNT,
        server_default=text("3"),
    )
    driver_unconfirmed_block_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_DRIVER_UNCONFIRMED_BLOCK_HOURS,
        server_default=text("24"),
    )
    #: **منعُ الطلب الجديد عن الراكب** (§٧) — دقائقُ بعد الرحلة بلا إقرارٍ ولا مرجع
    rider_unconfirmed_block_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_RIDER_UNCONFIRMED_BLOCK_MINUTES,
        server_default=text("30"),
    )
    #: **إطفاءُ قناة الكاش للراكب** (§٧): عددُ أحكام «لم يدفع» في نافذةٍ من الأيام
    rider_unpaid_rulings_cash_off: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_RIDER_UNPAID_RULINGS_CASH_OFF,
        server_default=text("2"),
    )
    rider_unpaid_rulings_window_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_RIDER_UNPAID_RULINGS_WINDOW_DAYS,
        server_default=text("90"),
    )
    #: **نافذةُ الاعتراض على إتمامٍ آليّ** (§٧) — ساعاتٌ، وتُجمَّد على الصفّ لحظةَ الإتمام
    dispute_window_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_DISPUTE_WINDOW_HOURS,
        server_default=text("72"),
    )

    # ------------------------------------- التقريب (SPEC §٧٠، الترحيلة `0104`)
    # **مطفأٌ في كلِّ سوقٍ بالترحيلة**: إشعالُ الأردن كتابةٌ على الإنتاج يُقرّها المالك (§٧٠-ب)، وليبيا لا يُمسّ صفُّها.
    # **والإعدادُ وحدَه يحكم** (`services/rounding.policy_for`): مطفأً لا يتغيّر مبلغٌ واحد عمّا كان.

    #: **أيُقرَّب ما يدفعه الناسُ ويقبضونه في هذا السوق؟**
    rounding_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    #: **وحدةُ التقريب** — نصفُ دينارٍ افتراضاً (`0.500`)، و`1.000` و`0.250` أمثلةُ المالك
    rounding_unit: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=DEFAULT_ROUNDING_UNIT, server_default=text("0.500")
    )
    #: **اتجاهُه** — `nearest` (نصفُه للأعلى) · `up` · `down` (`RoundingMode`)
    rounding_mode: Mapped[str] = mapped_column(
        String(8), nullable=False, default="nearest", server_default=text("'nearest'")
    )
    #: **لحظةُ آخرِ إشعال** — تُختم في اللوحة حين ينقلب المفتاحُ من مطفأٍ إلى مشتعل. **ومنها يُعرف ما قبلها**: قيدٌ أقدمُ منها
    #: لم يُقرَّب ولا يُقرَّب (§٧٠-أ/١١). و`null` لسوقٍ لم يُشعَل قطّ
    rounding_enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def tips_configured(self) -> bool:
        """هل ضُبطت مبالغُ البقشيش؟ صفرٌ في السقف يعني «لا» فتُخفى الميزة."""
        return self.tip_max > 0 and (
            self.tip_preset_small > 0 or self.tip_preset_medium > 0
        )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<PaymentSetting {self.country_code}>"
