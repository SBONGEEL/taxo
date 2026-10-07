"""نسخةٌ ثالثةٌ لسياستَي الخصوصية — **سطورُ الخدمات الجديدة وساعاتِ العمل** (SPEC §٦٤-هـ/٤، `design/APPROVALS-62.md` §٥-٢).

    python -m scripts.policies_v3 --dry     # يقرأ ويطبع الخطّةَ ولا يكتب حرفاً
    python -m scripts.policies_v3           # يكتب المسوّدتين ولا ينشر شيئاً

## لمَ نسخةٌ ثالثة — **وبإذن من**

المالكُ في رسالته الرابعة (٢٠٢٦-١٠-٠٧): «البياناتُ الشخصيةُ الجديدةُ في الأردن — ساعاتُ العمل، وبياناتُ الراكب الآخر، وبياناتُ المستلم —
**انشر سطورَ الخصوصية التي كتبتَها قبل أن تجمع تلك الميزاتُ شيئاً**، وضع نصَّها في التقرير لمراجعته. ولا يتغيّر نصٌّ عامٌّ غيرُها.»

## ما يفعله — **يُلحق ولا يعيد الكتابة**

يقرأ **النسخةَ المنشورةَ الآن** لكلِّ وثيقة ويكتب نسخةً جديدةً = **نصُّها حرفاً + قسمٌ أخيرٌ بالسطور الجديدة** — فلا يمسّ نصّاً راجعه المالك،
**ولا يفترق ما على التطوير عمّا على الإنتاج إلا بما افترق قبله**. ويكتب عبر `policies.create_version` — **بابُ اللوحة نفسُه** — مسوّدةً
لا تُخدَم لأحد؛ **والنشرُ فعلُ مسؤولٍ من اللوحة** يُسجَّل في التدقيق.

**و`requires_reconsent = True`** (قراري): هذه سطورٌ عن **بياناتٍ لم تُجمع قبلها** — لا تصحيحُ صياغة كـ`v2` — فيُسأل كلُّ مستعمِلٍ القبولَ من
جديد كما يُسأل عند كلِّ نسخةٍ تغيّر ما وافق عليه.

**وidempotent**: إن وُجد عنوانُ القسم في أعلى النسخ لم يكتب شيئاً. **والرجوع**: المسوّدةُ تُحذف (`delete_draft`)، والمنشورةُ تُسحب
(`withdraw`) فتعود السابقة — بابا اللوحة نفسُهما.
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.models.enums import CountryCode, PolicyApp, PolicyDocType
from app.models.privacy import PrivacyPolicy
from app.services import policies as policies_service

DRY = "--dry" in sys.argv

#: **الأردنُ وحدَه** — ليبيا مستثناةٌ تبقى كما هي (§٦٤-هـ/٢)
MARKETS = (CountryCode.JO,)

HEADING = "ما أضفناه مع الخدمات الجديدة"

RIDER_SECTION = f"""{HEADING}

- رحلةٌ لشخصٍ آخر: حين تطلب رحلةً لشخصٍ آخر نحفظ اسمَه ورقمَ هاتفه لهذه الرحلة وحدَها، ليعرفه الكبتنُ ويتصل به عند الالتقاط. لا نرسل إليه شيئاً ولا نستعمل رقمَه لغير هذه الرحلة، ونحذف الاسمَ والرقمَ بعد ثلاثين يوماً من انتهائها. وعليك أن يعلم صاحبُهما أنك أعطيتنا إيّاهما.
- الطرد: حين ترسل طرداً نحفظ اسمَ المستلم وعنوانَه ورقمَ هاتفه لهذا التوصيل وحدَه، ليصل إليه الكبتنُ ويسلّمه. ونحذفها بعد ثلاثين يوماً من انتهاء التوصيل، ولا نستعملها لغيره.
- رابطُ التتبّع: رابطُ التتبّع الذي تشاركه يُظهر لكلِّ من يفتحه اسمَ الكبتن وسيارتَه ولوحتَها وموقعَه حتى تنتهي الرحلة، ثمّ يتوقّف. ولا يُظهر رقمَك ولا محفظتك.
- المشوار الثابت: نحفظ نقطتي مشوارك وأيامَه وأوقاتَه ما دام الاشتراكُ قائماً، ونعرضها على الكبتن الذي يخدمه. ونحذفها بعد ثلاثين يوماً من انتهاء الاشتراك.
- بين المدن: يرى الكبتنُ اسمَك قبل الانطلاق بساعة، ورقمَك عند بدء الرحلة.
"""

CAPTAIN_SECTION = f"""{HEADING}

