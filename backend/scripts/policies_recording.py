"""قسمُ **«تسجيلُ المكالمات»** في سياستَي الخصوصية وشرطَي الاستعمال — **مسوّداتٌ لا تُنشر** (SPEC §٧١-ب/٤، أمرُ المالك ٢٠٢٦-١٠-٠٩).

    python -m scripts.policies_recording            # يقرأ ويطبع الخطّةَ ولا يكتب حرفاً
    python -m scripts.policies_recording --write    # يكتب المسوّدات الأربع ولا ينشر شيئاً

## لمَ قسمٌ مستقلّ — **وبإذن من**

المالكُ (٢٠٢٦-١٠-٠٩): «اكتب قسماً منفصلاً للتسجيل في سياسة الخصوصية والشروط: ماذا، ولماذا، وكم، ومن يسمع. **أبقِه غيرَ منشورٍ
ومطفأً**، وضع نصَّه في التقرير.» — **فهذا السكربتُ لا ينشر شيئاً بحال**: النشرُ فعلُ مسؤولٍ من اللوحة بعد أن يقرّ المالكُ الصياغة.

**وعنوانُ القسم حرفاً هو ما يشترطه إشعالُ التسجيل** (`services/trip_chat.RECORDING_PRIVACY_MARKER`): بابُ اللوحة يرفض
`call_recording_enabled = true` حتى يُنشر القسمُ في سياستَي الراكب والكبتن معاً — **فتغييرُ حرفٍ في العنوان يُبقي التسجيلَ مطفأً**.

## ولمَ «استثناءٌ» صريح

قسمُ «محادثةُ الرحلة ومكالمتُها» المنشورُ يقول **«ولا نحفظ الصوت»** — وهو صادقٌ ما دام التسجيلُ مطفأً. **فقسمُ التسجيل يسمّي نفسَه
استثناءً منه** بدل أن يُعاد تحريرُ نصٍّ منشور: النصّان يُقرآن معاً ولا يتناقضان.

**ويُلحق ولا يعيد الكتابة** كـ`policies_v3`: النسخةُ الجديدة = **المنشورةُ حرفاً + القسم**، عبر `policies.create_version` (بابُ اللوحة
نفسُه)، **و`requires_reconsent = True`**: صوتٌ لم يُجمع قبلها. **وidempotent**: عنوانُ القسم في أعلى النسخ ⇒ لا كتابة.
**والرجوع**: المسوّدةُ تُحذف من اللوحة (`delete_draft`).
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
from app.services.trip_chat import RECORDING_PRIVACY_MARKER

WRITE = "--write" in sys.argv

#: **الأردنُ وحدَه** — ليبيا لا تُمسّ (§٧١)
MARKETS = (CountryCode.JO,)

#: **العنوانُ حرفاً من الحارس** — لا نسخةٌ ثانيةٌ تفترق عنه
HEADING = RECORDING_PRIVACY_MARKER


def _privacy_section(other: str) -> str:
    """**ماذا، ولماذا، وكم، ومن يسمع** — والإقرارُ قبل كلِّ مكالمة، كما يفرضه الخادم (`ride_calls`: لا رنينَ ولا ردَّ بلا إقرار)."""
    return f"""{HEADING}

- متى نسجّل: لا نسجّل أيَّ مكالمةٍ داخل التطبيق إلا بعد أن يظهر قبلها إشعارٌ يقول إنها ستُسجَّل. لا يرنّ هاتفُ {other} حتى يُقرّ المتصلُ بالإشعار، ولا يستطيع من يُتّصَل به الردَّ حتى يُقرّ به هو أيضاً. وإن لم تُرد التسجيلَ فلا تُكمل المكالمة، وتبقى محادثةُ الرحلة متاحةً لك.
- ما نحفظه: صوتَ المكالمة المسجَّلة، ومعه ما نحفظه لكلِّ مكالمة: وقتُها ومدّتُها ومن اتصل بمن والرحلة. وهذا استثناءٌ مما في قسم «محادثةُ الرحلة ومكالمتُها» أننا لا نحفظ الصوت: نحفظه في المكالمة التي ظهر قبلها إشعارُ التسجيل وحدَها.
- لماذا: للسلامة، ولمعالجة البلاغات والخلافات بين الراكب والكبتن، ولمراجعة جودة الخدمة. لا نستعمله للإعلان، ولا نبيعه، ولا نعطيه لأحدٍ خارج TAXO إلا إذا ألزمنا القانونُ بذلك.
- من يسمعه: موظّفون مخوَّلون في فريق TAXO يحملون صلاحيةً خاصّةً بالاستماع وحدَه، منفصلةً عن غيرها من الصلاحيات. وكلُّ استماعٍ يُسجَّل باسم من استمع ووقتِه. ولا يُتاح التسجيلُ لأيِّ طرفٍ في التطبيق.
- كم نحتفظ به: تسعين يوماً من وقت المكالمة — وهي مدّةٌ تضبطها TAXO — ثمّ نحذف الملف، ولا يُسمع بعد انقضائها.
- حذفُ الحساب: تُحذف تسجيلاتُ كلِّ مكالمةٍ كنتَ طرفاً فيها حين يُحذف حسابُك."""


TERMS_SECTION = f"""{HEADING}

- قد تُسجَّل مكالماتُ الرحلة داخل التطبيق حين تُفعِّل TAXO التسجيل. ولا تُسجَّل مكالمةٌ إلا بعد إشعارٍ يظهر قبلها ويُقرّ به كلٌّ من الطرفين.
- إقرارُك بالإشعار موافقةٌ على تسجيل تلك المكالمة وحدَها. وإن لم توافق فلا تُكمل المكالمة، وتبقى محادثةُ الرحلة متاحة.
- تُستعمل التسجيلاتُ وفق سياسة الخصوصية: للسلامة ومعالجة البلاغات والخلافات ومراجعة الجودة، ويجوز الرجوعُ إليها في النظر في بلاغٍ يخصّك.
- لا يجوز استعمالُ المكالمة للإساءة أو التهديد أو التحرّش، وما يقع فيها من ذلك يُعالَج وفق هذه الشروط.
"""

DOCS = (
    (PolicyDocType.PRIVACY_POLICY, PolicyApp.RIDER, _privacy_section("الكبتن")),
    (PolicyDocType.PRIVACY_POLICY, PolicyApp.DRIVER, _privacy_section("الراكب")),
    (PolicyDocType.TERMS_OF_USE, PolicyApp.RIDER, TERMS_SECTION),
    (PolicyDocType.TERMS_OF_USE, PolicyApp.DRIVER, TERMS_SECTION),
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
    print(f"  الوضع   : {'**كتابةُ مسوّدات**' if WRITE else 'قراءةٌ وعرضٌ فقط'}")
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
                if WRITE:
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
        if WRITE:
            await session.commit()
            print(f"\n  ⇒ كُتبت {written} مسوّدة، وتُخطّيت {skipped}. **ولم يُنشر شيء** — والتسجيلُ مطفأٌ حتى يُنشر القسم.")
        else:
            await session.rollback()
            print(f"\n  ⇒ **لم يُكتب حرف** — {written} ستُكتب، {skipped} تُتخطّى.")
    await engine.dispose()


asyncio.run(main())
