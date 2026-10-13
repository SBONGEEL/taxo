"""مفاتيحُ الدفع في الجزائر بأمر المالك (SPEC §٧٤-ط/٤) — **المحفظةُ و«نظامُ الدفع» وطريقةُ بطاقات TAXO، والجزائرُ مغلقةٌ للعموم**.

**يُشغَّل على الإنتاج بعد الرفع** في حاوية الخلفية (معاينةٌ افتراضاً، و`--apply` للكتابة):

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps backend python -m scripts.algeria_switches_74 [--apply]

* **`wallet_enabled` و`payment_requests_enabled` للجزائر** — الراكبُ يدفع الرحلةَ نقداً أو من محفظته، والمحفظةُ تُشحن بالبطاقة (Chargily)
  وبطاقاتِ TAXO والتحويلِ بإيصال. **والبطاقةُ للرحلة (`card_enabled`) تبقى مطفأة** — تُقرأ وتُقال ولا تُمسّ.
* **طريقةُ «بطاقة TAXO»** (رمزُ شراء) للشحن وحدَه. **والتحويلُ بإيصال والنقدُ في المكتب لا يُنشآن**: الأوّلُ يحتاج رقمَ حسابٍ والثاني عنوانَ
  مكتب — **والاثنان عند المالك** (`design/APPROVALS-74.md`)؛ وطريقةُ تحويلٍ بلا وجهةٍ لا تُفعَّل أصلاً (بابُ اللوحة يردّها).
* **ولا يُفتح سوقٌ ولا يُمسّ الأردنُ وليبيا** (أمرُ المالك: «Jordan and Libya keep their current payment behaviour»).
* **وكلُّ مفتاحٍ سطرٌ في التدقيق بسببه** (`settings_service.set_flag`)، **بلا فاعل** — لا مشرفَ قرّر في اللوحة.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.models.enums import AuditAction, CountryCode, FeatureKey, PaymentProviderKind  # noqa: E402
from app.models.payment_request import PayMethod  # noqa: E402
from app.services import audit, settings_service  # noqa: E402

COUNTRY = CountryCode.DZ
REASON = "أمرُ المالك §٧٤-ط/٤: الرحلةُ نقداً أو من المحفظة، والبطاقةُ للشحن والاشتراك — والجزائرُ مغلقةٌ للعموم"
SWITCHED_ON = (FeatureKey.WALLET_ENABLED, FeatureKey.PAYMENT_REQUESTS_ENABLED)
CARD_CODE = "taxo_card"
CARD_NAME = "بطاقة TAXO"


async def main_async(*, write: bool, session_factory=SessionLocal) -> list[str]:
    lines: list[str] = []
    async with session_factory() as session:
        for key in SWITCHED_ON:
            before = await settings_service.is_feature_enabled(session, COUNTRY, key)
            await settings_service.set_flag(session, country_code=COUNTRY, feature_key=key, enabled=True, actor=None, reason=REASON)
            lines.append(f"{key.value}: {'مشتعلٌ كما كان' if before else 'يُشعَل'}")
        card = await settings_service.is_feature_enabled(session, COUNTRY, FeatureKey.CARD_ENABLED)
        lines.append(f"card_enabled (البطاقةُ للرحلة): {'⚠ مشتعل — لا يُمسّ هنا ويُقال' if card else 'مطفأ كما يجب'}")

        method = await session.scalar(
            select(PayMethod).where(PayMethod.country_code == COUNTRY, PayMethod.kind == PaymentProviderKind.PURCHASE_CODE)
        )
        if method is None:
            method = PayMethod(
                country_code=COUNTRY, kind=PaymentProviderKind.PURCHASE_CODE, code=CARD_CODE, name=CARD_NAME,
                enabled=True, for_topup=True, for_subscription=False, sort_order=1,
            )
            session.add(method)
            await session.flush()
            await audit.record(
                session, actor=None, action=AuditAction.CREATE, entity_type="payment_provider", entity_id=method.id,
                details={"script": "algeria_switches_74", "kind": "purchase_code", "country_code": COUNTRY.value},
            )
            lines.append(f"الطريقة «{CARD_NAME}»: تُنشأ مفعَّلةً للشحن وحدَه")
        else:
            lines.append(f"الطريقة «{method.name}»: قائمة — {'مفعَّلة' if method.enabled else 'موقوفة (لا تُمسّ)'}")
        if write:
            await session.commit()
        else:
            await session.rollback()
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="مفاتيحُ الدفع في الجزائر (SPEC §٧٤-ط/٤)")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for line in asyncio.run(main_async(write=args.apply)):
        print(f"  {line}")
    print("✓ كُتب" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
