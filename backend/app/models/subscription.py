"""خطط اشتراك الكباتن واشتراكاتهم الفعلية (SPEC القسم 4/8).

**لا اشتراك ساري = لا رحلات.** الفحص يقع في التوزيع
(`dispatch.eligible_driver_ids`) لا في الواجهة، فالجدولان هذان هما ما يقرأه
كل عرضِ طلبٍ على كبتن.

**التجديد سجلٌّ جديد لا تعديلُ صف** (القسم 4): تاريخ الاشتراكات كله محفوظ،
فيُقرأ في تقارير اللوحة كما يُقرأ الدفتر. ولذلك «الاشتراك الساري» ليس صفاً
بعينه بل *سؤالٌ عن الوقت*: هل يوجد صفٌّ يغطي هذه اللحظة؟
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
    PaymentMethod,
    SubscriptionDurationType,
    SubscriptionStatus,
)

if TYPE_CHECKING:
    from app.models.driver import Driver


class SubscriptionPlan(UUIDMixin, TimestampMixin, Base):
    """خطة اشتراك الكبتن (يومي/أسبوعي/شهري) لكل دولة."""

    __tablename__ = "subscription_plans"
    __table_args__ = (
        UniqueConstraint("country_code", "name"),
        CheckConstraint("price >= 0", name="subscription_price_non_negative"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_type: Mapped[SubscriptionDurationType] = mapped_column(
        pg_enum(SubscriptionDurationType, "subscription_duration_type"), nullable=False
    )
    price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[Currency] = mapped_column(pg_enum(Currency, "currency"), nullable=False)
    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<SubscriptionPlan {self.country_code}/{self.name}>"


class DriverSubscription(UUIDMixin, TimestampMixin, Base):
    """اشتراكٌ واحد مدفوعٌ مقدماً لكبتن، بمدة الخطة التي اشتراها.

    **الصفُّ لا يُنشأ إلا وقد وصل ماله** — بأي قناة من قنوات القسم 8: المحفظة
    والبطاقة فوريتان، والكاش وكليك يسجّلهما الموظف بعد قبضهما. فلا حالة
    «بانتظار الدفع» هنا كما لا يوجد رصيدٌ قبل تأكيد شحنته.

    `payment_method` يعيد استعمال نوع قنوات الدفع نفسه: القنوات الأربع في
    القسم 8 هي القنوات الأربع في القسم 6 بأعيانها، ونوعٌ ثانٍ لها يعني قائمتين
    قابلتين للافتراق.

    `transaction_id` غير فارغ للمحفظة وحدها — هي القناة الوحيدة التي يخرج مالها
    من رصيد الكبتن فيُقيَّد عليه `subscription_payment` (القسم 9: الرصيد =
    أرباح − عمولات − **الاشتراكات المدفوعة منها** − سحوبات). كاشٌ أو كليكٌ أو
    بطاقةٌ لا يمر مالها بالمحفظة أصلاً، فقيدُ خصمٍ عليها يخصم من الكبتن مرتين —
    نفس تفريق `WALLET_FUNDED_METHODS` في دفعات الرحلة.
    """

    __tablename__ = "driver_subscriptions"
    __table_args__ = (
        CheckConstraint("expires_at > starts_at", name="subscription_period_positive"),
        CheckConstraint("amount_paid >= 0", name="subscription_amount_non_negative"),
        CheckConstraint(
            "discount_amount >= 0", name="subscription_discount_non_negative"
        ),
        CheckConstraint(
            "offer_discount_amount >= 0",
            # **اسمٌ قصير**: الطويلُ يبلغ ٦٤ محرفاً مع بادئة الجدول، وPostgres يقتطع
            # عند ٦٣ ويُلحق تجزئة — فيفترق اسمُه في القاعدة عن اسمِه في النموذج
            # ويُبلّغ `test_migrations_match_models` انحرافاً في كل تشغيل
            name="offer_discount_non_negative",
        ),
        # مفتاح عدم التكرار الذي يفرضه القسم 14: ضغطتان على «تجديد» لا تشتريان
        # اشتراكين. فريدٌ على مستوى الجدول كما في `payments` — العميل يولّده
        # لعمليةٍ بعينها، وNULL لا يتعارض مع NULL فما لا مفتاح له لا يُقيَّد.
        UniqueConstraint("idempotency_key", name="uq_driver_subscriptions_idempotency_key"),
        # سؤال التوزيع الوحيد: «هل يغطي هذا الكبتنَ صفٌّ الآن؟»
        Index("ix_driver_subscriptions_driver_expires", "driver_id", "expires_at"),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        # RESTRICT كبقية الجداول المالية: سجلٌّ دُفع ثمنه لا يُمحى بحذف صاحبه
        ForeignKey("drivers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # مجمّد لحظة الشراء ولا يُقرأ من الخطة بعدها: رفعُ سعر الخطة اليوم لا يغيّر
    # ما دفعه كبتنُ الأمس — نفس منطق `rides.commission_percent_at_ride`
    amount_paid: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        pg_enum(PaymentMethod, "payment_method"), nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        pg_enum(SubscriptionStatus, "subscription_status"),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
        index=True,
    )

    # قيد الدفتر الناتج — للمحفظة وحدها (انظر شرح الصنف)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("wallet_transactions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # ------------------------------------------------ العرضُ الذي خصم (البند ٥٤)

    # **`RESTRICT` لا `SET NULL`**: عرضٌ يُحذف بعد أن اشترى به عشرون كبتناً يمحو
    # **سببَ** خصومهم فيبقى `discount_amount` رقماً بلا اسم. والحذفُ إطفاءٌ
    # (`is_active = false`) لا محو.
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("subscription_offers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    # **ما تنازلنا عنه فعلاً** — وفي مسار الكاش/كليك هو `list_price − amount_paid`
    # لا ما حسبه العرض: فإن حصّل المشرفُ مبلغاً آخر بقي «كم تنازلنا؟» جواباً واحداً
    discount_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0"), server_default="0"
    )
    # **ما منحه العرضُ لحظتَها، مجمَّداً** — وهو غيرُ `discount_amount`:
    # الأولُ ما قرّره العرض، والثاني ما وقع فعلاً. ويتساويان في المحفظة
    # والبطاقة دائماً، ويفترقان في الكاش/كليك حين يحصّل المشرفُ مبلغاً آخر.
    #
    # **وبه وحدَه يصدق وسمُ «تسويةٍ يدوية»**: مقارنةٌ حيّةٌ بين رقمين مجمَّدين،
    # فلا تنحرف حين يُعدَّل العرضُ بعد شهر — بخلاف إعادةِ الحساب من نسبة العرض
    # اليوم. **ولا عمودَ «تسوية» يُخزَّن**: الوسمُ يُقاس ولا يُختم (قاعدةُ
    # «flagged» في تقارير عدم التطابق).
    offer_discount_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0"), server_default="0"
    )
    # **سعرُ الخطة قبل الخصم، مجمَّداً** — وليس تكراراً لـ`amount_paid`: الأولُ ما
    # كان يُدفع لولا العرض، والثاني ما دُفع. وبغيره يُقرأ سعرُ الخطة **اليوم**
    # فيُعاد تسعيرُ تنازلٍ وقع قبل شهرين. قاعدةُ `commission_percent_at_ride`.
    list_price: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0"), server_default="0"
    )

    # مرجع خارجي: حوالة كليك أو إيصال الكاش أو مرجع الطلب لدى مزود البطاقة
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan")
    driver: Mapped["Driver"] = relationship("Driver", foreign_keys=[driver_id])

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<DriverSubscription {self.driver_id} → {self.expires_at}>"
