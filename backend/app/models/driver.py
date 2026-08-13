from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import (
    DocumentReviewStatus,
    DocumentType,
    DriverStatus,
    GenderPreference,
)

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.vehicle import Vehicle


class Driver(UUIDMixin, TimestampMixin, Base):
    """امتداد لـ users لحساب الكبتن."""

    __tablename__ = "drivers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[DriverStatus] = mapped_column(
        pg_enum(DriverStatus, "driver_status"),
        nullable=False,
        default=DriverStatus.PENDING,
        index=True,
    )
    cliq_alias: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rating_avg: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0.00")
    )
    is_online: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    # `use_alter`: بين الجدولين مرجع متبادل (rides.driver_id هنا وهناك)،
    # فيُنشأ هذا القيد بعد الجدولين لا معهما
    current_ride_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    # تفضيلُ الكبتن **دائم** لا لكل رحلة (المرحلة 10-ج): الراكبة تختار لرحلةٍ
    # بعينها، والكبتن يقرر لعمله كلِّه — ولذلك مكانُه هنا لا على الرحلة
    gender_preference: Mapped[GenderPreference] = mapped_column(
        pg_enum(GenderPreference, "gender_preference"),
        nullable=False,
        default=GenderPreference.ANY,
        server_default=GenderPreference.ANY.value,
    )

    # رمزُ الإحالة (المرحلة 12-ح). **فريدٌ عالمياً لا per-country**: الرمزُ
    # يُقال في مكالمة، وواحدٌ في الأردن يطابق واحداً في ليبيا هو رمزٌ يذهب
    # لصاحب الحساب الخطأ. ويُولَّد عند إنشاء الكبتن — لا عند أول فتحةٍ للشاشة:
    # توليدٌ عند القراءة يحتاج قفلاً على صفٍّ لا يُكتب فيه شيءٌ آخر، وبغيره
    # تُنتج ضغطتان رمزين. و`nullable` لأن القائمين قبل الترحيلة يأخذونه فيها
    referral_code: Mapped[str | None] = mapped_column(
        String(16), nullable=True, unique=True, index=True
    )

    user: Mapped["User"] = relationship(back_populates="driver")
    vehicles: Mapped[list["Vehicle"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    documents: Mapped[list["DriverDocument"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<Driver {self.id} ({self.status})>"


class DriverDocument(UUIDMixin, TimestampMixin, Base):
    """مستندات الكبتن: مسار الملف + حالة مراجعة مستقلة لكل مستند.

    **صفٌّ واحد لكل نوع** يفرضه الفريد `(driver_id, doc_type)`: رفعُ نفس
    النوع مرةً أخرى **يستبدل** سابقه ويعود `pending`. البديل — تراكمُ صفوفٍ
    لنفس النوع — يجعل سؤال «هل رخصتُه مقبولة؟» بلا جواب واحد، ويجعل شاشة
    المراجعة تعرض ثلاث رخصٍ لا يُعرف أيُّها السارية. ورفعُ بديلٍ عن مستندٍ
    مرفوض هو الحالة المقصودة أصلاً.

    ولا يُلغي الاستبدالُ اعتمادَ الكبتن: تغييرُ حالته يمر من
    `services/drivers.set_status` وحدها (SPEC القسم 13/2)، والمستند الجديد
    يظهر `pending` في اللوحة لتراه المراجعة.
    """

    __tablename__ = "driver_documents"
    __table_args__ = (
        UniqueConstraint(
            "driver_id", "doc_type", name="uq_driver_documents_driver_doc_type"
        ),
    )

    driver_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[DocumentType] = mapped_column(
        pg_enum(DocumentType, "document_type"), nullable=False
    )
    # مسارٌ **نسبي** إلى `settings.document_storage_root` — انظر
    # `core/storage.py`. لا يُعرض لأحد ولا يُبنى منه رابط: الملف يُقرأ من
    # مسارٍ يتحقق من الملكية أولاً
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    # نوع المحتوى **المستنتج من بايتات الملف** لا المُعلن من العميل — به
    # تُخدَم القراءة بلا استنتاجٍ ثانٍ في كل طلب
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    review_status: Mapped[DocumentReviewStatus] = mapped_column(
        pg_enum(DocumentReviewStatus, "document_review_status"),
        nullable=False,
        default=DocumentReviewStatus.PENDING,
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    driver: Mapped["Driver"] = relationship(back_populates="documents")

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<DriverDocument {self.doc_type} ({self.review_status})>"


# المستندات التي لا يُعتمد كبتنٌ قبل قبولها كلها (SPEC القسم 12/1 و13/2).
# `VEHICLE_PHOTO` خارجها عمداً: صورةُ المركبة تُطمئن الراكب ولا تُثبت حقاً،
# والمستندُ القانوني للمركبة هو `VEHICLE_REGISTRATION` وهو داخلها.
REQUIRED_DOCUMENT_TYPES: tuple[DocumentType, ...] = (
    DocumentType.DRIVING_LICENSE,
    DocumentType.NATIONAL_ID,
    DocumentType.VEHICLE_REGISTRATION,
)
