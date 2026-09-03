# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## الرفعُ خمسُ بوّاباتٍ بترتيبها (قرارُ المالك 2026-08-21) — **فوق كلِّ ما بعده**

**كلُّ مرحلةٍ بوّابة: ما لم تخضرَّ لا تبدأ التي بعدها.** وتُنفَّذ **عبر
`scripts/deploy.sh`** لا عن ذاكرة — فقاعدةٌ تُتذكَّر تُنسى، وقد نُسيت في هذا
المشروع مراراً.

**وترتيبُها ترتيبُ اعتمادٍ لا ترتيبَ سرد — فهو مُلزِمٌ لا مقترَح** (قرارُ
المالك 2026-08-22). كلُّ بوّابةٍ **تستهلك ما تُنتجه التي قبلها، وتهدم ما
تحتاجه التي قبلها**: الثالثةُ تنسخ **الحالَ التي ستهدمها الرابعة**، والرابعةُ
لا تبدأ قبل أن تخضرَّ الثالثة، والخامسةُ تقيس ما فعلته الرابعة. **فتقديمُ فعلٍ
من بوّابةٍ متأخّرةٍ يُسقط بوّابةً سابقة** — ووقع مقيساً: أُزيحت الملفّاتُ
المتصادمةُ **قبل** بوّابة النسخة وفيها ملفُّ compose نفسُه، فسقطت النسخةُ لأن
كلَّ أمرِ compose يذكر ملفاتِه ولم يعد الملفُّ هناك. **والاعتمادُ غيرُ مرئيٍّ
في السرد، ولا يظهر إلا حين يسقط.**

**وثلاثُ مطلقاتٍ فوق الخمس، لا تُوازَن بشيء:**

1. **لا رفعَ بلا نسخةٍ محقَّقة.**
2. **لا رفعَ يمسّ جدولَ مالٍ بلا عرضه على المالك.**
3. **ولا إلغاءَ لحارسٍ أو حدٍّ أمنيٍّ أثناء رفعٍ مهما أعاق — يُوقَف ويُسأل.**

**وإن سقط شيءٌ في أيِّ مرحلة: يُوقَف عندها، ولا يُكمَل، ولا يُصلَح على
الإنتاج.** يُعرض ما سقط وطريقُ الرجوع، والقرارُ للمالك.

### ١ — الإعلان

كم التزاماً يتغيّر · أفيها ترحيلة · أتمسّ **جدولَ مال** · **وطريقُ الرجوع**:
من أين، وكيف، وكم يستغرق. **ورفعٌ بلا طريقِ رجوعٍ لا يبدأ.** وما يمسّ جدولَ
مالٍ **يقف هنا لإذنه**.

### ٢ — الدفعُ وCI

شجرةٌ نظيفةٌ مودَعة · **مسحُ ما يُدفع عن أيِّ سرّ** — ووجدانُ سرٍّ **يوقف ولا
يُنظَّف** (تنظيفُه يخفي أنه كان هناك، والتاريخُ يبقى) · دفعُ الفرع والأوسمة ·
ثم **CI على استنساخٍ نظيف**: المجموعةُ الكاملة، والحرّاس، وبناءُ الثلاثة.

**وCI لا يخاطب الإنتاجَ إطلاقاً، ولا سرَّ في سجلّه.** وأحمرُ **يوقف كلَّ شيءٍ
هنا**، ويُذكر رقمُ التشغيل ورابطُه.

### ٣ — النسخة

القاعدة و`.env` والوثائق، **خارج الخادم**، **تُفتح ويُقاس محتواها**. وتعذّرُها
وقوفٌ وسؤال.

### ٤ — الرفع

> **ولا يُزاح إلا ما يتصادم** (قرارُ المالك 2026-08-22). **ما لا مسارَ له في
> الإيداع الهدف ملفُّ خادمٍ بحقٍّ لا نسخةٌ قديمة** — سرٌّ، أو بيانُ اعتماد، أو
> مخرجُ تشغيلٍ لا يعيده السحب. **والتعميمُ كان سيطمس الفرق**: «أزِح كلَّ ما
> ليس في الإيداع» يمحو ما لا يعود، و«لا تُزِح شيئاً» يُسقط السحبَ على أول
> تصادم.
>
> **فالسؤالُ واحدٌ لكلِّ ملفّ: أله مسارٌ في الإيداع الذي نذهب إليه؟** — فإن
> كان فهو نسخةٌ تُزاح، وإلا فهو **ملكُ الخادم** ويُترك في مكانه.

**الخادمُ يسحب من GitHub نفسَ الإيداع الذي خضّره CI** — لا من جهاز أحد. **أمرٌ
واحدٌ يفعل كلَّ شيء**، **ولا حاويةَ تُعاد وحدَها**، **وكلُّ أمرِ compose يذكر
ملفاتِه كلَّها صراحةً** (فخٌّ وقع مقيساً: إعادةٌ بملفٍّ ناقصٍ جعلت حاويةً تخدم
المصدرَ بدل `dist`). والترحيلةُ تُشغَّل هنا إن وُجدت، **و`downgrade` مقيسٌ قبلها
لا مقروء**.

### ٥ — التحقّق

**الرفعُ لم يتمّ حتى تخضرَّ كلُّها:**

- إيداعُ الخادم **=** الإيداعُ الذي خضّره CI.
- رقمُ الترحيلة على القاعدة **=** رأسُ الشجرة.
- **الأعمدةُ الأربعة للثلاثة**: المبنيّ = ما تخدمه الحاوية = ما يصل عبر النفق =
  ما يُحمَّل من الصفحة. **والحاويةُ تخدم `dist` لا المصدر.**
- **مسارٌ حيٌّ من متصفحٍ لا `curl`**، وإن مسّ الرفعُ شاشةً فتُفتح ويُقرأ DOMها.
- **ومراقبةُ السجلِّ دقائق**: صفرُ أخطاءٍ أو ما ظهر.

### التقرير

**جدولٌ بالخمس مقيسةً لا موصوفة**، ومعه **موضعُ النسخة ووقتُها وحجمُها**،
**ورقمُ CI**. **وتقريرٌ بلا الجدول يُقرأ رفعاً لم يتحقّق.**

---

## ما لم يُكتب في ملفٍّ لم يحدث (قرارُ المالك 2026-08-21) — **مع المطلقتين**

**كلُّ قرارٍ وقاعدةٍ ودرسٍ يُكتب في ملفه لحظةَ الاتفاق، لا في ذاكرة الجلسة.**
الجلساتُ تنتهي والملفاتُ تبقى — **وما تذكره أنت لا يذكره من يأتي بعدك**.

1. **أيُّ قرارٍ يقوله المالكُ في محادثة: يُكتب فوراً في موضعه** (`SPEC.md` أو
   `CLAUDE.md`)، **ولا يؤجَّل إلى آخر الجلسة**. والتأجيلُ هو بعينه ما يجعل
   القرارَ يضيع: الجلسةُ تنتهي فجأةً، وما في الرأس يذهب معها.
2. **وفي كلِّ تقرير: سطرٌ يقول ماذا كُتب اليومَ وأين.**

### التسليمُ التلقائيّ — يُراقَب ويُبدأ قبل الحدِّ لا عنده

**راقب حجمَ جلستك بنفسك.** وحين **تقترب** من حدِّها — لا حين تبلغه — افعل هذا
**بلا أن يطلبه أحد**:

1. **امسح ما قيل في هذه الجلسة ولم يُكتب في ملف، واكتبه.**
2. **أودع كلَّ شيءٍ ووسم**، وتأكّد أن الشجرة نظيفة.
3. **حدّث `HANDOFF.md`**: أين نقف · ما ينتظر المالك · ما ينتظر طرفاً ثالثاً ·
   **وأولُ خمسةِ أعمالٍ للجلسة القادمة بترتيبها**.
4. **ثم قل**: «الجلسة تقترب من حدّها، التسليم جاهز — نظّفها.» **وقف. ولا تبدأ
   عملاً جديداً بعدها.**

**ولمَ قبل الحدِّ لا عنده**: التسليمُ نفسُه عملٌ يحتاج سعة — فمن ينتظر البلوغَ
يجد أن ما يسلّم به قد نفد.

<!--جديد-->
### وفي بداية كلِّ جلسة

**يُقرأ `CLAUDE.md` كاملاً** — فقراءتُه كاملةً صارت ممكنةً بعد أن كانت دعوى.

