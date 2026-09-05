from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class SiteSettings(UUIDMixin, TimestampMixin, Base):
    """ما تعرضه الصفحةُ التعريفيةُ العامّة — **يُبدَّل من اللوحة بلا نشر**.

    **ولماذا جدولٌ جديدٌ ولا يُوسَّع القائم**: جداولُ الإعدادات في هذا المشروع
    **مكتوبةٌ بأعمدةٍ مسمّاة لكلِّ ميدان** (`payment_settings` ·
    `security_settings` · `map_settings` · `otp_settings`) **ولا مخزنَ
    مفتاح-قيمةٍ عامٌّ فيها يتّسع لـ`site.*`**. فالشرطُ في المواصفة («إن اتّسع»)
    **قِيس فلم يتّسع**، والبديلُ المكتوبُ فيها هو هذا الجدول.

    **وصفٌّ واحدٌ لا صفٌّ لكلِّ سوق** — بخلاف `feature_flags` و`promo_banners`.
    **والعلّةُ أن هذا موقعُ الشركة لا واجهةُ سوق**: عنوانٌ واحدٌ
    (`taxo.tajora.ly`) وجهةٌ واحدةٌ مالكة (`taxo-joly` — عمّان)، **والأردنُ هو
    البلدُ الوحيدُ المذكور فيه** بقرار المالك. وصفٌّ لكلِّ سوقٍ كان يَعِد بما
    لا يقع: صفحتان لا تُخدَمان من عنوانين.

    **والقفلُ بقيدٍ لا بعُرف**: `singleton` عمودٌ ثابتُ القيمة عليه فريدٌ، فلا
    يُكتب صفٌّ ثانٍ **ولو أخطأ نداءٌ** — وجدولُ إعداداتٍ بصفّين يجعل «أيُّهما
    يحكم؟» سؤالاً لا جواب له، وقد وقع في هذا المشروع من قبل.

    **ولا سرَّ هنا ولا مسارَ إلى سرّ**: كلُّ حقلٍ في هذا الجدول **يُنشر على
    بابٍ عامٍّ بلا جلسة** (`GET /public/site`). فما لا يصحّ أن يقرأه غريبٌ لا
    يُكتب فيه — بيانُ الاعتماد بيتُه `provider_credentials` مشفَّراً.
    """

    __tablename__ = "site_settings"
    __table_args__ = (
        CheckConstraint("singleton = TRUE", name="site_settings_singleton"),
    )

    #: **العمودُ الذي يمنع الصفَّ الثاني** — فريدٌ وقيمتُه محجوزةٌ بـ`CHECK`.
    singleton: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, unique=True
    )

    # ── 01 · Hero ──────────────────────────────────────────────────────────
    hero_title: Mapped[str] = mapped_column(String(120), nullable=False)
    hero_subtitle: Mapped[str] = mapped_column(String(240), nullable=False)
    #: «في الأردن الآن» — يُبدَّل يومَ يُفتح سوقٌ ثانٍ، بقرارِ إنسانٍ لا بحساب.
    hero_note: Mapped[str] = mapped_column(String(80), nullable=False)

    # ── الشريط الإعلاني ────────────────────────────────────────────────────
    #
    # **ثلاثةُ حقولٍ لا حقلان**: نصٌّ بلا مفتاحٍ يُخفى بتفريغه — **وتفريغُ نصٍّ
    # لإخفاء عنصرٍ يفقد النصَّ**، فمن أطفأه اليومَ يكتبه من جديدٍ غداً.
    announce_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    announce_text: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    announce_url: Mapped[str] = mapped_column(String(300), nullable=False, default="")

    # ── التواصل ────────────────────────────────────────────────────────────
    support_email: Mapped[str] = mapped_column(String(120), nullable=False)
    privacy_email: Mapped[str] = mapped_column(String(120), nullable=False)
    #: **روابطُ التواصل — الفارغُ لا يُرسم أيقونةً معطَّلة** (شرطُ المالك).
    social_facebook: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    social_instagram: Mapped[str] = mapped_column(
        String(300), nullable=False, default=""
    )
    social_tiktok: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    social_x: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    social_whatsapp: Mapped[str] = mapped_column(String(300), nullable=False, default="")

    # ── إظهار وإخفاء ───────────────────────────────────────────────────────
    #
    # **مخفيٌّ لا مطفأ**: المطفأُ يُرسم بشارة «قريباً» (وذاك مفتاحُ الميزة في
    # `feature_flags`، ولا يُنسخ هنا)، **والمخفيُّ لا يُرسم أصلاً**. وهما
    # معنيان مختلفان، وخلطُهما يجعل «قريباً» تعني «لا شيء».
    hidden_sections: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    hidden_cards: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    # ── الأسئلة الشائعة ────────────────────────────────────────────────────
    #: `[{"q": "...", "a": "...", "order": 1}]` — الترتيبُ من الحقل لا من موضع
    #: العنصر، فإعادةُ ترتيبٍ لا تعني إعادةَ كتابةِ المصفوفة.
    faq: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    # ── 11 · التحميل ───────────────────────────────────────────────────────
    #
    # **المفتاحُ نُقل من `landing/config.js` ولم يُخترع ثانياً** (شرطُ المالك):
    # كان ملفّاً على القرص يُبدَّل بنشرةٍ — فصار حقلاً يُبدَّل من اللوحة **ويصل
    # الزائرَ في دقيقة**. ولا مفتاحَ ثانٍ لهذا المفهوم في أيِّ موضع.
    #
    # **وقيمتان لا ثلاث**: `none` كانت في الملفّ وأُسقطت هنا **لأنها لم تُستعمل
    # قطّ**، ولأن «لا زرَّ بلا رابط» يغطّي حالتَها: رابطٌ فارغٌ يعطي شارةً
    # معطَّلة، وذاك أوضحُ للزائر من قسمٍ يختفي بلا أثر.
    distribution_mode: Mapped[str] = mapped_column(
        String(8), nullable=False, default="apk"
    )
    play_url_rider: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    play_url_driver: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    #: **فارغٌ حتى تُنشر نسخةُ iOS** — والفارغُ يعطي شارةً معطَّلةً لا زرّاً كاذباً.
    ios_url: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    #: صفحةُ APK غيرُ المفهرسة في وضع المتجر — **مطفأةٌ افتراضاً**.
    apk_page_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # ── السياسات ───────────────────────────────────────────────────────────
    #
    # **مطفأٌ افتراضاً بقرارِ المالك المكتوب**: «لا تنشر سياسةً ولا تعرضها على
    # مستخدمٍ قبل مراجعتي». والنصوصُ الثمانِ في `privacy_policies` **مسوّداتُ
    # وكيلٍ لم يقرأها إنسانٌ بعد**، والصفحتان تُبنيان وتبقيان خلف هذا المفتاح.
    #
    # **ولا يُغني عنه أن الوثيقةَ غيرُ منشورة**: النشرُ في `privacy_policies`
    # يخصّ التطبيقات، وهذا يخصّ **الويب** — ومفتاحٌ واحدٌ لمعنيين يفتح أحدَهما
    # بالآخر من حيث لا يُرى.
    policies_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # ── نصوصٌ طويلة ────────────────────────────────────────────────────────
    #: وصفُ الصفحة لمحرّكات البحث — يُبدَّل بلا نشر.
    seo_description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:  # pragma: no cover - تشخيصي
        return f"<SiteSettings mode={self.distribution_mode}>"
