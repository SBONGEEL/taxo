# سجلُّ تطبيق الكبتن على Play — `ly.tajora.driver` (أمرُ المالك ٢٠٢٦-١١-٠٢، الجزء E)

**هذا الملفُّ بابٌ لا نسخة**: الأرقامُ اليوميّةُ في `design/PLAY-PRODUCTION-APPLICATION.md` («إعادةُ تقديم الكبتن»)، والإصداراتُ المغلقةُ
وملاحظاتُ المختبِرين في `design/PLAY-TEST-LOG.md`. **وما يُكتب هنا ما لا مكانَ له هناك**: الحالُ في سطر، وما يُفعل بعدُ، والأجوبةُ المُعدّة.

## الحالُ (٢٠٢٦-١١-٠٣)

- **الإنتاج**: غيرُ نشط. **رُفض الطلبُ ٢٠٢٦-١٠-٢٤ ٢١:٠٨** («يحتاج اختباراً إضافيّاً»: ١٤ يوماً بـ١٢ مختبِراً مشتركاً على الأقلّ من تاريخ المراجعة).
- **العدّاد** (لوحةُ Play، قُرئ ٢٠٢٦-١١-٠٣ مرّتين): «عدد المختبرين المشتركين حاليًا لمدة 9 أيام: 12» — **على الحدّ تماماً**، فأبكرُ إعادةٍ نحو **٢٠٢٦-١١-٠٨** إن لم ينقطع.
- **المسارُ المغلق (alpha)**: **`2.0 (1025)` مكتمل** (رُفع ٢٠٢٦-١١-٠٣ ~19:10Z، وقُرئ بعده بالـAPI) · internal `517 (1.1)` · مجموعتا المختبِرين
  `taxo-testers@` و`testers-community@` كما هما.

### الإصدارُ `2.0 (1025)` — ٢٠٢٦-١١-٠٣

- **من الإيداع** `a61f5791` (فرع `agent/partBCD`؛ الواجهةُ تُخدم من `driver.tajora.ly` فالحزمةُ تحمل ما لا يصل بالويب). مفتاحُ الرفع
  `3B:DC:73:91…`، ٥٦٦٩١٤٦ بايت، وملفُّ R8 رُفع معه (٩٥٩٩٦١٥ بايت). **وبابُه `scripts/play_api.py upload`**: alpha ثابتٌ فيه.
- **ملاحظاتُ الإصدار** (`design/testers-community/release-notes-driver-E.json`، ar/fr/en): الدخولُ محفوظٌ ولو أُغلق التطبيقُ لحظةَ تجديد الجلسة
  (`SecureFlushPlugin` بـ`commit()`، مقيسٌ على المحاكي في الجزء B) · الرجوعُ نافذةً نافذة والخروجُ بضغطتين · زرُّ النهاريّ/الليليّ بجانب الجرس.
- **وحُذف سطرٌ لم يُقَس**: «الوضعُ الليليُّ يتبع الهاتف في «حسب النظام»» — `values-night-v29/styles.xml` (`isLightTheme=false`) **في الحزمة،
  ولم يُشغَّل على المحاكي** (ذاكرةُ ويندوز ~٤٠٠MB وقتَها). **يُقاس على هذه الحزمة نفسِها ثمّ يُذكر**، لا قبل.
- **وسقط البناءُ الأوّل عند `check:served`** — حاويةُ التطوير على 5174 تخدم `dist` شجرةٍ أخرى (`~/prj/TAXO`) لا شجرةَ البناء. **ولم يُتجاوز**:
  أُوقفت حاويتا التطوير للتطبيقين، فقال الحارسُ «لم يُقس» بنصّه («الغيابُ ليس فشلاً»)، وبقي فحصُ `dist` والهدف أخضر.
- **الأعطالُ وANR**: صفرٌ في ٢٨ يوماً. **حالةُ السياسة**: «لم يتمّ العثور على أي مشاكل».

