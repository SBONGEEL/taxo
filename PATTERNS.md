<!--جديد-->
# PATTERNS.md — الأشكال، وما تعلّمناه بثمن

**مُلزِمٌ بشرطه في `CLAUDE.md`**: *قبل أن تشخّص عطباً أو تسمّي شكلاً أو تقول «هذا مثلُ كذا» — يُفتح هذا الملفّ.*

**وهذه ليست تاريخاً.** كلُّ شكلٍ هنا **صنفٌ يتكرّر** لا واقعةٌ مضت. **ومطابقةُ عَرَضٍ بشكلٍ مكتوبٍ هنا ليست تشخيصاً** — المكتوبُ يصير قالباً جاهزاً يُلبَس لأوّل عَرَضٍ يشبهه، **والقياسُ وحدَه هو التشخيص**.

**نقلٌ لا تحرير.** كلُّ ما تحت هذا السطر منقولٌ من `CLAUDE.md` بحرفه. وفهرسُه في `CLAUDE.md`.
<!--/جديد-->

### «An empty map is not a defect» — the three points, in order (2026-08-15)

The owner reported that captains had stopped appearing on the rider's map — the same symptom as trial item
7, which had been fixed and measured weeks earlier. **Nothing had regressed: nobody was broadcasting.** The
driver app on the phone had been logged out by the scenario probes, `geo:*` held no keys at all, and
`GET /drivers/nearby` answered `200 []` **truthfully**.

**So measure these three, in this order, before calling it a defect:**

1. **Is there a presence key in Redis?** `geo:drivers:{country}` and `geo:presence:{driver_id}` — a captain
   who is not broadcasting is not on any map, and `drivers.is_online` does not answer this question.
2. **What does `GET /drivers/nearby` return?** An empty array with a live presence key is a backend defect;
   an empty array with no key is the truth.
3. **What *kind* of markers are on the map — not how many.** Measured twice in one session: the rider's map
   always carries his own pulse and the destination pin, so `.mapboxgl-marker` count > 0 proves nothing.
   Distinguish them by their content (`taxo-pulse` / the pin `viewBox` / a car) — **counting markers lied
   twice in a single session**.

Proven end to end afterwards: a captain went online → `geo:drivers:JO` + his presence hash appeared →
`/drivers/nearby` returned `{"ref":"2681554d…","heading":124.9}` → the rider's map drew
`["موقعي","دبوس","سيارة"]`.

### The twelfth shape — a fallback that works, and hides the defect it was built for (2026-08-19)

**The OTP template feature had never once reached the wire, and nothing failed.** The gateway reads
`otp-template-rules.json` to decide whether an incoming template may go out. The file was **not in the
gateway's image at all** — no `COPY` in its `Dockerfile`, and the compose bind mounts it into the
**backend** only. So `template.js` took its deliberately-strict fallback (`max_body_bytes: 0`) and
rejected **every** template with `too_long:3928>0`, then sent its own built-in text instead.

**Every layer reported success.** The panel saved the template and previewed it. The backend validated
it against the same rules (it *does* have the file) and returned 200. The gateway returned 200 with a
real message id. WhatsApp delivered. The recipient read a correct OTP. The only trace was a `warn` line
inside a container's log — which is where it sat for as long as the feature has existed.

**The shape: a fallback whose success is indistinguishable from the feature working.** It is the
opposite failure mode to the sixth shape (a criterion measuring an event the system never emits). There,
a healthy channel reported failure. Here, a dead feature reported health — and that is worse, because
failure gets investigated and health does not.

**Three rules came out of fixing it, and the second is the general one.**

- **The condition ships inside the artifact that enforces it.** The rules file is now `COPY`d into the
  image, not left to a bind mount: a container that needs a correct compose file in order not to
  silently disable a feature is a container that will silently disable it.
- **A fallback is always logged *and* always visible where the decision is made.** `logger.warn` in a
  sidecar is not a visible trace. The gateway now publishes `template_rules.loaded` and
  `last_template_fallback` in `/status`, the backend carries both through `WhatsAppSessionOut`, and the
  panel's session card says «البوابةُ لا تقرأ ملفَّ شروط القالب، فترفض كلَّ قالبٍ محرَّر» — read by the same
  person who just edited the template. It also shouts once at startup, at `error`.
- **Guard the artifact, not only the tree** (the tenth shape applied). `npm test` in the gateway now
  asserts two separate things: that `rulesState().loaded` is true *and* that the `Dockerfile` carries the
  `COPY`. The first passes in a repo where the image is broken; only the second catches the real defect.
  Both verified by deletion — removing the file fails 9 tests, removing the `COPY` line fails 1.

**And the proof of the fix is not that saving works.** It is a dry-run through the real chain — template
saved through the panel's door, rendered by the backend's own `render`, posted to the gateway with
`deliver:false` — returning `fell_back:false` and `would_send` equal to the edited text. Before the fix
that same call returned `fell_back:true`.

### الشكلُ الثامنُ في ثوبٍ ثالث — **موضعان يحسبان قيمةَ مالٍ واحدة، وحدٌّ في أحدهما** (2026-08-23)

**الشكلُ الثامنُ الأصلُ**: بابان ينشران الشيءَ نفسَه ويفترقان. **وهذا وجهُه
في الحساب لا في النشر**: موضعان **يحسبان** قيمةَ مالٍ واحدة، **وكلٌّ صادقٌ
وحدَه**، والحدُّ الذي كُتب لأحدهما لا يبلغ الآخر.

**ووقع مقيساً**: «الرصيدُ المتاح» حُدّ عند الصفر في
`withdrawals.available_balance` — **خلفيّاً، في مسار سحب الكبتن** — بعد عطبٍ
مقيسٍ في 2026-08-20. ثم ظهر على شاشة **تحويل الراكب**: «رصيدك بعده
**−12.500 د.أ**» على رصيدٍ صفر. **ولم يمسكه ذاك الحدّ**، لأن هذا **طرحٌ في
المتصفّح** (`subtractMoney`) في تطبيقٍ آخر على مسارٍ آخر.

> **حدٌّ في موضعٍ لا يحرس موضعاً ثانياً يحسب الشيءَ نفسَه.**

**وما يجعله يفلت من كلِّ حارس**: لا حقلَ ناقصاً (`check:config`)، ولا مبلغاً
بلا قارئ (`check:money-visible`)، ولا ردَّين يفترقان (اختبارُ البابين) —
**فالبابان لا يفترقان، لأن أحدهما لا يمرّ بباب أصلاً**. والرقمُ يُحسب في
الشاشة، ولا شيءَ يقارنه بشيء.

**والعلاجُ الذي وقع طبقتان**: الرقمُ لا يُعرض سالباً، **والزرُّ يُطفأ بعلّةٍ
مكتوبة** — وزرٌّ يعمل ثم يردّ ٤٠٩ يعلّم صاحبَه أن يعيد الضغط. **والعلّةُ مع
الزرِّ لا داخلَ ورقةٍ لا تُفتح.**