> **ولا رقمَ لحجمه في هذا النصّ — بقصد** (قرارُ المالك 2026-09-01).
>
> **الفقرةُ التي تحت هذه تشهد على نفسها**: رقمٌ يُكتب في نثرٍ يبلى، ثم يُنقل
> بعد شهرٍ على أنه خبر. **وقد بلي هذا الرقمُ ثلاث مرّاتٍ في أسبوع** — كُتب
> ٥٤ ألفاً، ثم صار ٥٧,٨٤٤، ثم هبط بالنقل إلى ما دون ذلك بكثير، **وفي كلِّ
> مرّةٍ كان النصُّ يقول عدداً لم يعد قائماً**.
>
> **فالحجمُ يُقرأ من `tools/check-docs.mjs` وحدَه**: يطبع في كلِّ تشغيلٍ
> **حجمَ كلِّ ملفٍّ والسقفَ وما تبقّى منه**. **فمن أراد الرقمَ شغّله ولم
> يقدّره ولم ينقله من هنا** — ومن نقله من هنا لم يجد ما ينقل.
>
> **و`wc -m` في صدفة ويندوز يعدّ البايتات لا الحروف** (فخٌّ وقع مقيساً
> ٢٠٢٦-٠٨-٢٦): أجاب **68,182** لهذا الملف، والحروفُ **54,516** — والعربيةُ
> بايتان للحرف، **فالرقمُ مضخَّمٌ بالثلث**. ولو كُتب لَقيل «الملفُّ فوق سقفه
> بسبعة آلاف» وهو تحته بستّة، **ولَقِيست هجرةُ قواعدَ عاملةٍ لا موجبَ لها**.
> **فوحدةُ القياس جزءٌ من الرقم، ومن نقله بلا وحدته نقل عدداً لا خبراً.**

**وما عداه بشرطه**، والشروطُ الخمسةُ تحت هذا السطر مباشرةً — **لا تُقرأ
كلُّها في كلِّ جلسة، ويُفتح منها ما تحقّق شرطُه**.

**ثم يُقال في أوّل ردّ**: **أين نقف، وما أولُ خطوة.**

> **ولمَ استُبدل النصُّ السابق** («تُقرأ الثلاثة — `HANDOFF` · `SPEC` ·
> `CLAUDE` — قبل أيِّ شيء»): **قِيس في 2026-08-25 فسقط**. وكيلٌ في مهمّةٍ
> حقيقيةٍ فتح `HANDOFF.md` **٥٣٩ سطراً من ١٠١٢** ثمّ قال إن قراءتَه «**لم
> تغيّر الجوابَ بحرف**»، **ولم يفتح `SPEC.md` البتّة** — استبدل به `grep`
> مرّتين ثمّ بنى عليه دعوى «ليس في المواصفة».
>
> **فالعلّةُ في حجم ما يُطلب لا في همّة من يقرأ**: أمرٌ بقراءة ثلاثةِ ملفّاتٍ
> يبلغ مجموعُها ثلاثةَ أرباع المليون حرفٍ **يُؤدَّى طقساً ويُقرأ امتثالاً** —
> وهي «قائمةٌ تُملأ باليد تصير طقساً يُمرّ عليه» بعينها. **وبابان يقولان
> أمرين أسوأُ من بابٍ واحد**، فاستُبدل ولم يُضَفْ إليه.
>
> **وحدُّ هذا كلِّه مكتوبٌ لا مسكوتٌ عنه**: ما يفرضه الخطّاف هو **الفتح**، ولا
> شيءَ في المشروع يقيس **الاستعمال** — والقياسُ نفسُه أثبت الفرق.


## الملفّاتُ الخمسةُ المنقولة — شروطُها ملزِمةٌ لا «عند الحاجة»

**هذا الملفُّ يحمل القواعدَ العاملةَ وحدَها.** وما نُقل **لم يُنزَل رتبةً**: هو مُلزِمٌ **بشرطٍ صريحٍ مكتوبٍ هنا**، وفتحُه ليس اختياراً.

| شرطٌ يوجب الفتح | الملفّ | حروف | عناوين |
|---|---|---:|---:|
| **قبل أن تمسّ الخلفيةَ أو تضيف باباً أو تكتب في شاشة** | `ARCHITECTURE.md` | 91,425 | 6 |
| **قبل أن تشخّص عطباً أو تسمّي شكلاً** | `PATTERNS.md` | 35,619 | 18 |
| **قبل أن تصدّق حارساً أو تبنيَ واحداً أو تنقل رقمَه** | `GUARDS.md` | 77,118 | 50 |
| **قبل أن تقول إن شيئاً مبنيٌّ أو ليس مبنيّاً، أو تنقل رقماً عن حال المشروع** | `STATE.md` | 140,120 | 27 |
| **قبل أن تشغّل أمراً أو تبنيَ حاويةً أو تفتح المجموعة** | `COMMANDS.md` | 14,121 | 2 |

**والشرطُ هو ما يجعلها ملزِمة.** «عند الحاجة» تعني أن مَن لا يعرف أن الشيءَ مكتوبٌ **لن يفتح ملفّاً ليقرأه** — وهي «بابٌ بلا زرّ» في ثوب توثيق.

**و`ARCHITECTURE.md` أكثرُه نثرٌ بلا عناوين** (6 عناوينَ لـ91,425 حرف)، **فالطريقُ إليه شرطُه لا فهرسُه** — وهذا مكتوبٌ لا مسكوتٌ عنه. والثلاثةُ الباقيةُ يبلغها الفهرسُ سطراً سطراً.

**وحارسُه `tools/check-docs.mjs`**، مقيسٌ في الاتجاهين: **لا شكلَ بلا موضع، ولا موضعَ بلا شكل، ولا منقولَ بلا طريقٍ إليه** — والرقمان مطبوعان في كلِّ تشغيل.
<!--/جديد-->
---

## قاعدتان تعلوان على كلِّ ما بعدهما (قرارُ المالك 2026-08-21)

**تُقرأان قبل أيِّ شيءٍ في هذا الملف، وتعلوان على قاعدة «قلّل الوقوف» ولا
تُوازَنان بها.** ما بعدهما تفصيلٌ في **كيف** يُعمل؛ وهاتان في **ما لا يُعمل**.

### الأولى — لا رفعَ على الإنتاج بلا نسخةٍ قبله

**كلُّ تحديثٍ يُرفع على الخادم تسبقه نسخةٌ احتياطية، بلا استثناء.**

1. **النسخةُ تسبق الرفعَ لا تليه**، وتشمل **أربعةً لا ثلاثة** (قرارُ المالك
   2026-08-22): **القاعدة**، و**`.env`**، و**مجلد الوثائق**، **وما لا يعيده
   السحبُ من قرص الإنتاج** — ملفّاتُ النفق وlanding وما يظهر معها.

   **وقائمةُ الرابع تُحسب ولا تُكتب بيد**، فما يُكتب بيدٍ يُنسى أوّلَ مسارٍ
   يُضاف. ومصدرُها **ما تعتمد عليه الحاويات فعلاً**: `docker compose config`
   يطبع كلَّ مسارِ مضيفٍ مثبَّت، ويُؤخذ منه **ما هو خارج شجرة المشروع** —
   ومعه `git ls-files --others --exclude-standard` لما هو داخلها.

   **وقِيس أن ذلك يشمل `/home/taxo/secrets` كلَّه** — بيانَ اعتماد النفق،
   و`taxo.env`، و`tunnel-id`، ومسؤولي اللوحة. **ولم تكن في أيِّ نسخةٍ قطّ**،
   وضياعُها يعني **نفقاً لا يُعاد بناؤه**.

   > **⚠ و`tar` بلا `-h` ينسخ الوصلةَ لا هدفَها** (عطبٌ مقيسٌ 2026-08-22):
   > `~/taxo/.env` **وصلةٌ رمزية**، فكان `env.tar.gz` مدخلاً بصفر بايت —
   > **نسخةٌ بلا سرّ**، **والبوّابةُ تُخضِّرها** لأن فحصَها يسأل «أفي الأرشيف
   > مدخلٌ اسمُه `.env`؟» والوصلةُ مدخلٌ اسمُه `.env`. **وهي أخطرُ من نسخةٍ
   > غائبة**: الغائبةُ تُعرف يومَ تُطلب، وهذه **تُعلَن محقَّقة** — ولو سقط
   > الخادمُ لَعادت القاعدةُ و`.env` وصلةً معلَّقة، **فلا مفتاحَ Fernet ولا
   > تُفكّ `provider_credentials`**. **فيُقاس المحتوى لا اسمُ المدخل.**
2. **ولا تُقرأ ناجحةً حتى تُقاس**: يُتحقَّق من حجمها ومن أنها **تُفتح فعلاً**.
   **نسخةٌ لم تُختبر استعادتُها ليست نسخة** — وهو درسُ «لا نجاحَ يُعلَن قبل
   التحقق ممّا كُتب» بعينه.
