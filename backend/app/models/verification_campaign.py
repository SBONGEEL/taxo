"""حملةُ تأكيد الأرقام — **تُبنى ولا تُطلق** (قرارُ المالك 2026-08-31).

## ما هي

سوقٌ يُطلق فيه المالكُ حملةً، فيُمهَل **كلُّ حسابٍ رقمُه غير مؤكَّد** أربعةَ
عشرَ يوماً وثلاثةَ تذكيرات، ثم **يُوقَف حسابُه آلياً** حتى يؤكّده. **والفكُّ
بتأكيد الرقم وحدَه، فوراً وبلا مشرف.**

## ولمَ حالٌ مستقلّةٌ لا `is_blocked`

**`is_blocked` قرارُ مشرفٍ في شخص**: بابُه واحدٌ (`admin_users._set_blocked`)،
يشترط سبباً مكتوباً، ويسجّله في التدقيق. **وهذه حالٌ آليّةٌ تشفي نفسَها**:
سببُها معروفٌ وعلاجُها واحدٌ ويقع بلا إنسان.

**وخلطُهما عطبٌ في اتجاهين**: حملةٌ تفكّ `is_blocked` **تُطلق من حظره مشرفٌ
لسببٍ آخر** — بضغطةِ تأكيدِ رقم؛ ومشرفٌ يرفع الحظرَ **يُلغي إيقافاً آليّاً**
لم يُشفَ سببُه. **فحقلان لا حقل**، ولا يقرأ أحدُهما الآخر.

## والموظّفون خارج النطاق — **مقيسٌ لا محتاط**

قِيس على الإنتاج (2026-08-31): **كلُّ الركاب والكباتن أرقامُهم مؤكَّدة**،
**والوحيدان غيرُ المؤكَّدَين حسابا مشرف** — لا رقمَ لهما أصلاً، يدخلان باسمِ
مستخدم (SPEC §25.9). **فحملةٌ لا تستثني الموظّفين تُوقف اللوحةَ عن نفسها**
في أوّل تشغيل: من يفكّ الإيقافَ يحتاج لوحةً، واللوحةُ موقوفة.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode, VerificationCampaignStatus

#: **المهلةُ أربعةَ عشرَ يوماً** (قرارُ المالك) — عموداً لا ثابتاً في الكود:
#: حملةٌ جاريةٌ تحمل مهلتَها التي أُطلقت بها، **فتعديلُ الرقم لا يقصّر مهلةَ
#: من أُمهل** — وهي قاعدةُ `commission_percent_at_ride` نفسُها.
DEFAULT_DEADLINE_DAYS = 14

#: **ثلاثُ تذكيرات** بأيّامها من لحظة التسجيل في الحملة (قرارُ المالك).
REMINDER_DAYS: tuple[int, ...] = (0, 7, 13)

#: **دفعةُ مئتين** — لا لأن الإرسالَ بطيء، بل لأن قناةَ السوق مسقوفة.
BATCH_SIZE = 200

#: **سببُ الإيقاف — بيتُه هنا وحدَه** (قرارُ المالك 2026-08-31).
#:
#: **ولمَ في ملفِّ النموذج**: يقرؤه **ثلاثة** — الخدمةُ التي تُوقف، والخطأُ
#: الذي يَردّ (`verification.AccountSuspended`)، والحقلُ المنشورُ على
#: `UserOut`. **وثلاثُ نسخٍ لجملةٍ واحدةٍ تفترق أوّلَ تحرير**، فيقرأ المستخدمُ
#: في الإشعار غيرَ ما يقرأ في الشاشة غيرَ ما يقرأ في الرفض.
#:
#: **وهذا الملفُّ ورقةٌ في شجرة الاستيراد** — لا يستورد خدمةً، فلا دورة.
SUSPENSION_CODE = "phone_unverified"
SUSPENSION_MESSAGE = (
    "حسابك موقوف لأن رقم هاتفك غير مؤكَّد. أكّده الآن ويعود حسابك فوراً."
)


class VerificationCampaign(UUIDMixin, TimestampMixin, Base):
    """حملةُ سوقٍ واحد — **ولا تُطلق إلا بضغطة المالك**."""

    __tablename__ = "verification_campaigns"

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False
    )
    status: Mapped[VerificationCampaignStatus] = mapped_column(
        pg_enum(VerificationCampaignStatus, "verification_campaign_status"),
        nullable=False,
        server_default=text("'draft'"),
    )
    deadline_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_DEADLINE_DAYS))
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: **لحظةُ التجمّد الآليّ** — حين تسقط قناةُ السوق. و`NULL` تعني «تعمل».
    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: **مجموعُ ما تجمّدت** بالثواني — **وبه تُمدَّد المهل عند الاستئناف**.
    #:
    #: **ولمَ يُجمَع ولا يُحسب من `paused_at`**: الحملةُ قد تتجمّد وتستأنف
    #: مرّاتٍ، **وآخرُ تجمّدٍ لا يعرف ما قبله** — فمن أُمهل أربعةَ عشرَ يوماً
    #: وسقطت القناةُ ثلاثاً في يومين يخسر يومين لا يملك ردَّهما.
    paused_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: من أطلقها — **والإطلاقُ فعلُ إنسانٍ دائماً**، والتجمّدُ والاستئنافُ آليّان
    started_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        # **حملةٌ حيّةٌ واحدةٌ لكلِّ سوق** — واثنتان تُرسلان تذكيرين لواحد،
        # وتحسبان مهلتين لحسابٍ واحد
        Index(
            "uq_verification_campaign_live",
            "country_code",
            unique=True,
            postgresql_where=text("status IN ('draft', 'running', 'paused')"),
        ),
    )


class VerificationEnforcement(UUIDMixin, TimestampMixin, Base):
    """سطرُ حسابٍ في حملة — **التقدّمُ في صفٍّ لا في ذاكرة المهمّة**.

    **وهي قاعدةُ `notification_deliveries` نفسُها**: مهمّةٌ تموت في منتصف
    حملةٍ **تُستأنف ولا تُعاد** — وإعادتُها تعني تذكيراً ثانياً لمن ذُكِّر،
    وإيقافاً لمن أكّد.
    """

    __tablename__ = "verification_enforcements"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("verification_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: **المهلةُ تُحسب من هذا الحقل لا من نصّ** (قرارُ المالك): التاريخُ
    #: يُحقن في التذكير ولا يُكتب فيه.
    deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reminders_sent: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    last_reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: لحظةُ التأكيد — **وبها يُفكّ الإيقافُ وتُمدَّد أيامُ الاشتراك**
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: **أيامُ الإيقاف التي عُوِّضت في الاشتراك** — يُكتب مرّةً ولا يُعاد.
    #:
    #: **ولمَ عمودٌ ولا يُحسب من الفرق**: التعويضُ **وقع أو لم يقع**، وحسابُه
    #: من `suspended_at → resolved_at` في كلِّ قراءةٍ **يعوّض مرّتين** إن
    #: أُعيد تشغيلُ المسار.
    subscription_days_granted: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "user_id", name="uq_enforcement_per_campaign_user"
        ),
    )
