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

from app.core.deps import CurrentUser, DbSession, RedisDep
from app.schemas.account import DeletionRequestIn, DeletionStateOut
from app.services import account_deletion, token_service

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
    await token_service.revoke_all_for_user(redis, user.id)
    return DeletionStateOut(**await account_deletion.state(session, locked))


@router.delete("/deletion", response_model=DeletionStateOut)
async def restore_account(user: CurrentUser, session: DbSession) -> DeletionStateOut:
    """**التراجعُ في المهلة** — فعلٌ صريحٌ بعد الدخول، لا أثرٌ جانبيٌّ له."""
    locked = await account_deletion.restore(session, user=user)
    await session.commit()
    return DeletionStateOut(**await account_deletion.state(session, locked))
