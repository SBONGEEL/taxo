"""حسابُ المالك في اللوحة (SPEC §٧٦-ك/١) — **كلُّ صلاحيةٍ موجودةٍ وما يُضاف غداً**، بدور `owner` فوق `admin`.

**على الإنتاج، ومن الخادم وحدَه** — كما أُنشئ حسابا المشرف الأوّلان (`bootstrap_admins`) وحسابُ المالك الجزائريّ
(`provision_owner_account_74`)، **لا بتعديلٍ مباشرٍ في القاعدة**. والأمرُ يذكر ملفاتِه كلَّها:

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps -T --user "$(id -u):$(id -g)" -v /home/taxo/secrets:/out backend \\
      python -m scripts.provision_panel_owner --secrets-file /out/panel-owner.txt            # معاينة
    … --apply                                                                                 # الكتابة

* **الصلاحياتُ لا تُكتب صفوفاً**: `permissions.DEFAULTS[OWNER] = ALL` مشتقٌّ من التعداد — **فما يُضاف غداً يصله**، و`for_user` يعطيه
  الكلَّ ولو كُتبت له صفوف. **والمنحُ يُكتب في التدقيق بأمر المالك**: سطرٌ لكلِّ دور، وسطرٌ للحساب بصلاحياته كلِّها وحسّاسها.
* **ودورُه الأوّلُ `admin`** (عمود `users.role`) — فكلُّ بابٍ يسأل العمودَ وحدَه يعامله مشرفاً كما هو.
* **العاملُ الثاني إلزاميٌّ له وحدَه** (`security_settings.totp_required_for`) — يُسجَّل عند أوّل دخول؛ والمفتاحُ العامُّ لا يُمسّ.
* **وتغييرُ كلمة المرور عند أوّل دخولٍ غيرُ مبنيّ**: كلمةُ المشرف تتغيّر من الخادم وحدَه (`admin_password_reset`، قرارُ المالك ٢٠٢٦-٠٨-٢٠).
* **اسمُ المستخدم وكلمةُ المرور مولَّدان**، في ملفّ الأسرار وحدَه (600، لا يُكتب فوق ملفٍّ قائم)، **ولا يُطبعان**.
* **ولا يعمل مرّتين**: حسابٌ يحمل دورَ المالك يوقفه. **ولا يمسّ حساباً آخر.**
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.core.redis_client import get_redis_client  # noqa: E402
from app.models.enums import AuditAction, CountryCode, UserRole  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.user_role_grant import UserRoleGrant, has_role_clause  # noqa: E402
from app.services import admin_credentials, audit, permissions  # noqa: E402
from app.services.auth.password import set_password  # noqa: E402
from scripts.provision_test_accounts import ProvisionRefused, _check_secrets_path, _write_secrets  # noqa: E402

NAME = "Mohammed Aldeeb"
GRANTED_BY = "أمرُ المالك ٢٠٢٦-١٠-١٥ (SPEC §٧٦-ك/١)"
PANEL_URL = "https://admin.tajora.ly"

# **أسماءٌ لا تُخمَّن** — كحسابَي المشرف (`bootstrap_admins`): لا اسمَ المالك ولا `admin` ولا `owner`، ومعها لاحقةٌ عشوائيّة
_STEMS = ("qamar", "sanad", "rawasi", "athar", "nibras", "majd")


def _username() -> str:
    return f"{secrets.choice(_STEMS)}.{''.join(secrets.choice(string.digits) for _ in range(4))}"


def _password() -> str:
    """**٣٢ حرفاً (١٩٢ بتّاً)، بلا `=`** — الملفُّ `key=value` (العلّةُ في `bootstrap_admins._password`)."""
    return secrets.token_urlsafe(24)


async def main_async(
    *, secrets_file: Path, write: bool, session_factory=SessionLocal, redis=None
) -> tuple[list[str], User | None]:
    _check_secrets_path(secrets_file)
    async with session_factory() as session:
        session: AsyncSession
        if await session.scalar(select(User.id).where(has_role_clause(UserRole.OWNER)).limit(1)) is not None:
            raise ProvisionRefused("يوجد حسابٌ بدور المالك سلفاً — لا يُنشأ ثانٍ، ولا يُكتب فوقه")
        username, password = _username(), _password()
        user = User(
            phone=None,
            name=NAME,
            role=UserRole.ADMIN,
            country_code=CountryCode.JO,
            role_grants=[UserRoleGrant(role=UserRole.ADMIN), UserRoleGrant(role=UserRole.OWNER)],
        )
        session.add(user)
        await session.flush()
        await set_password(session, redis or get_redis_client(), user=user, new_password=password)
        await admin_credentials.create(session, user=user, username=username, is_break_glass=False)
        held = await permissions.for_user(session, user)
        if held != permissions.ALL:
            raise ProvisionRefused("دورُ المالك لا يعطي كلَّ الصلاحيات — يقف قبل أن يُكتب شيء")
        for role in (UserRole.ADMIN, UserRole.OWNER):
            await audit.record(
                session,
                actor=None,
                action=AuditAction.CREATE,
                entity_type="user_role_grant",
                entity_id=user.id,
                details={"role": role.value, "granted_by": GRANTED_BY, "script": "provision_panel_owner"},
            )
        await audit.record(
            session,
            actor=None,
            action=AuditAction.CREATE,
            entity_type="panel_owner_account",
            entity_id=user.id,
            details={
                "name": NAME,
                "roles": [UserRole.ADMIN.value, UserRole.OWNER.value],
                "permissions": sorted(p.value for p in held),
                "sensitive_included": sorted(p.value for p in permissions.SENSITIVE),
                "granted_by": GRANTED_BY,
                "second_factor": "إلزاميٌّ لدور المالك — يُسجَّل عند أوّل دخول",
                "script": "provision_panel_owner",
            },
        )
        lines = [
            f"حسابُ المالك · {NAME} · {user.id} · admin+owner · {len(held)} صلاحية "
            f"(ومعها الحسّاسة {len(permissions.SENSITIVE)}) · العاملُ الثاني إلزاميّ"
        ]
        if not write:
            await session.rollback()
            return lines, None
        _write_secrets(
            secrets_file,
            [
                "# حسابُ المالك في لوحة TAXO (SPEC §٧٦-ك/١) — وُلِّد على الخادم، ولا يُطبع في تقرير",
                f"panel={PANEL_URL}",
                f"name={NAME}",
                f"username={username}",
                f"password={password}",
                "# التحقّقُ بخطوتين إلزاميٌّ: أوّلُ دخولٍ يطلب تسجيلَ تطبيق المصادقة",
            ],
        )
        try:
            await session.commit()
        except BaseException:
            secrets_file.unlink(missing_ok=True)
            raise
    return lines, user


def main() -> int:
    parser = argparse.ArgumentParser(description="حسابُ المالك في اللوحة (SPEC §٧٦-ك/١)")
    parser.add_argument("--secrets-file", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        lines, _user = asyncio.run(main_async(secrets_file=args.secrets_file, write=args.apply))
    except ProvisionRefused as exc:
        print(f"✗ {exc}")
        return 1
    for line in lines:
        print(f"  {line}")
    print("✓ كُتب — اسمُ المستخدم وكلمةُ المرور في ملفّ الأسرار وحدَه" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
