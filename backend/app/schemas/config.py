from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.models.enums import CountryCode, Currency, VehicleCategory
from app.schemas.auth import AuthMethodResponse


class CountryConfigOut(BaseModel):
    country_code: CountryCode
    currency: Currency
    features: dict[str, bool]
    vehicle_categories: list[VehicleCategory]
    # بادئةُ الدولة وطولُ رقمها الوطني — من `core/phone.py` وحده، ليرسم
    # التطبيقان الحقل بلا كتابة «962» في كودهما
    dial_code: str
    national_number_length: int
    # ساعاتُ هدوء الحملات ومِنطقتُها الزمنية (القسم 10/13.6). عامّةٌ بطبيعتها:
    # تخبر المستخدم متى **لا** تصله الحملات، ولا يُقرأ منها سرّ. وتُنشر
    # لأن الواجهة لولاها تكتب رقماً من عندها فيخالف الجدول يوماً — والمنطقةُ
    # معها، وإلا قُرئت الساعة بتوقيت الجهاز لا بتوقيت الدولة.
    # و`null` تعني «لم تُضبط بعد» فلا تعرض الواجهةُ رقماً لا مصدر له
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_timezone: str | None = None
    # **المُحقِّق لهذه الدولة بعينها** (12-هـ) وقنواتُه بترتيبها.
    #
    # وُجد لأن قناةَ واتساب مفتاحُها per-country: فبلا هذا الحقل تقرأ شاشةُ
    # التسجيل مُحقِّقَ **الدولة الافتراضية** ثم يرسل المستخدمُ رمزاً من قناةٍ
    # أخرى — وهو بعينه عطبُ «ما يُعلن غيرُ ما يقع» الذي تكرر في هذا المشروع.
    # و`auth` أعلى الجواب يبقى للدولة الافتراضية: توافقٌ خلفيٌّ لا مصدرٌ ثانٍ.
    verification: str
    verification_channels: list[str] = []
    # **وطولُ الرمز معه per-country** — وهو تكملةُ الإصلاح نفسِه: كان
    # `verification` قد نُقل إلى صفِّ الدولة في 12-هـ **وبقي `otp_length` يُقرأ
    # من `auth` أي من الدولة الافتراضية**، فترسم الشاشةُ عددَ خاناتٍ لسوقٍ
    # وتتحقق الخلفيةُ بطول سوقٍ آخر. إصلاحٌ نصفُه ليس إصلاحاً.
    #
    # و`null` تعني مُحقِّقاً لا يأخذ رمزاً منّا (Firebase أو لا مُحقِّق).
    otp_length: int | None = None


class ConfigOut(BaseModel):
    """إعدادات عامة للواجهات (SPEC القسم 2).

    لا تحوي إلا ما هو عام بطبيعته: مفاتيح الميزات، العملات، والتوكن العام
    للخرائط. أي حقل سرّي في عقود المزودين لا يمر من هنا أبداً.
    """

    app: str
    auth: AuthMethodResponse
    countries: list[CountryConfigOut]
    providers: dict[str, dict[str, Any]]
    # الدولة التي تفترضها شاشاتُ ما قبل الدخول: لا حسابَ بعد فلا دولةَ
    # معروفة، والتصميم بلا منتقي دول. إعدادُ نشرٍ لا سرّ — مكانه `settings`
    # كـ`cors_origins` و`card_return_url`
    default_country_code: CountryCode
    # **قواعدُ التحقق منشورةً** (القسم ١٧.٣): يجلبها التطبيقُ ويخزّن آخرَ نسخةٍ
    # ليتحقق فوراً قبل وصول الرد وعند انقطاع الشبكة. مُشتقّةٌ من المخططات
    # برمجياً، ونصوصُها من السجل المركزي — فلا نسخةَ قواعدَ في التطبيق تفترق.
    validation: dict[str, dict[str, Any]]