**وأمّا حارسُه فسؤالٌ معروضٌ لم يُبنَ** — وهذه حجّتا الجانبين كما قِستُهما:

| | |
|---|---|
| **ما يجعله ممكناً** | مفرداتُ المال لها بيتٌ واحدٌ مستعمَل (`tests/money_format.py`)، ودوالُّ الحساب في الواجهة قليلةٌ ومعدودة (`subtractMoney` وأخواتُها). فحارسٌ يسأل «أيَّ حقلٍ ماليٍّ يمرّ بدالّةِ حسابٍ في الواجهة؟» **قابلٌ للكتابة**، ويُقاس في الاتجاهين |
| **ما يجعله شرطاً بشرياً** | ما يمسكه ليس «حساباً في الواجهة» — **§14 يمنعه أصلاً وهذا حارسُه** — بل **أن يكون للقيمة حدٌّ في الخلفية لا يعرفه الحسابُ الثاني**. وذلك يحتاج **جدولاً مكتوباً بيدٍ** يربط كلَّ قيمةٍ بحدِّها، **وهو «هل تذكّرتَ؟» التي يُبنى الحارسُ لإلغائها** |

**والقراءةُ التي أميل إليها**: الشقُّ الأولُ وحدَه (**«لا حسابَ مالٍ في
الواجهة»**) حارسٌ نظيفٌ يُبنى ويُقاس، **وهو يمسك هذه الحالةَ بعينها** لأن
`subtractMoney` حسابٌ في الواجهة. أمّا «حدٌّ في موضعٍ دون موضع» فيبقى شرطاً
بشرياً. **ولم يُبنَ منهما شيء — والقرارُ للمالك.**

### الشكلُ الرابعَ عشر — **سطحٌ تُفحص أطرافُه ولا يُسأل: أيتحدّث؟** (2026-08-23)

**كلُّ حرّاسنا يسألون أسئلةَ بنية**: أللمسار زرّ؟ أللحقل مرآة؟ أللاتحاد عضوٌ
ناقص؟ **ولا واحدٌ منهم يسأل سؤالَ زمن**: هل هذه الشاشةُ تعرض ما تغيّر بعد أن
رُسمت؟

**ووقع مقيساً**: سجلُّ رحلات اللوحة يعرض «مقبولة» **والرحلةُ `in_progress` في
القاعدة** — قِيس بعد `arrive` وبعد `start`. والعلّةُ سطرٌ غائب:
`LiveMap.tsx` فيه `REFRESH_MS = 5_000` و`setInterval`، و`Rides.tsx` **بلا
استطلاعٍ البتّة**. فالشاشةُ لقطةٌ تُقرأ متابعةً.

**وما يجعله يفلت من الثلاثة**: `check:doors` يمرّ لأن **للباب زرّاً** —
الشاشةُ تناديه فعلاً، مرةً واحدة. و`check:contract` يمرّ لأن **الفعلَ والمسارَ
صحيحان**. و`check:readers` يمسح `lib/` ولا يسأل عن الزمن. **ولا شيءَ يفشل،
ولا رقمَ يكذب — الرقمُ صحيحٌ لحظةَ قراءته وحدَها.**

**والقاعدةُ**: كلُّ شاشةٍ تعرض حالاً **تتغيّر بفعل غيرِ من يقرؤها** إمّا
تستطلع وإمّا تقول صراحةً إنها لقطة. **والصمتُ بينهما هو العطب** — لأن قارئَها
يفترض المتابعة، وافتراضُه مجّانيٌّ عليه وغالٍ علينا.

**ولم يُكشف إلا بقياسٍ حيٍّ من ثلاثة أسطحٍ معاً** — أوّلُ مرةٍ يقع ذلك في هذا
المشروع (2026-08-23). فالسطحُ الثالثُ يُفحص طرفاه — بابُه في الخلفية وشاشتُه
في الشجرة — **ولا يُقاس هو**.

### الشكلُ الخامسَ عشر — **حارسٌ صادقٌ تُوسَّع دعواه فوق نطاقه** (2026-08-23)

**من نادى حارساً مفرداً كتب عن سلسلةٍ لم يبلغها.**

**ووقع مقيساً**: `HANDOFF.md` شهد أن «البناءاتِ الثلاثةَ بحرّاسها خضراء»،
**وتطبيقُ الكبتن لا يمرّ `tsc` أصلاً** — `endpoints.ts:520` يستعمل `API_URL`
بلا استيراد. والقياسُ ثلاثيّ: الإيداعاتُ الستُّ **لم تُدفع** فـCI لم يعمل
عليها؛ و`tsc -b` **يفشل على الإيداع نفسِه** في شجرةِ عملٍ منفصلة؛ فالبناءُ
**يستحيل** أن يكون نجح بعد تلك الساعة، والشهادةُ كُتبت بعدها بساعةٍ ونصف.

**والحارسُ لم يكذب.** `check:client-doors` شُغِّل وصدق — أرقامُه مسجَّلةٌ في
رسالة الإيداع (١٤٢ · ٧٨ · ٦١) **وهي أرقامُه اليوم بحرفها**. الذي وقع أن
دعواه وُسِّعت: هو يقول «مسارٌ إداريٌّ بلا زرّ: لا شيء»، فتُرجمت «**البناءُ
أخضر**» — **وهي دعوى أكبرُ مما قِيس**. و`tsc -b` يقع **بعد عشرة حرّاسٍ** في
سلسلة `npm run build`، فمن ناداه مفرداً لم يبلغه.

**فليس هذا الشكلَ الثالثَ عشر** (حارسٌ يقيس ما لا يُقاس) **ولا حارساً يخترع**.
هو **صدقٌ في موضعه، وترجمةٌ خاطئةٌ لنطاقه** — وهي أخطرُ من الحمراء: **الحمراءُ
تُرى والشهادةُ الكاذبةُ لا تُرى**.

**والقاعدة**: **ما يُكتب في تقرير هو ما شُغِّل بحرفه، لا ما يُستنتج منه.**
«مرّ `check:doors`» ليست «مرّ البناء»، و«مرّت المجموعة» ليست «مرّ الحارس».
ومن أراد أن يشهد للبناء **يناديه هو** — `npm run build` — ويُثبت رمزَ خروجه.

### الشكلُ الثالث عشر — **التمييزُ المرئيُّ وشايةٌ ولو بدا تحسيناً** (2026-08-22)

**قاعدةٌ واحدةٌ تجمع عطبين وقعا في يومٍ واحدٍ ولا يشبه أحدُهما الآخرَ ظاهراً:**

| أين | ما بدا تحسيناً | ما كان في الحقيقة |
|---|---|---|
| صورةُ الكبتن | «لا صورةَ لمن أُعفيت» — احترامٌ للإعفاء | **كلُّ من لا صورةَ له مُعفى، والمُعفى امرأة**: فالغيابُ نفسُه إعلان |
| سيارةُ الخريطة | «مثلثٌ لمن لا اتجاهَ له» — أصدقُ من ادّعاء اتجاه | **شكلٌ ثانٍ يعلن من لا يبثّ اتجاهه** — ويُعدّ من الخارج |