3. **والنسخةُ خارج الخادم لا عليه.** الخادمُ الذي تحتاج النسخةَ بسببه هو الذي
   يسقط.
4. **ويُذكر في كلِّ تقرير رفع**: أين النسخة، ومتى أُخذت، وما حجمها.
5. **وإن تعذّرت النسخةُ لأيِّ سبب: لا تُرفع.** يُوقَف ويُسأل.
6. **وبابُها واحدٌ كـ`suite.sh`**: `scripts/deploy.sh` **يرفض البدءَ بلا نسخةٍ
   محقَّقة** — **قاعدةٌ تُطبَّق لا قاعدةٌ تُتذكَّر**، وهو الفرقُ الذي أنشأ فهرسَ
   الحرّاس في هذا الملف.

### الثانية — هذا نظامٌ يحمل مالَ الناس

**المشروع يحمل محافظَ وأرصدةً وسلَفاً واشتراكاتٍ لأشخاصٍ حقيقيين. والخطأُ فيه
لا يُقرأ عطباً في شاشة — يُقرأ مالاً ضاع من جيب كبتن.** وحدودُها، فلا تبقى
موعظة:

1. **على الإنتاج: لا `UPDATE` ولا `DELETE` يدوياً على أيِّ جدولِ مال** —
   الأرصدة، المعاملات، الاشتراكات، السلَف، الدفعات. **الدفترُ لا يُعدَّل**،
   والتصحيحُ يمرّ بمسار التصحيح المبنيّ (قيدٌ مقابلٌ، لا تحرير).
2. **ولا ترحيلةَ تمسّ جدولَ مالٍ بلا نسخةٍ محقَّقةٍ قبلها وعرضٍ على المالك.**
3. **ولا حذفَ صفٍّ على الإنتاج إطلاقاً.** الإيقافُ **تعليقٌ لا حذف**، كما هو
   مبنيّ.
4. **وأيُّ أمرٍ يُكتب على قاعدة الإنتاج يُعرض على المالك قبل تنفيذه، ولو بدا
   قراءةً محضة**: القراءةُ على الإنتاج تصير كتابةً بحرفٍ واحد.
5. **وأيُّ شكٍّ في أثر تغييرٍ على مالٍ قائم: يُوقَف ويُسأل.** والوقوفُ هنا **لا
   يُحسب توقّفاً زائداً** — وهذا **استثناءٌ صريحٌ** من قاعدة «قلّل الوقوف».

---

<!--جديد-->
## شجرةُ العمل داخل لينكس (قرارُ المالك 2026-09-03)

**الشجرةُ الحيّة `~/prj/TAXO` في `Ubuntu-24.04` داخل WSL2، ومنها يُشتغَل.**
و**`D:\prj\TAXO` باقيةٌ لم تُمسّ** — **نسخٌ لا نقل**، ولا يُحذف منها شيءٌ إلا
بقول المالك.

**والأسرارُ الأربعةُ منقولةٌ بصلاحياتها في لحظة النسخ لا بعدها**: `~/.ssh`
(٧٠٠، والمفاتيحُ الخاصّةُ ٦٠٠) · `~/.taxo-secrets` (٧٠٠، وملفّاتُه ٦٠٠) ·
`~/.cloudflared` (٧٠٠) · وأسرارُ الشجرة (`.env.local` ٦٠٠ و`secrets/` ٧٠٠).
**والقديمةُ على ويندوز باقيةٌ كلُّها.** **ولمَ في اللحظة نفسِها**: `644` على
مفتاحٍ خاصٍّ مقبولٌ على ويندوز **ومرفوضٌ في لينكس بلا سببٍ واضحٍ لمن لم يقرأه**.

**وما يبقى على ويندوز بحقٍّ لا بالإهمال** (مقيسٌ ٢٠٢٦-٠٩-٠٣): **بناءُ أندرويد**
(لا SDK ولا JDK في التوزيعة، و`local.properties` ×٣ تشير إلى SDK ويندوز) ·
**الهاتفُ بالـUSB** (لا `/dev/bus/usb` ولا `usbipd-win`) · **جولةُ Playwright**
(لا متصفّحَ في التوزيعة، والحارسُ يشترط Edge المركّب) · **`pull-backup.ps1`**.

**والحكمُ على النقل ثلاثةُ أرقامٍ مقيسة**: المجموعةُ الكاملة **٣٨:٣٥ →
٣٤:٢٥ (−١٠٫٨٪)** بمقياس `pytest` نفسِه في الطرفين، **والحرّاسُ الساكنون ٤٠ ث
→ ١٢ ث (−٧٠٪)**، **وبناءُ اللوحة ٥٠ ث → ٣٩ ث (−٢٢٪)**. **ودعوى سقطت معه**: لم تكن
الكلفةُ المهيمنة `TRUNCATE` **على قرص ويندوز** — **القاعدةُ في مجلَّدٍ مسمّى
داخل آلة Docker ولم تعبر جسرَ 9p يوماً**. وتفصيلُه في `STATE.md`.

**وشجرةُ العمل هي الجديدةُ وحدَها** (قرارُ المالك 2026-09-03): **كلُّ بناءٍ
وإيداعٍ فيها، ولا يُعمل على `D:` إلا بطلبٍ صريح**. **و`D:` ليست نسخةً
احتياطية**: بناءُ أندرويد وجولةُ الهاتف وPlaywright ما زالت عليها — **فهي
نصفُ مسارِ عملٍ قائم**. **ولا تُهجَر حتى تخضرَّ الجديدةُ جولتين أو ثلاثاً**.

**والاعتمادُ تمّ ٢٠٢٦-٠٩-٠٣**: الحاوياتُ العشر والنفقُ كلُّها من الشجرة
الجديدة، **و`check:served` أعطى الأعمدةَ الثلاثةَ خضراءَ في التطبيقات
الثلاثة** — وهي أوّلُ مرّةٍ يكتمل فيها ذلك في المشروع.

---

## الفهرس — كلُّ ما نُقل، بسطرٍ وموضع

**من لا يعرف أن الشيءَ مكتوبٌ لن يفتح ملفّاً ليقرأه.** فكلُّ شكلٍ وكلُّ قاعدةٍ منقولةٍ هنا بسطرٍ ومكانِه — 101 عنواناً منقولاً. **وما يُكتب جديداً في الأربعة يُبلَغ به هنا أيضاً ولا يُلزَم** (قرارُ المالك 2026-08-25): إلزامُ كلِّ عنوانِ خبرٍ يوميٍّ يطيل الفهرسَ حتى يصير قائمةً يُمرّ عليها، **وتركُه بلا سبيلٍ يُفرِّغ النقلَ من معناه**.

### `GUARDS.md` — الحرّاس وقواعدُهم

