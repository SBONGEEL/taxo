"""فقرةُ «وضع الضيف» في سياسة الخصوصية — **نسخةٌ جديدةٌ تُنشر** لكلِّ سوقٍ وتطبيق (SPEC §٧٦-ن/٧، أمرُ المالك ٢٠٢٦-١٠-١٥).

    python -m scripts.policies_guest            # معاينة — يقرأ ويطبع الخطّة ولا يكتب حرفاً
    python -m scripts.policies_guest --apply    # يكتب النسخَ الجديدة وينشرها

**النصُّ المنشورُ اليومَ هو الأساس** — تُقرأ النسخةُ المنشورةُ لكلِّ (سوق، تطبيق) وتُضاف الفقرةُ في آخرها **بكلِّ لغةٍ فيها** (العربيّةُ
دائماً، والإنجليزيّةُ والفرنسيّةُ حيث هما)، ثمّ تُنشر نسخةً برقمٍ أعلى **والسابقةُ مؤرشفةٌ بنصّها** (`policies.create_version` و`publish` —
بابا اللوحة نفسُهما). **و`requires_reconsent = False`** (قراري): الفقرةُ تصف ميزةً جديدةً لمن لا حسابَ له، **ولا تغيّر شيئاً ممّا وافق
عليه صاحبُ الحساب** — فسؤالُه القبولَ من جديد ضجيجٌ لا حماية.

**وidempotent**: نسخةٌ فيها الفقرةُ لا تُمسّ. **ولا مالَ هنا.**
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

REASON = "SPEC §٧٦-ن/٧ — فقرةُ وضع الضيف"
MARKER = "وضعُ الضيف"

SECTION = {
    "ar": """وضعُ الضيف — التجربةُ بلا حساب
يتيح زرُّ «تجربة كضيف» تجربةَ التطبيق دون رقم هاتفٍ أو حساب. كلُّ ما يُعرض فيه محاكاةٌ على جهازك: لا رحلاتَ حقيقيّة،
ولا كباتنَ ولا ركّابَ حقيقيّين، ولا مدفوعات. ولا نحفظ على خوادمنا من وضع الضيف إلا اثنين: سجلَّ بدء التجربة (التطبيق،
ولغة الجهاز، والبلد التقريبيّ من شبكتك) مع بصمةٍ مُجزَّأةٍ لمعرّف الجهاز ولعنوان الشبكة نستعملها لمنع الإساءة وحدها ولا
يُستعاد منها الجهازُ ولا العنوان؛ وما تكتبه أنت في «أرسل ملاحظة» مع صورة الشاشة إن أرفقتها. لا تُستعمل هذه البياناتُ في
إعلانٍ ولا تُعدّ في الإحصاءات، وتُحذف تلقائيّاً بعد 30 يوماً. ومن أراد حساباً حقيقيّاً فالتسجيلُ المعتادُ بالتحقّق من
رقمه، ولا يُنقل إليه شيءٌ من التجربة.""",
    "en": """Guest mode — trying the app without an account
The "Try as guest" button lets you try the app without a phone number or an account. Everything shown in it is a
simulation on your device: no real rides, no real drivers or riders, and no payments. From guest mode we keep only two
things on our servers: a record that a trial started (the app, your device language, and the approximate country of your
network) with a hashed fingerprint of the device identifier and network address, used only to prevent abuse and from which
neither the device nor the address can be recovered; and whatever you write in "Send feedback", with a screenshot if you
attach one. This data is never used for advertising, is not counted in statistics, and is deleted automatically after
30 days. To get a real account, sign up as usual by verifying your phone number; nothing from the trial is carried over.""",
    "fr": """Mode invité — essayer l'application sans compte
Le bouton « Essayer en invité » permet d'essayer l'application sans numéro de téléphone ni compte. Tout ce qui s'y affiche
est une simulation sur votre appareil : aucune vraie course, aucun vrai chauffeur ni passager, aucun paiement. Du mode
invité, nous ne conservons sur nos serveurs que deux choses : la trace du lancement de l'essai (l'application, la langue de
l'appareil et le pays approximatif de votre réseau) avec une empreinte hachée de l'identifiant de l'appareil et de l'adresse
réseau, utilisée uniquement pour prévenir les abus et dont on ne peut retrouver ni l'appareil ni l'adresse ; et ce que vous
écrivez dans « Envoyer un avis », avec la capture d'écran si vous en joignez une. Ces données ne servent jamais à la
publicité, ne sont pas comptées dans les statistiques et sont supprimées automatiquement après 30 jours. Pour un vrai
compte, inscrivez-vous normalement en vérifiant votre numéro ; rien de l'essai n'y est transféré.""",
}


def with_section(body: str | None, lang: str) -> str | None:
    if not body:
        return body
    return body.rstrip() + "\n\n" + SECTION[lang] + "\n"


async def main_async(*, write: bool, session_factory=SessionLocal) -> list[str]:
    lines: list[str] = []
    async with session_factory() as session:
        for country in (CountryCode.JO, CountryCode.LY, CountryCode.DZ):
            for app in (PolicyApp.RIDER, PolicyApp.DRIVER):
                label = f"{country.value}/{app.value}/privacy_policy"
                live = await policies_service.published(
                    session, country=country, doc_type=PolicyDocType.PRIVACY_POLICY, app=app
                )
                if live is None:
                    lines.append(f"{label}: لا منشورةَ — لا تُمسّ")
                    continue
                if MARKER in live.body_ar:
                    lines.append(f"{label}: فيها الفقرةُ أصلاً — لا تُمسّ (v{live.version})")
                    continue
                body = {
                    "ar": with_section(live.body_ar, "ar"),
                    "en": with_section(live.body_en, "en"),
                    "fr": with_section(live.body_fr, "fr"),
                }
                policy = await policies_service.create_version(
                    session,
                    country=country,
                    doc_type=PolicyDocType.PRIVACY_POLICY,
                    app=app,
                    body_ar=body["ar"] or "",
                    body_en=body["en"],
                    body_fr=body["fr"],
                    requires_reconsent=False,
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
                        "doc_type": "privacy_policy",
                        "app": app.value,
                        "version": policy.version,
                        "replaced": previous.version if previous else None,
                        "languages": [lang for lang, text in body.items() if text],
                        "reason": REASON,
                    },
                )
                langs = " · ".join(lang for lang, text in body.items() if text)
                lines.append(f"{label}: v{policy.version} تُنشر ({langs}) — v{previous.version if previous else '?'} مؤرشفة")
        if write:
            await session.commit()
        else:
            await session.rollback()
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="فقرةُ وضع الضيف في سياسة الخصوصية (SPEC §٧٦-ن/٧)")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for line in asyncio.run(main_async(write=args.apply)):
        print(f"  {line}")
    print("✓ نُشرت" if args.apply else "· معاينة — لم يُكتب شيء (أعد بـ--apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
