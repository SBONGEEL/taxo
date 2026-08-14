from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import MONEY, Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode


class WalletSetting(UUIDMixin, TimestampMixin, Base):
    """حدود المحفظة لكل دولة — تُدار من اللوحة (SPEC القسم 7/9/13.6).

    حدود التحويل تحرس ميزةً معطّلة افتراضياً خلف `wallet_transfer_enabled`،
    وحدُّ السحب الأدنى يمنع إغراق المحاسب بطلبات لا تساوي كلفة تحويلها.
    قيمها بعملة الدولة المشتقة من `country_code` — لا عمود عملة هنا.
    """

    __tablename__ = "wallet_settings"
    __table_args__ = (
        CheckConstraint(
            "transfer_daily_limit >= 0 AND transfer_monthly_limit >= 0 "
            "AND min_withdrawal_amount >= 0 AND withdrawal_reserve_amount >= 0",
            name="wallet_limits_non_negative",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, unique=True, index=True
    )
    transfer_daily_limit: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000")
    )
    transfer_monthly_limit: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000")
    )
    min_withdrawal_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000")
    )
    # **الرصيدُ المحتجَز** (البند ١٣): يبقى في محفظته ولا يُسحب، ويخرج عند طلب
    # إلغاء التفعيل. **شرطٌ على السحب لا قيدٌ في الدفتر**: قيدٌ يُكتب لحجزه
    # يجعل الرصيدَ يكذب على صاحبه — يقرأ رقماً ناقصاً بلا أن يُدفع له.
    # وصفرٌ يعني «لا احتجاز» لا «احتجزْ صفراً»، كبقية أصفار هذا الجدول
    withdrawal_reserve_amount: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("0.000"), server_default=text("0")
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<WalletSetting {self.country_code}>"
