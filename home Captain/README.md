# CODING AGENTS: READ THIS FIRST

This is a **handoff bundle** from Claude Design (claude.ai/design).

A user mocked up designs in HTML/CSS/JS using an AI design tool, then exported this bundle so a coding agent can implement the designs for real.

## What you should do — IMPORTANT

**Read `mobile-app-design-request/project/TAXO Captain - Home.dc.html` in full.** The user had this file open when they triggered the handoff, so it's almost certainly the primary design they want built. Read it top to bottom — don't skim. Then **follow its imports**: open every file it pulls in (shared components, CSS, scripts) so you understand how the pieces fit together before you start implementing.

**If anything is ambiguous, ask the user to confirm before you start implementing.** It's much cheaper to clarify scope up front than to build the wrong thing.

## About the design files

The design medium is **HTML/CSS/JS** — these are prototypes, not production code. Your job is to **recreate them pixel-perfectly** in whatever technology makes sense for the target codebase (React, Vue, native, whatever fits). Match the visual output; don't copy the prototype's internal structure unless it happens to fit.

**Don't render these files in a browser or take screenshots unless the user asks you to.** Everything you need — dimensions, colors, layout rules — is spelled out in the source. Read the HTML and CSS directly; a screenshot won't tell you anything they don't.

## Bundle contents

- `mobile-app-design-request/README.md` — this file
- `mobile-app-design-request/project/` — the `Mobile app design request` project files (HTML prototypes, assets, components)


---

# ما بُني، وما زاد على الرسم — وعلّةُ كلِّ زيادة

**كُتب في 2026-08-30 لحظةَ البناء، لا بعده.** ومن قرأ الرسمَ وحدَه ثمّ فتح
الشاشةَ سيجد فيها ما ليس فيه — **فهذه أسبابُه**، وإلا قُرئت الزيادةُ انحرافاً
عن تصميمٍ قيل «بلا تغييرٍ ولا استثناء».

## ثلاثةٌ بقيت رغم أن الرسم لا يذكرها

| ما بقي | لمَ لا يُنزع |
|---|---|
| **تفضيلُ جنس الركّاب** (بطاقةٌ فوق الأزرار) | من ضيّق من يُقلّهم **يرى طلباتٍ أقلّ** — **وسببُ القلّة يجب أن يكون أمام عينه** لا في شاشةٍ يفتحها بحثاً عن عطل. ونزعُها يجعل الكبتنَ يقرأ الصمتَ «لا طلبات اليوم». |
| **إشعارُ الإذن المرفوض** | شرطُ المالك 2026-08-21: من رفض إذنَ الإشعارات **لا تصله طلباتٌ وهو خارج التطبيق**. وموضعُه فوق زرِّ الاستقبال — **هناك يقرؤه وهو يقرّر أن يعمل**. |
| **مبدّلُ السِمة** في الرأس | ميزةٌ حيّةٌ يستعملها الناس، **ولا يُنزع مبنيٌّ لأن رسماً لا يذكره**. والرسمُ يرسم شاشةً، ولا يقول «احذف ما ليس هنا». |

## وثلاثةٌ في الرسم لم تُرسم كما هي — **لأنها لا تُقاس**

1. **«د.ل» و«طرابلس» و«حتى 50 د.ل»**: الرسمُ ليبيٌّ بالكامل **وليبيا مغلقةٌ
   بأمر المالك**. **فالعملةُ والمبالغُ من `GET /drivers/me/earnings`** بيوم
   الدولة، **ولا رقمَ مخبوزٌ في شاشة مال** (§14).
2. **«عمولة TAXO ‎0%»**: صفرٌ مرسوم. **والمعروضُ نسبتُه هو** —
   `commission_percent` على بابِ ملفّه، مجمَّدةٌ على وعد اشتراكه: **من اشترى
   على صفرٍ يرى صفراً ولو رفع السوقُ إلى خمسة**. **و`earnings.commission`
   مبلغٌ اقتُطع لا نسبة** — ولا يُعرض أحدُهما مكان الآخر.
3. **«المستوى 3»**: يُقرأ من `GET /drivers/me/progress`. **و`enabled: false`
   تعني أن السوقَ لا يشغّل المهامَّ** — **فلا يُرسم «المستوى ٠»** وهو لا
   وجودَ له، ويسقط السطرُ كلُّه.

## والبلاطاتُ واللافتةُ صارتا جدولين تُدارُ من اللوحة (قرارُ المالك)

الرسمُ يخبز ستَّ بلاطاتٍ ولافتةً بنصِّها. **وهي الآن صفوفٌ في `service_tiles`
و`promo_banners`** (الترحيلة `0063`): تُضاف سابعةٌ **بلا نشر**، وتُخفى ما
تأجّل. **و«قريباً» تُقرأ ولا تُنقر** — بلا `onClick` أصلاً، فلا خطأَ على لمسةٍ
متوقَّعة. **و«جديد» شارةٌ بمدّةٍ تنقضي في الخادم** لا حالٌ ثالثة.