**والقاعدة**: **امتيازٌ — أو نقصٌ — يُمنح لفئةٍ يصير علامةً عليها متى كان
غيابُه مرئياً.** فالحمايةُ ليست في منح الإعفاء، **بل في ألّا يُميَّز
المُعفى**؛ ولا في الصدق عن نقص المعلومة، **بل في ألّا يُعرَف من ينقصه**.

**والعلاجُ في الحالتين واحد: يُملأ الغيابُ بشيءٍ لا يُفرَّق عن الحضور** —
حرفٌ يُرسم في الخادم بطولٍ ثابت (`services/avatar.py`)، وسيارةٌ تُرسم عند صفر
درجةٍ كما تُرسم عند ١٢٤٫٩ (`carElement`). **ولا حقلَ يقول «عندي/ليس عندي»**:
حقلٌ كهذا يعيد الفرقَ من بابٍ آخر.

**ويُقاس في الشبكة لا في الشاشة**: من يقرأ الشبكة يرى **رمزَ الحالة وحجمَ
الردّ وترويسته** — فأيُّ فرقٍ في أحدها وشايةٌ ولو رسم التطبيقُ الشيءَ نفسَه.
و`tests/test_photo_leak.py` يقارن **البصمةَ** لا الصورة.

**وأخطرُ ما فيه أن التسرّبَ في الحالة المستقرّة لا في اللحظة**: الردّان كانا
متطابقين فعلاً (٤٠٤ بجسمٍ واحد)، **والوشايةُ في أن غيرَ المُعفى يرفع صورتَه
يوماً فتظهر** — فمن لم تظهر صورتُه أبداً مُعفاة. **فلا يُقاس ردٌّ واحدٌ
ويُقال «متطابقان»؛ يُسأل: ما الذي يفترق بعد أسبوع؟**

### The eleventh shape — an obstacle that exists only on a device (2026-08-19)

**Four in one feature, and none of them is visible from a browser, a test, or a build.** The switch
button was type-correct, unit-tested, and green in every guard — and did nothing on a phone:

| what appeared | what it was |
|---|---|
| the button did nothing at all | **`intent://` is a Chrome behaviour**; inside a WebView it is a no-op |
| "not installed" for an app **that was installed** | **Android 11+ package visibility** — without `<queries>` the OS hides other packages |
| `canOpenUrl` logged `Package name 'taxo-driver://…' not found` | on Android it takes a **package name**, not a URL; `openUrl` takes the URL. One parameter name, two meanings |
| the app opened and **sat on its login screen with the token in hand** | a cold start delivers the URL through `getLaunchUrl()`; **`appUrlOpen` never fires** |

**The most dangerous is the second, and its danger is its silence.** No exception, no log line, no failed
build — a correct call returns `false`, and the app then tells the user, in good Arabic, that an app on
his own phone is not installed. Every layer reported success.

**The rule: anything that touches the operating system — intents, package visibility, cold start, the
launcher — is not believable from a browser or a test.** A WebView is not Chrome, an emulator is not a
phone, and a green suite says nothing about whether the OS will hand your app the URL. These are
measured on the device or they are unknown.

**And a fifth, of the same family but about time**: the handoff window was 30 s "because opening an app
takes seconds". Measured cold start on the S21: **3.4 s and 15.1 s** — the worse one eats half the
window before the exchange call begins, and a perfectly valid handoff came back `invalid_token`. It is
120 s now, ≈8× the worst measured start, with the reasoning written where the constant lives: what
carries the security is single use, target binding, and re-checking at exchange — not brevity.

**A sixth was mine and it is the project's own recurring shape.** The landing route was placed *outside*
the session guard — and still *inside* `Boot`, which withholds rendering until config **and session**
resolve. So the route whose whole job is to create a session was waiting for one. Measured: token in
`location.hash`, `/config` answering 200, splash still up, exchange never attempted. The cure was not to
move the route but to delete it: **the exchange is not a screen**, so it now runs in the startup listener
before React mounts, and the splash — which exists to be the visible wait — is the wait.

### The tenth shape — a green build guard says nothing about what the user is running (2026-08-19)

**Both guards were green and the phone was running code from before the change.** `check:target`
refused an undeclared target and `check:dist` confirmed the built bundle carried
`https://api.tajora.ly` and no localhost. Both true. Both irrelevant: `dist` had been built *before* the
three confirm-sheet changes, and nobody rebuilt it.

**So the first press of the transfer confirm sent 4.500 د.أ on one tap** — the exact defect that had
just been fixed, reproduced live, because the fix was in the tree and not in the bundle.

**The shape: every guard in this project validates the source tree, and the user runs an artifact.**
`tsc`, `check:scale`, `check:enums`, `check:config`, `check:flags`, `check:slot`, `check:target`,
`check:dist` — all eight answer "is the code right?". **None answers "is this the code that is
running?"** And `check:dist` is the closest and still does not: it verifies the bundle's *target*, never
its *age*, so a stale `dist` from any earlier commit passes it perfectly.

It is the same family as the three container traps already recorded here — a `restart` that keeps the
old image, a bind mount inotify cannot cross, a `run` that inherits a restart policy. Each makes the
system look like it did what you asked. **This one adds a phone, where the gap can be days rather than
seconds**, and where the APK is a shell around a remote bundle so nothing about the installed app
changes when the bundle goes stale.

**The rule, and it is now step zero of every device round** (below): rebuild, redeploy, reinstall, and
then **prove from the device itself** that what is running is the latest build — by comparing the served
bundle hash against the one just built, not by trusting that a build happened.

### ⚠ وخُضرةُ CI **لا تحرس الشكلَ العاشر أصلاً** (قرارُ المالك 2026-08-24)

**يُقرأ قبل أن يُبنى على خضرةِ CI شيءٌ عن عمر الحزمة.**

`check:served` هو الحارسُ الوحيدُ لهذا الشكل، **وهو الحارسُ الوحيدُ في
المشروع الذي يغيّر سلوكَه في CI** — مقيسٌ 2026-08-24 بتشغيل **٤٣ حارساً
مرّتين** (بـ`CI` وبدونه) ومقارنةِ المخرَج والرمز: **الفرقُ فيه وحدَه، والباقي
متطابقٌ حرفاً**. وهو يعلن ذلك صراحةً ويخرج بصفر:

> «عمرُ الحزمة **لم يُقس**: بيئةُ CI تبني ولا تنشر، فالمقارنةُ تسأل عن خدمةٍ
> لم يصلها هذا البناء. محلُّه البوّابةُ الخامسة.»

**وهذا صوابٌ في موضعه** — قاعدةُ «حارسٌ يُشغَّل حيث لا يملك ما يقيسه يعلن *لم
يُقس*» — **وخطرُه في قراءته من بعيد**: من يرى CI أخضرَ بعد سنةٍ يظنّ أن
«الحزمةُ المخدومة = المبنيّة» **محروسةٌ هناك، وهي ليست محروسة**. والإعلانُ
يمرّ في سجلٍّ لا يقرؤه أحدٌ بعد أسبوع؛ **والخُضرةُ هي التي تبقى**.

