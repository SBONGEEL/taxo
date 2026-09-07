"""طلبُ إلغاء تفعيل حساب الكبتن (البند ١٣، SPEC القسم 7).

**بابٌ لم يكن في المشروع، وبه وحده يخرج الرصيدُ المحتجَز.** وثلاثةُ قراراتٍ في
شكله تستحق أن تُقرأ قبل تعديله:

- **طلبٌ يُراجَع لا مفتاحٌ يُرفع.** إغلاقُ الحساب يمسّ مالاً محجوزاً ودَيناً
  محتملاً ونزاعاً قد يكون مفتوحاً، فيمرّ بمشرفٍ كما يمرّ السحب. ولو كان زرّاً
  فوريّاً لصار بابَ خروجٍ من مسؤوليةٍ قائمة.
- **ولا عمودَ «مُلغى» على الكبتن يوازي هذا الجدول.** حالتُه في `drivers.status`
  وحدها (`deactivated`)، والجدولُ يحمل **الطلبَ** لا الحال — وحالتان لأمرٍ واحد
  تفترقان يومَ تُكتب إحداهما بلا الأخرى (درسُ `qualified_at`).
- **والشروطُ تُقرأ حيّةً لحظةَ الطلب**: رحلةٌ جارية، أو نزاعٌ مفتوح، أو دَينُ
  سلفةٍ قائم — لا تُخزَّن على الصف، فتغيّرُ الحال يعيد تقييمَ الطلب بلا لمسه.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import DeactivationStatus


class DeactivationRequest(UUIDMixin, TimestampMixin, Base):
    """طلبٌ واحد بإلغاء التفعيل — بحالته وقرارِ من بتّ فيه."""

    __tablename__ = "deactivation_requests"
    __table_args__ = (
        # **طلبٌ قائمٌ واحدٌ لكل كبتن**: فهرسٌ جزئيٌّ على الحالة المعلّقة —
        # ضغطتان متزامنتان لا تنتجان طلبين ينظر فيهما مشرفان
        Index(
            "uq_deactivation_pending",
            "user_id",
            unique=True,
            postgresql_where="status = 'pending'",
        ),
    )

    #: **موضوعُ الطلب حسابٌ لا كبتن** (الترحيلة `0075`، ٢٠٢٦-٠٩-٠٧).
    #:
    #: **وكان `driver_id`**، فلمّا أوجب المتجرُ مسارَ حذفٍ للراكب **لم يوسَّع
    #: الجدولُ ببابٍ ثانٍ بل بموضوعٍ أعمّ**: السؤالُ واحدٌ — «هذا الحسابُ يريد
    #: الخروج» — **وجدولان له يفترقان أوّلَ تعديل**.
    #:
    #: **والموانعُ هي التي تعرف الدور** لا الجدول: من له صفٌّ في `drivers`
    #: تُقرأ موانعُ الكبتن معها، **ومن يحمل الدورين تُجمع الموانعُ كلُّها** —
    #: فحسابٌ واحدٌ يُغلق مرّةً واحدة.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[DeactivationStatus] = mapped_column(
        pg_enum(DeactivationStatus, "deactivation_status"),
        nullable=False,
        default=DeactivationStatus.PENDING,
    )
    # سببُ الكبتن — اختياريٌّ ونصٌّ حرّ: من يترك يقول لماذا إن شاء، ولا يُحبس
    # خروجُه على قائمةٍ نختارها له
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # وسببُ المشرف عند الرفض — **مطلوبٌ في الخدمة** كسبب رفض المستند
    review_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<DeactivationRequest {self.user_id} ({self.status})>"
