"""دفتر المحفظة وطلبات الشحن والسحب (SPEC القسم 4/7/9).

**لا عمود رصيد في أي مكان.** الرصيد = مجموع `amount` لقيود المالك، و
`balance_after` لقطةٌ للتدقيق وقت القيد لا مصدرٌ يُقرأ منه. الدفتر غير قابل
للتعديل: ترحيلة `0006` تضع مُشغّلاً في القاعدة يرفض أي UPDATE أو DELETE عليه،
فالتصحيح يكون بقيد `adjustment` مضاد لا بمحو التاريخ.

`owner_id` يشير إلى `users.id` للراكب والكبتن معاً، و`owner_type` هو ما يميّز
المحفظتين. لذلك رصيد الكبتن يُستعلم بـ `driver.user_id` لا `driver.id` —
بخلاف `withdrawal_requests.driver_id` الذي يشير إلى `drivers` كما ينص القسم 4.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    TopupMethod,
    TopupRequestStatus,
    WalletOwnerType,
    WalletTransactionType,
    WithdrawalMethod,
    WithdrawalStatus,
)

if TYPE_CHECKING:
    from app.models.user import User

# إشارة المبلغ يحددها نوع القيد لا المستدعي: قيدٌ بإشارة مقلوبة يزيد الرصيد
# حيث يجب أن ينقصه، وهو خطأ لا يظهر إلا في المطابقة المالية بعد أشهر.
CREDIT_TYPES: tuple[WalletTransactionType, ...] = (
    WalletTransactionType.TOPUP,
    WalletTransactionType.RIDE_EARNING,
    WalletTransactionType.TRANSFER_IN,
    WalletTransactionType.REFUND,
    WalletTransactionType.TIP,
    # حافزُ الإحالة (12-ح): دائنٌ وحده — لا صفَّ مدينٍ يقابله، فالشركةُ تتحمّله
    WalletTransactionType.REFERRAL_BONUS,
    # صرفُ السلفة (البند ١٥): مالٌ يدخل محفظتَه فعلاً — ولذلك هو دائنٌ عاديّ،
    # والدَّينُ مقابلَه ليس في هذا الدفتر بل في جدوله
    WalletTransactionType.ADVANCE,
    # تعويضُ الإلغاء: دائنٌ للمتضرر — ومدينُه على **الراكب** لا على المنصّة،
    # فهما قيدان في دفترين لا قيدٌ من العدم كحافز الإحالة
    WalletTransactionType.CANCELLATION_COMPENSATION,
)

DEBIT_TYPES: tuple[WalletTransactionType, ...] = (
    WalletTransactionType.RIDE_PAYMENT,
    WalletTransactionType.COMMISSION,
    WalletTransactionType.TRANSFER_OUT,
    WalletTransactionType.WITHDRAWAL,
    WalletTransactionType.SUBSCRIPTION_PAYMENT,
    WalletTransactionType.TIP_PAYMENT,
    # اقتطاعُ السلفة: **خصمٌ من أرباحٍ داخلة لا سحبٌ على المكشوف** — فلا يقع
    # الرصيدُ تحت الصفر أبداً، ولا يُمسّ حارسٌ قائم
    WalletTransactionType.ADVANCE_REPAYMENT,
    # رسمُ الإلغاء: مدينٌ على من ألغى — أو على الكبتن الحاملِ الذي قبض المبلغَ
    # نقداً وليس كلُّه له (آليةُ عمولةِ رحلةِ الكاش نفسُها منذ 6-أ)
    WalletTransactionType.CANCELLATION_FEE,
)

# `adjustment` وحده يقبل الاتجاهين — تصحيح الإدارة قد يزيد أو ينقص
SIGNED_TYPES: tuple[WalletTransactionType, ...] = (WalletTransactionType.ADJUSTMENT,)

# حالات طلب السحب التي تحجز مبلغاً لم يُخصم بعد: القيد لا يُكتب إلا عند
# `paid` (SPEC القسم 9)، فبدون عدّها يطلب الكبتن رصيده مرتين
PENDING_WITHDRAWAL_STATUSES: tuple[WithdrawalStatus, ...] = (
    WithdrawalStatus.PENDING,
    WithdrawalStatus.APPROVED,
)


def _types_in(types: tuple[WalletTransactionType, ...]) -> str:
    return ", ".join(f"'{t.value}'" for t in types)


def _amount_sign_constraint() -> str:
    """قيد القاعدة مبنيٌّ من نفس القوائم أعلاه حتى لا يفترق الكود عن المخطط."""
    return (
        f"(type IN ({_types_in(CREDIT_TYPES)}) AND amount > 0) OR "
        f"(type IN ({_types_in(DEBIT_TYPES)}) AND amount < 0) OR "
        f"(type IN ({_types_in(SIGNED_TYPES)}) AND amount <> 0)"
    )


class WalletTransaction(UUIDMixin, TimestampMixin, Base):
    """قيد واحد في دفتر محفظة — يُكتب ولا يُعدّل ولا يُحذف."""

    __tablename__ = "wallet_transactions"
    __table_args__ = (
        CheckConstraint(_amount_sign_constraint(), name="wallet_amount_sign_by_type"),
        # محفظة مسبقة الدفع لا تُسحب على المكشوف — الحارس الأخير تحت أي سباق
        CheckConstraint("balance_after >= 0", name="wallet_balance_non_negative"),
        # منع تكرار عملية أُعيد إرسالها (SPEC القسم 14). NULL لا يتعارض مع
        # NULL في postgres، فالقيود التي لا مفتاح لها لا يقيّدها هذا.
        UniqueConstraint("owner_id", "idempotency_key"),
        Index(
            "ix_wallet_transactions_owner_created",
            "owner_type",
            "owner_id",
            "created_at",
        ),
    )

    owner_type: Mapped[WalletOwnerType] = mapped_column(
        pg_enum(WalletOwnerType, "wallet_owner_type"), nullable=False
    )
    # RESTRICT: حساب عليه حركة مالية لا يُحذف، والسجل يُحفظ ولا يُمحى
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    type: Mapped[WalletTransactionType] = mapped_column(
        pg_enum(WalletTransactionType, "wallet_transaction_type"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    # السلفةُ التي يخصّها القيد (البند ١٥) — صرفاً أو اقتطاعاً. **وهو ما
    # يجعل «المتبقّي» مجموعاً يُطرح** بدل عمودِ رصيدٍ على الجدول: نفسُ دورِ
    # `ride_id` تماماً، وبغيره لا سبيلَ لجمع اقتطاعات سلفةٍ بعينها
    advance_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("driver_advances.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    # مرجع خارجي: حوالة كليك، إشعار بنكي، أو معرّف عملية لدى المزود
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # من نفّذ العملية — فارغ حين ينشئها النظام نفسه
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<WalletTransaction {self.type} {self.amount}>"


class WalletTopupRequest(UUIDMixin, TimestampMixin, Base):
    """طلب شحن ينتظر تأكيداً بشرياً (SPEC القسم 7).

    كليك بلا API، فالراكب يحوّل على alias الشركة ويُدخل المرجع هنا وتؤكده
    الإدارة. الكاش يُنشئه الموظف مؤكداً من اللوحة. شحن Telr فوريٌّ آلي فلا
    يمر من هنا أصلاً — يأتي في المرحلة 6.
    """

    __tablename__ = "wallet_topup_requests"
    __table_args__ = (
        CheckConstraint("amount > 0", name="topup_amount_positive"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # **المحفظةُ تُعلَن عند الإنشاء وتُقرأ عند التأكيد** (SPEC §22): اشتقاقُها
    # من الدور لحظةَ التأكيد يجعل طلباً أُنشئ من تطبيق الراكب يُشحن في محفظة
    # الكبتن يومَ يكسب صاحبُه الدورَ الثاني. فارغٌ في الصفوف الأقدم — وقد
    # مُلئت في `0048` لأنها كانت معلومةً يقيناً وقتَها
    owner_type: Mapped[WalletOwnerType | None] = mapped_column(
        pg_enum(WalletOwnerType, "wallet_owner_type"), nullable=True
    )
    method: Mapped[TopupMethod] = mapped_column(
        pg_enum(TopupMethod, "topup_method"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    status: Mapped[TopupRequestStatus] = mapped_column(
        pg_enum(TopupRequestStatus, "topup_request_status"),
        nullable=False,
        default=TopupRequestStatus.PENDING,
        index=True,
    )
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    processed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # القيد الناتج عن التأكيد — الوصلة بين الطلب وأثره في الدفتر
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("wallet_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<WalletTopupRequest {self.amount} ({self.status})>"


class WithdrawalRequest(UUIDMixin, TimestampMixin, Base):
    """طلب سحب من محفظة الكبتن — للكباتن وحدهم (SPEC القسم 7/9).

    الراكب يشحن ولا يسحب أبداً، فلا مسار سحب له لا هنا ولا في الراوترات.
    قيد `withdrawal` يُكتب عند `paid` وحدها: قبله لم يخرج مال، وبعده يحمل
    الطلبُ مرجعَ التحويل الذي سجّله المحاسب.
    """

    __tablename__ = "withdrawal_requests"
    __table_args__ = (
        CheckConstraint("amount > 0", name="withdrawal_amount_positive"),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    method: Mapped[WithdrawalMethod] = mapped_column(
        pg_enum(WithdrawalMethod, "withdrawal_method"), nullable=False
    )
    status: Mapped[WithdrawalStatus] = mapped_column(
        pg_enum(WithdrawalStatus, "withdrawal_status"),
        nullable=False,
        default=WithdrawalStatus.PENDING,
        index=True,
    )
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    processed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("wallet_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<WithdrawalRequest {self.amount} ({self.status})>"
