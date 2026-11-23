"""يومُ اشتراكٍ لكبتن التجربة وحدَه — بصفرٍ لا مال (إذنُ المالك ٢٠٢٦-١١-٢٣: «كبتنُ التجربة وحدَه، الموسومُ is_test، يوماً واحداً،
بأداة اللوحة والدفتر والتدقيق» — لإكمال اختبار كليك الحيّ: الراكبُ يرى «ادفع بكليك» والمسارُ يعمل).

**يُشغَّل على الإنتاج بعد الرفع**، في حاوية الخلفية، **وملفُّ حسابَي التجربة مركَّبٌ للقراءة وحدَها** — والأمرُ يذكر ملفاتِه كلَّها:

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps -v /home/taxo/secrets/test-accounts.env:/in/test-accounts.env:ro backend \\
      python -m scripts.test_captain_day --test-accounts /in/test-accounts.env          # معاينةٌ لا تكتب
    … --apply                                                                         # الكتابة

## ما يفعله — من بابه الحقيقيّ

* **يجد كبتنَ التجربة برقمه** (`TAXO_TEST_CAPTAIN_PHONE`) **ويقف إن لم يكن موسوماً `is_test`** — فلا يمنح هذا السكربتُ حساباً حقيقيّاً شيئاً
  بحال. **ويقف إن كان مغطّىً بعد** (لا يومَ ثانياً فوق غطاءٍ قائم).
* **يسجّل الاشتراكَ بـ`subscriptions.record_manual`** — بابِ اللوحة نفسِه، **بخطّة الأردن اليوميّة وبمبلغ صفر** والمرجعُ يقول لماذا،
  والقيدُ في سجلّ التدقيق يكتبه البابُ نفسُه. **ولا قيدَ في دفتر المحفظة**: لا مالَ دخل ولا خرج (كما في `provision_test_accounts.py`).
  **والبابُ نفسُه يردّ أيَّ مبلغٍ غيرِ الصفر لحساب تجربة** (`test_accounts.require_real_money`).
* **بلا فاعل** — لا مشرفَ قرّر في اللوحة: إنسانٌ على الخادم شغّل سكربتاً بإذن المالك، وقيدٌ يسمّي من لم يفعل أسوأُ من قيدٍ لا يسمّي أحداً.
* **المعاينةُ افتراضٌ** — بلا `--apply` يُطبع ما سيُكتب ثمّ يُتراجع. **ومعاملةٌ واحدة.**
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.models.driver import Driver  # noqa: E402
from app.models.enums import CountryCode, PaymentMethod, SubscriptionDurationType  # noqa: E402
from app.models.subscription import SubscriptionPlan  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import subscriptions as subscriptions_service  # noqa: E402

COUNTRY = CountryCode.JO
REFERENCE = "اشتراكُ تجربةٍ يوماً واحداً — لا مال (اختبارُ كليك الحيّ، إذنُ المالك ٢٠٢٦-١١-٢٣)"


class DayRefused(RuntimeError):
    """**يقف ولا يكتب** — والنصُّ يسمّي ما غاب أو ما خالف."""


@dataclass(frozen=True, slots=True)
class Plan:
    lines: list[str]


def _phone(path: Path) -> str:
    repo = Path(__file__).resolve().parents[1]
    try:
        path.resolve().relative_to(repo)
    except ValueError:
        pass
    else:
        raise DayRefused("ملفُّ حسابَي التجربة داخل المستودع — يُقرأ من مجلّد الأسرار وحدَه")
    if not path.is_file():
        raise DayRefused(f"لا ملفَّ في {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        name, _, value = raw.strip().partition("=")
        if name.strip() == "TAXO_TEST_CAPTAIN_PHONE" and value.strip():
            return value.strip()
    raise DayRefused("TAXO_TEST_CAPTAIN_PHONE غائبٌ عن الملفّ")


async def _apply(session: AsyncSession, phone: str) -> list[str]:
    user = await session.scalar(select(User).where(User.phone == phone))
    if user is None:
        raise DayRefused("لا حسابَ بهذا الرقم")
    if not user.is_test:
        raise DayRefused("الحسابُ ليس موسوماً is_test — لا يُمنح شيئاً")
    if user.country_code is not COUNTRY:
        raise DayRefused("كبتنُ التجربة ليس في الأردن")
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        raise DayRefused("لا صفَّ كبتنٍ لهذا الحساب")
    covered = await subscriptions_service.coverage_until(session, driver.id)
    if covered is not None:
        raise DayRefused(f"مغطّىً حتى {covered.isoformat(timespec='minutes')} — لا يومَ ثانياً فوق غطاءٍ قائم")
    plan = await session.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.country_code == COUNTRY,
            SubscriptionPlan.is_active.is_(True),
            SubscriptionPlan.duration_type == SubscriptionDurationType.DAILY,
        )
    )
    if plan is None:
        raise DayRefused("لا خطّةَ يوميّةً فعّالةً في الأردن")
    subscription = await subscriptions_service.record_manual(
        session,
        driver=driver,
        user=user,
        plan_id=plan.id,
        method=PaymentMethod.CASH,
        amount_paid=Decimal("0.000"),
        reference=REFERENCE,
        actor=None,  # type: ignore[arg-type]
    )
    await session.flush()
    return [
        f"كبتنُ التجربة (is_test) — خطّةُ «{plan.name}» اليوميّة بمبلغ {subscription.amount_paid}",
        f"يبدأ {subscription.starts_at.isoformat(timespec='minutes')} وينتهي {subscription.expires_at.isoformat(timespec='minutes')}",
    ]


async def main_async(*, test_accounts: Path, write: bool, session_factory=SessionLocal) -> Plan:
    phone = _phone(test_accounts)
    async with session_factory() as session:
        lines = await _apply(session, phone)
        if write:
            await session.commit()
        else:
            await session.rollback()
    return Plan(lines=lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="يومُ اشتراكٍ بصفرٍ لكبتن التجربة وحدَه")
    parser.add_argument("--test-accounts", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="اكتب — وبلاها معاينةٌ تتراجع")
    args = parser.parse_args()
    try:
        plan = asyncio.run(main_async(test_accounts=args.test_accounts, write=args.apply))
    except DayRefused as exc:
        print(f"✗ {exc}")
        return 1
    for line in plan.lines:
        print(f"  {line}")
    print("✓ كُتب" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
