# إصدارُ الاختبار المغلق — الحزمتان وملاحظاتُ الإصدار (SPEC §٧٦/٧)

**إلى المسار نفسِه** (الاختبارُ المغلق «Alpha») **لا إلى الإنتاج**. **ولا وصولَ لي إلى Play Developer API** (لا حسابَ خدمةٍ ولا مفتاحَ
له في `~/.taxo-secrets`) — **فالحزمتان مبنيّتان وموقَّعتان هنا، والرفعُ خطواتٌ يؤدّيها المالكُ بيده** (§٧٦-أ/٧: «وإلا فجهّز الحزمتين
وخطواتٍ مرقّمة»).

## ⚠ ما لا يُمسّ في هذا الرفع (شرطُ §٧٦-أ)

- **لا يُوقَف المسارُ ولا يُستبدل ولا يُحذف ولا يُعلَّق** — **يُعيد عدَّ الأيّام الأربعة عشر**.
- **قائمةُ المختبِرين القديمةُ لا تُلغى ولا تُعدَّل** — تُضاف الحزمةُ إلى إصدارٍ جديدٍ في المسار نفسِه، وما سواه كما هو.
- **ولا بطاقةَ متجرٍ ولا إقراراتِ محتوى** في هذه الخطوات — إلا ما يملؤه المالكُ بنفسه.

## الحزمتان

<!--AAB-TABLE-->

## الخطواتُ — لكلِّ تطبيقٍ على حدة (الراكبُ ثمّ الكبتن)

1. Play Console ← اختر التطبيق (**TAXO** للراكب · **TAXO كابتن** للكبتن).
2. **الاختبار ← الاختبار المغلق** ← المسارُ **Alpha** ← **«إنشاء إصدار جديد»** (Create new release).
   **لا «إدارة المسار» ولا «إيقاف المسار مؤقتاً»** — الزرُّ الوحيدُ المقصودُ هو «إنشاء إصدار جديد».
3. **«تحميل»** (Upload) ← اختر ملفَّ `.aab` من الجدول أعلاه.
   - إن ردّ: «سبق أن تم استخدام رمز الإصدار …» **فالحزمةُ في مكتبة العناصر** — «إضافة من المكتبة» لا رفعٌ ثانٍ (`PLAY-LISTING.md` د-١٤).
4. **اسمُ الإصدار** يُملأ تلقائيّاً بالرقم — اتركه.
5. **ملاحظاتُ الإصدار**: الصق الكتلةَ الجاهزةَ أدناه كما هي (بوسومها).
6. **«التالي»** ← اقرأ التحذيرات (التحذيرُ ليس خطأ؛ «ملفُّ إزالة التشويش» تحذيرٌ معروف) ← **«حفظ»**.
7. **«نظرة عامة على النشر»** (Publishing overview) ← **«إرسال التغييرات للمراجعة»** إن طُلب.
8. **التحقّق** بعد المراجعة: صفحةُ المسار تقول **«أحدث إصدار: <الرقم>»**، وعددُ المختبِرين كما كان.

## ملاحظاتُ الإصدار — **بلا ذكرِ دولة** (SPEC §٧٦-ب)

**تطبيقُ الراكب**:

```
<ar>
• جديد: «أرسل ملاحظة» في «حسابي» — اكتب لنا رأيك أو خللاً رأيته، وأرفق صورة الشاشة إن شئت.
• سياسة الخصوصية وشروط الاستخدام بنسختهما الكاملة الجديدة، من «حسابي».
• إصلاحات وتحسينات.
</ar>
<fr-FR>
• Nouveau : « Envoyer une remarque » dans « Mon compte » — votre avis ou un problème rencontré, avec une capture d’écran si vous le souhaitez.
• Nouvelle version complète de la politique de confidentialité et des conditions d’utilisation, dans « Mon compte ».
• Corrections et améliorations.
</fr-FR>
<en-US>
• New: “Send feedback” in Account — tell us what you think or report a problem, with an optional screenshot.
• New full versions of the Privacy Policy and Terms of Use, in Account.
• Fixes and improvements.
</en-US>
```

**تطبيقُ الكبتن**:

```
<ar>
• جديد: «أرسل ملاحظة» في «حسابي» — اكتب لنا رأيك أو خللاً رأيته، وأرفق صورة الشاشة إن شئت.
• سياسة الخصوصية وشروط الاستخدام صارت في «حسابي» بنسختهما الكاملة الجديدة.
• إصلاحات وتحسينات.
</ar>
<fr-FR>
• Nouveau : « Envoyer une remarque » dans « Mon compte » — votre avis ou un problème rencontré, avec une capture d’écran si vous le souhaitez.
• La politique de confidentialité et les conditions d’utilisation, en version complète, sont désormais dans « Mon compte ».
• Corrections et améliorations.
</fr-FR>
<en-US>
• New: “Send feedback” in Account — tell us what you think or report a problem, with an optional screenshot.
• The full Privacy Policy and Terms of Use are now in Account.
• Fixes and improvements.
</en-US>
```

**وكلُّ سطرٍ مقيسٌ على ما رُفع**: زرُّ الملاحظة في «حسابي» بالتطبيقين (`FeedbackT2.tsx`)، وصفّا السياسة والشروط في «حسابي» للكبتن
جديدان (`driver-app/src/lib/legal.ts`) وكانا للراكب قبلُ — **فالفرقُ بين النصّين مقصود**. **ولا وعدَ بما لم يُبنَ.**

> **والشاشاتُ تُحمَّل من الخادم** (`server.url`): الزرُّ والصفحاتُ تصل المختبِرين المثبَّتين **برفع الخادم وحدَه**؛ والحزمةُ الجديدةُ
> لتجديد الغلاف ورقمِه، **ولتحمل ملاحظاتِ إصدارٍ يقرؤها المختبِر**.
