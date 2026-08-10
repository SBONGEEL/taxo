"""صفحة دفع كليك داخل التطبيق (SPEC القسم 6.2 — المرحلة 9).

القناة التي لا شاهد آلي عليها: المال ينتقل من الراكب إلى alias **الكبتن**
مباشرةً فلا يمر بحساب الشركة. حمايتُها من النزاع هي **السجل والمرجع**، فكل ما
يُختبر هنا يدور حول ذلك السجل: أن يحمل ما حُوِّل عليه فعلاً لا ما يقوله ملفُّ
الكبتن اليوم، وأن يُكتب مرةً واحدة، وأن يصل الكبتنَ فور كتابته.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import Counter
from decimal import Decimal

from httpx import AsyncClient, Response
from sqlalchemy import select

from app.models.payment import Payment
from app.services import cliq_qr
from tests.helpers import (
    DRIVER,
    EXPECTED_FARE,
    OTHER_RIDER,
    RIDER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    enable_features,
    enable_push_provider,
    pay_ride,
    payments_of,
    pushes_to,
    register,
    register_device,
    set_cliq_alias,
)

DRIVER_ALIAS = "0799999999"
TRANSFER_REFERENCE = "FT24081012345678"


async def _rider(client: AsyncClient, payload: dict = RIDER) -> dict:
    body = await register(client, payload)
    return {"headers": auth(body), "user_id": body["user"]["id"]}


async def _open_cliq_payment(
    client: AsyncClient, session_factory, *, alias: str = DRIVER_ALIAS
) -> tuple[dict, dict, dict, dict]:
    """راكبٌ وكبتنٌ ورحلةٌ منتهية ودفعةُ كليك مفتوحة بأجرة 8.000."""
    await enable_features(session_factory, "cliq_enabled")
    rider = await _rider(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)
    await set_cliq_alias(session_factory, driver["driver_id"], alias)

    body = (await pay_ride(client, rider["headers"], ride["id"], "cliq")).json()
    assert body["cliq_charge"] is not None, body
    return rider, driver, ride, body


async def _submit(
    client: AsyncClient, headers: dict, payment_id: str, reference: str = TRANSFER_REFERENCE
) -> Response:
    return await client.post(
        f"/payments/{payment_id}/cliq-reference",
        json={"transfer_reference": reference},
        headers=headers,
    )


# ------------------------------------------------------------------ البطاقة


async def test_cliq_charge_carries_the_alias_amount_and_internal_reference(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """«رمزٌ يحمل alias الكبتن والمبلغ ومرجعاً داخلياً» (SPEC القسم 6.2)."""
    _rider_, _driver, _ride, body = await _open_cliq_payment(client, session_factory)
    charge = body["cliq_charge"]

    assert charge["alias"] == DRIVER_ALIAS
    assert charge["amount"] == EXPECTED_FARE
    assert charge["currency"] == "JOD"
    assert charge["reference"].startswith(cliq_qr.REFERENCE_PREFIX)
    assert charge["transfer_reference"] is None

    # الثلاثة داخل الحمولة نفسها: هي ما يقرؤه تطبيق البنك لا ما نعرضه بجانبها
    assert DRIVER_ALIAS in charge["qr_payload"]
    assert charge["reference"] in charge["qr_payload"]
    assert EXPECTED_FARE in charge["qr_payload"]
    assert charge["reference"] in charge["deep_link"]


async def test_qr_payload_checksum_matches_the_emvco_layout(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الرمز يُقرأ بمعيار EMVCo: الحقل 63 مطابقٌ لما يحسبه القارئ.

    قارئٌ يحسب CRC على النص **بما فيه** `6304` نفسه — فإن أخطأ البناءُ هذا
    التفصيل رفض كلُّ تطبيق بنكٍ رمزاً يبدو سليماً بالعين.
    """
    _rider_, _driver, _ride, body = await _open_cliq_payment(client, session_factory)
    payload = body["cliq_charge"]["qr_payload"]

    body_without_crc, crc = payload[:-4], payload[-4:]
    assert body_without_crc.endswith("6304")
    assert crc == cliq_qr.crc16(body_without_crc)
    # وأول حقلين: نسخة الصيغة، ورمزٌ ديناميكي (لعمليةٍ واحدة لا لافتة ثابتة)
    assert payload.startswith("000201010212")