- رابطُ التتبّع: إن شارك الراكبُ رابطَ تتبّع رحلته، يرى من يفتحه اسمَك كما يراه الراكب وسيارتَك ولوحتَها وموقعَك أثناء هذه الرحلة وحدَها، ويتوقّف الرابطُ بانتهائها. ولا يُظهر رقمَ هاتفك.
- بين المدن: ترى أسماءَ ركّاب رحلتك قبل الانطلاق بساعة، وأرقامَهم عند بدئها فقط.
- ساعاتُ العمل: نحسب كلَّ يومٍ كم دقيقةً كنتَ متصلاً تستقبل الطلبات، لنعرض لك ساعاتِ عملك ويراها فريقُ TAXO. لا نحفظ موقعَك وأنت تنتظر — الرقمُ وحدَه. ونحفظه ثلاثةَ عشرَ شهراً ثمّ نجمعه شهرياً.
"""

DOCS = (
    (PolicyDocType.PRIVACY_POLICY, PolicyApp.RIDER, RIDER_SECTION),
    (PolicyDocType.PRIVACY_POLICY, PolicyApp.DRIVER, CAPTAIN_SECTION),
)


def _where() -> str:
    """أيُّ قاعدةٍ نخاطب — **بلا كلمةِ السرّ**."""
    url = os.environ.get("DATABASE_URL", "<غيرُ مضبوط>")
    if "@" in url:
        head, tail = url.split("@", 1)
        scheme = head.split("://", 1)[0] if "://" in head else "?"
        return f"{scheme}://<محجوب>@{tail}"
    return url


async def main() -> None:
    print(f"  القاعدة : {_where()}")
    print(f"  الوضع   : {'قراءةٌ وعرضٌ فقط (--dry)' if DRY else '**كتابةُ مسوّدات**'}")
    written = skipped = 0
    async with SessionLocal() as session:
        for country in MARKETS:
            for doc_type, app, section in DOCS:
                label = f"{country.value}/{app.value}/{doc_type.value}"
                rows = (
                    await session.scalars(
                        select(PrivacyPolicy)
                        .where(
                            PrivacyPolicy.country_code == country,
                            PrivacyPolicy.doc_type == doc_type,
                            PrivacyPolicy.app == app,
                        )
                        .order_by(PrivacyPolicy.version.desc())
                    )
                ).all()
                live = next((row for row in rows if row.is_published), None)
                if live is None:
                    print(f"  ✗ {label}: لا نسخةَ منشورة — **يُتخطّى** (لا يُلحق بما لم يراجعه أحد)")
                    skipped += 1
                    continue
                if HEADING in rows[0].body_ar:
                    state = "منشورة" if rows[0].is_published else "مسوّدة"
                    print(f"  · {label}: v{rows[0].version} ({state}) فيها القسمُ سلفاً — لا كتابة")
                    skipped += 1
                    continue
                new_text = live.body_ar.rstrip() + "\n\n" + section.strip() + "\n"
                print(f"  + {label}: v{live.version} المنشورة + القسم ⇒ v{rows[0].version + 1} مسوّدة · requires_reconsent=True")
                if not DRY:
                    await policies_service.create_version(
                        session,
                        country=country,
                        doc_type=doc_type,
                        app=app,
                        body_ar=new_text,
                        body_en=None,
                        requires_reconsent=True,
                    )
                written += 1
        if DRY:
            await session.rollback()
            print(f"\n  ⇒ **لم يُكتب حرف** — {written} ستُكتب، {skipped} تُتخطّى.")
        else:
            await session.commit()
            print(f"\n  ⇒ كُتبت {written} مسوّدة، وتُخطّيت {skipped}. **ولم يُنشر شيء** — النشرُ من اللوحة.")
    await engine.dispose()


asyncio.run(main())
