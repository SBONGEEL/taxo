from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


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
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_credentials"
    message = "رقم الهاتف أو كلمة المرور غير صحيحة"


class InvalidToken(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_token"
    message = "جلسة غير صالحة أو منتهية"


class AccountBlocked(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "account_blocked"
    message = "هذا الحساب محظور"


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


class InvalidInput(AppError):
    status_code = 422  # Unprocessable Content — نفس ما يعيده FastAPI للتحقق
    code = "invalid_input"
    message = "بيانات غير صالحة"


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
    message = "خدمة المسارات غير مهيأة — راجع عقد Mapbox في لوحة الإدارة"


class RoutingFailed(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "routing_failed"
    message = "تعذّر حساب المسار بين النقطتين"


class RideAlreadyActive(Conflict):
    code = "ride_already_active"
    message = "لديك رحلة جارية بالفعل"


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


class RatingNotAllowed(Conflict):
    """تقييمٌ لرحلة لم تكتمل، أو من ليس طرفاً فيها (SPEC القسم 5.9)."""

    code = "rating_not_allowed"
    message = "لا يمكن تقييم هذه الرحلة"


class AlreadyRated(Conflict):
    code = "already_rated"
    message = "سبق أن قيّمت هذه الرحلة"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        body: dict[str, object] = {"code": exc.code, "detail": exc.message}
        if exc.extra:
            body |= exc.extra
        headers = {}
        if isinstance(exc, RateLimited) and "retry_after" in exc.extra:
            headers["Retry-After"] = str(exc.extra["retry_after"])
        return JSONResponse(status_code=exc.status_code, content=body, headers=headers)
