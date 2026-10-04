"""حسابُ المشرف نفسِه — اسمُ المستخدم وكلمةُ المرور (قرارُ المالك 2026-08-20).

**وهو بابُ صاحبِ الحساب لا بابُ إدارةٍ لغيره**: كلُّ مسارٍ هنا يعمل على
`admin.id` ولا يقبل مُعرِّفَ أحدٍ آخر. ومشرفٌ يعدّل مشرفاً آخرَ **غيرُ مبنيٍّ
عمداً** — انظر SPEC §25.9.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentSessionId, DbSession, RedisDep, StaffUser
from app.core.exceptions import InvalidCredentials
from app.schemas.admin_account import (
    AdminAccountOut,
    ChangePasswordIn,
    ChangeUsernameIn,
)
from app.core.security import verify_password
from app.services import admin_credentials, token_service
from app.services.auth.password import set_password

router = APIRouter(prefix="/admin/account", tags=["admin"])


@router.get("", response_model=AdminAccountOut)
async def read_account(admin: StaffUser, session: DbSession) -> AdminAccountOut:
    row = await admin_credentials.for_user(session, admin.id)
    return AdminAccountOut(
        username=row.username if row else None,
        is_break_glass=bool(row and row.is_break_glass),
        has_phone=admin.phone is not None,
    )


@router.put("/username", response_model=AdminAccountOut)
async def change_username(
    payload: ChangeUsernameIn, admin: StaffUser, session: DbSession
) -> AdminAccountOut:
    """يغيّر اسمَه — **ويُسجَّل بالقديم والجديد** (`admin_credentials.rename`)."""
    row = await admin_credentials.rename(
        session, user=admin, new_username=payload.username
    )
    await session.commit()
    return AdminAccountOut(
        username=row.username,
        is_break_glass=row.is_break_glass,
        has_phone=admin.phone is not None,
    )


@router.put("/password", status_code=204)
async def change_password(
    payload: ChangePasswordIn,
    admin: StaffUser,
    session: DbSession,
    redis: RedisDep,
    current_sid: CurrentSessionId,
) -> None:
    """يغيّر كلمتَه — **بالحالية، ويُبطل بقيةَ الجلسات لا هذه**.

    **والحاليةُ شرطٌ لا احتياط**: جلسةٌ مسروقةٌ أو حاسوبٌ تُرك مفتوحاً يصير
    بغيرها بابَ استيلاءٍ دائم — يبدّل الكلمةَ فيُخرج صاحبَها ويبقى.

    **وإبطالُ البقية لا هذه**: من بدّل كلمتَه يريد إخراجَ غيره لا نفسِه، وإخراجُه
    يجعله يتردّد في التبديل — وهو نقيضُ الغرض. والجلسةُ الحاليةُ لا تُبطَل لأن
    التوكنَ في يد صاحبها الذي أثبت كلمتَه للتوّ.
    """
    if admin.password_hash is None or not verify_password(
        payload.current_password, admin.password_hash
    ):
        raise InvalidCredentials("كلمة المرور الحالية غير صحيحة")

    # **نفسُ السياسة القائمة**: الطولُ ٨–١٢٨ وقائمةُ المنع — لا شرطَ يُضاف
    # ولا يُنقص (`auth/password.validate_password`).
    #
    # **والجلسةُ الحاليةُ تبقى، والبقيةُ تسقط عند طلبها التالي** (SPEC §60):
    # `keep_sid` يستثنيها من الإبطال، و`kick` يُغلق مقابسَ غيرها لا مقابسَها.
    # **وكان قبل §60 يمحو مفتاحَ تجديدها هي أيضاً** — فتسقط بعد ربع ساعة رغم
    # الوعد المكتوب هنا وفي الشاشة. **والوعدُ هو المقصود**، فصار هو الواقع.
    await set_password(
        session,
        redis,
        user=admin,
        new_password=payload.new_password,
        keep_sid=current_sid,
    )
    await session.commit()
    await token_service.kick(redis, admin.id, keep=current_sid)
