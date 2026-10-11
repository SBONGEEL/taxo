"""نظامُ الدفع الجديد — طرقُ الدفع صفوفاً لكلِّ دولة، والدفعاتُ بحالاتها الخمس (SPEC §٧٣-أ/٥، §٧٣-هـ المرحلة ١).

**جدولان جديدان لا تعديلٌ في القائم**: `payments` (دفعُ الرحلة) و`wallet_topup_requests` (كليك والكاش في الأردن) و`provider_orders`
كما هي — **فدفعُ الأردن وليبيا لا يمرّ بسطرٍ هنا**، وهو ما يجعل «لم يتغيّر» قابلاً للإثبات.

**ولا تُحذف دفعةٌ أبداً**: الترحيلةُ `0112` تضع مُشغّلاً يرفض `DELETE` على `payment_requests` كمُشغّل الدفتر في `0006` — والحالاتُ
تتغيّر بـ`UPDATE` وحدَه، **وكلُّ رفضٍ وردٍّ وإلغاءٍ بسببٍ مكتوب** يحرسه قيدٌ في القاعدة لا الشيفرةُ وحدَها.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    CountryCode,
    Currency,
    PaymentProviderKind,
    PaymentRequestPurpose,
    PaymentRequestStatus,
    WalletOwnerType,
)

#: **الحالاتُ التي تحجز المرجعَ وبصمةَ الإيصال** — طلبٌ مرفوضٌ أو ملغًى يُفرج عنهما فيُقدَّم التحويلُ نفسُه من جديد بإيصالٍ صحيح،
#: ومعلَّقٌ أو معتمدٌ أو مردودٌ يحجزهما: **الدفعةُ الواحدةُ لا تُحتسب مرّتين** (§٧٣-هـ/٦)
LIVE_STATUSES_SQL = "status IN ('pending', 'approved', 'refunded')"


class PayMethod(UUIDMixin, TimestampMixin, Base):
    """**طريقةُ دفعٍ صفٌّ يُضاف ويُفعَّل من اللوحة لكلِّ دولة** (§٧٣-أ/٥).

    **والنوعُ يحكم ما يُطلب من المستخدم** (§٧٣-هـ/٢): التحويلُ البنكيُّ والدفعُ برقم هاتفٍ **إيصالُهما إجباريّ**، والكاشُ بلا إيصال.
    **وBaridiMob وCCP والتحويلُ البنكيُّ ورمزُ QR كلُّها `bank_transfer`** — والـQR صورةٌ ترافق الطريقةَ (`qr_image_path`) لا نوعٌ خامس.

    `integration` فارغٌ للطريقة اليدويّة؛ والوسيطُ الآليُّ (المرحلة ٣) يحمل اسمَ محوِّله فيُعرف به في الـwebhook الموحّد.
    """

    __tablename__ = "payment_providers"
    __table_args__ = (UniqueConstraint("country_code", "code"),)

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    kind: Mapped[PaymentProviderKind] = mapped_column(
        pg_enum(PaymentProviderKind, "payment_provider_kind"), nullable=False
    )
    #: معرّفٌ لاتينيٌّ قصيرٌ ثابت (`baridimob` · `ccp` · `bank` · `office_cash` …) — **لا يتغيّر بعد الإنشاء**: الطلباتُ تُقرأ به
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    #: الاسمُ كما يراه المستخدم
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    integration: Mapped[str | None] = mapped_column(String(40), nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    for_topup: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    for_subscription: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    #: **صاحبُ الحساب ورقمُه** — RIP لـBaridiMob/CCP، أو رقمُ الحساب البنكيّ، أو رقمُ الهاتف. **تبديلُه أخطرُ بابٍ في النظام**
    #: (§٧٣-هـ/١١): من بدّله حوّل مالَ الناس إلى حسابه — فيُحرَّر بـ`settings.write` وحدَها ويُدقَّق كلُّ تغيير
    account_holder: Mapped[str | None] = mapped_column(String(120), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr_image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qr_content_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<PayMethod {self.country_code}/{self.code} ({self.kind})>"


class PaymentRequest(UUIDMixin, TimestampMixin, Base):
    """**دفعةٌ في النظام الجديد** — شحنُ محفظةٍ أو اشتراكُ كبتن، بحالاتها الخمس (§٧٣-أ/٥).

    **والمبلغُ المقيَّدُ مبلغُ الموظّف الماليّ لا دعوى المستخدم** (قرارُ المالك ٢٠٢٦-٠٨-٢٩ في الشحن اليدويّ): الدعوى في `amount`، وما
    دخل في `credited_amount` وقيدُه في `transaction_id`. **والنوعُ مجمَّدٌ من الطريقة لحظةَ الإنشاء** — تبديلُ نوع الطريقة بعدها لا يغيّر
    ما طُلب من صاحب الطلب.
    """

    __tablename__ = "payment_requests"
    __table_args__ = (
        CheckConstraint("amount > 0", name="payment_request_amount_positive"),
        CheckConstraint(
            "credited_amount IS NULL OR credited_amount > 0", name="payment_request_credited_positive"
        ),
        # **كلُّ رفضٍ وردٍّ وإلغاءٍ بسببٍ مكتوب** (قرارُ المالك) — في القاعدة لا في الشيفرة وحدَها
        CheckConstraint(
            "status <> 'rejected' OR length(btrim(coalesce(rejection_reason, ''))) > 0",
            name="payment_request_rejection_has_reason",
        ),
        CheckConstraint(
            "status <> 'refunded' OR length(btrim(coalesce(refund_reason, ''))) > 0",
            name="payment_request_refund_has_reason",
        ),
        CheckConstraint(
            "status <> 'cancelled' OR length(btrim(coalesce(cancel_reason, ''))) > 0",
            name="payment_request_cancel_has_reason",
        ),
        CheckConstraint(
            "purpose <> 'subscription' OR plan_id IS NOT NULL", name="payment_request_subscription_has_plan"
        ),
        # **الدفعةُ الواحدةُ لا تُحتسب مرّتين** (§٧٣-هـ/٦): المرجعُ نفسُه وبصمةُ الإيصال نفسُها لا يُقدَّمان لطريقةٍ واحدةٍ مرّتين
        Index(
            "uq_payment_requests_reference_live",
            "provider_id",
            "reference_key",
            unique=True,
            postgresql_where=text(f"reference_key IS NOT NULL AND {LIVE_STATUSES_SQL}"),
        ),
        Index(
            "uq_payment_requests_receipt_live",
            "provider_id",
            "receipt_sha256",
            unique=True,
            postgresql_where=text(f"receipt_sha256 IS NOT NULL AND {LIVE_STATUSES_SQL}"),
        ),
        Index(
            "uq_payment_requests_external",
            "provider_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    #: **المحفظةُ تُعلَن عند الإنشاء وتُقرأ عند الاعتماد** (SPEC §22) — كطلبات الشحن القائمة حرفاً
    owner_type: Mapped[WalletOwnerType] = mapped_column(
        pg_enum(WalletOwnerType, "wallet_owner_type"), nullable=False
    )
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("payment_providers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kind: Mapped[PaymentProviderKind] = mapped_column(
        pg_enum(PaymentProviderKind, "payment_provider_kind"), nullable=False
    )
    purpose: Mapped[PaymentRequestPurpose] = mapped_column(
        pg_enum(PaymentRequestPurpose, "payment_request_purpose"), nullable=False
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=True
    )

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    credited_amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    status: Mapped[PaymentRequestStatus] = mapped_column(
        pg_enum(PaymentRequestStatus, "payment_request_status"),
        nullable=False,
        default=PaymentRequestStatus.PENDING,
        index=True,
    )

    #: مرجعُ التحويل كما كتبه صاحبُه — ومفتاحُه مطبَّعاً (بلا مسافاتٍ وبحروفٍ صغيرة) للفهرس الفريد
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reference_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: معرّفُ الدفعة عند الوسيط الآليّ (المرحلة ٣)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    receipt_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt_content_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    receipt_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    refund_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    refunded_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: قيدُ الاعتماد في الدفتر — وقيدُ الردّ المقابل
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("wallet_transactions.id", ondelete="RESTRICT"), nullable=True
    )
    refund_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("wallet_transactions.id", ondelete="RESTRICT"), nullable=True
    )
    #: **الاشتراكُ الذي فُعِّل** — فارغٌ لشحنٍ، أو لاشتراكٍ تعذّر شراؤه فبقي مالُه في المحفظة (`outcome_note` يقول لماذا)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("driver_subscriptions.id", ondelete="RESTRICT"), nullable=True
    )
    outcome_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    provider: Mapped[PayMethod] = relationship(PayMethod, lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<PaymentRequest {self.amount} ({self.status})>"
