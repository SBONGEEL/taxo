"""السياساتُ والشروط في اللوحة — **البند ١٠ (§39٫١٠، §34، §45)**.

**و`settings.write`**: نصٌّ قانونيٌّ يُنشر باسم الشركة **إعدادُ منصّةٍ لا
إدارةُ أسطول** — وهو نفسُ سببِ وضع الإصدارات هناك.

**ولا بابَ تعديل** — بقرارٍ مكتوبٍ في §34: «كلُّ حفظٍ صفٌّ جديدٌ برقمٍ أعلى،
ولا يُحرَّر صفٌّ فوق نفسه». **فمن أراد تصحيحَ حرفٍ كتب نسخةً**، ويبقى ما وافق
عليه الناسُ كما وافقوا عليه.

**والنشرُ فعلٌ ثانٍ بعد الحفظ**: النسخةُ تولد مسوّدةً، **وحفظٌ ينشر يجعل كلَّ
تصحيحٍ إعلاناً** — وهو ما يجعل الكاتبَ يخاف القلم.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.models.enums import AuditAction, CountryCode, PolicyApp, PolicyDocType
from app.models.privacy import PrivacyPolicy, UserPolicyConsent
from app.schemas.policy import (
    OrgProfileIn,
    OrgProfileOut,
    PolicyVersionIn,
    PolicyVersionOut,
)
from app.services import audit, policies as policies_service

router = APIRouter(prefix="/admin/policies", tags=["admin"])


async def _consent_counts(
    session: AsyncSession, ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """عددُ الموافقات لكلِّ نسخة — **استعلامٌ واحدٌ لا نداءٌ لكلِّ صف**.

    وهي قاعدةُ `payment_summaries` نفسُها: صفحةٌ من عشرين نسخةً لا تصير عشرين
    استعلاماً.
    """
    if not ids:
        return {}
    rows = await session.execute(
        select(UserPolicyConsent.policy_id, func.count())
        .where(UserPolicyConsent.policy_id.in_(ids))
        .group_by(UserPolicyConsent.policy_id)
    )
    return {policy_id: count for policy_id, count in rows}


def _row(policy: PrivacyPolicy, consents: int) -> PolicyVersionOut:
    return PolicyVersionOut(
        id=policy.id,
        country_code=policy.country_code,
        doc_type=policy.doc_type,
        app=policy.app,
        version=policy.version,
        min_accepted_version=policy.min_accepted_version,
        body_ar=policy.body_ar,
        body_en=policy.body_en,
        requires_reconsent=policy.requires_reconsent,
        is_published=policy.is_published,
        published_at=policy.published_at,
        consents=consents,
        created_at=policy.created_at,
    )


@router.get("", response_model=list[PolicyVersionOut])
async def list_policies(
    _staff: StaffUser,
    session: DbSession,
    country_code: CountryCode | None = None,
    doc_type: PolicyDocType | None = None,
    app: PolicyApp | None = None,
) -> list[PolicyVersionOut]:
    """كلُّ النسخ — **ومعها عددُ من وافق على كلٍّ**."""
    rows = await policies_service.versions(
        session, country=country_code, doc_type=doc_type, app=app
    )
    counts = await _consent_counts(session, [row.id for row in rows])
    return [_row(row, counts.get(row.id, 0)) for row in rows]


@router.post("", response_model=PolicyVersionOut, status_code=status.HTTP_201_CREATED)
async def create_policy_version(
    payload: PolicyVersionIn, admin: SettingsWriter, session: DbSession
) -> PolicyVersionOut:
    """يكتب نسخةً جديدةً **مسوّدة** — ولا ينشرها."""
    policy = await policies_service.create_version(
        session,
        country=payload.country_code,
        doc_type=payload.doc_type,
        app=payload.app,
        body_ar=payload.body_ar,
        body_en=payload.body_en,
        requires_reconsent=payload.requires_reconsent,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.CREATE,
        entity_type="privacy_policy",
        entity_id=policy.id,
        details={
            "country_code": policy.country_code.value,
            "doc_type": policy.doc_type.value,
            "app": policy.app.value,
            "version": policy.version,
            "requires_reconsent": policy.requires_reconsent,
            "min_accepted_version": policy.min_accepted_version,
        },
    )
    await session.commit()
    await session.refresh(policy)
    return _row(policy, 0)


@router.post("/{policy_id}/publish", response_model=PolicyVersionOut)
async def publish_policy(
    policy_id: uuid.UUID, admin: SettingsWriter, session: DbSession
) -> PolicyVersionOut:
    """ينشرها — **وينزع سابقَها، ويُسمّى المنزوعُ في التدقيق**.

    **«نُشرت الرابعة» وحدَها لا تقول أنّ الثالثة أُطفئت** — ومن يقرأ بعد شهرٍ
    «أيُّ نصٍّ كان قائماً في ذلك اليوم» يحتاج الاثنين.
    """
    policy = await policies_service.get(session, policy_id)
    previous = await policies_service.publish(session, policy, actor=admin)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.ACTIVATE,
        entity_type="privacy_policy",
        entity_id=policy.id,
        details={
            "country_code": policy.country_code.value,
            "doc_type": policy.doc_type.value,
            "app": policy.app.value,
            "version": policy.version,
            "min_accepted_version": policy.min_accepted_version,
            "replaced_version": None if previous is None else previous.version,
        },
    )
    await session.commit()
    await session.refresh(policy)
    counts = await _consent_counts(session, [policy.id])
    return _row(policy, counts.get(policy.id, 0))


@router.post("/{policy_id}/withdraw", response_model=PolicyVersionOut)
async def withdraw_policy(
    policy_id: uuid.UUID, admin: SettingsWriter, session: DbSession
) -> PolicyVersionOut:
    """يسحب النشرَ فيعود السوقُ بلا وثيقةٍ قائمة — **ولا يمحو شيئاً**.

    **وبابُ الرجوع شرطٌ لا ترف**: حالٌ تُدخَل ولا يُخرج منها «بابٌ بلا زرّ في
    اتجاهٍ واحد» — ومن نشر نصّاً في سوقٍ لم يُفتح بعد كان لا يملك إلا أن ينشر
    فوقه غيرَه.
    """
    policy = await policies_service.get(session, policy_id)
    await policies_service.withdraw(session, policy)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DEACTIVATE,
        entity_type="privacy_policy",
        entity_id=policy.id,
        details={
            "country_code": policy.country_code.value,
            "doc_type": policy.doc_type.value,
            "app": policy.app.value,
            "version": policy.version,
        },
    )
    await session.commit()
    await session.refresh(policy)
    counts = await _consent_counts(session, [policy.id])
    return _row(policy, counts.get(policy.id, 0))


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy_draft(
    policy_id: uuid.UUID, admin: SettingsWriter, session: DbSession
) -> None:
    """يحذف **مسوّدةً لم يوافق عليها أحد** — وما عداها يُرفض بالعربية."""
    policy = await policies_service.get(session, policy_id)
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.DELETE,
        entity_type="privacy_policy",
        entity_id=policy.id,
        details={
            "country_code": policy.country_code.value,
            "doc_type": policy.doc_type.value,
            "app": policy.app.value,
            "version": policy.version,
        },
    )
    await policies_service.delete_draft(session, policy)
    await session.commit()


@router.get("/org", response_model=OrgProfileOut)
async def read_org(_staff: StaffUser, session: DbSession) -> OrgProfileOut:
    """بيانُ الجهة — **وفراغُه حالٌ صحيحةٌ لا خطأ**."""
    row = await policies_service.org(session)
    if row is None:
        return OrgProfileOut(legal_name=None, address=None, privacy_email=None)
    return OrgProfileOut.model_validate(row)


@router.put("/org", response_model=OrgProfileOut)
async def write_org(
    payload: OrgProfileIn, admin: SettingsWriter, session: DbSession
) -> OrgProfileOut:
    """يكتب بيانَ الجهة — **وهذا يُحرَّر فوق نفسه بحقّ**: ليس نصّاً وافق عليه أحد."""
    row, changes = await policies_service.save_org(
        session,
        legal_name=payload.legal_name,
        address=payload.address,
        privacy_email=payload.privacy_email,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="org_profile",
        entity_id=row.id,
        changes=changes,
    )
    await session.commit()
    await session.refresh(row)
    return OrgProfileOut.model_validate(row)
