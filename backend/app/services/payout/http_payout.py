"""مُحوِّل payout عبر HTTP — **الملف الوحيد الذي يعرف شكل أسلاك المزود**.

> **ملاحظة تنفيذية صريحة، كالتي في `card_gateway/telr.py`.** لا عقد payout
> مُسلَّم ولا توثيق واجهته، فما دون **مبنيٌّ على الشكل الشائع لواجهات
> التحويل ويحتاج مطابقةً قبل أول تشغيل حقيقي**، مجموعٌ في ثوابت مسمّاة.
>
> وخطؤها لا يخصم من كبتنٍ شيئاً: قيد `withdrawal` لا يُكتب إلا على `paid`
> صريحة من جواب المزود، وأيُّ جوابٍ آخر يترك الطلب `approved` كما كان —
> ويبقى المسار اليدوي (تحويلٌ ثم تسجيلُ مرجع) قائماً بجانبه.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.payout.base import (
    REQUEST_TIMEOUT_SECONDS,
    PayoutError,
    PayoutRequest,
    PayoutState,
)

SEND_PATH = "/payouts"
CHECK_PATH = "/payouts/{provider_ref}"

FIELD_AMOUNT = "amount"
FIELD_CURRENCY = "currency"
FIELD_REFERENCE = "reference"
FIELD_METHOD = "method"
FIELD_BENEFICIARY = "beneficiary_name"
FIELD_DESTINATION = "destination"

REF_KEYS: tuple[str, ...] = ("id", "payout_id", "reference")
STATUS_KEY = "status"

PAID_STATUSES = frozenset({"paid", "completed", "settled", "success"})
FAILED_STATUSES = frozenset({"failed", "rejected", "cancelled", "returned"})


class HttpPayoutProvider:
    def __init__(self, *, endpoint: str, api_key: str) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _request(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """نداء واحد للمزود — نقطة الحقن الوحيدة في الاختبارات."""
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.request(
                    method,
                    f"{self._endpoint}{path}",
                    json=json,
                    headers=self._headers(),
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise PayoutError() from exc
        except ValueError as exc:
            raise PayoutError("جواب مزود التحويلات غير مقروء") from exc

        if not isinstance(payload, dict):
            raise PayoutError("جواب مزود التحويلات غير مقروء")
        return payload

    def _state(self, payload: dict[str, Any], fallback_ref: str) -> PayoutState:
        provider_ref = next(
            (str(payload[key]) for key in REF_KEYS if payload.get(key)), fallback_ref
        )
        status = str(payload.get(STATUS_KEY) or "").strip().lower()
        return PayoutState(
            provider_ref=provider_ref,
            # حالةٌ لا نعرفها تُحسب «قيد التنفيذ»: لا تعليم بالدفع على ظن
            settled=status in PAID_STATUSES or status in FAILED_STATUSES,
            paid=status in PAID_STATUSES,
            status_text=status or "غير معروفة",
        )

    async def send_payout(self, request: PayoutRequest) -> PayoutState:
        payload = await self._request(
            "POST",
            SEND_PATH,
            {
                FIELD_AMOUNT: str(request.amount),
                FIELD_CURRENCY: request.currency.value,
                # مرجعُنا يذهب مع الحوالة: به تُطابَق عند المزود ولا تُنفَّذ
                # مرتين إن أُعيد الطلب
                FIELD_REFERENCE: request.reference,
                FIELD_METHOD: request.method.value,
                FIELD_BENEFICIARY: request.beneficiary_name,
                FIELD_DESTINATION: request.destination,
            },
        )
        return self._state(payload, request.reference)

    async def check_payout(self, provider_ref: str) -> PayoutState:
        payload = await self._request(
            "GET", CHECK_PATH.format(provider_ref=provider_ref)
        )
        return self._state(payload, provider_ref)

    async def test_connection(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
                response = await http.get(self._endpoint, headers=self._headers())
        except httpx.HTTPError as exc:
            raise PayoutError("تعذّر الوصول إلى عنوان مزود التحويلات") from exc
        return f"الخدمة تستجيب (HTTP {response.status_code})"