- `check:slot` and the error boundaries — the fourth family member, and the guard that was missing (2026-08-15) → `GUARDS.md`
- وحارسٌ صحيحٌ يصير كاذباً حين يتغيّر ما تحته — **عمودُ النفق بعد قلب النطاقات** (قِيس 2026-08-26) → `GUARDS.md`
- The password policy, and a guard that hit the wrong target (2026-08-18) → `GUARDS.md`
- OTP message templates — the guard that moved rather than being deleted (2026-08-19) → `GUARDS.md`
- Latin digits everywhere — the display format was inverted (2026-08-19) → `GUARDS.md`
- قيمةٌ تنجو من كنسٍ لا يراها حارس — وأخواتُها معها (2026-08-22) → `GUARDS.md`
- والصحيحُ بالصدفة يستر الخاطئَ بالبنية (قرارُ المالك 2026-08-24) → `GUARDS.md`
- `check:doors` — the door-with-no-button family became a build guard (2026-08-19) → `GUARDS.md`
- `check:destinations` — حارسٌ مرجعُه قائمةٌ تُكتب بيدٍ يحرس الكتابةَ لا الواقع (2026-08-30) → `GUARDS.md`
- بلاغٌ كاذبٌ رابعٌ أوقف رفعاً — والقياسُ بعد التوسيع كشف ثغرةً أقدمَ منه (2026-08-30) → `GUARDS.md`
- ما يمرّ من ماسح الأسرار — بأصنافه لا بالظنّ (قِيس 2026-08-31) → `GUARDS.md`
- وكتابةٌ بلغةٍ على ويندوز تقلب نهاياتِ الأسطر — **وأمسكها `check:docs` وحدَه** (قِيس 2026-09-03) → `GUARDS.md`
- `check:update-gate` — **بوّابةُ قفلٍ منسوخةٌ ثلاثاً، فتُقاس بايتاً** (2026-09-03) → `GUARDS.md`
- A guard that invents a defect costs more than one that misses it (2026-08-20) → `GUARDS.md`
- `check:target` / `check:dist` — the build guard for "which backend is this bundle talking to" (2026-08-15) → `GUARDS.md`
- الحرّاس — وما لم يصر حارساً بعد (2026-08-20) → `GUARDS.md`
- القاعدةُ التي تسبق القواعد (قرارُ المالك 2026-08-21) → `GUARDS.md`
- امتيازٌ يُمنح لفئةٍ يصير علامةً عليها إن كان غيابُه مرئياً (قرارُ المالك 2026-08-22) → `GUARDS.md`
- وبوّابةٌ تصيح حيث لا خطر تُفرَّغ المطلقةُ من داخلها (قرارُ المالك 2026-08-22) → `GUARDS.md`
- وبابٌ يصيح ثم يخرج بصفرٍ ليس باباً (قِيس 2026-08-24) → `GUARDS.md`
- وخُضرةٌ كاذبةٌ على جهاز المطوّر أخطرُ منها في CI (قرارُ المالك 2026-08-24) → `GUARDS.md`
- وفحصُ الشكل ليس قياسَ السلوك — والشكلُ نفسُه بلغتين → `GUARDS.md`
- وعطبان يستر أحدهما الآخر يعيشان أطولَ من عطبٍ مفرد (قرارُ المالك 2026-08-24) → `GUARDS.md`
- **والسترُ يتراكم طبقاتٍ لا طبقةً واحدة** (تصحيحُ المالك 2026-08-24) → `GUARDS.md`
- وأثرُها في السجلّ: ما شهد به الساترُ يُشطب (قرارُ المالك 2026-08-24) → `GUARDS.md`
- قيمةٌ من العالم الحقيقيِّ يقرؤها اختبارٌ لا يملكها — توافق جهازاً وتخالف آخر (قرارُ المالك 2026-08-24) → `GUARDS.md`
- وأربعُ طبقاتٍ نُزلت في يومٍ واحد (2026-08-24) → `GUARDS.md`
- وتساوي الأعداد ليس تساويَ الأسباب (قرارُ المالك 2026-08-24) → `GUARDS.md`
- وحالُ الإنتاج لم تكن مشتقّةً من git يوماً — والبوّابةُ الرابعةُ تصف ما ليس كذلك منذ كُتبت (قرارُ المالك 2026-08-22) → `GUARDS.md`
- وحالُ ملفٍّ تعتمد على إعدادٍ يأتي مع السحب — فتُقاس بعده لا قبله (قرارُ المالك 2026-08-22) → `GUARDS.md`
- ومفتاحٌ مبذورٌ بلا زرّ: ميزةٌ لا يعرف بها إلا من كتبها (قرارُ المالك 2026-08-23) → `GUARDS.md`
- ومفتاحٌ بُني ليوقف الأذى **ولا يُطفأ** — بابٌ بلا زرّ في اتجاهٍ واحد (قرارُ المالك 2026-08-24) → `GUARDS.md`
- وزرٌّ يكتب مسارَه بيده يقفز فوق `check:contract` (قرارُ المالك 2026-08-23) → `GUARDS.md`
- وثلاثُ تسمياتٍ لشيءٍ واحد — من عائلة `detail` (قرارُ المالك 2026-08-23) → `GUARDS.md`
- و«أثمّة قيمةٌ مخترعة؟» ليست «أينقص عضو؟» — سؤالان لحارسٍ واحد (2026-08-23) → `GUARDS.md`
- وشكلان لشيءٍ واحدٍ — لا يمسكهما اختبارُ البابين لأنهما ليسا بابين (قرارُ المالك 2026-08-23) → `GUARDS.md`
- وتثبيتٌ يثبّت العقدةَ لا المسار — فحاويةٌ تخدم مجلَّداً محذوفاً (2026-08-22) → `GUARDS.md`
- ومسارُ نشرٍ جديدٌ لا يُصدَّق حتى يمرّ مرتين (قرارُ المالك 2026-08-22) → `GUARDS.md`
- ولا يُسأل عن وجود سرٍّ بصيغةٍ قد تطبعه (2026-08-22) → `GUARDS.md`
- وحقلٌ يقيس أن مفتاحاً **مكتوب** لا أن ملفاً **موجود** (قرارُ المالك 2026-08-22) → `GUARDS.md`
- وشرطٌ لا يتحقّق أبداً يُقرأ حراسةً وهو تعطيل (قرارُ المالك 2026-08-22) → `GUARDS.md`
- وغيابُ أداةِ القياس يوقف ولا يُقرأ سلامة (قرارُ المالك 2026-08-21) → `GUARDS.md`
- وحارسٌ يُشغَّل حيث لا يملك ما يقيسه يعلن «لم يُقس» لا «سليم» (قرارُ المالك 2026-08-21) → `GUARDS.md`
- وتوثيقٌ يصف ما ليس كذلك من عائلة الجدول الأحمر (قرارُ المالك 2026-08-21) → `GUARDS.md`
- وخبرٌ في هذا الملفّ يُقرأ حالاً قائمة — فيحمل حالَه وتاريخَه أو يُحذف (قرارُ المالك 2026-08-23) → `GUARDS.md`
- وقبل أن تحذف نصّاً كذب: أخبرٌ هو أم درس؟ (قرارُ المالك 2026-08-22) → `GUARDS.md`
- وشرطٌ زالت علّتُه ولم يُنزَع يمنع ما وُضع ليحرسه (قرارُ المالك 2026-08-21) → `GUARDS.md`
- وتعليقٌ يَعِد بما سيأتي لا يُقرأ ضماناً (قرارُ المالك 2026-08-21) → `GUARDS.md`
- وعقدٌ يُجمَّد ناقصاً ليس عقداً (قرارُ المالك 2026-08-22) → `GUARDS.md`
- وأربعةُ وكلاءَ في نسخةِ عملٍ واحدةٍ ليسوا أربعة (تجربةٌ مقيسة 2026-08-22) → `GUARDS.md`
- وما بدأناه لا يُبقى لأنه بدأ (قرارُ المالك 2026-08-22) → `GUARDS.md`
- قاعدةُ كلِّ حارس (قرارُ المالك 2026-08-20) — تُقرأ قبل الفهرس لا بعده → `GUARDS.md`
- الشكلُ الثالثَ عشر — رسمُ مالٍ يُحصَّل من جيبِ راكبٍ ولا يظهر على أيِّ شاشة (2026-08-21) → `GUARDS.md`
- وحارسُه: ما يمسكه وما **لا** يمسكه — يُقرأ قبل أن يُصدَّق → `GUARDS.md`
- وقد بُني (2026-08-21) — **وأولُ نسخةٍ منه كانت خضراءَ وهي عمياء** → `GUARDS.md`
- ب) ما بقي **شرطاً بشرياً** — ولا يُبنى له حارس، بقرار → `GUARDS.md`

- وبتُّ تنفيذٍ لا يسجّله الفهرس يُسقط خطّافاً في لينكس صامتاً (قِيس 2026-09-03) → `GUARDS.md`
- وحارسٌ خارجَ البابِ الواحد ليس حارساً — **مرّتان في يومين** (قِيس 2026-09-03) → `GUARDS.md`
- وقراءةُ حالةٍ غيرِ متعقَّبةٍ: موضوعُ السؤال لا مهربٌ منه (جُرد 2026-09-03) → `GUARDS.md`
- وجردُ البابِ الواحد — ثلاثةٌ خارجَه، ولا واحدَ منها يستحقّ الدخول (قِيس 2026-09-03) → `GUARDS.md`

### `PATTERNS.md` — الأشكال

