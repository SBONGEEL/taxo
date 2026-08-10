"""الحملات الإدارية/التسويقية وسجلّ تسليمها وساعات الهدوء (المرحلة 8).

**فئتان لا فئة واحدة**، والفرق بينهما ليس في النص بل في من يملك القرار:

- **المعاملاتي** — أحداث الرحلة وعرض الطلب وتنبيه الاشتراك — جزءٌ من الخدمة
  نفسها: لا يُطفأ من التطبيق، ولا تحبسه ساعات هدوء (كبتنٌ يعمل ليلاً يجب أن
  تصله بطاقة الطلب)، ولا صفَّ له في هذه الجداول. مكانه
  `services/notifications.py`.
- **التسويقي** — هذه الجداول: يملك المستخدم إطفاءه (`marketing_push_enabled`)،
  وله ساعات هدوء per-country، ويُرسل على دفعات بمهمة خلفية، ويُسجَّل من وصله
  ومتى.

خلطُهما يعني أحد أمرين: إما أن يُطفئ راكبٌ إعلاناً فيطفئ معه «وصل الكبتن»،
أو أن يصل إعلانٌ في الثالثة فجراً لأن الأحداث المستعجلة لا تعرف ساعات هدوء.

بنيةُ الفئة (ب) تُبنى الآن وواجهتُها في اللوحة في **المرحلة 11** (SPEC
القسم 13/16).
"""

from __future__ import annotations

import uuid
from datetime import datetime, time

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    CampaignAudience,
    CampaignStatus,
    CountryCode,
    DeliveryStatus,
)

# الحالات التي ما زالت الحملة فيها قابلةً للتعديل والإلغاء
OPEN_CAMPAIGN_STATUSES: tuple[CampaignStatus, ...] = (
    CampaignStatus.DRAFT,
    CampaignStatus.SCHEDULED,
)


