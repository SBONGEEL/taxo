"""**Chargily Pay V2** — الذهبية وCIB (SPEC §٧٣-هـ المرحلة ٣)، **بوثائقه المنشورة** في `dev.chargily.com/pay-v2` (قُرئت ٢٠٢٦-١٠-١١).

**ما أُخذ من الوثائق حرفاً**:
- الأساسُ `https://pay.chargily.net/test/api/v2` للاختبار و`https://pay.chargily.net/api/v2` للحيّ، والمصادقةُ `Authorization: Bearer <المفتاح السرّيّ>`.
- `POST /checkouts` بـ`amount` (عددٌ صحيح) و`currency` («dzd» وحدَها مدعومة) و`success_url` (إلزاميّ) و`failure_url` و`webhook_endpoint` و`locale`
  و`chargily_pay_fees_allocation` (`customer` · `merchant` · `split`)؛ ويعود بـ`id` و`checkout_url`.
- `GET /checkouts/{id}` بالحال: `pending` · `processing` · `paid` · `failed` · `canceled`. و`GET /balance` (زرُّ الاختبار).
- **الـwebhook**: ترويسةُ `signature` = `HMAC-SHA256` لجسم الطلب **الخام** بالمفتاح السرّيّ، **ومقارنةٌ ثابتةُ الزمن**؛ والجسمُ `type` و`data`.

**وما لم يُرسل لأنه غيرُ موثَّقٍ بما يكفي**: `metadata` (نوعُه في الوثائق «مصفوفة» بلا شكل) — والطلبُ يُعرف بمعرّف الصفحة نفسِها.
**ولا حدَّ أدنى للمبلغ موثَّق** — فما يرفضه الوسيطُ يُعاد نصُّه للمستخدم ولا يُخترع حدّ.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

import httpx

from app.models.enums import PaymentRequestStatus
from app.services import payment_gateways as base
from app.services.providers import credentials as credentials_service

TEST_BASE = "https://pay.chargily.net/test/api/v2"
LIVE_BASE = "https://pay.chargily.net/api/v2"

#: **من يحمل الرسوم بلغة TAXO ⇐ بلغة Chargily** (`chargily_pay_fees_allocation`)
FEES_ALLOCATION = {"taxo": "merchant", "user": "customer", "split": "split"}


class ChargilyGateway:
    name = "chargily"

    def __init__(self, *, secret_key: str, test_mode: bool) -> None:
        self._key = secret_key
        self.base_url = TEST_BASE if test_mode else LIVE_BASE
        self.test_mode = test_mode

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with base.http_client() as http:
                response = await http.request(
                    method,
                    f"{self.base_url}{path}",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._key}", "Accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            raise base.GatewayError("تعذّر الوصولُ إلى Chargily") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من Chargily") from exc
        if response.status_code >= 400 or not isinstance(body, dict):
            message = body.get("message") if isinstance(body, dict) else None
            raise base.GatewayError(f"Chargily: {message}" if message else "رفض Chargily الطلب")
        return body

    async def checkout(
        self,
        *,
        amount: Decimal,
        description: str,
        return_url: str,
        webhook_url: str,
        fee_bearer: str,
        customer: base.CheckoutCustomer,
    ) -> base.Checkout:
        # **عددٌ صحيحٌ بالدينار** (الوثائق: `amount` integer) — والطلبُ دينارٌ صحيحٌ أصلاً (§٧٣-ج/٣)
        body = await self._request(
            "POST",
            "/checkouts",
            {
                "amount": int(amount),
                "currency": "dzd",
                "success_url": return_url,
                "failure_url": return_url,
                "webhook_endpoint": webhook_url,
                "description": description[:255],
                "locale": "ar",
                "chargily_pay_fees_allocation": FEES_ALLOCATION[fee_bearer],
            },
        )
        checkout_id, url = body.get("id"), body.get("checkout_url")
        if not isinstance(checkout_id, str) or not isinstance(url, str):
            raise base.GatewayError("جوابُ Chargily بلا معرّفٍ أو رابط")
        return base.Checkout(external_id=checkout_id, checkout_url=url)

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        body = await self._request("GET", f"/checkouts/{external_id}")
        status = body.get("status")
        amount = Decimal(str(body["amount"])) if body.get("amount") is not None else None
        if status == "paid":
            return base.GatewayEvent(external_id, PaymentRequestStatus.APPROVED, amount=amount)
        if status == "failed":
            return base.GatewayEvent(external_id, PaymentRequestStatus.REJECTED, reason="رفض الوسيطُ الدفع")
        if status == "canceled":
            return base.GatewayEvent(external_id, PaymentRequestStatus.CANCELLED, reason="أُلغي الدفعُ عند الوسيط")
        return None  # `pending` · `processing`

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        signature = headers.get("signature") or ""
        expected = hmac.new(self._key.encode(), body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            raise base.WebhookSignatureInvalid()
        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise base.WebhookSignatureInvalid() from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not str(payload.get("type", "")).startswith("checkout."):
            return []
        checkout_id = data.get("id")
        return [checkout_id] if isinstance(checkout_id, str) else []

    async def test_connection(self) -> str:
        await self._request("GET", "/balance")
        return f"الاتصالُ بـChargily يعمل — الوضع: {'اختبار' if self.test_mode else 'حيّ'}"


def build_chargily(values: Mapping[str, Any]) -> ChargilyGateway:
    key = str(values.get("secret_key") or "").strip()
    if not key:
        raise base.GatewayUnavailable("لا مفتاحَ سرّيّاً في عقد Chargily")
    return ChargilyGateway(secret_key=key, test_mode=credentials_service.is_on(values, "test_mode"))