- القياسُ الصادقُ لا يأذن بفعلٍ خارج نطاقه (2026-08-25) → `PATTERNS.md`
- وللعائلة وجهٌ خامس — **حاويةٌ تخدم `dist` والمصدرُ يتغيّر تحتها** (قِيس 2026-08-26) → `PATTERNS.md`
- متغيّرٌ واحدٌ في كلِّ مرّة — لا فعلان يمسّان سطحاً واحداً في يوم (2026-08-25) → `PATTERNS.md`
- الشكلُ السادسَ عشر — **اسمٌ يُبحث عنه نصّاً، ونداءٌ بمفتاحٍ متغيّر** (2026-08-25) → `PATTERNS.md`
- «An empty map is not a defect» — the three points, in order (2026-08-15) → `PATTERNS.md`
- The twelfth shape — a fallback that works, and hides the defect it was built for (2026-08-19) → `PATTERNS.md`
- الشكلُ الثامنُ في ثوبٍ ثالث — **موضعان يحسبان قيمةَ مالٍ واحدة، وحدٌّ في أحدهما** (2026-08-23) → `PATTERNS.md`
- الشكلُ الرابعَ عشر — **سطحٌ تُفحص أطرافُه ولا يُسأل: أيتحدّث؟** (2026-08-23) → `PATTERNS.md`
- الشكلُ الخامسَ عشر — **حارسٌ صادقٌ تُوسَّع دعواه فوق نطاقه** (2026-08-23) → `PATTERNS.md`
- الشكلُ الثالث عشر — **التمييزُ المرئيُّ وشايةٌ ولو بدا تحسيناً** (2026-08-22) → `PATTERNS.md`
- The eleventh shape — an obstacle that exists only on a device (2026-08-19) → `PATTERNS.md`
- The tenth shape — a green build guard says nothing about what the user is running (2026-08-19) → `PATTERNS.md`
- ⚠ وخُضرةُ CI **لا تحرس الشكلَ العاشر أصلاً** (قرارُ المالك 2026-08-24) → `PATTERNS.md`
- The tenth shape's newest face — two columns for one product, and one lags in silence (2026-08-21) → `PATTERNS.md`
- The tenth shape, three times — and why step zero is now three-way → `PATTERNS.md`
- `save()` announces success only after it sees the file (2026-08-20) → `PATTERNS.md`
- The tenth shape has a sibling on the server — writing a setting is not the setting taking effect (2026-08-20) → `PATTERNS.md`
- Step zero for every phone round — prove the artifact before measuring anything → `PATTERNS.md`
- The ninth shape — an intermediate step no human has ever pressed (2026-08-19) → `PATTERNS.md`
- The eighth shape — two doors publishing the same thing, each honest alone (2026-08-19) → `PATTERNS.md`
- The seventh shape — a money amount that serialises as `"0"` instead of `"0.000"` (2026-08-19) → `PATTERNS.md`
- The sixth shape — a success criterion measuring an event the system never emits (2026-08-18) → `PATTERNS.md`

### `STATE.md` — حالُ البناء

- Where the project stands → `STATE.md`
- The batch of six is built and committed (`eac926e`, 2026-08-15) — and four things remain → `STATE.md`
- The cancellation fee: what is built, and the four things left → `STATE.md`
- The four that remained are built (2026-08-15, second session) — and one item is deferred by a decision → `STATE.md`
- Three things the build itself taught, all worth keeping → `STATE.md`
- What stands between here and launch — the whole list, in order (2026-08-18) → `STATE.md`
- 0. The cancellation fee is finished — one sub-item waits on an owner decision → `STATE.md`
- 1. Blocking, and not code → `STATE.md`
- 2. ✅ Backups — **built end to end** (2026-08-16) → `STATE.md`
- 3. The three registered specs, in the owner's order → `STATE.md`
- 4. ✅ «افتح في خرائط قوقل» — **built** (2026-08-16) → `STATE.md`
- 5. The map work — **1–4 built, 5–6 remain** (2026-08-16) → `STATE.md`
- 6. The unplanned stop point — built, all six branches (2026-08-16, SPEC §5.10-ب) → `STATE.md`
- 7. ✅ Subscription offers — **built end to end** (2026-08-19, `design/SUBSCRIPTION-OFFERS.md`, `FUTURE-FEATURES` 54) → `STATE.md`
- The Jordan channel is the launch blocker, not Libya (2026-08-19) → `STATE.md`
- The dev stack has been mutated by the scenarios — do not read it as the intended state → `STATE.md`
- Subscription offers (item 54) — built end to end (2026-08-19) → `STATE.md`
- Stage 13 — the full manual run on two phones (2026-08-15) → `STATE.md`
- The cash-payment round trip, measured on both phones (2026-08-15) → `STATE.md`
- Item 15 — driver advances, the first money the platform lends (2026-08-14) → `STATE.md`
- The queue the owner set (2026-08-13), in order → `STATE.md`
- The splash screen and the app icons → `STATE.md`
- Stage 13 — the trial run, and what only a real ride could show (2026-08-14) → `STATE.md`
- The device trial list, items 7 and 8 (2026-08-14) → `STATE.md`
- The floating bottom bar, and three defects the browser found (2026-08-13) → `STATE.md`
- Rider design-matching: five packages, all delivered → `STATE.md`
- Open debt and decisions waiting on the owner → `STATE.md`
- متجرُ المركبات — أيقظت السلسلةُ الخمس (2026-08-27) → `STATE.md`
- البند ٦ — مسارُ الرحلة النشطة في ملفِّ الكبتن، **مبنيٌّ ومقيس** (٢٠٢٦-٠٩-٠٣) → `STATE.md`
- البند ٨ — لوحةُ الإصدارات والتحديثُ الإلزاميّ، **مبنيٌّ ومقيس** (٢٠٢٦-٠٩-٠٣) → `STATE.md`
- البندان ٩ و١٠ — **الإعلانُ مبنيٌّ سلفاً، والسياساتُ سُلِّمت مسوّدة** (٢٠٢٦-٠٩-٠٣) → `STATE.md`
- البند ١١ — التحكّمُ بالمستخدمين والتواصلُ الفرديّ، **مبنيٌّ ومقيس** (٢٠٢٦-٠٩-٠٣) → `STATE.md`
- بندُ التسهيل — **الفروعُ السبعة، وثلاثةُ بنودٍ وُلدت منه** (٢٠٢٦-٠٩-٠٣) → `STATE.md`
- ما بُني وقِيس → `STATE.md`
- وعطبان أمسكهما أوّلُ تشغيلٍ للاختبار الجديد — **ولم يكن ليُمسكهما قياسٌ يدويّ** → `STATE.md`
- وثلاثةُ بنودٍ مستقلّةٍ وُلدت منه — **تُقرأ بنوداً لا نواقص** → `STATE.md`
- ⚠ وما لم يُقَس — ولا يُقرأ سلامة → `STATE.md`

- النقلُ إلى داخل WSL — ما قِيس قبل وبعد (٢٠٢٦-٠٩-٠٣) → `STATE.md`
- اعتمادُ الشجرة الجديدة — الحاوياتُ والنفقُ تحوّلا، والأعمدةُ الثلاثة (٢٠٢٦-٠٩-٠٣) → `STATE.md`

### `ARCHITECTURE.md` — المعمار

- Country visibility — one flag per market, and Libya is its first use (2026-08-19) → `ARCHITECTURE.md`
- The error contract — one body shape, and the 422 that had no handler at all (2026-08-18) → `ARCHITECTURE.md`
- The app switch — a handoff token, and the busy check that could not ask its own question (2026-08-19) → `ARCHITECTURE.md`
- The rule that dissolves the ambiguities: context of the act, not role of the actor (2026-08-19) → `ARCHITECTURE.md`
- The roles model became a set — and the dangerous half was never authorisation (2026-08-19) → `ARCHITECTURE.md`
- وصار بابان يقرنان هويةً بموقع لا باب — **وسطران فوق هذا بليا** (2026-09-03) → `ARCHITECTURE.md`
- Architecture → `ARCHITECTURE.md`

### `COMMANDS.md` — الأوامر

- Commands → `COMMANDS.md`
- Five accounts exist on the dev stack, and the visual checks need them → `COMMANDS.md`
- بعد كلِّ إقلاعٍ للآلة: النفقُ لا يعود وحدَه — **`docker start` لا `compose up`** (قرارُ المالك ٢٠٢٦-٠٩-٠٣) → `COMMANDS.md`
- ⚠ و`docker start` لا `docker compose up` — **والعلّةُ مقيسة** → `COMMANDS.md`
- والتحقّقُ ثلاثةُ أسطرٍ لا واحد → `COMMANDS.md`
<!--/جديد-->
<!--جديد-->
- ومن داخل WSL — أربعةُ فخاخٍ وقعت مقيسةً (٢٠٢٦-٠٩-٠٣) → `COMMANDS.md`
- ونقلُ الحاويات إلى شجرةٍ لينكسيّة — ثلاثةٌ تُقرأ قبل أوّل `up` (٢٠٢٦-٠٩-٠٣) → `COMMANDS.md`
<!--/جديد-->
### أ) دروسٌ صارت حرّاساً — تُقرأ من الحارس لا من هنا

