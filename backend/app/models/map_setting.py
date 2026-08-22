"""إعداداتُ خريطةِ سوقٍ واحد (قرارُ المالك 2026-08-22).

**وهي للخريطة وحدَها لا للتوزيع** — وهذا هو الفرقُ الذي يحمل الجدولَ كلَّه.
`dispatch` يقرأ `SEARCH_RADIUS_KM` و`MAX_SEARCH_RADIUS_KM` من
`services/geo.py` **ثوابتَ في الكود**، لأنها قواعدُ المواصفة §5.3 لا تفضيلاتُ
سوق؛ وقد كُتب ذلك في `CLAUDE.md` صراحةً: أرقامُ التوزيع الثلاثةُ ثوابتُ وحدةٍ
لا إعدادات. **فلو صارت هذه الحقولُ تحكم التوزيعَ لصار مشرفٌ يوسّع مدى البحث
فيغيّر من يصله الطلبُ وكم ينتظر الراكب** — وهو تغييرُ سلوكِ سوقٍ من حقلِ عرض.

**وما تحكمه**: كم سيارةً يرى الراكبُ على خريطته وإلى أيِّ بُعد. سوقٌ كثيفٌ
يضيّق (خمسون سيارةً على شاشةِ هاتفٍ زحمةٌ لا معلومة)، وسوقٌ متفرّقٌ يوسّع
وإلا بدت الخريطةُ خاليةً وفيها كباتن.

**والصفرُ ليس «بلا حدّ» هنا** بخلاف `otp_settings`: صفرُ سياراتٍ **يُخفي
الميزة**، وصفرُ كيلومتراتٍ كذلك — فكلاهما مرفوضٌ بقيدٍ في القاعدة، ويُطفأ
العرضُ بمفتاحه لا بتصفيرِ رقمِه. **رقمٌ يعني شيئين لا يُقرأ**.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, pg_enum
from app.models.enums import CountryCode

# **مطابقةٌ لما كان مبنيّاً قبل الجدول**: `geo.SEARCH_RADIUS_KM` و`SEARCH_LIMIT`.
# فمن لا صفَّ له يرى ما كان يراه بالضبط — **جدولٌ جديدٌ لا يغيّر سلوكاً قائماً**
DEFAULT_NEARBY_RADIUS_KM = "3.0"
DEFAULT_NEARBY_MAX_COUNT = 50


class MapSetting(TimestampMixin, Base):
    """ما يراه الراكبُ على خريطته في سوقٍ واحد."""

    __tablename__ = "map_settings"
    __table_args__ = (
        CheckConstraint(
            "nearby_radius_km > 0 AND nearby_max_count > 0",
            name="map_settings_positive",
        ),
    )

    country_code: Mapped[CountryCode] = mapped_column(
        pg_enum(CountryCode, "country_code"), primary_key=True
    )

    nearby_radius_km: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text(DEFAULT_NEARBY_RADIUS_KM),
    )
    nearby_max_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text(str(DEFAULT_NEARBY_MAX_COUNT))
    )