## خطرُ نهاية Testers Community — مقيسٌ ٢٠٢٦-١١-٠٣

- **لوحتُهم**: TAXO Driver «Day 16 of 16 · 0 days remaining»، ١٥/١٥ مختبِراً «actively testing»، تقريران «Available». **وعدّادُ Play: ١٢ لا ١٥**
  — فثلاثةٌ على الأقلّ من الخمسة عشر ليسوا مشتركين متّصلين منذ المراجعة، **ولا يُعرف من الكونسول كم من الاثني عشر منهم** (الأعضاءُ في Google Groups).
- **ما تقوله صفحتُهم** (الأسئلةُ الشائعة، قُرئت اليوم): «We keep your group opted in for the full window» — **النافذةُ ١٤ يوماً من دورتهم**،
  **ولا شيءَ مكتوبٌ عمّا بعد اليوم ١٦**. ودورتُهم بدأت ١٨ أكتوبر، **وساعةُ Google بدأت من المراجعة ٢٤ أكتوبر** — فاليومُ ١٤ عند Google ≈ **٧–٨ نوفمبر**، بعد نهاية دورتهم.
- **فإن خرجوا**: ينزل المشتركون إلى عدد مختبِرينا وحدَهم — وعدّادُ Play يعيد العدَّ من الصفر لكلِّ من يشترك بعدها، **فمختبِرٌ جديدٌ اليومَ لا يُحسب ١٤ يوماً
  قبل ~١٧ نوفمبر**. **أي أن الحلَّ الوحيدُ قبل ٧–٨ نوفمبر بقاءُ الاثني عشر الحاليّين**، والجددُ يحمون ما بعد ذلك (إن طلب Google دورةً أخرى).
- **العددُ الآمن**: ١٢ مشتركاً متّصلين هو الحدّ؛ **وهامشٌ ٣ (١٥ مشتركاً) يحمي من خروج اثنين أو ثلاثة** حتى قرار Google (٢٤–٤٨ ساعة، وقد يبلغ ٧ أيّام بعد الإرسال).
- **ما يُفعل، ولا شيءَ يُشترى** (أمرُ المالك): (١) رسالةٌ إلى دعم Testers Community يطلب إبقاءَ مختبِريهم مشتركين حتى قرار Google — **مسوّدتُها
  أدناه، ولا تُرسل إلا بإذن المالك**؛ (٢) ٣–٥ مختبِرين من كباتننا وأهلنا يشتركون **اليوم** عبر الرابط — ليحموا ما بعد ١٧ نوفمبر لا ما قبله.

> **مسوّدةُ رسالة الدعم (EN)**: Hello, our app TAXO Driver (ly.tajora.driver) reaches day 16 today. Google asked us for 14 more days of closed
> testing counted from 24 October, so our re-application is on 7–8 November and Google's decision may take a few days after that. Could your
> testers please stay opted in until we confirm Google's decision? Thank you.

## ما يُفعل بعدُ

1. **تحديثٌ مغلقٌ بعد رفع B+C+D** — فيه ما لا يصل بالويب: حفظُ رمز الجلسة بـ`commit()` لا `apply()` (§٢٣.٢-أ، قتلُ التطبيق لحظةَ التدوير)،
   و`loggingBehavior: "none"`. **وملاحظاتُ الإصدار صادقة**: ما تغيّر فعلاً لا «تحسينات».
2. **اقتراحاتُ Testers Community**: الجولةُ وزرُّ «شارك التطبيق» مبنيّان (STATE)؛ **وصفُ المتجر ولقطاتُه لم تُمسّ** — «كبتن» داخل التطبيق وحدَه.
3. **أجوبةُ الطلب القادم**: تُكتب في `design/PLAY-PRODUCTION-APPLICATION.md` من أرقام هذا السجلّ لا من الذاكرة.
4. **ولا يُرسل الطلبُ إلا بكلمة المالك**؛ وإن طلب Google رمزاً أو كلمةَ مرور: وقوفٌ وسؤال.

