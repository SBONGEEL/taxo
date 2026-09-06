"""نسخةٌ ثانيةٌ للوثائق الأربع — **تُكتب مسوّدةً، والنشرُ فعلُ إنسان**.

    python -m scripts.policies_v2 --dry     # يقرأ ويطبع الخطّةَ ولا يكتب حرفاً
    python -m scripts.policies_v2           # يكتب المسوّداتِ ولا ينشر شيئاً

## لِمَ وُجد هذا السكربت — **و`seed_policies` لا يغني عنه**

`seed_policies.py` **idempotent بالثلاثية**: لا يكتب حيث يوجد صفّ، **بقصدِ
ألّا يدفن مراجعةَ إنسانٍ تحت نسخةٍ آلية**. فهو **لا يصنع نسخةً ثانيةً أبداً**،
وذاك صوابُه لا عيبُه.

**والرفعةُ لا تحمل الصفوف**: نصُّ الوثائق يعيش في القاعدة (§34)، **فتصحيحُ
النصِّ في الشيفرة لا يبلغ الإنتاج بالرفع** — وقد قِيس ذلك ٢٠٢٦-٠٩-٠٦ حين
بقيت `v1` على الإنتاج بعد رفعةٍ خضراءَ كاملة.

## ما يفعله بالضبط — **ثلاثةُ حدودٍ لا يتجاوزها**

1. **يكتب صفّاً جديداً وحدَه** عبر `policies.create_version` — **وهو الباب
   الذي تستعمله اللوحة نفسُها**، لا `INSERT` بيد. ورقمُ النسخة يُحسب من
   `_next_version` فلا يُخترع.
2. **ولا يمسّ `v1` ولا أيَّ صفٍّ قائم**: صفرُ `UPDATE` وصفرُ `DELETE`
   وصفرُ `execute(` — **مقيسٌ على الأسطر التنفيذية وحدَها** (٥٨ سطراً بعد
   تجريد التوثيق والتعليقات بمُحلِّل `ast`). و`v1` **تبقى منشورةً** حتى ينشر
   إنسانٌ `v2` من اللوحة.

   > **⚠ والقياسُ على الملفِّ كلِّه كذب أوّلَ مرّة**: `grep` وجد الكلمتين —
   > **في هذه الجملة التي تنفيهما**. **فدعوى «لا تَرِد كلمةُ كذا» تصطدم
   > بنصِّها**، ويُقرأ العددُ الموجبُ عطباً أو يُطفأ القياسُ لأنه «يصيح على
   > السليم». **والنصُّ يُجرَّد قبل أن يُقاس.**
3. **و`requires_reconsent = False`** — قرارُ المالك ٢٠٢٦-٠٩-٠٦: حذفُ كلمةٍ
   تصف حالَ الوثيقة **لا يغيّر ما وافق عليه أحد**. والأثرُ أن
   `min_accepted_version` يبقى على نسخةِ المنشورة السابقة، **فلا يُطالَب
   مستعمِلٌ قائمٌ بقبولٍ جديد**.

## وطريقُ الرجوع — **مقيسٌ لا موصوف**

**المسوّدةُ لا تُخدَم لأحد**: `policies.published` يقرأ `is_published` وحدَه،
**فحتى لحظةِ النشر لا شيءَ تغيّر لأيِّ مستعمِل**. والرجوعُ حينئذٍ **حذفُ
المسوّدة** (`delete_draft`، وهو مسموحٌ للمسوّدة بلا قبولٍ عليها) — أو تركُها
ولا أثرَ لها.

**وبعد النشر** — إن نشرتَ ثمّ عدلتَ — **`withdraw` يعيد المنشورةَ السابقة**،
وهو بابُ اللوحة نفسُه. **ولا يُحذف نصٌّ نُشر** (§34).

## وما لا يفعله — يُقال ولا يُقرأ سكوتُه ضماناً

· **لا ينشر**. `--publish` ليس فيه أصلاً — **والنشرُ يحتاج `actor` مسؤولاً
  يُسجَّل في التدقيق**، وسكربتٌ بلا وجهٍ ليس مسؤولاً.
· **ولا يقارن نصّاً بنصّ ليقرّر «أهذا تحسين؟»** — يقارن **تطابقاً حرفياً**
  وحدَه: إن كان المنشورُ يساوي النصَّ الجديد **لم يكتب شيئاً**.
· **ولا يعرف أيَّ قاعدةٍ يخاطب** — يقرؤها من `DATABASE_URL` في بيئته،
  **ويطبعها قبل أن يكتب** فلا يُشغَّل على قاعدةٍ يظنّها غيرَها.
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
from scripts.seed_policies import DRAFTS, MARKETS

DRY = "--dry" in sys.argv


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
    print(f"  الأسواق : {', '.join(m.value for m in MARKETS)}")
    print()

    written = skipped = 0
    async with SessionLocal() as session:
        for country in MARKETS:
            for doc_type, app, body in DRAFTS:
                new_text = body.strip() + "\n"
                label = f"{country.value}/{app.value}/{doc_type.value}"

                # **كلُّ نسخِ الثلاثيّة تُقرأ** — لا المنشورةُ وحدَها: مسوّدةٌ
                # مكتوبةٌ سلفاً بالنصِّ نفسِه تجعل تشغيلاً ثانياً يكتب ثالثةً.
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

                if not rows:
                    print(f"  ✗ {label}: لا صفَّ أصلاً — **يُتخطّى**")
                    print("      (هذا سكربتُ نسخةٍ ثانية، والأولى بابُها seed_policies)")
                    skipped += 1
                    continue

                top = rows[0]
                live = next((r for r in rows if r.is_published), None)

                if top.body_ar == new_text:
                    state = "منشورة" if top.is_published else "مسوّدة"
                    print(f"  · {label}: v{top.version} ({state}) **نصُّها هو النصُّ الجديد** — لا كتابة")
                    skipped += 1
                    continue

                nxt = top.version + 1
                print(f"  + {label}")
                print(f"      المنشورةُ الآن : v{live.version if live else '—'} · {len(live.body_ar) if live else 0} حرفاً")
                print(f"      ستُكتب        : v{nxt} · {len(new_text)} حرفاً · **مسوّدة** · requires_reconsent=False")
                print(f"      الفرق         : {len(new_text) - (len(live.body_ar) if live else 0):+d} حرفاً")
                for mark in ("مسوّدة", "لسنا ناقلاً", "Mapbox", "WhatsApp", "Firebase"):
                    was = (live.body_ar.count(mark) if live else 0)
                    now = new_text.count(mark)
                    if was != now:
                        print(f"        «{mark}»: {was} ⇒ {now}")

                if not DRY:
                    await policies_service.create_version(
                        session,
                        country=country,
                        doc_type=doc_type,
                        app=app,
                        body_ar=new_text,
                        body_en=None,
                        requires_reconsent=False,
                    )
                written += 1

        if DRY:
            # **ولا `commit` ولا `flush` باقٍ**: القراءةُ وحدَها وقعت.
            await session.rollback()
            print(f"\n  ⇒ **لم يُكتب حرف** — {written} ستُكتب، {skipped} تُتخطّى.")
        else:
            await session.commit()
            print(f"\n  ⇒ كُتبت {written} مسوّدة، وتُخطّيت {skipped}. **ولم يُنشر شيء.**")
            print("     النشرُ من اللوحة: الوثائق ← النسخة ← «انشر».")

    await engine.dispose()


asyncio.run(main())
