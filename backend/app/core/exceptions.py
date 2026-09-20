from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core import validation_errors
from app.core.request_id import HEADER as REQUEST_ID_HEADER
from app.core.request_id import request_id_of

logger = logging.getLogger(__name__)


# **الرسالةُ تُكتب لمن يقرؤها** (2026-08-14، بعد أن قرأ راكبٌ على هاتفه «راجع
# عقد Firebase في لوحة الإدارة»). ولا يعني ذلك «لا تذكر العقود» بل قسمةً بحسب
# من يصل إليه الخطأ: ما يظهر في تطبيقَي الراكب والكبتن يقول **ما جرى وما يفعله
# القارئ**، وما لا يظهر إلا في اللوحة (التحويل الآلي، اختبارُ الاتصال، مفتاحُ
# التشفير) يبقى بلغة المشرف — فتلك جملتُه هو. والرمزُ (`code`) هو ما يبحث به
# المشرفُ في السجل، فلا يضيع التشخيص.


class AppError(Exception):
    """خطأ أعمال معروف — يُترجم لاستجابة JSON موحّدة."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"
    message: str = "حدث خطأ"

    def __init__(self, message: str | None = None, **extra: object) -> None:
        self.message = message or self.message
        self.extra = extra
        super().__init__(self.message)


class InvalidCredentials(AppError):
    """**رسالةٌ لا تسمّي بابَ الدخول** (تصحيحٌ مقيس 2026-08-21).

    كانت «رقم الهاتف أو كلمة المرور غير صحيحة»، **واللوحةُ تُدخَل باسمِ مستخدم**
    وحسابا الإنتاج بلا رقمٍ أصلاً — فمن ردَّته يقرأ أن رقمَه خطأ ولا رقمَ أرسل،
    **فيبحث في الجهة الخاطئة**. وقد وقع ذلك فعلاً.

    وتُستعمل أيضاً حيث لا هويةَ في السؤال أصلاً — كإطفاء العامل الثاني بكلمة
    المرور — فتسميةُ «الرقم» هناك أبعدُ عن الحال.

    **ولا تفرّق بين «لا حساب» و«كلمةٌ خطأ»**: التفريقُ يهدي من يجرّب إلى أيِّ
    الاسمين موجود، وهو ما يمنعه `_DUMMY_HASH` في مسار الكلمة توقيتاً.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_credentials"
    message = "بيانات الدخول غير صحيحة"


