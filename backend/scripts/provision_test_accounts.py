"""حسابا التجربة على الإنتاج (SPEC §٦٥-ج) — **راكبٌ واحدٌ وكبتنٌ واحد يبقيان للاختبارات القادمة**.

**يُشغَّل في حاوية الخلفية، وملفُّ الأسرار يُربط إليها ربطاً** — من جذر المشروع على الخادم (`~/taxo`)، **والأمرُ يذكر ملفاتِه
كلَّها** (`CLAUDE.md`):

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps --user "$(id -u):$(id -g)" -v /home/taxo/secrets:/out \\
      backend python -m scripts.provision_test_accounts --secrets-file /out/test-accounts.env

**ولمَ الربطُ صريحاً**: حاويةُ الخلفية لا ترى من القرص إلا `./backend` (في `/app`) و`./secrets` **للقراءة وحدَها** —
**و`/home/taxo/secrets` ليس فيها**. فمسارٌ بلا ربطٍ يسقط، **والمسارُ الذي يخطر بعده أسوأ**: `/app/…` هو شجرةُ المستودع على
الخادم، و`/tmp` داخل حاويةٍ تُحذف بخروجها — **فالحسابان ملتزَمان وكلمتاهما ضاعتا، وإعادةُ التشغيل تقول «موجود»**. فالسكربتُ
**يردّ الثلاثة قبل أن يكتب صفّاً** (`_check_secrets_path`). **و`--user`** كي يكون الملفُّ ملكَ `taxo` بإذن 600 كـ`taxo.env` —
لا ملكَ جذر الحاوية فلا يقرؤه صاحبُه. **وهذا الأمرُ مكتوبٌ لا مقيس**: لم يُشغَّل على الخادم بعد.

**يُشغَّل على الخادم بعد رفع `redesign` الذي يحمل عزلَهما** (قرارُ ٢٠٢٦-١٠-٠٨ في §٦٥-هـ): حسابُ تجربةٍ بلا عزلٍ يأخذ طلبَ راكبٍ
حقيقيٍّ ويدخل إحصاءاتِ المالك. **ولا يُشغَّل في غير ذلك إلا من مجموعة الاختبارات.**

## ما يفعله — وكلُّه من أبوابه الحقيقيّة

١. **الحسابان** بـ`create_account` — البابِ الوحيد (رمزُ الإحالة وبناءُ الدور وتصفيرُ عدّاد الرموز تقع كما تقع لكلِّ حساب).
٢. **الوسمُ `is_test`** يُكتب فوراً بعد الإنشاء وقبل أيِّ بابٍ آخر — **فكلُّ ما يليه يرى حسابَ تجربة**: العرضُ لا يُحلّ لكبتنها،
   والهديةُ لا تُعدّ في المجاميع. **وهذا السكربتُ والقاعدةُ هما الكاتبان الوحيدان للوسم** — لا حقلَ له في أيِّ مخطَّط طلب.
٣. **مركبةُ الكبتن** بحقول `VehicleCreate` نفسِها وتطبيعِ بابها (`POST /drivers/me/vehicles`) — ولا خدمةَ لإنشاء المركبة غيرُه.
٤. **الاعتمادُ** بـ`drivers.approve` — **البابِ الوحيد**، بحارسيه مستوفَيين (رقمٌ مُثبَت، ومستنداتٌ معتمدة).
٥. **الاشتراكُ** بـ`subscriptions.record_manual` — بابِ الإدارة الذي يسجّل اشتراكاً **بالمبلغ الذي قُبض فعلاً**، وهو هنا
   **صفر**: النموذجُ يقبله (`amount_paid >= 0`)، والمرجعُ يقول «اشتراكُ تجربة — لا مال». **ولمَ لا المحفظة**: الشراءُ منها
   يحتاج رصيداً، والرصيدُ لا يُعطى إلا «تصحيحَ تجربة» بيد مشرفٍ من اللوحة — **وقيدان (تصحيحٌ ثمّ خصمٌ) يقولان ما يقوله صفرٌ
   واحدٌ مكتوبٌ بسببه**. **والتجديدُ بعد الشهر** من التطبيق نفسِه: «تصحيحُ تجربة» من اللوحة، ثمّ شراءٌ من المحفظة.

## والتجاوزاتُ مسمّاةٌ لا ممرَّرةٌ صامتة — وهي تجاوزاتُ `provision_round_captain.py` نفسُها

* **`phone_verified_at` يُكتب بلا رمز.** الرقمُ مختلَقٌ لا يملكه أحدٌ (انظر أدناه) — **فلا رمزَ يصله أصلاً**، والتحقّقُ
  بالرقم مستحيلٌ بالبناء. **وأثرُه يُقال**: `drivers.approve` يشترط الإثباتَ لأن رقمَ الكبتن ما تصله حوالاتُ كليك — **وهذا
  الحسابُ لا يُرسَل إليه مالٌ حقيقيٌّ بحال** (السحبُ مغلقٌ عليه في `withdrawals`).
* **المستنداتُ تُكتب معتمدةً بلا ملفّات** — `file_path` فارغٌ بقصد كي يُقرأ الصفُّ على حقيقته: اعتمادٌ لحساب تجربة لا وثيقةٌ
  رُوجعت. **و`reviewed_by` فارغٌ**، وقيودُ التدقيق بلا فاعل: **لا مشرفَ قرّر هذا** — إنسانٌ على الخادم شغّل سكربتاً، **وقيدٌ
  يسمّي من لم يفعل أسوأُ من قيدٍ لا يسمّي أحداً** (قاعدةُ `admin_password_reset.py`). **ولا يُستعمل حسابُ المالك بحال** (§٦٥-ج/٤).

## الرقمان — ‎+962 71‎ لأن الخطةَ تحجزه ولا تُسنده

**فخُّ `COMMANDS.md` بعينه**: أرقامُ التطوير «مختلقةٌ لكنها بشكل أرقامٍ أردنيةٍ حقيقية — وبعضُها مسجَّلٌ على واتساب عند أصحابه»،
**ووصلت رسالةٌ حقيقيّةٌ إلى غريبٍ حقيقيّ** (`+962790000021`، 2026-08-16). **فلا يُختار رقمٌ في 077/078/079** (Orange · Umniah ·
Zain) **ولا 0746/0747/0755**: كلُّها في قائمة ITU لإسنادات الأردن (بلاغ 23.VI.2020) — **ولا شيءَ فيها يبدأ بـ070 ولا 071**.

**و071–073 «محجوزةٌ لخدماتٍ متنقّلةٍ مستقبلية»** في خطة الترقيم الوطنية (TRC، `national_numbering_plan.pdf`):
«The numbering ranges 071xxxxxxx-073xxxxxxx are designated as Reserved for Future Mobile Services» — **وحجمُ كتل الإسناد منها
«يُحدَّد حينها»**، أي أن **الإسنادَ لا يقع قبل أن تُفتح الخطةُ نفسُها**. **وبابُ الأرقام في النظام** (`core/phone.py`: تسعُ
خاناتٍ تبدأ بـ7) **يقبله كما يقبل غيرَه**.

**ولمَ لا 070** — وكان اختيارَ النسخة الأولى بدعوى «لا مشغّلَ له»، **وصُحِّحت في المراجعة (2026-10-08)**: الخطةُ نفسُها **تُسند
0700–0709 لخدمة الرقم الشخصيّ** (Personal Number Services) — رقمٌ يُحوِّل إلى هاتف إنسانٍ حقيقيّ، **يُمنح بالطلب في كتلٍ
من ألف بلا تعديلٍ للخطة**، و`+962700000651` كان في الكتلة الأولى منها. **و«مُسندٌ لغرضٍ لم يُمنح بعد» ليس «غيرَ مُسند»**: يومَ
تُمنح الكتلةُ يصل الرمزُ وإعادةُ تعيين كلمة المرور غريباً — **فيملك حسابَ التجربة**. والمحجوزُ أبعد: لا يُمنح منه شيءٌ قبل قرارٍ
يفتحه.

**وحدُّ هذا مكتوبٌ لا مسكوتٌ عنه**: نصّا الخطة أعلاه **من ملخّص بحثٍ لوثيقة TRC لا من الوثيقة نفسِها** — خادمُها ردّ الاتصال
(2026-10-08)؛ وقائمةُ ITU قُرئت من ملفّها. **فتُفتح الخطةُ قبل أوّل تشغيلٍ على الخادم**، والاختيارُ **وثيقةٌ لا برهان** — إن فُتح
071 يوماً صار احتمالاً. **ولذلك لا يُرسل السكربتُ شيئاً إلى الرقمين بحال**: لا رمزَ ولا رسالةَ نصّيةً ولا واتساب (`create_account`
لا يُرسل، و`approve` لا يُرسل، والاختبارُ يُسقط أيَّ نداءٍ لمزوّد الرسائل). **الرقمُ مُعرِّفُ دخولٍ هنا لا قناة.**

## الأسرار — في الملف وحدَه، ولا تُطبع

كلمتا المرور **تُولَّدان عشوائياً** (`secrets.token_urlsafe`) وتمرّان بسياسة كلمات المرور كما تمرّ في التسجيل،
**وتُكتبان في `--secrets-file` وحدَه بإذن 600** — **ولا تُطبعان، ولا تُكتبان في المستودع ولا التقارير ولا المحادثة** (§٦٥-ج/٣).
والشاشةُ تطبع الرقمين والمعرّفين و«كُتبت البيانات في الملف» لا غير.

* **والملفُّ لا يُكتب فوقه أبداً** (`O_EXCL`): مسارٌ خاطئٌ يشير إلى `taxo.env` كان سيمحو أسرارَ الإنتاج بضغطة.
* **ويُكتب قبل الالتزام**: إن سقط الالتزامُ حُذف الملفُّ الذي كتبناه — **وإن سقطت الكتابةُ لم يُلتزم شيء**. فلا حسابان بكلمتين
  لا يعرفهما أحد، ولا ملفٌّ لحسابين لم يوجدا.

## وإعادةُ تشغيله لا تغيّر شيئاً

حسابان موجودان موسومان ⇒ «موجود» لكلٍّ منهما، **ولا كتابة**. **وما عدا ذلك يقف ولا يُصلِح**: حسابٌ بأحد الرقمين **غيرُ موسوم**
(لا يُوسَم حسابٌ لم يُنشئه هذا السكربت)، أو أحدُهما دون الآخر (السكربتُ يُنشئهما في معاملةٍ واحدة — فنصفٌ قائمٌ يعني يداً أخرى).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

# **جذرُ الخلفية من موضع الملف** لا `/app` مكتوباً: يعمل في الحاوية وفي مجموعة الاختبارات بالسطر نفسِه
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core import password_policy  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.core.phone import normalize_phone  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.driver import Driver, DriverDocument, required_document_types  # noqa: E402
from app.models.enums import (  # noqa: E402
    AccountKind,
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
from app.schemas.driver import VehicleCreate  # noqa: E402
from app.services import drivers as drivers_service  # noqa: E402
from app.services import subscriptions as subscriptions_service  # noqa: E402
from app.services.auth.base import create_account  # noqa: E402

COUNTRY = CountryCode.JO

#: **‎+962 71‎ — بادئةٌ تحجزها الخطة ولا تُسندها** (انظر رأسَ الملف). و٦٥ في الذيل رقمُ القسم في المواصفة
RIDER_PHONE = "+962710000651"
CAPTAIN_PHONE = "+962710000652"
#: **البادئةُ التي يُفحص بها الرقمان قبل أيِّ كتابة** — رقمٌ عُدِّل يوماً إلى 079 (أو أُعيد إلى 070) يقف هنا لا عند غريب
_RESERVED_PREFIX = "+96271"

#: **جذرُ الخلفية** — `/app` في الحاوية، **وهو شجرةُ المستودع على الخادم** (`./backend` مربوطاً)
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
#: **ما يُمحى بخروج الحاوية أو بإقلاع الخادم** — `docker compose run --rm` يحذف كلَّ ما لم يُربط
_EPHEMERAL_ROOTS: tuple[Path, ...] = (Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"))

RIDER_NAME = "راكبُ التجربة"
CAPTAIN_NAME = "كبتنُ التجربة"

_VEHICLE = VehicleCreate(
    make="Toyota",
    model="Corolla",
    year=2020,
    color="أبيض",
    plate_number="TST-0652",
    category=VehicleCategory.ECONOMY,
)

#: **المرجعُ المكتوبُ على صفِّ الاشتراك** — من يقرأ التقريرَ بعد شهرٍ يعرف لماذا صفر
SUBSCRIPTION_REFERENCE = "اشتراكُ تجربة — لا مال (SPEC §65-ج)"
_REVIEW_NOTE = "اعتمادُ حساب تجربة (SPEC §65-ج) — لا ملفَّ ولا مراجعة"

#: **الأطولُ أوّلاً** — اشتراكُ تجربةٍ يُجدَّد أقلَّ مرّات
_DURATION_ORDER = (
    SubscriptionDurationType.MONTHLY,
    SubscriptionDurationType.WEEKLY,
    SubscriptionDurationType.DAILY,
)

PRESENT = "موجود"
WRITTEN = "كُتبت البيانات في الملف"


class ProvisionRefused(Exception):
    """**وقوفٌ بنصٍّ يسمّي السبب** — ولا يُصلَح شيءٌ على الإنتاج من هنا.

    **و`Exception` لا `SystemExit`**: الثاني يُرفع من داخل `asyncio.run` فتعامله الحلقةُ معاملةَ الإطفاء لا الخطأ — والنصُّ
    يُطبع في `main` ويخرج السكربتُ بواحد.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class Outcome:
    created: bool
    rider_id: str
    captain_id: str


