"""رسمُ الإلغاء بعد القبول — الجدولُ وإعداداتُه (`design/CANCELLATION-FEE.md`).

**وهو أولُ دَينٍ يقع بين مستخدمَين في هذا النظام.** السلفةُ (البند ١٥) دَينٌ
للمنصّة على كبتن، وهذا **مالُ كبتنٍ عند راكب** والمنصّةُ تنقله ولا تملكه — ومن
هذا الفرق تُشتقّ كلُّ قاعدةٍ هنا: طرفان بالاسم في الصف، وقيدان في الدفتر لا
قيدٌ واحدٌ صافٍ، ومبلغٌ **لا يدخل الرصيدَ المتاح قبل أن يصل**.

**والعطبُ الذي يُصلَح بهذا الملف**: كان `rides.cancellation_fee` يُحسب ويُجمَّد
ويُعرض للراكب — **ولا يُحصَّل أبداً**. لا صفَّ دفعةٍ، ولا قيدَ في دفترٍ، ولا
شيءَ لمن تحرّك. رقمٌ على شاشةٍ يقول للراكب إنه مدينٌ **بلا بابٍ يدفع منه**،
ولكبتنٍ أنه استحقّ **بلا مالٍ يصله**.

أربعُ قواعدَ في شكل الجدول، كلُّها من قراراتٍ مكتوبة:

* **`payer_user_id` و`beneficiary_driver_id` صريحان**: المالُ يمرّ بين طرفين
  مسمَّيين، وجدولٌ يعرف الرحلةَ وحدَها يُجيب «كم» ولا يُجيب «لمن».
* **لا عمودَ «متبقٍّ»**: المبلغُ كاملٌ أو مسدَّد، ولا سدادَ جزئيّ — قرارُ
  المالك في الفرع (د). وعمودٌ كهذا يفتح سؤالاً ثالثاً في كل شاشة.
* **`amount` و`currency` مجمَّدان لحظةَ الإلغاء** كـ`commission_percent_at_ride`:
  إدارةٌ تعدّل التسعيرةَ غداً لا تُغيّر ديناً وقع أمس.
* **والتسويةُ كلٌّ أو لا شيء**: `settled_at` و`collected_from_ride_id` (أو
  `waived_by`+`waive_reason`) تُكتب معاً أو لا تُكتب — قيدُ CHECK، كشطبِ
  السلفة. فصفٌّ «مسدَّد» بلا أثرٍ يقول أين ذهب المال هو ما لا يُصدَّق لاحقاً.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    CancellationChargeStatus,
    CountryCode,
    Currency,
    UnpaidCancellationOutcome,
)

# **مسافةُ الإعفاء الافتراضية بالأمتار**: كبتنٌ لم يبرح مكانَه لم يُتعِب أحداً.
# ٣٠٠ متراً هامشُ خطأِ GPS في المدينة تقريباً، فما دونها «لم يتحرك» عملياً.
# وهي حقلٌ في اللوحة لا ثابتٌ في الكود
DEFAULT_EXEMPT_WITHIN_METERS = 300

# **عددُ الإلغاءات غير المسدَّدة قبل إيقاف الطلب** — صفرٌ يعني «لا إيقاف»،
# كأصفار `wallet_settings`: «لم يُضبط بعد» لا «أوقفه من أول مرة»
DEFAULT_BLOCK_AFTER_UNPAID = 0

# **مدةُ الانتظار قبل إجراءٍ على دَينٍ لم يعد صاحبُه** (القسم ١٠) — وصفرُها
# «لا إجراء»، وهو الافتراضُ حتى يضبطها المالك كبقية الإعدادات المالية
DEFAULT_UNPAID_AFTER_DAYS = 0


class CancellationSetting(TimestampMixin, Base):
    """سياسةُ رسم الإلغاء لدولةٍ واحدة — **والقيمةُ نفسُها ليست هنا**.

    مبلغُ الرسم يبقى في `pricing_rules.cancellation_fee` حيث كان: هو رقمٌ
    **لكل فئةِ مركبة** (سيارةٌ عاديةٌ ليست كسيارةٍ فاخرة)، ونقلُه إلى هنا
    يجعله رقماً واحداً لدولةٍ فيُفقد ما يميّزه. وما هنا هو **متى يُستحقّ ومتى
    يُعفى وماذا يقع إن لم يُسدَّد** — سياسةٌ لا سعر.
    """

    __tablename__ = "cancellation_settings"

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), primary_key=True
    )

    # الإعفاءُ بالقرب (القسم ٣): يُقاس من **آخر موقعٍ مبثوث** لا من موقعه
    # لحظةَ القبول — من قَبِل بعيداً ثم قطع نصفَ الطريق تحرّك فعلاً
    exempt_within_meters: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_EXEMPT_WITHIN_METERS))
    )
    # **بلا موقعٍ مبثوث يُعفى الراكب** (قرارُ المالك، الفرع أ): لا دليلَ على
    # تحرّك، والشكُّ لمن سيُخصم منه — ومن تحرّك فعلاً يعترض في اللوحة.
    # وهو مكتوبٌ حقلاً لا سلوكاً مدفوناً كي يُقرأ ويُراجَع
    exempt_when_location_unknown: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("true")
    )

    # التكرار (القسم ٤): كم ديناً قائماً قبل أن يُمنع من الطلب
    block_after_unpaid: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_BLOCK_AFTER_UNPAID))
    )

    # حين لا يعود الراكبُ أبداً (القسم ١٠) — **الإدارةُ تقرّر، لا الكود**
    unpaid_after_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_UNPAID_AFTER_DAYS))
    )
    unpaid_outcome: Mapped[UnpaidCancellationOutcome] = mapped_column(
        pg_enum(UnpaidCancellationOutcome, "unpaid_cancellation_outcome"),
        nullable=False,
        server_default=UnpaidCancellationOutcome.KEEP_PENDING.value,
    )


class RideCancellationCharge(UUIDMixin, TimestampMixin, Base):
    """رسمُ إلغاءٍ واحد: مَن يدفعه، ومَن يقبضه، وهل وصل.

    **صفٌّ واحدٌ لكل رحلة**: قيدٌ فريدٌ على `ride_id` — الرحلةُ تُلغى مرةً،
    وصفّان عليها يعنيان تحصيلَ الرسم مرتين. وهو حارسُ المال هنا، إذ يمرّ
    الإنشاءُ بمسارٍ واحدٍ يمكن أن يُطلب مرتين معاً.
    """

    __tablename__ = "ride_cancellation_charges"
    __table_args__ = (
        Index("uq_cancellation_charge_ride", "ride_id", unique=True),
        # المسدَّدُ يحمل أثرَه، والمعفوُّ يحمل سببَه — أو لا يُكتب أيُّهما
        CheckConstraint(
            "(status <> 'settled') OR settled_at IS NOT NULL",
            name="cancellation_settled_needs_time",
        ),
        CheckConstraint(
            "(status <> 'waived') OR "
            "(waived_by_user_id IS NOT NULL AND waive_reason IS NOT NULL "
            "AND settled_at IS NOT NULL)",
            # **والاسمُ قصيرٌ عمداً**: Postgres يقصّ ما تجاوز ٦٣ محرفاً ويضيف
            # هشّاً، فيختلف اسمُ القيد في القاعدة عن اسمِه في النموذج —
            # و`test_migrations_match_models` يقرأ ذلك انحرافاً في كل تشغيل
            name="cancellation_waive_needs_actor",
        ),
        # مؤشّرُ «ما عليه من دَين» — سؤالُ مسارِ الطلب في كل رحلة
        Index(
            "ix_cancellation_charge_payer_pending",
            "payer_user_id",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
    )
    # الطرفان بالاسم: المالُ يمرّ بينهما، والمنصّةُ ناقلٌ لا طرف
    payer_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    beneficiary_driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[Currency] = mapped_column(
        pg_enum(Currency, "currency"), nullable=False
    )

    status: Mapped[CancellationChargeStatus] = mapped_column(
        pg_enum(CancellationChargeStatus, "cancellation_charge_status"),
        nullable=False,
        server_default=CancellationChargeStatus.PENDING.value,
        index=True,
    )

    # الرحلةُ التي سُدِّد معها — فارغٌ في الخصم الفوري من المحفظة
    collected_from_ride_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rides.id", ondelete="SET NULL"), nullable=True
    )
    # الكبتنُ الحاملُ في حالة الكاش (القسم ٦-أ): قبض بيده ما ليس كلُّه له
    carrier_driver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )

    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    waived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    waive_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
