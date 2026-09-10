<!--جديد-->
# GUARDS.md — الحرّاس، وما لم يصر حارساً بعد

**مُلزِمٌ بشرطه في `CLAUDE.md`**: *قبل أن تصدّق حارساً أو تبنيَ واحداً أو تنقل رقمَه — يُفتح هذا الملفّ.*

**وجدولُ «دروسٌ صارت حرّاساً» بقي في `CLAUDE.md`** لأنه فهرسٌ بطبعه — سطرٌ لكلِّ حارس. **وتفصيلُ كلِّ حارسٍ هنا**، ومعه «قاعدةُ كلِّ حارس» التي تُقرأ قبل الفهرس لا بعده.

**نقلٌ لا تحرير.** كلُّ ما تحت هذا السطر منقولٌ من `CLAUDE.md` بحرفه. وفهرسُه في `CLAUDE.md`.
<!--/جديد-->

### `check:slot` and the error boundaries — the fourth family member, and the guard that was missing (2026-08-15)

**A blank screen on two money surfaces, from one line.** `Button` with `asChild` renders Radix `Slot`
and passed it **two children** — the loading node and `children`. `Slot` uses `React.Children.only`,
**and `{null}` counts as a child**, so it threw; nothing caught it; React unmounted the tree. Measured on
the phone: `document.body` with **zero text and two elements**. It hit `CliqPanel` (paying by CliQ) and
`WalletTopup` (topping up the wallet) — so **the rider could neither pay by CliQ nor add money**, with no
message and nothing in any log.

**And no build could see it**: the types are perfectly correct; the break is at runtime inside a third-party
component. That makes it **the fourth shape in this project's "what the build cannot see" family** —
after a class silently dropped by tailwind-merge, a key missing from the pixel scale, and a value missing
from an *array* rather than a union.

**So it has a guard now**: `check:slot`, which parses with TypeScript's own parser rather than grepping.
Its rules and the reason it is not a regex are written in `scripts/check-slot.mjs`.

**And the sweep found the rest of the family is empty**: two `asChild` call sites, both in the rider app,
both single-child at the call site — the defect was in the shared `Button`, not the callers. The driver app
and the panel import no `Slot` at all, so the guard passes trivially there and starts working the day
someone adds one.

**The boundaries exist because the silence is what cost the day.** `ErrorBoundary` now wraps the routes in
all three apps — **inside** the providers, so a screen crash replaces that screen while the theme, the
session and the bottom bar stay alive. Three rules: it **logs first** (`console.error` with the component
stack — a boundary that hides the cause is worse than the crash), it **promises nothing** («لم يقع شيءٌ على
حسابك أو رحلتك — المشكلة في العرض وحده») and offers two doors, and it **resets on navigation** via
`resetKey={location.pathname}` so an error message cannot stick to the next screen. Verified by feeding the
rides list a row with `ride: null` — measured: message rendered, error logged, bottom bar intact, and the
screen healthy again after the cause was removed.

### The password policy, and a guard that hit the wrong target (2026-08-18)

**Composition rules were asked for and declined; a blocklist was built instead, and the owner accepted
the reasoning.** `NIST SP 800-63B` forbids verifiers from requiring a digit or an uppercase letter — the
rules produce predictable shapes (`Taxi2024`) and raise friction without raising entropy — and recommends
a length minimum plus a blocklist. The existing 8–128 rule already matched that guidance, so tightening
would have moved *away* from it, on the most fragile funnel this platform has. **Nothing existing would
have broken either way**: the check runs where a password is *set*, never at login, so no account can be
locked out by it.

**Three block kinds, in `core/password_policy.py`, checked in `validate_password`** — the one door both
registration and reset pass through. Common list (every entry ≥8 chars, since shorter ones die on length
anyway — a shorter entry is a line that cannot fire), the phone itself, and pure repetition.

**And the phone check shipped wrong in its first cut, which the suite caught: 27 failures.** It compared
by plain substring, so `SuperSecret123` was rejected because its digits — `123` — appear inside
`962791234567`. That is the whole lesson: **"the password is their phone number" is not "the password
shares digits with their phone number."** The rule is now two conditions together — the text must be
digits only (after separators), and it must equal the number or be a ≥7-digit tail of it — which catches
`0791234567`, `+962791234567` and `791234567` and nothing else. A guard that fires on innocents is worse
than no guard: it gets disabled, and this one would have blocked most valid registrations.

**The list is never published and neither is its size.** `GET /config` publishes the limits and not this
— a published blocklist reads as a *sorted guessing guide*, since it is exactly what an attacker tries
first. And the refusal names its reason without naming the list: one code (`weak_password`) with three
messages, because the admin counts one category while the person choosing needs to know which one they hit.

### OTP message templates — the guard that moved rather than being deleted (2026-08-19)

**`SPEC.md` §19 holds the design; this is what building it found.** Two admin-editable templates
(registration and password reset), each with its own field, live preview and independent save.

**The gateway's rule used to be "no door accepts text"** — `/send` took a number and a code, and the
one link-free text was composed inside `session.js`, so "the promise is kept by whoever owns the wire,
not by whoever calls it". Editable templates require the backend to hand the gateway text, which is
exactly what that rule forbade. **The owner decided the guard moves rather than disappears**, and the
distinction is the whole point: the promise was never "the gateway composes" but **"nothing violating
the conditions reaches the wire"**. It is now kept by *validation* instead of *composition* —
`template.js::chooseText` checks every incoming text and **falls back to the built-in default** on any
violation. Read it as a relocation, not a concession.

Five rules from the build:

- **The conditions are one file read by two languages** (`whatsapp-gateway/otp-template-rules.json`,
  bind-mounted read-only into the backend). Two copies diverge at the first edit, and then the panel
  accepts what the gateway silently refuses — which is precisely "a broken template that works for a
  month and nobody knows". The file lives with the gateway because **the condition is a property of the
  wire**.
- **Checking at the gateway does not replace checking at save.** Whoever learns of the refusal in the
  panel fixes it; whoever learns of it from a message that never arrived does not know anything
  happened at all. Three doors say it: a 422 at save naming the template *and* the condition, a line on
  the template's own card («هذا القالب مرفوضٌ عند الإرسال»), and a `warn` in the gateway log — **no
  silent fallback**.
- **The cap is measured, not estimated: 3989 bytes.** `POST /send` caps the body at 4096 (measured on
  the live container: 4095 accepted, 4097 refused) and the worst-case JSON envelope is 106 — so the text
  gets 3989, ≈1994 Arabic characters. WhatsApp's own text limit is far higher and never binds first.
- **Global, because the number is global.** One contract and one number serve both markets, so the
  template is a property of the *number*, not the market — a global table like `security_settings`, and
  a screen that does not follow the country switch. The invalidating condition is written down: if each
  market gets its own number or contract, revisit it. **No "just in case" country column.**
- **The Cloud API transport cannot carry it at all** — Meta's authentication templates take no free text,
  only the code parameter. So the panel says on the screen that this governs the self-hosted wire alone,
  rather than letting an admin edit a field that does nothing on the other transport.

**And the isolation test passed with the two templates swapped.** Mixing them is the one failure that
produces no symptom: both carry a valid code, nothing raises, nobody complains — and someone registering
reads "password reset". The first guard counted occurrences (one of each), which stays true after a
swap. Rewritten to read the **AST** — which purpose sits inside which endpoint function — it now fails
two tests on a swap and passes eight on correct code, verified by doing the swap. **The question is
never "how many?" but "which is in which?"**

### Latin digits everywhere — the display format was inverted (2026-08-19)

**`SPEC.md` §20 is the policy.** Every number the user sees is now Latin, in all three apps and the
panel — the reverse of what the project was built on (`DESIGN.md` §4). Three things about how it was
done are worth keeping.

**The funnel was flipped, not deleted.** `arabicDigits` became `digits` in place: it used to replace
Latin digits with Arabic-Indic, and now **normalises** Arabic-Indic and Persian digits to `[0-9]`. That
is deliberately stronger than removing the call: a string arriving from `toLocaleString` with Arabic
numerals still comes out Latin, so the funnel *guarantees* rather than *assumes*. 184 call sites kept
working with one edit to the body plus a rename — and the rename mattered, because a function called
`arabicDigits` returning Latin is a lie someone will believe.

**The locale is written down, and that is the `check:target` lesson applied to text.** `"ar"` yields
Latin numerals in today's ICU and `"ar-EG"` yields Arabic-Indic — so the old code was half relying on a
library default that no line here controls. `DISPLAY_LOCALE = "ar-u-nu-latn"` pins it: Arabic month
names, Latin numerals, and a library upgrade can no longer change what a date looks like without a line
changing here.

**Two guards, and neither replaces the other.** `check:digits` parses each file with TypeScript's own
parser and rejects an Arabic-Indic digit inside a string or JSX text, *and* an unpinned locale in a
formatter call — the second catches a defect with **no Arabic character anywhere in the source**, which
no text search could find. `tests/digit_format.py` sweeps every response the suite produces, because an
error message or a published limit carrying «٢٤» reaches the screen as text and **never passes through
the funnel** — it is a string, not a number. One reads what was written; the other reads what came out.

**The guard caught the author twice within a minute of being written**: two `الخطوة ١ من ٣` literals
survived my own edit pass because `str.replace(..., 1)` had hit the docstring above them instead of the
JSX below. Verified by reintroducing both shapes and watching it fail.

**And the sweep found two live ones plus a flaky test that was never flaky.** The two are provider
field labels published to the panel — «سقف الرسائل لكل رقم في الساعة (فارغ = ٣)» — Arabic-Indic digits
reaching a screen through a *string*, exactly the class the source guard cannot see.

