"""عقدُ Digistore24 للأردن من ملفّ الأسرار (أمرُ المالك ٢٠٢٦-١١-٢٣، SPEC §١١٣) — **المفتاحُ والعبارةُ لا يمرّان بمحادثةٍ ولا بلوحةٍ ولا بسجلّ**.

**يُشغَّل على الإنتاج بعد الرفع**، في حاوية الخلفية، **وملفّا الأسرار مركَّبان للقراءة وحدَها** — والأمرُ يذكر ملفاتِه كلَّها:

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps -v /home/taxo/secrets/digistore24.env:/in/ds24.env:ro \\
      -v /home/taxo/secrets/test-accounts.env:/in/test-accounts.env:ro backend \\
      python -m scripts.digistore24_contract --secrets-file /in/ds24.env --test-accounts /in/test-accounts.env   # معاينة
    … --apply                                                                                                     # الكتابة

## ما يفعله

* **يقرأ من ملفّ الأسرار**: `DS24_MODE` (`test` أو `live`) · `DS24_API_KEY` · `DS24_IPN_PASSPHRASE` · ومعرّفاتِ المنتجات الثلاثة
  (`DS24_PRODUCT_DAILY` · `DS24_PRODUCT_WEEKLY` · `DS24_PRODUCT_MONTHLY`، أرقامٌ بلا غيرها) — **ويقف إن غاب شيءٌ أو خالف شكلَه**،
  **ولا يطبع منه حرفاً** إلّا معرّفاتِ المنتجات (ليست أسراراً: تظهر في رابط صفحة الدفع).
* **وفي وضع التجربة يحصر العقدَ في كبتن التجربة** (`allowlist` = `TAXO_TEST_CAPTAIN_PHONE` من ملفّ حسابَي التجربة) — **ولا يُكتب عقدٌ تجريبيٌّ
  بلا قائمة سماح**: طريقةٌ تُعرض لكبتنٍ حقيقيٍّ في وضع التجربة تَعِده بدفعٍ لا يقع. **وفي الوضع الحيّ تُفرَّغ القائمة** إلّا إن طُلب إبقاؤها.
* **يكتب عقدَ «Digistore24» للأردن مفعَّلاً** ببابه القائم (`credentials.upsert`) — مشفَّراً، **وسطرُ التدقيق بأسماء الحقول وحدَها**.
* **ولا يشعل مفتاحاً**: مفتاحا الطريقة (الموقع · Play) يُقرآن ويُقالان — إشعالُهما قرارٌ يُكتب في التقرير لا أثرٌ جانبيّ. **وصفُّ الطريقة**
  (`digistore24_card`، ترحيلة `0188`) يُقرأ ولا يُنشأ هنا: غيابُه يوقف.

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
METHOD_CODE = "digistore24_card"
PRODUCTS = {"product_daily": "DS24_PRODUCT_DAILY", "product_weekly": "DS24_PRODUCT_WEEKLY", "product_monthly": "DS24_PRODUCT_MONTHLY"}
_PRODUCT_ID = re.compile(r"^\d{3,12}$")
_PHONE = re.compile(r"^\+\d{8,15}$")


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
    mode = secrets.get("DS24_MODE", "").lower()
    if mode not in ("test", "live"):
        raise ContractRefused("DS24_MODE غائبٌ أو ليس test ولا live")
    values: dict[str, object] = {"test_mode": mode == "test"}
    for field, name in (("api_key", "DS24_API_KEY"), ("ipn_passphrase", "DS24_IPN_PASSPHRASE")):
        if len(secrets.get(name, "")) < 16:
            raise ContractRefused(f"{name} غائبٌ أو أقصرُ من شكله")
        values[field] = secrets[name]
    found = 0
    for field, name in PRODUCTS.items():
        product = secrets.get(name, "")
        if not product:
            continue
        if not _PRODUCT_ID.match(product):
            raise ContractRefused(f"{name} ليس معرّفَ منتجٍ (أرقامٌ وحدَها)")
        values[field] = product
        found += 1
    if not found:
        raise ContractRefused("لا معرّفَ منتجٍ في الملفّ — يكفي واحد، ويُعرض زرُّ خطّته وحدَها")
    if mode == "test":
        if not test_phone or not _PHONE.match(test_phone):
            raise ContractRefused("وضعُ التجربة بلا هاتف كبتن التجربة (TAXO_TEST_CAPTAIN_PHONE) — لا عقدَ تجريبيَّ بلا قائمة سماح")
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
        raise ContractRefused(f"لا صفَّ طريقةٍ «{METHOD_CODE}» للأردن — ترحيلةُ 0188 لم تُشغَّل")
    current = await credentials_service.get_credential(session, ProviderKey.DIGISTORE24, COUNTRY)
    exists = current is not None and current.country_code == COUNTRY
    lines.append(f"العقد: {'يُحدَّث' if exists else 'يُنشأ'} — الوضع: {mode} · مفعَّل")
    products = " · ".join(f"{field.removeprefix('product_')}={values[field]}" for field in PRODUCTS if field in values)
    lines.append(f"المنتجات: {products}")
    allow = str(values.get("allowlist", "—"))
    lines.append("قائمةُ السماح: " + ("كبتنُ التجربة وحدَه" if mode == "test" else ("فارغة — للجميع" if allow == "" else "تبقى كما هي")))
    await credentials_service.upsert(
        session,
        provider_key=ProviderKey.DIGISTORE24,
        country_code=COUNTRY,
        values=values,
        is_active=True,
        actor=None,
    )
    lines.append(f"الطريقة «{method.name}»: {'مفعَّلة' if method.enabled else 'معطَّلة'} — لا يغيّرها هذا السكربت")
    for key, label in (
        (FeatureKey.DIGISTORE24_CARD_ENABLED, "مفتاحُ الموقع"),
        (FeatureKey.DIGISTORE24_CARD_PLAY_ENABLED, "مفتاحُ Play"),
    ):
        on = await settings_service.is_feature_enabled(session, COUNTRY, key)
        lines.append(f"{label} في الأردن: {'مشتعل' if on else 'مطفأ'} — لا يشعله هذا السكربت")
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
    parser = argparse.ArgumentParser(description="عقدُ Digistore24 للأردن من ملفّ الأسرار")
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
