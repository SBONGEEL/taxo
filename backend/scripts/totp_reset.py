"""مخرجُ الطوارئ من التحقق الثنائي (SPEC القسم 14.1، المرحلة 12-د).

    python -m scripts.totp_reset --phone +962790000001
    python -m scripts.totp_reset --phone +962790000001 --release-enforcement

**ويُبنى قبل الإلزام لا بعده.** بغيره يكون هذا العطلَ الوحيدَ غيرَ القابل
للإصلاح في المنصة كلها: لوحةٌ لا يدخلها أحدٌ ليصلح ما يمنع الدخول — مشرفٌ فقد
هاتفه وورقةَ رموزه، والإلزامُ يمنعه من إطفاء عامله من داخل اللوحة (وهو ما يجعل
الإلزامَ إلزاماً).

**ولا يُفتح هذا الباب من الشبكة أبداً**: من يشغّله يملك القاعدة أصلاً، فليس
تصعيداً لصلاحية — والفرقُ أنه لا يُنادى بتوكن. ولذلك:

- يكتب **قيدَ تدقيق** بلا فاعلٍ (`actor=None`): الفاعلُ إنسانٌ على الخادم لا
  حسابٌ في الجدول، وقيدٌ بلا فاعلٍ أصدقُ من قيدٍ ينسبه لمن لم يفعله.
- **ويُبطل كلَّ جلسات صاحب الحساب**: عواملُ دخوله تبدّلت للتوّ.
- ويكتب صفَّ إشعارٍ لصاحبه — إن لم يكن هو من طلب، فهذا أوّلُ ما يجب أن يعرفه.

و`--release-enforcement` يُطفئ مفتاحَ الإلزام العالميَّ نفسَه، للحالة التي لا
يبقى فيها مشرفٌ واحدٌ يملك عاملاً.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import delete, select

from app.core.db import SessionLocal, engine
from app.core.phone import normalize_phone
from app.core.redis_client import close_redis_client, get_redis_client
from app.models.enums import AuditAction, CountryCode
from app.models.security_setting import SecuritySetting
from app.models.totp import UserRecoveryCode, UserTotp
from app.models.user import User
from app.models.enums import AccountKind
from app.services import audit, inbox, token_service


async def _reset(phone: str, *, release_enforcement: bool) -> int:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.phone == phone, User.account_kind == AccountKind.TAXO))
        if user is None:
            print(f"لا حساب بالرقم {phone}")
            return 1

        record = await session.scalar(
            select(UserTotp).where(UserTotp.user_id == user.id)
        )
        if record is not None:
            await session.execute(
                delete(UserRecoveryCode).where(UserRecoveryCode.user_id == user.id)
            )
            await session.delete(record)
            await audit.record(
                session,
                actor=None,
                action=AuditAction.DELETE,
                entity_type="user_totp",
                entity_id=user.id,
                # لا رقمَ هاتفٍ في `details`: القاعدةُ أن يحمل أسماءَ ما تغيّر لا
                # قيمَه، و`entity_id` يحمل صاحبَ الحساب أصلاً
                details={"stage": "emergency_reset"},
            )
            await inbox.record(
                session,
                user_id=user.id,
                kind="totp_reset",
                title="أُلغي التحقق الثنائي",
                body=(
                    "أُلغي التحقق الثنائي على حسابك من الخادم. "
                    "سجّله من جديد، وإن لم تكن أنت من طلب ذلك فراجع الإدارة فوراً."
                ),
            )
            print(f"أُلغي التحقق الثنائي للحساب {phone}")
        else:
            print(f"لا تحقق ثنائي مسجّل على {phone}")

        if release_enforcement:
            row = await session.scalar(select(SecuritySetting).limit(1))
            if row is not None and row.admin_totp_required:
                row.admin_totp_required = False
                await audit.record(
                    session,
                    actor=None,
                    action=AuditAction.UPDATE,
                    entity_type="security_settings",
                    entity_id=row.id,
                    details={"stage": "emergency_reset", "fields": ["admin_totp_required"]},
                )
                print("أُطفئ مفتاح إلزام التحقق الثنائي")
            else:
                print("مفتاح الإلزام مطفأٌ أصلاً")

        await session.commit()

    redis = get_redis_client()
    revoked = await token_service.revoke_all_for_user(redis, user.id)
    print(f"أُبطلت {revoked} جلسة")
    return 0


async def _main() -> int:
    parser = argparse.ArgumentParser(description="إلغاء التحقق الثنائي لحسابٍ بعينه")
    parser.add_argument("--phone", required=True, help="رقم الهاتف (E.164 أو محلي)")
    parser.add_argument(
        "--country",
        choices=[c.value for c in CountryCode],
        default=CountryCode.JO.value,
        help="الدولة لتطبيع الرقم المحلي",
    )
    parser.add_argument(
        "--release-enforcement",
        action="store_true",
        help="يُطفئ مفتاح الإلزام العالمي أيضاً",
    )
    args = parser.parse_args()

    phone = normalize_phone(args.phone, CountryCode(args.country))
    try:
        return await _reset(phone, release_enforcement=args.release_enforcement)
    finally:
        await close_redis_client()
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
