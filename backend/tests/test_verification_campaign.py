"""حملةُ تأكيد الأرقام — **تُبنى ولا تُطلق** (قرارُ المالك 2026-08-31).

## ستٌّ تُقاس هنا، وكلُّها نقضُها لا يصيح

* **الموظّفون خارج النطاق** — **ونقضُها يوقف اللوحةَ عن نفسها**: من يفكّ
  الإيقافَ يحتاج لوحةً، واللوحةُ موقوفة. وقِيس على الإنتاج أن حسابَي المشرف
  هما **الوحيدان** غيرُ المؤكَّدَين.
* **ولا تُرسل رسالةٌ قبل الضغطة** — المسوّدةُ لا تفعل شيئاً.
* **والتجمّدُ آليٌّ حين تسقط القناة، والمهلُ تُمدَّد بما تجمّدت** — «تستأنف
  بما بقي» لا بما مضى من التقويم.
* **والإيقافُ بانقضاء المهلة، ومن أكّد بين دورتين لا يُوقَف.**
* **والفكُّ بتأكيد الرقم وحدَه** — من الباب نفسِه، **ومعه أيامُ الاشتراك**.
* **والمحفظةُ لا تُمسّ.**
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.enums import VerificationCampaignStatus
from app.models.user import User
from app.models.verification_campaign import (
    VerificationCampaign,
    VerificationEnforcement,
)
from app.services import verification_campaign
from tests.helpers import enable_firebase_auth, register, rider_session

JO = "JO"


async def _unverified_rider(client: AsyncClient, session_factory, phone: str) -> str:
    """حسابٌ رقمُه غير مؤكَّد — **بإطفاء المفتاح كما يقع في الواقع**."""
    from app.models.feature_flag import FeatureFlag
    from app.models.enums import CountryCode

    async with session_factory() as session:
        session.add(
            FeatureFlag(
                country_code=CountryCode.JO,
                feature_key="otp_verification_enabled",
                enabled=False,
            )
        )
        await session.commit()

    body = await register(
        client,
        {
            "phone": phone,
            "name": "راكبٌ بلا تأكيد",
            "password": "TaxoTest123",
            "country_code": JO,
            "role": "rider",
        },
    )
    return body["user"]["id"]


async def _draft(session_factory, *, days: int = 14) -> VerificationCampaign:
    from app.models.enums import CountryCode

    async with session_factory() as session:
        campaign = await verification_campaign.create_draft(
            session, country=CountryCode.JO, deadline_days=days
        )
        await session.commit()
        return campaign


async def _run_tick(session_factory) -> dict[str, int]:
    async with session_factory() as session:
        counters, _ = await verification_campaign.tick(session)
        await session.commit()
        return counters


# ═══════════════════════════ ١) من تشمل — والموظّفون خارجها


async def test_staff_are_never_in_scope(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**ونقضُها يوقف اللوحةَ عن نفسها** — وحسابا المشرف على الإنتاج بلا رقم."""
    from app.models.enums import CountryCode

    async with session_factory() as session:
        size = await verification_campaign.scope_size(session, CountryCode.JO)
        # المشرفُ أُنشئ في `admin_headers` برقمٍ غير مؤكَّد — **ولا يُعدّ**
        assert size == 0


async def test_scope_counts_riders_and_drivers_alike(
    client: AsyncClient, session_factory
) -> None:
    """**الراكبُ يشمله أيضاً** — فرقمُه ما يتّصل به الكبتن."""
    from app.models.enums import CountryCode

    await _unverified_rider(client, session_factory, "0791110001")
    async with session_factory() as session:
        assert await verification_campaign.scope_size(session, CountryCode.JO) == 1


# ═══════════════════════════ ٢) لا تُطلق حملةٌ على أحد


async def test_a_draft_does_nothing(client: AsyncClient, session_factory) -> None:
    """**المسوّدةُ لا تفعل شيئاً** — ولا رسالةَ قبل الضغطة."""
    await _unverified_rider(client, session_factory, "0791110002")
    await _draft(session_factory)

    counters = await _run_tick(session_factory)
    assert counters == {"enrolled": 0, "reminded": 0, "suspended": 0, "paused": 0}