async def test_alias_is_frozen_on_the_payment_not_read_from_the_driver(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """تغييرُ الكبتن aliasه لا يغيّر وجهةَ حوالةٍ وقعت (SPEC القسم 6.2/5).

    السجلُّ هو كلُّ ما يملكه فاصلُ النزاع في هذه القناة؛ وaliasٌ يُقرأ لحظةَ
    العرض يجعله يقرأ بعد أسبوع وجهةً غير التي حُوِّل عليها فعلاً.
    """
    rider, driver, ride, body = await _open_cliq_payment(client, session_factory)
    await set_cliq_alias(session_factory, driver["driver_id"], "0788888888")

    after = await payments_of(client, rider["headers"], ride["id"])
    assert after["cliq_charge"]["alias"] == DRIVER_ALIAS
    assert after["payments"][0]["cliq_alias"] == DRIVER_ALIAS


# ------------------------------------------------------------ مرجع الحوالة


async def test_rider_submits_the_transfer_reference_and_it_is_recorded(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الخطوة الثالثة: يعود الراكب من بنكه ويُدخل المرجع (SPEC القسم 6.3)."""
    rider, _driver, _ride, body = await _open_cliq_payment(client, session_factory)
    payment_id = body["cliq_charge"]["payment_id"]

    response = await _submit(client, rider["headers"], payment_id)
    assert response.status_code == 200, response.text

    charge = response.json()["cliq_charge"]
    assert charge["transfer_reference"] == TRANSFER_REFERENCE
    assert charge["transfer_reference_at"] is not None
    # الدفعة تبقى `pending`: المرجع قولُ الراكب، والتأكيد قولُ الكبتن
    assert response.json()["payments"][0]["status"] == "pending"
    assert response.json()["payments"][0]["cliq_transfer_reference"] == TRANSFER_REFERENCE


async def test_the_transfer_reference_is_written_once_and_never_edited(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """«سجلٌّ غير قابل للتعديل» (SPEC القسم 6.5) — لا يُكتب فوق مرجعٍ أُعلن."""
    rider, _driver, _ride, body = await _open_cliq_payment(client, session_factory)
    payment_id = body["cliq_charge"]["payment_id"]

    assert (await _submit(client, rider["headers"], payment_id)).status_code == 200
    second = await _submit(client, rider["headers"], payment_id, "FT-OTHER-REFERENCE")

    assert second.status_code == 409
    assert second.json()["code"] == "conflict"
    async with session_factory() as session:
        stored = await session.scalar(
            select(Payment.cliq_transfer_reference).where(
                Payment.id == uuid.UUID(payment_id)
            )
        )
    assert stored == TRANSFER_REFERENCE


async def test_only_the_riders_own_payment_accepts_a_reference(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """لا IDOR: راكبٌ آخر لا يكتب على دفعةٍ ليست له (SPEC القسم 14)."""
    _rider_, _driver, _ride, body = await _open_cliq_payment(client, session_factory)
    intruder = await _rider(client, OTHER_RIDER)

    response = await _submit(
        client, intruder["headers"], body["cliq_charge"]["payment_id"]
    )
    assert response.status_code == 404


async def test_the_driver_cannot_submit_a_reference_for_his_rider(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """المرجع يكتبه من حوّل — والكبتن يؤكد أو ينازع لا غير."""
    _rider_, driver, _ride, body = await _open_cliq_payment(client, session_factory)
    response = await _submit(
        client, driver["headers"], body["cliq_charge"]["payment_id"]
    )
    assert response.status_code == 403


async def test_a_cash_payment_has_no_transfer_reference(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """الكاش يقع يداً بيد فلا مرجع له — ولا رمزَ كليك على شاشته."""
    rider = await _rider(client)
    driver = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, driver)
    ride = await completed_ride(client, rider["headers"], driver)

    body = (await pay_ride(client, rider["headers"], ride["id"], "cash")).json()
    assert body["cliq_charge"] is None

    response = await _submit(client, rider["headers"], body["payments"][0]["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_payment_transition"


async def test_the_charge_disappears_once_the_driver_confirms(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """رمزٌ يبقى معروضاً بعد التأكيد يدعو إلى تحويلٍ ثانٍ."""
    rider, driver, ride, body = await _open_cliq_payment(client, session_factory)
    payment_id = body["cliq_charge"]["payment_id"]
    await _submit(client, rider["headers"], payment_id)

    confirmed = await client.post(
        f"/payments/{payment_id}/confirm", headers=driver["headers"]
    )
    assert confirmed.status_code == 200, confirmed.text

    after = await payments_of(client, rider["headers"], ride["id"])
    assert after["cliq_charge"] is None
    # والسجل يبقى كاملاً على الصف بعد أن اختفت البطاقة
    assert after["payments"][0]["cliq_transfer_reference"] == TRANSFER_REFERENCE
    assert after["payments"][0]["confirmed_by"] == "driver"


# ------------------------------------------------------------------ الإشعار


async def test_submitting_the_reference_notifies_the_driver(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """«إشعار فوري للكبتن» (SPEC القسم 6.4) — على المقبس وعلى Push معاً."""
    await enable_push_provider(session_factory)
    rider, driver, _ride, body = await _open_cliq_payment(client, session_factory)
    await register_device(
        client, driver["headers"], device_id="driver-phone", token="fcm-driver"
    )

    response = await _submit(client, rider["headers"], body["cliq_charge"]["payment_id"])
    assert response.status_code == 200, response.text

    messages = await pushes_to("fcm-driver")
    assert len(messages) == 1, messages
    assert TRANSFER_REFERENCE in messages[0]["body"]
    assert messages[0]["data"]["type"] == "cliq_transfer_submitted"
    # أولويةٌ عادية: لا عدّاد عشرين ثانية هنا كبطاقة الطلب
    assert messages[0].get("high_priority") in (False, None)


# ------------------------------------------------------------------ التزامن


async def test_two_submissions_at_once_leave_one_reference_and_one_notice(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    """ضغطتان معاً على «أرسلت المرجع» — واحدةٌ تكتب والأخرى ترتدّ 409.

    هذا هو الثابت الذي يملكه قفلُ صف الدفعة وحده: بحذف `for_update` من
    `get_payment` تقرأ الطلبتان الحقلَ فارغاً معاً فتمرّان من فحص «كُتب
    سلفاً»، فتصير النتيجة `Counter({200: 2})` ويصل الكبتنَ إشعاران بمرجعين
    لحوالةٍ واحدة — وهي بالضبط الحالة التي لا يكشفها اختبارٌ متسلسل.

    والحكم على الثابت لا على التوقيت: مرجعٌ واحد في القاعدة، وإشعارٌ واحد.
    """
    await enable_push_provider(session_factory)
    rider, driver, _ride, body = await _open_cliq_payment(client, session_factory)
    payment_id = body["cliq_charge"]["payment_id"]
    await register_device(
        client, driver["headers"], device_id="driver-phone", token="fcm-driver"
    )

    # `wait_for` لأن الجمود يعلّق ولا يرفع: لا يكشفه إلا انقضاء مهلة
    responses = await asyncio.wait_for(
        asyncio.gather(
            _submit(client, rider["headers"], payment_id, "FT-FIRST-0001"),
            _submit(client, rider["headers"], payment_id, "FT-SECOND-002"),
        ),
        timeout=20,
    )

    assert Counter(response.status_code for response in responses) == Counter(
        {200: 1, 409: 1}
    )
    loser = next(r for r in responses if r.status_code == 409)
    assert loser.json()["code"] == "conflict"

    async with session_factory() as session:
        stored = await session.scalar(
            select(Payment.cliq_transfer_reference).where(
                Payment.id == uuid.UUID(payment_id)
            )
        )
    assert stored in {"FT-FIRST-0001", "FT-SECOND-002"}
    assert len(await pushes_to("fcm-driver")) == 1

    # ولا الدفتر تحرّك: المرجع قولٌ لا تحصيل (SPEC القسم 6)
    async with session_factory() as session:
        payment = await session.get(Payment, uuid.UUID(payment_id))
        assert payment.status.value == "pending"
        assert payment.transaction_id is None
        assert payment.amount == Decimal(EXPECTED_FARE)
