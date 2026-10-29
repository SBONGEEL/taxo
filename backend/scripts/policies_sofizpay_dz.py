"""سياسةُ خصوصيّة الجزائر التي **تسمّي SofizPay** (SPEC §٨٥/٥، أمرُ المالك ٢٠٢٦-١٠-٢٩ «publish the Algeria privacy policy naming SofizPay»).

    python -m scripts.policies_sofizpay_dz            # معاينة — يقرأ ويطبع الخطّة ولا يكتب حرفاً
    python -m scripts.policies_sofizpay_dz --apply    # يكتب نسختَي الراكب والكبتن وينشرهما

**يُلحق ولا يعيد الكتابة** (نمطُ `policies_recording`): النسخةُ الجديدة = **المنشورةُ حرفاً بلغاتها الثلاث + قسمُ SofizPay** بلغته، عبر
`policies.create_version` و`policies.publish` (بابا اللوحة). **و`requires_reconsent = True`**: مزوّدٌ جديدٌ يتلقّى بياناتِ الدافع —
فيُسأل كلُّ مستعمِلٍ في الجزائر القبولَ من جديد (شاشةُ الموافقة القائمة). **وidempotent**: العنوانُ في أعلى نسخة ⇒ لا كتابة.
**والرجوع**: `policies.withdraw` على الجديدة ثمّ نشرُ السابقة من اللوحة. **ولا مالَ هنا.**
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402
from app.models.enums import AuditAction, CountryCode, PolicyApp, PolicyDocType  # noqa: E402
from app.models.privacy import PrivacyPolicy  # noqa: E402
from app.services import audit  # noqa: E402
from app.services import policies as policies_service  # noqa: E402

REASON = "أمرُ المالك ٢٠٢٦-١٠-٢٩: SofizPay وسيطاً حيّاً في الجزائر — سياسةُ الخصوصيّة تسمّيه (SPEC §٨٥/٥)"
#: **علامةُ القسم** في العربيّة — بها يُعرف أنه نُشر
MARK_AR = "الدفعُ عبر SofizPay"

SECTION = {
    "ar": f"""{MARK_AR}

- حين تختار الدفعَ ببطاقة الذهبية أو CIB عبر SofizPay (مزوّدِ دفعٍ في الجزائر)، نرسل إليه مبلغَ الدفعة واسمَك ورقمَ هاتفك وبريدَك الإلكترونيّ — يشترطها لإنشاء الدفعة — ووصفاً عامّاً للعمليّة («TAXO شحن رصيد» أو «TAXO اشتراك»).
- تُدخل بياناتِ بطاقتك في صفحة SofizPay أو صفحة SATIM/بريد الجزائر مباشرةً، لا في TAXO. ولا نرى رقمَ بطاقتك ولا رمزَها السرّيّ ولا نحفظهما.
- نسأل SofizPay عن حال الدفعة ونحفظ مرجعَها، ولا يُضاف الرصيدُ إلى محفظتك ولا يُفعَّل اشتراكُك إلا بعد أن يؤكّد SofizPay الدفعةَ لحساب TAXO بمبلغها.""",
    "fr": """Paiement via SofizPay

- Lorsque vous choisissez de payer par carte Edahabia ou CIB via SofizPay (prestataire de paiement en Algérie), nous lui transmettons le montant du paiement, votre nom, votre numéro de téléphone et votre e-mail — exigés pour créer le paiement — ainsi qu’une description générale de l’opération (« TAXO recharge » ou « TAXO abonnement »).
- Vous saisissez les données de votre carte directement sur la page de SofizPay ou celle de SATIM/Algérie Poste, pas dans TAXO. Nous ne voyons ni ne conservons votre numéro de carte ni son code.
- Nous interrogeons SofizPay sur l’état du paiement et conservons sa référence ; votre solde n’est crédité et votre abonnement n’est activé qu’après la confirmation par SofizPay du paiement vers le compte de TAXO, pour son montant.""",
    "en": """Payment through SofizPay

