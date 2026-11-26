"""سجلُّ إصدارات التطبيقات — **البند ٨ (§39٫٨، §43)**.

## الرقمُ الذي يُقارَن هو `versionCode` لا اسمُ نسخة

**وهذا مقيسٌ في هذه الشجرة لا مفترَض**: `android/app/build.gradle` يشتقّ
`versionCode` **من عدد الإيداعات** ويترك `versionName` ثابتاً — قِيست الحزمتان
فكانتا `versionName "1.0"` و`"1.1"` **و`versionCode 392` كلتاهما**. **فاسمُ
النسخة زينةٌ، والرقمُ هو ما يفرّق بناءً عن بناء** عند أندرويد نفسِه.

**فلو قارنّا نصّاً بصيغة `1.2.3` لاخترعنا ترقيماً لا ينتجه شيءٌ في المشروع**،
ولاحتاج كلُّ تطبيقٍ مقارِنَ semver من عنده — **ثلاثُ نسخٍ من قاعدةٍ واحدة**.
والرقمُ عددٌ صحيحٌ يزيد أبداً، **والمقارنةُ تقع في الخلفية وحدَها**.

## وصفٌّ واحدٌ يحمل الرقمَ والحدَّ معاً — **ولا مفتاحَ نشر**

**الأربعةُ في §39٫٨ صفاتُ سجلٍّ واحد**: رقمُ الإصدار · أدنى إصدارٍ مقبول ·
رابطُ التحميل · نصُّ «ما الجديد». **والسياسةُ القائمةُ هي صفُّ أعلى رقمٍ
موجود** — فكلُّ قرارِ إصدارٍ يذكر الحدَّ معه، **ولا يبقى حدٌّ قديمٌ ساكناً
يُنسى من كتبه**.

**ولا `is_published`**: صفٌّ موجودٌ = سياسةٌ قائمة. **وحالةٌ ثالثةٌ («موجودٌ
ولا يعمل») تُنسى مطفأةً** فيُقرأ السجلُّ حياً وهو ليس كذلك — والذي يمنع صفّاً
يشير إلى حزمةٍ غير موجودة هو **فحصُ الرابط قبل الحفظ** (§39٫٨: «ولا يُقفَل
أحدٌ خارج التطبيق بلا رابط تحميلٍ صالحٍ يُفحص قبل الحفظ»).

## وغيابُ السجلِّ لا يقفل أحداً

**تطبيقٌ لا صفَّ له يُقرأ «لا تدخّل»** لا «كلُّ النسخ مرفوضة» — والقاعدةُ
العامّة «الغيابُ يعطّل» تعني هنا **تعطيلَ الحجب** لا تعطيلَ التطبيق. وهي
المرآةُ نفسُها التي جعلت `country_visible` تُقرأ ظاهرةً عند الغياب.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, pg_enum
from app.models.enums import ClientApp, ReleasePlatform, ReleaseSource

#: أقصى مدّةٍ لكتم التنبيه الاختياريّ — شهرٌ. وما فوقه «لا يعود أبداً» بصيغةٍ
#: أخرى، **وكتمٌ أبديٌّ يُكتب بابَ إطفاءٍ لا حقلَ مدّة**.
MAX_REMINDER_HOURS = 720


class AppRelease(Base):
    """إصدارٌ واحدٌ من تطبيقٍ واحد، ومعه الحدُّ الذي يفرضه."""

    __tablename__ = "app_releases"
    __table_args__ = (
        # **لا رقمان متساويان لتطبيقٍ واحدٍ على نظامٍ واحد**: الرقمُ هو الهوية
        # عند أندرويد، وصفّان به يجعلان «الأخير» غيرَ معرَّف. **والنظامُ في
        # المفتاح** (2026-10-12): رقمُ iOS يُرقَّم وحدَه، فيلتقي برقم أندرويد
        # **والمتجرُ في المفتاح** (٢٠٢٦-١١-٢٠): الحزمةُ نفسُها برقمها تُنشر في Play وفي Galaxy Store — **صفٌّ لكلٍّ منهما ليس تكراراً**
        UniqueConstraint(
            "app",
            "platform",
            "source",
            "build",
            name="uq_app_releases_app_platform_source_build",
        ),
        # **ولا حدٌّ فوق الإصدار نفسِه**: يُقفل صاحبُ أحدث حزمةٍ خارجَ تطبيقه
        # ولا شيءَ يحمّله ليخرج — وهو القفلُ الذي لا مخرجَ منه
        CheckConstraint(
            "min_supported_build <= build", name="ck_app_releases_min_within"
        ),
        CheckConstraint("build > 0", name="ck_app_releases_build_positive"),
        CheckConstraint(
            "open_map_min_build IS NULL OR open_map_min_build > 0",
            name="ck_app_releases_open_map_positive",
        ),
        CheckConstraint(
            "min_supported_build > 0", name="ck_app_releases_min_positive"
        ),
        CheckConstraint(
            f"reminder_hours >= 0 AND reminder_hours <= {MAX_REMINDER_HOURS}",
            name="ck_app_releases_reminder_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    app: Mapped[ClientApp] = mapped_column(
        pg_enum(ClientApp, "client_app"), nullable=False, index=True
    )
    #: نظامُ الحزمة — **والحكمُ والرابطُ لكلِّ تطبيقٍ على كلِّ نظام** (قرارُ المالك
    #: 2026-10-12): الصفُّ الحاكمُ لـ(تطبيق، نظام) هو أعلى رقمٍ فيهما، **ورابطُه هو
    #: ما يفتحه زرُّ «تحديث»** — فالتبديلُ من صفحة التحميل إلى المتجر تعديلُ حقلٍ في اللوحة.
    platform: Mapped[ReleasePlatform] = mapped_column(
        pg_enum(ReleasePlatform, "release_platform"),
        nullable=False,
        default=ReleasePlatform.ANDROID,
        server_default=ReleasePlatform.ANDROID.value,
    )
    #: **المتجرُ الذي ثبّت الحزمة** (أمرُ المالك ٢٠٢٦-١١-٢٠ السابع) — `default` = Google Play والموقع، **وهو كلُّ صفٍّ قبله**.
    #: ومتجرٌ بلا صفٍّ يُحكم بصفِّ `default` (`releases.current`).
    source: Mapped[ReleaseSource] = mapped_column(
        pg_enum(ReleaseSource, "release_source"),
        nullable=False,
        default=ReleaseSource.DEFAULT,
        server_default=ReleaseSource.DEFAULT.value,
    )
    #: `versionCode` الحزمة — عددٌ صحيحٌ يزيد أبداً (عددُ الإيداعات).
    build: Mapped[int] = mapped_column(Integer, nullable=False)
    #: **أدنى غلافٍ تُرسم فيه الخريطةُ المفتوحة** (SPEC §١٠٥/٥، ٢٠٢٦-١١-١٦). الغلافُ يحمّل الواجهةَ من خادمنا،
    #: **فما يُرفع من الواجهة يصل كلَّ غلافٍ قديمٍ وجديد** — والمفتاحُ `open_map_display` وحدَه لا يفرّق بينهما.
    #: فارغاً (الافتراض) لا يُرسم MapLibre في أيِّ غلاف ولو اشتعل المفتاح؛ والمتصفّحُ لا غلافَ له فيحكمه المفتاحُ وحدَه.
    open_map_min_build: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: أدنى حزمةٍ تُقبل. ما دونها **شاشةُ تحديثٍ لا تُغلق**.
    min_supported_build: Mapped[int] = mapped_column(Integer, nullable=False)
    #: من أين تُحمَّل — **ويُفحص قبل الحفظ**، فلا قفلَ بلا مخرج.
    download_url: Mapped[str] = mapped_column(String(500), nullable=False)
    #: «ما الجديد» بالعربية — يقرؤه صاحبُ الهاتف لا نحن.
    release_notes: Mapped[str] = mapped_column(Text, nullable=False)
    #: **حدٌّ أدنى لكلِّ دولة** (SPEC §43، ٢٠٢٦-١١-٢٦): `{"JO": 1573}` يحلّ محلَّ `min_supported_build` **في تلك الدولة وحدَها** —
    #: فيصير التحديثُ إلزاميّاً في سوقٍ ويبقى اختياريّاً في غيره. **والدولةُ تأتي من التطبيق** (آخرُ سوقٍ عرفه، محفوظةً لإقلاعٍ قادم)،
    #: ومن لا تُعرف دولتُه يُحكم بالحدِّ العامّ. وكلُّ قيمةٍ لا تتجاوز `build` (تُفحص في الخدمة)، كالحدِّ العامِّ بقيده.
    country_min_builds: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    #: كم يسكت التنبيهُ الاختياريُّ بعد إغلاقه — **مضبوطٌ من اللوحة** (§39٫٨). **و0 = «في كلِّ فتح»**: «لاحقاً» يكتمه في الفتح نفسِه
    #: ويعود في الإقلاع التالي (٢٠٢٦-١١-٢٦، مسلكُ غلاف 772 بعينه).
    reminder_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=24, server_default="24"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