class NotificationCampaign(UUIDMixin, TimestampMixin, Base):
    """حملة إشعارات واحدة يكتبها المشرف."""

    __tablename__ = "notification_campaigns"
    __table_args__ = (
        # جمهور «دولة بعينها» بلا دولة جمهورٌ غير معرَّف — والقاعدة تمنعه
        CheckConstraint(
            "(audience::text = 'by_country') <= (country_code IS NOT NULL)",
            name="campaign_country_required",
        ),
        # حملةٌ مجدولة بلا موعد لا تُرسل أبداً، وموعدٌ بلا جدولة لا يُقرأ
        CheckConstraint(
            "(status::text = 'scheduled') <= (scheduled_at IS NOT NULL)",
            name="campaign_scheduled_requires_time",
        ),
        CheckConstraint("sent_count >= 0", name="campaign_sent_count_non_negative"),
        Index("ix_notification_campaigns_status_scheduled", "status", "scheduled_at"),
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)

    audience: Mapped[CampaignAudience] = mapped_column(
        pg_enum(CampaignAudience, "campaign_audience"), nullable=False
    )
    # مُضيِّقٌ لأي جمهور، ومطلوبٌ لجمهور «دولة بعينها» وحده
    country_code: Mapped[CountryCode | None] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=True
    )

    status: Mapped[CampaignStatus] = mapped_column(
        pg_enum(CampaignStatus, "campaign_status"),
        nullable=False,
        default=CampaignStatus.DRAFT,
        index=True,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # عددُ من وصلهم فعلاً — يُقرأ في اللوحة، وتفصيلُه في `deliveries`
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # يبقى بعد حذف الحساب كما في `admin_audit_logs` — من أرسل حملةً سؤالٌ
    # يُسأل بعد رحيله
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<NotificationCampaign {self.title} ({self.status})>"


class NotificationDelivery(UUIDMixin, TimestampMixin, Base):
    """سطرٌ لكل مستخدمٍ في كل حملة: أُرسل؟ فشل؟ تُخطّي؟ ومتى.

    **الفريد `(campaign_id, user_id)` هو حارس عدم التكرار**: مهمةٌ أُعيد
    تشغيلها بعد سقوطٍ في منتصف دفعة لا ترسل لمن وصله بالفعل.
    """

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "user_id", name="uq_notification_deliveries_campaign_user"
        ),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("notification_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # سجلُّ إرسالٍ لا سجلٌّ مالي: يذهب مع صاحبه — نفس منطق `device_tokens`
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        pg_enum(DeliveryStatus, "delivery_status"), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<NotificationDelivery {self.campaign_id} {self.status}>"


class NotificationSetting(UUIDMixin, TimestampMixin, Base):
    """ساعات الهدوء per-country (SPEC القسم 13/6).

    **بمِنطقةٍ زمنية صريحة**: «لا إرسال بعد العاشرة» جملةٌ بلا معنى ما لم
    يُقل عاشرةُ مَن. والعمود نصٌّ لا ثابتُ كود لأن الحدّ يُضبط من اللوحة.

    النافذة قد تعبر منتصف الليل (22:00 → 08:00) وهو الوضع الافتراضي، ولذلك
    الفحص لا يقارن مجالاً واحداً بل يفرّق بين الحالتين — انظر
    `services/campaigns.py::within_quiet_hours`.
    """

    __tablename__ = "notification_settings"
    __table_args__ = (
        UniqueConstraint("country_code", name="uq_notification_settings_country_code"),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    quiet_hours_start: Mapped[time] = mapped_column(Time, nullable=False)
    quiet_hours_end: Mapped[time] = mapped_column(Time, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<NotificationSetting {self.country_code}>"


class UserNotification(UUIDMixin, TimestampMixin, Base):
    """صندوق وارد المستخدم: **أثرٌ دائم لإشعارٍ عابر** (المرحلة 9-ب).

    قبل هذا الجدول كان الإشعار حدثاً بلا سجل: `services/notifications.py`
    تبثّ على Redis وتبعث Push ثم تنسى. فمن أُغلق تطبيقُه ساعةً لا يعرف أن
    اشتراكه انتهى، ولا أن نزاعه فُصل، ولا أن وثيقته رُفضت — وأيقونةُ الجرس
    في التصميم تصف ميزةً لا مصدر لها.

    ثلاث قواعد:

    - **يُكتب من نفس نقطة الإرسال لا من جانبها.** كلُّ إشعارٍ يمر بـ
      `services/inbox.py::record` من داخل `notifications.py` و`campaigns.py`،
      وهما البابان الوحيدان للإرسال. قناةٌ ثالثة تُضاف يوماً تكتب هنا لأن
      البابين هما ما يُضاف إليهما، لا لأن أحداً تذكّر.
    - **يُكتب ولو لم يُرسل Push.** لا عقد FCM، أو الجهاز مفتوحٌ فلا يُرسل
      إليه — كلاهما لا يعني أن الحدث لم يقع. الصفُّ أثرُ الحدث لا أثرُ
      المزوّد.
    - **`kind` هي `data["type"]` نفسها** التي تحملها حمولة Push، فلا يفترق
      ما يفتحه الضغط على الإشعار عمّا يفتحه الضغط على صفّه في الصندوق.

    و`ON DELETE CASCADE`: سجلُّ عرضٍ لا سجلٌّ مالي — يذهب مع صاحبه، كما
    `device_tokens`.

    **التقليم (retention) ليس هنا:** الجدول ينمو بلا حد اليوم. مهمةُ كنسٍ
    دورية مكانها **المرحلة 12** مع بقية مهام الصيانة — وحتى ذلك الحين
    القراءةُ مسقوفةٌ بـ `limit` والفهرس على `(user_id, created_at)`.
    """

    __tablename__ = "user_notifications"
    __table_args__ = (
        Index("ix_user_notifications_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # نوع الحدث كما في `PushMessage.data["type"]` — نصٌّ لا ENUM: الأنواع
    # تُضاف مع كل حدثٍ جديد، وترحيلةٌ لكل نصٍّ جديد ثمنٌ بلا مقابل. ونفس
    # الاعتبار الذي جعل `feature_flags.feature_key` نصّاً
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    # نفس حمولة Push: مُعرّفاتٌ تفتح الشاشة الصحيحة. **لا مال ولا سرّ فيها**
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<UserNotification {self.kind} ({self.user_id})>"
