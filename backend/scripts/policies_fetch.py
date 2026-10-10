"""سطرُ الطرد في سياسة خصوصية الراكب يتّسع لـ«أحضر غرضي» (SPEC §٧٢-ج/١، أمرُ المالك ٢٠٢٦-١٠-١٠).

    python -m scripts.policies_fetch              # يقرأ ويطبع الخطّةَ ولا يكتب حرفاً
    python -m scripts.policies_fetch --publish    # يكتب النسخةَ وينشرها (بأمر المالك)

## لمَ — **وبإذن من**

المالكُ (٢٠٢٦-١٠-١٠): «اسمُ من يسلّم الغرضَ ورقمُه لهذا الطلب وحدَه، ويُحذفان بعد ٣٠ يوماً، **تحت سطر خصوصية الطرد المنشور — وسِّع صياغتَه
إن لزم واذكر التغييرَ في تقريرك**». والسطرُ المنشورُ يقول «حين ترسل طرداً نحفظ اسمَ المستلم…» — **ولا يذكر من يسلّم غرضاً ولا وصفَه**، فيُوسَّع.

## ما يفعله — **يستبدل سطراً واحداً حرفاً**

يقرأ **النسخةَ المنشورة** لسياسة خصوصية الراكب في الأردن، ويستبدل `OLD` بـ`NEW` — **وما عداه حرفاً**، ويقف إن لم يجد `OLD` كما هو.
ويكتب عبر `policies.create_version` و`publish` — **بابا اللوحة نفسُهما** — بقيد تدقيقٍ بلا فاعلٍ وسببُه فيه.

**و`requires_reconsent = False`** (قراري): المالكُ قرّر أن السطرَ المنشورَ **يغطّيه** — فالتوسيعُ إيضاحٌ لما وافق عليه الراكبُ لا بيانٌ من
صنفٍ جديد (طرفٌ ثالثٌ لتوصيلٍ واحد، يُمحى بالمدّة نفسِها). **والرجوع**: سحبُ النسخة من اللوحة (`withdraw`) فتعود السابقة.
**وidempotent**: `NEW` في المنشورة ⇒ لا كتابة. **وليبيا لا تُمسّ.**
"""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.models.enums import AuditAction, CountryCode, PolicyApp, PolicyDocType
from app.models.privacy import PrivacyPolicy
from app.services import audit
from app.services import policies as policies_service

PUBLISH = "--publish" in sys.argv
REASON = "بأمر المالك — SPEC §72-ج/1 (2026-10-10): سطرُ الطرد يتّسع لـ«أحضر غرضي»"

#: **السطرُ المنشورُ حرفاً** (`policies_v3.RIDER_SECTION`)
OLD = (
    "- الطرد: حين ترسل طرداً نحفظ اسمَ المستلم وعنوانَه ورقمَ هاتفه لهذا التوصيل وحدَه، ليصل إليه الكبتنُ ويسلّمه. "
    "ونحذفها بعد ثلاثين يوماً من انتهاء التوصيل، ولا نستعملها لغيره."
)
NEW = (
    "- الطرد و«أحضر غرضي»: حين ترسل طرداً نحفظ اسمَ المستلم وعنوانَه ورقمَ هاتفه، وحين تطلب أن نُحضر لك غرضاً نحفظ اسمَ من يسلّمه "
    "للكبتن ورقمَ هاتفه وعنوانَ الاستلام ووصفَ الغرض — لهذا التوصيل وحدَه، ليصل إليه الكبتنُ ويُتمّه. "
    "ونحذفها بعد ثلاثين يوماً من انتهاء التوصيل، ولا نستعملها لغيره. وعليك أن يعلم من تعطينا اسمَه ورقمَه أنك أعطيتنا إيّاهما."
)


async def main() -> None:
    print(f"  الوضع : {'**كتابةٌ ونشر**' if PUBLISH else 'قراءةٌ وعرضٌ فقط'}")
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(PrivacyPolicy)
                .where(
                    PrivacyPolicy.country_code == CountryCode.JO,
                    PrivacyPolicy.doc_type == PolicyDocType.PRIVACY_POLICY,
                    PrivacyPolicy.app == PolicyApp.RIDER,
                )
                .order_by(PrivacyPolicy.version.desc())
            )
        ).all()
        live = next((row for row in rows if row.is_published), None)
        if live is None:
            raise SystemExit("✗ لا نسخةَ منشورةً لسياسة خصوصية الراكب في الأردن — يقف")
        if NEW in live.body_ar:
            print(f"  · v{live.version} المنشورة فيها السطرُ الموسَّعُ سلفاً — لا كتابة")
            await engine.dispose()
            return
        if live.body_ar.count(OLD) != 1:
            raise SystemExit(f"✗ سطرُ الطرد ليس في المنشورة v{live.version} حرفاً مرّةً واحدة — يقف ولا يكتب")
        if not rows[0].is_published:
            raise SystemExit(f"✗ مسوّدةٌ v{rows[0].version} فوق المنشورة — تُراجَع من اللوحة أوّلاً، يقف")
        print(f"  − {OLD}\n  + {NEW}")
        print(f"  ⇒ v{live.version} المنشورة ⇒ v{rows[0].version + 1} · requires_reconsent=False")
        if not PUBLISH:
            await session.rollback()
            print("  ⇒ **لم يُكتب حرف**")
            await engine.dispose()
            return
        draft = await policies_service.create_version(
            session,
            country=CountryCode.JO,
            doc_type=PolicyDocType.PRIVACY_POLICY,
            app=PolicyApp.RIDER,
            body_ar=live.body_ar.replace(OLD, NEW),
            body_en=None,
            requires_reconsent=False,
        )
        previous = await policies_service.publish(session, draft, actor=SimpleNamespace(id=None))  # type: ignore[arg-type]
        await audit.record(
            session, actor=None, action=AuditAction.ACTIVATE, entity_type="privacy_policy",  # type: ignore[arg-type]
            entity_id=draft.id,
            details={"country_code": "JO", "doc_type": PolicyDocType.PRIVACY_POLICY.value, "app": PolicyApp.RIDER.value,
                     "version": draft.version, "min_accepted_version": draft.min_accepted_version,
                     "replaced_version": None if previous is None else previous.version, "reason": REASON},
        )
        await session.commit()
        print(f"  ✓ نُشرت v{draft.version}")
    await engine.dispose()


asyncio.run(main())
