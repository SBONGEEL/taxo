"""منحُ عرضٍ لكبتن التجربة وحدَه ثمّ نزعُه — لشراء تجربةٍ بسعر العرض من زرّ صفحة البيع.

**إذنُ المالك ٢٠٢٦-١١-٢٤ السادس، البند ٢** (`design/OWNER-2026-11-24-SIXTH-POINTS-LAUNCH-OFFERS-VIDEOS.md`): «يُعطى عرضُ
TAXO MAN 45 لحساب كبتن التجربة الأردنيّ وحدَه (is_test) بأداة اللوحة مع التدقيق، لهذه التجربة» — ثمّ يُنزع فوراً.

**يُشغَّل على الإنتاج بعد الرفع** في حاوية الخلفية، وملفُّ حسابَي التجربة مركَّبٌ للقراءة وحدَها:

    … run --rm --no-deps -v /home/taxo/secrets/test-accounts.env:/in/test-accounts.env:ro backend \
      python -m scripts.test_captain_offer --test-accounts /in/test-accounts.env --offer "TAXO MAN 45" --grant   # معاينة
    … --grant --apply     ·     … --revoke --apply

* **يجد كبتنَ التجربة برقمه ويقف إن لم يكن موسوماً `is_test`** — فلا يمنح هذا السكربتُ حساباً حقيقيّاً شيئاً بحال، **والبابُ نفسُه**
  (`offers.grant` لجمهورٍ محسوب، و`offers.revoke_test_grant`) يرفض غيرَ حساب التجربة.
* **المنحُ والنزعُ من البابين الحقيقيّين** وقيدُ تدقيقٍ لكلٍّ **بلا فاعل** (إنسانٌ على الخادم بإذن المالك، لا مشرفٌ في اللوحة) والسببُ مكتوب.
* **لا مالَ يُكتب هنا**: المنحةُ تفتح العرضَ في `offers.resolve` لهذا الحساب وحدَه؛ والشراءُ نفسُه من صفحة البيع في وضع تجربة Digistore24.
* **المعاينةُ افتراضٌ** — بلا `--apply` يُطبع ما سيُكتب ثمّ يُتراجع. **ومعاملةٌ واحدة.**
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.models.driver import Driver  # noqa: E402
from app.models.enums import AuditAction, CountryCode  # noqa: E402
from app.models.subscription_offer import SubscriptionOffer  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import audit, offers as offers_service  # noqa: E402

COUNTRY = CountryCode.JO
REASON = "شراءُ تجربةٍ بسعر العرض من زرّ صفحة البيع ثمّ نزعٌ فوراً — إذنُ المالك ٢٠٢٦-١١-٢٤ السادس، البند ٢"


class OfferRefused(RuntimeError):
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
        raise OfferRefused("ملفُّ حسابَي التجربة داخل المستودع — يُقرأ من مجلّد الأسرار وحدَه")
    if not path.is_file():
        raise OfferRefused(f"لا ملفَّ في {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        name, _, value = raw.strip().partition("=")
        if name.strip() == "TAXO_TEST_CAPTAIN_PHONE" and value.strip():
            return value.strip()
    raise OfferRefused("TAXO_TEST_CAPTAIN_PHONE غائبٌ عن الملفّ")


async def _apply(session: AsyncSession, phone: str, offer_name: str, revoke: bool) -> list[str]:
    user = await session.scalar(select(User).where(User.phone == phone))
    if user is None:
        raise OfferRefused("لا حسابَ بهذا الرقم")
    if not user.is_test:
        raise OfferRefused("الحسابُ ليس موسوماً is_test — لا يُمنح شيئاً")
    if user.country_code is not COUNTRY:
        raise OfferRefused("كابتنُ التجربة ليس في الأردن")
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        raise OfferRefused("لا صفَّ كابتنٍ لهذا الحساب")
    offers = (
        await session.execute(
            select(SubscriptionOffer).where(
                SubscriptionOffer.country_code == COUNTRY, SubscriptionOffer.name == offer_name
            )
        )
    ).scalars().all()
    if len(offers) != 1:
        raise OfferRefused(f"عروضٌ بهذا الاسم في الأردن: {len(offers)} — يُطلب واحدٌ بعينه")
    offer = offers[0]
    if revoke:
        grant_id = await offers_service.revoke_test_grant(
            session, offer_id=offer.id, driver_id=driver.id
        )
        await audit.record(
            session,
            actor=None,
            action=AuditAction.DELETE,
            entity_type="subscription_offer_grant",
            entity_id=grant_id,
            details={"driver_id": str(driver.id), "offer_id": str(offer.id), "reason": REASON, "test_account": True},
        )
        return [f"نُزع «{offer.name}» عن كابتن التجربة (is_test)"]
    row = await offers_service.grant(
        session, offer_id=offer.id, driver_id=driver.id, actor_id=None, note=REASON  # type: ignore[arg-type]
    )
    await audit.record(
        session,
        actor=None,
        action=AuditAction.CREATE,
        entity_type="subscription_offer_grant",
        entity_id=row.id,
        details={"driver_id": str(driver.id), "offer_id": str(offer.id), "reason": REASON, "test_account": True},
    )
    return [f"مُنح «{offer.name}» لكابتن التجربة (is_test) وحدَه — جمهورُ العرض «{offer.audience}»"]


async def main_async(
    *, test_accounts: Path, offer: str, revoke: bool, write: bool, session_factory=SessionLocal
) -> Plan:
    phone = _phone(test_accounts)
    async with session_factory() as session:
        lines = await _apply(session, phone, offer, revoke)
        if write:
            await session.commit()
        else:
            await session.rollback()
    return Plan(lines=lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="منحُ عرضٍ لكابتن التجربة وحدَه أو نزعُه")
    parser.add_argument("--test-accounts", required=True, type=Path)
    parser.add_argument("--offer", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--grant", action="store_true")
    action.add_argument("--revoke", action="store_true")
    parser.add_argument("--apply", action="store_true", help="اكتب — وبلاها معاينةٌ تتراجع")
    args = parser.parse_args()
    try:
        plan = asyncio.run(
            main_async(test_accounts=args.test_accounts, offer=args.offer, revoke=args.revoke, write=args.apply)
        )
    except (OfferRefused, Exception) as exc:  # noqa: BLE001 — يُطبع السببُ ولا يُكتب شيء
        print(f"✗ {exc}")
        return 1
    for line in plan.lines:
        print(f"  {line}")
    print("✓ كُتب" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