The third is worth more. `test_the_list_is_not_published_anywhere` asserted `entry not in body` over
`list(COMMON_PASSWORDS)[:10]` — a **frozenset**, so the ten sampled entries differ between runs, and
`"password"` is both a blocklist entry and the published *field name* in `GET /config`'s validation
rules. So the test failed roughly one run in five, for a reason that has nothing to do with the
blocklist being published. It is the "flaky under load is a hypothesis, not a diagnosis" rule again:
this was a **wrong assertion**, not flakiness. Now it walks the payload's values, subtracts its keys
(a field's own name explains itself), and checks **all 53** rather than a random ten.

**And the failure mode is now benign — which has a second face that matters more than the first.**
Before, a number that skipped the funnel came out Latin in an Arabic-Indic app: **visibly wrong**, and
anyone opening the screen saw it. Now a number that skips the funnel comes out Latin in a Latin app,
i.e. correct-looking. The conversion stopped being load-bearing for correctness — **and stopped being
observable at the same moment**.

So a missing `digits()` call now leaves **no trace on any screen**. No visual pass will ever find one
again, and the sight-check that caught this class for two years is retired. **`check:digits` is not a
tidiness guard; it is the only remaining detector**, and the one shape it must never miss is the
literal — an Arabic-Indic digit typed into a constant string, which is now the only way a stray digit
can still reach a screen looking odd. Verified against eight literal shapes (object value, `Record`
value, array element, template middle, function return, JSX attribute, JSX text, plain const) and all
eight fail the guard. Its two exclusions were re-read to confirm they hold conversion ranges only and
no display text.

**Read the pairing as the rule**: when a wrong value stops being visible, the guard that replaces the
eye is load-bearing, and weakening it is not a style decision.

### قيمةٌ تنجو من كنسٍ لا يراها حارس — وأخواتُها معها (2026-08-22)

**`#facc15` بقي في `MapView.tsx` بعد كنس 12-أ** الذي أسقط الأصفرَ من §1.1،
فبقيت سياراتُ الخريطة بلونٍ **ليس في اللوحة أصلاً**. **ولا حارسَ يراه**:
`check:scale` يقرأ أصنافَ Tailwind، وهذه قيمةٌ ستّ عشريّةٌ مكتوبةٌ في SVG
**داخل سلسلةِ نصّ** — خارج كلِّ سلّمٍ وكلِّ اتحاد.

**والقاعدةُ التي أمر بها المالك: ما نجا منه واحدٌ نجا منه غيرُه غالباً — فيُمسح
الملفُّ كلُّه لا السطرُ المُبلَّغُ عنه.** والمسحُ أخرج ثلاثةً أخرى في يومٍ واحد:

- **دبّوسا الراكب** `#16a34a`/`#dc2626` — **أخضرُ Tailwind وأحمرُه**، لا
  `--ok`/`--dng`؛ وتطبيقُ الكبتن يرسم الدبّوسين نفسَهما بقيم اللوحة الصحيحة.
  **فبابان يرسمان شيئاً واحداً بلونين** — الشكلُ الثامن في اللون.
- **خطُّ المسار** يُكتب `dark ? "#e6edf3" : "#171b20"` بيدٍ في التطبيقين، لأن
  `paint` في mapbox **ليس CSS فلا يقرأ `var(...)`**. والعلّةُ صحيحةٌ والنسخةُ
  خطأ: `cssColor("--tx", …)` تقرأ القيمةَ المحسوبةَ من الجذر، **فتتبع اللوحةَ
  بلا نسخة**.

**والسمةُ هي المعيار لا الذوق**: لونٌ ثابتٌ يذوب في إحدى السمتين مهما حُسن
اختيارُه، و`--tx` **ينقلب** — داكنٌ على خريطةٍ فاتحة، فاتحٌ على داكنة. مقيسٌ:
`#171b20` فاتحاً و`#e6edf3` داكناً في المتصفح نفسِه.

**والحجمُ مقيسٌ لا مقدَّر** (شرطُ المالك): ٣٠ بكسل CSS على عرض ٣٩٠ = **٧٫٧٪**
من العرض، **٩٠ بكسلَ جهاز** عند ٣×، ≈**٥٫٧ مم**. **ولا يُقرأ من المستطيلِ
المحيط**: المقيسُ ٤٢ بكسلاً لأن مربّعاً بزاوية ١٢٤٫٩° محيطُه ٣٠×١٫٣٩ — **حجمُ
الالتفاف لا حجمُ الأيقونة**.

#### والصحيحُ بالصدفة يستر الخاطئَ بالبنية (قرارُ المالك 2026-08-24)

**وهذا ما أبقى العائلةَ سنةً كاملة.** قِيس 2026-08-24: **٤٣ موضعاً** تكتب
**اسمَ متغيّر CSS مكانَ اسم الرمز** — `text-mut` بدل `text-muted`، `bg-sur2`
بدل `bg-surface-2`، `text-tx` بدل `text-ink` — **ولا قاعدةَ في CSS المبنيّ
لأيٍّ منها**.

**ولمَ لم يرَها أحد؟** لأن **`text-tx` كان صحيحاً بالصدفة**: صنفٌ بلا قاعدةٍ
**يرث** لونَ أبيه، ولونُ الأب هو الحبرُ نفسُه — فالنصُّ الأساسيُّ يُرسم
سليماً تماماً. **فمن نظر إلى الشاشة رأى نصّاً صحيحاً ولم يسأل عن الخافت** —
والخافتُ (`text-mut`) كان يرث الحبرَ أيضاً، **فيُرسم بالحبر الكامل ولا
تراتُبَ بصريّ**؛ والخلفياتُ شفّافةٌ فبطاقاتٌ لا تنفصل عن صفحتها؛ و`border-brd`
يسقط إلى **رماديِّ Tailwind الافتراضيِّ `#e5e7eb`** — **لونٍ ليس في اللوحة
أصلاً**.

> **فالقاعدة**: **الصحيحُ بالصدفة يستر الخاطئَ بالبنية.** وحيثما كان لعطبٍ
> **وجهٌ يبدو سليماً** فذلك الوجهُ هو ما يمنع السؤال — **ولا يُقاس صنفٌ
> بجاره بل بقيمته المحسوبة**.

**وأداةُ القياس هي `getComputedStyle` لا العين**: حُقن الصنفُ القديم والصحيحُ
في **الصفحة نفسِها** وقُرئ الناتج — فبان أن `text-mut` يعطي حبراً كاملاً
و`text-muted` يعطي ‎rgb(139,148,158). **وهي «اقرأ من الشيء الذي يحكم» في ثوب
لون**: الشجرةُ تقول `text-mut`، **وCSS المبنيُّ وحدَه يقول أله قاعدةٌ أم لا**.

### `check:doors` — the door-with-no-button family became a build guard (2026-08-19)

**This project's oldest recurring shape now stops the build.** A backend capability ships, is tested,
and no UI ever reaches it: the seventh flag with no switch, the badge grant with no button, the payment
refund tested in three files with no row to press, `/drivers/nearby` declared and called by nobody —
which is what left the rider's map empty for weeks.

`admin-panel/scripts/check-doors.mjs` compares **every admin route in the backend** (120 of them)
against what the panel actually calls, and fails on anything with neither a caller nor a **written
reason** in `DELIBERATE`.

**Its two halves are what make it a guard rather than a nuisance, and both were learned by being
wrong:**

- **Comments are stripped before matching.** The first version counted a *mention of the path in a
  comment* as a caller, and so hid `POST /drivers/me/online`. A guard that lies in one direction is a
  guard you trust.
- **A declaration is not a button.** The second version accepted the path appearing in
  `api/endpoints.ts` — but that file only *declares*. Requiring the exported function's name to be used
  **outside** `endpoints.ts` immediately surfaced six more doors, including the entire quiet-hours
  editor (`GET`/`PUT /admin/campaigns/settings/{country}` — declared since stage 8, called by nobody),
  which is where the timezone that computes "the country's day" in every report lives.
- And it accepts a path built inline in a screen (`window.location.href = …` for the backup download),
  because a guard that shouts at working code gets disabled.

**Exemptions carry their reason as text, and a stale one fails the build too** — a list of excuses
nobody prunes becomes a lie. Verified by deletion: removing the refund call fails it.

**What the sweep that produced it found, by class rather than by case.** Two detectors: 227 backend
routes against every frontend, and 50 admin input schemas against what the panel sends. Fifteen routes
with no caller (three of them correctly so — a provider webhook, a deliberate second door, and the REST
location fallbacks), plus fields with no input — of which the sharpest was `backup_settings.weekday`:
the panel offers «أسبوعياً» and never sends a day, so `is_due` reads `weekday is None` and **no backup
is ever taken**, on a schedule that looks configured. Nothing fails until restore day.

### A guard that invents a defect costs more than one that misses it (2026-08-20)

**`check:contract` was built to catch a class nothing else could see, and its first three versions each
lied — the third one badly enough that the owner ordered a whole task on a defect that did not exist.**

| version | what it did | cost |
|---|---|---|
| 1 | counted a query string as part of the path | 14 false reports on healthy calls |
| 2 | read `method: "cash"` from a nearby payload literal | announced an HTTP verb named `CASH` |
| 3 | read `uploadVerb` from the *calling* file, not `client.ts` | **reported `POST` on a route that has sent `PUT` for a month** |

The third is the expensive one. I presented it as measured fact; the owner authorised a fix; and the
`405` I had "measured" came from **my own probe sending POST by hand**, not from the app. The app was
never broken. What was broken was the panel bundle — the tenth shape, third occurrence.

**The asymmetry is the lesson.** A guard that *misses* something leaves you where you were: the defect
survives, and you find it another way. A guard that *invents* something spends real work on nothing —
and worse, it teaches you to distrust its true findings. `check:flags`, `check:doors` and `check:digits`
all earn their keep because their reports are believed.

**So: every new guard is measured in both directions before it is trusted, and its first report is not
acted on until it is verified independently.**

- **Does it catch a real defect?** Break something on purpose and watch it fail.
- **Does it stay silent on a healthy tree?** Run it unmodified and watch it pass.
- **Does it catch the *specific* shape it was built for?** For `check:contract` that is a wrong verb on
  a correct path — the exact thing a path-only guard would wave through.

All three were run before it went into the build: a fabricated path fails it, `POST` on
`/drivers/me/earnings` fails it naming the accepted verb, and a clean tree passes with 257 calls.

### `check:target` / `check:dist` — the build guard for "which backend is this bundle talking to" (2026-08-15)

**`dist` on this machine is not a check artifact; it is what the container serves to the phones over
the tunnel.** So a plain `npm run build` — no `VITE_API_BASE_URL` — silently overwrites it with a bundle
that calls `http://localhost:8001`, an address that does not exist inside the phone. The app then sits on
the splash saying «الشبكة ضعيفة — جارٍ المحاولة» while the network is fine and a raw `fetch` from the same
WebView returns 200. **Nothing else can see it**: the build succeeds, `tsc` passes, and `check:scale`,
`check:enums` and `check:config` are all green, because the defect is not in the code — it is a variable
that was not passed. It cost this session twice.

**It is two gates, and their order is the difference between a warning and a guard.** `check:target`
(`--intent`) runs **before** `vite build` and refuses an undeclared target, so the wrong `dist` is never
written — a post-build check alone lets the damage land and then tells you about it while the container
is already serving it. `check:dist` (`--dist`) runs after and measures the output: the declared host must
appear in the bundle, and no `localhost`/`127.0.0.1` URL may survive anywhere in it — which catches a
*stale file left in the directory* from an earlier build, something the variable cannot know about.

**The default is the safe one and the intent is declared**: a local build needs `DEV_BUILD=1`, and
type-checking alone was never a reason to build — `npm run lint` does that. It sits in both PWAs and
**not** in the panel, which is served on `127.0.0.1:5175` by design.

## الحرّاس — وما لم يصر حارساً بعد (2026-08-20)

> ### القاعدةُ التي تسبق القواعد (قرارُ المالك 2026-08-21)
>
> **من يجيب سؤالاً لا دليلَ له يصنع دليلاً.** والامتناعُ عن الجواب صوابٌ لا
> تقصير.
>
> **ووقعت مقيسةً في اليوم نفسِه**: طلب المالكُ جدولَ «جولةِ الإشعارات على
> S21 — الحالاتُ الثلاث، وما وصل بالضبط، وهل تفتح الضغطةُ الشاشةَ الصحيحة».
> **ولم تقع تلك الجولة**، ولا وصل إشعارٌ واحد؛ الذي قِيس كان **القدرةَ
> والحضورَ** لا الوصول. **وكان الجدولُ سيُكتب لو أجبتُ** — أعمدتُه معقولةٌ
> وصياغتُه ممكنة، **ولا شيءَ فيه من قياس**.
>
> **وهذا أخطرُ من حارسٍ يخترع عطباً**: ذاك يُكشف بقياسٍ ثانٍ، وهذا **يُقرأ
> تقريرَ ميدان** فيُبنى عليه قرار. وثمنُه ثمنُ «الإعدادُ مكتوبٌ ليس الإعدادَ
> سارياً» و«الشاشةُ الفارغةُ ليست دليلاً»: **جوابٌ صحيحُ الشكل عن قياسٍ لم
> يقع**.
>
> **فالقاعدة**: يُقال «لم يُقَس» صراحةً، ويُسمّى **ما قِيس بدلاً منه**،
> **ويُدرج المطلوبُ في قائمة ما يحتاج جهازاً**. ولا يُملأ فراغُ الدليل بصياغة.
>
> ### امتيازٌ يُمنح لفئةٍ يصير علامةً عليها إن كان غيابُه مرئياً (قرارُ المالك 2026-08-22)
>
> **والحمايةُ في ألّا يُميَّز المُعفى، لا في منحه الإعفاء.**
>
> **ووقع مقيساً**: السائقةُ التي تختم الإدارةُ جنسَها **مُعفاةٌ من الصورة
> الشخصية** (البند ٥٢) — حمايةً لها. **وكلُّ كبتنٍ غيرِ مُعفى يجب أن يرفع
> صورتَه ليُعتمد**، فتُراجَع وتظهر للراكب. **فمن لا تظهر صورتُه أبداً
> مُعفاةٌ — أي امرأة.** والإعفاءُ صار **علامةً** على من وُجد ليحميه.
>
> **وأخبثُ ما فيه أن اللحظةَ كانت سليمة**: قِيس أن الردّين — لمُعفاةٍ ولمن
> تنتظر صورتُه المراجعة — **متطابقان بالبايت** (٤٠٤ بنفس الجسم والترويسة).
> **فالوشايةُ في الحالة المستقرّة لا في الاستجابة**، ولا يكشفها فحصُ ردٍّ
> واحد مهما دقّ. **والزمنُ هو القناة.**
>
> **والعلاجُ ليس إخفاءَ الفرق بل إزالتَه**: البابُ يردّ **صورةً دائماً** —
> الحقيقيةَ لمن رُوجعت، **وحرفَ اسمه مرسوماً في الخادم** لمن سواه. فلا غيابَ
> يُرى أصلاً. **وثلاثُ قنواتٍ تُغلق معاً**: رمزُ الحالة (٢٠٠ دائماً)، والنوعُ
> (`image/jpeg` دائماً ولو كان الأصلُ PNG)، **والطولُ — ثابتٌ بالبايت بحشوٍ
> بعد علامة نهاية JPEG**. **ولولا الحشو لبقي الطولُ قناة**: وجهٌ ٢٠ ك.ب وحرفٌ
> ٢٫٣ ك.ب، ومن يعدّ البايتات يعرف.
>
> **ولا حقلَ `has_photo`** — الطلبُ هو الجواب؛ وحقلٌ يقول «له صورة» يعيد
> الوشايةَ من بابٍ آخر.
>
> **والقاعدةُ تتجاوز الصور**: كلَّما مُنح استثناءٌ لفئةٍ — إعفاءٌ من وثيقة، أو
> من رسم، أو من خطوة — **يُسأل: هل يُرى أثرُه؟** فإن رُئي فقد صار الاستثناءُ
> بطاقةَ تعريف.
>
> ### وبوّابةٌ تصيح حيث لا خطر تُفرَّغ المطلقةُ من داخلها (قرارُ المالك 2026-08-22)
>
> **وهي أخطرُ من بوّابةٍ غائبة**: الغائبةُ تتركك حيث كنت، وهذه **تعلّم مشغّلَها
> التجاوز** — فيصير `TAXO_MONEY_OK=1` عادةً تُكتب بلا قراءة، **وتُفقد الثقةُ
> بصياحها يومَ يكون في محلّه**.
>
> **ووقع مقيساً**: المطلقةُ الثانية («لا رفعَ يمسّ جدولَ مالٍ بلا إذن») كانت
> تُقاس بـ**مدى الإيداعات**: أيُّ إيداعٍ بين الخادم وHEAD مسَّ ترحيلةً أو
> نموذجاً فيه اسمُ جدولِ مال. فأوقفت **نشرَ صفحةِ تنزيل** — لأن شجرةَ الخادم
> متأخّرةٌ ٧٣ التزاماً، **والترحيلتان المُبلَّغُ عنهما مطبَّقتان سلفاً**
> (`alembic_version = 0052`)، **والأمرُ لا يرسل ملفَّ خلفيةٍ واحداً**.
>
> **فالعِلّةُ في القياس لا في القاعدة** — والقاعدةُ لم تُمسّ. صار السؤالان:
> **أثمّة ترحيلةٌ معلَّقة؟** (رأسُ القاعدة على الخادم مقابل الشجرة) **وهل ما
> يُرسَل في هذه الدفعة يمسّ نموذجاً أو ترحيلة؟** — وسكوتُهما معاً هو الجواب.
>
> **والقاعدةُ العامة**: **حارسُ المطلقات يقيس ما سيقع لا ما في التاريخ.** وما
> لا يقع اليومَ ليس خطراً اليوم؛ وإدراجُه يجعل الإذنَ الاستثنائيَّ روتيناً،
> **وهو الطريقُ الوحيدُ الذي تُفرَّغ به مطلقةٌ بلا أن يقرّر أحدٌ إفراغَها**.
>
> ### وبابٌ يصيح ثم يخرج بصفرٍ ليس باباً (قِيس 2026-08-24)
>
> **من عائلة «بابٌ يفرض قاعدةً يُقاس أنه يفرضها لا أنه يمرّ»، وفي أخطر
> مواضعها: بوّابةُ الدمج نفسُها.**
>
> **ووقع مقيساً**: طُلب إثباتُ أن CI أخضر، **فإذا هو أحمرُ يُبلِّغ نجاحاً**.
> سجلُّ الوظيفة يقول بحروفه `1176 errors` و`EXIT=1` **ويطبع سطرَ السقوط
> بالعربية** — والخطوةُ والوظيفةُ والتشغيلُ كلُّها `success`.
>
> **والعلّةُ حرفٌ في صَدَفة**: `exit "${code:-1}"`. والبديلُ في `${var:-…}`
> يقع حين يكون المتغيّرُ **فارغاً أو غيرَ مضبوط — لا حين يكون صفراً**.
> و`code` صفرٌ **دائماً** هناك، لأن أمرَ الحاوية ينتهي بـ`echo` وهو ينجح مهما
> فعل ما قبله. **فسطرُ الفشل كان `exit 0` حرفياً.**
>
> **وعطبٌ ثانٍ اختبأ خلفه**: المجموعةُ كانت تعمل في CI **بلا قاعدةٍ ولا
> Redis** — `--no-deps` مقصودٌ في الباب (لا يُعاد تشغيلُ خدمةٍ صحيحةٍ لأجل
> مجموعة)، **وثمنُه أنه لا يُقيمها إن غابت**، ولا خطوةَ في سير العمل تُقيمها.
> **فكانت البوّابةُ تُشغّل شيئاً لا يستطيع أن ينجح، ثم تعلن نجاحه.**
>
> **والدرسُ في العلاقة بينهما**: الأولُ **يُخفي** الثاني، والثاني وحدَه كان
> سيُكشف في أوّل تشغيل. **فعطبٌ في الإبلاغ أخطرُ من عطبٍ في العمل** — لأنه
> يُبطل كلَّ قياسٍ بعده، **وكلُّ خضرةٍ سابقةٍ لتلك الوظيفة صارت غيرَ مُثبَتة**
> ولا تُنقل شهادةً.
>
> **والقاعدة**: كلُّ بابٍ يُفترض فيه أن يمنع **يُقاس بإسقاطٍ متعمَّد** — لا
> يكفي أن يُرى وهو يمرّ، **ولا أن يُرى وهو يطبع رسالةَ سقوط**: يُقرأ **رمزُ
> خروجه**. وهي «صمتُ الحارس يحتاج إثباتاً» بوجهها الثالث: هناك حارسٌ لا يقرأ
> شيئاً، وهنا **حارسٌ يقرأ ويحكم ويقول الحكم — ثم لا يُنفّذه**.
>
> **وذيلٌ عمليّ**: `${x:-y}` **لا يحرس من الصفر**. وحيثما كان الصفرُ هو
> «النجاح» فالكتابةُ الصحيحةُ شرطٌ صريح — أو **قراءةُ الرمز من الأثر الذي
> كتبه صاحبُ العمل نفسُه** (`EXIT=` في ملفِّ المخرَج) لا من الأمر الذي
> غلّفه، **فالغلافُ ينجح والمغلَّفُ يسقط**.

> ### وخُضرةٌ كاذبةٌ على جهاز المطوّر أخطرُ منها في CI (قرارُ المالك 2026-08-24)
>
> **الشكلُ يُسمّى بموضعه لا بآليته** — فآليتُه تتبدّل، **وموضعُه هو الذي
> يقرّر ثمنَه**.
>
> **والموضعُ هنا هو الذي يُتَّخذ فيه قرارُ الدفع.** خُضرةٌ كاذبةٌ في CI
> تُكشف عند أوّل قراءةٍ للسجلّ، **وخُضرةٌ كاذبةٌ على جهازك تُقرأ إذناً
> بالدفع** — فما بعدها كلُّه مبنيٌّ عليها: التقرير، والإيداع، والشهادة التي
> تُنقل إلى المالك. **وأنت لا تعود إليها، لأنك رأيتها خضراء.**
>
> **فيُقاس البابُ الذي تُشغّله أنت بالصرامة التي تُقاس بها البوّابة** — لا
> أهون. والعكسُ هو ما يقع عادةً: تُبنى الحراسةُ للبعيد ويُوثَق بالقريب.
>
> **وآليتُها في هذه المرّة** (تُقرأ مثالاً لا تعريفاً):
>
> `suite.sh` يقرأ حكمَه من `backend/.suite.out` (`grep -c '^EXIT=0$'`)،
> **ولم يكن يمسح الملفَّ قبل التشغيل**. فتشغيلٌ يسقط **قبل أن يكتب حرفاً**
> — أمرُ حاويةٍ مكسور، أو صورةٌ لا تُبنى — **يقرأ حكمَ التشغيل الذي قبله
> ويعلن «المجموعةُ خضراء»**.
>
> **ووقع مقيساً**: كُسر أمرُ الحاوية بتعليقٍ وُضع بين أسطر الاستمرار،
> **فلم يعمل شيءٌ البتّة** — **وأعلن البابُ خضرةً محلياً**، وسقط في CI حيث
> الاستنساخُ نظيفٌ ولا ملفَّ فيه.
>
> > **والخضرةُ الكاذبةُ على جهاز المطوّر أخطرُ منها في CI**: هذا هو الموضعُ
> > الذي يُقرَّر فيه الدفعُ أصلاً. فمن رآها اطمأنّ ودفع، **والبوّابةُ بعده
> > تقيس شيئاً لم يُقس عنده**.
>
> **والقاعدة**: **كلُّ بابٍ يقرأ حكمَه من أثرٍ على القرص يمسح الأثرَ قبل أن
> يبدأ.** وإلا فهو لا يقيس هذا التشغيل، **بل آخرَ تشغيلٍ نجح** — وذاك قد
> يكون بالأمس، وعلى شجرةٍ أخرى.
>
> #### وفحصُ الشكل ليس قياسَ السلوك — والشكلُ نفسُه بلغتين
>
> **`bash -n` مرّ على الأمر المكسور** لأن التعليقَ بعد `\` **سليمُ التركيب**
> وإن ابتلع بقيّةَ الأمر. **و`tsc --noEmit` خرج بصفرٍ على عطبِ نوعٍ حقيقيّ**
> لأن الجذرَ `{"files": []}` فلم يفحص ملفاً.
>
> **والاثنان شيءٌ واحدٌ بلغتين**: أداةٌ تفحص **الشكل** — تركيبَ صَدَفةٍ أو
> اتساقَ أنواع — **فتُنسب إليها شهادةٌ عن العمل**. وهي لم تُسأل عن العمل قطّ،
> **وسكوتُها جوابٌ عن سؤالٍ آخر**.
>
> **فالقاعدة**: **لا تُصدَّق أداةٌ تفحص الشكل وتُنسب إليها شهادةٌ عن السلوك.**
> والفاصلُ عمليٌّ وسهل: **أتستطيع هذه الأداةُ أن تُشغّل الشيء؟** فإن كانت لا
> تُشغّله فهي لا تشهد له — **مهما كان اسمُها ومهما كان رمزُ خروجها**.

> ### وعطبان يستر أحدهما الآخر يعيشان أطولَ من عطبٍ مفرد (قرارُ المالك 2026-08-24)
>
> **وهي أثقلُ من كلٍّ منهما وحدَه**، لأنها تشرح **لماذا نجَوا**: عطبٌ مفردٌ
> يصطدم بأوّل قياس، **وعطبان متساندان يُلغي كلٌّ منهما الأثرَ الذي كان
> سيكشف الآخر**.
>
> **ووقع مقيساً**: بوّابةُ CI كانت (١) تخرج بصفرٍ حين تسقط، **و**(٢) تُشغّل
> المجموعةَ **بلا قاعدةٍ ولا Redis**. **والثانيةُ وحدَها كانت ستنكشف في أوّل
> تشغيل** — ألفٌ ومئةٌ وستةٌ وسبعون خطأَ تهيئةٍ لا يُخطئها ناظر. **والأولى
> ابتلعت الإعلان**، فبقيت الثانيةُ مستورةً بعددِ تشغيلاتٍ لا يُعرف.
>
> **والقاعدة**: **حين يُصلَح عطبٌ في الإبلاغ يُبحث عن عطبٍ في العمل قبل إعلان
> الخُضرة** — فالإبلاغُ الكاذبُ لم يكن يستر نفسَه، **كان يستر شيئاً**.
> والسؤالُ الذي يُطرح فوراً: **ما الذي كان هذا الصمتُ يغطّيه طوال هذه
> المدّة؟** وإن لم يُعثر على شيء **فذلك نتيجةٌ تُقال**، لا سكوتٌ يُمرّ.
>
> #### **والسترُ يتراكم طبقاتٍ لا طبقةً واحدة** (تصحيحُ المالك 2026-08-24)
>
> **كُتبت هذه القاعدةُ لعطبين، فظهر ثالثٌ تحتهما في أوّل تشغيلٍ صادق.** فلا
> يُقال «أُصلح الساترُ فانكشف المستور» — **بل يُقال: أُصلحت طبقةٌ، وما تحتها
> لا يُعرف حتى يُشغَّل الباب**.
>
> **والثلاثةُ مقيسةٌ بترتيب انكشافها** (٢٠٢٦-٠٨-٢٤):
>
> | الطبقة | العطب | كيف انكشف |
> |---|---|---|
> | ١ | `exit "${code:-1}"` **يخرج بصفر** | بطلب إثباتِ خضرةِ CI — والسجلُّ يناقض الحكم |
> | ٢ | **المجموعةُ تعمل بلا قاعدة** (`--no-deps` ولا خطوةَ تُقيمها) | ظهر **بعد** إصلاح ١، في التشغيل ٤١ |
> | ٣ | **بيانُ اعتمادٍ مكتوبٌ في الكود** (`taxo:taxo`) وافق الجهازَ صدفةً | ظهر **بعد** إصلاح ٢، في التشغيل ٤٣ |
>
> **ولم يكن أيٌّ منها قابلاً للرؤية قبل الذي فوقه**: الثالثُ لا أثرَ له ما دام
> الاتصالُ لا يقع أصلاً، والثاني لا حكمَ له ما دام الحكمُ مبتلَعاً.
>
> **فالحكمُ الصريح**: **لا تُعلَن خُضرةٌ حتى يُشغَّل البابُ صادقاً مرّةً على
> الأقلّ ويُقرأ ما يخرج منه.** وإصلاحُ ساترٍ **ليس نتيجة** — هو **إذنٌ
> بالقياس** فحسب. ومن أعلن الخضرةَ عند إصلاح الطبقة الأولى كان سيُخطئ مرّتين
> قبل أن يبلغ القاع.
>
> **وعلامةُ أنك ما زلت في الطبقات**: كلُّ إصلاحٍ يُنتج **عطباً جديداً في
> الموضع نفسِه** لا في موضعٍ آخر. فذاك ليس تعثّراً — **هو نزولٌ منتظم**، ويُعدّ
> ويُكتب حتى يمرّ تشغيلٌ كامل.
>
> **ويسري على غير CI**: احتياطٌ ينجح فيستر ميزةً ميتة (الشكلُ الثاني عشر)،
> وحقلٌ يقيس تصريحاً لا واقعة، **وصنفٌ صحيحٌ بالصدفة يستر أخاه الخاطئ
> بالبنية** — كلُّها الصورةُ نفسُها: **ساترٌ ومستور**. **ومن أصلح الساترَ ثم
> أعلن السلامةَ فقد أعلنها عن الشيء الذي كان يستره.**
>
> #### وأثرُها في السجلّ: ما شهد به الساترُ يُشطب (قرارُ المالك 2026-08-24)
>
> **كلُّ خُضرةٍ سابقةٍ لوظيفة «المجموعةُ الكاملة» في CI تُشطب من الشهادة** —
> **لا تُنقل، ولا يُبنى عليها، ولا يُستثنى منها ما بُنيت عليه ثقةٌ في جولاتٍ
> ماضية** (نصُّ المالك). فالوظيفةُ كانت تُبلِّغ `success` **ولم تكن قادرةً
> على الفشل**، فخضرتُها لم تكن قياساً أصلاً.
>
> **والقاعدةُ العامّة خلفه**: **أداةٌ يثبت أنها لا تستطيع أن تقول «لا»
> تُشطب شهاداتُها كلُّها بأثرٍ رجعيّ** — لا تُخصم منها الحالاتُ التي «بدت
> صحيحة»، لأن التمييزَ بينها وبين غيرها هو بعينه ما لا تملكه.

> ### قيمةٌ من العالم الحقيقيِّ يقرؤها اختبارٌ لا يملكها — توافق جهازاً وتخالف آخر (قرارُ المالك 2026-08-24)
>
> **أثمنُ ما خرج من يوم CI، لأنه وقع ثلاث مرّاتٍ في يومٍ واحدٍ بثلاثة أقنعة.**
>
> | ما قُرئ | من أين | كيف انكشف |
> |---|---|---|
> | **ساعةُ الجدار** | زمنٌ حقيقيٌّ بين نداءين | `pause_charge` = ٢٫٠٠١ بدل ٢٫٠٠٠ — **٠٫٣ ثانيةٍ بالضبط** تحت حمل المجموعة |
> | **كلمةُ المرور التي وافقت صدفةً** | `taxo:taxo` مكتوبةٌ في الكود، و`.env.local` كلمتُه `taxo` | `InvalidPasswordError` على **١١٧٦** اختباراً في CI |
> | **القرصُ عند ٨٢٪** | `shutil.disk_usage` على مضيفٍ لا يملكه الاختبار | `filesystem_percent=82` على عاملِ GitHub |
>
> **والثلاثةُ شيءٌ واحد**: تأكيدٌ يقرأ **قيمةً لا يتحكّم فيها الاختبار** —
> فتوافقه على جهازٍ وتخالفه على آخر، **ولا شيءَ في الشجرة يتغيّر بينهما**.
>
> > **وما وافق صدفةً لا يُقاس بموافقته بل بما يجعله يخالف.** فسنةٌ من الخضرة
> > لا تقول شيئاً عن `taxo:taxo`؛ الذي يقول شيئاً هو **أوّلُ بيئةٍ تولّد كلمةً
> > غيرَها**. والسؤالُ الصحيحُ ليس «أيعمل؟» بل **«ما الذي لو تغيّر لأسقطه؟»** —
> > فإن كان الجوابُ شيئاً **خارج الشجرة**، فليس عندك قياسٌ بل مصادفةٌ مستمرّة.
>
> **والعلاجُ ليس إضعافَ التأكيد** — هو **تملُّكُ المُدخل**: يُثبَّت
> `disk_usage`، ويُقرأ العنوانُ من ملفِّ بيئةٍ مُصرَّح، **ويُقاس المعنى لا
> ناتجُ العملية** (حدٌّ لا مساواةٌ في رسم الوقفة). **فيبقى ما يحرسه كما هو،
> ويزول ما لا يملكه.**
>
> **وعلامتُه قبل أن يقع**: تأكيدٌ يذكر **رقماً دقيقاً** لكميّةٍ يولّدها
> العالم — زمنٌ، أو مساحةٌ، أو مسارٌ، أو ساعةُ نظامٍ، أو ترتيبٌ في قرص.
> **فيُسأل عند كتابته: من يملك هذه القيمة؟** فإن لم يكن الاختبارُ **فهي مُدخلٌ
> يُثبَّت، لا حقيقةٌ تُؤكَّد.**
>
> #### وأربعُ طبقاتٍ نُزلت في يومٍ واحد (2026-08-24)
>
> **ولا واحدةٌ منها كانت مرئيةً قبل التي فوقها:**
>
> | # | الطبقة | لم تكن تُرى لأن… |
> |---|---|---|
> | ١ | `exit "${code:-1}"` **يخرج بصفر** | — (هي الأعلى) |
> | ٢ | **المجموعةُ تعمل بلا قاعدة** | الحكمُ كان مبتلَعاً فلا أحدَ يقرأ السقوط |
> | ٣ | **بيانُ اعتمادٍ في الكود** | الاتصالُ لم يكن يقع أصلاً، فلا كلمةَ تُختبر |
> | ٤ | **قرصُ المضيف ٨٢٪** | المجموعةُ لم تكن تبلغ اختبارَ النسخ |
>
> **فالسترُ يتراكم**، **ولا يُعلَن نزولُه حتى يُشغَّل البابُ صادقاً ويُقرأ ما
> يخرج منه.** وكلُّ إصلاحٍ من هذه الأربعة **بدا نهايةً وكان إذناً بالقياس**.

> ### وتساوي الأعداد ليس تساويَ الأسباب (قرارُ المالك 2026-08-24)
>
> **رقمٌ يُقارَن بلا سببه ليس قياساً.**
>
> **ووقع مقيساً**: التشغيلُ ٤١ أخرج **١١٧٦ خطأً**، والتشغيلُ ٤٣ أخرج **١١٧٦
> خطأً** — **والعلّتان مختلفتان تماماً**:
>
> | | ٤١ | ٤٣ |
> |---|---|---|
> | العدد | ١١٧٦ | ١١٧٦ |
> | السبب | **لا قاعدةَ أصلاً** — لم تُقَم | **القاعدةُ قائمةٌ وترفض**: `InvalidPasswordError` |
>
> **ولو قُورن الرقمان وحدَهما لَقُرئ «لم يتغيّر شيء»** — والحقيقةُ أن طبقةً
> كاملةً أُصلحت بينهما، وأن الفشلَ انتقل من «لا يبلغ القاعدة» إلى «يبلغها
> فتردّه». **فالتقدّمُ كان في السبب لا في العدد.**
>
> **وعكسُها يقع أيضاً**: عددان مختلفان بسببٍ واحد — كأن يسقط ٣ ثم ٧ من علّةٍ
> واحدةٍ اتّسع أثرُها.
>
> **فالقاعدة**: **يُقرأ السببُ ثم يُقرأ العدد**، ولا يُنقل رقمٌ في تقريرٍ بلا
> السبب الذي أنتجه. **وتساوي رقمين بين تشغيلين لا يُقرأ «لم يتغيّر شيء» حتى
> يُقارَن سببُهما.**

> ### وحالُ الإنتاج لم تكن مشتقّةً من git يوماً — والبوّابةُ الرابعةُ تصف ما ليس كذلك منذ كُتبت (قرارُ المالك 2026-08-22)
>
> **من عائلة الجدول الأحمر، وأخطرُ مواضعها**: `scripts/deploy.sh` — البابُ
> الذي وُجد **ليفرض** الخمسَ لأن «المكتوبَ لا يُطبَّق والحارسَ يُطبَّق».
>
> **ورأسُه يعدّ خمساً ويطبّق ثلاثةً ونصفاً**: ١ إعلان · ٢ دفعٌ وCI · ٣ نسخة ·
> ٤ **تحقّقُ النسخة** (وهو جزءٌ من الثالثة) · ٥ `tar -cf - "$@" | ssh … tar -xf -`.
> فـ**الرابعةُ لم تكن مبنيّةً البتّة** — لا سحبَ ولا ترحيلةَ ولا إعادةَ
> حاويات — **والخامسةُ لم يكن لها وجودٌ أصلاً**.
>
> **وأسوأُ من غيابها أنها تفعل عكسَها**: نصُّها «**الخادمُ يسحب من GitHub
> نفسَ الإيداع الذي خضّره CI — لا من جهاز أحد**»، **وتنفيذُها دفعُ ملفاتٍ من
> قرص المطوّر**. فالبابُ يمرّ أخضرَ وقد فعل الشيءَ الذي وُجد ليمنعه.
>
> **والثمنُ مقيسٌ على الإنتاج**: ٨٣ ملفاً خارج الإيداع (٥٠ معدَّلاً و٣٥ غيرَ
> متتبَّع)، **ومنها الترحيلتان `0051` و`0052`** — **والقاعدةُ عند ترحيلةٍ لا
> وجودَ لها إلا كملفٍّ غيرِ متتبَّعٍ على قرصٍ واحد**. فلو سقط ذلك القرصُ لَما
> عرف أحدٌ ما الذي كان يعمل. **ولم يُكشف حتى فشل السحبُ لسببٍ آخرَ تماماً**
> (أرشيفٌ فارغ) — أي أن العطبَ نجا سنةً لأن **البابَ كان ينجح**.
>
> **والقاعدةُ التي تبقى**: **بابٌ يفرض قاعدةً يُقاس أنه يفرضها، لا أنه يمرّ.**
> وأوّلُ سؤالٍ عنه: **ما الذي يُقاس ليقول «تمّ»؟** — فإن كان الجوابُ «أنه لم
> يُخطئ» فهو ليس باباً بل مروراً. **والفحصُ الحاسم**: يُقرأ ما يفعله السطرُ
> **مقابل ما يعِد به عنوانُه**، سطراً سطراً — وهو ما لم يُفعل لهذا الملفّ قطّ
> لأن اسمَه كان يكفي.
>
> ### وحالُ ملفٍّ تعتمد على إعدادٍ يأتي مع السحب — فتُقاس بعده لا قبله (قرارُ المالك 2026-08-22)
>
> **«أهذا الملفُّ متتبَّع؟ أمُتجاهَل؟ أزائد؟» ليست صفةً في الملفّ**، بل **حكمٌ
> يصدره إعدادٌ** — `.gitignore` والشجرةُ المسحوبة. **وذلك الإعدادُ يأتي مع
> السحب**، فالقياسُ قبله يقيس عالماً آخر.
>
> **ووقع ثلاث مرّاتٍ في مسارٍ واحدٍ في يوم**:
>
> - قُرئ `.gitignore` **الهدفِ من الخادم قبل جلبه** — فخرج فارغاً، و
>   `--exclude-from` على فارغٍ **ينجح ولا يستبعد شيئاً**: تصفيةٌ عمياءُ مرّت
>   خضراءَ ساعةً، ولم يكشفها إلا رقمٌ مطبوع.
> - وصُفّي بتجاهُلِ **إيداع الخادم القديم** لا الهدف — فدخلت حزمتا APK
>   (١٦٫٥ م.ب) في «ما لا يعيده السحب»، **وهي مخرجُ بناءٍ يُعاد**.
> - ثم **بعد** أن نجح السحبُ صار الجوابُ **صفراً** — وهو **الحالُ المقصودة**،
>   فقرأه الفحصُ عطباً وأوقف رفعاً **لأن ما قبله نجح**.
>
> **والقاعدة**: كلُّ سؤالٍ حكمُه من إعدادٍ يتغيّر بالسحب **يُطرح في الطرف
> الذي سنصير إليه** — يُرسَل الإعدادُ من عندنا إن لزم، **ولا يُقرأ من طرفٍ لم
> يصله بعد**. وهي أختُ «`sshd -T` لا الملفّ» و«`openapi` لا `app.routes`»:
> **اقرأ من الشيء الذي سيحكم، لا من الذي بين يديك.**
>
> **وذيلُها الذي كلّف أكثرَها**: **الغيابُ ثلاثةُ معانٍ لا واحد** — نقصٌ، أو
> حالٌ مقصودة، أو عطبٌ في القياس. **ومن يخلطها يوقف على الصواب كما يوقف على
> الخطأ**، ورسالتُه لا تدلّ على أيِّهما — فيُبحث عن العطب في غير موضعه.
>
> ### ومفتاحٌ مبذورٌ بلا زرّ: ميزةٌ لا يعرف بها إلا من كتبها (قرارُ المالك 2026-08-23)
>
> **وهو «بابٌ بلا زرّ» في أخبث مواضعه**: هناك مسارٌ خلفيٌّ لا يناديه أحد،
> **وهنا ميزةٌ كاملةٌ مبنيّةٌ ومختبَرةٌ ومبذورةٌ في القاعدة — ولا سبيلَ إلى
> إشعالها**. فالبناءُ تمّ، والحارسُ صامت، **والمالكُ لا يعلم أنها موجودة**.
>
> > **أُصلح، وقِيس 2026-08-23**: `check:flags` أخضرُ و**الاثنان والعشرون كلُّها لها أزرار**. **والدرسُ يبقى والخبرُ يُحذف** — ومن كرّر الرقمَ بعد إصلاحه (وقع في هذه الجلسة) نقل خبراً متأخّراً على أنه حال.
>
**ووقع مقيساً**: من اثنين وعشرين مفتاحاً **ثلاثةَ عشرَ بلا زرّ في اللوحة** —
> ومنها `vehicle_skins_enabled` و`subscription_offers_enabled`، **ميزتان
> مبنيّتان بالكامل**. **وطلبهما المالكُ بنفسه فلم يجدهما**، فأُشعلتا من
> الخادم — **وإشعالُ مفتاحٍ من صدفةِ وصولٍ إلى قاعدةٍ ليس باباً**.
>
> **والوجهُ الآخرُ باقٍ وهو الأخطر، وقِيس بدقّةٍ أكبر 2026-08-23**: اثنتان وعشرون شاشةً، **ثمانٍ منها تكتب مالاً**، **وشاشتان فقط تقرآن مفتاحاً** — والسؤالُ ليس «أللشاشة مفتاح؟» بل **«أثمّة مفتاحٌ يوقف الأذى الذي تصنعه؟»**. نصفُ
> شاشات اللوحة **لا يمكن إطفاؤها إن ساءت**. فالسؤالُ سؤالان لا واحد: «أللمفتاح
> زرّ؟» و«أللزرِّ مفتاح؟»، **وهو الاتجاهان اللذان يُسأل عنهما كلُّ حارسٍ يقارن
> مجموعتين**.
>
> ### ومفتاحٌ بُني ليوقف الأذى **ولا يُطفأ** — بابٌ بلا زرّ في اتجاهٍ واحد (قرارُ المالك 2026-08-24)
>
> **وهذا أثقلُ ما في العائلة**: «مفتاحٌ مبذورٌ بلا زرّ» يترك ميزةً لا تُشعَل،
> **وهذا يترك حارساً لا يُطفأ** — أي أن الشيءَ الذي بُني ليوقف الأذى **هو
> نفسُه المعطَّل**. والفرقُ في اتجاه الضرر: ميزةٌ لا تُشعَل خسارةٌ مؤجَّلة،
> **وحارسٌ لا يُطفأ خسارةٌ في اللحظة التي وُجد لها**.
>
> **ووقع مقيساً**: بُني مفتاحا مالٍ — تجميدُ التسعير وإيقافُ الصرف — بخلفيةٍ
> وثمانيةِ اختباراتٍ وزرَّين وشريطَين. **وشرطُ «هذا حارس» في الشاشة كان
> مفتاحاً واحداً مكتوباً بيده**:
>
> ```ts
> const isGuard = key === "otp_verification_enabled";
> ```
>
> فلمّا دخل المفتاحان `GUARDED_FLAGS` في الخلفية **لم يرثا شيئاً**: لا وسمَ
> «حارس»، ولا ورقةَ سببٍ تُكتب، **والضغطةُ ترسل طلباً بلا سببٍ فيرتدّ ٤٢٢**.
> فالمفتاحان **يُشعَلان ولا يُطفآن**، وهما إنما وُجدا للإطفاء.
>
> **ولم يكشفه اختبارٌ ولا حارس، بل قياسٌ من المتصفّح.** والثمانيةُ خضراء —
> لأنها تقيس **الخلفية**، والخلفيةُ سليمة. و`check:flags` أخضرُ — لأنه يسأل
> «أللمفتاح زرّ؟» **وللمفتاح زرٌّ فعلاً**. و`tsc` أخضرُ لأن الشرطَ صحيحُ
> النوع. **فكلُّ طبقةٍ صدقت عن نفسِها، والوظيفةُ معطَّلة.**
>
> **والسؤالُ الذي لم يكن يُسأل**: ليس «أللمفتاح زرّ؟» ولا «أللزرِّ مفتاح؟»
> بل **«أيعرف الزرُّ أنّ مفتاحَه حارس؟»** — وهو سؤالٌ ثالثٌ لا يجيبه أيٌّ من
> الأولين.
>
> **وصار حارساً** (قرارُ المالك 2026-08-24): مُدَّ `check:flags` إلى مرآةٍ
> ثالثة تقارن `GUARDED_FLAGS` في اللوحة بها في الخلفية **في الاتجاهين** —
> ناقصٌ يعني حارساً بلا ورقةِ سببٍ فلا يُطفأ، وزائدٌ يعني ورقةً تُطلب ولا
> يشترطها أحد. **ومعه المصرّفُ**: الاتحادُ يُشتقّ من المصفوفة (`as const`)
> فـ`Record<GuardedFlag, …>` يرفض حارساً بلا نصِّ أثر.
>
> **والقاعدةُ العامّة التي تتجاوز المفاتيح**: كلَّما كان لشيءٍ **صفةٌ تُغيّر
> كيف يُعامَل** — «هذا حارس»، «هذا مالٌ»، «هذا لا يُحذف» — **تُقرأ الصفةُ من
> مجموعةٍ لها مصدرٌ واحد، ولا تُكتب في شرطٍ باسمِ أوّلِ من حملها**. فالشرطُ
> باسمٍ مفردٍ **صحيحٌ يومَ يُكتب**، ويصير كذباً صامتاً عند الثاني — **ولا
> يفشل شيءٌ حين يصير كذلك**.
>
> **وذيلٌ من الحادثة نفسِها**: ورقةُ السبب ونصُّ الرفض كانا يقولان «مفتاح
> التحقق» **لمن جمّد التسعير** — وهي العلّةُ التي فُصلت لأجلها
> `GUARDED_FLAGS` عن `DEFAULT_ENABLED_FLAGS` أصلاً، **عادت من بابِ من ورث
> المجموعةَ ولم يرث نصَّها**. فما يُوسَّع من واحدٍ إلى مجموعةٍ **يُسأل عن
> نصِّه كما يُسأل عن شرطه**.
>
> **وثالثةٌ ظهرت في القياس نفسِه**: `Pricing.tsx` كانت **تُخفي** زرَّ الحفظ
> عند التجميد لا تُعطّله — **وتوثيقُ `GuardBanner` نفسِه يقول «الزرُّ يُعطَّل
> ولا يُخفى»**، و`Finance.tsx` تتبعه. **فشاشتان أختان تحرسان الشيءَ نفسَه
> بسلوكين**، والعلّةُ خاصّيةٌ واحدةٌ جمعت سببين لا يشبه أحدُهما الآخر:
> `canEdit = isAdmin && !frozen`. **وغيابُ الصلاحية يُخفي، والتجميدُ يُعطّل**
> — فمن جمعهما في قيمةٍ واحدةٍ فقد أحدَهما.
>
> ### وزرٌّ يكتب مسارَه بيده يقفز فوق `check:contract` (قرارُ المالك 2026-08-23)
>
> **والحارسُ يحرس البابَ ولا يرى من قفز السور.** `check:contract` يقارن كلَّ
> نداءٍ في `api/endpoints.ts` بفعلٍ ومسارٍ في الخلفية — **فمن بنى عنوانَه
> بيده في الشاشة (`${API_URL}/...`) لم يمرّ بالباب أصلاً**، ولا يُحسب ولا
> يُقاس ولا يظهر في عدد ما قرأه الحارس.
>
> **والقاعدةُ العامة**: كلُّ حارسٍ يقيس عبورَ **طبقةٍ** يُسأل: **ما الذي
> يستطيع تجاوزَ الطبقة؟** — فإن كان التجاوزُ ممكناً فالحارسُ يقيس المطيعين
> وحدَهم. **وعددُه الأخضرُ يقول «٢٥٧ نداءً سليماً» ولا يقول «وثلاثةٌ لم
> أرَها».**
>
> ### وثلاثُ تسمياتٍ لشيءٍ واحد — من عائلة `detail` (قرارُ المالك 2026-08-23)
>
> **اسمٌ واحدٌ لمعنى واحد.** «مركباتي» في زرٍّ، و«المتجر» في عنوان، و«الكراج»
> في ثالث — **شيءٌ واحدٌ بثلاثة أسماء**، فلا القارئُ يعرف أنها واحدة، ولا من
> يبحث في الكود يجدها، **ولا من يشتكي منها يُفهَم عنه**.
>
> **وهي عائلةُ `detail` بعينها**: اسمٌ واحدٌ حمل معنيين (رسالةُ الخطأ العربية
> وقائمةُ 422) فقرأ العميلُ مصفوفةً وطبع `[object Object]`. **والاتجاهان
> ضرران**: معنىً بأسماء يُشتّت، واسمٌ بمعانٍ يكذب.
>
> **والعلاجُ سجلٌّ مركزيٌّ للنصوص**، لا بحثٌ واستبدال: النصُّ المكتوبُ حيث
> يُستعمل **يُنسخ عند ثاني مُستعمِل**، والرابعُ يخترع رابعاً.
>
> ### و«أثمّة قيمةٌ مخترعة؟» ليست «أينقص عضو؟» — سؤالان لحارسٍ واحد (2026-08-23)
<!--جديد-->

> ### ⚠ وثمنُ هذا الحدِّ قِيس بعد سنةٍ وأسبوعين — **٢٠٪ من دفترٍ يراه المشرف** (2026-09-07)
>
> **الحدُّ كُتب هنا 2026-08-23 وبقي نظريّاً.** وفي 2026-09-07 فُتحت اللوحةُ
> بعينٍ لا بقراءة، **فوُجد `tip_payment` و`cancellation_fee` مرسومَين
> بالإنجليزية** في درج ملفِّ راكبٍ بين «شحن» و«تسوية».
>
> **والمقياس**: `WalletTransactionType` **ثمانيةَ عشرَ في الخلفية وعشرةٌ في
> اللوحة** — **٢٣ صفّاً من ١١٥، أي ٢٠٫٠٪**.
>
> **وستّةُ أنواعٍ في شاشةٍ يراها الراكبُ نفسُه** (`customer-app`) — **وهي
> أسوأ**: المشرفُ يعرف المفاتيحَ الإنجليزية، **والراكبُ لا يعرف شيئاً**.
>
> **و`check:enums` كان أخضرَ في كلِّ تلك الأيام، وهو صادقٌ**: لا قيمةَ
> مخترَعة. **والسؤالُ الثاني لم يكن يُسأل** — وهو مكتوبٌ في هذا السطر بعينه.
>
> **فحدٌّ يُكتب ولا يُقاس ثمنُه يبقى حبراً**: كُتب هنا، وقُرئ مراراً، **ولم
> يتحرّك أحدٌ حتى فُتحت شاشة**. **والكتابةُ ليست قياساً.**
>
> **وعلاجُه `check:enum-coverage`** — سؤالُ «أينقص عضو؟» في طبقتين.
>
> #### وحارسٌ جديدٌ يُقاس قبل أن يُصدَّق
>
> **أوّلُ تشغيلٍ للحارس الجديد أعطى تسعةَ بلاغات — أربعةٌ منها كاذبة**:
> نمطُ قراءة مفاتيح الخريطة كان `[a-z_0-9]`، **و`JOD` و`JO` كبيرةُ الحروف**،
> فاتُّهمت `CURRENCY_LABEL` و`COUNTRY_LABEL` و`CURRENCY_FULL` بالنقص وهي
> كاملة.
>
> **ولو صُدِّق الحارسُ في أوّل تشغيله لَـ«أُصلحت» خرائطُ سليمة** — أو
> لَأُطفئ لأنه «يصيح على السليم»، **فيسقط معه العطبُ الحقيقيُّ الذي أمسكه**.
>
> **فالحارسُ الجديد يُقاس قبل أن يُصدَّق**، ونسبةُ الكذب في أوّل تشغيلٍ
> **٤ من ٩**.
<!--/جديد-->
>
> **`check:enums` كان يسأل أحدَهما ويُقرأ كأنه يسأل الاثنين.**
>
> | السؤال | ما يمسكه | ما يفلت |
> |---|---|---|
> | **أثمّة قيمةٌ مخترعة؟** | اتحادٌ نُسخ ثم زِيد عليه (`awaiting_confirmation`) | **النقص** |
> | **أينقص عضو؟** | اتحادٌ نُسخ ثم زاد التعدادُ بعده | — |
>
> **والثاني هو الذي يفلت من `tsc` أيضاً**: اتحادٌ أصغرُ **صحيحٌ في نفسه**،
> و`Record<Union, X>` عليه **كاملٌ بحقّ** — فلا شيءَ يشكو.
>
> **ووقع مقيساً**: `WalletTransactionType` اثنا عشرَ عضواً والخلفيةُ ثمانيةَ
> عشر. **فستةُ أنواعِ مالٍ تصل كشفَ الكبتن بلا اسم** — `TRANSACTION_LABEL[type]`
> ترجع `undefined` **فتُرسم حركةُ مالٍ بلا سطرٍ يسمّيها**: `advance` ·
> `advance_repayment` · `cancellation_fee` · `cancellation_compensation` ·
> `referral_bonus` · `skin_purchase`. **ثلاثةٌ منها مبالغُ تخرج من جيبه.**
>
> **وأمسك الحارسُ سابعاً في أوّل تشغيلٍ بعد المدّ**: `DriverStatus` ينقصه
> `deactivated` — حالٌ **تُكتب** (`services/deactivation.py`) و**تُقرأ**
> (`services/withdrawals.py`)، فحسابٌ مُلغىً يصل الشاشةَ **بسطرِ حالٍ فارغ**.
> **وتعليقُ `Account.tsx` كان يَعِد بأن حالاً جديدةً «تكسر البناء» — ولم
> تكسره**، وهو «تعليقٌ يَعِد بما لا يقع» في موضعٍ ثالث.
>
> **والقاعدةُ العامة**: كلُّ حارسٍ يقارن مجموعتين **يُسأل عن الاتجاهين**.
> ومجموعةٌ مسطّحةٌ تجيب «أهذه القيمةُ معروفة؟» **ولا تجيب «أينقص من هذا
> الاتحاد شيء؟»** — والثاني يحتاج **الخريطةَ باسمها**، لا المجموعةَ.
>
> ### وشكلان لشيءٍ واحدٍ — لا يمسكهما اختبارُ البابين لأنهما ليسا بابين (قرارُ المالك 2026-08-23)
>
> **الشكلُ الثامن يسأل: أبابان ينشران الشيءَ نفسَه ويفترقان؟** وحارسُه يقارن
> الردَّين حقلاً حقلاً. **وهذا سؤالٌ آخرُ لا يجيبه**: **بابٌ واحدٌ ينشر
> شكلين لشيءٍ واحد**، والشكلان **يفترقان في المعنى لا في الحقول**.
>
> **ووقع مقيساً**: مركبةُ الكراج تُخزَّن في خانتين — `store` للمتجر و`map`
> للخريطة. والبابُ واحدٌ (`art_url(skin.id, slot)`) **والحقولُ متطابقة**،
> **فاختبارُ البابين يمرّ**. لكنّ الرفعَ **ملفٌّ واحدٌ يملأ الخانتين**
> (`_trim_and_fit` بمقاسين)، فالمجسّمُ الواقعيُّ للنادرة يُصغَّر إلى ١٢٨
> ويوضع على الخريطة **بمنظوره الجانبيّ** — والخريطةُ تُرى من فوق. **فالسيارةُ
> على الخريطة ليست السيارةَ التي اشتراها، وهي مع ذلك «من مصدرٍ واحد».**
>
> **وما يجعله يفلت من كلِّ حارس**: لا حقلَ ناقصٌ (`check:config`)، ولا بابَ
> بلا زرّ (`check:doors`)، ولا ردَّين يفترقان (اختبارُ البابين)، **ولا شيءَ
> يفشل** — الملفُّ يُخدَم ٢٠٠ ويُرسم. **والفرقُ يراه إنسانٌ ينظر، ولا يقيسه
> شيء.**
>
> **والقاعدة**: حيثما كان لشيءٍ واحدٍ **أكثرُ من تمثيل** — مقاسان، منظوران،
> صيغتان — **يُسأل: أهما مشتقّان من أصلٍ واحدٍ اشتقاقاً صحيحاً، أم أن أحدهما
> يُصنع من الآخر بعمليةٍ لا تصلح له؟** والتصغيرُ يصلح لمقاس، **ولا يصلح
> لمنظور**.
>
> **وحارسُه ليس مقارنةَ ردّين بل شرطُ اكتمال**: ما لا يحمل تمثيلاته كلَّها
> **لا يُعرض** — وهو نفسُ حكم «ما لا رسمةَ له لا يُعرض في المتجر»، موسَّعاً من
> «أله رسمة؟» إلى «**أله كلُّ رسماته؟**».
>
> ### وتثبيتٌ يثبّت العقدةَ لا المسار — فحاويةٌ تخدم مجلَّداً محذوفاً (2026-08-22)
>
> **رابعُ فخاخ الحاويات، وأخبثُها**: الثلاثةُ السابقةُ تجعل الحاويةَ تبدو أنها
> فعلت ما طُلب؛ **وهذا يجعلها تخدم ماضياً لا وجودَ له على القرص**.
>
> **ووقع مقيساً**: `landing/` أُعيد إنشاؤها أثناء السحب (أُزيحت ملفاتُها ثم
> أعادها git)، **فتغيّرت عقدتُها**. و`docker` يثبّت **العقدةَ لحظةَ التشغيل**
> لا المسار — فبقيت الحاويةُ تخدم المجلَّدَ القديمَ **وقد حُذف**:
>
> | | |
> |---|---|
> | عقدةُ المضيف | `813073` |
> | عقدةُ الحاوية | `799107` |
>
> **وكلُّ ما نملكه كان صحيحاً**: الخادمُ سحب الحزمَ، والبصماتُ على القرص
> تطابق البيان، و`pull-release` أعلن ✓. **والحافةُ تخدم بناءَ ١٩ آب** —
> وقرأتُ ذلك أوّلاً «حافةٌ تخزّن»، **وكان الأصلُ نفسُه يخدم القديم**.
>
> **وما يكشفه العقدةُ لا الحجمُ ولا التاريخ**: `stat -c %i` على الطرفين. وأيُّ
> مقارنةٍ بالمحتوى **تكذب في الاتجاهين** — الملفُّ الجديد موجودٌ على القرص،
> والحاويةُ لا تراه.
>
> **والعلاجُ إعادةُ إنشاءٍ لا إعادةَ تشغيل**: `restart` يُبقي التثبيتَ كما هو،
> **و`up -d --force-recreate <خدمة>` وحدَها تُعيد حلَّ المسار**.
>
> **والقاعدةُ العامة**: **كلُّ مسارٍ مثبَّتٍ في حاويةٍ يُعاد إنشاؤها إن استُبدل
> المجلَّدُ نفسُه** — و«استُبدل» يشمل ما لا يبدو استبدالاً: `mv` لمحتوياته ثم
> إعادةَ إنشائها، وسحبَ git، وفكَّ أرشيفٍ فوقها. **والفحصُ عقدةٌ تُقارَن، لا
> ملفٌّ يُقرأ.**
>
> ### ومسارُ نشرٍ جديدٌ لا يُصدَّق حتى يمرّ مرتين (قرارُ المالك 2026-08-22)
>
> **أربعةُ فخاخٍ في مسارٍ واحدٍ يومَ بنائه** — وكلُّها في `scripts/deploy.sh`
> نفسِه، وكلُّها **صحيحةُ الشكل** حتى شُغِّلت:
>
> | الفخّ | ما كشفه |
> |---|---|
> | ترتيبُ البوّابات ترتيبُ اعتماد | إزاحةٌ قبل النسخة أذهبت ملفَّ compose |
> | نسخةٌ تُقاس بالاسم لا بالمحتوى | `.env` وصلةٌ — أرشيفٌ بلا سرّ يُعلَن محقَّقاً |
> | خطوةٌ تُهيّئ لأخرى تُنقض بنقضها | سحبٌ ساقطٌ ترك الشجرةَ منقوصةً دائماً |
> | حكمٌ من إعدادٍ يأتي مع السحب | تصفيةٌ عمياء، ثم صفرٌ يُقرأ عطباً |
>
> **وما يجمعها أن الباب كان سلسلةَ أوامرَ ناجحةٍ لا معاملةً لها حالٌ صحيحةٌ
> في كلِّ لحظة** — فكلُّ سقوطٍ ترك **نصفَ فعل**، وظهر أثرُه في **بوّابةٍ ليست
> بوّابتَه**.
>
> **فالقاعدة**: مسارُ نشرٍ يُبنى ويُقاس في يومٍ واحد **لا تكفيه مراجعةٌ
> واحدة**، **ولا يُصدَّق حتى يمرّ مرتين** — مرةً تُثبت أنه يعمل، ومرةً تُثبت
> أن نجاحَه ليس صدفةَ حالةٍ ابتدائية. **وأخصُّ ما يُعاد قياسُه: ما يفعله حين
> يسقط**، لا ما يفعله حين ينجح — فالسقوطُ هو ما لم يُجرَّب.
>
> ### ولا يُسأل عن وجود سرٍّ بصيغةٍ قد تطبعه (2026-08-22)
>
> **ووقع مقيساً**: أردتُ معرفةَ **هل** `GITHUB_TAXO_TOKEN` مضبوطٌ فكتبتُ
> `${VAR:+موجود}${VAR:-<فارغ>}` — **والثانيةُ تطبع القيمةَ حين تكون موجودة**،
> فخرج الرمزُ كاملاً في سجلِّ الجلسة. **والفحصُ نجح والسرُّ تسرّب.**
>
> **وهو أخطرُ من أن يكون زلّةَ صياغة**: قاعدةُ المشروع «**ولا سرَّ في سجلّه**»
> مكتوبةٌ في البوّابة الثانية، **والسجلُّ هنا محادثةٌ لا ملفّ** — لا يُنظَّف
> ولا يُعاد كتابته. وعلاجُه **تدويرُ الرمز**، لا حذفُ السطر: حذفُه يخفي أنه
> كان هناك، وهي القاعدةُ نفسُها التي تمنع تنظيفَ سرٍّ من التاريخ.
>
> **فالصيغةُ الوحيدةُ المسموحة** لسؤال «أموجودٌ؟»: `[ -n "$VAR" ] && echo موجود
> || echo فارغ` — **أو `${VAR:+موجود}` وحدَها بلا بديلٍ يتبعها**. ولا يُكتب
> `${VAR:-…}` عن متغيّرٍ قد يحمل سرّاً **البتّة**، لأن البديلَ يُقرأ حارساً
> وهو الذي يطبع.
>
> ### وحقلٌ يقيس أن مفتاحاً **مكتوب** لا أن ملفاً **موجود** (قرارُ المالك 2026-08-22)
>
> **من عائلة «الاحتياطُ الذي نجاحُه لا يُميَّز عن عمل الميزة»** (الشكلُ الثاني
> عشر) — **ووجهُه أن الحقلَ يُعلن ولا يقيس**. والتصريحُ والواقعةُ يتطابقان
> يومَ يُكتبان، **ثم يفترقان بلا أن يفشل شيء**.
>
> **ووقع مقيساً**: `has_artwork` بُنيت لتُخفي من المتجر مركبةً لا رسمةَ لها
> (قرارُ المالك: «وعدٌ لا يُنجَز أسوأُ من غيابه»)، **فقاست `asset_key is not
> None`** — أي أن **اسماً مكتوبٌ في عمود**. وقاعدةُ التطوير تحمل أربعةَ صفوفٍ
> بمفاتيحَ مخترعةٍ (`city-taxi` · `dragon` · `gold-coupe` · `silver-sedan`)
> **لا ملفَّ لواحدٍ منها في الحزمة** — فمرّت الأربعةُ من الحارس، **وبابُ
> الرسمة يردّ ٤٠٤ على كلِّ واحدةٍ منها**، أي أن المتجرَ كلَّه كان يُرسم
> مكسوراً. **والحارسُ الذي وُجد ليمنع ذلك بعينه كان يقول «سليم».**
>
> **وصيغتُه التي تُحفظ** (قرارُ المالك 2026-08-22): **احتياطٌ يعمل في موضعه
> أخفى عطباً في موضعٍ آخر.** وهو **الشكلُ الثاني عشر بوجهٍ جديد**: هناك
> احتياطٌ ينجح فيخفي أن **ميزتَه** ميتة، وهنا احتياطٌ ينجح **حيث وُضع** فيخفي
> عطباً **في مكانٍ لم يُوضع له**.
>
> **وما وقع**: `driverElement` تسقط إلى السيارة العامّة عند فشل الصورة —
> **وهو صوابٌ تامٌّ في الخريطة** (الشكلُ الثالثَ عشر: الغيابُ لا يُميَّز، فلا
> يصير من لا رسمةَ له معروفاً). **والصورةُ كانت تفشل لأنها ٤٠٤ لكلِّ مركبةٍ في
> الكتالوج** — والخريطةُ لم تشكُ لأن السقوطَ يعمل، **والمتجرُ كان يرسم بطاقةً
> مكسورةً ولم يفتحه أحد**.
>
> **والقاعدةُ التي تتبعها**: **الاحتياطُ يُسجَّل حيث يقع لا حيث يُرى أثرُه.**
> فمن يقرأ `driverElement` يرى احتياطاً مبرَّراً بعلّةٍ صحيحة، **ولا شيءَ فيه
> يقول إنه يبتلع ٤٠٤ يخصّ مورداً يقرؤه غيرُه**. ويُقال في موضع السقوط: **ما
> الذي يُبتلع هنا، ومن غيري يقرأ هذا المورد؟** — فإن كان له قارئٌ ثانٍ **فلا
> يُبتلع صامتاً** ولو صحّ ابتلاعُه هنا.
>
> **ولم يُكشف إلا بفتح شاشةٍ**: لا اختبارٌ خلفيٌّ رآه (المساعدُ كان يكتب
> `asset_key=name`، **فيتطابق التصريحُ والواقعةُ في الاختبار وحدَه**)، ولا
> بناءٌ، ولا حارس.
>
> **فالقاعدة**: كلُّ حقلٍ يجيب «أعندي كذا؟» **يُقاس بأداةِ من يستهلكه**، لا
> بوجود قيمةٍ في عمود — كما يُقرأ الإعدادُ من `sshd -T` لا من الملفّ الذي
> كتبتَه، وكما يُقرّ `storage.save` بالنجاح **بعد أن يرى الملفَّ بحجمه** لا
> بعد انتهاء النقل. **والعمودُ تصريحٌ، والملفُّ واقعة** — والسؤالُ الفاصل:
> **من كتب القيمةَ التي أقارن بها، وهل يستطيع أن يكذب؟**
>
> ### وشرطٌ لا يتحقّق أبداً يُقرأ حراسةً وهو تعطيل (قرارُ المالك 2026-08-22)
>
> **من عائلة «الاحتياطُ الذي نجاحُه لا يُميَّز عن عمل الميزة»** (الشكلُ الثاني
> عشر) — بوجهٍ أخبث: هناك **احتياطٌ ينجح فيخفي أن الميزةَ ميتة**، وهنا
> **شرطٌ يُقرأ صرامةً وهو بابٌ مسدود**.
>
> **ووقع مقيساً**: `scripts/deploy-command.sh` — الأمرُ المفروضُ على مفتاح
> النشر — كان يشترط `TAXO_RELEASE_TOKEN` **من البيئة**. **و`sshd` لا يمرّر
> بيئةً إلى أمرٍ مفروض**، فالشرطُ **لا يتحقّق أبداً**: المفتاحُ المقيَّدُ
> يُردّ في كلِّ مرة، **ويُقرأ ذلك حراسةً محكمة** وهو تعطيلٌ كامل.
>
> **وما يجعله صامتاً أن الرفضَ هو المتوقَّع**: اختبارُ المفتاح يقيس **ما
> يُرفض**، فرفضٌ زائدٌ يبدو نجاحاً. **ولا يُكشف إلا بقياس الاتجاه الثاني** —
> أن الشكلَ السليم **يمرّ** — وهو السطرُ الذي أنقذه.
>
> **فالقاعدة**: كلُّ شرطٍ يقرأ من بيئةٍ أو ملفٍّ **يُقاس أنه يتحقّق في مساره
> الحقيقيّ**، لا في صدفةٍ يدويةٍ يضبطه فيها من كتبه.
>
> ### وغيابُ أداةِ القياس يوقف ولا يُقرأ سلامة (قرارُ المالك 2026-08-21)
>
> **وهي أهمُّ ما خرج من يوم CI**: حارسٌ **سكت في الموضع الذي وُجد له**.
>
> **ووقع مقيساً**: `tools/apk-manifest.mjs` يمنع نشرَ بناءٍ تغيّرت بصمتُه ولم
> يتغيّر `versionCode` — **ويقرأ الرقمَ بـ`aapt2`**. وفي عامل GitHub لم يكن
> `aapt2` في المسار الذي يبحث فيه، **فخرج الحقلُ فارغاً**، و`Number(undefined)`
> هو `NaN`، **وكلُّ مقارنةٍ به تُرجع `false`** — فمرّ الحارسُ صامتاً.
>
> **وموضعُ سكوته هو بيتُ القصيد**: صار النشرُ يقع من CI لا من جهاز، أي أن
> هذا الحارسَ صار **الوحيدَ الذي يقف بين الناس وحزمةٍ لا يقرؤها أندرويد
> تحديثاً** — وسكت هناك بالضبط.
>
> **فالقاعدة**: **أداةُ القياس إن غابت وقف الحارسُ وقال إنها غابت.** ولا
> يُقرأ غيابُها سلامةً، ولا يُستبدل بها افتراضٌ (`?? 0`) — فالافتراضُ هنا
> **يصنع الجوابَ الذي يمنعه الحارس**.
>
> **وقرينتُها في العائلة**: «حارسٌ يُشغَّل حيث لا يملك ما يقيسه يعلن *لم
> يُقس*». الفرقُ أن تلك **سياقٌ لا شأنَ له به فيخرج بصفر**، وهذه **قياسٌ هو
> شأنُه وأداتُه مفقودة فيخرج بواحد**. **والخلطُ بينهما يحوّل الأولى إلى بابٍ
> للثانية**: «لم يُقس» تُكتب حيث الصوابُ «قف».
>
> ### وحارسٌ يُشغَّل حيث لا يملك ما يقيسه يعلن «لم يُقس» لا «سليم» (قرارُ المالك 2026-08-21)
>
> **وهو الوجهُ العمليُّ للقاعدة الخامسة**: «صمتُ الحارس يحتاج إثباتاً كما يحتاجه
> صياحُه». تلك تمنعه أن يمرّ أخضرَ وهو لم يقرأ شيئاً؛ **وهذه تمنعه أن يصيح
> حيث لا شيءَ ليقرأه أصلاً**.
>
> **ووقع مقيساً**: `check:served` يسأل «أهذه هي الحزمةُ التي بُنيت الآن؟»
> **وشُغِّل في CI — وCI تبني ولا تنشر**، فقارن حزمةَ العامل بحزمةِ جهاز
> المالك عبر النفق العامّ، **فأجاب «لا» أبداً**. وتعليقُ سير العمل كان يقول
> إنه «يمرّ هنا بلا خادم»، **والقياسُ نفاه**: الخادمُ معلَنٌ على الإنترنت.
>
> **وثمنُه أن الحارسَ يُطفأ أو يُتجاوَز البابُ من حوله** — وكلاهما أسوأُ من
> غيابه: الأولُ يُسقط ما يمسكه حقاً، والثاني يُبطل البابَ كلَّه.
>
> **فالقاعدة**: كلُّ حارسٍ يعرف **ما يملك قياسَه في هذا السياق**؛ وما لا
> يملكه **يُعلنه صراحةً ويخرج بصفر**، ويُسمّى الموضعُ الذي يُقاس فيه.
> `check:served` يقول اليوم: «لم يُقس — بيئةُ CI تبني ولا تنشر، ومحلُّه
> البوّابةُ الخامسة».
>
> ### وتوثيقٌ يصف ما ليس كذلك من عائلة الجدول الأحمر (قرارُ المالك 2026-08-21)
>
> **ووقع مقيساً مرتين في يوم**: توثيقُ `suite.sh` يقول «**البابُ واحدٌ في
> البيئتين**» وأن ملفَّ البيئة «يُصرَّح ولا يُثبَّت» — **و`docker-compose.yml`
> يثبّت `.env.local` في `env_file` لأربع خدمات**، فينقض التصريحَ صامتاً ويقف
> على استنساخٍ نظيف. وتعليقُ سير العمل يقول إن `check:served` «يمرّ بلا
> خادم» — وهو يصله.
>
> **وهو الجدولُ الأحمرُ بعينه**: جدولٌ في هذا الملف كان يصف «ما فعلته
> واتساب» وهو يصف **ما أبلغت به أدواتُنا**، فبُني عليه حكمٌ على طرفٍ ثالث.
>
> **والفرقُ بين هذا وبين تعليقٍ يَعِد بما سيأتي**: ذاك دَينٌ بلا موعد،
> **وهذا خبرٌ كاذبٌ الآن** — يُقرأ فيُبنى عليه، ويصرف القارئَ عن الموضع الذي
> فيه العطب. **فكلُّ جملةٍ توثيقٍ تصف سلوكاً تُقرأ دعوى تحتاج قياساً**، وما
> لم يُقس منها يُكتب «كذا هو المقصود» لا «كذا يقع».
>
> ### وخبرٌ في هذا الملفّ يُقرأ حالاً قائمة — فيحمل حالَه وتاريخَه أو يُحذف (قرارُ المالك 2026-08-23)
>
> **القاعدةُ السابقة تقول متى يُحذف الخبر. وهذه تقول ما يجب أن يحمله ما دام
> باقياً** — لأن الحذفَ لا يقع لحظةَ الإصلاح، وبين الإصلاح والحذف **يُقرأ
> الخبرُ ويُبنى عليه**.
>
> **ووقع مقيساً في الجلسة نفسِها**: «من اثنين وعشرين مفتاحاً **ثلاثةَ عشرَ
> بلا زرّ**» كان صحيحاً يومَ كُتب، **ثم أُصلح ولم يُحدَّث السطر**. فقرأتُه
> أنا — كاتبَ الملفّ — **ونقلتُه إلى المالك حالاً قائمةً في تقرير**، وبنى
> عليه ترتيبَ عملٍ كاملاً. **و`check:flags` كان أخضرَ طوال ذلك.**
>
> **وخطرُه أنه لا يُقرأ خبراً أصلاً**: نصُّ `CLAUDE.md` كلُّه يُقرأ «هكذا
> المشروعُ اليوم»، فالخبرُ فيه **يتنكّر في ثوب قاعدة** — ولا شيءَ في صياغته
> يقول إنه لحظةٌ مضت.
>
> **فالقاعدة، وهي شرطُ كتابةٍ لا شرطُ تنظيف:**
>
> | ما يُكتب | كيف يُكتب |
> |---|---|
> | **رقمٌ أو عددٌ أو حال** | **بتاريخه ملتصقاً به** — «١٣ بلا زرّ (2026-08-19)» — فمن قرأه بعد شهرٍ يعرف أنه يحتاج قياساً |
> | **وما له حارسٌ يقيسه** | **يُحال إلى الحارس ولا يُنسخ رقمُه** — «`check:flags` يقول كم»، فالرقمُ يُقرأ من مصدره الحيِّ لا من نصٍّ ميّت |
> | **ودرسٌ عن صنفٍ يتكرر** | **بلا رقمٍ أصلاً** — «مفتاحٌ يُبذَر بلا زرّ فلا يعلم به إلا كاتبُه»، وهذه لا تشيخ |
>
> **والفحصُ الفاصل قبل نقل أيِّ رقمٍ من هذا الملفّ إلى تقرير**: **أثمّة حارسٌ
> يقيسه؟** فإن كان **فشغِّله ولا تنقل**، وإن لم يكن **فقُل «مكتوبٌ بتاريخ
> كذا، ولم يُقَس اليوم»**. **ونقلُ رقمٍ من الملفّ بلا أحدهما هو الخطأُ
> بعينه** — وهو أخطرُ من الخبر المتأخّر نفسِه، لأن التقريرَ يُقرأ قياساً.
>
> ### وقبل أن تحذف نصّاً كذب: أخبرٌ هو أم درس؟ (قرارُ المالك 2026-08-22)
>
> **هذا هو المعيارُ الذي يمنع حذفَ ما يجب أن يبقى وإبقاءَ ما يجب أن يُحذف** —
> وبغيره يقع الخطأُ في الاتجاهين، وكلاهما غالٍ.
>
> | الصنف | ما هو | الحكم |
> |---|---|---|
> | **خبرٌ عن حالٍ قائمة** | «الحقلُ لا يظهر في أيِّ شاشة» · «الخادمُ متأخّرٌ ستَّ عشرةَ التزاماً» | **يُحذف إن كذب** — ولا يُترك سجلاً |
> | **درسٌ عن صنفٍ يتكرر** | «مبلغٌ يُعرَض وهو يتراكم ويصمت وهو يُحصَّل» | **يبقى**، ويُفصَل عن الحال **بسطرٍ فوقه** يقول إن هذه الحالةَ بعينها أُصلحت |
>
> **ولمَ لا يُترك الخبرُ سجلاً**: هو **صحيحُ الشكل** — مقيسٌ، مؤرَّخ، بجدولٍ
> وأرقام — فلا شيءَ فيه يشي بأنه متأخّر. ومن يقرؤه يبني عليه؛ **وهذا وقع
> مقيساً**: `HANDOFF.md` §٤ أوقف جلسةً كاملةً على «قرارِ المالك» في عطبٍ كان
> قد أُصلح في اليوم نفسِه. **وإبقاؤه «للتاريخ» يعيد الفخَّ لا يوثّقه.**
>
> **ولمَ يبقى الدرس**: قيمتُه ليست في الحقل الذي صمت بل في **أن الصنفَ يتكرر
> بحقلٍ آخر** — وحذفُه يُسقط حارساً بشرياً ويجعل الوقوعَ الثاني اكتشافاً من
> الصفر. **وأخطرُ من الحذف إبقاؤه بلا سطرِ الفصل**: يُقرأ حينها خبراً، فيعود
> الصنفُ الأول من باب الثاني.
>
> **والسؤالُ الفاصل**: **هل يُبطل الإصلاحُ هذا النصَّ أم يكمله؟** ما يُبطله
> خبر، وما يكمله درس. والثالثُ الذي لا يُخلط بهما: **تعليقٌ يَعِد بما سيأتي** —
> فذاك لا يُحذف ولا يُفصَل، بل **يُنقل بنداً في `HANDOFF.md`** (القاعدةُ فوقه).
>
> **ويُطبَّق على الملفات الثلاثة بحدوده**: `SPEC.md` و`HANDOFF.md` يحملان
> **الخبرَ والقرار** فالكذبُ فيهما يُحذف؛ و`CLAUDE.md` يحمل **الدرس** فالأصلُ
> فيه البقاءُ مع سطر الفصل. **ومن كتب خبراً في `CLAUDE.md` فقد أخطأ موضعَه**
> قبل أن يكذب.
>
> ### وشرطٌ زالت علّتُه ولم يُنزَع يمنع ما وُضع ليحرسه (قرارُ المالك 2026-08-21)
>
> **وهو الوجهُ الثاني لـ«قائمةُ أعذارٍ لا تُنظَّف تصير كذباً»**: تلك تسمح بما
> لم يعد يستحقّ السماح، **وهذا يمنع ما لم يعد يستحقّ المنع**. وكلاهما سطرٌ
> كُتب **وهو صحيح**، وبقي بعد أن زال سببُه — والفرقُ في اتجاه الضرر لا في
> الصنف.
>
> **ووقع مقيساً**: `scripts/deploy.sh` يموت عند البوّابة الثانية بسطرٍ يقول
> «CI لم يُقس بعد — يُكمَل حين **يوجد المستودعُ وأسرارُه**». وكان صادقاً يومَ
> كُتب. **وقد وُجد المستودع** (`origin` مضبوط) **ووُجد CI**
> (`.github/workflows/ci.yml`) — **والسطرُ باقٍ يمنع كلَّ رفع**، أي **يمنع
> البابَ الذي كُتب ليحرسه**.
>
> **وخطرُه أنه يُقرأ حكمةً**: من يجده يظنّ أن شرطاً لم يتحقّق بعد، **فينصرف
> إلى طريقٍ حول الباب** — وهو بالضبط ما يمنعه الباب. فالشرطُ الميتُ لا يُهمَل
> فحسب؛ **يدفع إلى تجاوزه**.
>
> **فالقاعدة**: كلُّ شرطٍ يُكتب بصيغة «حتى يوجد كذا» **يحمل معه كيف يُعرف أنه
> وُجد** — فحصاً يُجرى لا ذاكرةً تُستدعى. وما لا يستطيع فحصَ نفسِه **يُدرج
> بنداً في `HANDOFF.md`**، فيُقرأ في كلِّ جلسةٍ ويُقلَّم.
>
> ### وتعليقٌ يَعِد بما سيأتي لا يُقرأ ضماناً (قرارُ المالك 2026-08-21)
>
> **وقع مقيساً**: `device.ts` كان يقول `return "web"` وفوقه تعليقٌ يقول
> «**وتغليفُ Capacitor لاحقاً يجعله `ios`/`android` بلا تغييرٍ في العقد**».
> **وجاء اللاحقُ ولم يتغيّر السطر** — فكلُّ جهازٍ سُجِّل «ويب» وهو أندرويد،
> والتعليقُ نفسُه هو ما جعل القارئَ يمرّ عليه مطمئنّاً.
>
> **والوعدُ في تعليقٍ ليس له تاريخُ استحقاق**: لا يفشل بناءٌ حين يحين، ولا
> يصيح حارس. **فهو دَينٌ بلا موعد** — ومن كتبه يذهب، ومن يقرؤه يظنّه مُنجَزاً
> أو مؤجَّلاً بقرار.
>
> **فالقاعدة**: ما يُنتظر يُكتب **بنداً في `HANDOFF.md`** أو **شرطاً يفشل**،
> لا جملةً في تعليق. وما بقي في تعليقٍ يُقرأ وصفاً لما هو **قائمٌ الآن** لا
> وعداً بما سيصير.
>
> **وقريبُه في اليوم نفسِه**: صنفا لونٍ (`warn-soft`/`warn-brd`) **غيرُ
> موجودَين في السلّم** كُتبا فصُرِّفا بلا أثرٍ ولا خطأ — وهو فخُّ
> `check:scale` نفسُه في ثوب لون، **والحارسُ يقرأ السلالمَ الرقمية وحدَها
> فمرّ أخضر**. أُمسك بالقراءة لا بالبناء.
>
> ### وعقدٌ يُجمَّد ناقصاً ليس عقداً (قرارُ المالك 2026-08-22)
>
> **من عائلة «شرطٌ زالت علّتُه ولم يُنزَع»، بوجهٍ يضرب أربعةً دفعةً واحدة.**
>
> **ووقع مقيساً**: جمّدتُ عقدَ ميزةٍ قبل توزيعِ العمل — مخططاتٍ وأخطاءً
> مسمّاةً ونماذجَ — **وأودعتُ النماذجَ بلا ترحيلتها**. فسقطت **تهيئةُ مجموعة
> الاختبارات كلِّها** بـ«relation does not exist»، أي أن **الفروعَ الأربعةَ
> بدأت حمراء**، ولم يكن العطبُ من أحدهم.
>
> **وخطرُ التجميد أنه يُقرأ ضماناً**: من يُعطى «عقداً مجمَّداً» يبني عليه ولا
> يفحصه — فالنقصُ فيه **ينتقل إلى كلِّ فرعٍ بلا أن يراه أحد**، بخلاف نقصٍ في
> ملفٍّ يملكه واحد.
>
> **فالقاعدة**: ما يُجمَّد **يُشغَّل قبل أن يُسلَّم** — مجموعةٌ خضراءُ مرةً
> واحدةً على القاعدة نفسِها التي ستُبنى عليها الفروع. **والتجميدُ بلا تشغيلٍ
> إعلانُ جاهزيةٍ لم تُقَس.**
>
> ### وأربعةُ وكلاءَ في نسخةِ عملٍ واحدةٍ ليسوا أربعة (تجربةٌ مقيسة 2026-08-22)
>
> **الجواب: أسرعُ في الإنتاج الخام، ومعطوبُ العزل — والقياسُ يُكتب ولو كان
> «لا»، فتجربةٌ مقيسةٌ فشلت خيرٌ من تجربةٍ تُعاد كلَّ ستة أشهر.**
>
> | المقياس | العدد |
> |---|---|
> | زمنُ الجدار للأربعة متوازين | **≈٤٥ دقيقة** (أطولُهم ٢٧٠٣ث) |
> | مجموعُ أزمنتهم = تقديرُ التسلسل | **≈٢س ٤٥د** (٩٨٧٢ث) |
> | النسبةُ الخام | **≈٣٫٧×** |
> | إيداعاتٌ نجت | ٤ فروع · ٦ إيداعات · ≈٩٠٠٠ سطر |
> | **تصادماتٌ بنيوية** | **٢** (نسخةُ عملٍ واحدة · قاعدةُ اختبارٍ واحدة) |
> | ردُّ فرعيٍّ عن ملفٍّ يملكه غيرُه | **١** (الترحيلةُ سُحبت مني إليّ) |
> | إعادةُ عملٍ بسبب عقدٍ تغيّر تحت وكيل | **١** (طبقةُ عرضٍ كاملة) |
> | **مُخرَجٌ ضاع قياسُه** | **٢٥ اختباراً** لم يُشغَّل منها واحد |
>
> **والعطبان البنيويّان هما الدرس، لا النسبة:**
>
> 1. **نسخةُ عملٍ واحدةٌ لأربعةِ كُتّاب**: `git checkout -b` عند الثاني **يدوس
>    فرعَ الأول**، و`HEAD` يتنقّل تحت من يكتب. اضطُرَّ اثنان إلى الإيداع
>    بأدوات git الدنيا (`commit-tree`/`update-ref`) بلا تحريك `HEAD`، وفتح
>    ثالثٌ **شجرةَ عملٍ منفصلة** من تلقاء نفسه — **وهو الحلُّ الصحيحُ الذي كان
>    يجب أن أعطيَه ابتداءً**. **وإيداعي أنا نزل على فرعِ وكيلٍ لا على الأصل**
>    وما انتبهتُ إلا بقراءة `git branch --contains`.
> 2. **قاعدةُ اختبارٍ واحدةٌ باسمٍ ثابت** (`taxo_test` في `conftest.py`)،
>    و`suite.sh` **يرفض تشغيلاً ثانياً بحقّ**. فوكيلٌ كتب ٢٥ اختباراً **لم
>    يستطع تشغيلَ واحدٍ منها طوال الجلسة** — عملٌ تامٌّ ومجهولُ الحال، وهو
>    بالضبط «بُني ولم يُقَس».
>
> **فالشرطُ قبل أيِّ توزيعٍ قادم — الاثنان معاً ولا يُجزَّآن:**
> **شجرةُ عملٍ لكلِّ وكيل** (`git worktree` أو `isolation: worktree`)،
> **وقاعدةُ اختبارٍ لكلِّ وكيل** (اسمٌ مشتقٌّ لا ثابت). **وبدونهما التوزيعُ
> يُنتج كوداً ولا يُنتج قياساً** — والكودُ غيرُ المقيس في هذا المشروع ليس
> مكسباً.
>
> **وما نجح فيه فعلاً**: **تجميدُ العقد قبل التوزيع** — أربعةٌ كتبوا على شكلٍ
> واحدٍ فلم يقع الشكلُ الثامن بينهم؛ **وملكيةُ ملفٍّ لكلِّ وكيل** — لم يكتب
> اثنان في ملفٍّ واحدٍ ولا مرة؛ **وأنّ كلَّ واحدٍ أمسك عطباً في نطاقه**
> (`skin_purchase` غيرُ موجودةٍ في تعداد القاعدة · `lazy="joined"` يُسقط كلَّ
> قفلٍ على صفِّ الكبتن · مفتاحُ تفرّدٍ يتجاوز `VARCHAR(64)` · بديلٌ منشورٌ
> نادرٌ يعيد وشايةَ الشكل الثالثَ عشر من باب البديل).

> ### وما بدأناه لا يُبقى لأنه بدأ (قرارُ المالك 2026-08-22)
>
> **يُبقى لأنه يُقاس أفضلَ من بديله.** والبدءُ ليس حجّةً — وكلفةُ ما أُنفق
> ذهبت سواءٌ أكملنا أم رجعنا، **فإدخالُها في القرار يجعلها تُدفع مرتين**.
>
> **وموضعُه كلُّ اختيارٍ له بديلٌ قائم**: توزيعُ عملٍ على وكلاءَ فرعيين
> يُقاس بزمن الجدار وعددِ تصادمات الدمج **مقابل تقدير التسلسل**؛ وحارسٌ
> جديدٌ يُقاس في الاتجاهين؛ وصياغةُ اختبارٍ تُقاس بحذف ما تحرسه.
>
> **والقاعدةُ تُلزم بالقول لا بالظنّ**: من بدأ طريقاً ثم قاسه أسوأَ **يقوله
> صراحةً ويرجع**، ولا يُكمل لأن الرجوعَ يبدو تراجعاً. **والسكوتُ عن قياسٍ
> سيّئٍ أغلى من القياس نفسِه**، لأنه يجعل الطريقَ الخطأ سابقةً تُحتذى.

> ### قاعدةُ كلِّ حارس (قرارُ المالك 2026-08-20) — تُقرأ قبل الفهرس لا بعده
>
> **١) يُقاس في الاتجاهين قبل أن يُصدَّق.** يمسك عطباً **مصنوعاً** عمداً،
> **ويصمت على شجرةٍ سليمة**. واحدٌ منهما وحدَه لا يكفي: حارسٌ يمسك ولا يصمت
> ضجيجٌ يُطفأ، وحارسٌ يصمت ولا يمسك زينةٌ في ملفِّ البناء.
>
> **٢) ولا يُبنى على بلاغه الأول أمرٌ قبل قياسه استقلالاً.** حارسٌ **يخترع**
> عطباً أغلى من حارسٍ يفوته: الذي يفوته يتركك حيث كنت، والذي يخترعه ينفق عملاً
> على لا شيء **ويُفقد الثقةَ بما يجده حقاً**. وقد وقع مقيساً في ٢٠٢٦-٠٨-٢٠:
> `check:contract` في نسخته الثالثة أبلغ عن فعلٍ خاطئٍ على مسارٍ سليم، فصدر أمرُ
> إصلاحٍ لعطبٍ لا وجودَ له — و«الدليل» كان **مسبارَ المُبلِّغ نفسِه**.
>
> **٤) وشاشةٌ فارغةٌ ليست دليلاً حتى يُعرف سببُ فراغها.** وقع مقيساً في
> ٢٠٢٦-٠٨-٢٠: أُطفئت ميزةُ العروض فقُرئ اختفاءُ سطرِها من ورقة الترحيب برهاناً
> على أن السطر يتبع العرض — **والتطبيقُ كانت جلستُه ساقطةً أصلاً**، فلا ورقةَ
> كانت لتختفي. **والإثباتُ بدليلٍ خطأ يُقرأ إثباتاً** ويُغلق البابَ على
> المراجعة: النتيجةُ صحيحةٌ فلا أحدَ يعود إليها، والطريقُ إليها باطل. فيُسأل
> عن **سببِ** الفراغ قبل أن يُبنى عليه حكم.
>
> **٦) وتأكّد من العنوان الذي تقرأ منه قبل أن تحكم بغياب عنصر.** وقع مقيساً
> مرتين في 2026-08-21: قُرئ `#presign-note` **بعد** نقرِ زرِّ واتساب، وكانت
> النقرةُ قد نقلت الصفحةَ إلى `api.whatsapp.com` — **فقُرئت صفحةٌ أخرى وسُمّي
> ذلك غياباً**، وأُعلن مرتين أن عنصراً حاضراً ليس هناك. **فمع كلِّ حكمٍ
> بالغياب يُقرأ `location.href`** — وإلا كان الحكمُ عن صفحةٍ لا عن عنصر.
>
> **٨) ولا تقس صلاحيةَ كتابةٍ بمحاولة كتابة.** وقع مقيساً 2026-08-21: أردتُ
> معرفةَ ما تطلبه نقطةُ الكتابة في GitHub، فأرسلتُ `PUT` بجسمٍ فارغٍ متوقّعاً
> رفضاً — **فردَّ `201 Created` وأنشأ ملفاً في مستودع المالك**. حُذف في الحال،
> **وبقي أثرُه إيداعين في التاريخ** لا يُمحيان إلا بإعادة كتابةٍ ممنوعة.
> **فالقياسُ بالفعل تنفيذٌ لا قياس**: تُقرأ ترويسةُ الصلاحيات من نقطةٍ
> **قرائية** (`x-accepted-github-permissions`)، أو يُسأل الرمزُ عن نفسِه.
>
> **٩) وأداةٌ تصمت لا تُصدَّق حتى تُقاس في الاتجاه الثاني — ولو كانت
> مِسباراً عابراً.** القاعدةُ الخامسةُ تقولها للحرّاس، **وهذه تمدّها إلى ما
> تكتبه لنفسك في دقيقة**: مِسبارٌ يُشغَّل مرةً ويُبنى على جوابه **يُصدَّق
> كما يُصدَّق حارسٌ في ملفِّ البناء**.
>
> **ووقع مقيساً 2026-08-24**: كُتب مِسبارُ كنسٍ للألوان بـ`heredoc` في
> Git Bash — **فطوت الصدفةُ `\\b` إلى محرف backspace** (مقيسٌ: ملفُّ المخرَج
> يحمل `\b` واحداً لا اثنين). فلم يطابق التعبيرُ شيئاً، **ومرّ أخضرَ على
> عطبٍ حيٍّ وأعلن «شجرةٌ نظيفة»**. ولولا أنه أُعيد عليه العطبُ عمداً
> لَنُقلت «نظيفة» تقريراً — وبعد إصلاحه أخرج **أربعةَ أعطابٍ حيّةٍ** لم
> يكن أحدٌ يعلم بها.
>
> **والشكل**: **أداةٌ صامتةٌ تُقرأ نفياً**. والصمتُ هنا لم يكن جواباً بل
> **غيابَ سؤال**.
>
> **وذيلٌ عمليٌّ يخصّ هذه البيئة**: `heredoc` في Git Bash **يطوي `\\` إلى
> `\`** ولو كان المحدِّدُ بين علامتي اقتباس. **فلا يُكتب تعبيرٌ نمطيٌّ فيه
> هروبٌ عبر `heredoc` هنا** — يُكتب الملفُّ بأداةِ كتابةٍ لا تمرّ بالصَّدَفة،
> أو يُقرأ الناتجُ بـ`cat -A` قبل تشغيله.
>
> **١٠) وأمرٌ تكتبه بيدك للقياس يُقاس في الاتجاهين كما يُقاس الحارس.**
>
> **وتصحيحٌ في التسمية قبل القاعدة** (قرارُ المالك 2026-08-24): سُمِّي هذا
> أوّلاً **«حارساً كاذباً»** — **وليس كذلك**. لا حارسَ في هذا المشروع بالأمر
> الخاطئ؛ **الكاذبُ أمرٌ كتبتُه بيدي للقياس**. والفرقُ ليس لفظياً: حارسٌ
> كاذبٌ يُصلَح في ملفِّ البناء ويُصلَح للجميع، **وأمرٌ يدويٌّ كاذبٌ لا موضعَ
> لإصلاحه** — يعود في أوّل مرةٍ يكتبه أحدٌ ثانية، **فعلاجُه قاعدةٌ لا رقعة**.
>
> **والقاعدةُ على وجهها**: مع `{"files": [], "references": [...]}` — وهو
> شكلُ `tsconfig.json` في التطبيقات الثلاثة — **يفحص `tsc --noEmit` المجرَّدُ
> صفرَ ملفّ ويخرج بصفرٍ أبداً**، مهما كان في الشجرة. لا يتبع المراجعَ إلا
> وضعُ البناء `-b`. **فالخروجُ بصفرٍ هناك ليس شهادةً بل امتناعاً عن الفحص** —
> وهو «صفرٌ مقروءٌ يُقرأ سلامة» (القاعدةُ ٥) في ثوب أمرٍ يدويّ.
>
> **ومقيسٌ في الاتجاهين**: على عطبِ نوعٍ حقيقيٍّ (`TS2741`) أمسكه
> `npm run lint` وخرج بـ٢، **وخرج المجرَّدُ بصفر**. **وقِيست أبوابُ المشروع
> الثلاثةُ فوُجدت سليمةً كلُّها**: `tsc -b` في `build` و`tsc -b --noEmit` في
> `lint`.
>
> **فيُنادى بابُ المشروع** (`npm run lint` / `npm run build`) **ولا يُخترع
> أمرٌ يشبهه**؛ ومن اضطُرّ إلى أمرٍ يدويٍّ **أثبت أنه يمسك عطباً مصنوعاً قبل
> أن يبني على صمته**.
>
> **وكذب عليّ أمرٌ يدويٌّ مرتين في يومٍ واحد** (2026-08-24): هذا،
> **و`heredoc` الذي طوى `\\b`** فأعلن شجرةً نظيفةً على عطبٍ حيّ. **مرّتان في
> يومٍ ليستا صدفة**: الأمرُ اليدويُّ لا يمرّ بمراجعةٍ ولا باختبارٍ ولا
> بتاريخ، **فهو أضعفُ حلقةٍ في كلِّ قياس** — ويُعامَل معاملةَ الحارس لا
> معاملةَ الملاحظة.
>
> **٧) ولا تقارن بقيمةٍ كتبها مِسبارُك.** وقع مقيساً 2026-08-21: حُكم بأن خادماً
> «هو هو» لأن مفتاحَ مضيفه مطابقٌ لما في `known_hosts` — وكان مِسباري نفسُه قد كتبه
> هناك قبل دقائقَ بـ`StrictHostKeyChecking=no`. **فالمقارنةُ دارت على نفسها**،
> وبُني عليها بلاغُ «الخادمُ أغلق بابه» وكان الخادمُ غيرَ خادمنا أصلاً. **فيُستعمل
> `yes` في كلِّ مِسبارٍ يقيس هوية**، ليصير الاختلافُ رفضاً لا سكوتاً — ويُسأل قبل
> كلِّ مطابقة: **من كتب الطرفَ الذي أقارن به؟**
>
> **٥) وصمتُ الحارس يحتاج إثباتاً كما يحتاجه صياحُه.** كلُّ حارسٍ **يُعلن كم
> ملفاً قرأ**، و**صفرٌ مقروءٌ يُقرأ عطباً لا سلامة**. وهذا ما منع صياغةً ثانيةً
> من الدخول في 2026-08-20: `check:readers` كان يفحص المسارَ بتعبيرٍ يفترض `/`
> فاصلاً، فلم يطابق `src\lib\` على ويندوز — **فلم يقرأ ملفاً واحداً ومرّ
> أخضر**. ولو أُدرج حينها لبقي في القائمة حارساً لا يقرأ شيئاً، **يُحسب في
> العدد ويُطمئن**.
>
> **٦) واختبارٌ أخضرُ يحرس عطباً أخطرُ من اختبارٍ غائب — لأنه يمنع إصلاحه.**
> وقع مقيساً 2026-08-20: `test_what_he_carries_leaves_his_available_balance`
> كان يؤكّد `available == balance - dues` أي `0 − 0.750 = −0.750` — **فيحرس
> «الرصيد المتاح −٠٫٧٥٠ د.أ» على شاشة الكبتن**، ويُسقط إصلاحَه يومَ يُصلَح.
> والغائبُ يتركك حيث كنت؛ **وهذا يقف في وجه من يأتي بعدك ويقول: هنا قاعدةٌ
> محروسة.** وعلاجُه أن يقيس **المعنى** لا العملية — «يُطرح ويقف عند الصفر» لا
> «ناتجُ الطرح» — **وبشرطين لا واحد**، فلا يُستبدل النصفُ المحروسُ بأضعفَ منه.
>
> **وتعميمُها من واقع اليوم: القاعدةُ تسري على الاختبار كما تسري على الشاشة.**
> أولُ صياغةٍ لاختبار «بابان ينشران الشيءَ نفسَه» قاست **دفتراً فارغاً** —
> رحلةٌ منتهيةٌ لا تكتب قيداً حتى تُسوَّى، والكاشُ لا يكتب `ride_earning`
> أصلاً (§9). فكانت تقارن قائمتين فارغتين وتمرّ **خضراء**، وتحرس الفراغَ لا
> الحقول. **و`assert` قبل المقارنة هو ما يمنعه**: يُتحقَّق أن فيما تقيسه شيئاً
> **قبل** أن يُقاس. واختبارٌ أخضرُ لا يقيس شيئاً أسوأُ من غيابه، لأنه يُحسب في
> العدد ويُطمئن.
>
> **٣) وهذا يسري على التشخيص كما يسري على الحارس.** مطابقةُ عَرَضٍ بدرسٍ محفوظٍ
> في هذا الملف **ليست تشخيصاً**: في اليوم نفسِه شُخِّص تشغيلُ اختباراتٍ شاردٌ
> بأنه «`run` يرث `restart`» — درسٌ مكتوبٌ هنا — **والقياسُ نفاه**
> (`RestartPolicy=no`). المكتوبُ يصير قالباً جاهزاً يُلبَس لأول عَرَضٍ يشبهه،
> **والحارسُ لا يفعل ذلك لأنه يقيس**.

**القاعدةُ التي أنشأت هذا القسم**: في جلسةٍ واحدة أوقفني `check:enums` عن اتحادٍ
مختلط، **ووقعتُ في فخٍّ مكتوبٍ في هذا الملف حرفياً** — تشغيلُ اختباراتٍ شاردٌ
يمسك قاعدةَ الاختبار. **فالمكتوبُ لا يُطبَّق، والحارسُ يُطبَّق** (قرارُ المالك
2026-08-20). فما صار حارساً يُختصر هنا إلى إشارة، وما بقي نصّاً يُسمّى صراحةً
**لأنه هو الذي سيتكرّر**.

### الشكلُ الثالثَ عشر — رسمُ مالٍ يُحصَّل من جيبِ راكبٍ ولا يظهر على أيِّ شاشة (2026-08-21)

> **وهذا درسٌ لا وصفُ حال: العطبُ نفسُه أُصلح في اليوم نفسِه** (SPEC §٥٫١٠-ب/و)
> — السطورُ ترتسم اليومَ في الشاشات الأربع، ولها حارسان (`check:money-visible`
> واختبارُ البابين). **ويبقى القسمُ لأن الشكلَ يتكرر بحقلٍ آخر**، لا لأن هذا
> الحقلَ ما زال صامتاً. **والفرقُ بينهما هو ما حُذف من `SPEC.md` و`HANDOFF.md`
> في ٢٠٢٦-٠٨-٢٢**: درسٌ يُحفظ، وخبرٌ متأخّرٌ يُمحى.

**كلفتُه ليست في المبلغ بل في أنه غيرُ قابلٍ للمراجعة.** رحلةٌ بمحطتين على
تسعيرة الأردن تحمل **1.000 د.أ رسمَ محطات** (14٪ من عرضٍ قدرُه 7.212) ورسمَ
انتظارٍ بالدقيقة فوقهما — **كلُّه داخلٌ في `final_fare`، ولا سطرَ له في تفاصيل
الرحلة، ولا في شاشة الدفع، ولا في شاشة الكبتن المسمّاة «تفصيل السعر»، ولا في
اللوحة**. فالراكبُ يدفع رقماً لا يستطيع اشتقاقَه، والكبتنُ يقرأ نهائياً يخالف
المقدَّر بلا سبب، **والمشرفُ يفصل في نزاعٍ برقمين لا يفسّران الفرق** — وتوثيقُ
شاشته كان يَعِد بأنهما يفسّرانه.

**وما يجعله صامتاً**: الحقلُ **يُنشر** في كلِّ `RideOut`، **ويُقرأ فعلاً** —
لكن **أثناء تراكمه وحدَه** (`StopProgress` · `PauseNotice` · `ActiveRide`).
فهو يختفي **لحظةَ تحوّله من عدّادٍ إلى مبلغٍ يُدفع**. لا `tsc` يراه، ولا
`check:config` (يسأل عن **مرآةٍ** لا عن **قارئ**)، ولا `check:readers` (يمسح
`lib/` وحدَها)، ولا اختبارٌ خلفيٌّ (الحسابُ صحيحٌ بالثانية ومُختبَر).

**والقاعدةُ التي تبقى**: **كلُّ مبلغٍ يدخل `final_fare` له سطرٌ في التفصيل
وفي شاشة الدفع معاً** — الثانيةُ لأن المواصفة وعدت فيها بألّا تفاجئ
(§5.10)، والأولى لأن المجموعَ بلا مفرداتِه رقمٌ يُصدَّق ولا يُراجَع.
**وصفرٌ لا يُرسم**: سطرٌ فارغٌ يعلّم قارئَه أن يمرّ على السطور بلا قراءة.

#### وحارسُه: ما يمسكه وما **لا** يمسكه — يُقرأ قبل أن يُصدَّق

**الصنفُ الذي يُمسك بحارس**: مبلغٌ تحسبه الخلفيةُ **ولا يصل أيَّ واجهة** —
اسمُه لا يظهر في أيِّ من التطبيقات الثلاثة خارج `api/types.ts`. وهذا وقع
مقيساً من قبل: `pending_compensation` في محفظة الكبتن، و`stops_charge` قبل
اليوم.

**وما لا يمسكه، ويجب أن يُقال قبل أن يُبنى**: **العطبُ الذي أنشأه لم يكن من
هذا الصنف.** `waiting_charge` **كان يُقرأ** — في شاشة الوقوف. فحارسٌ يقيس
«هل لهذا الاسم قارئ؟» **يمرّ عليه أخضرَ**. الفرقُ ليس في وجود القارئ بل في
**أيِّ شاشةٍ يقرؤه**، وذلك يحتاج تصريحاً لكلِّ حقلٍ بأين يجب أن يظهر —
**وقائمةٌ تُملأ باليد هي بعينها «هل تذكّرتَ؟» التي يُبنى الحارسُ لإلغائها**.

**فالخلاصةُ التي تُحفظ**: حارسُ «لا يصل أيَّ واجهة» **يستحقّ البناء ويكسب
ثمنه**، **ولا يُقرأ على أنه يحرس هذا الشكل** — من يقرأ اسمَه ويطمئنّ يكون قد
استبدل بالمراجعة اطمئناناً، **وهو الثمنُ نفسُه الذي يدفعه توثيقٌ يَعِد بما لا
يقع**.

#### وقد بُني (2026-08-21) — **وأولُ نسخةٍ منه كانت خضراءَ وهي عمياء**

`tools/check-money-visible.mjs`، في بناء اللوحة وحدَها كـ`check:doors`
(السؤالُ عابرٌ للتطبيقات وجوابُه واحدٌ أينما شُغِّل). يقرأ حقولَ المال من
**مخططات الخلفية** ويشترط لكلٍّ قارئاً في أحد التطبيقات الثلاثة **خارج
`api/types.ts`** — فالمرآةُ تصريحٌ لا قراءة، وهي قاعدةُ `check:doors` نفسُها.

**ودرسُه أهمُّ منه**، وهو قاعدةُ الحارس مطبَّقةً على الحارس: **نسختُه الأولى
مرّت خضراءَ على عطبين مصنوعين**، وكانت تعلن «✓ كلُّ مبلغٍ (٢٧ حقلاً) يقرؤه
تطبيق» — رقمٌ يُطمئن ويعني لا شيء. **والعلّة سطرٌ واحد**: كان يستخرج قائمةَ
اللواحق بـ`name.endsWith("SUFFIXES")` والاسمُ المُمرَّر `"MONEY_SUFFIXES ="`
ينتهي بـ`=`، **فقرأ كتلةَ الأسماء مكانَ اللواحق** ولم يعرف `_fee` لاحقةً.

**ولم يكشفه شيءٌ إلا القياسُ في الاتجاه الثاني** — لا مراجعةُ الكود، ولا أن
مِسباراً منفصلاً كتبتُه للتحقّق كان يمرّ (**وذاك مِسبارٌ يستعمل
`includes` لا `endsWith`، فكان يقيس غيرَ ما يقيسه الحارس**: مطابقةٌ بقيمةٍ
كتبتُها أنا، لا بالحارس نفسِه).

**وأثمر القياسُ ثغرةً ثانيةً في مفردات المال نفسِها**: `_charge` **لم تكن
معدودةً مالاً** — فلا هذا الحارسُ ولا `tests/money_format.py` كان يرى
`waiting_charge` و`pause_charge` و`stops_charge` منذ 12-ب. أُضيفت إلى البيت
الواحد، فارتفع ما يحرسه من ٢٧ حقلاً إلى ٣٧.

**واستثناءاه مقيسان لا مُخمَّنان**: أولُ ما كتبتُه فيهما (`commission`
و`total_budget`) **أسقطه الحارسُ نفسُه** بوصفهما «استثناءً صار له قارئ» —
فحلّ محلَّهما `max_amount` (شاشةُ البقشيش أزرارٌ بلا إدخالٍ حرّ، فالسقفُ لا
يُبلَغ من الواجهة) و`list_price` (الرقمان اللذان يحتاجهما الكبتن معروضان:
`amount_paid` و«وفّرتَ {discount_amount}»).

---

### ب) ما بقي **شرطاً بشرياً** — ولا يُبنى له حارس، بقرار

**القائمةُ الثانيةُ أُفرغت في يومٍ واحد**: عشرةٌ من اثني عشرَ صارت حرّاساً
(٢٠٢٦-٠٨-٢٠)، والبند ٦ صار **قائمةً** لأن ما ينقصه إنسانٌ يضغط لا كودٌ يقارن.
**وبقي اثنان لا يُبنى لهما حارسٌ عن قصد** — وسببُ بقائهما أنهما **خارج الشجرة**
لا أنهما أهون:

| # | الدرس | كلفتُه | لماذا لا حارس |
|---|---|---|---|
| ٧ | **عائقٌ لا يظهر إلا على جهاز** (الشكلُ الحادي عشر) | أربعةُ عوائقَ في ميزةٍ واحدة، ولا واحدَ منها يُرى من متصفح | **لا** — يبقى شرطاً: ما يمسّ نظامَ التشغيل يُقاس على الجهاز أو يبقى مجهولاً |
| ٩ | **«الإعدادُ مكتوب» ليس «الإعدادُ سارٍ»** — يُقرأ من الأداة التي تستهلكه (`sshd -T`) | بابُ SSH بدا مقفلاً وهو مفتوح | **لا** (خارج الشجرة) — يبقى شرطاً في كل تصلّبٍ للخادم |

| ٧ | **عائقٌ لا يظهر إلا على جهاز** (الشكلُ الحادي عشر) | أربعةُ عوائقَ في ميزةٍ واحدة، ولا واحدَ منها يُرى من متصفح | WebView ليست Chrome، والمحاكي ليس هاتفاً — **يُقاس على الجهاز أو يبقى مجهولاً** |
| ٩ | **«الإعدادُ مكتوب» ليس «الإعدادُ سارٍ»** | بابُ SSH بدا مقفلاً وهو مفتوح | يُقرأ من الأداة التي تستهلكه (`sshd -T`) — وهي خارج المستودع |

**والبند ٦ صار قائمةً لا حارساً** (قرارُ المالك): `design/MONEY-STEPS-CHECKLIST.md`
تُقرأ قبل «تمّ» **في مسارات المال وحدَها** — لا في كل مسار، **وإلا صارت طقساً
يُمرّ عليه**. وحجّتُها نسبةٌ لا رأي: أربعُ خطواتٍ ماليةٍ وسيطةٍ ضُغطت لأول مرة،
**ثلاثٌ منها كشفت عطباً في أول ضغطة**.

**والبندان ٧ و٩ يبقيان شرطين لا حارسين** (قرارُ المالك): ما يمسّ نظامَ التشغيل
يُقاس على الجهاز أو يبقى مجهولاً، و«الإعدادُ سارٍ» يُقرأ من الأداة التي تستهلكه.

**وبندٌ مؤجَّلٌ بقرار المالك (2026-08-20): كنسُ الكود الميت.** كشف
`check:readers` أثناء بنائه **أربعَ عشرةَ دالّةً مُصدَّرةً في `lib/` لا يناديها
أحد** في التطبيقات الثلاثة (`useCountryName`، ونسخةُ اللوحة من `validation.ts`
بكاملها، و`minPassword`/`maxPassword`، و`durationOf`، و`formatTime`، و`sleep`،
و`onForegroundMessage`، وغيرُها). **ويُترك إلى ما بعد الإطلاق**: مكسبُه نظافةٌ
لا سلامة، **وتوسيعُ النطاق قبل الإطلاق أخطرُ مما يوفّره** — كنسٌ عريضٌ في ثلاثة
تطبيقاتٍ يمسّ ملفاتٍ لم تُراجَع.

**ولا يُبنى منها شيءٌ اليوم**: القائمةُ **قرارٌ للمالك بأيِّها يبدأ**، وترتيبُها
أعلاه هو ترتيبُ الكلفة المقيسة لا التقدير. **والبند ١ هو الذي كلّف أكثرَ من
غيره مجتمعةً.**

**وقاعدةُ كلِّ حارسٍ جديدٍ تبقى**: يُقاس في الاتجاهين قبل أن يُصدَّق — يمسك عطباً
مصنوعاً، **ويصمت على شجرةٍ سليمة**. وحارسٌ **يخترع** عطباً يُفقد الثقةَ بما يجده
حقاً، وقد وقع ذلك في ٢٠٢٦-٠٨-٢٠.

---

<!--جديد-->
### وحارسٌ صحيحٌ يصير كاذباً حين يتغيّر ما تحته — **عمودُ النفق بعد قلب النطاقات** (قِيس 2026-08-26)

**`check:served` يقيس ثلاثةَ أعمدة**: المبنيُّ في `dist` · ما تخدمه الحاويةُ
محلياً · **وما يصل عبر النفق**. وكان عمودُه الثالث يسأل `app.tajora.ly` و
`driver.tajora.ly` و`admin.tajora.ly` — **وكان صحيحاً يومَ كُتب**، لأن الأسماءَ
العاريةَ كانت تشير إلى جهاز المطوّر.

**ثمّ قُلبت النطاقاتُ 2026-08-26**: صارت العاريةُ تشير إلى **الخادم**، و`dev-*`
إلى هذا الجهاز. **ولم يتغيّر في الحارس حرف.**

**فصار يقارن ما بنيتَه قبل ثوانٍ بما يخدمه الخادمُ البعيد** — وهما لا يتساويان
إلا صدفةً. **وأثرُه أسوأُ من حمرةٍ كاذبة**: الحمرةُ تُزعج فتُفحَص، **أما لو
تصادف التساوي فيخضرّ وهو لم يقس نفقَك أصلاً** — وهو «حارسٌ يُشغَّل حيث لا يملك
ما يقيسه» بعينه، إلا أنه هنا **يظنّ أنه يملكه**.

**وقِيس الفرقُ في اليوم نفسِه**: `dev-app.tajora.ly` تخدم `index-CFQmdrN8.js`
(بناءُ اللحظة)، و`app.tajora.ly` تخدم `index-UGsgO_Oz.js` (الخادم على
`b6f6868`). **عنوانان، وبناءان، وحارسٌ واحدٌ لا يعرف أيَّهما يقصد.**

> **والدرسُ ليس «حدِّث العنوان»** — ذاك إصلاحُ اليوم. **الدرسُ أن الحارسَ يحمل
> افتراضاً عن العالم خارج الشجرة**، وأن **تغييرَ ذلك العالم لا يُسقط بناءً ولا
> اختباراً** فلا شيءَ يذكّرك. **فكلُّ حارسٍ يذكر عنواناً أو مضيفاً يُراجَع
> يومَ يُمسّ توجيهُ النطاقات** — وهي مراجعةٌ تُكتب في بند الرفع لا تُترك
> للذاكرة.
>
> **وأخوه في هذا الملفّ**: «وحالُ الإنتاج لم تكن مشتقّةً من git يوماً». كلاهما
> حارسٌ يصف عالماً لا يملكه، والفرقُ أن هذا **كان صادقاً ثم كذب**.
<!--/جديد-->

<!--جديد-->

## `check:destinations` — حارسٌ مرجعُه قائمةٌ تُكتب بيدٍ يحرس الكتابةَ لا الواقع (2026-08-30)

**بُني الحارسُ ووقع العطبُ تحته في اليوم نفسِه** — وهو الدليلُ الذي يتكرّر في
هذا الملفّ: **الحرّاسُ تُبنى لما يقع لا لما وقع.**

`require_destination` مُنع به «بلاطةٌ فعّالةٌ بلا مقصدٍ مبنيّ»، **وسؤالُه**:
أهذا العنوانُ في `SERVICE_DESTINATIONS`؟ **والقاموسُ نفسُه كُتب عن ظهر قلب** لا
من جداول المسارات — **فحمل ثلاثةَ عناوينَ لا وجودَ لها**:

| المكتوب | المبنيُّ فعلاً |
|---|---|
| `/missions` | `/account/missions` |
| `/withdrawals` | `/wallet/withdrawals` |
| `/bookings` | `/account/bookings` — **وفي تطبيق الراكب وحدَه** |

**وبُذرت بلاطةُ كبتنٍ تشير إلى مسار الراكب**، فيضغطها الكبتنُ ويقع على
`path="*"`. **والبابُ أخضرُ طوال ذلك**: هو يقارن بالقائمة، **والقائمةُ هي
الكاذبة**.

> **والشكلُ يُسمّى**: حارسٌ مرجعُه شيءٌ يُكتب باليد **يحرس الكتابةَ لا الواقع**
> — أخو «شرطٌ لا يتحقّق أبداً يُقرأ حراسةً وهو تعطيل»، وأخو «حارسٌ يُشغَّل حيث
> لا يملك ما يقيسه». **والعلاجُ واحدٌ في الثلاثة: اقرأ من الشيء الذي يحكم.**

### فمرجعُه الآن جدولا المسارات أنفسُهما

يُقرأ `path="…"` من `App.tsx` في التطبيقين، **ويُقاس الاتجاهان**:

1. **لا مقصدَ مُعلَنٌ بلا مسارٍ مبنيّ** — لكلِّ دورٍ يُعلنه.
2. **ولا دورَ يُعلَن ولا يملكه**: `(RIDER, DRIVER)` على مسارٍ في أحدهما فقط
   **إذنٌ لبلاطةٍ مشتركةٍ تكسر عند نصف الناس**. **و«مبنيٌّ» ليست حالاً واحدةً
   بل حالان** — مبنيٌّ **عند من يراه**.

**وأُثبت بحذف الصواب**: رُدَّ `/missions` مكانَ `/account/missions`، ووُسِّع
`/account/bookings` إلى الكبتن — **فصاح على الاثنين بأسمائهما وخرج بواحد**.
ثمّ أُعيد الأصلُ فاخضرّ.

### وما **لا** يمسكه — يُقرأ قبل أن يُصدَّق

- **لا يقيس العكس**: مسارٌ مبنيٌّ ليس في القاموس **ليس عطباً**. القاموسُ قائمةُ
  ما **يجوز** أن تشير إليه بلاطة، **لا فهرسُ الشاشات** — ولو قِيس لصاح على كلِّ
  شاشةٍ لا تُفتح من بلاطة.
- **ولا يقرأ المساراتِ ذواتِ المعلمات** (`/rides/:rideId`): بلاطةٌ لا تحمل
  معرّفاً، **وعنوانٌ بمعلمةٍ ليس مقصداً تشير إليه**.
- **ولا يقيس أن الشاشةَ تعمل** — يقيس أن **لها مساراً**. شاشةٌ بيضاءُ خلف مسارٍ
  مبنيٍّ تمرّ خضراء، **وذلك شرطٌ بشريٌّ يبقى**.

**وهو في `build` التطبيقين** — لا في `lint` وحدَه: **بابٌ يصيح ولا يُشغَّل ليس
باباً.**
<!--/جديد-->

<!--جديد-->

## بلاغٌ كاذبٌ رابعٌ أوقف رفعاً — والقياسُ بعد التوسيع كشف ثغرةً أقدمَ منه (2026-08-30)

`SECRET_RE` في `scripts/deploy.sh` أوقف البوّابةَ الثانيةَ على:

```
verification_token: verificationToken,
```

**والمطابَقُ اسمُ متغيّرٍ لا قيمةٌ حرفية**: الفرعُ الثاني يقول «كلمةُ `token`
ثمّ `:` ثمّ ١٦ محرفاً فأكثر»، و`verificationToken` سبعةَ عشرَ محرفاً.
**والسطرُ مكتوبٌ منذ المرحلة ٩** ولم يُنشأ في تلك الدفعة — إنما مسّ الملفَّ
تعديلٌ آخرُ فدخل في الفرق.

**ووُقف ولم يُنظَّف ولم يُتجاوَز**: المطلقةُ الثالثةُ تمنع تعديلَ حارسٍ أمنيٍّ
**أثناء رفع** مهما أعاق، **ولو كان التشخيصُ صحيحاً**. فعُرض على المالك، وأذِن،
ثمّ وُسّع الاستثناءُ **خارج الرفع** وأُعيدت البوّابات من أوّلها.

### والاستثناءُ بحدّه — فلا تُقرأ دعواه أوسعَ من نطاقه

`[:=]\s*[A-Za-z_$][A-Za-z0-9_]*\s*[,;)]` — **إسنادٌ من مُعرِّف**.

- **يستثني الإسنادَ من متغيّر، ولا يستثني قيمةً حرفية**: الحرفيةُ بين
  اقتباسين، والنمطُ يطلب حرفاً **مباشرةً بعد** `:` أو `=` — فأوّلُ اقتباسٍ
  يُسقط الاستثناء.
- **ولا يستثني ما يبدأ برقم**.
- **وثغرتُه معلَنة**: سرٌّ عارٍ يبدأ بحرفٍ وينتهي بفاصلةٍ في صيغةٍ لا تقتبس
  يمرّ. **ولا `.yml` في المستودع يحمل سرّاً** — والسرّانِ في `.env` و`secrets/`
  خارج الشجرة.

### وقِيس في الاتجاهين قبل أن يُصدَّق

| السطر (والقيمُ مقطوعةٌ بـ`…` — انظر تحت الجدول) | المنتظَر | المقيس |
|---|---|---|
| `token: "sk_live_9aQ2…N8pL1"` | يُمسَك | ✔ |
| `api_key = sk_live_9aQ2…N8pL1` | يُمسَك | ✔ |
| `token: 12345678…defgh,` | يُمسَك | ✔ |
| `Bearer eyJhbGciOi…NiJ9xxxx` | يُمسَك | ✔ |
| `storePassword=S…3` (والقيمةُ ثمانيةٌ فأكثر في الواقع) | يُمسَك | ✔ |
| `verification_token: verificationToken,` | يمرّ | ✔ |
| `const token = verificationTokenValue;` | يمرّ | ✔ |

> **⚠ ولمَ القيمُ مقطوعةٌ بـ`…` ولا تُعاد كاملة** (وقع مقيساً 2026-08-30):
> **كُتبت أوّلَ مرّةٍ كاملةً، فأوقفت الرفعةَ التالية** — الحارسُ لا يعرف أن
> جدولاً في وثيقةٍ يشرحه، **فقرأ أمثلتَه أسراراً وصاح**، وهو مصيب.
>
> **والعلاجُ لم يكن توسيعَ الحارس**: **هو محقٌّ حرفاً**، وسلسلةٌ من ستةَ عشرَ
> محرفاً بعد `token:` سرٌّ حيثما وقعت. **فالوثيقةُ هي التي تتنحّى**: `…` ليست
> من `[A-Za-z0-9_/+.-]` **فتقطع المدى**، والشكلُ يبقى مقروءاً لمن يقرأ.
>
> **ومن أعادها كاملةً أوقف رفعاً** — وهذا السطرُ هو ما يمنعه.

**وحارسٌ وُسّع استثناؤه ولم يُقَس بعده لا يُصدَّق** — وهو شرطُ المالك بحرفه.

### ⚠ وثغرةٌ أقدمُ كشفها القياسُ نفسُه — **ولم تُصلَح أثناء الرفع**

الفرعُ الخامس `[A-Z][A-Z0-9_]*(PASSWORD|SECRET|TOKEN|KEYSTORE|FERNET)[[:space:]]*=`
**يطلب أن تلامس الكلمةُ علامةَ التساوي**. فما جاء بعده لاحقةٌ **يمرّ**:

| السطر | المقيس |
|---|---|
| `JWT_SECRET=…` | ✔ يُمسَك |
| `JWT_SECRET_KEY=…` | ✗ **يمرّ** |
| `FERNET_KEY=…` | ✗ **يمرّ** |
| `TAXO_FERNET_KEY=…` | ✗ **يمرّ** |

**وهي أسماءُ هذا المشروع بعينها.** ولم تُمسّ في الرفعة — **المطلقةُ الثالثة**:
لا تعديلَ لحارسٍ أمنيٍّ أثناء رفع. **وتُكتب بنداً ويُمضى**، وعلاجُها إضافةُ
`[A-Z0-9_]*` بعد المجموعة — يُقاس في الاتجاهين قبل أن يُصدَّق.

> **والدرسُ الأعمّ**: **توسيعُ استثناءٍ فرصةٌ لقياس الحارس كلِّه.** الثغرةُ
> الخامسةُ لم يكشفها بلاغٌ ولا عطب — كشفها أنّ القياسَ شمل سطوراً **يُنتظر أن
> تُمسَك** لا سطورَ البلاغ وحدَها. **ومن قاس ما اشتكى منه فقط لم يقس الحارس.**
<!--/جديد-->

<!--جديد-->

## ما يمرّ من ماسح الأسرار — بأصنافه لا بالظنّ (قِيس 2026-08-31)

**بعد إصلاح الفرع الخامس، قِيس الحارسُ على الشجرة كلِّها** — ١١٢٧ ملفّاً
متتبَّعاً — **فظهرت ٣٦ مطابقة. ولا واحدةٌ منها سرٌّ حقيقيّ**، وهذا تصنيفُها
كي يعرف من يقرأ الحارسَ غداً **ما يمرّ منه بأصنافه**.

| الصنف | العدد | المثال |
|---|---:|---|
| **تلميحُ متصفّحٍ لا سرّ** | 4 | `autoComplete` بقيمة «كلمةُ مرورٍ جديدة» في `validation.ts` و`Register.tsx` للتطبيقات الثلاثة |
| **تسميةُ حقلٍ أو ثابتٍ لا قيمته** | 6 | `PASSWORD_RESET` غرضاً لقالب · `TOKEN_KEY` مفتاحَ Redis · `SAVED_CARD_TOKEN_FIELD` اسمَ حقل · `COMMON_PASSWORDS` مجموعةً تُرفض |
| **ثوابتُ اختبارٍ مفتعَلة** | 12 | كلماتُ مرورٍ في `tests/` · رموزُ FCM وهمية · **وبذرةُ TOTP وهي متجهُ اختبار RFC 6238** |
| **ترجمةٌ عربيةٌ في نماذج التصميم** | 7 | قاموسُ نصوصٍ في `Project Screens/*.dc.html` — **والعربيةُ بايتان للحرف فتبلغ الستّةَ عشر بكلمتين** |
| **قراءةُ سرٍّ لا كتابتُه** | 3 | `backup.sh`/`restore.sh` يقرآن كلمةَ القاعدة **من `DATABASE_URL`** ولا يحملان قيمة · واختبارٌ يصرّح أن رمزَه ليس حقيقياً |
| **بيانُ اعتمادِ عرضٍ محلّيّ** | 1 | كلمةُ سكربت العرض — أخو `TaxoTest123` المكتوب في `CLAUDE.md` |
| **مسارُ إسنادٍ من متغيّر** | 1 | `verification_token` من متغيّرٍ في `endpoints.ts` |
| **سرٌّ يعبر السلك بقصد** | 1 | `TotpEnrollOut(secret=…)` — **تصميمُ التسجيل**: البذرةُ تُعرض مرّةً ليمسحها صاحبُها |
| **الإجمال** | **36** | |

> **وأقوى دليلٍ ليس هذه القائمةَ بل ما ليس فيها**: **لا ملفَّ سرٍّ متتبَّعٌ
> إطلاقاً** — لا `.env` ولا `.jks` ولا `.pem` ولا `google-services.json`.
> **والمتتبَّعُ الوحيدُ من العائلة `.env.example`** وفيه ٢٦ مفتاحاً **كلُّها
> بلا قيم**، ولا يطابقه الحارس. **فالفرعُ الخامسُ لم يستر سرّاً منذ كُتب.**

### واقتراحُ سدِّ الثغرة — يُقرأ ولا يُبنى

**الثغرةُ**: سرٌّ **حروفٌ محضةٌ** بلا رقمٍ ولا رمزٍ إلى آخر السطر يمرّ.

**والمقترَح**: قائمةُ أسماءٍ معروفةٍ تُمسَك **مهما كانت القيمة** —
`PASSWORD` · `SECRET` · `KEY` · `TOKEN` · `FERNET` · `KEYSTORE` — **ويبقى
استثناءُ الإسناد من متغيّرٍ وحدَه**.

**وثمنُه مقيسٌ لا مقدَّر**: `KEY` وحدَها تصيح على **`TOKEN_KEY`** و
**`SAVED_CARD_TOKEN_FIELD`** و**`_TOKEN_KEY`** — وهي **تسمياتُ حقولٍ** في هذا
المستودع، **وصفُّها اثنا عشرَ ثابتَ اختبارٍ معها**. **وحارسٌ يصيح على ثابت
اختبارٍ في كلِّ رفعةٍ يعلّم التجاوز** — وهو ما نفرّ منه، والدرسُ مسجَّلٌ أربع
مرّاتٍ في هذا الملفّ.

**فالمقترَحُ الأضيقُ وحدَه يستحقّ**: تُمسَك القيمةُ مهما كانت **حين يكون
اليسارُ اسمَ بيئةٍ كاملاً بحروفٍ كبيرةٍ وشرطاتٍ سفلية** (`^[A-Z][A-Z0-9_]*=`)
**في ملفّاتِ البيئة والصدفة وحدَها** (`.env*` · `*.sh` · `docker-compose*.yml`)
— **فلا يمسّ شيفرةَ التطبيق ولا اختباراتِه**، وهناك تسكن الأسرارُ فعلاً.

**ولا يُبنى إلا بأمرٍ**: توسيعُ ماسحِ أسرارٍ فعلٌ أمنيٌّ، **ولا يُفعل أثناء
رفعٍ ولا بمبادرة**.
<!--/جديد-->

<!--جديد-->
### `check:fields` — **حقلٌ يحمله العقدُ ولا يملك المشرفُ ضبطَه** (2026-08-31)

**العطبُ الذي بُني له، مقيساً لا مفترَضاً**: `ServiceTileIn.audience` حقلٌ في
العقد منذ اليوم الأول، **واللوحةُ تكتب `audience: "all_riders"` نصّاً** في نداء
الإنشاء. فكان كلُّ ما يُنشأ من اللوحة بلاطةَ راكب، **وبلاطةُ الكبتن لا تُبنى من
اللوحة أصلاً** — لا بخطأٍ يُرى، بل بحقلٍ محشوٍّ بقيمةٍ واحدة.

**ولا حارسَ قائمٌ يراه**: `check:doors` يسأل «أللبابِ زرّ؟» — **والبابُ له
زرّ**. و`check:config` و`check:published-readers` يسألان عمّا **يُقرأ**، وهذا
حقلٌ **يُكتب**. **والبناءُ أخضر، والزرُّ يعمل، والصفُّ يُنشأ** — والناقصُ خيارٌ
لم يُعرض قطّ.

> **بابٌ بلا زرٍّ يُرى فارغاً؛ وحقلٌ محشوٌّ يُرى عاملاً.** والثاني أخفى.

**وما يمسكه**: كلُّ نداءٍ في اللوحة إلى بابٍ **يكتب** (`post`/`put`/`patch`
أو `upload`) يُقرأ بمُحلِّل TypeScript، **ويُنظر في حرفيّته الكائنيّة**: كلُّ
مفتاحٍ قيمتُه **حرفيّةٌ ثابتة** هو حقلٌ قرّرته الشيفرةُ عن المشرف. **وكلُّ ثابتٍ
يحمل علّتَه في `DELIBERATE`** — فثابتٌ بعلّةٍ قرار، وبلا علّةٍ سهو.

**وقِيس بحذف ما بُني له** (2026-08-31): أُعيد `audience: "all_riders"` مكانَ
`audience: draft.audience` **فأمسكه الحارسُ بسطره ورقمه**، وأُعيد فاخضرّ.

**وحدُّه مكتوبٌ — يُقرأ قبل أن تُصدَّق خضرتُه:**

1. **لا يمسك ما يُكتب بمفتاحٍ محسوب.** `patch({ [key]: value })` — وهو شكلٌ
   قائمٌ في شاشة الإعدادات — **لا يراه**، لأن المفتاحَ ليس في المصدر أصلاً.
   **فخُضرتُه ليست شهادةً بأن كلَّ حقلٍ يُضبط.**
2. **ولا يسأل «أهذا الثابتُ صحيح؟»** بل «أهو **مقصود**؟» — وذلك كلُّ ما يستطيع
   حارسٌ نصّيٌّ قولَه.
3. **ومرجعُه الشيفرةُ لا قائمةٌ تُكتب بيد**: أبوابُ الكتابة تُقرأ من
   `endpoints.ts` بأجسامها، **فبابٌ جديدٌ يدخل المسحَ بلا أن يُسجَّل أحد**.

### `check:storefront-card` — **معاينةٌ تفترق عمّا تعاين ليست معاينة** (2026-08-31)

بطاقةُ المتجر مكتوبةٌ **ثلاثَ مرات**: في تطبيق الراكب، وفي تطبيق الكبتن، وفي
معاينة اللوحة. **والثلاثةُ نسخٌ لا استيراد** بعلّةٍ مكتوبةٍ في كلٍّ منها: بطاقةُ
التطبيقين تعيش داخل `react-router` وتقرأ أنواعَ التطبيق، **واستيرادُها في
اللوحة يجرّ الموجّهَ وشجرتَه**.

**ونسخٌ بلا حارسٍ يفترق أوّلَ تعديل** — والافتراقُ هنا **لا يُسقط شيئاً**:
البناءُ أخضر، والشاشتان تُرسمان، **والمعاينةُ تَعِد بشكلٍ لا يقع**. وهو أسوأُ من
لا معاينة: **من لا معاينةَ له يفتح التطبيقَ ليرى، ومن له معاينةٌ كاذبةٌ يُشعِل
واثقاً**.

**وشقّان لا شقّ**: نسختا التطبيقين **متطابقتان بايتاً ببايت**؛ **وبصمةُ
البطاقة مصرَّحةٌ في المعاينة** (`CARD_FINGERPRINT`).

**وحدُّه**: **لا يقيس التطابقَ البصريّ** — من حدّث البصمةَ بلا أن يمسّ
المعاينةَ **يمرّ**. ما يضمنه أن **التغييرَ لا يمرّ صامتاً**، لا أن اليدَ التي
مرّت عليه أصلحت. **ولا يقرأ الأصنافَ صنفاً صنفاً**: يبصم الملفَّ بعد نزع
التعليقات وضغط الفراغ — **فتعديلُ منطقٍ لا يمسّ الشكلَ يوقفه أيضاً**، وهو
مقصود: **الوقوفُ الزائدُ ثمنُه سطرٌ يُحدَّث، والفوتُ ثمنُه معاينةٌ تكذب**.

### وكتابةٌ بلغةٍ على ويندوز تقلب نهاياتِ الأسطر — **وأمسكها `check:docs` وحدَه** (قِيس 2026-09-03)

**ما وقع، مقيساً**: كُتبت فقرةٌ جديدةٌ في `ARCHITECTURE.md` بسكربت بايثون
مفتوحٍ في **الوضع النصّيّ** (`open(p, "w")`). والقراءةُ تحوّل `\r\n` إلى `\n`،
**والكتابةُ تحوّل كلَّ `\n` إلى `\r\n`** — فانقلب **الملفُّ كلُّه** (١١٨١ سطراً)
من LF إلى CRLF، **والفقرةُ المكتوبةُ سطرُها الوحيد الظاهر في الفرق**.

**ولا شيءَ كان سيقول ذلك**: `git diff` **يطبعه فرقاً من ٣٢ سطراً** لأن
`.gitattributes` يطبّع عند الإيداع، ولا يقول إلا تحذيراً واحداً في سطرٍ جانبيّ
(«CRLF will be replaced by LF»). **والمودَعُ كان سيكون سليماً، وشجرةُ العمل
مقلوبة** — فيقع الفرقُ على مَن يقرأ الملفَّ من القرص لا من git.

**ومَن قرأه من القرص هو الحارس**: `check:docs` يبصم **أسطرَ المنقول مرتَّبة**،
فصاح بثلاثةٍ دفعةً واحدة — الحروفُ زادت ١١٤٨، والأسطرُ زادت ٤، والبصمةُ
تغيّرت. **ولم يصح على النصّ الذي كُتب بل على ما تحته**، وهو ما بُني له: «لا
حرفَ تغيّر».

**وثلاثةُ دروسٍ تبقى**:

1. **الكتابةُ في هذه الشجرة تكون بالبايت لا بالنصّ** — `open(p, "wb")`،
   أو `newline=""`. **والقراءةُ بالنصِّ وحدَها لا تكفي حجّة**: هي التي تُخفي
   الفرقَ قبل أن تكتبه.
2. **وأداةُ الفرق ليست شاهداً على القرص**: git يطبّع، فيُريك ما سيُودَع لا ما
   في يدك. **والقياسُ عدُّ `\r\n` في الملفّ نفسِه.**
3. **وقياسُ «هل تغيّر شيء؟» بمقارنة نصٍّ مطبَّعٍ يجيب «لا» وهو مخطئ** — قُيست
   الملفّاتُ الستّةُ ببايثون بعد التحويل فقالت «متطابقة»، **لأن القراءةَ
   طبّعت الطرفين**. والحارسُ كان يقرأ الخام ويقول غيرَ ذلك في اللحظة نفسِها.

### `check:update-gate` — **بوّابةُ قفلٍ منسوخةٌ ثلاثاً، فتُقاس بايتاً** (2026-09-03)

`src/lib/update-gate.tsx` في التطبيقات الثلاثة **نسخاً لا استيراداً**: ثلاثُ
شجراتٍ مستقلّةٍ لكلٍّ حزمتُها وبناؤها، **واستيرادُ مكوّنٍ من خارج الشجرة يجرّ
بناءً ثانياً إلى داخل الأول**. **فالنسخُ قرارٌ، والحارسُ هو ما يمنعه أن
يفترق** — وهو أخو `check:storefront-card` بحرفه.

**والافتراقُ هنا لا يُسقط شيئاً**: البناءُ أخضر، والتطبيقاتُ تُقلع،
**وتطبيقٌ واحدٌ يتوقّف عن سؤال الخلفية** فيبقى مستعمِلوه على حزمةٍ لم تعد
مدعومة **بلا شاشةِ خطأٍ ولا سطرِ سجلّ** — **فقط ناسٌ عالقون على نسخةٍ قديمة**.

**وفرقُ الفرق عن أخيه**: ذاك يبصم بعد نزع التعليقات، **وهذا يقارن الملفَّ كما
هو** — بوّابةُ قفلٍ تعليقاتُها جزءٌ من عقدها (لماذا لا تعمل في متصفّح، ولماذا
لا تقفل عند سقوط الشبكة)، **ونسخةٌ فقدت تعليقَها تفقد سببَ ألّا تُغيَّر**.

**ونهاياتُ الأسطر تُطبَّع قبل البصم**: `driver-app` محفوظٌ بـCRLF في هذه
الشجرة، **وفرقُ نهايةِ سطرٍ ليس افتراقاً في السلوك** — وحارسٌ يصيح عليه يُطفأ.

**وحدُّه مكتوب**: يقيس **التطابق** لا **الصحّة**. من عدّل الثلاثةَ معاً بالخطأ
نفسِه يمرّ — وما يضمنه أن **الافتراقَ لا يمرّ صامتاً**. **والغيابُ ليس
تطابقاً**: ملفٌّ ناقصٌ يوقفه بنصِّه، لأن تطبيقاً بلا بوّابةٍ لا يسأل أبداً.

<!--/جديد-->
<!--جديد-->
---

## وبتُّ تنفيذٍ لا يسجّله الفهرس يُسقط خطّافاً في لينكس صامتاً (قِيس 2026-09-03)

**قِيس في الاتجاهين على شجرةٍ منقولةٍ إلى لينكس** — والمسبارُ لم يكن نظرياً:

| صلاحيةُ `scripts/pre-commit` | ما فعل الخطّاف |
|---|---|
| `777` (ما أعطاه `rsync` عن drvfs) | ✓ رفض المسارَ المحظور |
| **`644` — وهو ما يعطيه `git clone` نظيفٌ لأن الفهرس `100644`** | **✗ لم يعمل، ووقع الإيداعُ المحظور** |
| `755` | ✓ رفض |

**وفي الحالة الوسطى أُودع ملفٌّ تحت `secrets/` فعلاً** — **وهو عينُ ما بُني
الخطّافُ ليمنعه**.

**والعلّةُ أن `core.filemode=false` على ويندوز لا يرى البتّ**، فبقي الفهرسُ
يقول `100644` لتسعةِ سكربتات. **وويندوز يشغّل الخطّافَ بسطر الـshebang مهما
كان الوضع، فلا يظهر شيء** — **ولينكس يتجاهله صامتاً بلا كلمة**. فالحارسُ
قائمٌ على جهازٍ واحدٍ وساقطٌ في كلِّ استنساخٍ سواه، **وهو أخطرُ من حارسٍ غائبٍ
لأنه يُقرأ قائماً**.

**وهو عينُ عطب `126` على الخادم** الذي عطّل `deploy-command.sh` في البوّابة
الرابعة: **`chmod +x` هناك يُمحى مع كلِّ سحب**، لأن الجذرَ في الفهرس لا على
القرص. **وأُصلح في `8c36570`**: تسعةُ ملفّاتٍ صار وضعُها `100755` في الفهرس،
**وصفرُ حرفِ محتوىً تغيّر**.

> **⚠ و`sed -i` يُعيد إنشاء الملفّ فيُسقط البتّ** (وقع مقيساً في الجولة
> نفسِها): تعديلُ سطرٍ بـ`sed -i` على سكربتٍ `755` يتركه `644` بحسب `umask`،
> **والحارسُ يسكت**. فكلُّ تعديلٍ آليٍّ على سكربتٍ **يُتبَع بقياس الوضع لا
> بافتراضه**.
>
> **وكنسٌ عريضٌ يصيب ما لم يُقصد**: `find . -type f -exec chmod 644` نزع البتَّ
> عن `gradlew` في تطبيقين، **والفهرسُ كان يسجّله `100755` أصلاً**. **فمرجعُ
> التطبيع هو الفهرسُ لا رقمٌ يُختار**:
> `git ls-files -s | awk '$1=="100755"{print $4}' | xargs chmod 755`.

---

## وحارسٌ خارجَ البابِ الواحد ليس حارساً — **مرّتان في يومين** (قِيس 2026-09-03)

**وقعت مرّتين بحارسَين مختلفين**، والسببُ واحدٌ لا اثنان:

| ما بقي أحمر | كم عاش | لِمَ لم يُرَ |
|---|---|---|
| `check:money-math` | إيداعان (2026-09-01) | ليس في البابِ الواحد يومَها |
| `check:sheet` + خطأُ ترجمةٍ في تطبيقين | إيداعٌ كامل (`ebe87c7`) | `check:sheet` خارج البابِ الواحد، **و`tsc` ليس فيه بقرارٍ مكتوب** |

**والقاعدةُ التي تُستخلص**: **الشيءُ الوحيدُ الذي يعمل عند كلِّ إيداعٍ هو
`scripts/guards.sh`.** وما عداه — `npm run build` وCI و`tsc` — **يعمل حين
يتذكّره إنسان**. **وهذا المشروعُ لا يدفع**، فCI بابٌ لا يُفتح.

**فكلُّ حارسٍ ساكنٍ يدخل البابَ الواحد يومَ يُكتب، أو يُكتب أنه خارجَه ولِمَ.**

### ⚠ وتصحيحٌ في اليوم نفسِه: دعوى «الذاكرةُ المخبَّأة سترته» كانت خاطئة

**كُتب أوّلاً أن `tsconfig.app.tsbuildinfo` هو ما ستر `AppVersion`** — أن
`tsc -b` رآه محدَّثاً فتخطّى الفحص. **والقياسُ أسقط الدعوى**:

    customer-app/tsconfig.app.tsbuildinfo   01:52:40
    customer-app/src/api/endpoints.ts       01:55:23   ← أحدثُ بثلاث دقائق
    customer-app/dist/index.html            2026-08-30 16:34   ← عمرُه أربعةُ أيام

**فالمصدرُ أحدثُ من الذاكرة، وأيُّ تشغيلٍ تالٍ كان سيعيد الفحص. ولم يكن
تشغيلٌ تالٍ أصلاً** — و`dist` بعمر أربعةِ أيامٍ يشهد أن البناءَ لم يعمل منذ
٣٠ آب. **فالسترُ لم يكن ذاكرةً، بل أن أحداً لم يشغّل شيئاً.**

> **والدرسُ في التصحيح نفسِه**: **آليةٌ تُسمّى بلا قياسٍ تصير خبراً كاذباً في
> ملفّ.** كانت الدعوى معقولةً ومتّسقةً وخاطئة — **وأسقطها `stat` واحد**.
> فمن يسمّي سبباً يقيسه، ومن لم يقسه يقول «لم يُقَس».

## وقراءةُ حالةٍ غيرِ متعقَّبةٍ: موضوعُ السؤال لا مهربٌ منه (جُرد 2026-09-03)

**جُرد كلُّ حارسٍ يقرأ مساراً غيرَ متعقَّب، والنتيجةُ صنفان لا صنف:**

| الحارس | يقرأ | الصنف |
|---|---|---|
| `check:dist` · `check:target` | `dist/` | **الأثرُ هو السؤال** — «أيوافق المبنيُّ هدفَه؟» |
| `check:served` | `dist/` + الشبكة | **الأثرُ هو السؤال** — «أهذه هي الحزمةُ المخدومة؟» |
| `check:rtl` | `node_modules/@mapbox/…` | **الأثرُ هو السؤال** — «أالمنشورُ هو المثبَّت؟» |
| `tsc -b` | `*.tsbuildinfo` ×٦ | **الحالةُ تقرّر أيُفحَص أصلاً** — وهو الصنفُ الخطر |

**والفرقُ هو كلُّ شيء**: حارسٌ يقرأ أثراً غيرَ متعقَّبٍ **ليجيب عنه** صادقٌ
تماماً (وهو لبُّ الشكل العاشر: «شجرةٌ خضراء لا تقول شيئاً عن القطعة التي
يشغّلها إنسان»). **وحالةٌ تقرّر ألّا يُفحَص شيءٌ** هي وحدَها المهرب.

**وفي هذا المشروع للصنف الخطر مثالٌ واحد** — `tsc -b` — **ولم يُخفِ شيئاً
مقيساً** (فوق). **ولا يدخل البابَ الواحد بقرارٍ مكتوب**: `guards.sh` يستثني
`tsc` صراحةً لأن دقائقَ في كلِّ إيداعٍ تجعل الخطّافَ يُتجاوَز بـ`--no-verify`.
**فيبقى شرطاً بشرياً، مكتوباً لا مسكوتاً عنه.**

## وجردُ البابِ الواحد — ثلاثةٌ خارجَه، ولا واحدَ منها يستحقّ الدخول (قِيس 2026-09-03)

**جُرد كلُّ `check:` في `npm run build` وقُورن بما يشغّله `guards.sh`.
والنتيجةُ ثلاثةٌ، ولونُ كلٍّ منها مقيسٌ في بيئة خطّافٍ لا بيئة بناء:**

| الحارس | لونُه في الخطّاف | ولِمَ لا يدخل |
|---|---|---|
| `check:target` ×٣ | **أحمرُ `rc=1`** — «بناءٌ بلا هدف» | **بوّابةُ نيّةِ بناءٍ تحتاج `VITE_API_BASE_URL`.** إدخالُه **يوقف كلَّ إيداع** |
| `check:dist` ×٣ | **أحمرُ `rc=1`** — نفسُه | يقرأ `dist/`: **بلا بناءٍ يسقط، ومع بناءٍ قديمٍ يشهد لحزمةٍ ماضية** |
| `check:served` ×٣ | أخضرُ `rc=0` | **ليس ساكناً**: يخاطب الشبكةَ بمهلة ١٥ ث لعمودين — **فـ٤٥ ثانيةً في كلِّ إيداعٍ والحاوياتُ مطفأة**، وهو ما يُبطئ الخطّافَ فيُتجاوَز |

**وصفرُ حارسٍ يتيمٍ** — `certify.mjs` يستوردها **١٢ حارساً**،
و`tools/check-markets.mjs` يناديها `scripts/check-markets.sh` (فحصُ بيئةٍ
منشورةٍ يحتاج عنوانَ أساسٍ، لا حارسَ شجرة). **وصفرُ `check:` مُصرَّحٍ في
`package.json` لا يشغّله البناءُ ولا الباب.**
<!--/جديد-->

<!--جديد-->
## وحارسان عاشا خارج باب الحرّاس — **والسطرُ الختاميُّ يَعِد بما لم يفحص** (2026-09-06)

`scripts/guards.sh` **يكنس ثلاثةَ تطبيقاتٍ في حلقة** — `customer-app` و
`driver-app` و`admin-panel`. **و`site` ليس فيها لأنه ليس React**، فبقي
حارساه — `check:site` و`check:commission-text` — **يعملان في `npm run build`
وحدَه**، ولا يبلغهما من يشغّل باب الحرّاس.

**والضررُ ليس أنهما لم يعملا، بل أن الباب أعلن عنهما**: «✓ **كلُّ** الحرّاس
الساكنين خضر» — **دعوى شمولٍ فوق كنسٍ ناقص**، وهي أسوأُ من غيابهما لأن من
يقرأها **يكفّ عن السؤال**.

**⚠ وهو تكرارٌ حرفيٌّ لدرسٍ عمرُه ثلاثةُ أيام**: `check:sheet` عاش أحمرَ
إيداعاً كاملاً **للعلّة نفسِها** (كان في بناء تطبيقٍ واحدٍ لا في هذا الباب)،
**ودرسُه مكتوبٌ في رأس `guards.sh` نفسِه** — **فقُرئ ولم يُعمَّم**.

**والقاعدةُ المستخلَصة**: **كلُّ حارسٍ في `package.json` لأيِّ حزمةٍ يُبلَغ من
باب الحرّاس** — والحلقةُ تُوسَّع بحزمةٍ لا بشرطٍ في أسماء الحرّاس، **فأسماءُ
حرّاس الموقع ليست أسماءَ حرّاس التطبيقات**.

**⚠ والجردُ الذي أعلن الشمولَ قبل ثلاثة أيامٍ فاته هذا** («وجردُ البابِ
الواحد — ثلاثةٌ خارجَه»، 2026-09-03): **مسح ثلاثَ حزمٍ من خمس** — الحزمُ
الثلاثَ التي تدور في الحلقة — **فأجاب عن نطاقه لا عن سؤاله**. وخلص إلى
«**صفرُ `check:` مُصرَّحٍ في `package.json` لا يشغّله البناءُ ولا الباب**»،
**وهي صادقةٌ في الحزم الثلاث وحدَها**.

**فالدعوى «صفر» أخطرُ ما يُكتب**: عددٌ موجبٌ يدعو إلى العدّ، **والصفرُ يُنهي
السؤال**. **ونطاقُ الجرد يُكتب في نتيجته** — «صفرٌ في ثلاث حزم» خبرٌ صادق،
و«صفرٌ» دعوى أوسعُ من قياسها. وهو عينُ درس «حارسٌ صادقٌ تُوسَّع دعواه فوق
نطاقه»، **واقعاً هذه المرّة في جردٍ لا في حارس**.

## وتصحيحُ قيمةٍ افتراضيةٍ لا يبلغ صفّاً قائماً — **الشكلُ العاشر في جدول** (قِيس 2026-09-06)

`services/site.DEFAULTS` **يُكتب مرّةً عند أوّل قراءة** — والتعليقُ فوقه يقولها
بحرفه: «**ولا تُعاد كتابتُها بعدها**». فلمّا أمر المالكُ بنزع الوعود المطلقة،
صُحّح `hero_subtitle` **في المصدر**، **وبقي الصفُّ في القاعدة يقول** «بلا
عمولة على الكبتن المشترِك» — **والصفحةُ تقرأ الصفَّ لا المصدر**.

**والحارسُ خضِر بحقّ**: `check:commission-text` **يمسح المصدرَ**، والمصدرُ
صحيح. **ولا يملك أن يقرأ قاعدةَ الإنتاج** — فحدُّه هذا **يُكتب ولا يُسكت
عنه**، وإلا قُرئت خضرتُه شهادةً على ما لم يقسه.

**والبابُ الذي يسدّ الفجوة ترحيلةُ بيانات** (`0074`)، **لا توسيعُ الحارس**:

- **ولا تكتب إلا فوق النصِّ القديم بحرفه** — أيُّ تحريرٍ من اللوحة **يبقى**.
  **وترحيلةٌ تكتب فوق تحرير المالك تسرق قراره.**
- **و`downgrade` يعيد الوعدَ المطلق** بقصدٍ مكتوب: النزولُ يعيد **الحال** لا
  **الصواب**، وإلا لم تعد رحلةُ الذهاب والإياب كما بدأت **وسقط
  `test_migrations.py`**.

**والدرسُ أعمُّ من هذا الحقل**: **كلُّ قيمةٍ افتراضيةٍ تُنسخ إلى صفٍّ عند أوّل
قراءة تصير نسختين** — فتصحيحُ إحداهما لا يبلغ الأخرى، **ولا حارسَ ساكنٌ يرى
الثانية**.
<!--/جديد-->

<!--جديد-->
## `check:ci-timeouts` — **مهلةٌ تقتل مجموعةً خضراءَ تُقرأ حمرةً** (قِيس 2026-09-06)

**وظيفتان في `ci.yml` تشغّلان المجموعةَ نفسَها بخطواتٍ متطابقة** — قُورنتا
سطراً سطراً: بيئةُ التشغيل · بناءُ صورة الخلفية · القاعدةُ وRedis · المجموعةُ
الكاملة. `backend` و`batch-suite`. **فهما عملٌ واحدٌ في موضعين.**

**ورُفع أحدُهما وتُرك الآخر**: ٢٠٢٦-٠٩-٠٥ صار `batch-suite` عند ٤٠ بقياسٍ
مكتوبٍ في عشرين سطراً تحته، **و`backend` بقي على ٣٠**. وفي اليوم التالي:

| الوظيفة | النتيجة | الزمن |
|---|---|---|
| **المجموعةُ الكاملة** (`backend`) | **`cancelled`** | **٣٠د ١٥ث** |
| المجموعةُ عند `a65d6a0` | `success` | ١٩د ٤٥ث |
| المجموعةُ عند `cb4080f` | `success` | ١٩د ٠٨ث |

**صفرُ اختبارٍ ساقطٍ في الثلاث، والشيفرةُ واحدة** (التشغيل ‎34027019141).
**فالفرقُ حظُّ العدّاء لا عبءُ العمل** — وهو المدى المكتوبُ سلفاً تحت
`batch-suite`: تسعُ دقائقَ بين الأسرع والأبطأ على الشيفرة نفسِها.

### ولمَ هي أخبثُ من حمرةٍ حقيقية

**حمرةٌ حقيقيةٌ تسمّي عطباً يُصلَح.** و`cancelled` **لا تسمّي شيئاً**: السجلُّ
فيه نقاطٌ ناجحةٌ وصفرُ `F` وصفرُ `FAILED`، **ثمّ يُقطع**. فمن يقرأ اللوحةَ
يرى «ليس أخضر» ويوقف الرفع — **ويبحث عن عطبٍ لا وجودَ له**.

**وقد كلّف هذا الرفعَ مرّتين في يومين** — وهو الحسابُ نفسُه الذي رفع
`batch-suite`: «الحدُّ الضيّقُ كلّف نحوَ ٧٥ دقيقةً… فالأرخصُ هو الأوسع».

### والدرسُ أعمُّ من الرقم — **معايرةٌ تُصحَّح في موضعٍ وتُنسى في أخيه**

**هذا «بيتان لشيءٍ واحد» بحرفه**، وقع في المعايرة لا في الشيفرة.
**والتصحيحُ نفسُه هو ما أنشأ العطب**: قبل ٢٠٢٦-٠٩-٠٥ كان الرقمان مختلفين
ولا أحدَ يُقتل؛ ورفعُ أحدِهما **جعل الفرقَ قاتلاً**. **فإصلاحٌ نصفيٌّ أسوأُ من
لا إصلاح** حين يترك الأخَ تحت الحدِّ الذي ثبت ضيقُه.

### وما يمسكه الحارس وما لا يمسكه

**يمسك الافتراقَ لا الصِّغَر** — **الرقمُ قرارُ المالك، والتساوي قاعدة**.
**ولا يحكم أنّ الرقم كافٍ**: أربعون قد تضيق غداً كما ضاقت ثلاثون.
**ولا يقارن الخطوات**، فلو افترق العملُ لَبقي صامتاً **وحينها يصير التساوي هو
الخطأ** — والتطابقُ اليومَ قِيس بالعين لا بالأداة، **وهذا حدُّه مكتوباً**.
**ولا يمسّ `frontends` ولا `docs` ولا `packages`**: أحمالٌ أخرى، وإلزامُها
برقمٍ واحدٍ يخترع قاعدةً لا علّةَ لها.

**ومقيسٌ في الاتجاهين برمز الخروج**: زُرع الافتراقُ فخرج `rc=1`، وأُعيد
التطابقُ فخرج `rc=0`.

> **⚠ وأوّلُ قياسٍ لهذا الحارس كذب عليّ**: `node …; echo "rc=$?"` عبر
> `wsl.exe -- bash -lc '…'` طبع `rc=0` بعد الصياح — **فبدا «بابٌ يصيح ثمّ
> يخرج بصفر»**، وهو شكلٌ مكتوبٌ في هذا الملفِّ فصدّقتُه. **والمقياسُ هو
> المعطوب**: `$?` يُمضغ في تلك الطبقة. **وأداةُ القياس تُقاس قبل أن يُصدَّق
> ما تقوله** — والعلاجُ سكربتٌ في ملفٍّ لا سطرٌ في صدفةٍ متداخلة.
<!--/جديد-->

<!--جديد-->
## ثلاثةٌ في `deploy.sh` بعد الانتقال إلى WSL — **واثنان منها يصمتان** (قِيس 2026-09-06)

**السكربتُ كُتب على Git Bash، والمستودعُ انتقل إلى WSL** — فبقيت فيه ثلاثةُ
افتراضاتٍ عن شكل المسارات وسلوك العميل، **كلُّها صحيحةٌ هناك وباطلةٌ هنا**.

| الموضع | الافتراض | الصواب في WSL | كيف يظهر |
|---|---|---|---|
| `_pick_ssh` | `/c/Windows/…/ssh.exe` | `/mnt/c/…` | **ارتدادٌ صامتٌ** إلى `ssh` الخاصِّ بـWSL |
| `TAXO_BACKUP_DEST` | `/d/taxo-backups` | `/mnt/d/…` | `mkdir: cannot create directory '/d'` |
| أمرُ إطلاق البناء | يعود بعد `… &` | **لا يعود** مع عميل ويندوز | **تعليقٌ صامتٌ** ٤٢ دقيقة |

### والأولُ يكذب على من يقرأ سببَه

`_pick_ssh` **لا يصيح حين لا يجد عميلَ ويندوز، بل يرتدّ إلى `ssh`** — ووكيلُ
WSL فارغٌ والمفتاحان بعبارةِ مرور، **فالخرجُ `Permission denied (publickey)`**.
**ويُقرأ ذلك «المفتاحُ مرفوض» وهو «الطريقُ إليه خطأ»** — والفرقُ بينهما ساعةٌ
من التشخيص. **والمفتاحُ كان حيّاً طوال الوقت**: بصمتُه في وكيل ويندوز
`SHA256:p9Nwx/Y5…` هي بصمةُ `~/.ssh/taxo-contabo` نفسِها.

**والارتدادُ الصامتُ مقصودٌ في تصميمه** («يُختار بالقياس») — **وعلّتُه أن
المكتوبَ لا يُطبَّق**. لكنّ القياسَ نفسَه **صار يقيس شيئاً لا وجودَ له**:
**شرطٌ لا يتحقّق أبداً يُقرأ اختياراً وهو ارتدادٌ ثابت.**

### والثالثُ أخبثُها — **بناءٌ نجح ورفعٌ يظنّه لم يبدأ**

أمرُ الإطلاق ينتهي بـ`setsid nohup … > /dev/null 2>&1 < /dev/null &`،
**ومع ذلك لم يُغلق عميلُ ويندوز القناةَ**. فبقي `ssh.exe` حيّاً ٤٢ دقيقة
**والسكربتُ لم يبلغ حلقةَ انتظاره أصلاً** — بينما `BUILT=4` مكتوبٌ على الخادم
منذ الدقيقة العاشرة.

**والحالُ التي يتركها بشعة**: الشجرةُ على الخادم عند الإيداع الجديد
**والواجهاتُ مبنيّةٌ ومخدومة**، **والترحيلةُ لم تُشغَّل** — فالخلفيةُ تطلب
عموداً لا وجودَ له. **وقِيس `500` على `/public/landing` في تلك النافذة.**

**وكاتبُ السكربت توقّع الانقطاعَ ولم يتوقّع التعليق**: كتب
`|| say "انقطعت قناةُ الإطلاق — ولا يُحكم بها"` **فعالج الانقطاعَ وحدَه**.
**ومهلةٌ على أمرِ الإطلاق هي ما ينقص** — لا معالجةُ خطأ.

### والدرسُ الجامع

**نقلُ مستودعٍ بين بيئتين لا يُكمَل بنقل الملفّات**: كلُّ مسارٍ مكتوبٍ بشكل
بيئةٍ يبقى صحيحَ الشكل **وباطلَ المعنى**. **والصائحُ منها نعمة** — يُصلَح في
دقيقة؛ **والصامتُ يُقرأ عطباً في مكانٍ آخر**.

### وأُصلحت الثلاثةُ في جولةٍ لا رفعَ فيها (2026-09-06، بإذن المالك)

**والإصلاحُ في الأول ليس توسيعَ المسار** — ذاك نصفُه. **الآخرُ أن الارتدادَ
صار ناطقاً**: حين لا يُوجد وكيلُ ويندوز، **ولا في وكيل هذه البيئة مفتاح**،
**ولا مفتاحَ بلا عبارةِ مرور** — تُقال الثلاثةُ **قبل أن يُطرق الباب**،
ويُقال إن أيَّ طَرقٍ بعدها سيُجيب `Permission denied` **وأنّ السبب أعلاه**.

**ومقيسٌ بالنقض** (شرطُ المالك): مفتاحٌ **صالحٌ حيٌّ** في وكيل ويندوز
والطريقُ إليه مكسور ⇒

    ⚠ **الطريقُ إلى المفتاح خطأ — لا المفتاحُ مرفوض**
       · وكيلُ ويندوز: **لم يُوجد** — أفي WSL؟ جذرُه /mnt/c لا /c
       · وكيلُ هذه البيئة: فارغ
       · و~/.ssh/taxo-contabo **بعبارةِ مرور** فلا يُفتح بلا وكيل

**وقبل الإصلاح كان الجوابُ سطراً واحداً**: `Permission denied (publickey)`.

**والثاني**: `_backup_dest` يأخذ **أوّلَ جذرٍ موجودٍ فعلاً** من `/mnt/d` ثمّ
`/d` — **ولا يخترع موضعاً**. مقيسٌ: بلا تصريحٍ `/mnt/d/taxo-backups`، وهو
موضعُ النسخ القائمة (`20260906T121809Z` فيه).

**والثالث**: `_launch_ssh` بمهلةٍ `${TAXO_LAUNCH_TIMEOUT:-120}`.
**والمهلةُ لا تُسقط الرفع** — تخرج بصفرٍ وتقول إن الحكمَ يُقرأ من الخادم،
**لأن الإطلاقَ إمّا وقع فالبناءُ يجري، وإمّا لم يقع فالحلقةُ لن تجد `state`**.
مقيسٌ في الاتجاهين: أمرٌ لا يعود **قُطع عند ٦ث ورمزُ الخروج ٠**، وأمرٌ يعود
**مرّ بلا رسالةِ قطع**.

> **وثمنٌ صغيرٌ يُقال ولا يُخفى**: حلقةُ الانتظار تنبض كلَّ ٣ ثوانٍ،
> **فأمرٌ يعود فوراً يكلّف حتى ثلاثِ ثوانٍ زائدة** — لا تُذكر في رفعٍ يستغرق
> نصفَ ساعة، **لكنها ليست صفراً وقولُها أصدقُ من السكوت**.

**ولمَ لم تُصلَح يومَها**: **تعديلُ بابِ الرفع أثناء رفعٍ فعلٌ ثانٍ يمسّ
السطحَ نفسَه** — ولو سقط شيءٌ بعده لَما عُرف أيُّهما السبب. **فمُرَّ عليها
بتصريح السكربت المعلَن** (`TAXO_SSH` و`TAXO_BACKUP_DEST`) **حتى تمّ الرفع**.
<!--/جديد-->

<!--جديد-->
## قسمةُ الأسرار بالاستعمال لا بالثقة — **`.env` محميٌّ من الشجرة مكشوفٌ في التشغيل** (قرارُ المالك 2026-09-07)

**والعلّةُ في طبيعة `.env` لا في من يملكه**: يُقرأ في **كلِّ** بناء، **وتراه
كلُّ عمليةٍ في الحاوية**، **ويظهر في `docker inspect`** وفي أثر الأخطاء حين
يُطبع بيئةَ التشغيل. **فهو محميٌّ من الشجرة ومكشوفٌ في التشغيل** — والحمايتان
ليستا واحدة.

**فالقاعدة**: **ما لا يُقرأ في تشغيلٍ يوميّ لا يوضع في `.env`** — وضعُه هناك
**تعريضٌ بلا مقابل**.

| الصنف | مثالُه | موضعُه |
|---|---|---|
| **يُقرأ في كلِّ بناءٍ وتشغيل** | كلمةُ القاعدة · مفتاحُ Fernet · `JWT_SECRET` · مفتاحُ بوّابة واتساب | **`.env` بحقّ** |
| **يقرؤه إنسانٌ أو رفعٌ وحدَه** | مفتاحُ التوقيع وكلمتُه · رمزُ GitHub · مفتاحُ SSH | **خارجَه** |

**والقسمةُ تُقاس ولا تُقدَّر**: يُسأل عن كلِّ مفتاح **من يقرؤه فعلاً** —
`docker-compose*.yml` · `ci.yml` · الشجرةُ كلُّها. **ومسحٌ ناقصُ النطاق يقلب
الحكم**: أوّلُ قياسٍ هنا مسح `backend/app` و`tools` و`scripts` **وفاته
`backend/scripts/seed.py`**، فبدت خمسةُ مفاتيحَ بلا قارئٍ وهي مقروءة.

### وحارسُها `check:env-leak` — **يمسك النسخَ لا الإيداع**

**الخطرُ ليس أن يُودَع `.env`** — الخطّافُ يمنعه، **ومقيسٌ بالنقض**:
`git add` يرفضه بـ`ignored`، و`git add -f` يُدخله الفهرسَ **فيرفضه الخطّافُ
بنصّه**. **بل أن تُنسَخ قيمةٌ منه** إلى تقريرٍ أو سجلٍّ أو تعليقٍ أو مثال.

**وأمسك في أوّل تشغيلٍ تسريباً حقيقياً**: `backend/scenario_demo.py` كان يحمل
**كلمةَ مشرف التطوير حرفاً**، **والتعليقُ فوقها يقول إنها «من `.env.local`»**
— **فنسختان لشيءٍ واحد، والملفُّ متتبَّع**. صارت تُقرأ من البيئة.

**ولا يطبع القيمةَ أبداً** — يسمّي المفتاحَ والموضعَ. **ومقيسٌ أنه لا يطبعها**:
زُرعت قيمةُ `JWT_SECRET` في ملفٍّ متتبَّع، فصاح `rc=1` **وخرجُه خالٍ منها**.

**وثلاثةُ حدودٍ مكتوبةٍ فيه**: لا يرى صدفةً حيّةً ولا سجلَّ حاوية · ولا يمسك
قيمةً مُرمَّزة · ولا يعمل بلا `.env` **فيقول «لم يُقس» ولا يُقرأ ذلك سلامة**.

**وقيَمٌ لا تُحرَس بعلّتها**: أقلُّ من ١٢ حرفاً، ومفاتيحُ إعدادٍ في `SAFE`
بأسمائها — **واسمُ المشرف ورقمُه منها**: حارسٌ يصيح على اسمِ إنسانٍ في أربعة
ملفّاتِ وثائقَ **يُطفأ، ويسقط معه ما يمسكه حقّاً**. وقد وقع في أوّل تشغيل.
<!--/جديد-->

<!--جديد-->
## `check:exec-bit` — **سكربتٌ يفقد بتَّ التنفيذ، ولا يشكو حتى يُشغَّل** (قِيس مرّتين 2026-09-07)

**العلّةُ في أداة التحرير لا في الشيفرة**: تحريرُ ملفٍّ عبر
`\\wsl.localhost` من ويندوز **يكتبه بصلاحية `644`** فيفقد `x`.

| الملفّ | ما وقع |
|---|---|
| `scripts/guards.sh` | سقط بـ`Permission denied` عند أوّل تشغيلٍ بعد تحرير |
| `scripts/deploy.sh` | **`EXIT=126` قبل أن تبدأ البوّابةُ الأولى** |

**وهو عينُ العطب على الخادم**: `git` يحفظ نمطَ الملفّ، **فما يُودَع بلا `x`
يُسحب بلا `x`** — و`deploy.sh` يشغّل `scripts/pull-release.sh` على الإنتاج،
**فيسقط رفعٌ في منتصفه بسببٍ لا علاقةَ له بالشيفرة**.

### ولمَ حارسٌ لا قاعدةٌ تُتذكَّر

**النمطُ لا يُرى في `git diff` كما يُرى سطرُ نصّ** — يظهر سطراً واحداً
(`mode change 100755 => 100644`) **يمرّ عليه القارئ**.

### وأمسك ثلاثةً في أوّل تشغيل — **أقدمَ من العطب الذي بُني له**

| الملفّ | النمط | الأثر |
|---|---|---|
| `admin-panel/android/gradlew` | **644** | **وأخواه 755** — بناءُ المشرف من استنساخٍ نظيفٍ يسقط بـ126 |
| `backend/scripts/backup.sh` | 644 | سكربتُ النسخ |
| `backend/scripts/restore.sh` | 644 | سكربتُ الاستعادة |

**والأولُ هو الشاهد**: `customer-app` و`driver-app` عند `755` و`admin-panel`
عند `644` — **فرقٌ في ثلاثة ملفّاتٍ متطابقةٍ بقيّتُها**، ولم يره أحدٌ لأنه
لا يظهر إلا عند تشغيلٍ من استنساخٍ نظيف.

### وحدُّه — **ما يُنادى باسمه لا بمُفسِّره**

`*.sh` وكلُّ ملفٍّ **بلا امتدادٍ** فيه شِبانغ (`gradlew` · `pre-commit`).
**و`.mjs` و`.py` خارجُه بقياسٍ لا بظنّ**: قِيس أنها تُنادى `node tools/…`
في كلِّ موضع — **فبتُّها لا يُستعمل**. وأوّلُ تشغيلٍ أخرجها **أربعاً مقابل
ثلاثةٍ حقيقية**، **وأربعةُ أسطرِ ضجيجٍ تُطفئ حارساً**.

**ولا يمسك العكس** — ملفٌّ عاديٌّ صار `755` ليس عطباً هنا. **ولا يقرأ القرص**:
مرجعُه فهرسُ git، **لأن المقصودَ ما يصل الخادم**.

**ومقيسٌ في الاتجاهين**: نُزع البتُّ من `deploy.sh` فصاح `rc=1` وسمّاه،
وأُعيد فخرج `rc=0`، **والشجرةُ كما كانت**.
<!--/جديد-->

<!--جديد-->
## `check:enum-coverage` — **حارسٌ يسأل عن الزائد ولا يسأل عن الناقص يمرّ فوق عشرين بالمئة من دفترٍ يراه المشرف** (قِيس 2026-09-07)

**الحدُّ كان مكتوباً منذ 2026-08-23**: «و«أثمّة قيمةٌ مخترعة؟» ليست «أينقص
عضو؟» — سؤالان لحارسٍ واحد». **وثمنُه لم يُقَس حتى اليوم.**

### ما وُجد على شاشةٍ حيّة

`WalletTransactionType`: **ثمانيةَ عشرَ عضواً في الخلفية، عشرةٌ في اللوحة**.
والثمانيةُ الناقصةُ **تُرسم بمفتاحها الإنجليزيّ** في درج الملفّ — رأيتُ
`tip_payment` و`cancellation_fee` بين «شحن» و«تسوية» و«دفع رحلة».

    ٢٣ صفّاً من ١١٥ في دفتر التطوير — **٢٠٫٠٪**

**و`check:enums` أخضرُ بحقّ**: العشرةُ كلُّها في تعداد الخلفية، **فلا قيمةَ
مخترعة**. **والسؤالُ الثاني لم يكن يُسأل.**

### ولمَ الناقصُ أخبثُ من الزائد

**الزائدُ يكسر شيئاً** — قيمةٌ لا يرسلها الخادمُ تترك شاشةً فارغةً أو تسقط
بالمُترجِم أحياناً. **والناقصُ لا يكسر شيئاً**: يرسم مفتاحاً إنجليزياً في
شاشةٍ عربية، **والشيفرةُ صحيحةٌ والاختباراتُ خضرٌ ولا يشكو أحد**.

### وأمسك أربعةً في أوّل تشغيلٍ بعد إصلاح المحفظة

| الموضع | الناقص | الأثر |
|---|---|---|
| `DriverStatus` (اللوحة) | `deactivated` | **كبتنٌ ألغى تفعيلَه يُرسم `deactivated`** |
| `TopupMethod` (اللوحة) | `card` | قناةُ شحنٍ لا تُسمّى |
| `ProviderKey` (اللوحة) | `email` | **مزوّدٌ لا تعرفه صفحةُ العقود فلا يُرسم** |
| `WalletTransactionType` (**الراكب**) | ستّة | **وهو أسوأُ من اللوحة**: المشرفُ يعرف المفاتيح، **والراكبُ لا يعرف شيئاً** |

**وطبقتان لا واحدة**: الاتحادُ يغطّي التعداد، **والخريطةُ تغطّي الاتحاد** —
فإضافةُ عضوٍ بلا اسمٍ تُنتج العطبَ نفسَه. **والحارسُ لاحق أثرَه**: لمّا
أُضيفت الأعضاءُ صاح على أسمائها الناقصة.

### وحدوده — تُقال ولا يُقرأ سكوتُها ضماناً

**لا يقرأ نصَّ الاسم**: «شحن» و«xyz» سواءٌ عنده — **يمسك الغياب لا الرداءة**.
**ولا يعرف أيَّ اتحادٍ يُعرض فعلاً** — والثمنُ عضوٌ يُترجَم بلا حاجة.
**ولا يطابق ما اختلف اسمُه**: المطابقةُ بالاسم **شرطٌ لا اكتشاف**.

> **⚠ وأوّلُ تشغيلٍ اتّهم أربعَ خرائطَ بريئة**: نمطُ المفاتيح كان `[a-z_0-9]`
> **و`JOD` و`JO` كبيرةُ الحروف** — فبدت `CURRENCY_LABEL` و`COUNTRY_LABEL`
> ناقصةً وهي كاملة. **أربعةُ بلاغاتٍ كاذبةٍ من تسعة**، صُحّحت قبل أن تُصدَّق.
> **والحارسُ الذي يخترع عطباً أغلى من واحدٍ يفوته.**

## ونصُّ زرِّ الملفّ — **بيتان لنصٍّ واحد** (وُحِّد 2026-09-07)

`/rides` كانت تقول **«الملفّ»** و`/riders` تقول **«الملف والمحفظة»** —
**والشدّةُ نفسُها تفترق**. **وقِيس على الشاشة لا في الشيفرة.** صار
`OPEN_PROFILE_LABEL` بيتاً واحداً يقرؤه الموضعان.
<!--/جديد-->

<!--جديد-->
## وشكلان لسؤالٍ واحدٍ ليسا نسختين إذا حمل كلٌّ شرطاً (٢٠٢٦-٠٩-٠٧)

**القاعدةُ في هذا المشروع «بيتٌ واحدٌ للحقيقة»**، وهي صحيحةٌ — **وحدُّها أن
البيتَ الواحدَ لسؤالٍ واحدٍ من سائلٍ واحد**.

**وقعت مقيسةً**: بطاقةُ عرض الاشتراك على رئيسة الكبتن تسأل ما تسأله الصفحةُ
التعريفية — «أيُّ عرضٍ قائم» — **فأُعيد استعمالُ `LandingOfferOut` توفيراً
للتكرار**. **ثم عاد الاختبارُ بحقولٍ ناقصة**: الشكلُ العامُّ **نُزعت منه
الأرقامُ بقرار مالك** (§52٫3) لأن الصفحةَ العامّة لا يخرج منها سعر.

**والتوحيدُ كان سيُسقط أحدَ الشرطين حتماً**: إمّا يعود السعرُ إلى الحمولة
العامّة — **وهو ما مُنع نصّاً** — أو يُحجب عن الكبتن الذي يدفعه، **فتقول له
البطاقةُ «عرض» بلا رقمٍ فيضغط ليعرف**، وهو إعلانٌ لا خبر.

**فالسؤالُ قبل التوحيد ليس «أهما متشابهان؟» بل «أيحملان الشرطَ نفسَه؟»** —
فإن اختلف الشرطُ فهما شكلان بعلّتين، **ويُكتب في كلٍّ منهما لمَ ليس الآخر**،
وإلا وحّدهما من يأتي بعدُ بحسن نيّة.

**والفرقُ عن التكرار المذموم مقياسٌ لا ذوق**: نسختان **بلا سببٍ مكتوب**
تفترقان صامتتين — وشكلان **بسببين مكتوبين** يقف عندهما من أراد دمجَهما.
<!--/جديد-->


<!--جديد-->
## حارسان لِما يُرى لا لِما يُقرأ — **موضعٌ بلا صورة، ولافتةٌ بلا نصّ** (٢٠٢٦-٠٩-٠٩)

**كلاهما يمسك عطباً يراه الزائرُ ولا يراه اختبار.**

### `check:shots` — **يمنع بناءَ الموقع، ولا يخفي البطاقةَ الفارغة**

**العلّةُ مقيسة**: `taxo.tajora.ly` تعرض **سبعةَ مواضعَ** بنصّ «لقطة لم
تُلتقط بعد»، **أربعةٌ منها في قسمٍ عنوانُه «خمس محطات من الطلب إلى الدفع»**.

**وموضعُه بوّابةُ البناء** (`site/package.json` → `build`) — فلا يُبنى الموقعُ
ولا يُنشر وفيه موضعٌ بلا ملفّ. **ورمزُ خروجه عددُ الناقص** (قِيس: `5`).

**ولمَ المنعُ لا الإخفاء — والخيارُ كان قائماً**: الإخفاءُ **يجعل الصفحةَ
تكذب بالسكوت**، فقسمٌ يعرض ثلاثاً من خمسٍ **ولا شيءَ يقول إن اثنتين نقصتا**.
**والبطاقةُ الفارغةُ تقول الحقيقةَ وإن قبُحت** — وقُبحُها هو ما يجعل أحداً
يصلحها.

**وما لا يقيسه يقوله**: يقيس أن **لكلِّ موضعٍ ملفّاً**، لا أن الملفَّ حديثٌ
ولا أن نصَّه مقروء. **لقطةٌ باليةٌ تمرّ من هنا** — وقد وقع: `captain-home.png`
كانت تعرض «عمولة TAXO 0%» والعمولةُ الحيّةُ 2٪ (الشكلُ الثاني والعشرون).

### `banner_is_ready` — **لافتةٌ بلا نصٍّ لا تبلغ أحداً، والصفُّ يبقى**

**العلّةُ مقيسة**: صفٌّ عنوانُه «لافتة جديدة» (العنوانُ الافتراضيّ) وجسمُه
فارغ **ومشتعل** — فظهر على رئيسية الراكب بطاقةً فيها جرسٌ ولا شيءَ غيره،
**ودخل لقطةَ الشاشة المنشورة**.

**وموضعُه `services/storefront.banners_for`** — الخلفيةُ لا التطبيق:
**ثلاثةُ تطبيقاتٍ ترسم اللافتات، وشرطٌ في واحدٍ يترك بابين مفتوحين.**

**والصفُّ لا يُحذف** (قرارُ المالك): الحذفُ يمحو شاهداً، والتحريرُ بيده.
**فيُمنع العرضُ ويُقال السببُ للمشرف** في `AdminPromoBannerOut.blocked_reason`
— **محسوبٌ لا مخزون**، ومصدرُه الدالّةُ نفسُها فلا شرطان يفترقان.

**والشرطُ أوسعُ من الحاجة بقصد**: **نصٌّ يُقرأ** — عنوانٌ حقيقيٌّ **أو** جسم.
واشتراطُ الاثنين يحجب لافتةً صالحة، **وحارسٌ يصيح على سليمٍ يُطفأ فيسقط معه
ما يمسكه حقّاً**.

**ونقضُهما مقيس**: بنزع التصفية يسقط `test_an_empty_banner_never_reaches_a_rider`
بنصّه («لافتةٌ بلا نصٍّ بلغت الراكب»)، وبحذف لقطةٍ يسقط `check:shots` باسمها.
<!--/جديد-->

<!--جديد-->
## بوّابةُ المعمار تصيح على **ذِكرِ** مسارٍ في بيانات، لا على كتابةٍ فيه (قِيس ٢٠٢٦-٠٩-١٠)

**ما وقع**: كتابةُ بندٍ في `STATE.md` — لا في الخلفية ولا قربَها — **رُفضت**
بنصّ الشرط الأول: «قبل أن تمسّ الخلفيةَ أو تضيف باباً — يُقرأ `ARCHITECTURE.md`».
**والملفُّ المكتوبُ فيه `STATE.md`، والملفُّ المذكورُ في النصّ ملفُّ بناءِ
الخلفية** — مذكوراً **خبراً عنه**، لا مفتوحاً للكتابة.

**والآليةُ مقروءةٌ لا مُقدَّرة** (`tools/hooks/arch-gate.mjs`):

    ١١٤   else if (INTERPRETERS.has(name) && WRITE_HINTS.test(command)) {
    ١١٥     // مُفسِّرٌ لا يُقرأ نصُّه: تُؤخذ كلُّ سلسلةٍ تشبه مساراً تحت `backend/`
    ١١٦     for (const m of command.matchAll(/…backend[/\]…/g)) add(m[0]);

**فالشرطان يجتمعان على أمرٍ بريء**: الاسمُ `python3` **مُفسِّر**، و`open(p,"w")`
**أثرُ كتابة** — ثمّ يُمسح **الأمرُ كلُّه** بحثاً عمّا يشبه مساراً تحت الخلفية.
**والنصُّ المكتوبُ يمرّ في الأمر نفسِه** (وثيقةٌ داخل `heredoc`)، **فصار
المحتوى هدفاً**. `p` وحدَه هو الهدفُ الحقيقيّ، وقيمتُه `STATE.md`.

**والثمنُ مقيسٌ لا مُقدَّر**: قراءةُ **١١٨١ سطراً** من `ARCHITECTURE.md`
لكتابة بندِ أخبارٍ في ملفٍّ آخر، ثمّ إعادةُ الأمر.

### وهو من عائلةٍ مكتوبةٍ في هذا الملفّ — **ويخالفها في نصفها**

يقرأ أوّلَ وهلةٍ «حارسٌ يخترع عطباً أغلى من حارسٍ يفوته»، و«بوّابةٌ تصيح حيث
لا خطر تعلّم مشغّلَها التجاوز فتُفرَّغ المطلقةُ من داخلها». **وهذا صحيحٌ في
الأثر**: بوّابةٌ تصيح على كتابةِ وثيقةٍ تُدرَّب على أن تُتجاوَز، وبابُ التجاوز
مبنيٌّ سلفاً (`.claude/.guard/OFF` وسجلُّ `bypass.log`، **وفيه تجاوزان مسجّلان
٢٠٢٦-٠٨-٢٥**).

**ويخالفها في العلّة، وهذا هو الذي يُقرأ قبل أن يُضيَّق:** الصياحُ هنا **ليس
خطأً في القياس بل ثمنَ خشونةٍ مقصودة**. المُفسِّرُ **لا يُقرأ نصُّه**، فلا
سبيلَ إلى معرفة قيمة `p` بلا تنفيذه. والخشونةُ نفسُها — «امسح الأمرَ كلَّه» —
**هي التي تمسك الحالةَ الحقيقية**:

    python3 -c 'p="backend/app/services/x.py"; open(p,"w").write(…)'

**فتضييقُها إلى «حرفيّةٌ داخل نداء الكتابة» يفتح ثقباً حقيقياً** ليغلق إزعاجاً.
**والمقايضةُ صريحة: بلاغٌ كاذبٌ على وثيقة مقابلَ كتابةٍ صامتةٍ في الخلفية.**

### **ولم تُضيَّق اليوم، بقرار**

**تضييقُ حارسٍ فعلٌ يُعرض على المالك لا يُفعل** — «ولا إلغاءَ لحارسٍ أو حدٍّ
أمنيٍّ… يُوقَف ويُسأل»، و«إشعارٌ ليس أمراً». **فالخياراتُ تُكتب بأثمانها ولا
يُنفَّذ منها شيء:**

| الخيار | ثمنُه المقيس |
|---|---|
| **يُترك كما هو** | ثمنُه قراءةُ `ARCHITECTURE.md` — **وهي شرطُ المشروع أصلاً**، فالخسارةُ وقتٌ لا حراسة |
| تُستثنى أجسامُ `heredoc` من المسح | **يفتح الثقبَ الأوسع**: سكربتُ بايثونَ داخل `heredoc` هو **أشيعُ** أشكال الكتابة في هذه الجلسات |
| يُشترط قربُ المسار من أثر الكتابة | هشٌّ في مُفسِّرٍ لا يُقرأ نصُّه، **ويسقط بأولِ سطرٍ يُباعد بينهما** |
| يُستثنى حين يكون **هدفُ التوجيه** خارجَ الخلفية | **لا يصحّ هنا**: لا توجيهَ في الأمر، والهدفُ داخلَ نصِّ المُفسِّر |

**والحدُّ الذي يُقرأ من هذا البند**: خضرةُ هذه البوّابة **ليست شهادةً أن
المعمارَ قُرئ** (مكتوبٌ في نصِّها)، **وحمرتُها ليست شهادةً أن الخلفيةَ تُمسّ**.
**فهي تقيس ذِكرَ المسار لا الكتابةَ فيه** — وذلك مكتوبٌ الآن بدل أن يُكتشف
مرّةً أخرى.
<!--/جديد-->

<!--جديد-->
## النسخةُ الرابعةُ عمياءُ عن المُهمَل — **١٥ ميغا على قرص الإنتاج خارجَ كلِّ نسخة** (قِيس ٢٠٢٦-٠٩-١٠)

**القاعدةُ تقول أربعةً**: القاعدة · `.env` · الوثائق · **وما لا يعيده السحبُ من
قرص الإنتاج**. **والرابعُ يُحسب ولا يُكتب بيد** من مصدرين: مسارات المضيف
المثبَّتة في `docker compose config` **لِما هو خارج شجرة المشروع**، و
`git ls-files --others --exclude-standard` لِما هو داخلها.

**وبينهما ثقبٌ لا يمرّ منه شيءٌ صغير:**

    .gitignore:67            landing/downloads
    متتبَّعٌ هناك              **صفر**
    على قرص الإنتاج           **15,507,597 بايت** · 3 ملفّات
    git ls-files --others --exclude-standard   →  **0**   ← الرقمُ الذي تقرؤه البوّابة
    git ls-files --others (بالمُهمَل)           →  **3**   ← الحقيقة

**فحزمُ صفحة التحميل — الراكب والكبتن وبيانُهما — في المنطقة الميتة**: ليست
**خارج** الشجرة فيلتقطها المصدرُ الأول، وليست **غيرَ متتبَّعةٍ غيرَ مُهمَلة**
فيلتقطها الثاني. **وسطرُ البوّابة «غيرُ المتتبَّع: لا شيء — الشجرةُ مشتقّةٌ من
git بالكامل» صادقٌ في نصّه كاذبٌ في دلالته**: المُهمَلُ مستثنىً من السؤال
أصلاً، فالصفرُ جوابُ سؤالٍ لم يُطرح.

### **وثمنُه محدودٌ لا كارثيّ — والحدُّ مقيسٌ لا مُقدَّر**

**الحزمُ تُستعاد من إصدار GitHub**، وقد قِيس ذلك اليومَ فعلاً: `v0.2.4` سُحب
بـ`scripts/pull-release.sh` فأعاد الثلاثةَ وطابق بصماتِها بالبيان. **فالخسارةُ
دقائقُ لا يوم**، بشرطين: أن يبقى الإصدارُ على GitHub، **وأن يكون آخرُ ما نُشر
على الصفحة له وسمٌ** — ومن رفع حزمةً بلا وسمٍ فقد كسر الشرطَ الثاني، **وذلك
مُغلقٌ ببابه**: `pull-release.sh` يقرأ من وسمٍ ولا يقبل غيرَه.

**فهذا بندُ ثقبٍ في تعريف، لا إنذارُ ضياع.** وكتابتُه هنا لأن **الوصفَ يكذب**:
من يقرأ «أربعةً» يظنّ أن كلَّ ما على القرص محفوظ.

### وثلاثةُ طرقٍ بأثمانها — **ولم يُختَر منها شيءٌ بقرار**

| الطريق | ثمنُه |
|---|---|
| **يُترك ويُكتب** (ما وقع اليوم) | **صفرُ كلفة**، والوصفُ يصير صادقاً. ويبقى الاعتمادُ على بقاء إصدارات GitHub |
| يُضاف مصدرٌ ثالثٌ للرابع: `git ls-files --others` **بلا** `--exclude-standard`، مصفّىً بقائمةٍ بيضاء | يُدخل `node_modules` و`dist` وكلَّ مخرَجِ بناءٍ إن أُخذ على عواهنه — **والقائمةُ البيضاء تُكتب بيد**، وهي بعينها ما تتجنّبه القاعدة |
| تُنقل الحزمُ خارج الشجرة | يكسر `pull-release.sh` و`check:apk` معاً، **وكلاهما يقرأ `landing/downloads` بالاسم** |

**والحدُّ الذي يُقرأ من هذا البند**: خضرةُ البوّابة الثالثة تعني «القاعدةُ
و`.env` والوثائقُ وما هو **خارج الشجرة**» — **ولا تعني «كلُّ ما على القرص»**.
**ومن أضاف مساراً مُهمَلاً على الإنتاج فعليه أن يسأل: أيعيده السحبُ أم لا؟**
<!--/جديد-->
