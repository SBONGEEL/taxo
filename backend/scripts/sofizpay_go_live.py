"""SofizPay حيّاً في الجزائر (SPEC §٨٥/٦، `design/SOFIZPAY-GO-LIVE.md`، أمرُ المالك ٢٠٢٦-١٠-٢٩ «Go live now»).

    python -m scripts.sofizpay_go_live                 # معاينة — يقرأ ويطبع ولا يكتب
    python -m scripts.sofizpay_go_live --pilot         # حيٌّ لقائمة السماح: حسابُ المالك الحقيقيّ في الجزائر وحدَه
    python -m scripts.sofizpay_go_live --open-all      # بعد دفعة المالك الناجحة: تُفرَّغ القائمة ⇐ لكلّ الجزائر

**ما يكتبه**: عقدُ SofizPay الجزائريّ — `sandbox` **مطفأ** و`allowlist` و**مفعَّل** — وطريقةُ `sofizpay` مفعَّلةً للشحن والاشتراك. **ولا يمسّ
`account`** (المفتاحُ العامّ أدخله المالكُ من اللوحة) إلا ليتحقّق أنه مفتاحُ Stellar عامٌّ (`G…` بستّةٍ وخمسين حرفاً). **ولا مفتاحَ سرّيّ**:
لا حقلَ له في العقد أصلاً. **وChargily لا يُمسّ** (يبقى مخفيّاً).

**ورقمُ المالك من القاعدة لا من اليد**: صاحبُ إذن الحدود الوحيدُ في الجزائر الذي ليس حسابَ تجربة (`provision_owner_account_74`) — **ولا
يُطبع إلا مقنَّعاً**. **وكلُّ كتابةٍ سطرٌ في التدقيق.** **والرجوع**: إطفاءُ العقد من صفحة العقود.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402
from app.models.enums import AuditAction, CountryCode, PaymentProviderKind, ProviderKey  # noqa: E402
from app.models.market import BorderAllowance  # noqa: E402
from app.models.payment_request import PayMethod  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import audit  # noqa: E402
from app.services.providers import credentials as credentials_service  # noqa: E402

COUNTRY = CountryCode.DZ
METHOD_CODE = "sofizpay"
METHOD_NAME = "بطاقة الذهبية أو CIB (SofizPay)"


def _mask(phone: str) -> str:
    return phone[:4] + "…" + phone[-3:]


async def main(mode: str) -> None:
    async with SessionLocal() as session:
        values = await credentials_service.get_values(session, ProviderKey.SOFIZPAY, COUNTRY, active_only=False)
        if values is None:
            raise SystemExit("✗ لا عقدَ SofizPay للجزائر — يُدخل المالكُ المفتاحَ العامّ من صفحة العقود أوّلاً")
        account = str(values.get("account") or "")
        if not (account.startswith("G") and len(account) == 56):
            raise SystemExit("✗ حسابُ العقد ليس مفتاحَ Stellar عامّاً — يقف")
        owners = (await session.scalars(
            select(User).join(BorderAllowance, BorderAllowance.user_id == User.id)
            .where(User.country_code == COUNTRY, User.is_test.is_(False))
        )).all()
        if len(owners) != 1 or not owners[0].phone:
            raise SystemExit(f"✗ حسابُ المالك الحقيقيّ في الجزائر ليس واحداً ({len(owners)}) — يقف")
        owner = owners[0]
        allow = "" if mode == "open-all" else owner.phone
        print(f"  العقد: الحساب {account[:6]}…{account[-5:]} · sandbox الآن {credentials_service.is_on(values, 'sandbox')} ⇒ False")
        print(f"         allowlist ⇒ {'فارغة (كلُّ الجزائر)' if not allow else _mask(allow) + ' (حسابُ المالك)'} · مفعَّل")
        print(f"         بريدُ حساب المالك: {'موجود' if owner.email else '**غائب** — SofizPay يشترطه: يُضاف من اللوحة'}")
        method = await session.scalar(select(PayMethod).where(PayMethod.country_code == COUNTRY, PayMethod.integration == METHOD_CODE))
        print(f"  الطريقة: {'قائمة' if method else 'تُنشأ'} «{METHOD_NAME}» · شحنٌ واشتراك · الرسومُ على TAXO")
        if mode == "preview":
            await session.rollback()
            print("\n  ⇒ معاينة — لم يُكتب حرف")
            await engine.dispose()
            return
        await credentials_service.upsert(
            session, provider_key=ProviderKey.SOFIZPAY, country_code=COUNTRY,
            values={"sandbox": False, "allowlist": allow}, is_active=True, actor=None,
        )
        if method is None:
            method = PayMethod(
                country_code=COUNTRY, kind=PaymentProviderKind.BANK_TRANSFER, code=METHOD_CODE, name=METHOD_NAME,
                integration=METHOD_CODE, enabled=True, for_topup=True, for_subscription=True, fee_bearer="taxo", sort_order=0,
            )
            session.add(method)
            await session.flush()
            action = AuditAction.CREATE
        else:
            audit.apply_changes(method, {"enabled": True, "for_topup": True, "for_subscription": True})
            action = AuditAction.UPDATE
        # **SofizPay أوّلاً** (أمرُ المالك ٢٠٢٦-١٠-٢٩): ثمّ BaridiMob ثمّ الكاشُ حيث يُسمح — قبل كلِّ طريقةٍ أخرى في السوق
        others = (await session.scalars(
            select(PayMethod.sort_order).where(PayMethod.country_code == COUNTRY, PayMethod.id != method.id)
        )).all()
        method.sort_order = min(others, default=1) - 1
        await audit.record(
            session, actor=None, action=action, entity_type="payment_provider", entity_id=method.id,
            details={"script": "sofizpay_go_live", "mode": mode, "integration": METHOD_CODE, "country_code": COUNTRY.value,
                     "reason": "أمرُ المالك ٢٠٢٦-١٠-٢٩ «Go live now» — SPEC §٨٥/٦"},
        )
        await session.commit()
        print(f"\n  ⇒ كُتب: العقدُ حيٌّ مفعَّل ({'لكلّ الجزائر' if not allow else 'لقائمة السماح'}) والطريقةُ مفعَّلة")
    await engine.dispose()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group()
    g.add_argument("--pilot", action="store_true")
    g.add_argument("--open-all", action="store_true")
    a = p.parse_args()
    asyncio.run(main("pilot" if a.pilot else "open-all" if a.open_all else "preview"))
