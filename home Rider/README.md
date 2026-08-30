# CODING AGENTS: READ THIS FIRST

This is a **handoff bundle** from Claude Design (claude.ai/design).

A user mocked up designs in HTML/CSS/JS using an AI design tool, then exported this bundle so a coding agent can implement the designs for real.

## What you should do — IMPORTANT

**Read `mobile-app-design-request/project/TAXO Rider - Home.dc.html` in full.** The user had this file open when they triggered the handoff, so it's almost certainly the primary design they want built. Read it top to bottom — don't skim. Then **follow its imports**: open every file it pulls in (shared components, CSS, scripts) so you understand how the pieces fit together before you start implementing.

**If anything is ambiguous, ask the user to confirm before you start implementing.** It's much cheaper to clarify scope up front than to build the wrong thing.

## About the design files

The design medium is **HTML/CSS/JS** — these are prototypes, not production code. Your job is to **recreate them pixel-perfectly** in whatever technology makes sense for the target codebase (React, Vue, native, whatever fits). Match the visual output; don't copy the prototype's internal structure unless it happens to fit.

**Don't render these files in a browser or take screenshots unless the user asks you to.** Everything you need — dimensions, colors, layout rules — is spelled out in the source. Read the HTML and CSS directly; a screenshot won't tell you anything they don't.

## Bundle contents

- `mobile-app-design-request/README.md` — this file
- `mobile-app-design-request/project/` — the `Mobile app design request` project files (HTML prototypes, assets, components)


---

# ما بُني، وما زاد على الرسم — وعلّةُ كلِّ زيادة

**كُتب في 2026-08-30 لحظةَ البناء، لا بعده.**

## ثلاثةٌ في الرسم لم تُرسم كما هي — **لأنها لا تُقاس**

| ما في الرسم | ما بُني | العلّة |
|---|---|---|
| **«5 كباتن قريبون · دقيقتان»** | العددُ وحدَه بلا مهلة | العددُ يُقرأ من `drivers` الحيّة. **ومهلةُ الوصول لا تُحسب قبل أن تُعرف نقطةُ الالتقاط** — **ورقمٌ يُرسم ولا يُقاس وعدٌ يعدّه صاحبُه ولا يجده**. |
| **«طرابلس»** تحت الاسم | عنوانُ موقعه حين يُعرف، وإلا فلا سطر | **لا حقلَ مدينةٍ في أيِّ حمولة**، **ومدينةٌ تُخمَّن من إحداثيّةٍ حسابٌ في الجهاز**. وليبيا مغلقةٌ أصلاً. |
| **«المطار»** ثالثَ الاختصارات | ثلاثةٌ من **أماكنه المحفوظة** | الاثنان الأولان محفوظان بحقّ، **والمطارُ ليس مكاناً محفوظاً بل بلاطةُ خدمةٍ في الشبكة تحتها** — ورسمُه اختصاراً يفتح **بابين لشيءٍ واحد** (الشكلُ الثامن). |
| **«12.500 د.ل»** و**«واربح 2 د.ل»** | من `GET /wallet/me` و`GET /me/referrals` | **لا مبلغَ مخبوزٌ في شاشة مال** (§14)، وليبيا مغلقة. **وصفُّ الإحالة لا يظهر بلا جائزةٍ مقروءة**: «ادعُ صديقاً واربح» بلا مبلغٍ دعوةٌ بلا وعد. |

## و«أعِد الرحلة» تنسخ الوجهةَ وحدَها

الرسمُ يكتب «أعِد الرحلة» على بطاقةٍ فيها التاريخُ والأجرةُ والطرفان. **وثلاثةٌ
لا تُنسخ من الرحلة الماضية**:

1. **نقطةُ الانطلاق** — أين هو **الآن** لا أين كان؛ ونسخُها تضع كبتناً على
   رصيفٍ غادره الراكبُ منذ يومين.
2. **الأجرة** — تُحسب في الخلفية لحظتَها، **والقديمةُ تعريفةُ يومها**.
3. **المحطاتُ الوسيطة** — مسارٌ يُعاد بمحطاتٍ لم يطلبها **أغلى بلا إذنه**.

**فالمنسوخُ الوجهةُ وحدَها**، ومنها إلى ورقة التأكيد التي يراجعها ويضغط —
**لا طلبٌ يُرسل بلمسة**.

## والبلاطاتُ واللافتةُ صارتا جدولين تُدارُ من اللوحة (قرارُ المالك)

**عرضُ الخصم النسائيِّ المرسوم نموذجٌ لا نصٌّ مخبوز** — نزل صفّاً في
`promo_banners` بنافذةِ عرضٍ **إلزاميّة** تُقاس في الخادم. **ولا تُقاس في
الجهاز**: ساعةُ الجهاز يملكها صاحبُه، **ولافتةٌ انتهت تبقى ظاهرةً لمن أخّر
ساعتَه**.