| الدرس | الحارس |
|---|---|
| صنفٌ خارج سلّم البكسل يُصرَّف بلا أثر | `check:scale` |
| اتحادُ سلاسلَ يخالف تعدادَ الخلفية، **أو يخلط قيمةً مخترعةً بحقيقية** | `check:enums` (وقائمةُ `UI_UNIONS` تُصرَّح بأسبابها) |
| خانةٌ عربية-هندية في نصٍّ معروض، أو مُنسِّقٌ بلا لغةٍ مثبَّتة | `check:digits` + `tests/digit_format.py` |
| `asChild` بأكثرَ من ابنٍ واحد — يُفرِّغ الشاشة | `check:slot` |
| مفتاحُ ميزةٍ بلا زرّ — **وحارسٌ لا يعرف زرُّه أنه حارس** | `check:flags` (ثلاثُ مرايا: الاتحاد · المرسومة · **مجموعةُ الحرّاس في الاتجاهين**) |
| حقلٌ تنشره الخلفيةُ بلا مرآة، أو مرآةٌ بلا مُرسِل | `check:config` |
| مسارٌ إداريٌّ بلا زرّ («بابٌ بلا زرّ») | `check:doors` |
| نداءٌ من تطبيقٍ بلا **فعلٍ ومسارٍ** في الخلفية | `check:contract` |
| **حسابُ مالٍ في الواجهة** — و§14 يحصره في الخلفية | **`check:money-math`** — يقرأ العُقَدَ بمُحلِّل TypeScript لا بالنصّ، **ويجيب الشقَّ الأول وحدَه**: «أثمّة حساب؟» لا «أصحيحٌ هو؟». وثلاثُ فجواتٍ مكتوبةٍ بعللها |
| **قيمةُ مالٍ تحسبها الخلفيةُ ولا تصل أيَّ واجهة** (الشكلُ الثالثَ عشر) | **`check:money-visible`** — ومفرداتُ المال من بيتها الواحد في `tests/money_format.py`، **ولا يمسك «تُقرأ في الشاشة الخطأ»** ويقول ذلك |
| حزمةٌ تخالف هدفَها أو فيها عنوانٌ محلّيّ | `check:target` + `check:dist` |
| مبلغٌ يُسلسَل «0» لا «0.000» (الشكلُ السابع) | `tests/money_format.py` |
| نموذجٌ يفترق عن ترحيلته | `tests/test_migrations.py` |
| **تشغيلُ اختباراتٍ شاردٌ يمسك `taxo_test`** | **`scripts/suite.sh`** — بابٌ واحدٌ للمجموعة، يرفض قبل أن يبدأ ويسمّي الحاوية |
| **حزمةٌ تُخدَم غيرُ التي بُنيت** (البند ١) | **`check:served`** — ثلاثةُ أعمدة: المبنيُّ · المحلّيُّ · النفق. **ولا يقيس الهاتف** ويقول ذلك. **⚠ ولا يقيس شيئاً في CI البتّة** — انظر أدناه |
| **حافةٌ تخدم نسخةَ أمس والأصلُ صحيح** (العمودُ الخامس) | **`landing/nginx.conf`** عند الأصل، و`tools/check-apk.mjs` **يقرأ من الحافة لا من القرص** |
| **مبلغٌ بعلامةٍ محلولةٍ مرتين فيُطبع عارياً** (البند ٥) | **`check:money`** — يرفض `money(…, currencyLabel(…))` و`CURRENCY_LABEL[…]` |
| **قفلُ صفٍّ بلا اختبارِ تزامن** (البند ٢) | **`tests/test_locks_have_tests.py`** — ولا يفحص أن الاختبارَ يسقط بحذف القفل، **ويقول ذلك**: يبقى شرطاً بشرياً |
| **مساعدُ اختبارٍ يختصر مساراً حقيقياً** (البند ٨) | **`tests/test_no_shortcut_fixtures.py`** — ومفتاحُ الاستثناء `ملف:سطر` فنقلُ البناء يُظهره من جديد |
| **غلافٌ يشير إلى غير هدفه — حزمةٌ عامةٌ تخاطب جهازَ تطوير** | **`check-apk.mjs`** — يقرأ `server.url` **من داخل الحزمة** لا من الشجرة، و`SHELL_TARGET` **يُصرَّح**: غلافٌ بلا هدفٍ مكتوبٍ يُسقط الفحص. والقاعدةُ كانت في المواصفة §18.1 مع اعترافها: «لا اختبارَ يفشل» |
| **مفاتيحُ سوقٍ في بيئةٍ منشورة تفترق عمّا يُشحن — أو سوقٌ يشترط التحقق بقناةٍ ميتة** | **`scripts/check-markets.sh`** — مرجعُه `FEATURE_DEFAULTS` **لا جهازُ التطوير** (المقارنةُ بالتطوير أخرجت ١٢ سطرَ ضجيجٍ من ١٣)، ويُقرأ من الوحدة التي تشحنه. **وقاعدتُه الأولى لا تحتاج بيئةً ثانية** |
| **فخُّ حاويةٍ: صورةٌ أقدمُ من تبعياتها، أو خلفيةٌ بلا نطاقات النفق** (البند ١٠) | **`scripts/check-stack.sh`** — **ولا يفحص المِرآة/inotify**، ويقول ذلك |
| **تسميةُ خطأٍ بلا تصنيفِ جنس** (البند ١٢) | **`tests/test_label_gender.py`** — والمذكَّرُ لم يعد افتراضاً صامتاً |
| **جملةٌ مؤلَّفةٌ داخل `data` الإشعار** (البند ١١) | **`tests/test_notification_data.py`** — يمسح الشجرةَ لا الاستجابة، و`title`/`body` وحدَهما مستثنيان لأن النظامَ يرسمهما |
| **حقلٌ يُحسب في `lib/` ولا يقرؤه أحد** (البند ٤) | **`check:readers`** — ويبلّغ عن **المنسيِّ لا عن المُمرَّر جملةً**: كائنٌ لا يُقرأ منه شيءٌ يُسلَّم إلى مكتبة، وكائنٌ تُقرأ بعضُ حقوله ويُهمل بعضُها هو العطب |
| **بابان ينشران الشيءَ نفسَه ويفترقان** (البند ٣) | **`tests/test_two_doors.py`** — يقارن الردَّين **حقلاً حقلاً**، ويُجبر كلَّ حمولةٍ متعددةِ الأبواب تحمل حقولاً محسوبةً على تصنيفٍ بعلّته |

<!--جديد-->
**وحارسان أُضيفا 2026-08-31 — تفصيلُهما في `GUARDS.md`:**

| الدرس | الحارس |
|---|---|
| **حقلٌ في العقد تكتبه الشيفرةُ ثابتاً فلا يملك المشرفُ ضبطَه** — «بابٌ بلا زرٍّ يُرى فارغاً، **وحقلٌ محشوٌّ يُرى عاملاً**» | **`check:fields`** — يقرأ حرفيّاتِ أبواب الكتابة بمُحلِّل TypeScript، **وكلُّ ثابتٍ يحمل علّتَه**. ولا يمسك المفتاحَ المحسوب، **ويقول ذلك** |
| **بطاقةٌ منسوخةٌ ثلاثاً تفترق — فمعاينةُ اللوحة تَعِد بشكلٍ لا يقع** | **`check:storefront-card`** — تطابقُ التطبيقين بايتاً، وبصمةٌ مصرَّحةٌ في المعاينة. **ولا يقيس التطابقَ البصريّ**، ويقول ذلك |
<!--/جديد-->

> **وأولُ تشغيلٍ لحارس البند ٣ أمسك عطباً كُتب قبل ساعاتٍ في اليوم نفسِه**
> (2026-08-20): `commission_percent` مُلئ في باب الكبتن ونُسي في باب اللوحة.
> **فالشكلُ الثامن تكرّر ومعه حارسُه في يومٍ واحد** — وهذا هو الدليل: **الحرّاسُ
> تُبنى لما يقع لا لما وقع.** من يقرأ فهرساً كهذا يظنّه سجلَّ أخطاءٍ ماضية،
> وهو في الحقيقة قائمةُ ما سيقع ثانيةً — وقد وقع أحدُها قبل أن يجفَّ حبرُ حارسه.
>
> **وثلاثةُ قراراتٍ أقرّها المالك في اليوم نفسِه لأنها تتكرّر:** المعالجةُ
> **بالبانِي الواحد لا بالحقل** (إصلاحُ الحقل يترك البابَ الثالثَ بلا شيءٍ
> يجده غداً)؛ **وتضييقُ المسح** إلى ما يحمل حقولاً محسوبةً — قائمةٌ بطول خمسين
> تصير طقساً يُمرّ عليه؛ **واستثناءُ ما يصيح على السليم** (`money(value)` بلا
> عملة) — حارسٌ يصيح على سليمٍ يُطفأ، فيسقط معه ما يمسكه حقاً.