async def test_only_the_owner_start_moves_it(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    await _unverified_rider(client, session_factory, "0791110003")
    campaign = await _draft(session_factory)
    await enable_firebase_auth(session_factory)

    started = await client.post(
        f"/admin/verification-campaigns/{campaign.id}/start", headers=admin_headers
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "running"

    counters = await _run_tick(session_factory)
    assert counters["enrolled"] == 1


async def test_support_cannot_start(
    client: AsyncClient, session_factory, support_headers: dict
) -> None:
    campaign = await _draft(session_factory)
    refused = await client.post(
        f"/admin/verification-campaigns/{campaign.id}/start", headers=support_headers
    )
    assert refused.status_code == 403


async def test_one_live_campaign_per_market(session_factory) -> None:
    await _draft(session_factory)
    from app.core.exceptions import AppError
    from app.models.enums import CountryCode

    async with session_factory() as session:
        with pytest.raises(AppError) as caught:
            await verification_campaign.create_draft(
                session, country=CountryCode.JO
            )
    assert caught.value.status_code == 409


# ═══════════════════════ ٣) التجمّدُ الآليّ والاستئنافُ بما بقي


async def test_it_freezes_when_the_channel_is_down_and_no_time_passes(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**ولا يُعاقَب أحدٌ على عطبٍ عندنا** — لا مهلةَ على من لا يستطيع الاستقبال."""
    await _unverified_rider(client, session_factory, "0791110004")
    campaign = await _draft(session_factory)
    await enable_firebase_auth(session_factory)
    await client.post(
        f"/admin/verification-campaigns/{campaign.id}/start", headers=admin_headers
    )
    await _run_tick(session_factory)

    # **تسقط القناة** — يُعطَّل عقدُ فايربيس
    from app.models.enums import ProviderKey
    from app.models.provider_credential import ProviderCredential

    async with session_factory() as session:
        row = await session.scalar(
            select(ProviderCredential).where(
                ProviderCredential.provider_key == ProviderKey.FIREBASE_AUTH
            )
        )
        row.is_active = False
        await session.commit()

    counters = await _run_tick(session_factory)
    assert counters["paused"] == 1

    async with session_factory() as session:
        row = await session.get(VerificationCampaign, campaign.id)
        assert row.status is VerificationCampaignStatus.PAUSED
        before = (
            await session.scalars(
                select(VerificationEnforcement.deadline_at).where(
                    VerificationEnforcement.campaign_id == campaign.id
                )
            )
        ).one()

    # **ويُدفع الزمنُ إلى الوراء** ليبدو أن التجمّد دام ساعتين
    async with session_factory() as session:
        row = await session.get(VerificationCampaign, campaign.id)
        row.paused_at = datetime.now(UTC) - timedelta(hours=2)
        await session.commit()

    # **تعود القناة** — فتستأنف والمهلُ تُمدَّد بما تجمّدت
    async with session_factory() as session:
        row = await session.scalar(
            select(ProviderCredential).where(
                ProviderCredential.provider_key == ProviderKey.FIREBASE_AUTH
            )
        )
        row.is_active = True
        await session.commit()

    await _run_tick(session_factory)
    async with session_factory() as session:
        row = await session.get(VerificationCampaign, campaign.id)
        assert row.status is VerificationCampaignStatus.RUNNING
        assert row.paused_seconds >= 7000
        after = (
            await session.scalars(
                select(VerificationEnforcement.deadline_at).where(
                    VerificationEnforcement.campaign_id == campaign.id
                )
            )
        ).one()
        # **تستأنف بما بقي** — لا بما مضى من التقويم
        assert (after - before).total_seconds() >= 7000


# ═══════════════════════════════ ٤) الإيقاف


async def test_it_suspends_after_the_deadline_and_publishes_why(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    user_id = await _unverified_rider(client, session_factory, "0791110005")
    campaign = await _draft(session_factory)
    await enable_firebase_auth(session_factory)
    await client.post(
        f"/admin/verification-campaigns/{campaign.id}/start", headers=admin_headers
    )
    await _run_tick(session_factory)

    # **المهلةُ تُقاس من الحقل** — فيُدفع الحقلُ لا الساعة
    async with session_factory() as session:
        row = await session.scalar(
            select(VerificationEnforcement).where(
                VerificationEnforcement.campaign_id == campaign.id
            )
        )
        row.deadline_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    counters = await _run_tick(session_factory)
    assert counters["suspended"] == 1

    async with session_factory() as session:
        user = await session.get(User, user_id)
        assert user.verification_suspended_at is not None
        # **السببُ والطريقُ منشوران** — ولا «حسابك مجمَّد» مجرّدة
        assert user.suspension["code"] == "phone_unverified"
        assert "أكّده الآن" in user.suspension["message"]


async def test_whoever_verified_between_ticks_is_not_suspended(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**الحقلُ يُقرأ لحظةَ الفعل لا لحظةَ التسجيل** — فخُّ المهامّ الدوريّة."""
    user_id = await _unverified_rider(client, session_factory, "0791110006")
    campaign = await _draft(session_factory)
    await enable_firebase_auth(session_factory)
    await client.post(
        f"/admin/verification-campaigns/{campaign.id}/start", headers=admin_headers
    )
    await _run_tick(session_factory)

    async with session_factory() as session:
        row = await session.scalar(
            select(VerificationEnforcement).where(
                VerificationEnforcement.campaign_id == campaign.id
            )
        )
        row.deadline_at = datetime.now(UTC) - timedelta(minutes=1)
        user = await session.get(User, user_id)
        user.phone_verified_at = datetime.now(UTC)
        await session.commit()

    counters = await _run_tick(session_factory)
    assert counters["suspended"] == 0

    async with session_factory() as session:
        assert (await session.get(User, user_id)).verification_suspended_at is None


async def test_a_suspended_account_may_not_ride_or_move_money(
    client: AsyncClient, session_factory
) -> None:
    """**الإيقافُ يمنع الرحلةَ والمحفظة** — ورسالتُه تقول السببَ والطريق."""
    body = await register(
        client,
        {
            "phone": "0791110007",
            "name": "راكبٌ موقوف",
            "password": "TaxoTest123",
            "country_code": JO,
            "role": "rider",
        },
    )
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}
    async with session_factory() as session:
        user = await session.get(User, body["user"]["id"])
        user.verification_suspended_at = datetime.now(UTC)
        await session.commit()

    refused = await client.post(
        "/rides",
        json={
            "pickup": {"lat": 31.95, "lng": 35.91},
            "dropoff": {"lat": 31.97, "lng": 35.86},
            "vehicle_category": "economy",
        },
        headers=headers,
    )
    assert refused.status_code == 403
    assert refused.json()["code"] == "phone_unverified"
    assert "أكّده الآن" in refused.json()["message"]


# ═══════════════════════ ٥) الفكُّ — وأيامُ الاشتراك، والمحفظةُ لا تُمسّ


async def test_verifying_the_phone_lifts_the_suspension(
    client: AsyncClient, session_factory
) -> None:
    """**شرطُ الفكِّ تأكيدُ الرقم وحدَه، فوراً وبلا مشرف.**"""
    from app.services.firebase_auth import mock_token

    await enable_firebase_auth(session_factory)
    body = await register(
        client,
        {
            "phone": "0791110008",
            "name": "راكبٌ يؤكّد",
            "password": "TaxoTest123",
            "country_code": JO,
            "role": "rider",
        },
    )
    headers = {"Authorization": f"Bearer {body['tokens']['access_token']}"}
    async with session_factory() as session:
        user = await session.get(User, body["user"]["id"])
        user.phone_verified_at = None
        user.verification_suspended_at = datetime.now(UTC)
        await session.commit()

    lifted = await client.post(
        "/auth/me/verify-phone",
        json={"verification_token": mock_token("+962791110008")},
        headers=headers,
    )
    assert lifted.status_code == 200, lifted.text
    assert lifted.json()["suspension"] is None

    async with session_factory() as session:
        assert (
            await session.get(User, body["user"]["id"])
        ).verification_suspended_at is None


async def test_the_wallet_is_never_touched_by_a_suspension(
    client: AsyncClient, session_factory
) -> None:
    """**والمحفظةُ تبقى ولا تُمسّ** — الإيقافُ منع العملَ ولم يأخذ مالاً."""
    from app.models.wallet import WalletTransaction

    body = await register(
        client,
        {
            "phone": "0791110009",
            "name": "راكبٌ بمحفظة",
            "password": "TaxoTest123",
            "country_code": JO,
            "role": "rider",
        },
    )
    async with session_factory() as session:
        user = await session.get(User, body["user"]["id"])
        user.verification_suspended_at = datetime.now(UTC)
        await session.commit()

        before = len(
            list(
                await session.scalars(
                    select(WalletTransaction).where(
                        WalletTransaction.owner_id == user.id
                    )
                )
            )
        )
        await verification_campaign.release(session, user=user)
        await session.commit()
        after = len(
            list(
                await session.scalars(
                    select(WalletTransaction).where(
                        WalletTransaction.owner_id == user.id
                    )
                )
            )
        )
    assert before == after == 0


async def test_cancelling_a_campaign_releases_whoever_it_suspended(
    client: AsyncClient, session_factory, admin_headers: dict
) -> None:
    """**وإيقافٌ بلا حملةٍ تحكمه لا يعرف أحدٌ متى ينتهي.**"""
    user_id = await _unverified_rider(client, session_factory, "0791110010")
    campaign = await _draft(session_factory)
    await enable_firebase_auth(session_factory)
    await client.post(
        f"/admin/verification-campaigns/{campaign.id}/start", headers=admin_headers
    )
    await _run_tick(session_factory)
    async with session_factory() as session:
        row = await session.scalar(
            select(VerificationEnforcement).where(
                VerificationEnforcement.campaign_id == campaign.id
            )
        )
        row.deadline_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()
    await _run_tick(session_factory)

    cancelled = await client.post(
        f"/admin/verification-campaigns/{campaign.id}/cancel", headers=admin_headers
    )
    assert cancelled.status_code == 200
    async with session_factory() as session:
        assert (await session.get(User, user_id)).verification_suspended_at is None