**فالحكم**: **الشكلُ العاشرُ يُقاس محلياً وعند البوّابة الخامسة وحدَهما.**
وخُضرةُ CI تشهد للشجرة — للحرّاس، وللأنواع، وللمجموعة — **ولا تشهد لعمر
القطعة التي يشغّلها إنسان**. ومن نقل خضرةَ CI شهادةً على ذلك فقد نقل ما لم
يُقَس.

### The tenth shape's newest face — two columns for one product, and one lags in silence (2026-08-21)

**What a person downloads and what we measure by cable are two different artefacts**, and nothing
makes the gap visible. Measured this session: the driver APK installed over USB carries the
foreground service and the push plugin; **the download page still serves the 19 Aug build with
neither**. So a device round run against the published package would have measured *a different
product*, and a human installing from the page **would have wiped what we were measuring**.

**It is the same principle one layer further out** — tree ≠ `dist` ≠ container ≠ tunnel ≠ edge ≠
**what is in a human's hand** — but with a twist the earlier faces did not have: **the two artefacts
can be produced by the same command and still diverge**, because publishing is a separate act from
building. Nothing fails; both are "the app".

**So step zero grew a sixth column**: «ما تخدمه صفحةُ التنزيل» beside «المثبَّتُ على الهاتف», for
both APKs. And the rule: **every package measured by cable is either published or explicitly
declared unpublished** — the page is never left behind while something else is measured.

**And `versionCode` is what makes the divergence visible to Android itself**: two builds under the
same code are the same package to the OS, so the second does not install as an update.
`tools/apk-manifest.mjs` refuses to publish a changed fingerprint under an unchanged code — it fired
on this very build, which is why the driver package is now `versionCode 2` / `1.1`.

### The tenth shape, three times — and why step zero is now three-way

**A green source tree says nothing about the artifact a person is running.** It has now cost this
project three separate investigations:

1. **The rider's transfer sheet** sent 4.500 on one tap — the fix was in the tree, the bundle predated it.
2. **The panel's document viewer** appeared not to exist — it was built after the served `dist`.
3. **The driver app's upload** appeared to send `POST` — the phone held an older bundle, and my guard
   compounded it.

Each time the reasoning was identical and each time it was reconstructed from scratch. **So step zero
is no longer a habit; it is a table in every report after every build**, and it covers the panel too —
not just the two phones, which is what let occurrence 2 through:

| | built | served locally | served publicly |
|---|---|---|---|
| every app | hash | must match | must match |

**Three columns, not two.** The local container can serve a fresh `dist` while the tunnel serves a
stale one, and the phone can hold something older than both.

### `save()` announces success only after it sees the file (2026-08-20)

**The twelfth shape, third dress.** `core/storage.save` wrote to a temp file, `replace`d it into place,
`chmod`ed it, and returned — **and the caller then wrote a database row pointing at it**. Nothing
between those two steps ever asked whether the file was there.

Finishing a transfer is not the same as writing bytes: a full disk, a refused permission, a read-only
mount — each ends the loop with no exception and leaves a row that promises a file which is not there.
**And a row promising a missing file is worse than a failed upload**: the first is discovered on review
day by someone who cannot act on it, the second is retried in its own second.

`save()` now `stat()`s the final path and compares the size against what it counted; a mismatch unlinks
the file, logs both numbers, and raises. **The rule generalises: any path that writes a file
acknowledges success after verifying the file exists at its size — never after the transfer ends.**

### The tenth shape has a sibling on the server — writing a setting is not the setting taking effect (2026-08-20)

**The tenth shape says a green guard tells you nothing about the artifact that is running.** Its
server-side twin appeared on the first hardening pass: `PasswordAuthentication no` was **written
correctly** into `/etc/ssh/sshd_config.d/50-taxo-hardening.conf`, `sshd -t` validated, `systemctl reload
ssh` succeeded — and passwords were **still accepted**.

**Cause, measured**: Contabo's image ships `/etc/ssh/sshd_config.d/50-cloud-init.conf` carrying
`PasswordAuthentication yes`. Drop-ins load alphabetically and **the first declaration wins in sshd** —
`c` sorts before `t`, so cloud-init's `yes` beat our `no` in a file with the same numeric prefix. The
fix was the name (`00-taxo-hardening.conf`), not the content.

**And the cloud-init file was deliberately not deleted**: the provider's tooling may rewrite it, so
deleting reads as success and then silently returns. **It is left in place and outranked.**

**The rule: measure the setting from the tool that consumes it, never from the file you wrote.**
`sshd -T` prints the *effective* configuration after all includes and precedence. Reading it is what
turned "I wrote the hardening" into "the hardening is in force" — and had I trusted the write, I would
have announced a locked door that was open.

It generalises past sshd. Anything with an include directory and first-or-last-wins precedence — nginx,
sysctl, systemd drop-ins, PAM, `apt.conf.d` — has the same trap, and in every one of them the config
file you edited is not the answer to "what is in force".

### Step zero for every phone round — prove the artifact before measuring anything

**Do not begin a measurement on a bundle whose age you have not checked.** The order is fixed:

1. **Rebuild both PWAs with their declared target** (`VITE_API_BASE_URL=… npm run build`), so
   `check:target`/`check:dist` run and `dist` is current.
2. **Restart the containers that serve them — with every compose file they need.** On this machine
   that is `docker compose -f docker-compose.yml -f docker-compose.tunnel.yml`; a plain
   `docker compose up -d backend` recreates it **without** the tunnel's `CORS_ORIGINS`, and both phones
   then sit on «الشبكة ضعيفة» while the backend answers curl perfectly. Measured on 2026-08-19. Then read
   the served bundle name (`curl https://app.tajora.ly | grep assets/index-…`) and confirm the hash
   **changed** from before.
3. **Reinstall the APKs** and record `firstInstallTime`/`lastUpdateTime` from `dumpsys package`.
4. **Prove it on the device**: the WebView's page URL is the declared host, and the loaded bundle hash
   matches the one built in step 1.

Only then does a measurement mean anything. A round that skips this measures an unknown version, and
its findings — including "the fix did not work" — are about that unknown version.

### The ninth shape — an intermediate step no human has ever pressed (2026-08-19)

**The ratio is the whole argument. Four money steps were pressed for the first time; three of them
revealed a defect on the first press.** Not "under load", not "on an edge case" — on the first press,
by the first person who ever pressed them.

| step pressed | what the first press revealed |
|---|---|
| the captain's subscription confirm sheet | it showed the **undiscounted** price while the card above it showed the discounted one |
| the panel's manual-subscription amount field | its label named the list price, so an admin typing "the amount owed" typed the wrong number |
| the rider's transfer confirm | **there was no confirm at all** — a typed phone number sent money on one tap |
| the rider's tip | pressing an amount **sent it immediately**, on a screen built to be tapped fast |

