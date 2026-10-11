"""نظامُ الدفع الجديد — المرحلة ١ (SPEC §٧٣-هـ): **الطرقُ صفوفاً، والحالاتُ الخمس، والإيصالُ إجباريّ، ولا تُحتسب دفعةٌ مرّتين**.

**والأردنُ وليبيا لا يمرّان بسطرٍ هنا**: مفتاحُهما مطفأ، فلا طريقةَ تُعرض ولا طلبَ يُفتح — **ودفعُهما القائمُ تقيسه اختباراتُه كما هي**.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text

from app.core.exceptions import AppError
from app.models.audit import AdminAuditLog
from app.models.driver import Driver
from app.models.enums import (
    CountryCode,
    DriverStatus,
    FeatureKey,
    PaymentProviderKind,
    WalletTransactionType,
)
from app.models.feature_flag import FeatureFlag
from app.models.payment_request import PayMethod, PaymentRequest
from app.models.wallet import WalletTransaction
from tests.helpers import DRIVER, RIDER, auth, ensure_plan, register, rider_session
from tests.money_format import offenders

ALGERIAN_RIDER = RIDER | {"phone": "0551234567", "country_code": "DZ", "name": "راكبٌ من الجزائر"}
SECOND_ALGERIAN = RIDER | {"phone": "0552345678", "country_code": "DZ", "name": "راكبةٌ من وهران"}
ALGERIAN_DRIVER = DRIVER | {"phone": "0661234567", "country_code": "DZ", "name": "كبتنٌ من الجزائر"}

PNG = b"\x89PNG\r\n\x1a\n" + b"receipt-one" * 20
PNG_OTHER = b"\x89PNG\r\n\x1a\n" + b"receipt-two" * 20
PDF = b"%PDF-1.4 receipt"


async def algeria_market(session_factory, *, enabled: bool = True) -> dict[str, uuid.UUID]:
    """**سوقُ الجزائر بنظامه الجديد** — المحفظةُ والمفتاح، وطرقٌ ثلاث: BaridiMob (تحويلٌ برقم RIP) وكاشُ المكتب وطريقةٌ موقوفة."""
    async with session_factory() as session:
        for key in (FeatureKey.WALLET_ENABLED, FeatureKey.WALLET_TRANSFER_ENABLED):
            session.add(FeatureFlag(country_code=CountryCode.DZ, feature_key=key.value, enabled=True))
        session.add(
            FeatureFlag(
                country_code=CountryCode.DZ, feature_key=FeatureKey.PAYMENT_REQUESTS_ENABLED.value, enabled=enabled
            )
        )
        baridimob = PayMethod(
            country_code=CountryCode.DZ,
            kind=PaymentProviderKind.BANK_TRANSFER,
            code="baridimob",
            name="بريدي موب",
            enabled=True,
            account_holder="TAXO",
            account_number="00799999000123456789",
        )
        office = PayMethod(
            country_code=CountryCode.DZ, kind=PaymentProviderKind.CASH, code="office_cash", name="كاش في المكتب",
            enabled=True, sort_order=1,
        )
        dormant = PayMethod(
            country_code=CountryCode.DZ, kind=PaymentProviderKind.BANK_TRANSFER, code="bank", name="تحويلٌ بنكيّ",
            enabled=False, account_number="0011",
        )
        jordan = PayMethod(
            country_code=CountryCode.JO, kind=PaymentProviderKind.CASH, code="office_cash", name="كاش", enabled=True
        )
        session.add_all([baridimob, office, dormant, jordan])
        await session.commit()
        return {"baridimob": baridimob.id, "office": office.id, "dormant": dormant.id, "jordan": jordan.id}


async def submit(client: AsyncClient, headers: dict, provider: uuid.UUID, amount: str, *, reference: str | None = "BM-1",
                 receipt: bytes | None = PNG, purpose: str = "wallet_topup", plan_id: str | None = None):
    data = {"provider_id": str(provider), "purpose": purpose, "amount": amount}
    if reference is not None:
        data["reference"] = reference
    if plan_id is not None:
        data["plan_id"] = plan_id
    files = {"receipt": ("receipt.png", receipt, "image/png")} if receipt is not None else None
    return await client.post("/payment-requests", data=data, files=files, headers=headers)


async def balance(client: AsyncClient, headers: dict) -> str:
    response = await client.get("/wallet/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["balance"]


# ------------------------------------------------------------------ المفتاح والطرق


async def test_the_switch_is_off_everywhere_by_default_and_jordan_sees_nothing(client: AsyncClient, session_factory) -> None:
    await algeria_market(session_factory, enabled=False)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    jordanian = await rider_session(client, RIDER)
    for who in (algerian, jordanian):
        refused = await client.get("/payment-requests/methods", headers=who["headers"])
        assert refused.status_code == 403 and refused.json()["code"] == "feature_disabled"
    # **والأردنُ لا يقرأ من المفتاح شيئاً**: `/config` يحمله مطفأً كبقية المفاتيح
    config = (await client.get("/config")).json()
    jordan = next(c for c in config["countries"] if c["country_code"] == "JO")
    assert jordan["features"]["payment_requests_enabled"] is False


async def test_methods_list_only_what_is_enabled_in_my_market(client: AsyncClient, session_factory) -> None:
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    body = (await client.get("/payment-requests/methods", headers=algerian["headers"])).json()
    assert body["currency"] == "DZD"
    assert [m["id"] for m in body["methods"]] == [str(ids["baridimob"]), str(ids["office"])]
    transfer, cash = body["methods"]
    assert transfer["requires_receipt"] is True and transfer["account_number"] == "00799999000123456789"
    assert cash["requires_receipt"] is False
    # **وطريقةُ سوقٍ آخر ٤٠٤** — ولو كانت مفعَّلةً هناك
    assert (await client.get(f"/payment-requests/methods/{ids['jordan']}/qr", headers=algerian["headers"])).status_code == 404


# ------------------------------------------------------------------ الطلب وحرّاسه


async def test_a_transfer_needs_its_receipt_and_its_number(client: AsyncClient, session_factory) -> None:
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    no_receipt = await submit(client, algerian["headers"], ids["baridimob"], "1500", receipt=None)
    assert no_receipt.status_code == 422 and no_receipt.json()["field"] == "receipt"
    no_reference = await submit(client, algerian["headers"], ids["baridimob"], "1500", reference=None)
    assert no_reference.status_code == 422 and no_reference.json()["field"] == "reference"
    # **وكسرُ الدينار يُردّ** (§٧٣-ج/٧) — ولا يُقرَّب من وراء ظهر كاتبه
    fraction = await submit(client, algerian["headers"], ids["baridimob"], "1500.5")
    assert fraction.status_code == 422 and fraction.json()["code"] == "amount_not_multiple"
    # **والطريقةُ الموقوفةُ غيرُ متاحة**
    dormant = await submit(client, algerian["headers"], ids["dormant"], "1500")
    assert dormant.status_code == 404

    created = await submit(client, algerian["headers"], ids["baridimob"], "1500")
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "pending" and body["amount"] == "1500" and body["currency"] == "DZD"
    assert offenders(body) == []
    # **ولا رصيدَ يتغيّر قبل الاعتماد**
    assert await balance(client, algerian["headers"]) == "0"


async def test_cash_at_the_office_needs_no_receipt(client: AsyncClient, session_factory) -> None:
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    created = await submit(client, algerian["headers"], ids["office"], "2000", reference=None, receipt=None)
    assert created.status_code == 201, created.text


async def test_the_staff_amount_is_what_enters_the_wallet(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await submit(client, algerian["headers"], ids["baridimob"], "1500")).json()["id"]

    # **كسرٌ في مبلغ الموظّف يُردّ كذلك**
    fraction = await client.post(
        f"/admin/payment-requests/{request_id}/approve", json={"credited_amount": "1450.5"}, headers=admin_headers
    )
    assert fraction.status_code == 422

    approved = await client.post(
        f"/admin/payment-requests/{request_id}/approve", json={"credited_amount": "1450"}, headers=admin_headers
    )
    assert approved.status_code == 200, approved.text
    row = approved.json()
    assert row["status"] == "approved" and row["amount"] == "1500" and row["credited_amount"] == "1450"
    assert offenders(row) == []
    assert await balance(client, algerian["headers"]) == "1450"

    async with session_factory() as session:
        entries = (await session.scalars(select(WalletTransaction).where(
            WalletTransaction.idempotency_key == f"payment_request:{request_id}"))).all()
        assert len(entries) == 1 and entries[0].type is WalletTransactionType.TOPUP
        assert entries[0].amount == Decimal("1450.000")
        audited = await session.scalar(select(func.count()).select_from(AdminAuditLog).where(
            AdminAuditLog.entity_type == "payment_request", AdminAuditLog.entity_id == uuid.UUID(request_id)))
        assert audited == 1

    again = await client.post(f"/admin/payment-requests/{request_id}/approve", json={}, headers=admin_headers)
    assert again.status_code == 409 and again.json()["code"] == "invalid_status_transition"


async def test_every_rejection_carries_its_written_reason(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await submit(client, algerian["headers"], ids["baridimob"], "1500")).json()["id"]
    bare = await client.post(f"/admin/payment-requests/{request_id}/reject", json={"reason": " "}, headers=admin_headers)
    assert bare.status_code == 422
    rejected = await client.post(
        f"/admin/payment-requests/{request_id}/reject",
        json={"reason": "المبلغُ لم يصل حسابَ TAXO"},
        headers=admin_headers,
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    mine = (await client.get("/payment-requests/me", headers=algerian["headers"])).json()
    assert mine[0]["rejection_reason"] == "المبلغُ لم يصل حسابَ TAXO"
    assert await balance(client, algerian["headers"]) == "0"

    # **والقاعدةُ نفسُها ترفض رفضاً بلا سبب** — لا الشيفرةُ وحدَها
    async with session_factory() as session:
        with pytest.raises(Exception):
            await session.execute(text(
                "UPDATE payment_requests SET rejection_reason = NULL WHERE id = :i"), {"i": request_id})
            await session.commit()


async def test_one_transfer_is_never_counted_twice(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    ids = await algeria_market(session_factory)
    first = await rider_session(client, ALGERIAN_RIDER)
    second = await rider_session(client, SECOND_ALGERIAN)
    created = await submit(client, first["headers"], ids["baridimob"], "1500", reference="BM 77 01")
    assert created.status_code == 201

    # **المرجعُ نفسُه** — بمسافاتٍ وحروفٍ أخرى، ومن حسابٍ آخر
    same_reference = await submit(client, second["headers"], ids["baridimob"], "1500", reference="bm7701", receipt=PNG_OTHER)
    assert same_reference.status_code == 409 and same_reference.json()["code"] == "payment_already_submitted"
    # **والإيصالُ نفسُه** — برقمٍ آخر
    same_receipt = await submit(client, second["headers"], ids["baridimob"], "1500", reference="BM-99")
    assert same_receipt.status_code == 409

    # **ورفضُه يُفرج عنهما**: يُقدَّم التحويلُ نفسُه من جديد بإيصالٍ صحيح
    await client.post(
        f"/admin/payment-requests/{created.json()['id']}/reject", json={"reason": "الصورةُ غيرُ مقروءة"}, headers=admin_headers
    )
    again = await submit(client, first["headers"], ids["baridimob"], "1500", reference="BM 77 01")
    assert again.status_code == 201


async def test_the_owner_cancels_only_his_own_pending_request(client: AsyncClient, session_factory) -> None:
    ids = await algeria_market(session_factory)
    owner = await rider_session(client, ALGERIAN_RIDER)
    stranger = await rider_session(client, SECOND_ALGERIAN)
    request_id = (await submit(client, owner["headers"], ids["baridimob"], "1500")).json()["id"]
    assert (await client.post(f"/payment-requests/{request_id}/cancel", json={}, headers=stranger["headers"])).status_code == 404
    cancelled = await client.post(f"/payment-requests/{request_id}/cancel", json={}, headers=owner["headers"])
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancel_reason"] == "ألغاه صاحبُه"


async def test_a_refund_reverses_the_credit_only_while_the_money_is_there(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    first = (await submit(client, algerian["headers"], ids["office"], "2000", reference=None, receipt=None)).json()["id"]
    await client.post(f"/admin/payment-requests/{first}/approve", json={}, headers=admin_headers)

    refunded = await client.post(
        f"/admin/payment-requests/{first}/refund", json={"reason": "طلب صاحبُه ردَّ المال"}, headers=admin_headers
    )
    assert refunded.status_code == 200 and refunded.json()["status"] == "refunded"
    assert await balance(client, algerian["headers"]) == "0"

    # **ومالٌ أُنفق لا يُستردّ بقيدٍ سالب**
    second = (await submit(client, algerian["headers"], ids["office"], "1000", reference=None, receipt=None)).json()["id"]
    await client.post(f"/admin/payment-requests/{second}/approve", json={}, headers=admin_headers)
    async with session_factory() as session:
        from app.models.user import User
        from app.services import wallet

        owner = await session.get(User, uuid.UUID(algerian["user"]["id"]))
        await wallet.record(session, owner=owner, tx_type=WalletTransactionType.ADJUSTMENT, amount=Decimal("-600"))
        await session.commit()
    short = await client.post(
        f"/admin/payment-requests/{second}/refund", json={"reason": "خطأٌ في الاعتماد"}, headers=admin_headers
    )
    assert short.status_code == 409 and short.json()["code"] == "insufficient_balance"


async def test_a_payment_is_never_deleted(client: AsyncClient, session_factory) -> None:
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await submit(client, algerian["headers"], ids["baridimob"], "1500")).json()["id"]
    async with session_factory() as session:
        with pytest.raises(Exception, match="never deleted"):
            await session.execute(text("DELETE FROM payment_requests WHERE id = :i"), {"i": request_id})
    async with session_factory() as session:
        assert await session.get(PaymentRequest, uuid.UUID(request_id)) is not None


# ------------------------------------------------------------------ اشتراكُ الكبتن


async def _algerian_captain(client: AsyncClient, session_factory) -> dict:
    body = await register(client, ALGERIAN_DRIVER)
    async with session_factory() as session:
        driver = await session.scalar(select(Driver).where(Driver.user_id == uuid.UUID(body["user"]["id"])))
        driver.status = DriverStatus.APPROVED
        await session.commit()
        return {"headers": auth(body), "driver_id": driver.id, "user_id": body["user"]["id"]}


async def test_a_subscription_paid_by_transfer_is_a_topup_then_a_wallet_purchase(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    ids = await algeria_market(session_factory)
    captain = await _algerian_captain(client, session_factory)
    plan_id = await ensure_plan(session_factory, country="DZ", name="خطةُ اختبارٍ جزائريّة", price="1500")

    short = await submit(client, captain["headers"], ids["office"], "1000", reference=None, receipt=None,
                         purpose="subscription", plan_id=str(plan_id))
    assert short.status_code == 422 and short.json()["field"] == "amount"

    created = await submit(client, captain["headers"], ids["office"], "1500", reference=None, receipt=None,
                           purpose="subscription", plan_id=str(plan_id))
    assert created.status_code == 201, created.text
    approved = await client.post(f"/admin/payment-requests/{created.json()['id']}/approve", json={}, headers=admin_headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["subscription_id"] is not None and approved.json()["outcome_note"] is None
    # **شحنٌ ثمّ شراء**: المحفظةُ عادت صفراً، والاشتراكُ قائم
    assert await balance(client, captain["headers"]) == "0"
    async with session_factory() as session:
        from app.models.subscription import DriverSubscription

        rows = (await session.scalars(select(DriverSubscription).where(
            DriverSubscription.driver_id == captain["driver_id"]))).all()
        assert [str(r.id) for r in rows] == [approved.json()["subscription_id"]]


async def test_a_purchase_that_fails_leaves_the_money_in_the_wallet(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    ids = await algeria_market(session_factory)
    captain = await _algerian_captain(client, session_factory)
    plan_id = await ensure_plan(session_factory, country="DZ", name="خطةٌ تُوقف", price="1500")
    created = await submit(client, captain["headers"], ids["office"], "1500", reference=None, receipt=None,
                           purpose="subscription", plan_id=str(plan_id))
    # **الخطةُ تُوقف بين الطلب والاعتماد**
    async with session_factory() as session:
        from app.models.subscription import SubscriptionPlan

        plan = await session.get(SubscriptionPlan, plan_id)
        plan.is_active = False
        await session.commit()
    approved = await client.post(f"/admin/payment-requests/{created.json()['id']}/approve", json={}, headers=admin_headers)
    assert approved.status_code == 200
    assert approved.json()["subscription_id"] is None
    assert approved.json()["outcome_note"].startswith("شُحنت المحفظةُ ولم يُفعَّل الاشتراك")
    assert await balance(client, captain["headers"]) == "1500"


# ------------------------------------------------------------------ الـwebhook الموحّد
# **مقيسٌ في `test_payment_gateways.py`** على المحوِّلَين الحقيقيَّين بشبكةٍ مزيّفة (المرحلة ٣) — كان هنا وسيطٌ مزيَّفٌ في سجلٍّ أُزيل


# ------------------------------------------------------------------ اللوحة: الطرقُ وصلاحيّاتُها


async def test_a_transfer_method_is_not_enabled_without_a_destination(client: AsyncClient, admin_headers: dict) -> None:
    payload = {"country_code": "DZ", "kind": "bank_transfer", "code": "ccp", "name": "CCP", "enabled": True}
    refused = await client.post("/admin/payment-methods", json=payload, headers=admin_headers)
    assert refused.status_code == 422 and refused.json()["field"] == "enabled"
    created = await client.post("/admin/payment-methods", json=payload | {"account_number": "0079999"}, headers=admin_headers)
    assert created.status_code == 201, created.text
    duplicate = await client.post("/admin/payment-methods", json=payload | {"account_number": "1"}, headers=admin_headers)
    assert duplicate.status_code == 409

    method_id = created.json()["id"]
    changed = await client.patch(f"/admin/payment-methods/{method_id}", json={"account_number": "0071111"}, headers=admin_headers)
    assert changed.status_code == 200 and changed.json()["account_number"] == "0071111"
    # **ونزعُ الرقم عن طريقةٍ مفعَّلةٍ مرفوض** — كتفعيلها بلا رقم
    emptied = await client.patch(f"/admin/payment-methods/{method_id}", json={"account_number": ""}, headers=admin_headers)
    assert emptied.status_code == 422

    qr = await client.put(f"/admin/payment-methods/{method_id}/qr", files={"file": ("qr.png", PNG, "image/png")},
                          headers=admin_headers)
    assert qr.status_code == 200 and qr.json()["has_qr"] is True
    pdf = await client.put(f"/admin/payment-methods/{method_id}/qr", files={"file": ("qr.pdf", PDF, "application/pdf")},
                           headers=admin_headers)
    assert pdf.status_code == 422


async def test_changing_the_account_number_is_audited_with_before_and_after(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    ids = await algeria_market(session_factory)
    await client.patch(f"/admin/payment-methods/{ids['baridimob']}", json={"account_number": "0079000"}, headers=admin_headers)
    async with session_factory() as session:
        row = await session.scalar(select(AdminAuditLog).where(
            AdminAuditLog.entity_type == "payment_provider", AdminAuditLog.entity_id == ids["baridimob"]))
        assert row is not None
        assert row.details["changes"]["account_number"] == {"before": "00799999000123456789", "after": "0079000"}


async def test_support_reads_the_queue_but_moves_no_money(
    client: AsyncClient, session_factory, support_headers: dict
) -> None:
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await submit(client, algerian["headers"], ids["baridimob"], "1500")).json()["id"]
    listed = await client.get("/admin/payment-requests?status=pending", headers=support_headers)
    assert listed.status_code == 200 and listed.json()[0]["id"] == request_id
    for verb in ("approve", "reject"):
        body = {} if verb == "approve" else {"reason": "تجربةٌ ممنوعة"}
        refused = await client.post(f"/admin/payment-requests/{request_id}/{verb}", json=body, headers=support_headers)
        assert refused.status_code == 403
    # **والإيصالُ فيه حسابُ صاحبه** — لا يُفتح بصلاحية قراءة
    assert (await client.get(f"/admin/payment-requests/{request_id}/receipt", headers=support_headers)).status_code == 403
    # **ولا تحريرَ للطرق**
    edit = await client.patch(f"/admin/payment-methods/{ids['baridimob']}", json={"account_number": "1"}, headers=support_headers)
    assert edit.status_code == 403


async def test_the_receipt_reaches_finance_as_uploaded(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    ids = await algeria_market(session_factory)
    algerian = await rider_session(client, ALGERIAN_RIDER)
    request_id = (await submit(client, algerian["headers"], ids["baridimob"], "1500")).json()["id"]
    receipt = await client.get(f"/admin/payment-requests/{request_id}/receipt", headers=admin_headers)
    assert receipt.status_code == 200 and receipt.content == PNG
    assert receipt.headers["content-type"] == "image/png"


def test_the_signature_error_is_an_app_error() -> None:
    from app.services.payment_gateways import WebhookSignatureInvalid

    assert issubclass(WebhookSignatureInvalid, AppError)
