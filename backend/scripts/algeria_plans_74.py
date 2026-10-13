"""خططُ اشتراك الجزائر وعرضُ الإطلاق بأمر المالك (SPEC §٧٤-ل/٢) — **الشهريُّ 6,000 د.ج، واليوميُّ والأسبوعيُّ متناسبان معه**.

    docker compose … run --rm --no-deps backend python -m scripts.algeria_plans_74 [--apply]

* **التناسبُ بأيّام الخطّة في الشيفرة** (`subscriptions`: الشهرُ ٣٠ يوماً): اليوميُّ 6,000 ÷ 30 = **200**، والأسبوعيُّ 6,000 × 7 ÷ 30 = **1,400**
  — دنانيرُ صحيحةٌ ومضاعفاتٌ لعشرة (قاعدةُ تقريب الجزائر)، **فالتقريبُ لا يغيّرها**. **والأسماءُ اسمُ الأردن**: «TAXO X1 — يومي» ·
  «TAXO X7 — أسبوعي» · «TAXO X30 — شهري».
* **الخطّةُ الموقوفةُ** («TAXO X30» بـ6,000، أنشأها سكربتُ حسابات التجربة) **هي الشهريّة نفسُها** — تُسمّى وتُفتح، **فلا خطّتان شهريّتان**.
* **عرضُ الإطلاق** «أول أسبوع مجاناً»: ١٠٠٪ على الأسبوعيّة، **للكبتن الجديد**، مرّةً واحدة، **وعمولتُه صفرٌ صريحاً** («first week free with
  zero commission») — **والجزائرُ بلا عمولةٍ اليوم أصلاً**، والصفرُ الصريحُ يبقيها صفراً للأسبوع الأوّل لو أُشعلت يوماً.
* **ومن يكتب**: بلا فاعل (المالكُ قرّر في المحادثة، لا مشرفٌ في اللوحة) — **وكلُّ صفٍّ سطرٌ في التدقيق بالأمر**. **وتجميدُ التسعير يُحترم.**
* **معاينةٌ افتراضاً، ومعاملةٌ واحدة، وإعادتُه لا تكرّر.**
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.currency import currency_for_country  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.models.enums import AuditAction, CountryCode, SubscriptionDurationType  # noqa: E402
from app.models.subscription import SubscriptionPlan  # noqa: E402
from app.models.subscription_offer import SubscriptionOffer  # noqa: E402
from app.services import audit, money_guards  # noqa: E402

COUNTRY = CountryCode.DZ
MONTHLY = Decimal("6000")
PLANS = (
    (SubscriptionDurationType.DAILY, "TAXO X1 — يومي", MONTHLY / 30),
    (SubscriptionDurationType.WEEKLY, "TAXO X7 — أسبوعي", MONTHLY * 7 / 30),
    (SubscriptionDurationType.MONTHLY, "TAXO X30 — شهري", MONTHLY),
)
OFFER_NAME = "أول أسبوع مجاناً"
REASON = "أمرُ المالك ٢٠٢٦-١٠-١٣ (SPEC §٧٤-ل/٢)"


async def main_async(*, write: bool, session_factory=SessionLocal) -> list[str]:
    lines: list[str] = []
    async with session_factory() as session:
        await money_guards.require_pricing_writes(session, actor=None, country_code=COUNTRY)
        plans = list(await session.scalars(select(SubscriptionPlan).where(SubscriptionPlan.country_code == COUNTRY)))
        weekly_id = None
        touched: set = set()
        for duration, name, price in PLANS:
            price = price.quantize(Decimal("1"))
            assert price % 10 == 0, f"{name}: {price} ليس مضاعفاً لعشرة"
            plan = next((p for p in plans if p.duration_type is duration and p.price == price), None)
            if plan is None:
                plan = SubscriptionPlan(country_code=COUNTRY, name=name, duration_type=duration, price=price,
                                        currency=currency_for_country(COUNTRY), is_active=True)
                session.add(plan)
                await session.flush()
                action, note = AuditAction.CREATE, "تُنشأ مفتوحة"
            else:
                changes = audit.apply_changes(plan, {"name": name, "is_active": True})
                action, note = AuditAction.UPDATE, ("تُسمّى وتُفتح" if changes else "قائمةٌ كما هي")
            await audit.record(session, actor=None, action=action, entity_type="subscription_plan", entity_id=plan.id,
                               details={"country_code": COUNTRY.value, "name": name, "price": str(price), "reason": REASON})
            lines.append(f"{name}: {int(price):,} د.ج — {note}")
            touched.add(plan.id)
            if duration is SubscriptionDurationType.WEEKLY:
                weekly_id = plan.id
        # **ولا خطّةَ أخرى مفتوحةٌ في الجزائر** غيرُ الثلاث (لا شيءَ قبلها اليوم — ويُقال لو وُجد)
        others = [p for p in plans if p.is_active and p.id not in touched]
        for other in others:
            lines.append(f"⚠ خطّةٌ أخرى مفتوحةٌ في الجزائر لم تُمسّ: {other.name}")

        offer = await session.scalar(
            select(SubscriptionOffer).where(SubscriptionOffer.country_code == COUNTRY, SubscriptionOffer.name == OFFER_NAME)
        )
        if offer is None:
            offer = SubscriptionOffer(
                country_code=COUNTRY, name=OFFER_NAME, discount_type="money_percent", discount_value=Decimal("100"),
                plan_id=weekly_id, is_active=True, audience="new_driver", max_uses_per_driver=1,
                commission_percent=Decimal("0"),
            )
            session.add(offer)
            await session.flush()
            await audit.record(session, actor=None, action=AuditAction.CREATE, entity_type="subscription_offer",
                               entity_id=offer.id, details={"country_code": COUNTRY.value, "name": OFFER_NAME, "reason": REASON})
            lines.append(f"«{OFFER_NAME}»: ١٠٠٪ على الأسبوعيّة · للكبتن الجديد مرّةً · عمولةٌ صفر — يُنشأ")
        else:
            lines.append(f"«{OFFER_NAME}»: قائمٌ — لا يُمسّ")
        if write:
            await session.commit()
        else:
            await session.rollback()
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="خططُ اشتراك الجزائر (SPEC §٧٤-ل/٢)")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for line in asyncio.run(main_async(write=args.apply)):
        print(f"  {line}")
    print("✓ كُتب" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
