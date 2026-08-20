"""إعادةُ كلمةِ مرور مشرفٍ من الخادم — **البابُ الوحيد** (قرارُ المالك 2026-08-20).

**ولمَ من الخادم وحدَه؟** المشرفُ يدخل باسمِ مستخدمٍ لا رقمَ له، ومسارُ الاستعادة
كلُّه مبنيٌّ على إثبات ملكية رقم. والبدائلُ الثلاثةُ أسوأ: بريدٌ يعني حقلاً
ومزوّداً ومسارَ تحقّقٍ جديداً وبابَ استيلاءٍ ثانياً؛ وسؤالُ أمانٍ أضعفُ من
الكلمة نفسِها؛ ورقمٌ للمشرف ينقض القرارَ من أساسه.

**وهذا نفسُ منطق `totp_reset.py`**: بابٌ خارج الشبكة هو ما يجعل الإلزامَ ممكناً.
ومن يفقد الوصولَ إلى الخادم يفقد اللوحة — **خطرٌ مقبولٌ مكتوبٌ لا سهو** (SPEC
§25.9)، ومخرجُه حسابُ الطوارئ الثاني.

    python -m scripts.admin_password_reset --username <اسم> [--revoke-sessions]

**ولا تُطبع الكلمةُ الجديدة في أيِّ مخرَج**: تُقرأ من طرفيةٍ بلا صدى.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.admin_credential import AdminCredential, normalize_username
from app.models.enums import AuditAction
from app.models.user import User
from app.services import audit
from app.services.auth.password import set_password


async def _run(username: str, revoke: bool) -> int:
    redis = get_redis_client()
    async with SessionLocal() as session:
        row = await session.scalar(
            select(AdminCredential).where(
                AdminCredential.username == normalize_username(username)
            )
        )
        if row is None:
            print(f"لا حسابَ إداريٌّ بهذا الاسم: {username}", file=sys.stderr)
            return 1

        user = await session.get(User, row.user_id)
        if user is None:  # pragma: no cover - مفتاحٌ أجنبيٌّ يمنعه
            print("الحسابُ المرتبطُ غيرُ موجود", file=sys.stderr)
            return 1

        first = getpass.getpass("كلمة المرور الجديدة: ")
        again = getpass.getpass("أعدها: ")
        if first != again:
            print("الكلمتان غيرُ متطابقتين", file=sys.stderr)
            return 1

        # **نفسُ السياسة**: `set_password` تمرّ بـ`validate_password` — الطولُ
        # وقائمةُ المنع، لا شرطَ يُضاف من هنا ولا يُنقص
        await set_password(session, redis, user=user, new_password=first)

        # **بلا فاعلٍ في السجل**: الفاعلُ إنسانٌ على الخادم، وصفٌّ يسمّي من لم
        # يفعل أسوأُ من صفٍّ لا يسمّي أحداً (قاعدةُ `totp_reset`)
        await audit.record(
            session,
            actor=None,
            action=AuditAction.UPDATE,
            entity_type="admin_credential",
            entity_id=row.id,
            details={
                "action": "password_reset_from_server",
                "username": row.username,
                "sessions_revoked": revoke,
            },
        )
        await session.commit()

    print(f"أُعيدت كلمةُ مرور «{username}».")
    if revoke:
        print("وأُبطلت جلساتُه كلُّها.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="إعادة كلمة مرور مشرف")
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--revoke-sessions",
        action="store_true",
        help="إبطالُ جلساته (`set_password` يفعله أصلاً — والعلمُ صريحٌ للسجل)",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.username, args.revoke_sessions))


if __name__ == "__main__":
    raise SystemExit(main())
