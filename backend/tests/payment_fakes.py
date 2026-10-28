"""**وسيطان مزيّفان بلا شبكة** — `httpx.MockTransport` يجيب بأشكال الوثائق المنشورة حرفاً (SPEC §٧٣-هـ المرحلة ٣).

**المحوِّلُ الحقيقيُّ هو المُختبَر** (`ChargilyGateway` · `SofizPayGateway`) — المزيَّفُ هنا الشبكةُ وحدَها: ما يُرسَل يُقرأ ويُقاس، وما يعود
بأشكال `dev.chargily.com` و`docs.sofizpay.com`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from typing import Any

import httpx

from app.models.enums import CountryCode, PaymentProviderKind
from app.models.payment_request import PayMethod
from app.services import payment_gateways
from tests.helpers import _enable_provider

#: **مفتاحٌ مولَّدٌ لكلِّ تشغيلٍ لا حرفيّ** — قيمةٌ حرفيّةٌ بشكل مفتاحٍ أوقفت ماسحَ الأسرار في الرفع (٢٠٢٦-١٠-١١)
CHARGILY_SECRET = "test_sk_" + secrets.token_hex(12)
SOFIZPAY_ACCOUNT = "GTAXOFAKEACCOUNT0000000000000000000000000000000000000000"
#: **حسابٌ بشكل مفتاح Stellar العامّ** (`G` وخمسةٌ وخمسون من أبجديّة base32) — لدفتر SofizPay وحدَه؛ مولَّدٌ لا حسابُ أحد
SOFIZPAY_LEDGER_ACCOUNT = "G" + "TAXOLEDGER" + "A" * 45

#: **مفتاحُ توقيعٍ مولَّدٌ لكلِّ تشغيل** — يحلّ عامُّه محلَّ مفتاح SofizPay في الاختبار، فيوقّع المزيَّفُ كما يوقّع SofizPay (§٨٧/٥)
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402

_SOFIZ_SIGNER = rsa.generate_private_key(public_exponent=65537, key_size=2048)
SOFIZ_TEST_PUBLIC_PEM = _SOFIZ_SIGNER.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
)


class ChargilyFake:
    def __init__(self) -> None:
        self.status: dict[str, str] = {}
        self.amount: dict[str, int] = {}
        self.fees: dict[str, dict[str, int]] = {}
        self.created: list[dict[str, Any]] = []
        #: **عملاءُ Chargily** (§٧٦-ع/٢) — ما أُنشئ بجسمه، و«المحذوفُ عنده» يُسقط صفحةً تذكره
        self.customers: list[dict[str, Any]] = []
        self.dead_customers: set[str] = set()
        #: **حقولٌ يقولها عن صفحةٍ بعينها** (`livemode` · `currency`) — تُضاف إلى جواب `GET /checkouts/{id}`
        self.extra: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _fees(amount: int, allocation: str) -> dict[str, int]:
        """**رسومٌ بشكل الوثائق** (`fees` · `fees_on_customer` · `fees_on_merchant`) — ٢٪ تقريبيّةٌ للاختبار وحدَه، على من تقوله الطريقة."""
        fee = max(15, amount * 2 // 100)
        return {"fees": fee, "fees_on_customer": fee if allocation == "customer" else 0,
                "fees_on_merchant": fee if allocation == "merchant" else 0}

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {CHARGILY_SECRET}"
        path = request.url.path
        if request.method == "POST" and path.endswith("/customers"):
            body = json.loads(request.content)
            self.customers.append(body)
            return httpx.Response(200, json={"id": f"cus_{len(self.customers):04d}", "entity": "customer", **body})
        if request.method == "POST" and path.endswith("/checkouts"):
            body = json.loads(request.content)
            if body.get("customer_id") in self.dead_customers:
                return httpx.Response(422, json={"message": "The selected customer id is invalid."})
            checkout_id = f"chk_{len(self.created) + 1:04d}"
            self.created.append(body)
            self.status[checkout_id] = "pending"
            self.amount[checkout_id] = body["amount"]
            self.fees[checkout_id] = self._fees(body["amount"], body.get("chargily_pay_fees_allocation", "merchant"))
            return httpx.Response(200, json={
                "id": checkout_id, "entity": "checkout", "amount": body["amount"], "currency": "dzd", "status": "pending",
                "checkout_url": f"https://pay.chargily.dz/test/checkouts/{checkout_id}/pay", **self.fees[checkout_id],
            })
        if request.method == "GET" and "/checkouts/" in path:
            checkout_id = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={
                "id": checkout_id, "entity": "checkout", "status": self.status.get(checkout_id, "pending"),
                "amount": self.amount.get(checkout_id), "currency": "dzd", **self.fees.get(checkout_id, {}),
                "checkout_url": f"https://pay.chargily.dz/test/checkouts/{checkout_id}/pay",
                **self.extra.get(checkout_id, {}),
            })
        if request.method == "GET" and path.endswith("/balance"):
            return httpx.Response(200, json={"entity": "balance", "livemode": False, "wallets": []})
        return httpx.Response(404, json={"message": "not found"})

    @staticmethod
    def signed(checkout_id: str, event: str = "checkout.paid", *, key: str = CHARGILY_SECRET) -> tuple[bytes, dict[str, str]]:
        """**إشعارٌ موقَّعٌ كما تقول الوثائق**: `HMAC-SHA256` للجسم الخام بالمفتاح السرّيّ في ترويسة `signature`."""
        body = json.dumps({"id": "evt_1", "entity": "event", "type": event, "data": {"id": checkout_id, "status": "paid"}}).encode()
        return body, {"signature": hmac.new(key.encode(), body, hashlib.sha256).hexdigest(), "content-type": "application/json"}


class SofizPayFake:
    def __init__(self) -> None:
        self.check: dict[str, dict[str, Any]] = {}
        self.created: list[dict[str, str]] = []
        #: **انقطاعُ الوسيط** (§٨٥) — `503` لكلِّ نداء
        self.down = False
        self.paths: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.paths.append(path)
        if self.down:
            return httpx.Response(503, text="Service Unavailable")
        if path.endswith("/make-cib-transaction/"):
            params = dict(request.url.params)
            self.created.append(params)
            cib_id = f"25170{len(self.created):05d}"
            self.check[cib_id] = {"order_number": cib_id, "orderStatus": 0, "respCode": "", "destination_account": params["account"],
                                  "Amount": f"{params['amount']}.00"}
            return httpx.Response(200, json={
                "success": True, "transaction_id": str(uuid.uuid4()), "cib_transaction_id": cib_id,
                "payment_url": f"https://cib.satim.dz/payment/{cib_id}", "amount": params["amount"],
                "status": "pending_user_transfer_start",
            })
        if path.endswith("/cib-transaction-check/"):
            order = request.url.params["order_number"]
            # **ومعاملةٌ لا يعرفها** بصيغة الوثائق: `{"error": "CIB transaction not found"}`
            return httpx.Response(200, json=self.check.get(order, {"error": "CIB transaction not found"}))
        return httpx.Response(404, json={"status": "error", "message": "Invalid or missing parameters."})


def sofizpay_signed(notice: dict[str, Any], *, url_safe: bool = True) -> dict[str, Any]:
    """**إشعارٌ موقَّعٌ كما يوقّع SofizPay** — RSA PKCS#1 v1.5 بـSHA-256 على `message`، وBase64 الآمنُ للعناوين كما يقرؤه الـSDK."""
    import base64

    message = "|".join(str(notice.get(k, "")) for k in ("cib_transaction_id", "payment_status", "amount"))
    raw = _SOFIZ_SIGNER.sign(message.encode(), padding.PKCS1v15(), hashes.SHA256())
    signature = (base64.urlsafe_b64encode(raw).rstrip(b"=") if url_safe else base64.b64encode(raw)).decode()
    return notice | {"message": message, "signature": signature}


