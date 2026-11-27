"""بندُ «لا استردادَ لاشتراكات البطاقة» في شروط كابتن الأردن (قرارُ المالك ٢٠٢٦-١١-٢٧، `design/OWNER-2026-11-26-FREEMIUS-BACKUP.md`).

    python -m scripts.policies_card_refund_jo            # معاينة — يقرأ ويطبع الخطّة ولا يكتب حرفاً
    python -m scripts.policies_card_refund_jo --apply    # يكتب نسخةً جديدةً وينشرها

**بنصِّ المالك**: «Put the no-refund clause only in the TAXO terms and policies page (captain terms, payments section), in Arabic,
French and English, as a normal clause among the others … No banner, no highlight, no popup.» — **فهو سطرٌ عاديٌّ يُدرج آخرَ بنود القسم
٥ («الدفعُ ومحفظتُك» · «Payment and your wallet» · «Paiement et portefeuille») بكلِّ لغةٍ في الوثيقة**، لا قسمٌ يُلحق ولا عنوانٌ ولا
تمييز. **و`requires_reconsent = False`**: «no popup» — فلا تُفتح شاشةُ إعادة الموافقة لأحد. **ولا سطرَ استردادٍ على شاشة الدفع**: هناك
رابطٌ صغيرٌ إلى هذه الصفحة وحدَه (`driver-app/src/screens/t2/CardPayT2.tsx`).

**والأردنُّ وحدَه**: البطاقةُ الاحتياطيّة (Freemius) وDigistore24 للأردن وحدَه، وشروطُ الجزائر وليبيا لا تُمسّ.

**النصُّ المنشورُ اليومَ هو الأساس** — يُقرأ ويُدرج فيه البندُ ثمّ يُنشر نسخةً برقمٍ أعلى **والسابقةُ مؤرشفةٌ بنصّها** (`create_version`
و`publish` — بابا اللوحة)، **ويقف ولا يكتب** إن لم يجد عنوانَ القسم ٥ في لغةٍ من لغاتها، أو وجد فوق المنشورة مسوّدة. **وidempotent**:
نسخةٌ فيها البندُ لا تُمسّ. **والرجوع**: `policies.withdraw` على الجديدة ثمّ نشرُ السابقة من اللوحة. **ولا مالَ هنا.**

**ويُشغَّل قبل الرفع الذي يبني الموقع** — الموقعُ يخبز النصَّ المنشورَ وقت البناء، والبوّابةُ الخامسةُ تقارن المخبوزَ بالمنشور؛ **وبنصِّه عبر
stdin** إلى حاوية الخلفية القائمة (`python - --apply < scripts/policies_card_refund_jo.py`) فلا يُشترط أن يكون في صورتها.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from types import SimpleNamespace

if "__file__" in globals():  # **وعبر stdin لا ملفَّ له** — والحاويةُ تبدأ من `/app` فالمسارُ فيها أصلاً
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal  # noqa: E402
from app.models.enums import AuditAction, CountryCode, PolicyApp, PolicyDocType  # noqa: E402
from app.services import audit  # noqa: E402
from app.services import policies as policies_service  # noqa: E402

REASON = "قرارُ المالك ٢٠٢٦-١١-٢٧: اشتراكاتُ البطاقة لا تُستردّ بعد الدفع — بندٌ عاديٌّ في القسم ٥ من شروط الكابتن"
COUNTRY = CountryCode.JO
DATE = "2026-11-27"

#: **البندُ بلغاته الثلاث** — والعربيُّ علامتُه: به يُعرف أنه أُدرج
CLAUSE = {
    "ar": "- الاشتراكاتُ المدفوعةُ بالبطاقة المصرفيّة لا تُستردّ بعد الدفع.",
    "en": "- Subscriptions paid by bank card are non-refundable after payment.",
    "fr": "- Les abonnements payés par carte bancaire ne sont pas remboursables après le paiement.",
}
MARKER = CLAUSE["ar"]

#: **عنوانُ القسم ٥ في كلِّ لغة** — كما في نصِّ الشروط المنشور (`scripts/policy_texts_76.py`)
HEADING = {
    "ar": re.compile(r"^5\)\s*الدفع"),
    "en": re.compile(r"^5\)\s*Payment"),
    "fr": re.compile(r"^5\)\s*Paiement"),
}
_NEXT_SECTION = re.compile(r"^\d+\)\s")
_UPDATED = re.compile(r"((?:آخر تحديث|Dernière mise à jour|Last updated)\s*:\s*)\d{4}-\d{2}-\d{2}")


class ClauseRefused(RuntimeError):
    """**يقف ولا يكتب** — والنصُّ يقول ما لم يُوجد."""


def with_clause(body: str | None, lang: str) -> str | None:
    """**البندُ آخرَ بنود القسم ٥** — بعد آخر سطرٍ يبدأ بـ«- » فيه وقبل القسم التالي؛ ولغةٌ بلا نصٍّ تبقى بلا نصّ."""
    if not body:
        return body
    lines = body.split("\n")
    start = next((i for i, line in enumerate(lines) if HEADING[lang].match(line.strip())), None)
    if start is None:
        raise ClauseRefused(f"لا عنوانَ للقسم ٥ في النصّ ({lang}) — لا يُكتب شيء")
    last = start
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        if _NEXT_SECTION.match(stripped):
            break
        if stripped.startswith("- "):
            last = i
    lines.insert(last + 1, CLAUSE[lang])
    out = "\n".join(lines)
    return _UPDATED.sub(lambda m: m.group(1) + DATE, out, count=1)


async def main_async(*, write: bool, session_factory=SessionLocal) -> list[str]:
    label = f"{COUNTRY.value}/driver/terms_of_use"
    async with session_factory() as session:
        live = await policies_service.published(session, country=COUNTRY, doc_type=PolicyDocType.TERMS_OF_USE, app=PolicyApp.DRIVER)
        if live is None:
            raise ClauseRefused(f"{label}: لا نسخةَ منشورة — يقف ولا يكتب")
        if MARKER in live.body_ar:
            return [f"{label}: فيها البندُ أصلاً (v{live.version}) — لا تُمسّ"]
        newest = max((row.version for row in await policies_service.versions(
            session, country=COUNTRY, doc_type=PolicyDocType.TERMS_OF_USE, app=PolicyApp.DRIVER
        )), default=live.version)
        if newest != live.version:
            raise ClauseRefused(f"{label}: فوق المنشورة v{live.version} مسوّدةٌ v{newest} — يقف ولا يكتب فوقها")
        body = {lang: with_clause(text, lang) for lang, text in (("ar", live.body_ar), ("en", live.body_en), ("fr", live.body_fr))}
        policy = await policies_service.create_version(
            session, country=COUNTRY, doc_type=PolicyDocType.TERMS_OF_USE, app=PolicyApp.DRIVER,
            body_ar=body["ar"] or "", body_en=body["en"], body_fr=body["fr"], requires_reconsent=False,
        )
        previous = await policies_service.publish(session, policy, actor=SimpleNamespace(id=None))  # type: ignore[arg-type]
        await audit.record(
            session, actor=None, action=AuditAction.ACTIVATE, entity_type="privacy_policy",  # type: ignore[arg-type]
            entity_id=policy.id,
            details={"country_code": COUNTRY.value, "doc_type": "terms_of_use", "app": "driver", "version": policy.version,
                     "previous_version": previous.version if previous else None, "requires_reconsent": False, "reason": REASON},
        )
        langs = " · ".join(lang for lang, text in body.items() if text)
        lines = [f"{label}: v{policy.version} تُنشر ({langs}) — v{previous.version if previous else '?'} مؤرشفة · بلا إعادة موافقة"]
        lines += [f"  {lang}: {CLAUSE[lang]}" for lang, text in body.items() if text]
        if write:
            await session.commit()
        else:
            await session.rollback()
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="بندُ «لا استرداد» لاشتراكات البطاقة في شروط كابتن الأردن")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        lines = asyncio.run(main_async(write=args.apply))
    except ClauseRefused as exc:
        print(f"✗ {exc}")
        return 1
    for line in lines:
        print(f"  {line}")
    print("✓ نُشرت" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
