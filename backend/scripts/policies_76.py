"""نشرُ السياسات والشروط الكاملة لمراجعة Google Play (SPEC §٧٦/٣، أمرُ المالك ٢٠٢٦-١٠-١٤) — **لكلِّ سوقٍ ولغة، نسخةً جديدةً تُنشر**.

    python -m scripts.policies_76            # معاينة — يقرأ ويطبع الخطّة ولا يكتب حرفاً
    python -m scripts.policies_76 --apply    # يكتب النسخَ الجديدة وينشرها

**أمرُ المالك بلفظه**: «Publish as a new version, keep old versions archived». **فالنسخةُ الجديدة صفٌّ جديدٌ برقمٍ أعلى** (§34: لا يُحرَّر
صفٌّ فوق نفسه) عبر `policies.create_version` و`policies.publish` — **بابا اللوحة نفسُهما** — **والسابقةُ تبقى في الجدول مؤرشفةً** بنصّها
ورقمها وتاريخ نشرها، ومعها موافقاتُ من وافق عليها.

**النصوصُ من `policy_texts_76.py`**: العربيّةُ لكلِّ سوق، **والفرنسيّةُ للجزائر**، **والإنجليزيّةُ للثلاث** (`body_en` — لمراجعي Google
وصفحاتها على الموقع). **و`requires_reconsent = True`** (قراري): هذه إعادةُ كتابةٍ كاملةٌ لا تصحيحُ فاصلة — فيُسأل كلُّ مستعمِلٍ القبولَ من
جديد كما يُسأل عند كلِّ نسخةٍ تغيّر ما وافق عليه.

**وidempotent**: وثيقةٌ منشورةٌ بالنصوص نفسِها لا تُمسّ. **والرجوع**: `policies.withdraw` على الجديدة يعيد السوقَ بلا وثيقة — **والسابقةُ تُنشر
ثانيةً من اللوحة** بنصّها كما كان.

**ولا مالَ هنا** — جدولُ الوثائق وحده، وبصمةُ المال تُؤخذ قبله وبعده كأيِّ كتابةٍ على الإنتاج.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal  # noqa: E402
from app.models.enums import AuditAction, CountryCode, PolicyApp, PolicyDocType  # noqa: E402
from app.services import audit  # noqa: E402
from app.services import policies as policies_service  # noqa: E402
from scripts import policy_texts_76 as texts  # noqa: E402

DATE = "2026-10-14"
REASON = "SPEC §٧٦/٣ — السياساتُ والشروطُ الكاملةُ لمراجعة Google Play"

#: **الأسواقُ الثلاثة ولغاتُها** — الفرنسيّةُ للجزائر وحدَها (تتبع لغةَ الهاتف هناك)
MARKETS: dict[CountryCode, tuple[str, ...]] = {
    CountryCode.JO: ("ar", "en"),
    CountryCode.LY: ("ar", "en"),
    CountryCode.DZ: ("ar", "en", "fr"),
}
DOCS = (
    (PolicyDocType.PRIVACY_POLICY, PolicyApp.RIDER),
    (PolicyDocType.TERMS_OF_USE, PolicyApp.RIDER),
    (PolicyDocType.PRIVACY_POLICY, PolicyApp.DRIVER),
    (PolicyDocType.TERMS_OF_USE, PolicyApp.DRIVER),
)


def bodies(country: CountryCode, doc_type: PolicyDocType, app: PolicyApp) -> dict[str, str | None]:
    langs = MARKETS[country]
    return {
        lang: (
            texts.render(doc=doc_type.value, app=app.value, country=country.value, lang=lang, date=DATE)
            if lang in langs
            else None
        )
        for lang in ("ar", "en", "fr")
    }


async def main_async(*, write: bool, session_factory=SessionLocal) -> list[str]:
    lines: list[str] = []
    async with session_factory() as session:
        for country in MARKETS:
            for doc_type, app in DOCS:
                label = f"{country.value}/{app.value}/{doc_type.value}"
                body = bodies(country, doc_type, app)
                live = await policies_service.published(session, country=country, doc_type=doc_type, app=app)
                if (
                    live is not None
                    and live.body_ar == body["ar"]
                    and (live.body_en or None) == body["en"]
                    and (live.body_fr or None) == body["fr"]
                ):
                    lines.append(f"{label}: منشورةٌ بهذه النصوص — لا تُمسّ (v{live.version})")
                    continue
                policy = await policies_service.create_version(
                    session,
                    country=country,
                    doc_type=doc_type,
                    app=app,
                    body_ar=body["ar"],
                    body_en=body["en"],
                    body_fr=body["fr"],
                    requires_reconsent=True,
                )
                previous = await policies_service.publish(session, policy, actor=None)
                await audit.record(
                    session,
                    actor=None,
                    action=AuditAction.ACTIVATE,
                    entity_type="privacy_policy",
                    entity_id=policy.id,
                    details={
                        "country_code": country.value,
                        "doc_type": doc_type.value,
                        "app": app.value,
                        "version": policy.version,
                        "replaced": previous.version if previous else None,
                        "languages": [lang for lang, text in body.items() if text],
                        "reason": REASON,
                    },
                )
                sizes = " · ".join(f"{lang} {len(text)}" for lang, text in body.items() if text)
                was = f"v{previous.version} مؤرشفة" if previous else "لا منشورةَ قبلها"
                lines.append(f"{label}: v{policy.version} تُنشر ({sizes} حرفاً) — {was}")
        if write:
            await session.commit()
        else:
            await session.rollback()
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="نشرُ السياسات والشروط الكاملة (SPEC §٧٦/٣)")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for line in asyncio.run(main_async(write=args.apply)):
        print(f"  {line}")
    print("✓ نُشرت" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