**وسطرٌ من واقع 2026-08-20 يخصّ التعديلَ الآليَّ نفسَه**: **الحذفُ بمطابقةٍ
نصّيةٍ على كودٍ متعددِ الأسطر يُتلف.** عدُّ أقواسٍ ساذجٌ لحذف دالّةٍ قطع توقيعاً
يمتدّ على سطرين ونوعُ عودته يحمل `{`، فترك `validation.ts` نصفَ ملف.
**والمُحلِّلُ هو الأداة** — `ts.createSourceFile` يعطي مدى العقدة بحدّه، ومعه
تعليقُه السابق. **وgit هو ما أنقذ**: `git checkout --` أعاد الملفَّ في ثانية.
فأيُّ كنسٍ عريضٍ لاحقاً **يبدأ من شجرةٍ نظيفةٍ مودَعة**، لا من شجرةٍ فيها عملُ
ساعةٍ لم يُلتزَم.

<!--جديد-->
## الوقوفُ للضرورة لا للاستئذان (قرارُ المالك 2026-08-28) — **تحكم متى تقف لا ما تدّعيه**

**الأصلُ أن تمضيَ إلى آخر ما أُمرتَ به وتجيبَ دفعةً واحدة.** ولا تقف إلا عند
**واحدٍ من ثلاثة**:

1. **شيءٌ يضيع بلا نسخة** — حذفٌ لا رجعةَ فيه، أو محوٌ لما لا نسخةَ له.
   **ووقعت**: رقعتان فيهما حزمتان ثنائيّتان لا نسخةَ لهما، **وصفرُ سطرٍ ضائعٍ
   كان سيُقرأ إذناً بمحوهما**.
2. **بوّابةٌ تسقط بنصّ** — **لا بانقطاع قناة**. **وصفرُ نصِّ وقوفٍ يعني أن
   بوّابةً لم تحكم**. **ووقعت**: `ssh` انقطع فبدا وقوفاً وليس به.
3. **أو فعلٌ ثانٍ يمسّ السطحَ نفسَه في الجولة نفسِها** — فلا يُعرف أيُّهما سببُ
   العطب.

**وما عدا ذلك يُكتب بنداً في `STATE.md` ويُمضى**: عطبٌ جانبيّ، حارسٌ ناقص، رقمٌ
لا يعجبك، فرصةُ تحسين، شيءٌ تراه ولم تُؤمَر به.

**ولا تقف لتستأذن في المضيّ، ولا لتعرض ما ستفعله، ولا لتسأل عمّا يجيبه
القياس. اقِس ثم امضِ.**

> **وحدُّ القاعدة مكتوبٌ فيها**: **هي تحكم متى تقف، لا ما تدّعيه.** ما لم
> يُقَس **يبقى غيرَ مقيسٍ ويُقال كذلك** — **والمضيُّ ليس إذناً بأن تقول «تمّ»
> عمّا لم تُثبته**. فالقاعدةُ تُسقط الوقوفَ الزائد، **ولا تُرخّص دعوى**.

<!--/جديد-->

### When to stop and ask — the owner's rule, restated (2026-08-20)

**Stopping is expensive and it was being overused.** The rule the owner set, verbatim in effect:

**Stop only for:**
- a **model or architecture** decision;
- a **conflict with SPEC**;
- something touching **someone else's money or safety** that he has not settled;
- **two options whose effect on the user genuinely differs**;
- a **secret or account only he can supply**;
- something that **needs his finger on a phone**.

**And probing a live auth door spends the human's budget, not yours** (measured 2026-08-21).
Proving the production admin credentials worked cost two of the owner's five attempts in a
five-minute window — and he hit «محاولات كثيرة» on his own next try. The probe was correct and
the finding was true; what was missing was **counting the cost of the measurement itself**.

Before driving a rate-limited path on a system a person is using: know the cap and the window
first, and prefer a probe that does not consume the same bucket — a different identity, a read
that answers the same question, or asking the person to try once while you watch. **`login:ip:`
is a separate bucket from `login:username:`**, so where the answer only needs "does this
credential authenticate", one attempt is the budget, not two.

**And a notice is not an order** (the owner's rule, 2026-08-21). What he tells you — a fact,
a constraint, a piece of context — is **information he is planning with**, not an instruction to
act on. The judgement on it is **his**. So when something you learned (or reported) implies an
action that **disables a feature, hides a surface, or narrows what a user can do**, *ask before
doing it* — even when the action looks obviously protective, and even when you are the one who
found the problem.

**It happened measured**: the packages on the public page point at a developer tunnel and carry a
debug signature. That is a true finding and it was right to report it. Turning it into "so the
download buttons come down" was **a decision presented as a consequence** — and the owner's actual
call was the opposite: keep the buttons, **say the cost in one sentence, and let whoever downloads
decide knowing it**.

**Read the asymmetry**: withholding a working feature to avoid a risk the owner has not weighed is
not the safe side of the choice — it is *making* the choice while appearing not to. Reporting costs
one paragraph; disabling costs the feature, and it is invisible to whoever expected it to be there.

**Never stop:**
- to present a table — put it in the report and carry on;
- to get permission to fix a defect you found;
- to confirm a condition he already recorded;
- to announce that you are about to begin;
- for a question that **measurement settles**: if you measured and one reasonable answer stands, do it
  and write down why.

**And two rules about the shape of stopping**, both of which cost this session real time:

1. **When you stop, stop on the decision alone** — and keep going on everything that does not depend on
   it. A blocked question is not a blocked session.
2. **Batch the questions.** Never ask one, stop, then ask another next turn. Finish everything you can
   and put every open question in **one** report — especially the phone-round items, which the owner
   should be able to do in a single sitting.

**And the boundary of "money" was corrected**: *"a money item is presented, not executed"* covers money
that **enters or leaves someone's pocket** — pricing, commission, discounts, payouts, refunds. It does
**not** cover the owner's own running costs. Disk, server bills, storage caps: **measure, decide,
execute, and say so in the report.**

## Project rules that override defaults

**`SPEC.md` is the single source of truth.** It is written in Arabic and defines every table, flow,
and constraint. If a requirement is ambiguous, ask before implementing. Do not add features it does
not describe.

**When you deviate from `SPEC.md` for a justified reason, update `SPEC.md` in the same session,
before the commit.** A deviation that outlives its session stops being a decision and becomes a
discrepancy nobody can tell from a bug.

**Section 16 of SPEC.md is a strict, ordered 13-stage plan — one stage per session.** Stages 1
(infrastructure, FastAPI skeleton, Alembic, `users`/`drivers`/`vehicles`, phone+password auth with
JWT), 2 (per-country settings tables, encrypted `provider_credentials` with admin CRUD, seed
script, `GET /config`), 3 (`rides`, Mapbox Directions pricing, request/status endpoints), 4
(Redis GEO presence, dispatch algorithm, WebSocket tracking and ride events), 5 (the
`wallet_transactions` ledger, rider topup/transfer, driver wallet and withdrawals), **6-أ**
(`payments` with cash/manual-CliQ/wallet/mixed and disputes, `ride_route_points` with `final_fare`
recalculation, `ratings`), **6-ب** (Telr card integration — `provider_orders`, hosted payment
page, signed webhook, instant card wallet topup, `saved_cards` tokenization and one-tap pay,
provider-side refunds), **7** (`driver_subscriptions`, purchase over all four channels, the
dispatch subscription check, and the Celery sweep), **8** (the full contracts page with test
connection, unified provider interfaces with mocks, and the OTP/Push/automatic-CliQ/payout
integrations), **9** (`customer-app/` — the rider PWA, plus the in-app CliQ payment page and the
backend fields it needed) and **9-ب** (backend only: driver-document upload/review on the
long-dormant `driver_documents` table, `core/storage.py`, and the `user_notifications` inbox
written from both send doors) are complete. **Stage 11 (the admin panel, `admin-panel/`) has begun** — shell, login, live map, drivers/documents,
finance (withdrawals and CliQ topups), disputes, campaigns, per-country settings and the provider
contracts page. The overview sits on `services/stats.py`, where three rules live: **aggregation happens in
the backend, full stop** — the same reasoning §14 applies to money, because a panel that sums rows
itself shows a number that disagrees with the database the moment a page is truncated; **"today" is
the country's day**, computed in the timezone stored on `notification_settings` (a UTC server
otherwise clips three hours off the start of an Amman day and adds three from yesterday); and
**"online now" counts live presence keys in Redis, not `drivers.is_online`** — the column says "the
switch is up", not "he is here", so an app killed mid-shift keeps its column raised until the key
expires.
**Stage 10's screens (the driver PWA, `driver-app/`) are
complete** — login/recovery, three-step registration, home with the offer card and active ride,
collect/rate/subscription, the ride log with details and dispute, the wallet with its withdrawal
sheet and request list, the account tab with settings/vehicle/cards, the notifications inbox and
the CliQ confirmation card. Do not implement
anything from a later stage unless the user asks for that stage. When a later-stage concern
appears in current code (e.g. no Celery job sweeps stale
`provider_orders` yet, no retention sweep trims `user_notifications`, and the campaigns page in the
admin panel lands in stage 11 while its endpoints already exist), leave a comment naming the stage
rather than building ahead.