def _new_password(phone: str) -> str:
    """**كلمةٌ قويةٌ تمرّ بسياسة التسجيل نفسِها** — فلا تُقبل هنا كلمةٌ يرفضها البابُ الحقيقيّ."""
    while True:
        candidate = secrets.token_urlsafe(24)
        try:
            password_policy.check(candidate, phone=phone)
        except Exception:  # noqa: BLE001 - احتمالٌ لا يكاد يقع؛ يُولَّد غيرُها
            continue
        return candidate


async def _existing(session: AsyncSession, phone: str) -> User | None:
    return await session.scalar(
        select(User).where(User.phone == phone, User.account_kind == AccountKind.TAXO)
    )


async def _plan(session: AsyncSession) -> SubscriptionPlan:
    plans = list(
        await session.scalars(
            select(SubscriptionPlan).where(
                SubscriptionPlan.country_code == COUNTRY,
                SubscriptionPlan.is_active.is_(True),
            )
        )
    )
    for duration in _DURATION_ORDER:
        for plan in plans:
            if plan.duration_type is duration:
                return plan
    raise ProvisionRefused(
        "لا خطةَ اشتراكٍ فعّالةٌ في الأردن — وكبتنٌ بلا اشتراكٍ لا يصله عرض. يُوقَف قبل أن يُكتب شيء"
    )


