"""إعداداتُ مشاركة الرحلة لكل دولة (المرحلة 12-ي، SPEC القسم 5.12)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, SmallInteger, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin, pg_enum
from app.models.enums import CountryCode

# **صفرٌ يعني «لم تُقرَّر بعد» فتُخفى الميزة** — كما تُقرأ مبالغُ البقشيش
# (12-و) ومكافأةُ الإحالة (12-ح). ولا يُبذر رقمٌ يبدو قراراً ولم يقرّره أحد:
# نسبةُ الخصم مالٌ يقرّره المالك بعد أن يرى ما يقبضه الكبتن من رحلتين.
DEFAULT_DISCOUNT_PERCENT = Decimal("0.00")

# أرقامُ المطابقة الثلاثة (SPEC §5.12: «وثلاثتُها أرقامُ إعداداتٍ per-country لا
# ثوابتُ كود»). وقيمُها الافتراضيةُ **تشغيليةٌ لا مالية**، فلا يضرّ بذرُها:
# ممرٌّ ٢كم حول المسار، والتفافٌ لا يزيد ٧ دقائق على رحلة الأول، ونافذةُ
# انتظارٍ ٩٠ ثانية لظهور شريك.
DEFAULT_CORRIDOR_KM = Decimal("2.000")
DEFAULT_MAX_DETOUR_MINUTES = 7
DEFAULT_PARTNER_WAIT_SECONDS = 90


class RideSharingSetting(UUIDMixin, TimestampMixin, Base):
    """سياسةُ المشاركة لكل دولة — تُدار من اللوحة.

    **جدولٌ مستقلٌّ لا حقولٌ على `pricing_rules`**، وهذا ليس ذوقاً:
    `pricing_rules` مفتاحُها `(country, vehicle_category)`، والخصمُ **per-country**
    بقرار المالك الثالث. فوضعُه هناك يجعل للقيمة الواحدة بيتين يختلفان أوّلَ مرة
    يُحرَّر أحدُهما — وهي القاعدةُ نفسُها التي أبقت `dropoff_point` عموداً واحداً
    في 12-ب. ونفسُ سببِ استقلال `referral_settings` عن `wallet_settings`.
    """

    __tablename__ = "ride_sharing_settings"
    __table_args__ = (
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100 "
            "AND corridor_km >= 0 AND max_detour_minutes >= 0 "
            "AND partner_wait_seconds >= 0",
            name="ride_sharing_values_in_range",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), nullable=False, unique=True, index=True
    )

    # **نسبةٌ ثابتة لا حسابٌ بالمسافة المشتركة** (قرارُ المالك الثالث): الثابتُ
    # يُفهَم ويُعلَن، والمحسوبُ أعدلُ ولا يُشرح في شاشة. ومعايرتُها مقيَّدةٌ
    # بشرطٍ صريح: **ما يقبضه الكبتن من رحلتين أعلى بوضوحٍ مما يقبضه من منفردة**
    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=DEFAULT_DISCOUNT_PERCENT,
        server_default=text("0"),
    )

    # عرضُ الممرِّ حول مسار الرحلة الأولى: انطلاقُ الثاني ووجهتُه داخله
    corridor_km: Mapped[Decimal] = mapped_column(
        Numeric(6, 3),
        nullable=False,
        default=DEFAULT_CORRIDOR_KM,
        server_default=text("2"),
    )
    # سقفُ ما تطول به رحلةُ الأول — وهو الرقمُ الذي يحمي من قَبِل أولاً
    max_detour_minutes: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=DEFAULT_MAX_DETOUR_MINUTES,
        server_default=text("7"),
    )
    # كم ينتظر طالبُ المشاركة ظهورَ شريك قبل أن تُنفَّذ رحلتُه بالخصم وحدَها
    partner_wait_seconds: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=DEFAULT_PARTNER_WAIT_SECONDS,
        server_default=text("90"),
    )

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<RideSharingSetting {self.country_code} {self.discount_percent}%>"
