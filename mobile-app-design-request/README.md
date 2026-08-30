# CODING AGENTS: READ THIS FIRST

This is a **handoff bundle** from Claude Design (claude.ai/design).

A user mocked up designs in HTML/CSS/JS using an AI design tool, then exported this bundle so a coding agent can implement the designs for real.

## What you should do — IMPORTANT

**Read `mobile-app-design-request/project/TAXO Driver - Offer Delivery.dc.html` in full.** The user had this file open when they triggered the handoff, so it's almost certainly the primary design they want built. Read it top to bottom — don't skim. Then **follow its imports**: open every file it pulls in (shared components, CSS, scripts) so you understand how the pieces fit together before you start implementing.

**If anything is ambiguous, ask the user to confirm before you start implementing.** It's much cheaper to clarify scope up front than to build the wrong thing.

## About the design files

The design medium is **HTML/CSS/JS** — these are prototypes, not production code. Your job is to **recreate them pixel-perfectly** in whatever technology makes sense for the target codebase (React, Vue, native, whatever fits). Match the visual output; don't copy the prototype's internal structure unless it happens to fit.

**Don't render these files in a browser or take screenshots unless the user asks you to.** Everything you need — dimensions, colors, layout rules — is spelled out in the source. Read the HTML and CSS directly; a screenshot won't tell you anything they don't.

## Bundle contents

- `mobile-app-design-request/README.md` — this file
- `mobile-app-design-request/project/` — the `Mobile app design request` project files (HTML prototypes, assets, components)


---

# ما نُفِّذ، وما فرضته المنصّةُ تحته (TAXO، 2026-08-30)

**بُنيت الشاشاتُ الأربعُ كما رُسمت** — الهندسةُ والألوانُ والأزرارُ والنصوصُ
والعدّادُ والتوسّعُ والسحب. وما دونه **ليس خروجاً عن التصميم بل ما تفعله
المنصّةُ تحته**، وقرارُ المالك أن يُكتب هنا **ليعرفه من يقرأ التصميمَ بعدنا**.

## أين نُفِّذت كلُّ شاشة

| الشاشة | الموضع |
|---|---|
| ٠١ داخل التطبيق | `driver-app/src/components/OfferSheet.tsx` (ويب) |
| ٠٢ ورقةٌ سفليّة | `OfferSheetWindow.java` (نافذةُ تراكب) |
| ٠٣ شاشةٌ مقفلة | `OfferActivity.java` (نشاطٌ أصليّ) |
| ٠٤ فقاعة / بديلها | `OfferBubble.java` · و`OfferActivity` بوسم `locked=false` |
| الأولويةُ بينها | `OfferAlert.java::show` |

## ١ — الورقةُ والفقاعةُ **إذنٌ واحد**، لا قناتان مستقلّتان

**مقيسٌ من أندرويد**: كلُّ ما يُرسم فوق تطبيقٍ آخر يمرّ بـ
`SYSTEM_ALERT_WINDOW` (`Settings.canDrawOverlays`). **فلا حالَ تُتاح فيها
الورقةُ ولا تُتاح الفقاعة** — هما شكلان لإذنٍ واحد.

**والقاعدةُ الأولى في التصميم تبقى كما هي** (أوّلُ متاحٍ يُستعمل والبقيّةُ
تُلغى)، **غير أنّ رفضَ هذا الإذن يُسقط الاثنتين معاً** ولا تنجو إحداهما.
ومن رفضه ينزل إلى الشاشة ٠٣/٠٤-البديل.

## ٢ — «في تطبيقٍ آخر» مقابل «خارج التطبيق تماماً» — **إشارةٌ لا يقين**

**أندرويد لا يقول أيُّ تطبيقٍ في المقدّمة** بلا إذنٍ خاصٍّ
(`PACKAGE_USAGE_STATS`). **والمتاحُ هو قربُ العهد بشاشتنا**: من غادرها قبل
أقلَّ من دقيقتين ما زال يستعمل هاتفَه ⇒ **ورقة** (٠٢)؛ ومن مضى عليه أطولُ من
ذلك ⇒ **فقاعة** (٠٤).

**وهذا تقريبٌ لما رسمه التصميمُ لا مطابقةٌ له**، وكُتب هنا كي لا يُقرأ يقيناً.

## ٣ — `USE_FULL_SCREEN_INTENT` قد ينزعه المتجر

**مقيسٌ من وثيقة أندرويد**: منذ أندرويد ١٤ صار الإذنُ محصوراً بتطبيقات
المكالمات والمنبّهات، **ومتجرُ Play ينزع المنحَ التلقائيَّ عمّا سواها**.
**ومقيسٌ على S21**: `granted=true` **لأن التثبيتَ جانبيّ** — وحزمةُ المتجر
قد لا تحمله.

**فيُقرأ حيّاً** (`canUseFullScreenIntent`) ولا يُفترض، **وإن لم يُمنح فإشعارٌ
بأقصى أهميّةٍ فيه المهلةُ والأجرةُ وزرٌّ يفتح التطبيق** — ولا يبقى الكبتنُ بلا
شيء (قرارُ المالك).

## ٤ — «كاش» تحت الأجرة: **الحقلُ مبنيٌّ وفارغٌ اليوم**

**التصميمُ يرسم «كاش · اقتصادي»، وطريقةُ الدفع لا تُعرف لحظةَ العرض**: الراكبُ
يختار القناةَ في شاشة الدفع **بعد** الرحلة (SPEC §6). **ولا تُخترع**: «كاش»
تعني مالاً في يد الكبتن وعمولةً عليه — **وكتابتُها ظنّاً تغيّر ما يقرّر به**.

فالحقلُ (`method`) مبنيٌّ في الحمولة وفي الرسم، ويُمرَّر فارغاً، **والسطرُ
يُطوى إلى «اقتصادي» وحدَها** بلا فاصلٍ معلَّق. ويومَ تُعرف القناةُ لحظةَ العرض
يُملأ الحقلُ ولا يُبنى شيء.

## ٥ — الشاشةُ المقفلةُ لملء الشاشة وحدَه

**بقرار المالك**: نُزع `FLAG_SHOW_WHEN_LOCKED` من الفقاعة والورقة — **فلا
تظهران فوق القفل**، والشاشةُ ٠٣ وحدَها تعمل هناك، كما رُسمت.

## ٦ — العربيّةُ وحدَها تُشحن

**التصميمُ يحمل `L.en` كاملاً، وهو مرجعٌ لا شحنة** (قرارُ المالك): نصُّ
الواجهة في هذا المشروع عربيٌّ بقاعدةٍ قائمة، والخاناتُ عربيّةٌ-هنديّة كما في
`_fmtN`.
