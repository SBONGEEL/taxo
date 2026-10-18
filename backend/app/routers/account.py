"""بابُ الحساب — **حذفُه حذفاً حقيقياً بعد مهلة، لصاحبه أيّاً كان دورُه** (SPEC §59).

## ولمَ حلّ محلَّ `‎/account/deactivation` ولم يُضَف بجانبه (٢٠٢٦-٠٩-٢٩)

**قرارُ المالك: حذفٌ بعد مهلة لا إغلاقٌ يُراجَع** — وApple ترفض التعليقَ
بديلاً عن الحذف. **وبابان يُغلقان الحسابَ الشكلُ الثامنُ بعينه**: كلٌّ صادقٌ
منفرداً ويفترقان أوّلَ تعديل. فالقديمُ أُزيل من هنا، **وطلباتُه القائمةُ قبل
اليوم تبقى في اللوحة** (`/admin/deactivations`) حتى يُبتّ فيها.

**والحالُ في الخدمة لا هنا** (`services/account_deletion.py`) — وهنا ثلاثةُ
أبواب: السؤال، والطلب، والاستعادة.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, RedisDep
from app.models.enums import PolicyApp
from app.models.privacy import UserPolicyConsent
from app.schemas.account import DeletionRequestIn, DeletionStateOut
from app.schemas.policy import AcceptPoliciesIn, PendingPoliciesOut, PendingPolicyOut
from app.services import account_deletion, token_service
from app.services import policies as policies_service

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/deletion", response_model=DeletionStateOut)
async def my_deletion_state(user: CurrentUser, session: DbSession) -> DeletionStateOut:
    """حالُ طلبه وموانعُه ورصيداه — **سؤالٌ واحدٌ بجوابٍ واحد**."""
    return DeletionStateOut(**await account_deletion.state(session, user))


@router.post(
    "/deletion", response_model=DeletionStateOut, status_code=status.HTTP_201_CREATED
)
async def request_deletion(
    payload: DeletionRequestIn,
    user: CurrentUser,
    session: DbSession,
    redis: RedisDep,
) -> DeletionStateOut:
    """يجدول الحذفَ بعد ٣٠ يوماً — **ويُلغي كلَّ جلساته بعد الالتزام**.

    **والإلغاءُ بعد الالتزام لا قبله**: جلساتٌ تُلغى ثم تسقط المعاملةُ تُخرج
    صاحبَها من حسابٍ لم يُجدوَل حذفُه.
    """
    locked = await account_deletion.request(
        session, redis, user=user, forfeit_amount=payload.forfeit_amount
    )
    await session.commit()
    await token_service.revoke_all_for_user(
        session, redis, user.id, reason=token_service.REVOKE_DELETION
    )
    await session.commit()
    await token_service.kick(redis, user.id)
    return DeletionStateOut(**await account_deletion.state(session, locked))


@router.delete("/deletion", response_model=DeletionStateOut)
async def restore_account(user: CurrentUser, session: DbSession) -> DeletionStateOut:
    """**التراجعُ في المهلة** — فعلٌ صريحٌ بعد الدخول، لا أثرٌ جانبيٌّ له."""
    locked = await account_deletion.restore(session, user=user)
    await session.commit()
    return DeletionStateOut(**await account_deletion.state(session, locked))


# ═══════════════ إعادةُ القبول (§٧٦-ع/٧ البند ٣) ═══════════════
#
# **بابان لصاحب الحساب**: ما ينتظر قبولَه، و«أوافق». **والحكمُ كلُّه في `services/policies.py`** — أيُّ نسخةٍ تُبرئ، وما تغيّر،
# وأيُّ معرّفٍ يُقبل — **والتطبيقان يعرضان**.


async def _pending_out(session, user, items: list[policies_service.Pending]) -> PendingPoliciesOut:
    out = []
    for item in items:
        doc, old = item.policy, item.accepted
        accepted_at = None
        if old is not None:
            accepted_at = await session.scalar(
                select(UserPolicyConsent.accepted_at).where(
                    UserPolicyConsent.user_id == user.id, UserPolicyConsent.policy_id == old.id
                )
            )
        out.append(
            PendingPolicyOut(
                id=doc.id,
                doc_type=doc.doc_type.value,
                version=doc.version,
                published_at=doc.published_at,
                accepted_version=old.version if old is not None else None,
                accepted_at=accepted_at,
                body_ar=doc.body_ar,
                body_fr=doc.body_fr,
                body_en=doc.body_en,
                changes_ar=policies_service.changed_lines(old.body_ar if old else None, doc.body_ar),
                changes_fr=policies_service.changed_lines(old.body_fr if old else None, doc.body_fr),
                changes_en=policies_service.changed_lines(old.body_en if old else None, doc.body_en),
            )
        )
    return PendingPoliciesOut(pending=out)


@router.get("/policies/pending", response_model=PendingPoliciesOut)
async def my_pending_policies(app: PolicyApp, user: CurrentUser, session: DbSession) -> PendingPoliciesOut:
    """**ما ينتظر قبولَه في هذا التطبيق** — وقائمةٌ فارغةٌ حالُ أكثرِ الناس."""
    items = await policies_service.pending_for(session, user=user, app=app)
    return await _pending_out(session, user, items)


@router.post("/policies/accept", response_model=PendingPoliciesOut)
async def accept_policies(payload: AcceptPoliciesIn, user: CurrentUser, session: DbSession) -> PendingPoliciesOut:
    """**«أوافق»** — يكتب القبولَ بتاريخه ونسخته، ويعيد ما بقي (فارغاً حين تمّ)."""
    left = await policies_service.accept_pending(session, user=user, app=payload.app, policy_ids=payload.policy_ids)
    await session.commit()
    return await _pending_out(session, user, left)