The one that held (the wallet topup sheet) was the one a visual pass had opened before.

**So the rule is not "test more". It is a prior**: a step is *expected* to be broken until someone has
pressed it, and the reason is structural rather than statistical. Three detectors exist in this project
and **none of them reaches an intermediate step**: there is **no frontend test runner at all** (stage 9
added no business logic to test, and that decision still stands), the backend suite calls the endpoint
that the step eventually reaches and never the step, and `tsc` type-checks a sheet that renders a
correct-looking wrong number. A screen that renders is a screen that compiles; **nothing in the toolchain
distinguishes "shows the price" from "shows *this* price"**.

**And two of the four were not wrong values but missing doors** — the transfer had no sheet and the tip
had no send button. Those are invisible to every guard by construction: a guard compares what exists
against a rule, and there was nothing to compare. This is the same family as "a rule with no door" and
"a field with no mirror", arriving through the step rather than through the field.

**What follows operationally**: when a money path is touched, press its *intermediate* steps on a real
device, and treat an unpressed one as a finding rather than as unknown. That is why the three changes of
2026-08-19 (`SPEC.md` §17.7-ب) were pressed on two phones before being called done, and why the
money-format sweep — the seventh shape's guard — cannot substitute: it reads what the backend published,
and every one of these four defects lived above it.

### The eighth shape — two doors publishing the same thing, each honest alone (2026-08-19)

**Whatever is published from two doors goes through one builder — or the difference is measured, never
assumed.**