- When you choose to pay by Edahabia or CIB card through SofizPay (a payment provider in Algeria), we send it the payment amount, your name, phone number and email — required to create the payment — and a generic description of the operation ("TAXO top-up" or "TAXO subscription").
- You enter your card details directly on SofizPay's page or SATIM/Algérie Poste's page, not in TAXO. We never see or store your card number or its code.
- We ask SofizPay for the payment status and keep its reference; your balance is credited and your subscription activated only after SofizPay confirms the payment to TAXO's account, for its amount.""",
}


#: **سطرُ «آخر تحديث» يقول تاريخَ هذه النسخة** — وإلا نُشرت نسخةٌ جديدةٌ تقول إنها لم تتغيّر منذ أسبوعين
DATE = "2026-10-29"
_UPDATED = re.compile(r"((?:آخر تحديث|Dernière mise à jour|Last updated)\s*:\s*)\d{4}-\d{2}-\d{2}")


def _with(body: str | None, lang: str) -> str | None:
    if body is None:
        return None
    body = _UPDATED.sub(lambda m: m.group(1) + DATE, body, count=1)
    return body.rstrip() + "\n\n" + SECTION[lang].strip() + "\n"


async def main(apply: bool) -> None:
    written = 0
    async with SessionLocal() as session:
        for app in (PolicyApp.RIDER, PolicyApp.DRIVER):
            label = f"DZ/{app.value}/privacy"
            rows = (await session.scalars(
                select(PrivacyPolicy).where(
                    PrivacyPolicy.country_code == CountryCode.DZ,
                    PrivacyPolicy.doc_type == PolicyDocType.PRIVACY_POLICY,
                    PrivacyPolicy.app == app,
                ).order_by(PrivacyPolicy.version.desc())
            )).all()
            live = next((r for r in rows if r.is_published), None)
            if live is None:
                raise SystemExit(f"✗ {label}: لا نسخةَ منشورة — يقف ولا يكتب")
            if MARK_AR in rows[0].body_ar:
                print(f"  · {label}: v{rows[0].version} فيها القسمُ سلفاً ({'منشورة' if rows[0].is_published else 'مسوّدة'}) — لا كتابة")
                continue
            if rows[0].id != live.id:
                raise SystemExit(f"✗ {label}: فوق المنشورة v{live.version} مسوّدةٌ v{rows[0].version} — يقف ولا يكتب فوقها")
            langs = [lang for lang, body in (("ar", live.body_ar), ("fr", live.body_fr), ("en", live.body_en)) if body]
            print(f"  + {label}: v{live.version} المنشورة ({'/'.join(langs)}) + قسمُ SofizPay ⇒ v{live.version + 1} · requires_reconsent=True")
            if not apply:
                continue
            draft = await policies_service.create_version(
                session, country=CountryCode.DZ, doc_type=PolicyDocType.PRIVACY_POLICY, app=app,
                body_ar=_with(live.body_ar, "ar"), body_en=_with(live.body_en, "en"), body_fr=_with(live.body_fr, "fr"),
                requires_reconsent=True,
            )
            previous = await policies_service.publish(session, draft, actor=SimpleNamespace(id=None))  # type: ignore[arg-type]
            await audit.record(
                session, actor=None, action=AuditAction.ACTIVATE, entity_type="privacy_policy",  # type: ignore[arg-type]
                entity_id=draft.id,
                details={"country_code": "DZ", "doc_type": "privacy_policy", "app": app.value, "version": draft.version,
                         "min_accepted_version": draft.min_accepted_version,
                         "replaced_version": None if previous is None else previous.version, "reason": REASON},
            )
            print(f"    ✓ نُشرت v{draft.version} (min_accepted_version={draft.min_accepted_version})")
            written += 1
        if apply:
            await session.commit()
        else:
            await session.rollback()
    print(f"\n  ⇒ {'نُشرت' if apply else 'ستُنشر'} {written if apply else 'ما عُلِّم بـ+'}")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    asyncio.run(main(parser.parse_args().apply))
