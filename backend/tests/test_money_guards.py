"""حارسا المال — يُقاسان في الاتجاهين، ويُقاس أن الجاريَ لا يتأثّر.

**والاتجاهُ الثاني هو المهمّ هنا**: حارسٌ يمنع الأذى وحدَه سهل، والصعبُ أن
يمنع الأذى **ولا يمنع ما بُني ليبقى عاملاً** — فالتجميدُ يوقف الكتابةَ ولا
يوقف تسعيرَ رحلة، والإيقافُ يمنع مغادرةَ المال ولا يمنع طلباً ولا اعتماداً.

**وثلاثةٌ من الثمانية لا تسقط بحذف الحارس — مقيسٌ لا مُقدَّر** (2026-08-24،
بتعطيل الدالّتين في `money_guards` وتشغيل الملفّ: **٥ تسقط و٣ تبقى**):

| يبقى أخضرَ بحذف الحارس | وما يملكه فعلاً |
|---|---|
| `test_the_absent_row_reads_as_working` | افتراضُ الغياب في `default_for` |
| `test_switching_a_money_guard_off_needs_a_written_reason` | العضويةُ في `GUARDED_FLAGS` |
| `test_a_ride_is_still_priced_while_pricing_is_frozen` | **ضيقُ** الحارس لا وجودُه |

**وتبقى الثلاثةُ ولا تُحذف** — كلٌّ منها يملك ثابتاً حقيقياً يسقط بحذف
**ذلك** الثابت. **وإنما تُسمّى** لئلّا يقرأها لاحقٌ حرّاساً للمفتاحين
فيظنَّ التغطيةَ ثمانيةً وهي خمسة. **وحارسٌ يوحي بتغطيةٍ لا يملكها أسوأُ من
غيابه** — وهي قاعدةُ `test_locks_have_tests` نفسُها مطبَّقةً على هذا الملفّ.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit import AdminAuditLog
from app.models.enums import CountryCode, FeatureKey, WithdrawalStatus
from app.models.wallet import WithdrawalRequest
from app.services import settings_service
from tests.helpers import rider_session
from tests.test_wallet_admin import _funded_driver, _request_withdrawal


async def _set(session_factory, key: FeatureKey, enabled: bool) -> None:
    async with session_factory() as session:
        await settings_service.set_flag(
            session, country_code=CountryCode.JO, feature_key=key, enabled=enabled
        )
        await session.commit()


# ───────────────────────── تجميدُ التسعير ─────────────────────────


async def test_the_absent_row_reads_as_working(session_factory) -> None:
    """**الغيابُ يعمل** — وإلا أوقف أوّلُ تنصيبٍ غيرِ مبذورٍ التسعيرَ كلَّه.

    > **ولا يسقط بحذف الحارس** (مقيسٌ 2026-08-24): يبقى أخضرَ وكلتا الدالّتين
    > في `money_guards` تعودان فوراً. **فلا يُقرأ حارساً لهما.**
    >
    > **وما يملكه**: `settings_service.default_for` وحدَه — أنّ مفتاحَي المال
    > في `DEFAULT_ENABLED_FLAGS`، فصفٌّ غائبٌ يُقرأ **مشتعلاً**. ويسقط بقلب
    > ذلك الافتراض، لا بحذف الحارس.
    """
    for key in (
        FeatureKey.PRICING_WRITES_ENABLED,
        FeatureKey.WITHDRAWAL_PAYOUT_ENABLED,
    ):
        assert settings_service.default_for(key) is True
        async with session_factory() as session:
            assert await settings_service.is_feature_enabled(
                session, CountryCode.JO, key
            )


async def test_switching_a_money_guard_off_needs_a_written_reason() -> None:
    """كلاهما في `GUARDED_FLAGS` — والإطفاءُ بلا سببٍ لا يُقبل.

    > **ولا يسقط بحذف الحارس** (مقيسٌ 2026-08-24). **فلا يُقرأ حارساً له.**
    >
    > **وما يملكه**: **العضويةُ في `GUARDED_FLAGS`** لا غير — ويسقط بحذف
    > أحد الاسمين منها. **ولا يمسّ مسارَ الرفض إطلاقاً**: لا يُنادي راوتراً
    > ولا يمرّ بدالّةٍ من `money_guards`، وإنما يقرأ مجموعةً ويقارن.
    >
    > **وهو قراءةُ مجموعةٍ لا قياسُ سلوك**: أنّ الإطفاءَ بلا سببٍ **يُرفض
    > فعلاً** يملكه `test_phone_verification.py::`
    > `test_disabling_the_flag_needs_a_written_reason` — **وعلى
    > `otp_verification_enabled` وحدَه**. فالرفضُ لمفتاحَي المال **غيرُ
    > مقيسٍ سلوكاً**، وإنما يُستدلّ عليه بأن الشرطَ في الراوتر على المجموعة
    > لا على مفتاحٍ بعينه. **وهذا استدلالٌ لا قياس، ويُقال كذلك.**
    """
    guarded = settings_service.GUARDED_FLAGS
    assert FeatureKey.PRICING_WRITES_ENABLED.value in guarded
    assert FeatureKey.WITHDRAWAL_PAYOUT_ENABLED.value in guarded


async def test_frozen_pricing_refuses_the_three_writes(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    body = {
        "country_code": "JO",
        "vehicle_category": "comfort",
        "base_fare": "1.500",
        "price_per_km": "0.600",
        "price_per_min": "0.120",
        "minimum_fare": "2.500",
        "cancellation_fee": "0.800",
    }
    # مشتعلٌ ⇒ يمرّ بلا اختراع
    created = await client.post("/admin/settings/pricing", json=body, headers=admin_headers)
    assert created.status_code == 201, created.text
    rule_id = created.json()["id"]

    await _set(session_factory, FeatureKey.PRICING_WRITES_ENABLED, False)

    # مطفأٌ ⇒ الأبوابُ الثلاثةُ مغلقةٌ **وبالعلّة مسمّاة**
    again = await client.post(
        "/admin/settings/pricing", json={**body, "vehicle_category": "economy"},
        headers=admin_headers,
    )
    patched = await client.patch(
        f"/admin/settings/pricing/{rule_id}",
        json={"base_fare": "9.000"}, headers=admin_headers,
    )
    removed = await client.delete(
        f"/admin/settings/pricing/{rule_id}", headers=admin_headers
    )
    for response in (again, patched, removed):
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "pricing_writes_disabled"

    # **ولا يُكتب شيء**: الصفُّ كما هو
    unchanged = await client.get("/admin/settings/pricing", headers=admin_headers)
    row = next(r for r in unchanged.json() if r["id"] == rule_id)
    assert Decimal(row["base_fare"]) == Decimal("1.500")


async def test_a_refused_write_leaves_its_own_audit_entry(
    client: AsyncClient, admin_headers: dict, session_factory
) -> None:
    """«من حاول التسعيرَ وهو مجمَّد» سؤالٌ يُسأل — ورفضٌ صامتٌ يُخفي جوابَه."""
    await _set(session_factory, FeatureKey.PRICING_WRITES_ENABLED, False)
    await client.post(
        "/admin/settings/pricing",
        json={
            "country_code": "JO", "vehicle_category": "comfort",
            "base_fare": "1.000", "price_per_km": "0.500", "price_per_min": "0.100",
            "minimum_fare": "2.000", "cancellation_fee": "0.750",
        },
        headers=admin_headers,
    )
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_type == "pricing_rule"
                )
            )
        ).all()
    refusals = [r for r in rows if (r.details or {}).get("refused_by_flag")]
    assert len(refusals) == 1
    assert refusals[0].details["refused_by_flag"] == "pricing_writes_enabled"
    # **وباسم من ضغطه** — قيدٌ بلا فاعلٍ لا يجيب السؤال
    assert refusals[0].actor_id is not None


async def test_a_ride_is_still_priced_while_pricing_is_frozen(
    client: AsyncClient, session_factory, jordan_settings
) -> None:
    """**أهمُّ اتجاهٍ في الملفّ**: التجميدُ يوقف الكتابةَ لا التسعير.

    والصفوفُ تُبذر **قبل** التجميد — فالمقيسُ أن رحلةً تُسعَّر بصفٍّ قائمٍ
    والكتابةُ مغلقة، لا أن التسعيرَ يعمل بلا صفوف.

    > **ولا يسقط بحذف الحارس** (مقيسٌ 2026-08-24) — **وهذا لازمٌ عن معناه لا
    > نقصٌ فيه**: هو يقيس أن الحارسَ **لا يتعدّى**، وحارسٌ محذوفٌ لا يتعدّى
    > بالتأكيد. **فلا يُقرأ حارساً للتجميد.**
    >
    > **وما يملكه**: **ضيقُ الحارس** — أنّ `require_pricing_writes` عند
    > كتابةِ `pricing` وحدَها ولم تتسرّب إلى `POST /rides/estimate`. ويسقط
    > يومَ يُنادى من مسار التسعير، **وذلك هو العطبُ الذي وُجد له**.
    >
    > **ولا يستطيع التمييزَ بين «الحارسُ ضيّق» و«لا حارسَ أصلاً»** — والذي
    > يميّزهما هو `test_frozen_pricing_refuses_the_three_writes`، وهو يسقط
    > بحذف الحارس. **فالاثنان نصفا قياسٍ واحد، ولا يُقرأ أحدُهما وحدَه.**
    """
    await _set(session_factory, FeatureKey.PRICING_WRITES_ENABLED, False)
    rider = await rider_session(client)
    estimate = await client.post(
        "/rides/estimate",
        json={
            "pickup": {"lat": 31.95, "lng": 35.91},
            "dropoff": {"lat": 31.97, "lng": 35.93},
            "vehicle_category": "economy",
        },
        headers=rider["headers"],
    )
    assert estimate.status_code == 200, estimate.text
    assert Decimal(estimate.json()["estimated_fare"]) > 0


# ───────────────────────── إيقافُ الصرف ─────────────────────────


async def test_stopping_payout_blocks_the_money_and_not_the_queue(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """**الاتجاهان في اختبارٍ واحد**: المالُ لا يغادر، والطابورُ يعمل كما كان.

    ومنعُ الطلب هو ما لا يُقبل: يُقرأ في تطبيق الكبتن «محفظتي معطوبة»، فيصنع
    موجةَ شكاوى عن عطبٍ لا وجودَ له.
    """
    driver = await _funded_driver(client, session_factory, admin_headers)
    await _set(session_factory, FeatureKey.WITHDRAWAL_PAYOUT_ENABLED, False)

    # **الطلبُ يُقبل** — والرصيدُ محجوزٌ به كما كان
    created = await _request_withdrawal(client, driver, "40.000")
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]

    # **والاعتمادُ يمرّ** — الحارسُ على الصرف لا على الحكم
    approved = await client.post(
        f"/admin/withdrawals/{request_id}/approve", headers=admin_headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    # **والمغادرةُ وحدَها ممنوعة**
    paid = await client.post(
        f"/admin/withdrawals/{request_id}/paid",
        json={"reference": "CLQ-TRX-99"},
        headers=admin_headers,
    )
    assert paid.status_code == 403, paid.text
    assert paid.json()["code"] == "withdrawal_payout_disabled"

    # **ولا قيدَ في الدفتر، ولا حالةَ وسطى**: يبقى `approved` لا حالاً جديدة
    balance = (
        await client.get("/wallet/me", headers=driver["headers"])
    ).json()["balance"]
    assert balance == "100.000"
    # **يُقرأ من القاعدة لا من باب**: المقيسُ حالُ الصفّ نفسِه
    async with session_factory() as session:
        status = await session.scalar(
            select(WithdrawalRequest.status).where(
                WithdrawalRequest.id == uuid.UUID(request_id)
            )
        )
    assert status is WithdrawalStatus.APPROVED


async def test_payout_passes_again_when_the_switch_is_raised(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    """مشتعلٌ ⇒ يمرّ بلا اختراع — وهو نصفُ القياس الذي لا يُترك."""
    driver = await _funded_driver(client, session_factory, admin_headers)
    request_id = (await _request_withdrawal(client, driver, "40.000")).json()["id"]
    await client.post(
        f"/admin/withdrawals/{request_id}/approve", headers=admin_headers
    )

    await _set(session_factory, FeatureKey.WITHDRAWAL_PAYOUT_ENABLED, False)
    blocked = await client.post(
        f"/admin/withdrawals/{request_id}/paid",
        json={"reference": "CLQ-1"}, headers=admin_headers,
    )
    assert blocked.status_code == 403

    await _set(session_factory, FeatureKey.WITHDRAWAL_PAYOUT_ENABLED, True)
    paid = await client.post(
        f"/admin/withdrawals/{request_id}/paid",
        json={"reference": "CLQ-1"}, headers=admin_headers,
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert (
        await client.get("/wallet/me", headers=driver["headers"])
    ).json()["balance"] == "60.000"


async def test_a_refused_payout_leaves_its_own_audit_entry(
    client: AsyncClient, admin_headers: dict, jordan_wallet: None, session_factory
) -> None:
    driver = await _funded_driver(client, session_factory, admin_headers)
    request_id = (await _request_withdrawal(client, driver, "40.000")).json()["id"]
    await client.post(
        f"/admin/withdrawals/{request_id}/approve", headers=admin_headers
    )
    await _set(session_factory, FeatureKey.WITHDRAWAL_PAYOUT_ENABLED, False)
    await client.post(
        f"/admin/withdrawals/{request_id}/paid",
        json={"reference": "CLQ-2"}, headers=admin_headers,
    )
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AdminAuditLog).where(
                    AdminAuditLog.entity_type == "withdrawal_request"
                )
            )
        ).all()
    refusals = [r for r in rows if (r.details or {}).get("refused_by_flag")]
    assert len(refusals) == 1
    assert refusals[0].details["refused_by_flag"] == "withdrawal_payout_enabled"
    assert refusals[0].actor_id is not None