**Any path that changes a row's status locks that row with `for_update` *before* it checks the
transition.** Reading the row, validating `current → target`, then writing is not atomic on its own:
under Postgres' READ COMMITTED default, concurrent requests all read the same pre-commit status,
all pass the check, and all report success. Load the row with `select(...).with_for_update()
.execution_options(populate_existing=True)` — see `topups.get_request` / `withdrawals.get_request`
(`for_update=True`) and `rides.cancel_ride` (`session.refresh(..., with_for_update=True)`).

**Lock order is always: the ride row, then the request/payment row, then the provider-order row,
then the driver row, then the cancellation-charge row, then the wallet advisory lock.** Every mutating path takes them in that order,
which is why nothing deadlocks. **Two paths let the driver himself drop his own approval —
replacing a required document and editing a vehicle's identity fields — and both re-read
`drivers.status` under `drivers_service.lock` (a `refresh(..., with_for_update=True)`), never from
the object the router handed them.** What that lock owns is not duplicate work but a **cancelled
suspension**: an admin suspending a driver at the moment he changes his plate would otherwise have
`suspended` overwritten by a `pending` computed from an `approved` read before it, putting a
suspended driver back in the review queue — one approval away from working again.
`test_vehicle_update_concurrency.py` drives exactly that interleaving and fails when the lock is
deleted. In `documents.upload` the lock is taken **after** the document row's, not before, because
the driver row must not be held across an upload whose length the client dictates. Creating payments locks the ride (`payments._payable_ride`) so two
concurrent requests cannot both read the same outstanding amount; every status change locks its own
row (`topups`/`withdrawals.get_request`, `payments.get_payment` with `for_update=True`,
`rides.cancel_ride`); `card_payments._locked_order` locks the payment *before* the
`provider_orders` row, because the admin refund path starts from the payment and then needs its
provider order — reversing either side would deadlock the two against each other; buying a
subscription locks the driver row (`subscriptions._locked_driver`) before reading how far the
driver's coverage already extends, so two concurrent purchases produce consecutive periods rather
than two payments for one month — and the card path takes that lock *after* the provider-order row
because a webhook starts from the order; ledger writes take the wallet lock last. No path takes a
payment row lock and then a ride lock. When a single operation touches two wallets, their advisory
locks are taken in sorted UUID order (`wallet._lock_wallets`). Adding a new lock means fitting it
into this order, not inventing a second one.

The cancellation-charge row sits between the driver row and the wallet locks, and **all three of its
paths enter from above it**: `collect_with_ride` from inside `payments.settle` (ride → payment →
charge → wallets), `on_wallet_funded` from a topup (no ride, no payment), and the panel's waive /
write-off from the charge itself. Its lock is taken **before** the status is checked, like every other
status change: without it two concurrent waives both read `pending` and one writes "waived" over a
collection that already moved money out of a rider's wallet.

Stage 8 added two mutating paths and both fit the same order. `cliq_topups.apply_state` locks the
provider-order row and then takes the wallet advisory lock (no ride and no payment row exist on a
wallet topup), and asks the acquirer *before* any lock in `reconcile`. `withdrawals.pay_via_provider`
is the deliberate exception to "never hold a row lock across a provider call": the call itself moves
the money, so it cannot run first — two concurrent clicks without the lock are two transfers, and the
lock's scope is one withdrawal row with a capped timeout.

Note which guard actually protects what: the driver row lock is redundant on the wallet purchase
path (the wallet advisory lock already serialises it) and is the *only* guard on the manual and
card paths, which write no ledger entry at all. That is why the concurrency test for it fires two
`POST /admin/subscriptions` at once rather than two wallet purchases — deleting the lock leaves the
wallet test green and turns the manual one's two consecutive periods into two identical ones.

**Never hold a row lock across a provider HTTP call when the call can happen first.**
`card_payments.reconcile` asks the provider *before* taking any lock, then applies the answer under
it: two concurrent settlements each spend one harmless extra `check` instead of one waiting out the
other's 20s network round-trip. Where the call genuinely must run inside the lock (opening an order
under the ride row lock in `card_payments._start`), the lock scope is a single ride and the timeout
is capped in `card_gateway/base.py`.

Do not let an idempotency key stand in for either lock. It bounds the financial damage, but a guard
that only works because the guard behind it also fired is a guard that has already failed — and
this exact defect shipped in stage 5 and was caught only by a concurrency test. Verify the tests
you write for a new lock by deleting the lock and watching them fail: dropping `with_for_update()`
from payment confirmation turns `Counter({200: 1, 409: 2})` into `Counter({200: 3})` while the
ledger still shows one entry, which is precisely the failure a passing sequential test would hide.

**A stage that touches money or state transitions is not done without a concurrency test.**
Sequential request-then-assert tests never enter the code path the locks exist for, so they prove
nothing about them. And write the test against the invariant the lock actually owns. Three concurrent `GET
/wallet/me/topups/cliq/{cart}` calls credit the wallet once *even with the row lock deleted* — the
ledger idempotency key and the wallet advisory lock already cover that — so that assertion proves
nothing about the lock. What the row lock alone owns is the order's **status**: `test_stage8_
concurrency.py::test_two_provider_answers_at_once_leave_a_coherent_order` drives a paid and a failed
settlement into a deliberately ordered interleaving (the first holds its transaction open while the
second starts) and asserts `paid ⇔ exactly one ledger entry`, `failed ⇔ none`. Delete the
`for_update` and it fails with a `failed` order whose money was credited.

Fire the requests together with `asyncio.gather` against the `client` fixture
(same event loop, separate session and transaction per request, so one really waits on the other's
lock in Postgres) and assert the invariant, not the timing: exactly N of M succeed, the losers carry
the *specific* error code, the ledger sum read straight from the database matches, and no
`balance_after` is negative. For deadlock, wrap the gather in `asyncio.wait_for` — a deadlock hangs
rather than raising, so only a timeout can fail the test. `tests/test_wallet_concurrency.py` is the
model to copy.

**User-facing strings, comments, and docs are in Arabic.** Identifiers stay English. Match this.

## Invariants from SPEC.md that constrain future stages

- Money columns are `NUMERIC(12,3)`. Never float.
- Provider API keys (Mapbox, Telr, SMS, FCM, payout) belong in the encrypted `provider_credentials`
  table managed from the admin "contracts" page — never in `.env` or code. `.env.local` holds only
  infrastructure secrets (DB, Redis, JWT, the Fernet key); its Mapbox/Telr tokens exist solely as
  input for `scripts/seed.py`, which writes them encrypted and is idempotent.
- Wallet balance is derived from the immutable `wallet_transactions` ledger. There is no balance column.
- Riders top up and transfer but **never** withdraw (SPEC section 7); only drivers have a withdrawal path.
- Pricing and all financial math happen in the backend only; the frontends display.
- `rides.commission_percent_at_ride` is frozen at creation and never recomputed retroactively.
- `saved_cards` never stores a PAN or CVV — only the provider's token plus brand/last4/expiry. The
  table exists from stage 6-أ but is written by stage 6-ب.
- Commission is enabled **only** through `commission_settings`; there is deliberately no
  `commission_enabled` feature flag, so the switch, the percent, and the scope cannot disagree.
- A `driver_subscriptions` row exists only once its money has arrived — there is no `pending`
  status. Cash and CliQ are recorded from the admin panel *after* collection; wallet and card write
  the row only after the ledger or the provider says so.
- Every endpoint touching a ride or wallet must verify ownership (no IDOR).
- `device_tokens.token` never leaves the backend, for the same reason `saved_cards.provider_token`
  doesn't: it is what lets someone send a notification in TAXO's name to a user's phone.
- CliQ ride payments are never confirmed automatically, whatever contracts are active: that money goes
  from the rider to the *driver's* alias and never touches the company account, so no acquirer can
  witness it. The acquirer contract covers wallet topups only and does not move `cliq` out of
  `DIRECTLY_COLLECTED_METHODS`.

Python is pinned to 3.12 in the Dockerfile even though the host has 3.14, because Celery does not
support 3.14 yet.