## ٢٠٢٦-١١-٠٤ — العدّادُ ١٠ أيّام، ورسالةُ Testers Community، وموعدُ الإعادة

- **العدّاد** (لوحةُ TAXO Driver، قُرئ ٢٠٢٦-١١-٠٤ ~١٥:٠٠ UTC): «عدد المختبرين المشتركين حاليًا لمدة 10 أيام: 12» — **يومٌ بيوم منذ ٣ نوفمبر (٩ أيام)**،
  فاليومُ ١٤ هو **٢٠٢٦-١١-٠٨** إن بقي الاثنا عشر.
- **لا تحديثَ مغلقٌ جديد**: `2.0 (1025)` على alpha منذ ٣ نوفمبر هو البناءُ بالإصلاحات الحقيقيّة (السجلُّ أعلاه)، **ولا فرقَ في `driver-app`
  ولا `customer-app` بين `a61f5791` (مصدرُه) و`2278977c` (رأسُ master اليوم)** — قِيس بـ`git diff --stat`. فبناءُ 1035 كان سيُرفع حزمةً مطابقةً
  بملاحظاتٍ تدّعي جديداً، **فأُوقف قبل أن يكتمل ولم يُرفع شيء**.

### رسالةُ Testers Community — يلصقها المالك (لا دفع)

> Hello, thank you for testing TAXO Driver (ly.tajora.driver). Google asked us for 14 more days of closed testing counted from 24 October,
> so our re-application is on 8 November, and Google's decision can take a few days after that. Could your testers please stay opted in and
> keep the app installed until we confirm Google's decision? A new closed-testing build (1025) is already available to them. We are not
> asking for any paid extension. Thank you.

### توصيةُ موعد الإعادة — **٢٠٢٦-١١-٠٨، وبشرطين يُقاسان صباحَه**

1. **العدّادُ يقول «14 يوماً» و١٢ فأكثر** — لا قبله: Google يعدّ من تاريخ المراجعة (٢٤ أكتوبر)، والعدّادُ اليومَ ١٠ أيّام.
2. **ولا عطلَ ولا ANR** في لوحة «جودة التطبيق» (صفرٌ في ٢٨ يوماً حتى اليوم).

**ولمَ لا ٧ نوفمبر** (السطرُ القديم): اليومُ ١٤ يكتمل في ٨ نوفمبر بقراءة اليوم؛ الإرسالُ قبله يُرفض بالعلّة نفسِها. **ولمَ لا أبعد**: دورةُ Testers
Community انتهت (اليوم ١٦/١٦ في ٣ نوفمبر)، فكلُّ يومٍ بعد ٨ نوفمبر يزيد خطرَ خروج بعضهم ونزولِ العدّاد تحت ١٢ — **وحينها يبدأ العدُّ من الصفر**.

**والأجوبةُ** في `design/PLAY-PRODUCTION-APPLICATION.md`؛ **ولا يُرسل الطلبُ إلا بكلمة المالك.**

### الأجوبةُ النهائيّة (٢٠٢٦-١١-٠٤) — تعديلُ ٨ و١٠ فقط

- **(ب) قِيس اليوم ✓**: `t2-exit-hint` في حزمتَي `driver.tajora.ly` (`index-DbsZPq8Z.js`) و`app.tajora.ly` (`index-WbFjuHvU.js`) — زرُّ الرجوع على الإنتاج.
- **8.** Since the review we shipped builds 960, 975, 994 and 1025: a security update, edge-to-edge display, a back button that closes one layer at a time, and sign-in kept if the app is killed. From feedback: a 4-card tour, a Share button and a new store listing.
- **10.** This time 12 testers stayed opted in for the full 14 days, and we shipped four closed builds after the review (960, 975, 994, 1025), each with real changes and honest notes. Testers tried every screen in guest mode, and each fix was checked on the live closed build.
