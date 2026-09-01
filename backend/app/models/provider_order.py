"""طلبات الدفع لدى مزود البطاقات (SPEC القسم 6.4/7 — المرحلة 6-ب).

بين لحظة إنشاء صفحة الدفع ولحظة وصول جواب المزود فراغٌ زمنيٌّ يعيش فيه العميل
على شبكةٍ لا نملكها: يغادر الراكب الصفحة، أو يصل الـ webhook مرتين، أو يصل قبل
أن يعود المتصفح. هذا الجدول هو ما يجعل ذلك الفراغ مُحاسَباً عليه — الصفُّ
الوحيد الذي يعرف «طلبٌ فُتح ولم يُحسم بعد».

**`cart_id` هو المُعرّف الذي نرسله للمزود ويعود به إلينا**، وهو فريد في
القاعدة: فبه وحده يجد الـ webhook صاحبَه، ولا يجد صاحبين.

الغرضان يستقران في مكانين مختلفين عند الدفع:

- `ride_payment`: صفُّ `payments` مُنشأٌ سلفاً `pending`، ويصير `confirmed`.
- `wallet_topup`: لا صفَّ طلبِ شحنٍ أصلاً — شحن البطاقة فوريٌّ آلي فلا ينتظر
  تأكيداً بشرياً (القسم 7)، فيُكتب قيد `topup` مباشرة و`transaction_id` هو
  أثره. `wallet_topup_requests` بيتُ ما ينتظر إنساناً وحده.

**ترتيب الأقفال: صف الرحلة ← صف الدفعة ← صف الطلب ← القفل الاستشاري للمحفظة.**
هذا الصف يُقفل بعد صف الدفعة لا قبله، لأن الاسترداد الإداري يقفل الدفعة أولاً
(`admin_payments`) ثم يحتاج طلبها ليردّه عند المزود؛ فلو قُفل الطلب أولاً في
مسار التسوية لتقابل المسارانِ في جمود.
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
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    CountryCode,
    Currency,
    PaymentProvider,
    ProviderOrderPurpose,
    ProviderOrderSource,
    ProviderOrderStatus,
)

if TYPE_CHECKING:
    from app.models.user import User

# حالات لم يُحسم فيها المزود بعد: الطلب ما زال يحجز مبلغه، ويجوز استعلامه
OPEN_ORDER_STATUSES: tuple[ProviderOrderStatus, ...] = (
    ProviderOrderStatus.CREATED,
)


class ProviderOrder(UUIDMixin, TimestampMixin, Base):
    """طلب دفعٍ واحد لدى مزود البطاقات."""

    __tablename__ = "provider_orders"
    __table_args__ = (
        CheckConstraint("amount > 0", name="provider_order_amount_positive"),
        # المُعرّف الذي يرجع به المزود — فريدٌ في القاعدة لا في الكود وحده،
        # فسباقُ إنشاءين لا ينتج مرجعين لطلبٍ واحد
        UniqueConstraint("cart_id", name="uq_provider_orders_cart_id"),
        # أجرةُ رحلةٍ لا تُفتح بلا رحلة ولا بلا صفِّ دفعةٍ يستقر فيها، وشحنُ
        # محفظةٍ لا رحلةَ له ولا دفعة: الغرض والوصلات لا يفترقان
        CheckConstraint(
            "(purpose = 'ride_payment') = (ride_id IS NOT NULL)",
            name="provider_order_ride_matches_purpose",
        ),
        CheckConstraint(
            "(purpose = 'ride_payment') = (payment_id IS NOT NULL)",
            name="provider_order_payment_matches_purpose",
        ),
        # واشتراكُ كبتنٍ لا يُفتح بلا خطةٍ يشتريها. المقارنة على النص لا على
        # قيمة الـ ENUM عمداً: `subscription` قيمةٌ أُضيفت للنوع في ترحيلة
        # `0009` نفسها، وpostgres يرفض استعمال قيمة enum جديدة في المعاملة التي
        # أضافتها — فالنص هو ما يجعل القيد يولد مع العمود في ترحيلة واحدة
        CheckConstraint(
            "(purpose::text = 'subscription') = (plan_id IS NOT NULL)",
            name="provider_order_plan_matches_purpose",
        ),
        Index("ix_provider_orders_provider_ref", "provider", "provider_order_ref"),
    )

    provider: Mapped[PaymentProvider] = mapped_column(
        pg_enum(PaymentProvider, "payment_provider"),
        nullable=False,
        default=PaymentProvider.TELR,
    )
    #: **من حصّل**: يدويّاً بيد مشرف، أو من إشعار القابض. **يُختم على الصفّ**
    #: فيُقرأ في التدقيق ولا يُخمَّن. انظر `ProviderOrderSource`.
    source: Mapped[ProviderOrderSource] = mapped_column(
        pg_enum(ProviderOrderSource, "provider_order_source"),
        nullable=False,
        server_default=ProviderOrderSource.ACQUIRER.value,
    )

    purpose: Mapped[ProviderOrderPurpose] = mapped_column(
        pg_enum(ProviderOrderPurpose, "provider_order_purpose"), nullable=False
    )
    status: Mapped[ProviderOrderStatus] = mapped_column(
        pg_enum(ProviderOrderStatus, "provider_order_status"),
        nullable=False,
        default=ProviderOrderStatus.CREATED,
        index=True,
    )

    # ما نرسله للمزود ويعود به: قصيرٌ عمداً (سقف `ivp_cart` لدى Telr)
    cart_id: Mapped[str] = mapped_column(String(25), nullable=False)
    # مرجع الطلب لدى المزود — لا يُعرف إلا بعد جوابه على الإنشاء
    provider_order_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # صفحة الدفع المستضافة؛ فارغة في الدفع بضغطة (لا صفحة تُفتح). ولقناة كليك
    # الآلية (المرحلة 8) هو الرابط الذي يفتح تطبيق البنك
    redirect_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # ما يحمله رمز الاستجابة السريعة في قناة كليك الآلية (المرحلة 8). يُحفظ
    # لأن الراكب قد يغلق الشاشة ويعود، ورمزٌ يُفقد بإغلاق شاشة يعني طلباً
    # معلّقاً لا سبيل لدفعه. فارغٌ في قناة البطاقة — لا رمز فيها أصلاً
    qr_payload: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # الدافع: الراكب في الغرضين. RESTRICT كبقية الجداول المالية
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # **التطبيقُ الذي فتح الدفع** (SPEC §22): العودةُ تتبع من بدأ لا دورَ من
    # يدفع — وحسابٌ بدورين لا يقول دورُه إلى أين يعود. فارغٌ في الصفوف الأقدم،
    # ومُلئت في `0049` لأنها كانت معلومةً يقيناً وقتَها
    opened_from_app: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # دولة العقد الذي فُتح به الطلب. عقود المزودين per-country (SPEC القسم 4)،
    # فبغير تثبيتها هنا يُستعلم طلبُ الأمس بعقد اليوم إن انتقل صاحبه دولة
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # من دولة الرحلة أو دولة صاحب المحفظة — لا تُقبل من عميل (SPEC القسم 4)
    currency: Mapped[Currency] = mapped_column(
        pg_enum(Currency, "currency"), nullable=False
    )

    ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # الخطة المشتراة حين يكون الغرض اشتراكاً (المرحلة 7). الخطةُ لا الاشتراك:
    # صفُّ الاشتراك لا يُنشأ إلا بعد أن يقول المزود «دُفع»، فالطلب يحمل ما
    # يكفي لإنشائه لا وصلةً إلى صفٍّ قد لا يوجد أبداً
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # أثر شحن المحفظة في الدفتر — نفس دور `transaction_id` في طلبات الشحن
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("wallet_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # هل طلب صاحبُها حفظَ البطاقة؟ القرار قرارُه لا قرارُنا (SPEC القسم 6.4)
    save_card: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # نصُّ المزود عند الرفض — يُعرض للراكب ويُقرأ في اللوحة عند النزاع
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # مرجع الردّ لدى المزود حين تُستردّ الدفعة عبره (SPEC القسم 6.4). الحالة
    # تبقى `paid` — الطلبُ دُفع فعلاً، والردُّ حركةٌ تالية له لا نقضٌ لتاريخه
    refund_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # **لحظةُ قول صاحبِه «حوّلتُ»** (قرارُ المالك 2026-09-01) — للمطالبات
    # اليدويّة وحدَها.
    #
    # **ولمَ عمودٌ ولا تكفي `status = created`**: تلك تعني **«فُتحت الشاشة»**
    # لا **«حوّلتُ»**. فقائمةُ المشرف كانت تخلط من فتح ونسي بمن دفع فعلاً —
    # **وهو ينتظر تأكيداً لمالٍ خرج من حسابه**، والأولُ لا ينتظر شيئاً.
    #
    # **وثانياً**: هو ما يجعل الضغطةَ الثانيةَ لا تُنشئ شيئاً — الحقلُ مختومٌ
    # فيُعاد الصفُّ نفسُه بلا صياح. **وصفٌّ ثانٍ لتحويلٍ واحدٍ يُقرأ دفعتين.**
    declared_paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<ProviderOrder {self.cart_id} {self.purpose} ({self.status})>"
