"""إنشاءُ حسابَي المشرف الأولين — **على الإنتاج، ومن الخادم وحدَه**.

**ولمَ اثنان لا واحد؟** مشرفٌ واحدٌ بلا رقمٍ ولا بريدٍ ولا استعادةٍ ذاتية يعني
أن **ضياعَ جهاز العامل الثاني يقفل اللوحةَ كلَّها**. والثاني حسابُ طوارئ: يبقى
مغلقاً ولا يُستعمل يومياً، **ودخولُه يُكتب في سجل التدقيق بصفته** فيُعرف حين
يُستعمل لا بعد شهر.

**ولمَ من هنا لا من `seed.py`؟** لأن `seed_admin` يرفض العملَ في الإنتاج صراحةً
(وهو صحيح: كلمةٌ تمرّ بملفِّ بيئةٍ ليست سرّاً). وهذا يُنشئ الحسابَين **بأسماءٍ
وكلماتٍ يولّدها هو** ويكتبها في ملفٍ واحدٍ بصلاحيات مالكه، **ولا يطبعها**.

    python -m scripts.bootstrap_admins --out /home/taxo/secrets/panel-admins.txt

ولا يعمل مرتين: وجودُ حسابٍ إداريٍّ بأيِّ اسمٍ يوقفه.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import secrets
import string
import sys

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.redis_client import get_redis_client
from app.models.admin_credential import AdminCredential
from app.models.enums import CountryCode, UserRole
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant
from app.services import admin_credentials
from app.services.auth.password import set_password

# **أسماءٌ لا تُخمَّن**: لا `admin` ولا `taxo` ولا `root` — وهي مرفوضةٌ في
# `validate_username` أصلاً. والمقاطعُ عربيةٌ منقولةٌ بحروفٍ لاتينية، ومعها
# لاحقةٌ عشوائيةٌ فلا يُخمَّن الاسمُ ولو عُرف النمط.
NEWLINE = chr(10)

_STEMS = ("nawras", "shafaq", "mirsal", "yaqin", "sahil", "wathiq")


def _username() -> str:
    stem = secrets.choice(_STEMS)
    tail = "".join(secrets.choice(string.digits) for _ in range(4))
    return f"{stem}.{tail}"


def _password() -> str:
    """**بلا `=`** — والعلّةُ مقيسة: الملفُّ `key=value`، وقيمةٌ فيها `=` قطعها
    `cut -d= -f2` فبدت كلمةٌ من ٢٨ حرفاً ثمانيةً، والدخولُ ردّ ٤٠١ بلا سبب
    ظاهر. **قوّةُ الكلمة لا تنقص بحرفٍ واحد، وغموضُ الملفِّ ثمنٌ لا يُدفع.**
    """
    alphabet = string.ascii_letters + string.digits + "!@#%^&*-_+?"
    return "".join(secrets.choice(alphabet) for _ in range(28))


async def _run(out_path: pathlib.Path) -> int:
    redis = get_redis_client()
    async with SessionLocal() as session:
        existing = await session.scalar(
            select(func.count()).select_from(AdminCredential)
        )
        if existing:
            print(
                f"يوجد {existing} حسابٌ إداريٌّ سلفاً — لا يُنشأ شيء",
                file=sys.stderr,
            )
            return 1

        lines = ["# حسابا لوحة TAXO — وُلِّدا على الخادم، ولا يُطبعان في تقرير"]
        for label, break_glass in (("اليوميّ", False), ("الطوارئ", True)):
            name, password = _username(), _password()
            user = User(
                phone=None,
                name=f"مشرف — {label}",
                role=UserRole.ADMIN,
                country_code=CountryCode.JO,
                role_grants=[UserRoleGrant(role=UserRole.ADMIN)],
            )
            session.add(user)
            await session.flush()
            await set_password(session, redis, user=user, new_password=password)
            await admin_credentials.create(
                session, user=user, username=name, is_break_glass=break_glass
            )
            note = " — لا يُستعمل يومياً" if break_glass else ""
            lines.append("")
            lines.append(f"[{label}]{note}")
            lines.append(f"username={name}")
            lines.append(f"password={password}")

        await session.commit()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    old = os.umask(0o077)
    try:
        out_path.write_text(NEWLINE.join(lines) + NEWLINE, encoding="utf-8")
    finally:
        os.umask(old)
    out_path.chmod(0o600)

    print(f"أُنشئ حسابان. الاعتمادات في: {out_path}")
    print("ولم تُطبع هنا — اقرأها من الملف.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="إنشاء حسابَي المشرف الأولين")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    return asyncio.run(_run(pathlib.Path(args.out)))


if __name__ == "__main__":
    raise SystemExit(main())
