"""دفعات الرحلة والبطاقات المحفوظة (SPEC القسم 4/6).

الدفعة صفٌّ لكل مبلغٍ يُحصَّل بقناة واحدة، لا صفٌّ لكل رحلة: **الدفع المختلط**
(القسم 6) رحلةٌ واحدة بصفّين — ما كفاه رصيد المحفظة، والباقي كاش. لذلك لا قيد
فريد على `ride_id`، وحارسُ «لا تُدفع الرحلة مرتين» مجموعُ الدفعات القائمة
مقابل `final_fare` في `services/payments.py` تحت قفل صف الرحلة.

المال لا يتحرك في الدفتر إلا عند `confirmed`، تماماً كما لا يتحرك في
`wallet_topup_requests` إلا عند التأكيد: دفعةٌ `pending` وعدٌ بالتحصيل لا أثر
مالي له.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    Currency,
    DisputeResolution,
    PaymentConfirmedBy,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)

if TYPE_CHECKING:
    from app.models.ride import Ride
    from app.models.user import User

# حالات تشغل مبلغاً من الرحلة: قائمةٌ تنتظر التحصيل أو محصَّلة فعلاً. ما عداها
# (`failed`، `refunded`) لا يحجز شيئاً، فيجوز فتح دفعة جديدة بقيمته.
OWING_PAYMENT_STATUSES: tuple[PaymentStatus, ...] = (
    PaymentStatus.PENDING,
    PaymentStatus.CONFIRMED,
    PaymentStatus.DISPUTED,
)

# قنوات يقبضها الكبتن بيده خارج المنصة (SPEC القسم 9): لا `ride_earning` لها
# في الدفتر لأن المال لم يمر بنا أصلاً — تدخل الكشوفات موسومةً «مُحصَّل مباشرة»
DIRECTLY_COLLECTED_METHODS: tuple[PaymentMethod, ...] = (
    PaymentMethod.CASH,
    PaymentMethod.CLIQ,
)

# القناة التي يخرج مالها **من رصيد الراكب** فيُقيَّد عليه `ride_payment`.
# ثلاث فئات لا فئتان: ما لا يمر بالمنصة (كاش وكليك)، وما يمر بها من المحفظة،
# وما يمر بها من غير المحفظة — **البطاقة**. مالُ البطاقة ينتقل من بطاقة الراكب
# إلى المزود مباشرة، فقيدُ خصمٍ على محفظته يخصم منه مرتين: مرةً على بطاقته
# ومرةً من رصيدٍ لم يمسّه أحد. الكبتن يُقيَّد له في الحالتين الأخيرتين
# (`ride_earning` — القسم 6.3)، فالفئة الثالثة تختلف في طرفٍ واحد لا في طرفين.
WALLET_FUNDED_METHODS: tuple[PaymentMethod, ...] = (PaymentMethod.WALLET,)


class Payment(UUIDMixin, TimestampMixin, Base):
    """دفعة واحدة على رحلة، بقناة واحدة."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="payment_amount_positive"),
        # حكمٌ بلا زمنٍ أو زمنٌ بلا حكم نصفُ فصلٍ في نزاع — والنصف لا يُقرأ
        CheckConstraint(
            "(resolution IS NULL) = (resolved_at IS NULL)",
            name="payment_resolution_complete",
        ),
        # فريد على مستوى الجدول لا لكل راكب: مفتاح الدفع يولّده العميل لعملية
        # بعينها. NULL لا يتعارض مع NULL في postgres، فما لا مفتاح له لا يقيَّد.
        UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        Index("ix_payments_ride_status", "ride_id", "status"),
    )

    ride_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    method: Mapped[PaymentMethod] = mapped_column(
        pg_enum(PaymentMethod, "payment_method"), nullable=False
    )
    # فارغ لما لا مزود خارجي له: الكاش وكليك اليدوي والمحفظة
    provider: Mapped[PaymentProvider | None] = mapped_column(
        pg_enum(PaymentProvider, "payment_provider"), nullable=True
    )
    provider_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # مشتقة من دولة الرحلة عبر `core/currency.py` — لا تُقبل من عميل أبداً
    currency: Mapped[Currency] = mapped_column(
        pg_enum(Currency, "currency"), nullable=False
    )

    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )
    confirmed_by: Mapped[PaymentConfirmedBy | None] = mapped_column(
        pg_enum(PaymentConfirmedBy, "payment_confirmed_by"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # مفتاح عدم التكرار الذي يفرضه القسم 14 على الدفع كما على التحويل: ضغطةٌ
    # مكررة أو webhook أُعيد إرساله لا يفتحان دفعةً ثانية على نفس الرحلة
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # القيد الناتج في دفتر المحفظة حين تُدفع الرحلة من الرصيد — الوصلة بين
    # الدفعة وأثرها المالي، كما في `wallet_topup_requests.transaction_id`
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("wallet_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # ------------------------------------------------------------- النزاع
    # الكبتن يضغط «لم يصلني» على دفعة كليك (القسم 6) فتصير `disputed` وتظهر
    # في لوحة الإدارة للفصل (القسم 13.4).
    dispute_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    disputed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution: Mapped[DisputeResolution | None] = mapped_column(
        pg_enum(DisputeResolution, "dispute_resolution"), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    ride: Mapped["Ride"] = relationship("Ride", foreign_keys=[ride_id])

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<Payment {self.method} {self.amount} ({self.status})>"


class SavedCard(UUIDMixin, TimestampMixin, Base):
    """بطاقة محفوظة للدفع بضغطة (SPEC القسم 6.4 — Tokenization).

    **لا رقم بطاقة هنا ولا CVV ولا أي بيانٍ يمكن أن يُدفع به.** المخزَّن رمزٌ
    (token) يصدره المزود ولا يعمل إلا لدى نفس المتجر، وما يكفي لعرض البطاقة
    للمستخدم: العلامة وآخر أربعة أرقام وتاريخ الانتهاء. هذا هو كل غرض
    الـ tokenization: أن يبقى رقم البطاقة عند المزود لا عندنا.

    الجدول يُنشأ الآن ويملؤه الكود في **المرحلة 6-ب** مع تكامل Telr: قيمةُ
    إنشائه مبكراً أن `payment_provider` وقيود الجدول تولد مع بقية مخطط الدفع
    في ترحيلة واحدة، لا أن يعدّلها لاحقاً تعديلُ ENUM على جدولٍ حيّ.
    """

    __tablename__ = "saved_cards"
    __table_args__ = (
        # نفس البطاقة لا تُحفظ مرتين لنفس المستخدم لدى نفس المزود
        UniqueConstraint("user_id", "provider", "provider_token"),
        CheckConstraint(
            "expiry_month BETWEEN 1 AND 12", name="saved_card_expiry_month_range"
        ),
        CheckConstraint("char_length(last4) = 4", name="saved_card_last4_length"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        # CASCADE بخلاف بقية الجداول المالية: الرمز المحفوظ ليس سجلاً محاسبياً
        # يُحتفظ به، بل بيانُ راحةٍ لا معنى له بعد ذهاب صاحبه
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        pg_enum(PaymentProvider, "payment_provider"),
        nullable=False,
        default=PaymentProvider.TELR,
    )
    provider_token: Mapped[str] = mapped_column(String(255), nullable=False)

    brand: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    expiry_month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    expiry_year: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<SavedCard ****{self.last4}>"
