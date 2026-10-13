"""عقدُ Chargily للجزائر من ملفّ الأسرار (SPEC §٧٤-ط/٥، §٧٤-ي/١) — **المفتاحُ لا يمرّ بمحادثةٍ ولا بلوحةٍ ولا بسجلّ**.

**يُشغَّل على الإنتاج بعد الرفع**، في حاوية الخلفية، **وملفُّ الأسرار مركَّبٌ للقراءة وحدَها** — والأمرُ يذكر ملفاتِه كلَّها:

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps -v /home/taxo/secrets/chargily.env:/in/chargily.env:ro backend \\
      python -m scripts.chargily_contract_74 --secrets-file /in/chargily.env            # معاينةٌ لا تكتب
    … --apply                                                                            # الكتابة

## ما يفعله

* **يقرأ الوضعَ ومفتاحَه** من الملفّ: `CHARGILY_MODE` (`test` أو `live`) والمفتاحُ السرّيُّ لذلك الوضع
  (`CHARGILY_TEST_SECRET_KEY` · `CHARGILY_LIVE_SECRET_KEY`) — **ويقف إن غاب أو لم يكن بشكل وضعه** (`test_sk_` · `live_sk_`)،
  **ولا يطبع منه حرفاً**: يقول اسمَ ما غاب لا قيمتَه.
* **يكتب عقدَ «Chargily Pay» للجزائر مفعَّلاً** ببابه القائم (`credentials.upsert`) — مشفَّراً، **وسطرُ التدقيق بأسماء الحقول وحدَها**،
  ووضعُ التجربة مشتعلٌ أو مطفأٌ بالوضع. **والمفتاحُ العامّ لا يُكتب**: الدفعُ كلُّه من الخادم، ولا شيءَ في التطبيق يحتاجه.
* **ويضمن طريقةَ «البطاقة الذهبية وCIB»** في نظام الدفع الجزائريّ: وسيطُها Chargily، **للشحن والاشتراك وحدَهما** (أمرُ المالك §٧٤-ط/٤)،
  مفعَّلة، **والرسومُ على TAXO** حتى يقرّر المالكُ غيرَه (`design/APPROVALS-74.md`).
* **ولا يفتح سوقاً ولا يشعل مفتاحاً**: «نظامُ الدفع» في الجزائر يُقرأ ويُقال — إشعالُه قرارٌ يُكتب في التقرير لا أثرٌ جانبيّ.

## وحرّاسُه

* **المعاينةُ افتراضٌ** — بلا `--apply` يُطبع ما سيُكتب ثمّ يُتراجع. **ومعاملةٌ واحدة.** **وبلا فاعل** (لا مشرفَ قرّر في اللوحة).
* **ملفُّ الأسرار لا يُقرأ من المستودع** — مسارٌ داخل الشجرة يُرفض.
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
from app.models.enums import AuditAction, CountryCode, FeatureKey, PaymentProviderKind, ProviderKey  # noqa: E402
from app.models.payment_request import PayMethod  # noqa: E402
from app.services import audit, payment_requests, settings_service  # noqa: E402
from app.services.providers import credentials as credentials_service  # noqa: E402

COUNTRY = CountryCode.DZ
METHOD_CODE = "chargily"
METHOD_NAME = "البطاقة الذهبية وCIB"
PREFIX = {"test": "test_sk_", "live": "live_sk_"}
KEY_NAME = {"test": "CHARGILY_TEST_SECRET_KEY", "live": "CHARGILY_LIVE_SECRET_KEY"}


class ContractRefused(RuntimeError):
    """**يقف ولا يكتب** — والنصُّ يسمّي ما غاب أو ما خالف، ولا يحمل قيمةً من الملفّ."""


@dataclass(frozen=True, slots=True)
class Plan:
    mode: str
    lines: list[str]


def _read_secrets(path: Path) -> tuple[str, str]:
    # **شجرةُ الخلفية** — وفي الحاوية هي `/app` (فالجذرُ فوقها `/` لا يصلح حدّاً)
    repo = Path(__file__).resolve().parents[1]
    try:
        path.resolve().relative_to(repo)
    except ValueError:
        pass
    else:
        raise ContractRefused("ملفُّ الأسرار داخل المستودع — يُقرأ من مجلّد الأسرار وحدَه")
    if not path.is_file():
        raise ContractRefused(f"لا ملفَّ أسرارٍ في {path}")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip('"').strip("'")
    mode = values.get("CHARGILY_MODE", "").lower()
    if mode not in PREFIX:
        raise ContractRefused("CHARGILY_MODE غائبٌ أو ليس test ولا live")
    key = values.get(KEY_NAME[mode], "")
    if not key:
        raise ContractRefused(f"{KEY_NAME[mode]} غائبٌ عن الملفّ")
    if not key.startswith(PREFIX[mode]):
        raise ContractRefused(f"{KEY_NAME[mode]} ليس بشكل مفتاح وضع {mode}")
    return mode, key


async def _apply(session: AsyncSession, *, mode: str, key: str) -> list[str]:
    lines: list[str] = []
    current = await credentials_service.get_credential(session, ProviderKey.CHARGILY, COUNTRY)
    lines.append(f"العقد: {'يُحدَّث' if current is not None and current.country_code == COUNTRY else 'يُنشأ'} — الوضع: {mode} · مفعَّل")
    await credentials_service.upsert(
        session,
        provider_key=ProviderKey.CHARGILY,
        country_code=COUNTRY,
        values={"secret_key": key, "test_mode": mode == "test"},
        is_active=True,
        actor=None,
    )

    method = await session.scalar(
        select(PayMethod).where(PayMethod.country_code == COUNTRY, PayMethod.integration == METHOD_CODE)
    )
    if method is None:
        method = PayMethod(
            country_code=COUNTRY,
            kind=PaymentProviderKind.BANK_TRANSFER,
            code=METHOD_CODE,
            name=METHOD_NAME,
            integration=METHOD_CODE,
            enabled=True,
            for_topup=True,
            for_subscription=True,
            fee_bearer="taxo",
            sort_order=0,
        )
        session.add(method)
        await session.flush()
        action = AuditAction.CREATE
        lines.append(f"الطريقة «{METHOD_NAME}»: تُنشأ مفعَّلةً — شحنٌ واشتراك، والرسومُ على TAXO")
    else:
        changes = audit.apply_changes(method, {"enabled": True, "for_topup": True, "for_subscription": True})
        action = AuditAction.UPDATE
        lines.append(f"الطريقة «{method.name}»: قائمة — {'تُفعَّل للشحن والاشتراك' if changes else 'كما هي'}")
    await audit.record(
        session,
        actor=None,
        action=action,
        entity_type="payment_provider",
        entity_id=method.id,
        details={"script": "chargily_contract_74", "integration": METHOD_CODE, "country_code": COUNTRY.value},
    )

    enabled = await settings_service.is_feature_enabled(session, COUNTRY, FeatureKey.PAYMENT_REQUESTS_ENABLED)
    lines.append(f"«نظام الدفع» في الجزائر: {'مشتعل' if enabled else 'مطفأ — لا تُعرض طريقةٌ حتى يُشعَل (لا يشعله هذا السكربت)'}")
    choices = await payment_requests.topup_choices(session, COUNTRY)
    lines.append("خياراتُ الشحن: " + (" · ".join(str(int(c)) for c in choices) if choices else "لا خيارات"))
    return lines


async def main_async(*, secrets_file: Path, write: bool, session_factory=SessionLocal) -> Plan:
    mode, key = _read_secrets(secrets_file)
    async with session_factory() as session:
        lines = await _apply(session, mode=mode, key=key)
        if write:
            await session.commit()
        else:
            await session.rollback()
    return Plan(mode=mode, lines=lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="عقدُ Chargily للجزائر من ملفّ الأسرار (SPEC §٧٤-ي/١)")
    parser.add_argument("--secrets-file", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="اكتب — وبلاها معاينةٌ تتراجع")
    args = parser.parse_args()
    try:
        plan = asyncio.run(main_async(secrets_file=args.secrets_file, write=args.apply))
    except ContractRefused as exc:
        print(f"✗ {exc}")
        return 1
    for line in plan.lines:
        print(f"  {line}")
    print("✓ كُتب" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
