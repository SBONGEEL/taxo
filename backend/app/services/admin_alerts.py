"""**إشعاراتُ المالك بنشاط المستخدمين** (SPEC §٨١، أمرُ المالك ٢٠٢٦-١٠-٢٠) — الفهرسُ والكتابةُ والجمعُ والإرسالُ والقراءة.

## الطريقُ كلُّه

١. **الالتقاط** في `services/alert_capture.py`: بعد الالتزام يُدفع ما وقع إلى قائمةٍ في Redis — **ولا ينتظره أحد**.
٢. **العاملُ كلَّ خمس ثوانٍ** (`drain`): يقرأ القائمةَ ويحلّ كلَّ حدثٍ من صفِّه **بعد الالتزام** (سوقُه ومبلغُه وسجلُّه)، **فما رُجع
   عنه أو حُذف لا يُكتب** — ثمّ يكتب `admin_alerts` **ويجمع** ثمّ يرسل.
٣. **الجمع**: حدثٌ يصل ونظيرُه (النوعُ والسوق) كُتب قبل أقلَّ من نافذته **يُضمّ إليه** — يكبر عددُه ومجموعُه، ويُستبدل إشعارُه على
   الجهاز بالمفتاح نفسِه (`tag`) **بلا صوتٍ ثانٍ**. فطلباتُ الذروة إشعارٌ واحدٌ يقول «١٢ طلبَ رحلة · الأردن».
٤. **الإرسال** لمن يملك `activity_alerts.receive` (المالكُ افتراضاً، وغيرُه بمنحٍ من المصفوفة) **بإعداد كلِّ واحد**: النوعُ لكلِّ قناة.

## ونصُّ القفل لا يحمل إنساناً

**العنوانُ نوعُ الحدث وسوقُه، والنصُّ المبلغُ وما يشبهه** (الطريقة · من ألغى · عددُ النجوم · «ضيف») — **لا اسمَ ولا رقمَ هاتف**؛
التفاصيلُ في سجلّها باللوحة بعد الدخول. **و`data` خامٌ** إلا `title`/`body` لما يرسمه الجهازُ بنفسه (بياناتٌ وحدَها) — كـ`channels.for_level`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.currency import COUNTRY_NAME, CURRENCY_LABEL, amount_text, currency_for_country
from app.core.exceptions import InvalidInput, NotFound
from app.models.admin_alert import AdminAlert, AdminAlertRead, AdminAlertSettings
from app.models.admin_permission import AdminPermissionGrant
from app.models.device import DeviceToken
from app.models.enums import (
    AdminPermission,
    CountryCode,
    Currency,
    DevicePlatform,
    DocumentType,
    UserRole,
    WalletOwnerType,
)
from app.models.user import User
from app.models.user_role_grant import has_role_clause
from app.services import alert_capture, devices, permissions
from app.services.documents import DOCUMENT_TYPE_LABEL
from app.services.push import PushMessage, get_push_provider_or_none

logger = logging.getLogger(__name__)

PERMISSION = AdminPermission.ACTIVITY_ALERTS_RECEIVE
#: **قيمٌ عامّةٌ لا تعداد** («phone» · «web») — تعدادٌ بها في الخلفية يدخل مجموعةَ `check:enums` الشاملةَ فيُسقط اتحاداتٍ لا شأنَ لها
#: في التطبيقين (`Field` و`Step`). **ومرآتُها في اللوحة يقابلها `admin-panel/scripts/check-enums.mjs → ALERT_MIRRORS`** قيمةً قيمة
CHANNELS = ("panel", "web", "phone")

# ═════════════════════════ الفهرس — بيتُ الأنواع الواحد


@dataclass(frozen=True, slots=True)
class AlertKind:
    kind: str
    #: **مجموعةُ العرض** — حساباتٌ · مالٌ · رحلاتٌ · دعم (مرشِّحُ «النوع» في القائمة، كما سمّاها المالك)
    category: str
    #: **فئةُ الصوت والقناة** — منها صوتُه ولونُه وأيقونتُه وقناةُ أندرويد
    tone: str
    label: str
    #: **صيغةُ الجمع بعدد** — «٣ طلبات رحلة»
    plural: str
    #: **نافذةُ الجمع بالثواني** — ما يصل في نافذة نظيره يُضمّ إليه
    window: int = 30


TONES: dict[str, str] = {
    # بنصِّ المالك: «رنّةُ نقودٍ لطيفة»
    "money_in": "مالٌ داخل",
    # **فئتان لم يسمّهما الأمرُ بصوت**: المالُ الخارجُ والمعلَّقُ (سحبٌ · استرداد · تسوية · إلغاء) — **ليس داخلاً ولا مشكلة**
    "money_out": "مالٌ خارج أو معلَّق",
    # بنصِّه: «نغمةٌ خفيفةٌ ناعمة»
    "account": "حسابٌ جديد",
    # بنصِّه: «تنبيهٌ مميّزٌ غيرُ حادّ» — دفعةٌ فشلت · شكوى · تقييمُ ١–٢ · سقفُ الدَّين
    "problem": "مشكلة",
    # بنصِّه: «نقرةٌ هادئة، فلا تصخب الذروة»
    "ride": "رحلات",
    # **والثانية**: رسائلُ «أرسل ملاحظة» — كلامُ إنسانٍ لا مالٌ ولا مشكلةٌ بالضرورة
    "feedback": "ملاحظات",
}

CATEGORIES: dict[str, str] = {
    "accounts": "الحسابات",
    "money": "المال",
    "rides": "الرحلات",
    "support": "الدعم",
}

_KINDS: tuple[AlertKind, ...] = (
    AlertKind("rider_signup", "accounts", "account", "راكبٌ جديد", "ركّاب جدد"),
    AlertKind("captain_signup", "accounts", "account", "كبتنٌ جديد", "كباتن جدد"),
    AlertKind("documents_submitted", "accounts", "account", "وثائقُ كبتنٍ أُرسلت", "وثائقُ كباتن أُرسلت"),
    AlertKind("documents_approved", "accounts", "account", "وثائقُ كبتنٍ قُبلت", "وثائقُ كباتن قُبلت"),
    AlertKind("documents_rejected", "accounts", "account", "وثائقُ كبتنٍ رُفضت", "وثائقُ كباتن رُفضت"),
    AlertKind("payment_succeeded", "money", "money_in", "دفعةٌ ناجحة", "دفعات ناجحة"),
    AlertKind("wallet_topup", "money", "money_in", "شحنُ محفظة", "عمليات شحن"),
    AlertKind("subscription_purchased", "money", "money_in", "اشتراكٌ جديد", "اشتراكات جديدة"),
    AlertKind("topup_requested", "money", "money_out", "طلبُ شحنٍ ينتظر", "طلبات شحن تنتظر"),
    AlertKind("withdrawal_requested", "money", "money_out", "طلبُ سحب", "طلبات سحب"),
    AlertKind("withdrawal_paid", "money", "money_out", "سحبٌ صُرف", "عمليات سحب صُرفت"),
    AlertKind("withdrawal_rejected", "money", "money_out", "سحبٌ رُفض", "عمليات سحب رُفضت"),
    AlertKind("payment_cancelled", "money", "money_out", "دفعةٌ أُلغيت", "دفعات أُلغيت"),
    AlertKind("payment_expired", "money", "money_out", "دفعةٌ انتهت مهلتُها", "دفعات انتهت مهلتُها"),
    AlertKind("refund", "money", "money_out", "استرداد", "عمليات استرداد"),
    AlertKind("manual_adjustment", "money", "money_out", "تسويةٌ يدويّة", "تسويات يدويّة"),
    AlertKind("payment_failed", "money", "problem", "دفعةٌ فشلت", "دفعات فشلت"),
    # **دفعُ الجزائر بأمان** (SPEC §٨٢) — وسيطٌ توقّف وعاد، ودفعةٌ وصلت ولم تُفعَّل، ودفعٌ مكرَّر، وقراراتُ مراجعة التحويل
    AlertKind("gateway_down", "money", "problem", "وسيطُ الدفع متوقّف", "انقطاعاتُ وسيط الدفع", window=0),
    AlertKind("gateway_up", "money", "money_in", "وسيطُ الدفع عاد", "عوداتُ وسيط الدفع", window=0),
    AlertKind("payment_stuck", "money", "problem", "دفعةٌ وصلت ولم تُفعَّل", "دفعات وصلت ولم تُفعَّل"),
    # **حمايةُ الدفع** (SPEC §٨٧) — طريقةٌ أُخفيت آليّاً بعد إخفاقاتٍ متتالية، وافتراقٌ في المطابقة اليوميّة
    AlertKind("payment_method_hidden", "money", "problem", "طريقةُ دفعٍ أُخفيت آليّاً", "طرقُ دفعٍ أُخفيت آليّاً", window=0),
    AlertKind("reconciliation_mismatch", "money", "problem", "افتراقٌ في المطابقة اليوميّة", "افتراقاتٌ في المطابقة", window=0),
    AlertKind("payment_extra", "money", "money_out", "دفعٌ مكرَّر — الزائدُ في المحفظة", "دفعات مكرَّرة"),
    AlertKind("transfer_duplicate", "money", "problem", "رقمُ تحويلٍ مكرَّر", "أرقامُ تحويلٍ مكرَّرة"),
    AlertKind("transfer_approved", "money", "money_in", "تحويلٌ اعتُمد", "تحويلات اعتُمدت"),
    AlertKind("transfer_rejected", "money", "money_out", "تحويلٌ رُفض", "تحويلات رُفضت"),
    AlertKind("debt_cap_reached", "money", "problem", "كبتنٌ بلغ سقفَ الدَّين", "كباتن بلغوا سقفَ الدَّين"),
    AlertKind("ride_requested", "rides", "ride", "طلبُ رحلة", "طلبات رحلة", window=120),
    AlertKind("ride_accepted", "rides", "ride", "رحلةٌ قُبلت", "رحلات قُبلت", window=120),
    AlertKind("ride_completed", "rides", "ride", "رحلةٌ اكتملت", "رحلات اكتملت", window=120),
    AlertKind("ride_cancelled", "rides", "ride", "رحلةٌ أُلغيت", "رحلات أُلغيت", window=120),
    AlertKind("complaint", "support", "problem", "شكوى", "شكاوى"),
    AlertKind("low_rating", "support", "problem", "تقييمٌ منخفض", "تقييمات منخفضة"),
    AlertKind("feedback", "support", "feedback", "ملاحظةٌ جديدة", "ملاحظات جديدة"),
)
CATALOG: dict[str, AlertKind] = {item.kind: item for item in _KINDS}

METHOD_LABEL = {"cash": "نقداً", "cliq": "كليك", "card": "بطاقة", "wallet": "المحفظة"}
CANCELLED_BY_LABEL = {"rider": "ألغاها الراكب", "driver": "ألغاها الكبتن", "no_driver": "لم يُعثر على كبتن"}
COMPLAINT_SOURCE_LABEL = {"dispute": "نزاعٌ على دفعة", "chat": "بلاغٌ على رسالة", "photo": "بلاغٌ على صورة"}
REVIEWED_BY_LABEL = {"reviewer": "بيد المراجع", "owner": "بيد المالك", "staff": "بيد الماليّة"}
_EXPIRED = re.compile(r"expire|انته|مهلة|timeout", re.IGNORECASE)

# ═════════════════════════ الحلّ — من حدثٍ ملتقطٍ إلى مسوّدة


@dataclass(slots=True)
class Draft:
    kind: str
    country: CountryCode | None
    amount: Decimal | None = None
    currency: Currency | None = None
    record_type: str | None = None
    record_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    #: **مفتاحُ التفرّد داخل الدفعة** — وثائقُ كبتنٍ واحدٍ في معاملةٍ واحدةٍ حدثٌ واحد
    dedupe: str | None = None


async def _person(session: AsyncSession, user_id: uuid.UUID, owner_type: str | None = None) -> tuple[str, str]:
    """**السجلُّ الذي يُفتح لصاحب حساب** — ملفُّ الكبتن إن كان المالُ مالَ كبتن، وإلا الراكب."""
    from app.models.driver import Driver

    if owner_type != WalletOwnerType.RIDER.value:
        driver_id = await session.scalar(select(Driver.id).where(Driver.user_id == user_id))
        if driver_id is not None:
            return "driver", str(driver_id)
    return "rider", str(user_id)


def _money(country: CountryCode | None, amount: Decimal | None) -> tuple[Decimal | None, Currency | None]:
    if amount is None or country is None:
        return None, None
    return amount, currency_for_country(country)


async def _resolve(session: AsyncSession, item: dict[str, Any]) -> Draft | None:
    """**حدثٌ واحدٌ من صفّه بعد الالتزام** — و`None` لما لم يعد موجوداً (رُجع عنه بنقطة حفظ) أو لا يُشعَر به."""
    from app.models.driver import Driver, DriverDocument
    from app.models.feedback import AppFeedback
    from app.models.guest import GuestSession
    from app.models.payment import Payment
    from app.models.payment_request import PaymentRequest, PayMethod
    from app.models.photo_report import UserPhotoReport
    from app.models.provider_order import ProviderOrder
    from app.models.rating import Rating
    from app.models.ride import Ride
    from app.models.rider_subscription import RiderSubscription
    from app.models.subscription import DriverSubscription
    from app.models.trip_chat import RideMessage, RideMessageReport
    from app.models.wallet import WalletTopupRequest, WalletTransaction, WithdrawalRequest
    from app.services import debts

    kind, model, extra = item["k"], item["m"], item.get("x") or {}
    if kind not in CATALOG:
        return None
    pk = uuid.UUID(item["id"])

    if model == "user":
        user = await session.get(User, pk)
        if user is None:
            return None
        return Draft(kind, user.country_code, record_type="rider", record_id=str(user.id), data={"test": user.is_test})

    if model == "driver":
        driver = await session.get(Driver, pk)
        if driver is None:
            return None
        user = await session.get(User, driver.user_id)
        country = user.country_code if user else None
        draft = Draft(kind, country, record_type="driver", record_id=str(driver.id), data={"test": bool(user and user.is_test)})
        if kind == "debt_cap_reached":
            draft.amount, draft.currency = _money(country, await debts.outstanding_of(session, driver.id))
        return draft

    if model == "document":
        document = await session.get(DriverDocument, pk)
        if document is None:
            return None
        driver = await session.get(Driver, document.driver_id)
        user = await session.get(User, driver.user_id) if driver else None
        return Draft(
            kind,
            user.country_code if user else None,
            record_type="driver",
            record_id=str(document.driver_id),
            data={"doc_type": document.doc_type.value, "test": bool(user and user.is_test)},
            dedupe=f"{kind}:{document.driver_id}",
        )

    if model == "payment":
        payment = await session.get(Payment, pk)
        if payment is None:
            return None
        ride = await session.get(Ride, payment.ride_id)
        rider = await session.get(User, ride.rider_id) if ride else None
        data: dict[str, Any] = {"method": payment.method.value, "test": bool(rider and rider.is_test)}
        if kind == "complaint":
            data["source"] = "dispute"
        return Draft(
            kind,
            ride.country_code if ride else None,
            amount=payment.amount,
            currency=payment.currency,
            record_type="ride",
            record_id=str(payment.ride_id),
            data=data,
            dedupe=f"payment:{payment.id}",
        )

    if model == "order":
        order = await session.get(ProviderOrder, pk)
        if order is None:
            return None
        if kind == "payment_failed" and order.failure_reason and _EXPIRED.search(order.failure_reason):
            kind = "payment_expired"
        user = await session.get(User, order.user_id)
        if order.ride_id is not None:
            record = ("ride", str(order.ride_id))
        else:
            record = await _person(session, order.user_id, order.opened_from_app if order.opened_from_app in ("rider", "driver") else None)
        return Draft(
            kind,
            order.country_code,
            amount=order.amount,
            currency=order.currency,
            record_type=record[0],
            record_id=record[1],
            data={"purpose": order.purpose.value, "provider": order.provider.value, "test": bool(user and user.is_test)},
            # **دفعةُ البطاقة تسقط مع طلبها في المعاملة نفسِها** — فيُقرأ الطلبُ وتُسقط الدفعةُ من الدفعة نفسِها
            dedupe=f"payment:{order.payment_id}" if order.payment_id else None,
        )

    if model == "ledger":
        entry = await session.get(WalletTransaction, pk)
        if entry is None:
            return None
        user = await session.get(User, entry.owner_id)
        country = user.country_code if user else None
        amount, currency = _money(country, abs(entry.amount))
        record = await _person(session, entry.owner_id, entry.owner_type.value)
        return Draft(
            kind, country, amount=amount, currency=currency, record_type=record[0], record_id=record[1],
            data={"owner": entry.owner_type.value, "test": bool(user and user.is_test)},
            # **ردُّ دفعةٍ يكتب قيدَ تسوية** — فيُقرأ ردّاً من دفعته ويسقط قيدُه هنا (`resolve_all`)
            dedupe=f"ledger:{entry.id}",
        )

    if model == "signal":
        # **حدثٌ لا صفَّ له** (SPEC §٨٢): وسيطٌ توقّف أو عاد، أو رقمُ تحويلٍ مكرَّرٌ رُدّ قبل أن يُكتب — سوقُه وما يُقال عنه من الحدث نفسِه
        country_value = extra.get("country")
        return Draft(
            kind,
            CountryCode(country_value) if country_value else None,
            data={key: extra[key] for key in ("gateway", "provider") if extra.get(key)},
        )

    if model == "payment_request":
        request = await session.get(PaymentRequest, pk)
        if request is None:
            return None
        method = await session.get(PayMethod, request.provider_id)
        if kind == "topup_requested" and method is not None and method.integration:
            return None
        # **قرارُ إنسانٍ على تحويلٍ يدويّ يُشعَر به باسمه** (`transfer_rejected`) — فلا «دفعةٌ فشلت» ثانيةٌ للحدث نفسِه
        if kind == "payment_failed" and method is not None and not method.integration and request.reviewed_by is not None:
            return None
        if kind == "payment_cancelled" and request.cancel_reason and _EXPIRED.search(request.cancel_reason):
            kind = "payment_expired"
        user = await session.get(User, request.user_id)
        return Draft(
            kind,
            request.country_code,
            amount=request.amount,
            currency=request.currency,
            # **تحويلُ BaridiMob يفتح صفحةَ مراجعته** (SPEC §٨٢-ب/٤) — لا «نظام الدفع» العامّ
            record_type="transfer" if method is not None and method.code == "baridimob" else "payment_request",
            record_id=str(request.id),
            data={"purpose": request.purpose.value, "pay_kind": request.kind.value, "test": bool(user and user.is_test)}
            | ({"by": extra["by"]} if extra.get("by") in ("reviewer", "owner", "staff") else {}),
            dedupe=(
                f"ledger:{request.refund_transaction_id}" if kind == "refund" and request.refund_transaction_id
                # **الاعتمادُ يُقرأ من قراره لا من قيده** — فلا «شحنُ محفظة» ثانٍ للحدث نفسِه
                else f"ledger:{request.transaction_id}" if kind == "transfer_approved" and request.transaction_id
                else None
            ),
        )

    if model == "topup_request":
        request = await session.get(WalletTopupRequest, pk)
        if request is None:
            return None
        user = await session.get(User, request.owner_id)
        country = user.country_code if user else None
        amount, currency = _money(country, request.amount)
        return Draft(
            kind, country, amount=amount, currency=currency, record_type="topup_request", record_id=str(request.id),
            data={"method": request.method.value, "test": bool(user and user.is_test)},
        )

    if model == "withdrawal":
        request = await session.get(WithdrawalRequest, pk)
        if request is None:
            return None
        driver = await session.get(Driver, request.driver_id)
        user = await session.get(User, driver.user_id) if driver else None
        country = user.country_code if user else None
        amount, currency = _money(country, request.amount)
        return Draft(
            kind, country, amount=amount, currency=currency, record_type="withdrawal", record_id=str(request.id),
            data={"method": request.method.value, "test": bool(user and user.is_test)},
        )

    if model == "subscription":
        row = await session.get(DriverSubscription, pk)
        if row is None:
            return None
        driver = await session.get(Driver, row.driver_id)
        user = await session.get(User, driver.user_id) if driver else None
        country = user.country_code if user else None
        amount, currency = _money(country, row.amount_paid)
        return Draft(
            kind, country, amount=amount, currency=currency, record_type="driver", record_id=str(row.driver_id),
            data={"who": "captain", "method": row.payment_method.value, "test": bool(user and user.is_test)},
        )

    if model == "rider_subscription":
        row = await session.get(RiderSubscription, pk)
        if row is None:
            return None
        user = await session.get(User, row.rider_id)
        amount, currency = _money(row.country_code, row.amount_paid)
        return Draft(
            kind, row.country_code, amount=amount, currency=currency, record_type="rider", record_id=str(row.rider_id),
            data={"who": "rider", "test": bool(user and user.is_test)},
        )

    if model == "ride":
        ride = await session.get(Ride, pk)
        if ride is None:
            return None
        rider = await session.get(User, ride.rider_id)
        fare = ride.final_fare if kind == "ride_completed" and ride.final_fare is not None else ride.estimated_fare
        data = {"category": ride.vehicle_category, "type": ride.ride_type, "test": bool(rider and rider.is_test)}
        if extra.get("by"):
            data["by"] = extra["by"]
        return Draft(
            kind, ride.country_code, amount=fare, currency=ride.currency, record_type="ride", record_id=str(ride.id), data=data,
        )

    if model == "rating":
        row = await session.get(Rating, pk)
        if row is None:
            return None
        ride = await session.get(Ride, row.ride_id)
        rater = await session.get(User, row.rater_id)
        return Draft(
            kind, ride.country_code if ride else None, record_type="ride", record_id=str(row.ride_id),
            data={"stars": row.stars, "rater": row.rater_type.value, "test": bool(rater and rater.is_test)},
        )

    if model == "feedback":
        row = await session.get(AppFeedback, pk)
        if row is None:
            return None
        country: CountryCode | None = None
        test = False
        if row.user_id is not None:
            user = await session.get(User, row.user_id)
            country, test = (user.country_code, user.is_test) if user else (None, False)
        elif row.guest_session_id is not None:
            guest = await session.get(GuestSession, row.guest_session_id)
            region = (guest.network_region or "").upper() if guest else ""
            country = CountryCode(region) if region in {code.value for code in CountryCode} else None
        return Draft(
            kind, country, record_type="feedback", record_id=str(row.id),
            data={"app": row.app, "guest": row.guest_session_id is not None, "test": test},
        )

    if model == "message_report":
        row = await session.get(RideMessageReport, pk)
        if row is None:
            return None
        message = await session.get(RideMessage, row.message_id)
        ride = await session.get(Ride, message.ride_id) if message else None
        return Draft(
            kind, ride.country_code if ride else None, record_type="chat_report", record_id=str(row.id), data={"source": "chat"},
        )

    if model == "photo_report":
        row = await session.get(UserPhotoReport, pk)
        if row is None:
            return None
        ride = await session.get(Ride, row.ride_id)
        return Draft(
            kind, ride.country_code if ride else None, record_type="photo_report", record_id=str(row.id), data={"source": "photo"},
        )

    return None


async def resolve_all(session: AsyncSession, items: list[dict[str, Any]]) -> list[Draft]:
    """**كلُّ دفعةٍ بلا تكرار**: وثائقُ كبتنٍ واحدٍ حدثٌ واحد، **والدفعةُ التي سقطت مع طلب بطاقتها تُقرأ من الطلب**."""
    resolved: list[tuple[str, Draft]] = []
    for item in items:
        try:
            draft = await _resolve(session, item)
        except Exception:  # pragma: no cover - حدثٌ تالفٌ لا يُسقط الدفعة
            logger.exception("تعذّر حلُّ حدثٍ لإشعارات المالك: %s", item)
            continue
        if draft is not None:
            resolved.append((item["m"], draft))
    order_payments = {draft.dedupe for model, draft in resolved if model == "order" and draft.dedupe}
    request_ledgers = {draft.dedupe for model, draft in resolved if model == "payment_request" and draft.dedupe}
    drafts: list[Draft] = []
    seen: dict[str, Draft] = {}
    for model, draft in resolved:
        if model == "payment" and draft.dedupe in order_payments:
            continue
        if model == "ledger" and draft.dedupe in request_ledgers:
            continue
        if model == "document" and draft.dedupe:
            if draft.dedupe in seen:
                first = seen[draft.dedupe]
                first.data["count_docs"] = int(first.data.get("count_docs", 1)) + 1
                continue
            seen[draft.dedupe] = draft
        drafts.append(draft)
    return drafts


# ═════════════════════════ الكتابةُ والجمع


def group_key(kind: str, country: CountryCode | None) -> str:
    return f"{kind}:{country.value if country else '-'}"


def _absorb(alert: AdminAlert, drafts: list[Draft]) -> None:
    """**يضمّ مسوّداتٍ إلى صفٍّ** — العددُ والمجموعُ (إن اتّحدت العملة)، **والسجلُّ يُفرَّغ** فيفتح الصفُّ القائمة."""
    for draft in drafts:
        if alert.amount is not None and draft.amount is not None and alert.currency == draft.currency:
            alert.amount = alert.amount + draft.amount
        elif alert.count > 0 and (draft.amount is not None or alert.amount is not None):
            alert.amount = None
            alert.currency = None
        alert.count += 1
    alert.record_type = None
    alert.record_id = None
    test = bool(alert.data.get("test")) or any(d.data.get("test") for d in drafts)
    alert.data = {"grouped": True, "test": test}


async def record(
    session: AsyncSession, drafts: list[Draft], *, now: datetime | None = None
) -> list[tuple[AdminAlert, bool]]:
    """يكتب ويجمع — ويعيد `(الصفّ، أضُمّ إلى قائم؟)` لكلِّ ما تغيّر. **والالتزامُ على المنادي.**"""
    moment = now or datetime.now(UTC)
    buckets: dict[str, list[Draft]] = defaultdict(list)
    for draft in drafts:
        buckets[group_key(draft.kind, draft.country)].append(draft)

    touched: list[tuple[AdminAlert, bool]] = []
    for key, items in buckets.items():
        spec = CATALOG[items[0].kind]
        existing = await session.scalar(
            select(AdminAlert)
            .where(AdminAlert.group_key == key, AdminAlert.last_event_at >= moment - timedelta(seconds=spec.window))
            .order_by(AdminAlert.last_event_at.desc())
            .limit(1)
        )
        if existing is not None:
            _absorb(existing, items)
            existing.last_event_at = moment
            # **عاد غيرَ مقروء** لمن قرأه قبل أن يكبر — الجديدُ فيه لم يُقرأ
            await session.execute(delete(AdminAlertRead).where(AdminAlertRead.alert_id == existing.id))
            touched.append((existing, True))
            continue
        first = items[0]
        alert = AdminAlert(
            kind=first.kind,
            category=spec.category,
            tone=spec.tone,
            country_code=first.country,
            count=1,
            amount=first.amount,
            currency=first.currency,
            record_type=first.record_type,
            record_id=first.record_id,
            data=dict(first.data),
            group_key=key,
            last_event_at=moment,
        )
        if len(items) > 1:
            _absorb(alert, items[1:])
        session.add(alert)
        touched.append((alert, False))
    await session.flush()
    return touched


# ═════════════════════════ نصُّ الدرج — العنوانُ والسطرُ على شاشة القفل


def tray_text(alert: AdminAlert) -> tuple[str, str]:
    """**نوعُ الحدث وسوقُه، والمبلغُ وما يشبهه** — ولا اسمَ ولا رقم (شرطُ المالك)."""
    spec = CATALOG[alert.kind]
    country = COUNTRY_NAME.get(alert.country_code, "") if alert.country_code else ""
    head = f"{alert.count} {spec.plural}" if alert.count > 1 else spec.label
    title = f"{head} · {country}" if country else head
    if alert.data.get("test"):
        title = f"تجربة · {title}"

    parts: list[str] = []
    if alert.amount is not None and alert.currency is not None:
        parts.append(f"{amount_text(alert.amount, alert.currency)} {CURRENCY_LABEL[alert.currency]}")
    data = alert.data
    if data.get("method") in METHOD_LABEL:
        parts.append(METHOD_LABEL[data["method"]])
    if data.get("by") in CANCELLED_BY_LABEL:
        parts.append(CANCELLED_BY_LABEL[data["by"]])
    if "stars" in data:
        parts.append("نجمةٌ واحدة" if data["stars"] == 1 else "نجمتان")
    if data.get("source") in COMPLAINT_SOURCE_LABEL:
        parts.append(COMPLAINT_SOURCE_LABEL[data["source"]])
    if data.get("doc_type"):
        try:
            label = DOCUMENT_TYPE_LABEL[DocumentType(data["doc_type"])]
        except (ValueError, KeyError):
            label = ""
        docs = int(data.get("count_docs", 1))
        if label:
            parts.append(label if docs == 1 else f"{docs} وثائق")
    if alert.kind == "feedback":
        parts.append("من ضيف" if data.get("guest") else ("من كبتن" if data.get("app") == "driver" else "من راكب"))
    if data.get("gateway"):
        parts.append(str(data["gateway"]).capitalize())
    if data.get("by") in REVIEWED_BY_LABEL:
        parts.append(REVIEWED_BY_LABEL[data["by"]])
    if data.get("who") == "rider":
        parts.append("راكب")
    elif data.get("who") == "captain":
        parts.append("كبتن")
    body = " · ".join(parts) if parts else "افتح اللوحة للتفاصيل"
    return title, body


# ═════════════════════════ المستلمون وإعدادُهم


async def recipients(session: AsyncSession) -> list[User]:
    """**من يملك الصلاحيةَ فعلاً** — المالكُ، ومن مُنحها بالاسم من المصفوفة. **ومحظورٌ أو مُغلَقٌ لا يستلم.**"""
    granted = select(AdminPermissionGrant.user_id).where(AdminPermissionGrant.permission == PERMISSION)
    rows = await session.scalars(
        select(User).where(
            User.is_blocked.is_(False),
            User.deactivated_at.is_(None),
            has_role_clause(UserRole.ADMIN, UserRole.SUPPORT, UserRole.OWNER),
            or_(has_role_clause(UserRole.OWNER), User.id.in_(granted)),
        )
    )
    found: list[User] = []
    for user in rows:
        if await permissions.holds(session, user, PERMISSION):
            found.append(user)
    return found


@dataclass(frozen=True, slots=True)
class Prefs:
    kinds: dict[str, dict[str, bool]]
    sounds: dict[str, bool]

    def on(self, kind: str, channel: str) -> bool:
        return bool(self.kinds.get(kind, {}).get(channel, True))


def _full(kinds: dict[str, Any] | None, sounds: dict[str, Any] | None) -> Prefs:
    """**ما غاب مشغَّل** — بنصِّ المالك «الافتراضيُّ: الكلُّ مشغَّل». ومفتاحٌ لا يعرفه الفهرسُ يُهمل."""
    kinds = kinds or {}
    sounds = sounds or {}
    full_kinds = {
        kind: {channel: bool((kinds.get(kind) or {}).get(channel, True)) for channel in CHANNELS} for kind in CATALOG
    }
    full_sounds = {tone: bool(sounds.get(tone, True)) for tone in TONES}
    return Prefs(full_kinds, full_sounds)


async def prefs_of(session: AsyncSession, user_id: uuid.UUID) -> Prefs:
    row = await session.get(AdminAlertSettings, user_id)
    return _full(row.kinds if row else None, row.sounds if row else None)


async def save_prefs(
    session: AsyncSession, user_id: uuid.UUID, *, kinds: dict[str, dict[str, bool]], sounds: dict[str, bool]
) -> Prefs:
    unknown = (set(kinds) - set(CATALOG)) | (set(sounds) - set(TONES))
    if unknown:
        raise InvalidInput(f"نوعٌ غيرُ معروف: {', '.join(sorted(unknown))}")
    prefs = _full(kinds, sounds)
    statement = insert(AdminAlertSettings).values(user_id=user_id, kinds=prefs.kinds, sounds=prefs.sounds)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[AdminAlertSettings.user_id],
            set_={"kinds": statement.excluded.kinds, "sounds": statement.excluded.sounds, "updated_at": func.now()},
        )
    )
    return prefs


# ═════════════════════════ الإرسال

#: **تطبيقُ الإدارة الذي يرسم إشعاراتِه بنفسه** — قنواتُه الستُّ وخدمتُه الأصليّة (`AdminAlertService.java`). **بعيدٌ عن ٢ و٣**
#: (مجموعتا قنوات الراكب والكبتن) وتحت سقف الحقل (٩٩، `schemas/device.py`)، **ويبلّغ به التطبيقُ حين يجد قنواتِه على الجهاز**
#: (`admin-panel/src/lib/push.ts`). **و`channels.level_of` يقرؤه ثالثةً** — فإشعاراتُ اللوحة القائمة (`cliq_claim_declared`) تصله كما هي
ADMIN_NATIVE = 51


def read_receipt(user_id: uuid.UUID, alert_id: uuid.UUID) -> str:
    """**إذنٌ بفعلٍ واحد**: «اجعل هذا مقروءاً لهذا المستلم» — يحمله زرُّ «مقروء» في الإشعار ولا يفتح غيرَه."""
    message = f"admin-alert-read:{user_id}:{alert_id}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()[:40]


def payload_for(alert: AdminAlert, *, user_id: uuid.UUID | None, bumped: bool, sample: bool = False) -> dict[str, str]:
    title, body = tray_text(alert)
    if sample:
        title = f"معاينة · {title}"
    data = {
        "type": "admin_alert",
        "alert_id": str(alert.id) if alert.id else "",
        "kind": alert.kind,
        "category": alert.category,
        "tone": alert.tone,
        "country": alert.country_code.value if alert.country_code else "",
        "count": str(alert.count),
        "amount": str(alert.amount) if alert.amount is not None else "",
        "currency": alert.currency.value if alert.currency else "",
        "record_type": alert.record_type or "",
        "record_id": alert.record_id or "",
        "tag": alert.group_key,
        "bumped": "1" if bumped else "0",
        # **للجهاز الذي يرسم بنفسه** — كـ`channels.for_level`: نصٌّ واحدٌ في الخادم لا نسخةٌ في كلِّ تطبيق
        "title": title,
        "body": body,
    }
    if user_id is not None and alert.id and not sample:
        data["read_receipt"] = read_receipt(user_id, alert.id)
        data["user_id"] = str(user_id)
    if sample:
        data["sample"] = "1"
    return data


async def _targets(session: AsyncSession, user_id: uuid.UUID) -> list[tuple[str, DevicePlatform, int | None]]:
    rows = await session.execute(
        select(DeviceToken.token, DeviceToken.platform, DeviceToken.push_channels).where(
            DeviceToken.user_id == user_id, DeviceToken.is_active.is_(True)
        )
    )
    return [(token, platform, level) for token, platform, level in rows.all()]


async def send_to(
    session: AsyncSession,
    user: User,
    alerts: list[tuple[AdminAlert, bool]],
    *,
    prefs: Prefs | None = None,
    sample: bool = False,
) -> dict[str, int]:
    """**لكلِّ جهازٍ رسالتُه**: المتصفّحُ وتطبيقُ الإدارة الجديدُ بياناتٍ وحدَها يرسمانها بأيقونتها وأزرارها، **والأقدمُ إشعارٌ يرسمه
    النظام** كما يصله اليومَ. **وفشلُ الإرسال يُعدّ ولا يُرمى.**"""
    provider = await get_push_provider_or_none(session)
    counts = {"web": 0, "phone": 0, "failed": 0}
    if provider is None:
        return counts
    prefs = prefs or await prefs_of(session, user.id)
    targets = await _targets(session, user.id)
    dead: list[str] = []
    for alert, bumped in alerts:
        data = payload_for(alert, user_id=user.id, bumped=bumped, sample=sample)
        title, body = data["title"], data["body"]
        for token, platform, level in targets:
            channel = "web" if platform is DevicePlatform.WEB else "phone"
            if not sample and not prefs.on(alert.kind, channel):
                continue
            native = platform is DevicePlatform.WEB or (level or 0) >= ADMIN_NATIVE
            if native:
                message = PushMessage(title=title, body=body, data=data, data_only=True, high_priority=True)
            else:
                plain = {key: value for key, value in data.items() if key not in ("title", "body")}
                message = PushMessage(title=title, body=body, data=plain)
            try:
                result = await provider.send([token], message)
            except Exception:  # pragma: no cover - مزوّدٌ خارجيّ
                logger.warning("تعذّر إرسالُ إشعار المالك", exc_info=True)
                counts["failed"] += 1
                continue
            counts[channel] += result.delivered
            counts["failed"] += result.failed
            dead.extend(result.invalid_tokens)
    if dead:
        await devices.deactivate_tokens(session, dead)
        await session.commit()
    return counts


async def deliver(session: AsyncSession, touched: list[tuple[AdminAlert, bool]]) -> None:
    if not touched:
        return
    for user in await recipients(session):
        try:
            await send_to(session, user, touched)
        except Exception:  # pragma: no cover - مستلمٌ تعطّل لا يحجب غيرَه
            logger.exception("تعذّر إرسالُ إشعارات المالك إلى %s", user.id)


# ═════════════════════════ العامل — يقرأ القائمةَ ويكتب ويرسل

BATCH = 500
_LOCK_KEY = "admin_alerts:drain_lock"


async def drain(session: AsyncSession, redis: Redis, *, now: datetime | None = None, push: bool = True) -> int:
    """**دورةٌ واحدة** — وقفلٌ في Redis يمنع دورتين معاً (عاملان في عمليّتين)، فلا يُضمّ حدثٌ مرّتين ولا يُكتب صفّان لجمعٍ واحد."""
    if not await redis.set(_LOCK_KEY, "1", nx=True, ex=60):
        return 0
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.lrange(alert_capture.QUEUE_KEY, 0, BATCH - 1)
            pipe.ltrim(alert_capture.QUEUE_KEY, BATCH, -1)
            raw, _ = await pipe.execute()
        if not raw:
            return 0
        items: list[dict[str, Any]] = []
        for entry in raw:
            try:
                items.append(json.loads(entry))
            except (TypeError, ValueError):
                continue
        drafts = await resolve_all(session, items)
        touched = await record(session, drafts, now=now)
        await session.commit()
        if push:
            await deliver(session, touched)
        return len(drafts)
    finally:
        await redis.delete(_LOCK_KEY)


#: **تسعون يوماً** — ما بعدها يُقرأ من سجلّه لا من الجرس
RETENTION_DAYS = 90


async def trim(session: AsyncSession, *, now: datetime | None = None) -> int:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=RETENTION_DAYS)
    result = await session.execute(delete(AdminAlert).where(AdminAlert.last_event_at < cutoff))
    return result.rowcount or 0


# ═════════════════════════ القراءة — الجرسُ والقائمة


def _visible(prefs: Prefs) -> list[str]:
    return [kind for kind in CATALOG if prefs.on(kind, "panel")]


def _unread_clause(user_id: uuid.UUID):
    read = select(AdminAlertRead.alert_id).where(
        AdminAlertRead.user_id == user_id, AdminAlertRead.alert_id == AdminAlert.id
    )
    return ~read.exists()


async def page(
    session: AsyncSession,
    user: User,
    *,
    category: str | None = None,
    kind: str | None = None,
    country: CountryCode | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    unread_only: bool = False,
    limit: int = 50,
    before: datetime | None = None,
) -> tuple[list[tuple[AdminAlert, bool]], int]:
    prefs = await prefs_of(session, user.id)
    conditions = [AdminAlert.kind.in_(_visible(prefs))]
    if category:
        conditions.append(AdminAlert.category == category)
    if kind:
        conditions.append(AdminAlert.kind == kind)
    if country:
        conditions.append(AdminAlert.country_code == country)
    if since:
        conditions.append(AdminAlert.last_event_at >= since)
    if until:
        conditions.append(AdminAlert.last_event_at < until)
    if before:
        conditions.append(AdminAlert.last_event_at < before)
    if unread_only:
        conditions.append(_unread_clause(user.id))
    is_read = (
        select(AdminAlertRead.alert_id)
        .where(AdminAlertRead.user_id == user.id, AdminAlertRead.alert_id == AdminAlert.id)
        .exists()
    )
    rows = await session.execute(
        select(AdminAlert, is_read).where(and_(*conditions)).order_by(AdminAlert.last_event_at.desc()).limit(limit)
    )
    unread = await unread_count(session, user, prefs=prefs)
    return [(alert, bool(read)) for alert, read in rows.all()], unread


async def unread_count(session: AsyncSession, user: User, *, prefs: Prefs | None = None) -> int:
    prefs = prefs or await prefs_of(session, user.id)
    total = await session.scalar(
        select(func.count()).select_from(AdminAlert).where(AdminAlert.kind.in_(_visible(prefs)), _unread_clause(user.id))
    )
    return int(total or 0)


async def mark_read(session: AsyncSession, user: User, *, ids: list[uuid.UUID] | None = None, everything: bool = False) -> int:
    if everything:
        prefs = await prefs_of(session, user.id)
        chosen = select(AdminAlert.id).where(AdminAlert.kind.in_(_visible(prefs)), _unread_clause(user.id))
        ids = list(await session.scalars(chosen))
    if not ids:
        return 0
    # **ما لا وجودَ له لا يُكتب** — معرّفٌ قديمٌ في لسانٍ مفتوحٍ بعد التقليم يكسر القيدَ ويُسقط الطلبَ كلَّه
    ids = list(await session.scalars(select(AdminAlert.id).where(AdminAlert.id.in_(ids))))
    if not ids:
        return 0
    statement = insert(AdminAlertRead).values([{"alert_id": alert_id, "user_id": user.id} for alert_id in ids])
    result = await session.execute(statement.on_conflict_do_nothing())
    return result.rowcount or 0


async def mark_read_by_receipt(session: AsyncSession, *, alert_id: uuid.UUID, user_id: uuid.UUID, receipt: str) -> None:
    """**زرُّ «مقروء» في الإشعار** — بلا جلسة: الإذنُ في الإيصال، **ولا يفعل إلا هذا** لهذا المستلم وهذا الصفّ."""
    if not hmac.compare_digest(read_receipt(user_id, alert_id), receipt or ""):
        raise NotFound("الإشعار غير موجود")
    if await session.get(AdminAlert, alert_id) is None:
        raise NotFound("الإشعار غير موجود")
    await session.execute(
        insert(AdminAlertRead).values(alert_id=alert_id, user_id=user_id).on_conflict_do_nothing()
    )


# ═════════════════════════ المعاينة — إشعارٌ بكلِّ نوعٍ إلى أجهزة المالك وحدَها، ولا يُكتب شيء

SAMPLE_AMOUNT = {CountryCode.JO: Decimal("4.750"), CountryCode.LY: Decimal("15.000"), CountryCode.DZ: Decimal("650")}
SAMPLE_DATA: dict[str, dict[str, Any]] = {
    "payment_succeeded": {"method": "cash"},
    "payment_failed": {"method": "card"},
    "ride_cancelled": {"by": "rider"},
    "low_rating": {"stars": 1, "rater": "rider"},
    "complaint": {"source": "dispute"},
    "feedback": {"guest": True, "app": "rider"},
    "documents_submitted": {"doc_type": "driving_license"},
    "documents_approved": {"doc_type": "national_id"},
    "documents_rejected": {"doc_type": "vehicle_registration"},
    "subscription_purchased": {"who": "captain", "method": "wallet"},
}
_SAMPLE_WITH_AMOUNT = {spec.kind for spec in _KINDS if spec.category == "money" or spec.kind == "ride_completed"}


def sample_alert(kind: str, country: CountryCode = CountryCode.JO, *, count: int = 1) -> AdminAlert:
    spec = CATALOG.get(kind)
    if spec is None:
        raise NotFound("نوعٌ غيرُ معروف")
    amount = SAMPLE_AMOUNT[country] * count if kind in _SAMPLE_WITH_AMOUNT else None
    return AdminAlert(
        id=uuid.uuid4(),
        kind=kind,
        category=spec.category,
        tone=spec.tone,
        country_code=country,
        count=count,
        amount=amount,
        currency=currency_for_country(country) if amount is not None else None,
        record_type=None,
        record_id=None,
        data=dict(SAMPLE_DATA.get(kind, {})) if count == 1 else {"grouped": True},
        group_key=f"sample:{kind}",
    )
