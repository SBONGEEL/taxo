"""حملةُ تأكيد الأرقام — أبوابُ اللوحة (قرارُ المالك 2026-08-31).

**أربعةُ أبوابٍ لا أكثر**: قراءةٌ، وإنشاءُ مسوّدة، وإطلاق، وإلغاء.

**ولا بابَ تجميدٍ ولا فكّ** — وذلك قرارٌ لا نقص: **التجمّدُ والاستئنافُ
آليّان بلا مشرف** (تسقط قناةُ السوق فتتجمّد، وتعود فتستأنف)، **وفكُّ إيقافِ
الحساب بتأكيد الرقم وحدَه**. **وزرٌّ يفكّ إيقافاً بلا تأكيدٍ يُفرِّغ الحملةَ
من معناها** — ومن ضغطه مرّةً سيضغطه لكلِّ من اشتكى.

**والإطلاقُ وحدَه فعلُ إنسان** — «ولا تُطلق حملةٌ على أحد» (قرارُ المالك):
تُنشأ مسوّدةً وتنتظر ضغطتَه.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import AdminUser, DbSession, StaffUser
from app.models.enums import AuditAction, CountryCode
from app.schemas.verification_campaign import (
    VerificationCampaignCreate,
    VerificationCampaignOut,
)
from app.services import audit, verification_campaign

router = APIRouter(prefix="/admin/verification-campaigns", tags=["admin"])


async def _out(session, campaign) -> VerificationCampaignOut:
    """**بانٍ واحدٌ لكلِّ الأبواب** — فلا يملأ بابٌ حقلاً وينساه آخر.

    وهو الشكلُ الثامن بعينه، وقد وقع في هذا المشروع مرّتين.
    """
    counts = await verification_campaign.progress(session, campaign.id)
    return VerificationCampaignOut(
        id=campaign.id,
        country_code=campaign.country_code,
        status=campaign.status,
        deadline_days=campaign.deadline_days,
        started_at=campaign.started_at,
        paused_at=campaign.paused_at,
        finished_at=campaign.finished_at,
        # **ما تشمله الآن** — يُقرأ **قبل** الضغط، فيعرف صاحبُ الإصبع على من
        # يطلق. **ورقمٌ يُكتشف بعد الإطلاق ليس قراراً.**
        scope_size=await verification_campaign.scope_size(
            session, campaign.country_code
        ),
        **counts,
    )


@router.get("", response_model=list[VerificationCampaignOut])
async def list_campaigns(
    _staff: StaffUser, session: DbSession
) -> list[VerificationCampaignOut]:
    return [
        await _out(session, row)
        for row in await verification_campaign.list_all(session)
    ]


@router.post("", response_model=VerificationCampaignOut, status_code=201)
async def create_campaign(
    payload: VerificationCampaignCreate, admin: AdminUser, session: DbSession
) -> VerificationCampaignOut:
    """**تُنشأ مسوّدةً ولا تُطلق** — ولا تُرسل رسالةً واحدةً قبل الضغطة."""
    campaign = await verification_campaign.create_draft(
        session, country=payload.country_code, deadline_days=payload.deadline_days
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="verification_campaign",
        entity_id=campaign.id,
        details={
            "country_code": campaign.country_code.value,
            "deadline_days": campaign.deadline_days,
        },
    )
    await session.commit()
    return await _out(session, campaign)


@router.post("/{campaign_id}/start", response_model=VerificationCampaignOut)
async def start_campaign(
    campaign_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> VerificationCampaignOut:
    """**الإطلاقُ ضغطةُ المالك** — ويُسجَّل باسمه وبعدد من شملهم يومَها."""
    size = await verification_campaign.scope_size(
        session, (await verification_campaign.get(session, campaign_id)).country_code
    )
    campaign = await verification_campaign.start(
        session, campaign_id=campaign_id, actor=admin
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="verification_campaign",
        entity_id=campaign.id,
        # **وعددُ من شملهم يومَ الإطلاق يُسجَّل** — فمن يقرأ بعد شهرٍ يعرف
        # على كم أُطلقت، **والنطاقُ يتغيّر فلا يُشتقّ لاحقاً**
        details={"action": "start", "scope_size": size},
    )
    await session.commit()
    return await _out(session, campaign)


@router.post("/{campaign_id}/cancel", response_model=VerificationCampaignOut)
async def cancel_campaign(
    campaign_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> VerificationCampaignOut:
    """**إلغاءٌ يفكّ ما أوقفته** — وإيقافٌ بلا حملةٍ تحكمه لا ينتهي أبداً."""
    campaign = await verification_campaign.cancel(session, campaign_id=campaign_id)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="verification_campaign",
        entity_id=campaign.id,
        details={"action": "cancel"},
    )
    await session.commit()
    return await _out(session, campaign)
