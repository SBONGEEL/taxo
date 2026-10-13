"""حسابُ المالك الحقيقيّ في الجزائر (SPEC §٧٤-ك/٢) — **راكبٌ في سوق الجزائر باسمه، ليس حسابَ تجربة**، لشحنةٍ حقيقيّةٍ صغيرةٍ بمفاتيح Chargily الحيّة.

**التسجيلُ في الجزائر مغلق** — فيُنشئه سكربتٌ ببابه الوحيد (`create_account`) على الإنتاج، والأمرُ يذكر ملفاتِه كلَّها:

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps --user "$(id -u):$(id -g)" -v /home/taxo/secrets:/out backend \\
      python -m scripts.provision_owner_account_74 --phone <رقمُ المالك> --secrets-file /out/owner-dz.env            # معاينة
    … --apply                                                                                                          # الكتابة

* **الرقمُ من المالك** («ask the owner … do not invent one») — لا افتراضَ له هنا، **ورقمٌ قائمٌ يقف** ولا يُكتب فوق حسابٍ أحد.
* **حسابٌ عاديّ**: لا وسمَ تجربة، **ولا رصيدَ تجريبيّ**، ولا اشتراك — **ومالُه ما يشحنه هو** (`test_accounts.require_real_money` يمرّ له).
* **في قائمة السماح بالحدود** (`markets.grant`) — يستعمله من ليبيا، كما أمر.
* **الرقمُ مؤكَّدٌ بلا رمز**: المالكُ أعطاه بنفسه، ولا قناةَ تحقّقٍ عاملةً في الجزائر — ويُكتب ذلك في التدقيق.
* **كلمةُ المرور قويّةٌ مولَّدة**، في ملفّ الأسرار وحدَه (600، لا يُكتب فوق ملفٍّ قائم)، **ولا تُطبع**.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.core.phone import dial_code_for, normalize_phone  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.enums import AuditAction, CountryCode, UserRole  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.auth import RegisterRequest  # noqa: E402
from app.services import audit, markets  # noqa: E402
from app.services.auth.base import create_account  # noqa: E402
from scripts.provision_test_accounts import (  # noqa: E402
    ProvisionRefused,
    _check_secrets_path,
    _existing,
    _new_password,
    _write_secrets,
)

COUNTRY = CountryCode.DZ
DEFAULT_NAME = "Mohammed Aldeeb"
ALLOWANCE_REASON = "حسابُ المالك الحقيقيّ في الجزائر — يستعمله من ليبيا (SPEC §٧٤-ك/٢)"


def _international(raw: str) -> str:
    """**الرقمُ بصيغته الدوليّة وبقواعد بلده** — قد يكون جزائريّاً أو ليبيّاً أو أردنيّاً (يستعمله المالكُ من ليبيا)، **وسوقُ الحساب الجزائرُ
    في الحالين**. والرقمُ المحلّيُّ بلا رمز دولةٍ يُردّ: لا يُخمَّن بلدُه."""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if raw.strip().startswith("00"):
        digits = digits[2:]
    elif not raw.strip().startswith("+"):
        raise ProvisionRefused("اكتب الرقمَ دوليّاً (+213… أو +218…) — لا يُخمَّن بلدُه")
    for country in (CountryCode.DZ, CountryCode.LY, CountryCode.JO):
        if digits.startswith(dial_code_for(country)):
            try:
                return normalize_phone(raw, country)
            except Exception as exc:  # noqa: BLE001 — رقمٌ لا يطابق قواعدَ بلده
                raise ProvisionRefused(f"الرقمُ لا يطابق قواعدَ أرقام {country.value}") from exc
    raise ProvisionRefused("رمزُ الدولة في الرقم ليس لسوقٍ من أسواق TAXO")


async def main_async(
    *, phone: str, name: str, secrets_file: Path, write: bool, session_factory=SessionLocal
) -> tuple[list[str], User | None]:
    _check_secrets_path(secrets_file)
    normalized = _international(phone)
    lines: list[str] = []
    async with session_factory() as session:
        session: AsyncSession
        if await _existing(session, normalized) is not None:
            raise ProvisionRefused("هذا الرقمُ لحسابٍ قائم — لا يُكتب فوقه. اطلب من المالك رقماً آخر أو استعمل الحسابَ القائم")
        password = _new_password(normalized)
        user = await create_account(
            session,
            phone=normalized,
            data=RegisterRequest(phone=normalized, password=password, name=name, country_code=COUNTRY, role=UserRole.RIDER),
            password_hash=hash_password(password),
            # **أعطاه المالكُ بنفسه** ولا قناةَ تحقّقٍ عاملةً في الجزائر — فيُؤكَّد بلا رمز، ويُكتب ذلك أدناه
            phone_verified_at=datetime.now(UTC),
        )
        await markets.grant(session, user=user, reason=ALLOWANCE_REASON, actor=None)
        await audit.record(
            session,
            actor=None,
            action=AuditAction.CREATE,
            entity_type="owner_account",
            entity_id=user.id,
            details={"script": "provision_owner_account_74", "country_code": COUNTRY.value, "is_test": False,
                     "phone_verified": "أعطاه المالكُ بنفسه — بلا رمز"},
        )
        lines.append(f"حسابٌ حقيقيّ · {COUNTRY.value} · …{normalized[-4:]} · {user.id} · راكب · في قائمة السماح")
        if not write:
            await session.rollback()
            return lines, None
        _write_secrets(secrets_file, ["=".join(pair) for pair in (("OWNER_DZ_PHONE", normalized), ("OWNER_DZ_PASSWORD", password))])
        try:
            await session.commit()
        except BaseException:
            secrets_file.unlink(missing_ok=True)
            raise
    return lines, user


def main() -> int:
    parser = argparse.ArgumentParser(description="حسابُ المالك الحقيقيّ في الجزائر (SPEC §٧٤-ك/٢)")
    parser.add_argument("--phone", required=True, help="الرقمُ كما أعطاه المالك — دوليّاً (+213… أو غيره)")
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--secrets-file", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        lines, _user = asyncio.run(
            main_async(phone=args.phone, name=args.name, secrets_file=args.secrets_file, write=args.apply)
        )
    except ProvisionRefused as exc:
        print(f"✗ {exc}")
        return 1
    for line in lines:
        print(f"  {line}")
    print("✓ كُتب — كلمةُ المرور في ملفّ الأسرار وحدَه" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