Subscription plans are published from **two** endpoints: `GET /subscriptions/plans`, and
`GET /subscriptions/me`, which carries them in its own response **on purpose** — the screen would
otherwise make two calls every morning (the reason is written in that route's docstring). The
per-driver discount was computed in the first and forgotten in the second. **The captain's screen reads
the second**, so it drew no discount at all while the API — asked directly — returned one correctly.

**Every test passed, and none of them could have caught it.** Each endpoint has its own test, each test
asks its own door, and **each door was honest about itself**: `/plans` really did carry the discount,
`/me` really did carry plans. Nothing compared them, because nothing knew they were the same thing.
Sixteen tests over the feature were green.

**Nor could any existing guard**: the payload shapes are identical (both `SubscriptionPlanOut`), so
`check:config` sees one mirrored type and is satisfied; `tsc` sees the fields present; the enum and
scale guards are unrelated. The types agreed **because they were the same type** — which is exactly why
the divergence was invisible: the difference was not in the shape but in **which values got filled**.

**Only opening the screen showed it**, which is the family's defining property.

**The rule, in order of preference:**

1. **One builder, called by both doors** — what was done here (`_plans_with_offers`). A second door
   cannot then forget, because there is nothing to remember.
2. **If they must stay separate, a test compares the two responses field by field** — not two tests
   each asserting its own door is fine.

**And the smell that precedes it**: a route that carries someone else's payload "so the screen needs one
call". That convenience is correct and worth keeping — it is the reason `/me` carries plans at all — but
it silently creates a second publisher of a value the first one owns. **Whenever a response embeds
another endpoint's payload, ask which of them computes it.**

### The seventh shape — a money amount that serialises as `"0"` instead of `"0.000"` (2026-08-19)

**It happened three times, so it is a class, not a slip.** `rewarded_total` when referrals were
generalised, `total_given_up` in subscription offers, and — caught by the guard within an hour of being
written — `discount_amount` on the subscription row itself.

**The mechanism**: a `MONEY` column read from Postgres arrives as `Decimal('0.000')` and serialises to
`"0.000"`; a value **constructed in Python** — a schema default, a `SUM` that returned nothing, or
`max(Decimal("0"), x)` — carries exponent 0 and serialises to `"0"`. The apps print money as text by
rule (§14 forbids passing it through `Number`), so a captain reads `٠` in a column of `٠٫٠٠٠`.

**Nothing existing can see it**: the type is `Decimal` and correct, the field exists, the number is
numerically right. Only its *text* differs — so `tsc`, `check:enums`, `check:config` and the build are
all green, and the two earlier instances were **covered by passing tests** that simply never asserted
the format.

**The third instance is the sharpest**: `max(Decimal("0"), Decimal("0.000"))` returns **the first
argument** — Python's `max` keeps the earlier of two equal values — so the unquantized zero wins even
though the subtraction produced a quantized one.

**The guard is a sweep over every response the suite produces**, not a per-field annotation
(`tests/money_format.py`, hooked into the `client` fixture). Two options were weighed:

- **Quantize at the serialization boundary** removes the possibility — but only if money is
  *distinguishable*. Of 187 `Decimal` fields in the schemas, 51 are **not** money (a discount
  percentage, a rating, a distance), and printing `15.000%` or a `4.500` rating is a display change
  nobody asked for. So it needs a `Money` type on 136 fields — and *"did you remember the type on the
  new field?"* **is the same class of oversight we are curing**, so the guard would itself need a guard.
- **The sweep needs no per-field discipline at all**: nothing is added when a new money column appears,
  and one test touching the endpoint is enough for it to be checked. Both earlier instances would have
  been caught the day they shipped.

Its limit is stated rather than hidden: **what the suite never touches is never checked** — it guards
what is exercised and claims nothing more. And the field vocabulary matches whole names and suffixes,
never substrings, with named exclusions (`discount_value` is a percentage, not an amount).

### The sixth shape — a success criterion measuring an event the system never emits (2026-08-18)

**This is the fifth family member's successor and the most expensive one so far.** The family is
"what the build cannot see": a class silently dropped by tailwind-merge, a key missing from the pixel
scale, a value missing from an *array* rather than a union, and `Slot` throwing on two children. All
four are about code that compiles and then does not do what it says. **The sixth is worse, because it
does not merely fail — it produces a confident, wrong diagnosis and points it at someone else.**

**The shape: a success criterion that waits on an event the system does not emit, in a channel whose
log is muted so the real failure signal cannot be seen either.**

The WhatsApp gateway judged "the message was sent" on `messages.update` with `status >= 2`, named in
its own comment «إقرارُ الخادم». Baileys **never emits that event for a server ack**: the status comes
only from a `<receipt>` node (`Socket/messages-recv.js:525`), whose map (`Utils/generics.js:249`) has
three entries and none of them is the server's ack; a successful `<ack>` is swallowed by `handleBadAck`
with no event at all. So — by the source, not by guesswork — the gateway was waiting for **a delivery
receipt from the recipient's handset**, which is exactly what the same file's comment forbids waiting
for. The real success equation was:

> **sending an OTP succeeds if the recipient's phone is awake within ten seconds.**

A phone in Doze returns 503, and `otp.issue` deletes the digest on any send failure — so the code
WhatsApp delivered was **invalidated on our side before its owner could read it**. That, not a banned
number, is what stopped registration.

**And the one signal that does mean "WhatsApp refused this message" was filtered out**: `handleBadAck`
emits `status = ERROR = 0`, and `>= 2` drops it. With `logger: pino({ level: "silent" })` on the socket,
Baileys' own `'received error in ack'` never reached `docker compose logs` either. **A channel blind to
the defect it is accused of produces a confident wrong verdict** — "the sending number is restricted"
was written into this file, and there was no path in the system capable of establishing it.

**Measured, end to end, on the owner's S21** (2026-08-18, ride to `218916166400`):

| event | when | what it is |
|---|---|---|
| bytes on the wire | 0 ms | `sendMessage` resolving = a websocket write, nothing more |
| `<ack class="message">` `error=null` | **+122 ms** | **WhatsApp accepted it.** No refusal, ever |
| `<receipt>` type absent ⇒ delivery | +2514 ms | the *handset*, and the only thing that satisfied `>= 2` |
| `messages.update status=3` | +2515 ms | derived from the receipt above |

The phone was in the owner's hand, so it returned 200 in 3.5 s. Asleep, the same healthy send is a 503.

**And a later send showed the old criterion was non-deterministic on top of being wrong.** A third
event can satisfy `>= 2`: a `<receipt type="sender">` from **our own linked phone** syncing the sent
message — status 2, arriving at 717 ms, from our own `@lid`. So the old verdict was decided by whichever
of three unrelated things happened first — our phone's sync receipt, the recipient's delivery receipt, or
nothing at all — and never once by the server's ack at 417 ms. `STATUS_MAP`'s `sender` entry *is*
SERVER_ACK by name, which is exactly how the misreading survived review: the name was right and the
sender of the event was not.

**The fix is three lines of judgement, and each is a rule worth keeping.** The verdict is now the raw
`<ack class="message">` node — read at its source rather than through the derived event, so the two
cannot disagree; `attrs.error` present is an immediate 503 carrying the code WhatsApp wrote (401 and
403 are not the same fact a month later, and one of them *is* a ban); and the delivery receipt is
**logged and never awaited** — it is the only proof of real arrival, so it stays in the log for the day
someone reports a code that never came, but it decides nothing. After the fix the same send returned
**200 in 0.89 s** with `CB:ack` at 481 ms and the receipt landing at 2362 ms marked `awaited: false`.

**The message id is generated before the send** (`generateMessageIDV2`) and the waiter registered before
a single byte leaves, because an ack that arrives in 122 ms can beat `sendMessage`'s own return — an ack
that *did* arrive read as "no ack", which is this very defect in a narrower window. And the early-reject
guard (`settled.catch(() => {})`) exists because an unhandled rejection **exits the process** on Node 22.

**Two more things this turned up, both previously invisible behind the mute.** Baileys' init queries were
timing out at 60 s on every connect; reading the raw wire at `trace` showed `<props protocol='2'>` is
**never answered** while `blocklist`, `privacy` and the 30 s pings are all answered — so the socket was
healthy and one unread query was hanging. `fireInitQueries: false` now, and its safety is measured from
our own state: `creds.json` carries no `lastPropHash`, so this number was QR-linked with props unanswered
its whole life. **And it explicitly was not what swallowed messages** — on the same socket with props
hanging, a message was acked in 122 ms. That swallowing was the DNS drop, already closed by pinning the
resolvers.

**The rule to carry forward: before trusting a success criterion, verify the system emits that event at
all.** Every downstream conclusion here — including a written claim about a third party — rested on one
unverified assumption about which event means what, and no test, build or type could see it. The verdict
came from the recorded evidence line "WhatsApp server ack: never arrives — on every number", which was
never a measurement of WhatsApp; it was a measurement of our own detector, which could not fire.

<!--جديد-->

### الشكلُ السادسَ عشر — **اسمٌ يُبحث عنه نصّاً، ونداءٌ بمفتاحٍ متغيّر** (2026-08-25)

**البحثُ عن اسمِ مفتاحٍ في الشجرة لا يجد من ينادي به متغيّراً ولا عضوَ
تعداد.** فالخلفيةُ تسأل `settings_service.is_feature_enabled(session, country,
key)`، و`key` عضوٌ من `FeatureKey` أو قيمةٌ تأتي من خريطة — **فلا يقع على
موضعِ النداء بحثُ نصٍّ عن `"tips_enabled"` أبداً**، ويعود البحثُ بصفرٍ عن مفتاحٍ
له قارئٌ عامل.

**فكلُّ حكمٍ على مفتاحٍ بالمسح النصّيِّ ظنّ. والمقياسُ نداءُ المسار الحيِّ:**
يُطفأ المفتاح، ويُنادى المسارُ الذي يُفترض أنه يحرسه، ويُقارن الجوابُ كلُّه بما
كان — فرقٌ مسمّى أو لا شيء.

**والصفرُ ليس نفياً في الاتجاهين**: بحثٌ نصّيٌّ يعود بصفرٍ لا يعني «بلا قارئ»،
وقياسٌ حيٌّ واحدٌ يعود بـ«لا فرق» لا يعني «بلا باب» — فقد يكون على المسار
**فحصان، الأولُ منهما يرفض بالرمز نفسِه فيستر الثاني**.

**والكلفةُ مقيسةٌ لا مقدَّرة** (`STATE.md`, 2026-08-25): من أربعةٍ وعشرين
مفتاحاً في هذا المشروع، أعطى المسحُ النصّيُّ **«صفرَ قارئ» لستّةٍ** —
`tips_enabled` · `next_instruction_enabled` · `pricing_writes_enabled` ·
`withdrawal_payout_enabled` · `driver_referrals_enabled` ·
`rider_referrals_enabled` — **ولكلٍّ منها قارئٌ حقيقيٌّ ظهر بالقياس الحيّ**.
**فربعُ الجدول كان سيُكتب كذباً** لو قُرئ من الشجرة.

**وهو صنفٌ لا واقعة**: كلُّ استدلالٍ يقوم على «لم أجد الاسم» يحمل العلّةَ
نفسَها — نداءٌ بمتغيّر، أو باسمٍ مركَّب، أو عبر خريطةٍ من قيمةٍ إلى مفتاح.
<!--/جديد-->
<!--جديد-->

### متغيّرٌ واحدٌ في كلِّ مرّة — لا فعلان يمسّان سطحاً واحداً في يوم (2026-08-25)

**لا يُفعل فعلان يمسّان السطحَ نفسَه في يومٍ واحد.**

فإن ظهر عطبٌ بعدهما، **لا يُعرف أيُّهما سببُه**. والعودةُ تكون عن الاثنين معاً،
**فلا يُتعلَّم أيُّهما كان** — ويُعاد الفعلان يوماً آخرَ بالجهل نفسِه.

**والمقياس**: بعد كلِّ فعل، **يُقاس أثرُه وحدَه على شجرةٍ هادئة**. ثمّ الفعلُ
التالي.

**مثالُها اليوم**: النشرُ يرفع الشيفرة، وتبديلُ `jwt_secret` **يُسقط كلَّ
الجلسات القائمة** — مقيسٌ لا مفترَض: `_create_token` واحدٌ للوصول والتجديد،
و`decode_token` يتحقّق بالسرِّ نفسِه، فيفشل كلُّ توكنٍ قائمٍ عند أوّل طلب.
**ولو وقعا معاً ثمّ عجز أحدٌ عن الدخول، لم يُعرف أهو النشرُ أم التبديل.**
فيُنشر وحدَه ويُقاس، ثمّ يُبدَّل السرُّ في يومٍ منفصل.

**وهي أختُ «عطبان يستر أحدهما الآخر»** (`GUARDS.md`) — تلك في العطب، وهذه في
الفعل. **وقد وقع فيها هذا الأسبوعُ مرّتين مقيستين**: `wallet_enabled` يستره
`wallet_transfer_enabled` على المسار نفسِه فيُقرأ «لا باب» كذباً؛ وفحصٌ أوّلُ
يستر ثانياً في `check:money-visible` فيمرّ الحقلُ أخضر.
<!--/جديد-->
<!--جديد-->

### القياسُ الصادقُ لا يأذن بفعلٍ خارج نطاقه (2026-08-25)

**قياسٌ صادقٌ في نطاقه يُقرأ إذناً بفعلٍ لا يقيسه** — وهو الشكلُ الثالثَ عشر
(*حارسٌ صادقٌ تُوسَّع دعواه فوق نطاقه*) في ثوب **فعلٍ** لا دعوى.

**والشرطُ نفسُه يُكتب ناقصاً**: «إن كان صفراً فاحذف» — والصفرُ صادق، **والحذفُ
يمحو ما لم يدخل القياسَ أصلاً**.

**ومثالُه مقيسٌ في اليوم نفسِه**: رقعةٌ محفوظةٌ قِيست بالسؤال «كم سطراً مضافاً
فيها لا أثرَ له في التاريخ؟» فكان الجواب **صفراً من ١٢٣١ سطراً** — قياسٌ صحيحٌ
تامّ. **لكنّ ١٧٫٨ من ١٨ ميغابايت في المجلّد لم تكن أسطراً**: حزمتان ثنائيّتان
لا نسخةَ لهما في أيِّ إصدار. **فصفرُ سطرٍ ضائعٍ ليس صفرَ شيءٍ ضائع.**

**فالقاعدة**: قبل فعلٍ لا رجعةَ فيه بناءً على قياس، يُسأل **ما الذي لم يدخل
القياس؟** — لا **ما الذي قاله**. ومن وجد شيئاً خارجه **يقف ويعرض**، ولا يُكمل
لأن الشرطَ المكتوبَ تحقّق حرفياً.
<!--/جديد-->

<!--جديد-->
### وللعائلة وجهٌ خامس — **حاويةٌ تخدم `dist` والمصدرُ يتغيّر تحتها** (قِيس 2026-08-26)

**العائلةُ الأربعةُ في `CLAUDE.md`** — `restart` يُبقي الصورة، وتجسيرٌ لا يعبره
inotify، و`run` يرث سياسةَ إعادة، و`uvicorn --reload` لا يعبر تجسير ويندوز —
**كلُّها تجعل الحاويةَ تبدو كأنها فعلت ما طلبتَ وقد فعلت غيرَه**. **وهذا
خامسُها، وهو أهدؤها صوتاً**: الحاويةُ **سليمةٌ تماماً**، والمصدرُ **جديدٌ
تماماً**، **ولا علاقةَ بينهما أصلاً**.

**فحاوياتُ الأسطح الثلاثة تشغّل `npx vite preview`** — لا `npm run dev`.
و`preview` **يخدم `dist` المبنيَّ**، فتعديلُ المصدر لا يبلغه حتى يُعاد البناء.
**و`docker-compose.yml` يقول `npm run dev`**، فمن قرأ الملفَّ ظنّ خادمَ تطوير؛
**والطاقمُ مرفوعٌ بـ`docker-compose.tunnel.yml`** وهو **يستبدل `command:`
كاملاً**. **فالملفُّ الذي تقرؤه ليس الملفَّ الذي يحكم.**

**وما يجعله فخّاً بعينه**: كلُّ ما تفعله يبدو ناجحاً. المصدرُ يُكتب، والأنواعُ
تمرّ، والحاويةُ تعمل، والصفحةُ تُفتح — **ثم لا يتغيّر شيء**. ولو كان الإصلاحُ
مما لا يُرى بالعين لَقيل «تمّ» وهو لم يبلغ الحزمةَ قطّ.

**وقد أنقذت اللقطةُ**: قُيس «قبل» بالعين، وأُصلح، وقُيس «بعد» — **فكانت
اللقطتان متطابقتين حرفاً بحرف**. والتطابقُ هو ما فتح التحقيق، ولولاه لَأُعلن
إصلاحٌ لم يقع.

> **والقاعدة**: **اسأل ما الذي تشغّله الحاويةُ فعلاً** —
> `docker inspect … --format '{{json .Config.Cmd}}'` — **لا ما يقوله ملفُّ
> compose الأساسيّ**. وهي «اقرأ من الشيء الذي يحكم» نفسُها، في ثوبٍ خامس.
>
> **ومعه أخٌ أصغرُ قِيس في اليوم نفسِه**: `node_modules` الحاويةِ **مجلَّدٌ
> مسمّى** لا جزءٌ من التجسير، **فتثبيتُ المضيف لا يبلغها**. تابعٌ جديدٌ
> يحتاج `docker exec … npm install` **ثم** إعادةَ تشغيل.


### إنذارٌ ينادي من لا يسمع — **أخطرُ من إنذارٍ صامت** (قِيس 2026-08-28)

**الصامتُ لا يدّعي شيئاً؛ وهذا يدّعي أنه بلّغ.** والفرقُ ليس فلسفياً: هذا
**يستهلك مفتاحَ التكرار** ثمّ يسكت المدّةَ كلَّها، فيقرأ من ينظر إلى Redis
«أُنذر» ويقرأ من ينظر إلى الصندوق «لا شيء» — **وكلاهما ينظر إلى نصف الحقيقة**.

**والمقيس**: مهمّةُ النسخ الاحتياطي تعمل كلَّ ربع ساعة، **و٣٤٠ نسخةً فشلت في
خمسة أيام** وسُجّل فشلُها بخطئه. والإنذارُ **عمل**: `alerts.any = True`،
و`stale_hours = 122`، **ومفتاحُ `backup:alerted` مضبوطٌ في Redis بـTTL حيّ**.
ثمّ نادى `notify_user` — **وهو بابُ دفعٍ وحدَه**: يعود فوراً بلا عقد FCM،
ويعود فوراً بلا أجهزةٍ مسجَّلة، **ولا يكتب صفَّ صندوقٍ أبداً**.

**والمُنذَرون مشرفون، واللوحةُ لا تسجّل أجهزةً بالتصميم** — مكتبٌ لا يستقبل
Push. **فالبابُ كان مغلقاً بنيةً لا عرَضاً**، وكلُّ إنذارٍ سقط فيه.

> **وثلاثةُ أشياءَ تجعل هذا الشكلَ يعيش طويلاً:**
>
> 1. **الكودُ يبدو صحيحاً**: حلقةٌ على المشرفين، ونداءُ إشعارٍ، و`commit`.
>    **والاستعلامُ يجد ثلاثةَ مشرفين فعلاً** — قِيس.
> 2. **والتوثيقُ يشهد بما لا يفعله**: نصُّ الدالّة يقول «يصل صندوقَ كلِّ
>    `admin` — **فلا يعتمد التنبيهُ على أن يفتح أحدٌ الشاشة**»، **وهي تنادي
>    باباً لا يكتب صندوقاً**. فمن قرأ النصَّ اطمأنّ.
> 3. **ومفتاحُ التكرار يزوّر شهادةَ الإرسال**: وجودُه يُقرأ «بُلِّغ»، وهو لا
>    يقول إلا «مرّ الفرعُ من هنا».

**والقاعدة**: **بابُ الإشعار يُختار بمن يستقبل لا بما يبدو أعمّ.** ما يجب أن
يبقى أثرُه يمرّ بالبابِ الذي يكتب الصندوقَ أولاً ثمّ يدفع (`_safe_notify`)،
**وما يُدفع وحدَه يُقال في نصّه إنه يُدفع وحدَه**.

**ولا يُقاس بأن الفرعَ عمل، بل بأن الأثرَ وُجد**: القياسُ الصادقُ هنا هو
**عدُّ صفوف الصندوق قبل وبعد** — كان `0 → 0`، وصار `0 → 3`.

<!--/جديد-->

<!--جديد-->
## نصفُ رفعةٍ أخطرُ من رفعةٍ لم تبدأ (قِيس 2026-08-28)

**رفعةٌ قُتلت عمليتُها من خارجها** في منتصف بوّابة الرفع: الكودُ سُحب،
**والواجهاتُ الثلاثُ بُنيت وصارت حيّةً** لأن `dist` مربوطٌ من القرص فلا يحتاج
إعادةَ حاوية — **والخلفيةُ والعاملُ لم يُعادا**، فبقيا يحملان ما قرآه يومَ
إقلاعهما.

**فصارت مسارات المال نصفين**: واجهةٌ تعرف إعلانَ المحفظة وخلفيةٌ لا تعرفه.
**وهو أخطرُ من قديمٍ متّسق**: القديمُ المتّسق يعمل، والنصفان يفترقان في
موضعٍ لا يشكو فيه شيء.

**وطريقُ الرجوع نفسُه كان يطيل الانقسام** (حجّةُ المالك): الرجوعُ يقتضي إعادةَ
بناء الواجهات الثلاث إلى القديم — **فعلٌ بحجم الإكمال وأثرُه إبقاءُ الانقسام
دقائقَ أطول**. فأُكمل ولم يُرجَع.

### وثلاثةُ أشياءَ تعلَّمت في الطريق

**١) عمليةٌ تنجو من قتل ما أطلقها.** `deploy.sh` بقي حيّاً بعد قتل مهمّته،
**وأنبوبُ مخرجه ذهب** — فكان سيأخذ النسخةَ ويعيد الحاويات **بلا قارئ**. وهي
عائلةُ «قتلُ العميل لا يقتل ما أطلقه» المسجَّلةُ للحاويات، **في ثوب صدفة**.
**فالسجلُّ يُكتب في ملفٍّ لا في أنبوب** — ما بقي في الملفّ نجا، وما كان في
الأنبوب ضاع.