class HorizonFake:
    """**Horizon مزيَّفٌ بأشكاله المنشورة** — `/accounts/{G}` بأرصدته، و`/accounts/{G}/payments` بسجلّاتٍ ومؤشّرات."""

    def __init__(self) -> None:
        self.balances: dict[str, list[dict[str, Any]]] = {}
        #: **سجلّاتُ الدفع الأحدثُ آخراً** — كما يرتّبها `order=asc`
        self.payments: dict[str, list[dict[str, Any]]] = {}
        self.calls: list[str] = []

    def pay(self, account: str, *, amount: str, incoming: bool = True, memo: str = "", asset_code: str = "DZT",
            created_at: str = "2026-10-28T10:00:00Z") -> dict[str, Any]:
        from app.services import sofizpay_ledger

        rows = self.payments.setdefault(account, [])
        token = str(1000 + len(rows))
        other = "G" + "OTHER" + "B" * 50
        record = {
            "id": token, "paging_token": token, "type": "payment", "created_at": created_at,
            "asset_type": "credit_alphanum4", "asset_code": asset_code, "asset_issuer": sofizpay_ledger.ASSET_ISSUER,
            "from": other if incoming else account, "to": account if incoming else other, "amount": amount,
            "transaction_hash": f"tx{token}", "transaction": {"memo": memo},
        }
        rows.append(record)
        return record

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(f"{path}?{request.url.query.decode() if isinstance(request.url.query, bytes) else request.url.query}")
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "accounts":
            account = parts[1]
            if account not in self.balances and account not in self.payments:
                return httpx.Response(404, json={"status": 404, "title": "Resource Missing"})
            if len(parts) == 2:
                return httpx.Response(200, json={"id": account, "balances": self.balances.get(account, [])})
            if parts[2] == "payments":
                params = dict(request.url.params)
                rows = list(self.payments.get(account, []))
                cursor = params.get("cursor")
                if params.get("order") == "desc":
                    rows = rows[::-1]
                    if cursor:
                        rows = [r for r in rows if int(r["paging_token"]) < int(cursor)]
                elif cursor and cursor != "now":
                    rows = [r for r in rows if int(r["paging_token"]) > int(cursor)]
                limit = int(params.get("limit", 10))
                page = rows[:limit]
                links: dict[str, Any] = {}
                if len(rows) > limit:
                    order = params.get("order", "asc")
                    links["next"] = {"href": f"https://horizon.stellar.org/accounts/{account}/payments?order={order}&limit={limit}&cursor={page[-1]['paging_token']}"}
                return httpx.Response(200, json={"_embedded": {"records": page}, "_links": links})
        return httpx.Response(404, json={"status": 404})