def _write_secrets(path: Path, lines: list[str]) -> None:
    """**إذنُ 600 من لحظة الإنشاء، ولا كتابةَ فوق ملفٍّ قائم** (`O_EXCL`).

    و`fchmod` بعد الفتح لأن `umask` الصدفة قد يُنقص الإذنَ الممرَّر لـ`open` — **فلا يُتّكأ عليه**.
    """
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ProvisionRefused(
            "ملفُّ الأسرار موجودٌ سلفاً — ولا يُكتب فوقه (مسارٌ خاطئٌ كان سيمحو أسرارَ الإنتاج). اختر مساراً جديداً"
        ) from exc
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _check_secrets_path(path: Path) -> None:
    """**مسارُ الأسرار يُفحص قبل أيِّ صفّ** — فلا يُلتزم حسابان بكلمتين في موضعٍ يضيع أو يُودَع.

    ثلاثةٌ مردودة، **وكلٌّ منها هو المسارُ الذي يخطر بعد أن يسقط الأمرُ الموثَّق** (رأسُ الملف):

    ١. **شجرةُ المستودع** — جذرُ الخلفية (`/app` في الحاوية، `./backend` على الخادم) أو مجلّدٌ فوقه `.git`: كلمتا مرورٍ على
       بُعد `git add` من المستودع، **ومن نسخته الاحتياطية** (§٦٥-ج/٣).
    ٢. **`/tmp` وأخواتُه** — يُمحى بخروج الحاوية: الحسابان ملتزَمان وكلمتاهما ضاعتا، **وإعادةُ التشغيل تقول «موجود»** فلا تُستعاد.
    ٣. **مجلّدٌ غيرُ موجود** — `/out` بلا `-v` يقف هنا بنصٍّ يدلّ على الربط، **لا عند `os.open` بعد أن كُتب الحسابان**.

    **وما لا يمسكه، ويُقال**: مجلّدٌ آخرُ داخل الحاوية لم يُربط (`/root` مثلاً) يُمحى كـ`/tmp` ولا يُعرف من المسار وحدَه —
    **والأمرُ الموثَّقُ هو الحارسُ هناك**.
    """
    target = path.expanduser().resolve()
    if target.is_relative_to(_BACKEND_ROOT) or any((folder / ".git").exists() for folder in target.parents):
        raise ProvisionRefused(
            "مسارُ الأسرار داخل شجرة المستودع — كلمتا المرور لا تُكتبان حيث تُودَع. "
            "اربط /home/taxo/secrets إلى الحاوية (-v /home/taxo/secrets:/out) واكتب في /out"
        )
    if any(target.is_relative_to(root.resolve()) for root in _EPHEMERAL_ROOTS):
        raise ProvisionRefused(
            "مسارُ الأسرار في مجلّدٍ يُمحى بخروج الحاوية — والحسابان يبقيان بلا كلمتين. "
            "اربط /home/taxo/secrets إلى الحاوية (-v /home/taxo/secrets:/out) واكتب في /out"
        )
    if not target.parent.is_dir():
        raise ProvisionRefused(
            f"مجلّدُ الأسرار غير موجود ({target.parent}) — داخل الحاوية لا يُرى /home/taxo/secrets إلا بربطه (-v)"
        )


