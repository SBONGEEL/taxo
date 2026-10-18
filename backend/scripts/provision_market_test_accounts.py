"""حساباتُ التجربة في كلِّ سوق (SPEC §٧٤-أ/١٠، §٧٤-ز) — **Aldeeb راكباً وكبتناً، وتوأما حسابَي التجربة القائمين، وراكبٌ وكبتنٌ جزائريّان**.

**يُشغَّل بعد التصفير** (الجزء ١ أوّلاً بنصّ المالك) **وبعد `provision_test_accounts`** (حسابا §٦٥-ج أصلا عائلتين هنا)، وفي حاوية الخلفية
وملفُّ الأسرار مربوطٌ إليها — **والأمرُ يذكر ملفاتِه كلَّها**:

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps --user "$(id -u):$(id -g)" -v /home/taxo/secrets:/out \\
      backend python -m scripts.provision_market_test_accounts --secrets-file /out/aldeeb-accounts.env

## ما يفعله — في معاملةٍ واحدة، وكلُّه من أبوابه الحقيقيّة

١. **العائلات** (`FAMILIES`): لكلِّ عائلةٍ حسابٌ أوّلُ وتوأمٌ في كلِّ سوقٍ آخر، **يجمعها `users.test_twin_of`** — فيعرف مُختارُ السوق
   إخوتَه. **وأصلا حسابَي §٦٥-ج لا يُنشآن هنا**: يُقرآن موسومَين أو يقف السكربت.
٢. **كلُّ حسابٍ** بـ`create_account` — البابِ الوحيد — **وبسوقه** (العملةُ والأسعارُ وطرقُ الدفع تتبعه)، **والوسمُ `is_test` فوراً**.
٣. **كلُّ كبتنٍ**: مركبةٌ، ومستنداتٌ معتمدةٌ بلا ملفّات، **واعتمادٌ بـ`drivers.approve`**، **واشتراكٌ بصفرٍ** بـ`record_manual` من خطّة سوقه
   — كما يفعل `provision_test_accounts` حرفاً، **وتجاوزاتُه المسمّاةُ هناك هي تجاوزاتُ هذا**.
٤. **رصيدُ التجربة** لكلِّ حساب (`test_markets.refill`): الأردن 100.000 · ليبيا 500.000 · الجزائر 20,000 — قيدٌ موسومٌ «رصيد تجريبي».
٥. **قائمةُ السماح بالعمل من الخارج** لكلِّ أفراد العائلات الأربع (بنصّ المالك: «الأربعة») — **لا للجزائريَّين**: هما يقيسان تجربةَ
   الجزائر كما يعيشها أهلُها، والحدودُ منها.

## والتجاوزُ الثالث مسمّى — خطّةُ الجزائر

**لا خطّةَ اشتراكٍ في الجزائر**، **وسعرُها للمالك** (الجزء ٨: «لا يتغيّر سعرُ اشتراكٍ قبل نعمِه»). وكبتنٌ بلا اشتراكٍ لا يصله عرض.
**فتُنشأ خطّةٌ شهريّةٌ واحدةٌ موقوفة** بسعر التوصية في `design/SUBSCRIPTION-STUDY-LY-DZ.md` — **موقوفةٌ لا يراها كبتنٌ ولا يشتريها**
(`available_plans` و`get_plan` يردّان الموقوفة). **ويُسجَّل اشتراكُ التجربة عليها بفتحها داخل المعاملة نفسِها ثمّ إيقافِها قبل
الالتزام** — فلا تُرى مفتوحةً من معاملةٍ أخرى لحظةً واحدة (READ COMMITTED)، **ويمرّ الاشتراكُ ببابه الحقيقيّ** لا بصفٍّ يُكتب باليد.
**ونعمُ المالك يفتحها من اللوحة، أو يعدّلها** — لا شيءَ هنا يقرّر عنه.

## الأرقام — بادئةٌ لا تُسند لإنسانٍ في كلِّ سوق

* **الأردن ‎+962 71‎** — محجوزةٌ في خطّة الترقيم (انظر رأسَ `provision_test_accounts.py`).
* **ليبيا ‎+218 99‎** — **097/098/099 غيرُ مُسنَدةٍ لمشغّل** في ما قُرئ (sent.dm، ٢٠٢٦-١٠-١٣).
* **الجزائر ‎+213 599‎** — **لا نطاقَ تجربةٍ منشوراً في الجزائر**، ولم يُعرف لـ0599 مشغّلٌ في ما قُرئ.

**وحدُّ هذا مكتوب**: البادئتان الأخيرتان **اختيارٌ لا برهان** — من ملخّصات بحثٍ لا من خطّة ترقيمٍ رسميّةٍ فُتحت.

**والثلاثُ معرّفاتُ دخولٍ لا قنوات**: لا قناةَ تحقّقٍ عاملةً في ليبيا والجزائر، **ولا يُرسل السكربتُ شيئاً إلى رقمٍ بحال** — والاختبارُ
يُسقط أيَّ نداءٍ لمزوّد رسائل.

## الأسرار — في الملف وحدَه

كلماتُ المرور مولَّدةٌ بسياسة التسجيل، **في `--secrets-file` وحدَه بإذن 600، ولا يُكتب فوق ملفٍّ قائم**، ويُكتب قبل الالتزام ويُحذف إن
سقط — **قواعدُ `provision_test_accounts` بدوالّها نفسِها**. والشاشةُ تطبع الأرقامَ والمعرّفات لا غير.

## وإعادةُ تشغيله لا تغيّر شيئاً

كلُّ الحسابات موجودةٌ موسومة ⇒ «موجود» لكلٍّ ولا كتابة. **وما عدا ذلك يقف ولا يُصلِح**: حسابٌ غيرُ موسومٍ بأحد الأرقام، أو بعضُها
دون بعض (المعاملةُ واحدة — فنصفٌ قائمٌ يعني يداً أخرى).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.currency import currency_for_country  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.core.phone import normalize_phone  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.driver import Driver, DriverDocument, required_document_types  # noqa: E402
from app.models.enums import (  # noqa: E402
    CountryCode,
    DocumentReviewStatus,
    PaymentMethod,
    SubscriptionDurationType,
    UserRole,
    VehicleCategory,
)
from app.models.subscription import SubscriptionPlan  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.vehicle import Vehicle  # noqa: E402
from app.schemas.auth import RegisterRequest  # noqa: E402
from app.services import drivers as drivers_service  # noqa: E402
from app.services import markets, test_markets  # noqa: E402
from app.services import subscriptions as subscriptions_service  # noqa: E402
from app.services.auth.base import create_account  # noqa: E402
from scripts.provision_test_accounts import (  # noqa: E402
    CAPTAIN_NAME,
    CAPTAIN_PHONE,
    PRESENT,
    RIDER_NAME,
    RIDER_PHONE,
    WRITTEN,
    ProvisionRefused,
    _check_secrets_path,
    _existing,
    _new_password,
    _write_secrets,
)

#: **البادئةُ التي لا تُسند لإنسانٍ في كلِّ سوق** — يُفحص بها كلُّ رقمٍ قبل أيِّ كتابة (رأسُ الملف)
RESERVED_PREFIX: dict[CountryCode, str] = {
    CountryCode.JO: "+96271",
    CountryCode.LY: "+21899",
    CountryCode.DZ: "+213599",
}

SUBSCRIPTION_REFERENCE = "اشتراكُ تجربة — لا مال (SPEC §74-ز)"
ALLOWANCE_REASON = "حسابُ تجربة — يعمل من خارج الدول (SPEC §74-ز)"
_REVIEW_NOTE = "اعتمادُ حساب تجربة (SPEC §74-ز) — لا ملفَّ ولا مراجعة"

#: **خطّةُ الجزائر الموقوفة** — بسعر التوصية في `design/SUBSCRIPTION-STUDY-LY-DZ.md`، **ولا تُفتح إلا بنعم المالك**
DZ_HELD_PLAN = ("TAXO X30", SubscriptionDurationType.MONTHLY, Decimal("6000"))

_DURATION_ORDER = (SubscriptionDurationType.MONTHLY, SubscriptionDurationType.WEEKLY, SubscriptionDurationType.DAILY)


@dataclass(frozen=True, slots=True)
class Family:
    key: str
    role: UserRole
    name: str
    #: **الحسابُ الأوّل** — سوقُه وهاتفه؛ و`existing` يعني أنه لا يُنشأ هنا بل يُقرأ موسوماً
    country: CountryCode
    phone: str
    existing: bool = False
    #: **التوائم**: سوقٌ ← هاتف
    twins: dict[CountryCode, str] = field(default_factory=dict)
    #: **في قائمة السماح بالعمل من الخارج** — كلُّ أفرادها
    outside: bool = False


FAMILIES: tuple[Family, ...] = (
    Family(
        "ALDEEB_RIDER", UserRole.RIDER, "Aldeeb", CountryCode.JO, "+962710000661",
        twins={CountryCode.LY: "+218990000661", CountryCode.DZ: "+213599000661"}, outside=True,
    ),
    Family(
        "ALDEEB_CAPTAIN", UserRole.DRIVER, "Aldeeb", CountryCode.JO, "+962710000662",
        twins={CountryCode.LY: "+218990000662", CountryCode.DZ: "+213599000662"}, outside=True,
    ),
    Family(
        "TEST_RIDER", UserRole.RIDER, RIDER_NAME, CountryCode.JO, RIDER_PHONE, existing=True,
        twins={CountryCode.LY: "+218990000651", CountryCode.DZ: "+213599000651"}, outside=True,
    ),
    Family(
        "TEST_CAPTAIN", UserRole.DRIVER, CAPTAIN_NAME, CountryCode.JO, CAPTAIN_PHONE, existing=True,
        twins={CountryCode.LY: "+218990000652", CountryCode.DZ: "+213599000652"}, outside=True,
    ),
    Family("DZ_RIDER", UserRole.RIDER, "راكبُ تجربة الجزائر", CountryCode.DZ, "+213599000671"),
    Family("DZ_CAPTAIN", UserRole.DRIVER, "كبتنُ تجربة الجزائر", CountryCode.DZ, "+213599000672"),
)


@dataclass(frozen=True, slots=True)
class Planned:
    """**حسابٌ يُنشأ** — مفتاحُه في ملفّ الأسرار، وسوقُه، وأصلُه إن كان توأماً."""

    label: str
    family: Family
    country: CountryCode
    phone: str
    primary: bool


def planned_accounts(families: tuple[Family, ...] = FAMILIES) -> list[Planned]:
    out: list[Planned] = []
    for family in families:
        if not family.existing:
            out.append(Planned(f"{family.key}_{family.country.value}", family, family.country, family.phone, True))
        for country, phone in family.twins.items():
            out.append(Planned(f"{family.key}_{country.value}", family, country, phone, False))
    return out


@dataclass(frozen=True, slots=True)
class Outcome:
    created: bool
    #: هاتفٌ ← معرّف
    ids: dict[str, str]


def _check_phones(families: tuple[Family, ...] = FAMILIES) -> None:
    for family in families:
        for country, phone in ((family.country, family.phone), *family.twins.items()):
            if not phone.startswith(RESERVED_PREFIX[country]):
                raise ProvisionRefused(f"رقمٌ خارج البادئة المحجوزة {RESERVED_PREFIX[country]} — قد يملكه إنسان")
            if normalize_phone(phone, country) != phone:
                raise ProvisionRefused(f"رقمٌ لا يقبله بابُ أرقام سوقه كما هو ({country.value})")


async def _plan_for(session: AsyncSession, country: CountryCode) -> tuple[SubscriptionPlan, bool]:
    """**خطّةُ سوق الكبتن** — المفعّلةُ الأطول؛ وإلا **خطّةُ الجزائر الموقوفة** (تُنشأ إن غابت). الثاني: «موقوفةٌ تُفتح داخل المعاملة»."""
    plans = list(await session.scalars(select(SubscriptionPlan).where(SubscriptionPlan.country_code == country)))
    for duration in _DURATION_ORDER:
        for plan in plans:
            if plan.is_active and plan.duration_type is duration:
                return plan, False
    if country is not CountryCode.DZ:
        raise ProvisionRefused(f"لا خطّةَ اشتراكٍ فعّالةٌ في {country.value} — يُوقَف قبل أن يُكتب شيء")
    name, duration, price = DZ_HELD_PLAN
    held = next((plan for plan in plans if plan.name == name), None)
    if held is None:
        held = SubscriptionPlan(
            country_code=country,
            name=name,
            duration_type=duration,
            price=price,
            currency=currency_for_country(country),
            is_active=False,
        )
        session.add(held)
        await session.flush()
    return held, True


async def _create(session: AsyncSession, item: Planned, password: str, twin_of: User | None) -> User:
    user = await create_account(
        session,
        phone=item.phone,
        data=RegisterRequest(
            phone=item.phone,
            password=password,
            name=item.family.name,
            country_code=item.country,
            role=item.family.role,
        ),
        password_hash=hash_password(password),
        # **رقمٌ لا يملكه أحدٌ لا يصله رمز** — التجاوزُ الأوّلُ في `provision_test_accounts`
        phone_verified_at=datetime.now(UTC),
    )
    await session.execute(
        update(User).where(User.id == user.id).values(is_test=True, test_twin_of=twin_of.id if twin_of else None)
    )
    await session.flush()
    await session.refresh(user)
    return user


async def _make_captain(session: AsyncSession, user: User) -> str:
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        raise ProvisionRefused("أُنشئ حسابُ كبتنٍ بلا صفِّ كبتن — يُوقَف ولا يُلتزم شيء")
    country = CountryCode(user.country_code)
    session.add(
        Vehicle(
            driver_id=driver.id,
            make="Toyota",
            model="Corolla",
            year=2020,
            color="أبيض",
            plate_number=f"TST-{user.phone[-4:]}-{country.value}",
            category=VehicleCategory.ECONOMY,
        )
    )
    stamped = datetime.now(UTC)
    for doc_type in required_document_types(gender_verified_female=False):
        session.add(
            DriverDocument(
                driver_id=driver.id,
                doc_type=doc_type,
                review_status=DocumentReviewStatus.APPROVED,
                file_path="",
                content_type="",
                size_bytes=0,
                reviewed_by=None,
                reviewed_at=stamped,
                review_note=_REVIEW_NOTE,
            )
        )
    await session.flush()
    await drivers_service.approve(session, driver=driver, actor=None)  # type: ignore[arg-type]

    plan, held = await _plan_for(session, country)
    if held:
        # **التجاوزُ الثالث** (رأسُ الملف): تُفتح داخل المعاملة وتُوقَف قبل الالتزام — لا تُرى مفتوحةً لحظة
        plan.is_active = True
        await session.flush()
    subscription = await subscriptions_service.record_manual(
        session,
        driver=driver,
        user=user,
        plan_id=plan.id,
        method=PaymentMethod.CASH,
        amount_paid=Decimal(0),
        reference=SUBSCRIPTION_REFERENCE,
        actor=None,  # type: ignore[arg-type]
    )
    if held:
        plan.is_active = False
    await session.flush()
    return f"{driver.status.value} · اشتراكٌ حتى {subscription.expires_at.date().isoformat()}"


async def provision(
    *,
    secrets_file: Path,
    session_factory: Callable[[], AsyncSession] = SessionLocal,
    out: Callable[[str], None] = print,
    families: tuple[Family, ...] = FAMILIES,
    title: str = "حساباتُ التجربة في كلِّ سوق (SPEC §74-ز)",
) -> Outcome:
    """**العائلاتُ مُمرَّرة** (§٧٨): حسابا Testers Community عائلتان أخريان تمرّان بالبابِ نفسِه حرفاً — `provision_testers_community`."""
    _check_phones(families)
    _check_secrets_path(secrets_file)
    plan = planned_accounts(families)

    async with session_factory() as session:
        # ── الأصلان القائمان: موسومان أو وقوف ──────────────────────────────
        primaries: dict[str, User] = {}
        for family in families:
            if not family.existing:
                continue
            found = await _existing(session, family.phone)
            if found is None or not found.is_test:
                raise ProvisionRefused(
                    f"أصلُ العائلة {family.key} ليس حسابَ تجربةٍ قائماً — شغّل provision_test_accounts أوّلاً. يُوقَف قبل أن يُكتب شيء"
                )
            primaries[family.key] = found

        # ── الجديدةُ: كلُّها موجودةٌ موسومة ⇒ لا شيء؛ بعضُها ⇒ وقوف ──────────
        found_new = {item.phone: await _existing(session, item.phone) for item in plan}
        for user in found_new.values():
            if user is not None and not user.is_test:
                raise ProvisionRefused(f"حسابٌ غيرُ موسومٍ برقم {user.phone} — لا يُوسَم حسابٌ لم يُنشئه هذا السكربت")
        present = [user for user in found_new.values() if user is not None]
        if present:
            if len(present) != len(plan):
                raise ProvisionRefused(
                    "بعضُ الحسابات موجودٌ دون بعض — والسكربتُ يُنشئها في معاملةٍ واحدة؛ يدٌ أخرى مرّت. يُوقَف ويُسأل"
                )
            for item in plan:
                user = found_new[item.phone]
                assert user is not None
                out(f"{PRESENT}: {item.family.name} · {item.country.value} · {user.phone} · {user.id}")
            return Outcome(created=False, ids={phone: str(user.id) for phone, user in found_new.items() if user})

        # ── الإنشاء ───────────────────────────────────────────────────────
        passwords = {item.phone: _new_password(item.phone) for item in plan}
        created: dict[str, User] = {}
        lines: list[str] = []
        for item in plan:
            twin_of = None if item.primary else primaries.get(item.family.key) or created[item.family.phone]
            user = await _create(session, item, passwords[item.phone], twin_of)
            created[item.phone] = user
            note = await _make_captain(session, user) if item.family.role is UserRole.DRIVER else "راكب"
            lines.append(f"✓ {item.family.name} · {item.country.value} · {user.phone} · {user.id} · {note}")

        # ── رصيدُ التجربة لكلِّ أفراد العائلات، وقائمةُ السماح للأربع ─────────
        members = [*primaries.values(), *created.values()]
        for user in members:
            await test_markets.refill(session, user=user, actor=None)
        for family in families:
            if not family.outside:
                continue
            group = [primaries[family.key]] if family.existing else []
            group += [created[phone] for phone in (family.phone, *family.twins.values()) if phone in created]
            for user in group:
                if await markets.active_allowance(session, user.id) is None:
                    await markets.grant(session, user=user, reason=ALLOWANCE_REASON, actor=None)
        await session.flush()

        _write_secrets(
            secrets_file,
            [f"# {title} — {datetime.now(UTC).isoformat(timespec='seconds')}"]
            + [
                "=".join(pair)
                for item in plan
                for pair in ((f"{item.label}_PHONE", item.phone), (f"{item.label}_PASSWORD", passwords[item.phone]))
            ],
        )
        try:
            await session.commit()
        except BaseException:
            secrets_file.unlink(missing_ok=True)
            raise

    for line in lines:
        out(line)
    out(WRITTEN)
    return Outcome(created=True, ids={phone: str(user.id) for phone, user in created.items()})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="حساباتُ التجربة في كلِّ سوق (SPEC §74-ز)")
    parser.add_argument(
        "--secrets-file",
        required=True,
        type=Path,
        help="مسارٌ جديدٌ بإذن 600 — في الحاوية: /out/aldeeb-accounts.env مع -v /home/taxo/secrets:/out",
    )
    args = parser.parse_args(argv)
    try:
        asyncio.run(provision(secrets_file=args.secrets_file))
    except ProvisionRefused as refused:
        print(f"✗ {refused.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