**٢) ولا يُحكم بانقطاع قناةٍ حكمَ بوّابة.** ظهرت ثلاثُ `ssh: Unknown error`
فبدت وقوفاً — **والبناءُ كان قد تمّ** (`BUILT=3`). **وعلامةُ الوقوف نصٌّ
يُكتب**: البابُ يكتب سببَه وطريقَ رجوعه في كلِّ `die`، **فصفرُ نصٍّ يعني أنه
لم يحكم**، لا أنه سكت عن حكم.

**٣) و`grep` داخل الحاوية ليس شهادةَ العملية الحيّة.** المصدرُ مربوطٌ من
القرص، **فأيُّ عمليةٍ جديدةٍ تقرأ الجديدَ وتشهد بالسلامة** والعمليةُ الحيّةُ
تحمل القديم. **والشهادةُ الصادقةُ أن يُسأل الخادمُ عمّا لا يعرفه إلا الجديد**:
قُرئ `openapi.json` **من النفق** فأعلن `AdjustmentCreate` بحقل `wallet` —
وهو حقلٌ لم يكن قبل اليوم.
<!--/جديد-->

<!--جديد-->
## ثابتٌ صادقٌ بحالةٍ واحدة يكذب حين تصير الحالتان (قِيس 2026-08-29)

`subscriptions.activate_paid_order` كان يختم **`payment_method = PaymentMethod.CARD`
ثابتاً في الشيفرة** — **وكان صادقاً**: مسارُ البطاقة كان وحدَه من ينادي هذه
الدالّة، فالثابتُ يصف الواقعَ بدقّة.