class Router:
    """**نقلٌ واحدٌ للوسطاء** — يوجّه بالمضيف."""

    def __init__(self, chargily: ChargilyFake, sofizpay: SofizPayFake, horizon: HorizonFake | None = None) -> None:
        self.chargily, self.sofizpay = chargily, sofizpay
        self.horizon = horizon or HorizonFake()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "pay.chargily.net":
            return self.chargily.handler(request)
        if request.url.host == "sofizpay.com":
            return self.sofizpay.handler(request)
        if request.url.host == "horizon.stellar.org":
            return self.horizon.handler(request)
        return httpx.Response(599)


def install_transport(monkeypatch, horizon: HorizonFake | None = None) -> tuple[ChargilyFake, SofizPayFake]:
    from app.services.payment_gateways import sofizpay as sofizpay_module

    chargily, sofizpay = ChargilyFake(), SofizPayFake()
    monkeypatch.setattr(payment_gateways, "http_transport", httpx.MockTransport(Router(chargily, sofizpay, horizon)))
    # **عامُّ مفتاح التوقيع المولَّد** محلَّ عامِّ SofizPay — فالتحقّقُ الحقيقيُّ هو المُختبَر، والموقِّعُ وحدَه مزيَّف
    monkeypatch.setattr(sofizpay_module, "SOFIZPAY_PUBLIC_KEY_PEM", SOFIZ_TEST_PUBLIC_PEM)
    return chargily, sofizpay


async def add_gateway_method(
    session_factory, integration: str, *, fee_bearer: str = "taxo", contract: bool = True, test_mode: bool = False,
    send_customer: bool = False,
) -> uuid.UUID:
    """**عقدُ الوسيط في صفحة العقود** (بالخدمة نفسِها) **وطريقتُه مفعَّلةً في نظام الدفع**.

    **و`test_mode`** (§٧٤-ط/٥): عقدٌ بوضع التجربة لا يفتحه إلا حسابُ تجربة — فالافتراضُ هنا **حيٌّ** لأن الاختبارات تدفع بحساباتٍ
    حقيقيّةٍ مزيّفة الشبكة؛ والوضعُ التجريبيُّ يُختبر باسمه."""
    if contract and integration == "chargily":
        await _enable_provider(
            session_factory, "chargily",
            {"secret_key": CHARGILY_SECRET, "test_mode": test_mode, "send_customer": send_customer}, country="DZ"
        )
    if contract and integration == "sofizpay":
        await _enable_provider(session_factory, "sofizpay", {"account": SOFIZPAY_ACCOUNT, "sandbox": test_mode}, country="DZ")
    async with session_factory() as session:
        method = PayMethod(
            country_code=CountryCode.DZ, kind=PaymentProviderKind.BANK_TRANSFER, code=integration,
            name={"chargily": "الذهبية وCIB", "sofizpay": "CIB عبر SofizPay"}[integration],
            integration=integration, enabled=True, fee_bearer=fee_bearer, sort_order=3,
        )
        session.add(method)
        await session.commit()
        return method.id
