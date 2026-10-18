"""حسابا Testers Community على الإنتاج (SPEC §٧٨) — **راكبٌ وكبتنٌ تُسلَّم بياناتُ دخولهما لمختبِرين من خارج TAXO**.

**قولُ المالك**: حسابان جديدان باسم «Testers Community» — **موسومان حسابَي تجربة، برصيدٍ تجريبيٍّ لا يُسحب ولا يُحوَّل، ودخولٍ
بكلمة مرورٍ بلا رسالة، وكلمةٍ لا تُغيَّر من التطبيق**؛ **لا يبلغان راكباً ولا كبتناً حقيقيّاً، ولا يتّصلان بإنسانٍ حقيقيّ، ولا يُطلقان
دفعاً حقيقيّاً عند Chargily، ولا يمسّان مالاً حقيقيّاً**؛ يعملان من أيِّ دولةٍ داخلَ عالم التجربة وحدَه؛ **وليسا حساباتِ Aldeeb ولا
حسابَي التجربة القائمين، ولا دخولَ لهما إلى اللوحة**.

**وكلُّ ذلك مبنيٌّ قبلهما** — فهما **عائلتان تمرّان بباب `provision_market_test_accounts` حرفاً**:

* **الوسمُ** `is_test` ⇒ العزلُ في الاتجاهين (`test_accounts`، والتوزيعُ لا يجمع عالَمين) · الاستثناءُ من كلِّ عدٍّ وتقرير ·
  **وكلُّ بابٍ يُدخل مالاً حقيقيّاً أو يُخرجه يردّهما** (السحب · التحويل · الشحنُ بقناةٍ حقيقيّة · Chargily وكلُّ بطاقة · السلفة).
* **رصيدُ التجربة** (`test_markets.refill`) قيدٌ موسومٌ «رصيد تجريبي» — **ومستثنًى من بصمة المال**: البصمةُ تُقرأ بـ`--as-of`
  لحظةَ «قبل»، وقيودُ ما بعدها لا تدخلها.
* **قائمةُ السماح بالعمل من الخارج** لكلِّ أفراد العائلتين — **فيعملان من أيِّ دولة**، ومُختارُ السوق يرى توائمَهما.
* **والكبتنُ** معتمدٌ بمركبةٍ ومستنداتٍ بلا ملفّات، **واشتراكٌ بصفرٍ** من خطّة سوقه.

**وما أضافه §٧٨** — في الخدمات لا هنا، فيحرس كلَّ حسابِ تجربة: **`set_password` و`account_deletion.request` يردّانه**
(`LockedOnTestAccount`) — فمختبِرٌ لا يغلق الحسابَ على من بعده.

## الأمران

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps --user "$(id -u):$(id -g)" -v /home/taxo/secrets:/out \\
      backend python -m scripts.provision_testers_community --secrets-file /out/testers-community.env

    # **إعادةُ ضبط حسابٍ أُسيء استعمالُه** — كلمةٌ جديدةٌ في ملفٍّ جديد، وإبطالُ كلِّ جلسات العائلة، وملءُ رصيد التجربة:
    …  backend python -m scripts.provision_testers_community --reset TC_RIDER --secrets-file /out/testers-community-<وقت>.env

**والكلمةُ تُكتب هنا بـ`hash_password` لا بـ`set_password`** — بقصد: الثاني يردّ حسابَ التجربة (§٧٨)، **والسكربتُ وحدَه صاحبُ
كلمته**. والسياسةُ هي هي (`_new_password` يمرّ بسياسة التسجيل).

## الأرقام

**‎+962 71‎ و‎+218 99‎ و‎+213 599‎** — البادئاتُ المحجوزةُ نفسُها (رأسُ `provision_market_test_accounts.py`)، بلاحقتين لم تُستعملا:
**…681 للراكب و…682 للكبتن**. **ولا رسالةَ إلى رقمٍ بحال.**
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from redis.asyncio import Redis  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.core.redis_client import get_redis_client  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.enums import CountryCode, UserRole  # noqa: E402
from app.services import test_markets, token_service  # noqa: E402
from scripts.provision_market_test_accounts import Family, Outcome, planned_accounts, provision  # noqa: E402
from scripts.provision_test_accounts import (  # noqa: E402
    WRITTEN,
    ProvisionRefused,
    _check_secrets_path,
    _existing,
    _new_password,
    _write_secrets,
)

NAME = "Testers Community"
TITLE = "حسابا Testers Community (SPEC §78)"

TC_FAMILIES: tuple[Family, ...] = (
    Family(
        "TC_RIDER", UserRole.RIDER, NAME, CountryCode.JO, "+962710000681",
        twins={CountryCode.LY: "+218990000681", CountryCode.DZ: "+213599000681"}, outside=True,
    ),
    Family(
        "TC_CAPTAIN", UserRole.DRIVER, NAME, CountryCode.JO, "+962710000682",
        twins={CountryCode.LY: "+218990000682", CountryCode.DZ: "+213599000682"}, outside=True,
    ),
)

RESET_DONE = "أُعيد ضبطُ الحساب"


async def create(
    *,
    secrets_file: Path,
    session_factory: Callable[[], AsyncSession] = SessionLocal,
    out: Callable[[str], None] = print,
) -> Outcome:
    return await provision(
        secrets_file=secrets_file, session_factory=session_factory, out=out, families=TC_FAMILIES, title=TITLE
    )


async def reset(
    key: str,
    *,
    secrets_file: Path,
    redis: Redis,
    session_factory: Callable[[], AsyncSession] = SessionLocal,
    out: Callable[[str], None] = print,
) -> None:
    """**كلمةٌ جديدةٌ للحساب الأوّل، وإبطالُ جلسات العائلة كلِّها، وملءُ رصيد التجربة** — ولا شيءَ غيرُ ذلك.

    **وجلساتُ التوائم تُبطَل معه**: مُختارُ السوق ينقل الجلسةَ إلى توأمٍ بلا كلمة، فمختبِرٌ في توأمٍ يبقى داخلاً لو أُبطل الأوّلُ وحدَه.
    """
    family = next((item for item in TC_FAMILIES if item.key == key), None)
    if family is None:
        raise ProvisionRefused(f"لا عائلةَ بهذا المفتاح: {key} — المفاتيح: {', '.join(item.key for item in TC_FAMILIES)}")
    _check_secrets_path(secrets_file)

    async with session_factory() as session:
        members = []
        for item in planned_accounts((family,)):
            user = await _existing(session, item.phone)
            if user is None or not user.is_test:
                raise ProvisionRefused(f"{item.phone} ليس حسابَ تجربةٍ قائماً — يُوقَف قبل أن يُكتب شيء")
            members.append((item, user))

        primary = next(user for item, user in members if item.primary)
        password = _new_password(primary.phone)
        primary.password_hash = hash_password(password)
        revoked = 0
        for _item, user in members:
            revoked += await token_service.revoke_all_for_user(
                session, redis, user.id, reason=token_service.REVOKE_PASSWORD_RESET
            )
            await test_markets.refill(session, user=user, actor=None)
        await session.flush()

        _write_secrets(
            secrets_file,
            [
                f"# {TITLE} — إعادةُ ضبط {family.key} — {datetime.now(UTC).isoformat(timespec='seconds')}",
                f"{family.key}_{family.country.value}_PHONE={primary.phone}",
                f"{family.key}_{family.country.value}_PASSWORD={password}",
            ],
        )
        try:
            await session.commit()
        except BaseException:
            secrets_file.unlink(missing_ok=True)
            raise

    for _item, user in members:
        await token_service.kick(redis, user.id)
    out(f"✓ {RESET_DONE}: {family.key} · {primary.phone} · جلساتٌ أُبطلت {revoked}")
    out(WRITTEN)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("--secrets-file", required=True, type=Path, help="مسارٌ جديدٌ بإذن 600 — في الحاوية تحت /out")
    parser.add_argument("--reset", choices=[family.key for family in TC_FAMILIES], help="يعيد ضبطَ حسابٍ قائم")
    args = parser.parse_args(argv)

    async def _run() -> None:
        if args.reset:
            await reset(args.reset, secrets_file=args.secrets_file, redis=get_redis_client())
        else:
            await create(secrets_file=args.secrets_file)

    try:
        asyncio.run(_run())
    except ProvisionRefused as refused:
        print(f"✗ {refused.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