async def _create(session: AsyncSession, *, phone: str, name: str, role: UserRole, password: str) -> User:
    user = await create_account(
        session,
        phone=phone,
        data=RegisterRequest(
            phone=phone,
            password=password,
            name=name,
            country_code=COUNTRY,
            role=role,
        ),
        password_hash=hash_password(password),
        # **التجاوزُ الأول مسمّى** — رقمٌ لا يملكه أحدٌ لا يصله رمز (رأسُ الملف)
        phone_verified_at=datetime.now(UTC),
    )
    # **الوسمُ قبل كلِّ بابٍ يليه** — كاتبُه الوحيدُ هذا السكربتُ والقاعدة
    await session.execute(update(User).where(User.id == user.id).values(is_test=True))
    await session.flush()
    await session.refresh(user)
    return user


async def provision(
    *,
    secrets_file: Path,
    session_factory: Callable[[], AsyncSession] = SessionLocal,
    out: Callable[[str], None] = print,
) -> Outcome:
    for phone in (RIDER_PHONE, CAPTAIN_PHONE):
        if not phone.startswith(_RESERVED_PREFIX):
            raise ProvisionRefused(f"رقمٌ خارج البادئة المحجوزة {_RESERVED_PREFIX} — قد يملكه إنسان")
        if normalize_phone(phone, COUNTRY) != phone:
            raise ProvisionRefused("رقمٌ لا يقبله بابُ الأرقام كما هو")
    _check_secrets_path(secrets_file)

    async with session_factory() as session:
        rider = await _existing(session, RIDER_PHONE)
        captain = await _existing(session, CAPTAIN_PHONE)

        if rider is not None or captain is not None:
            for found in (rider, captain):
                if found is not None and not found.is_test:
                    raise ProvisionRefused(
                        f"حسابٌ غيرُ موسومٍ برقم {found.phone} — لا يُوسَم حسابٌ لم يُنشئه هذا السكربت"
                    )
            if rider is None or captain is None:
                raise ProvisionRefused(
                    "أحدُ الحسابين موجودٌ دون الآخر — والسكربتُ يُنشئهما في معاملةٍ واحدة؛ يدٌ أخرى مرّت. يُوقَف ويُسأل"
                )
            out(f"{PRESENT}: {RIDER_NAME} · {rider.phone} · {rider.id}")
            out(f"{PRESENT}: {CAPTAIN_NAME} · {captain.phone} · {captain.id}")
            return Outcome(created=False, rider_id=str(rider.id), captain_id=str(captain.id))

        # **الخطةُ تُقرأ قبل أن يُكتب شيء** — غيابُها يقف هنا لا بعد حسابين بلا اشتراك
        plan = await _plan(session)

        rider_password = _new_password(RIDER_PHONE)
        captain_password = _new_password(CAPTAIN_PHONE)

        rider = await _create(
            session, phone=RIDER_PHONE, name=RIDER_NAME, role=UserRole.RIDER, password=rider_password
        )
        captain = await _create(
            session, phone=CAPTAIN_PHONE, name=CAPTAIN_NAME, role=UserRole.DRIVER, password=captain_password
        )
        driver = await session.scalar(select(Driver).where(Driver.user_id == captain.id))
        if driver is None:
            raise ProvisionRefused("أُنشئ حسابُ الكبتن بلا صفِّ كبتن — يُوقَف ولا يُلتزم شيء")

        # ── المركبة: حقولُ `VehicleCreate` وتطبيعُ بابها ──────────────────────
        session.add(
            Vehicle(
                driver_id=driver.id,
                make=_VEHICLE.make.strip(),
                model=_VEHICLE.model.strip(),
                year=_VEHICLE.year,
                color=_VEHICLE.color.strip(),
                plate_number=_VEHICLE.plate_number.strip().upper(),
                category=_VEHICLE.category,
            )
        )

        # ── التجاوزُ الثاني مسمّى: مستنداتٌ معتمدةٌ بلا ملفّات ولا مُراجِع ────
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

        # ── الاعتماد: البابُ الوحيد — **بلا فاعل**، فلا مشرفَ قرّره ──────────
        await drivers_service.approve(session, driver=driver, actor=None)  # type: ignore[arg-type]

        # ── الاشتراك: بابُ الإدارة بما قُبض فعلاً — صفر ──────────────────────
        subscription = await subscriptions_service.record_manual(
            session,
            driver=driver,
            user=captain,
            plan_id=plan.id,
            method=PaymentMethod.CASH,
            amount_paid=Decimal("0.000"),
            reference=SUBSCRIPTION_REFERENCE,
            actor=None,  # type: ignore[arg-type]
        )
        await session.flush()

        # ── الأسرارُ قبل الالتزام، والملفُّ يُحذف إن سقط الالتزام ─────────────
        _write_secrets(
            secrets_file,
            [
                f"# حسابا التجربة (SPEC §65-ج) — {datetime.now(UTC).isoformat(timespec='seconds')}",
                f"TAXO_TEST_RIDER_PHONE={rider.phone}",
                f"TAXO_TEST_RIDER_PASSWORD={rider_password}",
                f"TAXO_TEST_CAPTAIN_PHONE={captain.phone}",
                f"TAXO_TEST_CAPTAIN_PASSWORD={captain_password}",
            ],
        )
        try:
            await session.commit()
        except BaseException:
            secrets_file.unlink(missing_ok=True)
            raise

        out(f"✓ {RIDER_NAME} · {rider.phone} · {rider.id}")
        out(
            f"✓ {CAPTAIN_NAME} · {captain.phone} · {captain.id} · "
            f"{driver.status.value} · اشتراكٌ حتى {subscription.expires_at.date().isoformat()}"
        )
        out(WRITTEN)
        return Outcome(created=True, rider_id=str(rider.id), captain_id=str(captain.id))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="حسابا التجربة على الإنتاج (SPEC §65-ج)")
    parser.add_argument(
        "--secrets-file",
        required=True,
        type=Path,
        help=(
            "مسارٌ جديدٌ تُكتب فيه كلمتا المرور بإذن 600 — ولا يُكتب فوق ملفٍّ قائم، "
            "ولا في شجرة المستودع ولا /tmp. في الحاوية: /out/test-accounts.env مع -v /home/taxo/secrets:/out"
        ),
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