class InvalidToken(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_token"
    message = "جلسة غير صالحة أو منتهية"


class InvalidOtpCode(InvalidCredentials):
    """رمز تحقق خاطئ أو منتهٍ أو لم يُطلب أصلاً (المرحلة 8).

    رسالةٌ واحدة للحالات الثلاث عمداً: التفريق بينها يخبر المخمّن أيَّ الأرقام
    طُلب لها رمزٌ حيّ الآن.
    """

    code = "invalid_otp"
    message = "رمز التحقق غير صحيح أو انتهت صلاحيته"





class HandoffBlockedByActiveWork(AppError):
    """تبديلٌ أثناء عملٍ قائم — **يُرفض ويُقال سببُه**.

    كبتنٌ في رحلةٍ جارية أو راكبٌ في رحلةٍ نشطة: التبديلُ يترك الطرفَ الآخر
    ينتظر شاشةً لا تتحدّث. **والزرُّ يقول لماذا لا يعمل الآن** بدل أن يكون
    معطَّلاً بلا سبب — وهي قاعدةُ «زرٌّ معطَّلٌ يقول سببَه خيرٌ من زرٍّ يعمل ثم
    يرتدّ».
    """

    status_code = 409
    code = "handoff_blocked_by_active_work"
    message = "لا يمكن التبديل الآن — أنهِ رحلتك الجارية أولاً"

class AmbiguousRole(AppError):
    """حسابٌ بدورين بلغ موضعاً يقرّر **معنىً** بالدور — ولا قرارَ فيه بعد.

    **ولا قيمةَ افتراضيةَ هنا ولا «أوّلُ متاح»** (شرطُ المالك 2026-08-19): هذه
    مواضعُ تقرّر *ما هو الشيء* لا *من يجوز له* — أيُّ محفظة، ومن ألغى، وأيُّ
    برنامجِ إحالة، وأيُّ تطبيقٍ يعود إليه الدافع، وأيُّ سجلِّ رحلات. وتخمينُ
    أحدِ الدورين فيها يكتب مالاً في المكان الخطأ **بصمت**، أو يُخفي عن صاحبه
    نصفَ تاريخه بلا أثر.

    **وكلُّ موضعٍ رمزُه باسمه** لا رمزٌ عامّ: المشرفُ الذي يقرأ السجلَّ يحتاج أن
    يعرف **أيُّ قرارٍ غاب**، لا أن حساباً كان بدورين.

    وهي مستحيلةُ الوقوع اليوم: ترحيلةُ `0046` تنقل كلَّ حسابٍ بدورٍ واحد، ولا
    مسارَ يمنح ثانياً بعد. تبيت يومَ يُفتح بابُ المنح — وهو موضعُ القرار.
    """

    status_code = 409
    code = "ambiguous_role"

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

class InvalidOtpTemplate(AppError):
    """قالبُ رسالةِ رمزٍ يخالف شروطَ القناة.

    **الرسالةُ تسمّي القالبَ والشرط معاً**: «ينقص متغيّر» وحدَها تترك المشرفَ
    يخمّن أيَّ حقلٍ من الحقلين يعني، وهما على شاشةٍ واحدة.

    و`status_code` 422 لأنه ردٌّ على قيمةٍ أرسلها، لا على صلاحيةٍ ينقصها.
    """

    status_code = 422
    code = "invalid_otp_template"

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field

class WeakPassword(AppError):
    """كلمةُ مرورٍ مرفوضةٌ بالسياسة لا بالطول (`core/password_policy.py`).

    **رمزٌ واحدٌ ورسائلُ ثلاث**: المشرفُ يبحث في السجل عن «كلمة مرور ضعيفة»
    كصنفٍ واحد، وصاحبُ الكلمة يحتاج أن يعرف **أيَّها** ليختار غيرها. وثلاثةُ
    رموزٍ تجزّئ عدّاً لا يُسأل مجزّأً.

    **ولا تكشف الرسالةُ القائمة**: «من الأكثر شيوعاً» تكفي لاختيار غيرها، ولا
    تخبر أحداً بما فيها — وقائمةٌ معروفةٌ دليلُ تخمينٍ مرتَّب.
    """

    # `422` رقماً كـ`InvalidInput` أدناه: اسمُ Starlette للثابت مهجورٌ ويطبع
    # تحذيراً عند كل استيراد، والرقمُ لا يهجُر
    status_code = 422
    code = "weak_password"
    message = "كلمة المرور ضعيفة — اختر غيرها"


class PasswordTooCommon(WeakPassword):
    message = "كلمة المرور هذه من الأكثر شيوعاً — اختر غيرها"


class PasswordIsPhone(WeakPassword):
    message = "لا تجعل كلمة المرور رقمَ هاتفك — من يعرف رقمك يعرفها"


class PasswordTooRepetitive(WeakPassword):
    message = "كلمة المرور تكرارٌ لحرفٍ أو نمطٍ قصير — اختر غيرها"


class AccountNotRegistered(AppError):
    """رمزٌ صحيح لرقمٍ لا حساب له — الدخول بـ OTP لا يُنشئ حساباً ضمناً.

    الكشف هنا لا يُعدّ تعداداً للحسابات: صاحب الطلب أثبت ملكيته للرقم بالرمز.
    """

    status_code = status.HTTP_404_NOT_FOUND
    code = "account_not_registered"
    message = "لا يوجد حساب بهذا الرقم — أنشئ حساباً أولاً"


class AccountBlocked(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "account_blocked"
    message = "هذا الحساب محظور"


class AccountClosed(AppError):
    """**أغلقه صاحبُه** — وهو غيرُ المحظور، ورمزٌ ثانٍ لأن الجملةَ ثانية.

    **ورمزٌ واحدٌ لهما يقول لمن أغلق حسابَه إنه «محظور»** — تهمةٌ لا حال،
    **ويقرؤها الدعمُ فيبحث عن قرارِ حظرٍ لا وجودَ له**.
    """

    status_code = status.HTTP_403_FORBIDDEN
    code = "account_closed"
    message = "هذا الحساب مُغلقٌ بطلب صاحبه"


class PermissionDenied(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "لا تملك صلاحية هذا الإجراء"


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "العنصر غير موجود"


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "تعارض في البيانات"


class PhoneAlreadyRegistered(Conflict):
    code = "phone_already_registered"
    message = "رقم الهاتف مسجّل مسبقاً"


class EmailAlreadyRegistered(Conflict):
    """بريدٌ **مُثبَتٌ** على حسابٍ آخر (قرارُ المالك 2026-08-31).

    **والفهرسُ الفريدُ وحدَه لا يكفي**: هو يمنع الازدواجَ ولا يقول شيئاً — من
    اصطدم به قرأ **٥٠٠** بلا سطرٍ يفهمه، وهي بعينها «رفضٌ بلا مخرج».
    **فالفحصُ قبله يعطي الرسالة، والفهرسُ يبقى حارساً للسباق.**
    """

    code = "email_already_registered"
    message = "هذا البريد مسجَّل على حسابٍ آخر"


class InvalidInput(AppError):
    status_code = 422  # Unprocessable Content — نفس ما يعيده FastAPI للتحقق
    code = "invalid_input"
    message = "بيانات غير صالحة"


class OutsideServiceArea(InvalidInput):
    """نقطةٌ خارج نطاق خدمة السوق — **حدٌّ بالبلد لا بالمسافة**.

    **واسمُ الدولة من بيته لا مخبوزاً هنا** (`core/currency.COUNTRY_NAME`):
    نصٌّ يكتب «الأردن» حرفاً يكذب في السوق الثاني يومَ يُفتح.
    """

    code = "outside_service_area"
    message = "هذه الوجهة خارج نطاق خدمتنا"

    def __init__(self, country_code: object | None = None) -> None:
        name = _country_name(country_code)
        super().__init__(
            f"هذه الوجهة خارج نطاق خدمتنا — اختر مكاناً داخل {name}."
            if name
            else self.message
        )


class ServiceAreaUndeclared(AppError):
    """سوقٌ بلا صندوقٍ مصرَّح — **يقف ولا يُقرأ سلامة**.

    غيرُ بالغةٍ عملياً: اختبارُ الاكتمال يمنع شحنَ سوقٍ بلا صندوق. وبقاؤها
    هو الفرقُ بين «لا حدَّ لهذا السوق» و«الحدُّ لم يُصرَّح» — **وهما حالان
    لا يحملهما صمتٌ واحد**.
    """

    status_code = 503
    code = "service_area_undeclared"
    message = "نطاقُ الخدمة لهذا السوق غيرُ مضبوط — راجع الدعم"


def _country_name(country_code: object | None) -> str | None:
    """يُقرأ متأخّراً كسراً لدورةِ استيراد: `currency` يستورد `enums` وحدَه."""
    if country_code is None:
        return None
    from app.core.currency import COUNTRY_NAME
    from app.models.enums import CountryCode

    try:
        return COUNTRY_NAME[CountryCode(country_code)]
    except (KeyError, ValueError):
        return None


class RateLimited(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "محاولات كثيرة — حاول لاحقاً"


class FeatureNotAvailable(AppError):
    status_code = status.HTTP_501_NOT_IMPLEMENTED
    code = "feature_not_available"
    message = "هذه الميزة غير مفعّلة بعد"


class PricingRuleMissing(AppError):
    """لا تسعيرة لهذه الفئة في هذه الدولة — لا يجوز الاجتهاد بسعر افتراضي."""

    status_code = status.HTTP_409_CONFLICT
    code = "pricing_rule_missing"
    message = "لا توجد تسعيرة معتمدة لهذه الفئة في بلدك"


class RoutingUnavailable(AppError):
    """عقد Mapbox غير مُدخل أو غير مفعّل من صفحة العقود."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "routing_unavailable"
    message = "تعذّر حساب المسار الآن. حاول بعد قليل."


class RoutingFailed(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "routing_failed"
    message = "تعذّر حساب المسار بين النقطتين"


class RideAlreadyActive(Conflict):
    code = "ride_already_active"
    message = "لديك رحلة جارية بالفعل"


class WomenServiceUnavailable(Conflict):
    """طُلب تفضيلُ جنسٍ في دولةٍ خدمتُها النسائية مطفأة (المرحلة 10-ج)."""

    code = "women_service_unavailable"
    message = "خدمة التوصيل النسائي غير مفعّلة في هذه الدولة"


class MultiStopUnavailable(Conflict):
    """طُلبت محطاتٌ وسيطة في دولةٍ مفتاحُها مطفأ (المرحلة 12-ب).

    ولا يُبتلع صامتاً بحذف المحطات: راكبٌ طلب ثلاث وجهاتٍ فسار الكبتن إلى
    واحدة أسوأ من طلبٍ يُرفض بسببه.
    """

    code = "multi_stop_unavailable"
    message = "تعدد الوجهات غير مفعّل في هذه الدولة"


class CancelReasonNotApplicable(Conflict):
    """سببُ «الجنس لا يطابق» على رحلةٍ لم يُطلب فيها جنسٌ أصلاً.

    ولا يُقبل صامتاً: هو السبب الذي يُسقط رسوم الإلغاء ويُدخل بلاغاً على
    حسابٍ آخر، فقبولُه بلا محلٍّ يجعله باباً لتفادي الرسوم ووسمِ الأبرياء.
    """

    code = "cancel_reason_not_applicable"
    message = "سبب الإلغاء لا ينطبق على هذه الرحلة"


class InvalidRideTransition(Conflict):
    code = "invalid_ride_transition"
    message = "لا يمكن تنفيذ هذا الإجراء على حالة الرحلة الحالية"


class RideOfferExpired(Conflict):
    """لا يقبل الرحلةَ إلا الكبتنُ المعروضة عليه الآن، وضمن مهلته."""

    code = "ride_offer_expired"
    message = "انتهت مهلة هذا الطلب أو عُرض على كبتن آخر"


class FeatureDisabled(AppError):
    """ميزة مبنيّة لكنها مطفأة لهذه الدولة من `feature_flags`.

    تختلف عن `FeatureNotAvailable` (501): تلك ميزة لم تُبنَ بعد، وهذه مبنية
    وقرارُ إطفائها إداري — فالجواب 403 لا 501.
    """

    status_code = status.HTTP_403_FORBIDDEN
    code = "feature_disabled"
    message = "هذه الميزة غير مفعّلة في بلدك"


class WalletFrozen(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "wallet_frozen"
    message = "المحفظة مجمّدة — راجع الدعم"


class InsufficientBalance(Conflict):
    code = "insufficient_balance"
    message = "الرصيد غير كافٍ"


class WalletLimitExceeded(Conflict):
    """حد التحويل اليومي/الشهري أو الحد الأدنى للسحب (SPEC القسم 7/9)."""

    code = "wallet_limit_exceeded"
    message = "تجاوزت الحد المسموح"


class InvalidStatusTransition(Conflict):
    """انتقال غير مسموح في طلب شحن أو سحب."""

    code = "invalid_status_transition"
    message = "لا يمكن تنفيذ هذا الإجراء على حالة الطلب الحالية"


class InvalidPaymentTransition(Conflict):
    """انتقال غير مسموح في آلة حالات الدفعة (SPEC القسم 4)."""

    code = "invalid_payment_transition"
    message = "لا يمكن تنفيذ هذا الإجراء على حالة الدفعة الحالية"


class UnsupportedOrderPurpose(Conflict):
    """طلبُ دفعٍ مدفوعٌ بغرضٍ لا تسوّيه هذه القناة — **يُرفض ولا يُقيَّد**.

    كان فرعُ التسوية في `card_payments.apply_state` ينتهي بـ`else:` يشحن المحفظة،
    فكلُّ غرضٍ لا يعرفه يصير مالاً في محفظة صاحب الطلب بلا خطأ (`SPEC-DELIVERY.md`
    §D7). والرسالةُ بلغة المشرف: لا يبلغها راكبٌ إلا بعطبٍ في الخلفية نفسِها.
    """

    code = "unsupported_order_purpose"
    message = "غرضُ طلب الدفع لا تسوّيه هذه القناة — لم يُقيَّد شيء"


class RideNotPayable(Conflict):
    """لا تُدفع رحلةٌ لم تكتمل — شاشة الدفع تلي `completed` (SPEC القسم 5)."""

    code = "ride_not_payable"
    message = "لا يمكن الدفع قبل اكتمال الرحلة"


class RideAlreadyPaid(Conflict):
    """مجموع الدفعات القائمة يغطي `final_fare` — لا مبلغ متبقٍّ."""

    code = "ride_already_paid"
    message = "هذه الرحلة لها دفعة قائمة تغطي قيمتها"


class SubscriptionAlreadyPurchased(Conflict):
    """نفس مفتاح عدم التكرار وصل مرتين — الاشتراك مشترى فعلاً (SPEC القسم 14)."""

    code = "subscription_already_purchased"
    message = "هذه العملية نُفّذت بالفعل"


class NoSubscriptionToCancel(Conflict):
    """لا تغطيةَ قائمةً تُلغى (§38).

    **ولا يُقرأ «أُلغي» عن لا شيء**: زرٌّ يُجيب بنجاحٍ وهو لم يفعل شيئاً يعلّم
    المشرفَ أن الإلغاء وقع — ثمّ يجد الكبتنَ يعمل.
    """

    code = "no_subscription_to_cancel"
    message = "لا اشتراك ساري لهذا الكبتن"


class RatingNotAllowed(Conflict):
    """تقييمٌ لرحلة لم تكتمل، أو من ليس طرفاً فيها (SPEC القسم 5.9)."""

    code = "rating_not_allowed"
    message = "لا يمكن تقييم هذه الرحلة"


class AlreadyRated(Conflict):
    code = "already_rated"
    message = "سبق أن قيّمت هذه الرحلة"


class UnsupportedDocument(InvalidInput):
    """نوع ملفٍ لا نقبله — والحكم على **محتواه** لا على ما ادّعاه العميل."""

    code = "unsupported_document"
    message = "نوع الملف غير مدعوم — الصور (JPEG/PNG/WebP) وملفات PDF فقط"


class DocumentTooLarge(AppError):
    """تجاوز الملف السقف — 413 لا 422: الحجم ليس خطأ صياغة.

    الرقم صريحٌ لا ثابتُ starlette: الاسم تبدّل بين إصدارَيه
    (`REQUEST_ENTITY_TOO_LARGE` ← `CONTENT_TOO_LARGE`) والرقم لم يتبدّل.
    ونفس ما فعله `InvalidInput` مع 422.
    """

    status_code = 413
    code = "document_too_large"
    message = "حجم الملف أكبر من المسموح"


class DocumentFileMissing(NotFound):
    """الصفُّ موجود وملفُّه ليس على القرص — عطلٌ لا مدخلٌ خاطئ."""

    code = "document_file_missing"
    message = "تعذّر العثور على ملف المستند"


class DocumentsIncomplete(Conflict):
    """اعتمادُ كبتنٍ قبل اعتماد مستنداته المطلوبة (SPEC القسم 13/2)."""

    code = "documents_incomplete"
    message = "لا يُعتمد الكبتن قبل اعتماد مستنداته المطلوبة"


class InvalidTotpCode(InvalidCredentials):
    """رمزُ العامل الثاني خاطئ أو مستعمَل (SPEC القسم 14.1، المرحلة 12-د).

    401 كأختِها لا 422: الرمزُ الصحيحُ صياغةً والخاطئُ قيمةً ليس مدخلاً فاسداً
    بل بيانَ اعتمادٍ لم يُقبَل. **ونصُّها واحدٌ للخاطئ وللمستعمَل**: من يعرف
    أن رمزَه «سبق استعمالُه» يعرف أنه كان صحيحاً.
    """

    code = "invalid_totp"
    message = "رمز التحقق الثنائي غير صحيح أو انتهت صلاحيته"


class TotpEnrollmentRequired(AppError):
    """الإلزامُ مشتعلٌ وصاحبُ الحساب بلا عامل — 403 على كل مسارٍ إداريّ.

    يدخل بكلمة مروره ويجد كلَّ بابٍ مردوداً إلا بابَ التسجيل. والحارسُ يقرأ
    الصفَّ في كل طلبٍ كما يقرأ `is_blocked`، فلا مطالبةٌ تعيش في توكن.
    """

    status_code = status.HTTP_403_FORBIDDEN
    code = "totp_enrollment_required"
    message = "الدخول إلى اللوحة يستلزم تسجيل التحقق الثنائي أولاً"


class TotpNotEnrolled(Conflict):
    code = "totp_not_enrolled"
    message = "لا يوجد تحقق ثنائي مسجّل على هذا الحساب"


class TotpAlreadyEnrolled(Conflict):
    """إعادةُ التسجيل على عاملٍ مؤكَّد — مخرجُها الإطفاءُ برمزٍ حاضر.

    ولو مرّت لكانت «أعد التسجيل» طريقاً لتبديل العامل من جلسةٍ مسروقة بلا
    رمزٍ واحد.
    """

    code = "totp_already_enrolled"
    message = "للحساب تحققٌ ثنائيٌّ مسجّل — أطفئه أولاً"


class TotpEnforcementActive(Conflict):
    """إطفاءُ العامل وقتَ الإلزام — مفتاحٌ يُخرج منه كلُّ مشرفٍ ليس إلزاماً."""

    code = "totp_enforcement_active"
    message = "لا يمكن إطفاء التحقق الثنائي وهو مُلزَمٌ على دورك"


class TotpRecoveryProofRequired(Conflict):
    """إشعالُ الإلزام قبل إثبات أن الاسترداد يعمل (قرارُ المالك).

    الشرطُ على **المشرف الطالب نفسه**: عاملٌ مؤكَّد ورمزُ استردادٍ جُرِّب فعلاً.
    """

    code = "totp_recovery_proof_required"
    message = "أثبت أن رمز الاسترداد يعمل قبل إلزام الجميع بالتحقق الثنائي"


def register_exception_handlers(app: FastAPI) -> None:
    """المعالجاتُ **الأربعةُ** التي تغطّي كلَّ مخارج الخلفية (SPEC القسم ١٧.١).

    **أربعةٌ لا واحد، لأن للخطأ أربعةَ منابع**: أخطاءُ الأعمال التي نرفعها
    (`AppError`)، وأخطاءُ التحقق التي يرفعها Pydantic قبل أن يصل الطلبُ إلى
    سطرٍ من كودنا (`RequestValidationError`)، وما ترفعه FastAPI نفسُها
    (`HTTPException`: مسارٌ غيرُ موجود، طريقةٌ غيرُ مسموحة). **وما لم يتوقّعه أحد**
    (`Exception`) — وهو الرابعُ، أُضيف 2026-09-20 بعد أن كان يخرج نصّاً عارياً
    بلا `code` ولا `message`. وتغطيةُ الأول وحدَه — وهو ما كان — تترك الثلاثةَ
    الباقيةَ تخرج بشكل FastAPI، وهو **شكلٌ ثانٍ** يقرؤه العميلُ خطأً.
    """

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        # **الحقلُ `message` لا `detail`** (عقدُ الأخطاء، 2026-08-18): كان
        # `detail`، وهو اسمُ FastAPI نفسِه في الـ422 حيث تكون قيمتُه **مصفوفةً
        # لا نصّاً** — فيقرأ العميلُ كائناً ويعرض `[object Object]`. اسمٌ واحدٌ
        # لمعنيين هو العطبُ نفسُه لا تسميتُه.
        body: dict[str, object] = {"code": exc.code, "message": exc.message}
        if exc.extra:
            body |= exc.extra
        headers = {}
        if isinstance(exc, RateLimited) and "retry_after" in exc.extra:
            headers["Retry-After"] = str(exc.extra["retry_after"])
        return JSONResponse(status_code=exc.status_code, content=body, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """٤٢٢ بشكل العقد — **ومعالجٌ دائمٌ لا مؤقت**.

        **ولولاه لا يُشخَّص شيء**: بغيره يخرج جسمُ FastAPI الافتراضي
        (`{"detail": [ … ]}`) فلا يجد العميلُ نصّاً يعرضه، **ولا يُكتب سطرٌ في
        السجل أصلاً** — فيقرأ من يُشخِّص «422» بلا حقلٍ ولا سبب. وهو ما وقع
        فعلاً في `POST /drivers/me/vehicles`.

        **ويُسجَّل الجسمُ الوارد محجوبَ الأسرار** (القسم ١٧.٤): الحقلُ المرفوض
        وحدَه لا يكفي للتشخيص — «سنةُ الصنع يجب أن تكون رقماً» تحتاج أن نرى
        **ما أُرسل** لنعرف أهي فارغةٌ أم `null` أم نصٌّ بأرقامٍ عربية، وهي
        ثلاثةُ عيوبٍ مختلفةٍ في ثلاثة مواضع.
        """
        errors = exc.errors()
        try:
            raw_body = await request.json()
        except Exception:  # جسمٌ غيرُ JSON أو مقروءٌ سلفاً — ليس خطأً هنا
            raw_body = None

        logger.warning(
            "فشلُ تحقّقٍ في %s %s — %s | الجسم: %s",
            request.method,
            request.url.path,
            [
                {
                    "loc": error.get("loc"),
                    "type": error.get("type"),
                    "msg": error.get("msg"),
                }
                for error in errors
            ],
            validation_errors.redact(raw_body),
        )

        # **أوّلُ خطأٍ هو المعروض، وبقيتُها في `errors`**: الشاشةُ تنقل التركيزَ
        # إلى أوّل حقلٍ مرفوض (القسم ١٧.٧)، فالأولُ هو ما يقف عنده المستخدم؛
        # والبقيةُ تُرسل ليُعلَّم كلُّ حقلٍ بلونه في الدفعة نفسِها بدل أن
        # يُصلَح واحدٌ فيُرفض التالي.
        first = errors[0] if errors else {}
        body: dict[str, object] = {
            "code": "validation_error",
            "message": validation_errors.message_for(first),
        }
        field = validation_errors.field_of(first)
        if field:
            body["field"] = field
        if len(errors) > 1:
            body["errors"] = [
                {
                    "field": validation_errors.field_of(error),
                    "message": validation_errors.message_for(error),
                }
                for error in errors
            ]
        return JSONResponse(status_code=422, content=body)

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(
        _: Request, exc: HTTPException
    ) -> JSONResponse:
        """ما ترفعه FastAPI/Starlette نفسُها — بشكل العقد أيضاً.

        **والتسجيلُ على `starlette.exceptions.HTTPException` لا على وارثتها في
        FastAPI**، وهذا فرقٌ قِيس لا نُظِّر: «مسارٌ غير موجود» يرفعه راوترُ
        Starlette بالصنف الأمّ، فمعالجٌ على صنف FastAPI **لا يلتقطه** ويخرج
        `{"detail": "Not Found"}` بالإنجليزية وبالاسم القديم معاً. جُرِّب فخرج
        كذلك، ثم صُحِّح.

        **ولا يُعرض `exc.detail` كما هو**: نصُّه إنجليزيٌّ من المكتبة
        (`Not Found`)، وعرضُه يخالف القسمَ ١٧.٤. والحالةُ وحدَها كافيةٌ لاختيار
        نصٍّ عربيٍّ صادق، والنصُّ الأصليُّ يذهب إلى السجل.
        """
        code, message = _HTTP_STATUS_TEXT.get(
            exc.status_code, ("http_error", "تعذّر تنفيذ الطلب")
        )
        if exc.status_code >= 500:
            logger.warning("HTTPException %s: %s", exc.status_code, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code, "message": message},
            headers=getattr(exc, "headers", None),
        )


    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        """**المنبعُ الرابع** — ما لم يتوقّعه أحد (2026-09-20).

        **وكان غائباً، وغيابُه يُقرأ في هاتفِ إنسان**: استثناءٌ غيرُ متوقَّع
        كان يخرج من `ServerErrorMiddleware` نصّاً عارياً `Internal Server
        Error` بحالة ٥٠٠ — **لا `code` ولا `message`**. فيقرأ عميلُ التطبيق
        جسماً لا يعرفه ويعرض نصَّه الاحتياطيَّ العام، **والعقدُ الذي بُني
        ليكون واحداً يصير اثنين**: ثلاثةُ منابعَ تحترمه ورابعٌ لا.

        **والرقمُ المرجعيُّ هو الإضافة**: `request_id` يخرج في الجسم وفي رأس
        الردّ وفي سطر السجل معاً — فمن يقول «سقط طلبي» يحمل حرفاً يُبحث به،
        بدل أن يُقارَن وقتُ الشكوى بساعة الخادم.

        **ولا يُعرض نصُّ الاستثناء لصاحبه**: هو إنجليزيٌّ من مكتبة، وقد يحمل
        اسمَ جدولٍ أو قيمةً — والقسم ١٧٫٤ يحكم. يذهب إلى السجل كاملاً.
        """
        request_id = request_id_of(request.scope)
        logger.exception(
            "استثناءٌ غيرُ متوقَّع في %s %s (request_id=%s)",
            request.method,
            request.url.path,
            request_id or "—",
        )
        code, message = _HTTP_STATUS_TEXT[500]
        body: dict[str, object] = {"code": code, "message": message}
        headers: dict[str, str] = {}
        if request_id:
            body["request_id"] = request_id
            # **والرأسُ يُكتب هنا لا في الوسيط**: ردُّ هذا المعالج يخرج من
            # `ServerErrorMiddleware` فوق الوسيط، فلا يمرّ بمُغلِّفِ `send`
            # الذي يكتب الرأسَ في الردود الأخرى.
            headers[REQUEST_ID_HEADER] = request_id
        return JSONResponse(status_code=500, content=body, headers=headers)


# **نصوصُ حالاتِ HTTP** — سجلٌّ مركزيٌّ كبقية النصوص، لا نصٌّ في معالج.
_HTTP_STATUS_TEXT: dict[int, tuple[str, str]] = {
    401: ("unauthorized", "جلسة غير صالحة أو منتهية"),
    403: ("forbidden", "لا تملك صلاحية هذا الإجراء"),
    404: ("not_found", "غير موجود"),
    405: ("method_not_allowed", "طلبٌ غير مدعوم"),
    413: ("payload_too_large", "حجم الطلب أكبر من المسموح"),
    429: ("rate_limited", "طلباتٌ كثيرة — انتظر قليلاً ثم أعد المحاولة"),
    500: ("server_error", "خطأٌ في الخادم — أعد المحاولة"),
    502: ("upstream_error", "الخدمة غير متاحة الآن — أعد المحاولة"),
    503: ("service_unavailable", "الخدمة غير متاحة الآن — أعد المحاولة"),
    504: ("upstream_timeout", "الخادم لا يستجيب — أعد المحاولة"),
}


class CancellationDebtBlocked(AppError):
    """رسومُ إلغاءٍ متراكمةٌ بلغت حدَّ الإيقاف (`design/CANCELLATION-FEE.md` §4).

    **والنصُّ يقول ما يُفعل**: «لا يمكنك الطلب» وحدَها تُرسل صاحبَها إلى الدعم
    ليكتشف أن الحلَّ شحنُ محفظته — وهو ما كان يستطيعه وحدَه لو قيل له.
    """

    status_code = 402
    code = "cancellation_debt_blocked"
    message = "عليك رسومُ إلغاءٍ غيرُ مسدَّدة — اشحن محفظتك ليُخصم المستحق ثم أعد الطلب"


# ------------------------------------------- مركباتُ الكراج والمتجر (2026-08-22)
#
# **أخطاءٌ مسمّاةٌ لا رسالةٌ عامة** (§17): من يُرفض شراؤه يحتاج أن يعرف **أيَّ
# شرطٍ لم يتحقق** — والرصيدُ والنفادُ والمِلكيةُ والمستوى أربعةُ أفعالٍ مختلفة
# لمن رُفض، فرسالةٌ واحدةٌ تجعله يعيد المحاولةَ بلا سبب.


class SkinSoldOut(Conflict):
    code = "skin_sold_out"
    message = "نفدت الكمية — لم تعد هذه المركبة متاحة"


class SkinAlreadyOwned(Conflict):
    code = "skin_already_owned"
    message = "هذه المركبة في كراجك بالفعل"


class SkinLevelLocked(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "skin_level_locked"
    message = "هذه المركبة تُفتح عند مستوى أعلى"


class SkinNotOwned(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "skin_not_owned"
    message = "لا تملك هذه المركبة"


class SkinUnavailable(Conflict):
    code = "skin_unavailable"
    message = "هذه المركبة غير متاحة الآن"


class InvalidSkinArtwork(InvalidInput):
    code = "invalid_skin_artwork"
    message = "الملف ليس صورةً صالحة"
