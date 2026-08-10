"""مُحوِّل CliQ acquirer — **الملف الوحيد الذي يعرف شكل أسلاك حساب التاجر**.

> **ملاحظة تنفيذية صريحة، كالتي في `card_gateway/telr.py`.** لا عقد acquirer
> مُسلَّم في هذه الجلسة ولا توثيق واجهته، فما دون **مبنيٌّ على الشكل الشائع
> لواجهات التحصيل ويحتاج مطابقةً بالتوثيق قبل أول تشغيل حقيقي**، وهو مجموعٌ
> في ثوابت مسمّاة كي تُطابَق في دقائق: مسارا الإنشاء والاستعلام، أسماء حقول
> الحمولة، وموضع الحالة في الجواب.
>
> وخطؤها لا يحرّك مالاً خطأً: الدفتر لا يتحرك إلا على `paid` صريحة من
> `check_charge`، وأيُّ جوابٍ لا يُقرأ يبقي الطلب معلّقاً — ومعلّقٌ لا يشحن
> محفظةً بشيء. **المزود الوهمي هو ما بُني عليه المسار واختُبر** (القسم 15/أ).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.services.cliq.base import (
    REQUEST_TIMEOUT_SECONDS,
    CliqCharge,
    CliqChargeRequest,
    CliqChargeState,
    CliqError,
)

# مسارات الخدمة تحت عنوان العقد
CREATE_PATH = "/charges"
CHECK_PATH = "/charges/{provider_ref}"

# أسماء حقول الحمولة
FIELD_MERCHANT = "merchant_id"
FIELD_ALIAS = "alias"
FIELD_AMOUNT = "amount"
FIELD_CURRENCY = "currency"
FIELD_REFERENCE = "reference"
FIELD_DESCRIPTION = "description"
FIELD_PAYER_NAME = "payer_name"
FIELD_PAYER_PHONE = "payer_phone"

# مواضع القراءة من الجواب
REF_KEYS: tuple[str, ...] = ("id", "charge_id", "reference")
QR_KEYS: tuple[str, ...] = ("qr_payload", "qr", "payload")
LINK_KEYS: tuple[str, ...] = ("deep_link", "link", "url")
STATUS_KEY = "status"

PAID_STATUSES = frozenset({"paid", "settled", "completed", "success"})
FAILED_STATUSES = frozenset({"failed", "declined", "expired", "cancelled"})


def _first(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value)
    return None


class CliqAcquirerProvider:
    def __init__(
        self, *, endpoint: str, merchant_id: str, api_key: str, company_alias: str
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._merchant_id = merchant_id
        self._api_key = api_key
        self._company_alias = company_alias

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """نداء واحد للمزود — نقطة الحقن الوحيدة في الاختبارات."""
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.request(
                    method, f"{self._endpoint}{path}", json=json, headers=self._headers()
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise CliqError() from exc
        except ValueError as exc:
            raise CliqError("جواب مزود كليك غير مقروء") from exc

        if not isinstance(payload, dict):
            raise CliqError("جواب مزود كليك غير مقروء")
        return payload

    async def create_charge(self, request: CliqChargeRequest) -> CliqCharge:
        payload = await self._request(
            "POST",
            CREATE_PATH,
            {
                FIELD_MERCHANT: self._merchant_id,
                FIELD_ALIAS: self._company_alias,
                FIELD_AMOUNT: str(request.amount),
                FIELD_CURRENCY: request.currency.value,
                FIELD_REFERENCE: request.reference,
                FIELD_DESCRIPTION: request.description,
                FIELD_PAYER_NAME: request.customer_name,
                FIELD_PAYER_PHONE: request.customer_phone,
            },
        )

        provider_ref = _first(payload, REF_KEYS)
        qr_payload = _first(payload, QR_KEYS)
        if not provider_ref or not qr_payload:
            raise CliqError("مزود كليك لم يعد برمز الدفع")

        return CliqCharge(
            provider_ref=provider_ref,
            qr_payload=qr_payload,
            deep_link=_first(payload, LINK_KEYS),
        )

    async def check_charge(self, provider_ref: str) -> CliqChargeState:
        payload = await self._request(
            "GET", CHECK_PATH.format(provider_ref=provider_ref)
        )
        status = str(payload.get(STATUS_KEY) or "").strip().lower()

        amount: Decimal | None = None
        raw_amount = payload.get(FIELD_AMOUNT)
        if raw_amount is not None:
            try:
                amount = Decimal(str(raw_amount))
            except (InvalidOperation, ValueError):
                amount = None

        return CliqChargeState(
            provider_ref=provider_ref,
            # حالةٌ لا نعرفها تُحسب «لم تُحسم»: لا تخمين في اتجاه ولا في الآخر
            settled=status in PAID_STATUSES or status in FAILED_STATUSES,
            paid=status in PAID_STATUSES,
            status_text=status or "غير معروفة",
            amount=amount,
        )

    async def test_connection(self) -> str:
        """أيُّ جوابٍ من الخدمة دليلُ وصول؛ الفشل انقطاعُ الشبكة أو العنوان."""
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.get(self._endpoint, headers=self._headers())
        except httpx.HTTPError as exc:
            raise CliqError("تعذّر الوصول إلى عنوان مزود كليك") from exc
        return f"الخدمة تستجيب (HTTP {response.status_code})"