**ثمّ صار كليكُ اليدويُّ ينادي الدالّةَ نفسَها** — وهو الصوابُ (بيتٌ واحدٌ
بغرضٍ معلَن، لا بابٌ ثالث). **فانقلب الثابتُ من وصفٍ صحيحٍ إلى كذبٍ صامت**:
اشتراكٌ دُفع بكليك يُكتب في صفّه «بطاقة»، **ويُقرأ كذلك في كلِّ تقريرٍ بعده**.

**وخُبثُه أنه لا يُخطئ في شيء**: لا استثناءَ يُرمى، ولا حارسَ يصيح، والاشتراكُ
يُفعَّل صحيحاً بمبلغه الصحيح — **والحقلُ الوحيدُ الكاذبُ حقلٌ لا يقرؤه أحدٌ
اليوم**، ويقرؤه من يسأل بعد شهرٍ «بم يدفع الكباتن؟» فيجيب: بالبطاقة كلُّهم.

**والعلاجُ سطر**: يُمرَّر ما كان ثابتاً، **والافتراضُ يبقى ما كان** فلا ينكسر
النداءُ القديم. ومقيسٌ بعده: `amount_paid=1.200 · payment_method=cliq · active`.

### والقاعدةُ المستخلَصة

**كلُّ ثابتٍ في دالّةٍ مشتركةٍ هو دعوى «لا يوجد إلا هذا»** — تُراجَع **يومَ
يصير للدالّة نادٍ ثانٍ**، لا يوم كُتبت.

> **وأينَ يُبحث عنها**: قيمةٌ مكتوبةٌ حرفياً في دالّةٍ عامّة تصف **من ناداها**
> لا **ما تفعله** — مثل الطريقة والقناة والمصدر والدور. **وهي أخفُّ ما يُمسك
> بالاختبارات** لأن الاختبارَ يمرّ: القيمةُ صحيحةٌ للمسار الذي يفحصه.
<!--/جديد-->
