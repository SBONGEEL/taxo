"""البقشيش — هديةُ الراكب للكبتن (SPEC القسم 6.5، المرحلة 12-و).

**وليس أجرةً، وكلُّ ما في هذا الملف يتبع تلك الجملة**: لا يدخل `final_fare`،
ولا وعاءَ العمولة، **ولا يكون صفَّ `payments` أبداً** — «لا تُدفع الرحلةُ مرتين»
مجموعُ `OWING_PAYMENT_STATUSES` مقابل الأجرة، فصفُّ بقشيشٍ هناك يجعل رحلةً
مدفوعةً بالكامل تبدو مدفوعةً أكثر من أجرتها، أو يجعل بقشيشاً غيرَ مؤكَّدٍ يُقرأ
ديناً على الراكب.

**ولا عمودَ `status` ولا عمودَ `method`** — وهذا تبسيطٌ ظهر عند البناء لا سهو:

- **القناةُ المحفظةُ وحدها** في هذه المرحلة (رسمُ بوابةِ البطاقات على نصف دينارٍ
  يتجاوز البقشيشَ نفسه)، والمحفظةُ تستقر في **نفس المعاملة** — فلا حالةَ
  انتظارٍ يمكن أن توجد. ولو فشل الخصمُ لانسحبت المعاملةُ كلُّها ولم يبق صفٌّ
  أصلاً، أي أن قيمة `failed` **لا تُكتب أبداً**. وحالةٌ لا تُكتب هي بعينها
  `awaiting_confirmation` التي كسرت تأكيدَ الكاش في المرحلة 10: تعدادٌ يحمل
  قيمةً لا وجودَ لها يبني عليها من يقرؤه.
- فوجودُ الصفِّ **هو** أن المال تحرّك — نفسُ قاعدة `driver_subscriptions`: «لا
  صفَّ لاشتراكٍ لم يصل ماله».
- ويومَ تُضاف البطاقةُ يُضاف عمودُ `method` بافتراضٍ `wallet` في ترحيلته،
  فتُقرأ الصفوفُ القديمة صحيحةً بلا تخمين — وهذا أصدقُ من عمودٍ اليومَ بقيمةٍ
  واحدةٍ ممكنة.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin


class Tip(UUIDMixin, TimestampMixin, Base):
    """بقشيشٌ واحدٌ على رحلةٍ واحدة."""

    __tablename__ = "tips"
    __table_args__ = (
        CheckConstraint("amount > 0", name="tips_amount_positive"),
    )

    # **فريدٌ على الرحلة**: بقشيشٌ واحدٌ لكل رحلة، والحارسُ في القاعدة لا في
    # فحصٍ سابقٍ يمكن أن يُسبَق — نفسُ ما تفعله `ratings` بـ`(ride_id, rater_type)`
    ride_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rides.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # **الطرفان مكتوبان وإن كانا مشتقَّين من الرحلة**: قيدا الدفتر يقابلان هذا
    # الصفَّ بمالكٍ لكلٍّ منهما، و«كم بقشيشاً قبض هذا الكبتن» سؤالُ شاشة أرباحه
    # في كل فتحة — فقراءتُه ضمّاً على الرحلات عملٌ يتكرر بلا داعٍ
    rider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    # العملةُ من دولة الرحلة لا من العميل (SPEC القسم 4)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<Tip {self.amount} {self.currency} ride={self.ride_id}>"
