from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

# ما يبدأ به صفُّ دولةٍ جديد. ليس افتراضاً سخياً كأصفار `wallet_settings`:
# الصفر هنا يعني «لا مهلة» أي نزاعٌ فوري، وهو أسوأ ما يمكن أن يقع بالسكوت.
DEFAULT_CLIQ_CONFIRMATION_HOURS = 24


class PaymentSetting(UUIDMixin, TimestampMixin, Base):
    """سياساتُ الدفع لكل دولة — تُدار من اللوحة (SPEC القسم 6.2/13.6).

    اليوم حقلٌ واحد: **مهلةُ تأكيد حوالة كليك**. القسم 6.2/6 يقول «عند الرفض
    أو انقضاء مهلة التأكيد → `disputed`»، والرقمُ سياسةٌ لا قاعدة: مهلةٌ قصيرة
    تفتح نزاعاً على كبتنٍ نائم، وطويلةٌ تترك مال الراكب معلّقاً — ويختلف
    المناسبُ بين سوقٍ وسوق، فمكانُه جدولُ إعداداتٍ لا ثابتٌ في الكود.

    وهو **جدولٌ مستقل عن `wallet_settings`** لأنه ليس حدَّ محفظة: خلطُ
    السياستين في جدولٍ واحد يجعل اسمَه لا يصف محتواه، ويجرّ كلَّ سياسة دفعٍ
    قادمة إلى جدول المحفظة.
    """

    __tablename__ = "payment_settings"
    __table_args__ = (
        CheckConstraint(
            "cliq_confirmation_hours > 0",
            name="payment_cliq_confirmation_positive",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, unique=True, index=True
    )
    cliq_confirmation_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_CLIQ_CONFIRMATION_HOURS
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<PaymentSetting {self.country_code}>"
