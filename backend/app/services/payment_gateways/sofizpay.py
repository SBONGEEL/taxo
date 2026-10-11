"""**SofizPay** — بطاقةُ CIB عبر SATIM (SPEC §٧٣-هـ المرحلة ٣)، **بوثائقه المنشورة** في `docs.sofizpay.com` (قُرئت ٢٠٢٦-١٠-١١).

**ما أُخذ من الوثائق حرفاً**:
- `GET https://sofizpay.com/make-cib-transaction/` (و`/sandbox/make-cib-transaction/` للتجربة) بـ`account` و`amount` و`full_name` و`phone`
  و`email` (إلزاميّةٌ كلُّها) و`return_url` و`webhook_url` و`memo` (حتى ٢٨ بايتاً) و`redirect`؛ ويعود بـ`success` و`cib_transaction_id`
  و`payment_url`.
- `GET https://sofizpay.com/cib-transaction-check/?order_number=…` ⇐ `orderStatus` (`2` مقبول · `6` مرفوض) و`respCode` (`"00"` مقبول) و
  `destination_account` و`Amount`.
- إشعارُ `cib.payment.updated` بـ`cib_transaction_id` و`order_number` و`message` و`signature`.

**وما لم تقله الوثائق — ولم يُخمَّن** (يُذكر في التقرير ويُطلب من SofizPay):
1. **خوارزميّةُ توقيع الإشعار ومفتاحُه** — الوثائقُ تقول «توقيعٌ Base64» ولا تقول بأيِّ مفتاحٍ ولا على أيِّ نصّ. **فلا يُصدَّق الإشعارُ
   أصلاً**: يُقرأ منه المعرّفُ وحدَه، **والحقيقةُ من بابِ الفحص** — مقبولٌ برمزيه، **وحسابُ الوجهة حسابُنا، والمبلغُ مبلغُ الطلب**.
2. **مصادقةُ الطلبات** — لا مفتاحَ يُرسل في الوثائق؛ والحسابُ (`account`) معرّفُ التاجر.
3. **تحميلُ الرسوم على المشتري** — لا معاملَ له؛ فرسومُه على TAXO وحدَها (`FEE_BEARERS`).
4. **بابٌ لاختبار الاتصال بلا أثر** — لا يوجد؛ فزرُّ الاختبار يقول ذلك ولا يفتح دفعةً ليختبر.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.models.enums import PaymentRequestStatus
from app.services import payment_gateways as base
from app.services.providers import credentials as credentials_service

BASE = "https://sofizpay.com"


class SofizPayGateway:
    name = "sofizpay"

    def __init__(self, *, account: str, sandbox: bool) -> None:
        self.account = account
        self.sandbox = sandbox

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            async with base.http_client() as http:
                response = await http.get(f"{BASE}{path}", params=params, headers={"Accept": "application/json"})
        except httpx.HTTPError as exc:
            raise base.GatewayError("تعذّر الوصولُ إلى SofizPay") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise base.GatewayError("جوابٌ غيرُ مقروءٍ من SofizPay") from exc
        if response.status_code >= 400 or not isinstance(body, dict):
            message = body.get("message") if isinstance(body, dict) else None
            raise base.GatewayError(f"SofizPay: {message}" if message else "رفض SofizPay الطلب")
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
        if not customer.email:
            # **البريدُ إلزاميٌّ عند SofizPay** — ولا يُخترع بريدٌ لصاحب الدفعة
            raise base.GatewayError("SofizPay يشترط بريداً إلكترونيّاً في حسابك — أضفه أو اختر طريقةً أخرى")
        path = "/sandbox/make-cib-transaction/" if self.sandbox else "/make-cib-transaction/"
        body = await self._get(
            path,
            {
                "account": self.account,
                "amount": str(int(amount)),
                "full_name": customer.full_name,
                "phone": customer.phone,
                "email": customer.email,
                "return_url": return_url,
                "webhook_url": webhook_url,
                "memo": description.encode()[:28].decode(errors="ignore"),
                "redirect": "no",
            },
        )
        cib_id, url = body.get("cib_transaction_id"), body.get("payment_url")
        if body.get("success") is not True or cib_id in (None, "") or not isinstance(url, str):
            raise base.GatewayError("جوابُ SofizPay بلا معرّفٍ أو رابط")
        return base.Checkout(external_id=str(cib_id), checkout_url=url)

    async def check(self, external_id: str) -> base.GatewayEvent | None:
        body = await self._get("/cib-transaction-check/", {"order_number": external_id})
        status = body.get("orderStatus")
        if status == 2 and body.get("respCode") == "00":
            # **حسابُ الوجهة حسابُنا** — دفعةٌ مقبولةٌ إلى حسابٍ آخر ليست دفعةً لنا ولو حملت المعرّف
            if body.get("destination_account") != self.account:
                return base.GatewayEvent(external_id, PaymentRequestStatus.REJECTED, reason="وصلت الدفعةُ حساباً غيرَ حساب TAXO")
            try:
                amount = Decimal(str(body.get("Amount")))
            except (InvalidOperation, ValueError):
                amount = None
            return base.GatewayEvent(external_id, PaymentRequestStatus.APPROVED, amount=amount)
        if status == 6:
            reason = body.get("respCode_desc") or body.get("errorMessage") or "رفض البنكُ الدفع"
            return base.GatewayEvent(external_id, PaymentRequestStatus.REJECTED, reason=str(reason)[:500])
        return None

    def webhook_ids(self, headers: Mapping[str, str], body: bytes) -> list[str]:
        """**لا تحقّقَ من توقيعٍ لم توثَّق خوارزميّتُه** — يُقرأ المعرّفُ وحدَه، **والفحصُ المباشرُ يقرّر** (رأسُ الملفّ ١)."""
        try:
            payload = json.loads(body)
        except ValueError:
            return []
        if not isinstance(payload, dict):
            return []
        external = payload.get("cib_transaction_id") or payload.get("order_number")
        return [str(external)] if external not in (None, "") else []

    async def test_connection(self) -> str:
        return (
            "لا بابَ في وثائق SofizPay يختبر الاتصالَ بلا أن يفتح دفعة — العقدُ محفوظٌ ولم يُقَس الاتصال. "
            "جرّب دفعةً بوضع التجربة (sandbox) من التطبيق."
        )


def build_sofizpay(values: Mapping[str, Any]) -> SofizPayGateway:
    account = str(values.get("account") or "").strip()
    if not account:
        raise base.GatewayUnavailable("لا حسابَ في عقد SofizPay")
    return SofizPayGateway(account=account, sandbox=credentials_service.is_on(values, "sandbox"))
