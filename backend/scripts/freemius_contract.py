"""عقدُ Freemius للأردن من ملفّ الأسرار (أمرُ المالك ٢٠٢٦-١١-٢٦ و٢٧، SPEC §١٢٢) — **المفاتيحُ لا تمرّ بمحادثةٍ ولا بلوحةٍ ولا بسجلّ**.

**يُشغَّل على الإنتاج بعد الرفع**، في حاوية الخلفية، **وملفّا الأسرار مركَّبان للقراءة وحدَها** — والأمرُ يذكر ملفاتِه كلَّها:

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps -v /home/taxo/secrets/freemius.env:/in/freemius.env:ro \\
      -v /home/taxo/secrets/test-accounts.env:/in/test-accounts.env:ro backend \\
      python -m scripts.freemius_contract --secrets-file /in/freemius.env --test-accounts /in/test-accounts.env   # معاينة
    … --apply                                                                                                     # الكتابة

## ما يفعله

* **يقرأ من ملفّ الأسرار** (كما يكتبه `scripts/freemius_plans.py`): `product_id` · `public_key` (`pk_…`) · `secret_key` (`sk_…`) ·
  `api_token` · ومعرّفاتِ الخطط (`plan_daily` · `plan_weekly` · `plan_monthly` · `plan_monthly_full`، أرقامٌ وحدَها) · و`test_mode` (1 أو 0)
  — **ويقف إن غاب شيءٌ أو خالف شكلَه، ولا يطبع منه حرفاً** إلّا معرّفَ المنتج والخطط (ليست أسراراً: تظهر في رابط صفحة الدفع).
* **وفي وضع التجربة يحصر العقدَ في كبتن التجربة** (`allowlist` = `TAXO_TEST_CAPTAIN_PHONE`) — **ولا عقدَ تجريبيَّ بلا قائمة سماح**،
  ووضعُ التجربة يُعرض لحسابات التجربة وحدَها أصلاً (`is_test`). **وفي الوضع الحيّ تُفرَّغ القائمة** إلّا إن طُلب إبقاؤها.
* **يكتب عقدَ «Freemius» للأردن مفعَّلاً** ببابه القائم (`credentials.upsert`) — مشفَّراً، **وسطرُ التدقيق بأسماء الحقول وحدَها**.
* **ولا يغيّر «بوابة الدفع بالبطاقة»**: مفتاحا Digistore24 وFreemius يُقرآن ويُقالان — اختيارُ البوّابة من اللوحة أو من بابها المدقَّق.

## وحرّاسُه

* **المعاينةُ افتراضٌ** — بلا `--apply` يُطبع ما سيُكتب ثمّ يُتراجع. **ومعاملةٌ واحدة.** **وبلا فاعل** (لا مشرفَ قرّر في اللوحة).
* **ملفّا الأسرار لا يُقرآن من المستودع** — مسارٌ داخل الشجرة يُرفض.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.models.enums import CountryCode, FeatureKey, ProviderKey  # noqa: E402
from app.models.payment_request import PayMethod  # noqa: E402
from app.services import settings_service  # noqa: E402
from app.services.providers import credentials as credentials_service  # noqa: E402

COUNTRY = CountryCode.JO
METHOD_CODE = "freemius_card"
PLANS = ("plan_daily", "plan_weekly", "plan_monthly", "plan_monthly_full")
_ID = re.compile(r"^\d{2,12}$")
_PHONE = re.compile(r"^\+\d{8,15}$")
_KEYS = (("public_key", "pk_", 20), ("secret_key", "sk_", 20), ("api_token", "", 20))


class ContractRefused(RuntimeError):
    """**يقف ولا يكتب** — والنصُّ يسمّي ما غاب أو ما خالف، ولا يحمل قيمةً سرّيّةً من الملفّ."""


@dataclass(frozen=True, slots=True)
class Plan:
    mode: str
    lines: list[str]


def _read_env(path: Path) -> dict[str, str]:
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
    return values


def _contract_values(secrets: dict[str, str], test_phone: str | None, *, keep_allowlist: bool) -> tuple[str, dict[str, object]]:
    flag = secrets.get("test_mode", "").strip().lower()
    if flag not in ("1", "0", "true", "false"):
        raise ContractRefused("test_mode غائبٌ أو ليس 1 ولا 0")
    mode = "test" if flag in ("1", "true") else "live"
    product = secrets.get("product_id", "")
    if not _ID.match(product):
        raise ContractRefused("product_id غائبٌ أو ليس أرقاماً")
    values: dict[str, object] = {"test_mode": mode == "test", "product_id": product}
    for field, prefix, minimum in _KEYS:
        value = secrets.get(field, "")
        if len(value) < minimum or not value.startswith(prefix):
            raise ContractRefused(f"{field} غائبٌ أو خالف شكلَه")
        values[field] = value
    found = 0
    for field in PLANS:
        plan_id = secrets.get(field, "")
        if not plan_id:
            continue
        if not _ID.match(plan_id):
            raise ContractRefused(f"{field} ليس معرّفَ خطّة (أرقامٌ وحدَها)")
        values[field] = plan_id
        found += 1
    if not found:
        raise ContractRefused("لا معرّفَ خطّةٍ في الملفّ — يكفي واحد، ويُعرض زرُّ خطّته وحدَها")
    if mode == "test":
        if not test_phone or not _PHONE.match(test_phone):
            raise ContractRefused("وضعُ التجربة بلا هاتف كابتن التجربة (TAXO_TEST_CAPTAIN_PHONE) — لا عقدَ تجريبيَّ بلا قائمة سماح")
        values["allowlist"] = test_phone
    elif not keep_allowlist:
        values["allowlist"] = ""
    return mode, values


async def _apply(session: AsyncSession, *, mode: str, values: dict[str, object]) -> list[str]:
    lines: list[str] = []
    method = await session.scalar(
        select(PayMethod).where(PayMethod.country_code == COUNTRY, PayMethod.code == METHOD_CODE)
    )
    if method is None:
        raise ContractRefused(f"لا صفَّ طريقةٍ «{METHOD_CODE}» للأردن — ترحيلةُ 0194 لم تُشغَّل")
    current = await credentials_service.get_credential(session, ProviderKey.FREEMIUS, COUNTRY)
    exists = current is not None and current.country_code == COUNTRY
    lines.append(f"العقد: {'يُحدَّث' if exists else 'يُنشأ'} — الوضع: {mode} · مفعَّل · المنتج {values['product_id']}")
    plans = " · ".join(f"{field.removeprefix('plan_')}={values[field]}" for field in PLANS if field in values)
    lines.append(f"الخطط: {plans}")
    allow = str(values.get("allowlist", "—"))
    lines.append("قائمةُ السماح: " + ("كابتنُ التجربة وحدَه" if mode == "test" else ("فارغة — للجميع" if allow == "" else "تبقى كما هي")))
    await credentials_service.upsert(
        session,
        provider_key=ProviderKey.FREEMIUS,
        country_code=COUNTRY,
        values=values,
        is_active=True,
        actor=None,
    )
    lines.append(f"الطريقة «{method.name}»: {'مفعَّلة' if method.enabled else 'معطَّلة'} — لا يغيّرها هذا السكربت")
    for key, label in (
        (FeatureKey.DIGISTORE24_CARD_ENABLED, "مفتاحُ Digistore24"),
        (FeatureKey.FREEMIUS_CARD_ENABLED, "مفتاحُ Freemius"),
    ):
        on = await settings_service.is_feature_enabled(session, COUNTRY, key)
        lines.append(f"{label} في الأردن: {'مشتعل' if on else 'مطفأ'} — لا يغيّره هذا السكربت")
    return lines


async def main_async(
    *,
    secrets_file: Path,
    test_accounts: Path | None,
    write: bool,
    keep_allowlist: bool = False,
    session_factory=SessionLocal,
) -> Plan:
    secrets = _read_env(secrets_file)
    phone = _read_env(test_accounts).get("TAXO_TEST_CAPTAIN_PHONE") if test_accounts is not None else None
    mode, values = _contract_values(secrets, phone, keep_allowlist=keep_allowlist)
    async with session_factory() as session:
        lines = await _apply(session, mode=mode, values=values)
        if write:
            await session.commit()
        else:
            await session.rollback()
    return Plan(mode=mode, lines=lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="عقدُ Freemius للأردن من ملفّ الأسرار")
    parser.add_argument("--secrets-file", required=True, type=Path)
    parser.add_argument("--test-accounts", type=Path, help="ملفُّ حسابَي التجربة — يُشترط في وضع التجربة")
    parser.add_argument("--keep-allowlist", action="store_true", help="في الوضع الحيّ: أبقِ قائمةَ السماح كما هي")
    parser.add_argument("--apply", action="store_true", help="اكتب — وبلاها معاينةٌ تتراجع")
    args = parser.parse_args()
    try:
        plan = asyncio.run(
            main_async(
                secrets_file=args.secrets_file,
                test_accounts=args.test_accounts,
                write=args.apply,
                keep_allowlist=args.keep_allowlist,
            )
        )
    except ContractRefused as exc:
        print(f"✗ {exc}")
        return 1
    for line in plan.lines:
        print(f"  {line}")
    print("✓ كُتب" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
