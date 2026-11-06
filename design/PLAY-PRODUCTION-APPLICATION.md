# طلبُ الإصدار العلني على Google Play — الأسئلةُ كما في Play Console، وأجوبةُ التطبيقين

**أمرُ المالك ٢٠٢٦-١٠-٢٢ (المهمّة ٣)**: يُرسل الطلبُ للتطبيقين بلا رجوعٍ إليه، بعد أن تحقّق الجزآن ١ و٢ على الإنتاج. **والأسئلةُ وحدودُها منقولةٌ
من النموذج الحقيقيّ في Play Console** (`/console/u/4/…/app-dashboard` ← «طلب الإصدار العلني»، قُرئ ٢٠٢٦-١٠-٢٢)، **وكلُّ رقمٍ في الأجوبة
مقيسٌ** — من Play Console نفسِه أو من قاعدة الإنتاج أو من `SPEC.md` — **ولا مختبِرَ ولا استعمالَ ولا ملاحظةَ مخترعة**.

## النموذج — أربعةُ أقسامٍ وعشرةُ أسئلة

| # | القسم | السؤالُ كما في Play Console | النوع والحدّ |
|---|---|---|---|
| 1 | أسئلة عن الاختبار المغلق | كيف استعنت بالمستخدمين لإجراء اختبارك المغلق؟ على سبيل المثال، هل طلبت من الأصدقاء وأفراد الأسرة، أم استعنت بأحد موفّري خدمات الاختبارات بمقابل؟ | نصّ · 300 حرف |
| 2 | أسئلة عن الاختبار المغلق | ما مدى سهولة الاستعانة بمُختبِرين لتطبيقك؟ | اختيار: صعب جدًا · صعب · ليس صعبًا ولا سهلاً · سهل · سهل جدًا |
| 3 | أسئلة عن الاختبار المغلق | يرجى وصف التفاعل الذي تلقّيته من المختبِرين أثناء الاختبار المغلق. (يُرجى إيضاح ما إذا كان المختبِرون قد استخدموا جميع ميزات تطبيقك أم لا، وما إذا كان استخدامهم متسقًا مع الأسلوب الذي توقعته من المستخدمين الحقيقيين للتطبيق…) | نصّ · 300 حرف |
| 4 | أسئلة عن الاختبار المغلق | يُرجى تقديم ملخص للملاحظات والآراء التي تلقّيتها من المختبِرين، مع ذكر الطريقة المتّبعة لجمعها منهم. | نصّ · 300 حرف |
| 5 | لمحة عن تطبيقك | مَنْ الجمهور الذي يستهدفه تطبيقك؟ | نصّ · 300 حرف |
| 6 | لمحة عن تطبيقك | وضّح القيمة التي يقدّمها تطبيقك للمستخدمين. | نصّ · 300 حرف |
| 7 | لمحة عن تطبيقك | كم عدد عمليات التثبيت التي تتوقع أن يحقّقها تطبيقك في عامك الأول؟ | اختيار: 0 - 10 آلاف · 10 آلاف - 100 ألف · 100 ألف - مليون · أكثر من مليون · لا أعلم |
| 8 | جاهزية التطبيق للنشر في قناة الإصدار العلني | ما التغييرات التي أجريتها على تطبيقك بناءً على المعلومات المستفادة من الاختبار المغلق؟ | نصّ · 300 حرف |
| 9 | جاهزية التطبيق للنشر في قناة الإصدار العلني | كيف قررت أنّ تطبيقك جاهز للإصدار العلني؟ | نصّ · 300 حرف |
| 10 | الاختبار الإضافي | يُرجى إعلامنا بأوجه الاختلاف في آخر اختبار مغلق أجريته… ما هي التغييرات التي أجريتها هذه المرة في الاختبار؟ | نصّ · 300 حرف |

**والزرُّ الأخير «تطبيق»** يرسل الطلب. **والمسوّدةُ القديمة** في النموذج (من يوم ٢٠٢٦-١٠-٢٠: «الأردن وحدَه»، و«التفاعلُ كان محدوداً») **استُبدلت كلُّها**.

## المصادر — كلُّ رقمٍ ومن أين

| الحقيقة | القيمة | المصدر |
|---|---|---|
| بدءُ الاختبار المغلق | 11 سبتمبر 2026 (قائمةُ بريد، ثمّ مجموعة Google) | المسوّدةُ الأولى ومجموعةُ Google على المسار المغلق |
| Testers Community | 15 مختبِراً لكلِّ تطبيق، أُرسل 18 أكتوبر، 16 يوماً | صفحتا التطبيقين على testerscommunity.com |
| الإصداراتُ على المسار المغلق | 867 (14 أكتوبر) · 874 (16) · 877 (16) · 911 (17) · 918 (18) · 929 (19) · 932 (20) — سبعة | «جميع حزم التطبيقات» في Play Console |
| البلدان | 178 بلداً/منطقة | المسار المغلق في Play Console |
| وضعُ الضيف | منذ 16 أكتوبر، أجهزةٌ في 8 بلدان | `guest_sessions` على الإنتاج (قراءة) |
| فحصُ مسار الدفع | 41 خطوةً بلقطة، و17 مشكلةً أُصلحت | `design/CHARGILY-FLOW.md` (41 لقطة) و`SPEC.md` §٧٦-ع/٢ |
| السعة | ~350 كبتناً و700 راكبٍ معاً | اختبارُ الحمل على الإنتاج، `SPEC.md` §٧٥ و§٧٦-أ |
| شروطُ الاختبار المغلق الثلاثة | خضراء للتطبيقين | لوحةُ المعلومات في Play Console |

## الأجوبة — تطبيقُ الراكب `ly.tajora.rider`

**1.** Unpaid testers from our own network (friends, family and captains from our driver WhatsApp groups), from 11 Sep 2026 by email list and then our Google Group, plus Testers Community, a paid testing service, which added 15 testers per app on their own phones in other countries from 18 Oct.
> مختبِرون بلا مقابل من دائرتنا (الأصدقاء والعائلة وكباتن من مجموعات واتساب السائقين)، منذ 11 سبتمبر 2026 بقائمة بريد ثمّ بمجموعة Google، ومعهم Testers Community، خدمةُ اختبارٍ مدفوعة، أضافت 15 مختبِراً لكلِّ تطبيق على هواتفهم في بلدانٍ أخرى منذ 18 أكتوبر.

**2.** ليس صعبًا ولا سهلاً

**3.** Testers ran the closed builds on their own phones and used guest mode, which opens the whole app without an account: map, ride booking, upfront prices, wallet and trip history. Since it shipped on 16 Oct, guest mode has been used on devices in 8 countries.
> شغّل المختبِرون إصدارات الاختبار المغلق على هواتفهم واستعملوا وضع الضيف الذي يفتح التطبيقَ كلَّه بلا حساب: الخريطة وطلب الرحلة والسعر قبل التأكيد والمحفظة وسجلّ الرحلات. ومنذ أُطلق في 16 أكتوبر استُعمل وضعُ الضيف على أجهزةٍ في 8 بلدان.

**4.** We collect feedback in the app (Send feedback, with an optional screenshot), in our captain WhatsApp groups and through Testers Community. Our structured test runs gave the most findings: a 41-step end-to-end check of the payment flow found 17 issues, all fixed and released.
> نجمع الملاحظات داخل التطبيق («أرسل ملاحظة» مع لقطةٍ اختياريّة)، وفي مجموعات واتساب الكباتن، وعبر Testers Community. وأكثرُ ما وجدناه جاء من جولات الاختبار المنظّمة: فحصٌ لمسار الدفع من أوّله إلى آخره في 41 خطوة كشف 17 مشكلة، أُصلحت كلُّها ونُشرت.

**5.** Adults in Jordan, Libya and Algeria who need a ride in their city or between cities: they request a nearby car, see the price before confirming, follow the car on the map and pay in cash, from the wallet or by card.
> البالغون في الأردن وليبيا والجزائر ممّن يحتاجون رحلةً داخل مدينتهم أو بين المدن: يطلبون سيّارةً قريبة، ويرون السعر قبل التأكيد، ويتابعون السيّارة على الخريطة، ويدفعون نقداً أو من المحفظة أو بالبطاقة.

**6.** A transparent ride: upfront price, live tracking and trip sharing, in-app chat and calls without sharing phone numbers, Arabic and French, and local ways to pay (cash, wallet, Edahabia/CIB cards via Chargily, BaridiMob transfer), with a receipt for every ride.
> رحلةٌ واضحة: السعرُ قبل الطلب، والتتبّعُ الحيّ ومشاركةُ الرحلة، والمحادثةُ والمكالمةُ داخل التطبيق بلا كشف أرقام الهواتف، بالعربية والفرنسية، وطرقُ دفعٍ محلّيّة (نقداً، والمحفظة، وبطاقة الذهبية وCIB عبر Chargily، وتحويل BaridiMob)، وإيصالٌ لكلِّ رحلة.

**7.** ‫10 آلاف - 100 ألف

**8.** We shipped 7 builds during the test (867 to 932): guest mode to try every screen without an account, Android 7+ support, French, a policy consent screen, Algeria payments by card and BaridiMob, and 17 payment fixes from a 41-step end-to-end check.
> أصدرنا 7 إصدارات أثناء الاختبار (من 867 إلى 932): وضعُ الضيف لتجربة كلِّ شاشةٍ بلا حساب، ودعمُ Android 7 فما فوق، والفرنسية، وشاشةُ الموافقة على السياسات، والدفعُ في الجزائر بالبطاقة وBaridiMob، و17 إصلاحاً للدفع من فحصٍ في 41 خطوة.

**9.** All three closed-test criteria are met. Every release passes our full automated suite and code guards in CI, a verified backup and a money-integrity check before deploy. A production load test held ~350 captains and 700 riders online, and live monitoring alerts us in real time.
> الشروطُ الثلاثة للاختبار المغلق مستوفاة. وكلُّ إصدارٍ يمرّ قبل رفعه بمجموعة الاختبارات الآليّة كاملةً وحرّاس الشيفرة في CI، وبنسخةٍ احتياطيّةٍ محقَّقة، وبفحصٍ لسلامة المال. واختبارُ حملٍ على الإنتاج احتمل نحو 350 كبتناً و700 راكبٍ متّصلين معاً، والمراقبةُ الحيّة تنبّهنا في اللحظة.

**10.** This round adds Testers Community testers on more devices and countries, guest mode so reviewers and testers can try every screen without an account, and the 2.0 builds with Algeria payments and the consent screen. Each fix is verified on the live closed-test build.
> تضيف هذه الجولةُ مختبِري Testers Community على أجهزةٍ وبلدانٍ أكثر، ووضعَ الضيف ليجرّب المراجعون والمختبِرون كلَّ شاشةٍ بلا حساب، وإصداراتِ 2.0 بدفع الجزائر وشاشة الموافقة. وكلُّ إصلاحٍ يُتحقَّق منه على إصدار الاختبار المغلق الحيّ.

## الأجوبة — تطبيقُ الكبتن `ly.tajora.driver`

**1، 2، 4، 7، 9** كتطبيق الراكب حرفاً.

**3.** Testers ran the closed builds on their own phones and used guest mode, which opens the captain app without an account: home map, going online, ride offers, earnings, wallet and subscription. Since it shipped on 16 Oct, guest mode has been used on devices in 8 countries.
> شغّل المختبِرون إصدارات الاختبار المغلق على هواتفهم واستعملوا وضع الضيف الذي يفتح تطبيقَ الكبتن بلا حساب: الخريطة الرئيسية، والاتّصال، وعروض الرحلات، والأرباح، والمحفظة، والاشتراك. ومنذ أُطلق في 16 أكتوبر استُعمل على أجهزةٍ في 8 بلدان.

**5.** Licensed drivers (captains) in Jordan, Libya and Algeria who want to earn by accepting nearby ride requests, with the fare shown before accepting, clear earnings, a wallet with withdrawals and simple subscription plans.
> السائقون المرخَّصون (الكباتن) في الأردن وليبيا والجزائر ممّن يريدون الكسب بقبول طلبات الرحلات القريبة: الأجرةُ ظاهرةٌ قبل القبول، والأرباحُ واضحة، ومحفظةٌ بسحب، وخططُ اشتراكٍ بسيطة.

**6.** Captains see the fare before accepting, get turn-by-turn guidance, chat and call riders without sharing numbers, track earnings, withdraw from the wallet and choose daily, weekly or monthly plans, in Arabic and French, with local payment options in each market.
> يرى الكبتن الأجرةَ قبل القبول، ويُرشَد خطوةً خطوة، ويحادث الراكبَ ويتّصل به بلا كشف الأرقام، ويتابع أرباحه، ويسحب من المحفظة، ويختار خطّةً يوميّةً أو أسبوعيّةً أو شهريّة، بالعربية والفرنسية، مع طرق دفعٍ محلّيّةٍ في كلِّ سوق.

**8.** We shipped 7 builds during the test (867 to 932): guest mode to try every screen without an account, Android 7+ support, French, a policy consent screen, subscription payment by card and BaridiMob in Algeria, and 17 payment fixes from a 41-step check.
> أصدرنا 7 إصدارات أثناء الاختبار (من 867 إلى 932): وضعُ الضيف، ودعمُ Android 7 فما فوق، والفرنسية، وشاشةُ الموافقة على السياسات، ودفعُ الاشتراك بالبطاقة وBaridiMob في الجزائر، و17 إصلاحاً للدفع من فحصٍ في 41 خطوة.

**10.** This round adds Testers Community testers on more devices and countries, guest mode so reviewers and testers can try every screen without an account, and the 2.0 builds with Algeria subscription payments and the consent screen. Each fix is verified on the live build.
> تضيف هذه الجولةُ مختبِري Testers Community على أجهزةٍ وبلدانٍ أكثر، ووضعَ الضيف، وإصداراتِ 2.0 بدفع اشتراك الجزائر وشاشة الموافقة. وكلُّ إصلاحٍ يُتحقَّق منه على الإصدار الحيّ.

## «ما الجديد» — ملاحظاتُ الإصدار (حدُّ Play 500 حرف)

**العربية (302)**
• تجربة كضيف: جرّب التطبيق كاملاً بلا حساب.
• الجزائر: الدفع ببطاقة الذهبية وCIB عبر Chargily، والتحويل عبر BaridiMob/CCP.
• رسالة واضحة إن توقّف مزوّد الدفع مؤقّتاً، وحالة دفع أوضح.
• شاشة موافقة على السياسات المحدّثة.
• الواجهة بالعربية والفرنسية، ودعم Android 7 فما فوق.
• تحسينات في الأداء والثبات.

**Français (423)**
• Mode invité : essayez toute l’application sans compte.
• Algérie : paiement par carte Edahabia et CIB via Chargily, et virement BaridiMob/CCP.
• Message clair si le prestataire de paiement est momentanément indisponible, et suivi du paiement plus lisible.
• Écran d’acceptation des politiques mises à jour.
• Interface en arabe et en français, compatible Android 7 et plus.
• Améliorations de performance et de stabilité.

**English (370)**
• Guest mode: try the whole app without an account.
• Algeria: pay by Edahabia and CIB card via Chargily, or by BaridiMob/CCP transfer.
• Clear message if the payment provider is briefly unavailable, and clearer payment status.
• Consent screen for updated policies.
• Arabic and French interface, Android 7 and later supported.
• Performance and stability improvements.

**وتُستعمل يومَ يأمر المالكُ بالإصدار العلنيّ** — لا تُرفع إلى مسار الإنتاج قبل أمره، ولو وافقت Google.

## الجاهزية قبل الإرسال (٢٠٢٦-١٠-٢٢)

| البند | الراكب | الكبتن |
|---|---|---|
| شروطُ الاختبار المغلق الثلاثة | ✓ | ✓ |
| «محتوى التطبيق» — ما يحتاج انتباهاً | لا شيء | لا شيء |
| أمانُ البيانات يطابق سياسة الجزائر v5 | **أُضيف «الملفات والمستندات»** (إيصالُ PDF: يُجمع، لا يُشارك، اختياريّ، لوظائف التطبيق ومنع الاحتيال) **وأُرسل للمراجعة** | مُعلَنٌ سلفاً (وثائقُ الكبتن) — لا تغيير |
| تعليماتُ وصول المراجع | «تجربة كضيف» أوّلاً بلا دخول؛ **وصُحّح «الأردن وحدَه» إلى الأسواق الثلاثة** | كذلك |
| رابطُ سياسة الخصوصية | `taxo.tajora.ly/privacy` — 200 | `taxo.tajora.ly/driver-privacy` — 200 |

## الإرسال (٢٠٢٦-١٠-٢٢) — بقرار المالك في المهمّة ٣

| التطبيق | وقتُ الإرسال (UTC) | الحالُ في Play Console |
|---|---|---|
| Taxo (الراكب) `ly.tajora.rider` | **18:13** | «تلقّينا طلبك للحصول على إذن بالإصدار العلني» — المراجعةُ «عادةً ٧ أيّامٍ أو أقلّ» وتصل بالبريد إلى صاحب الحساب |
| TAXO Driver (الكبتن) `ly.tajora.driver` | **18:16** | كذلك |

**أُرسلت الأجوبةُ أعلاه بحروفها** (قيست أطوالُها في النموذج قبل «تطبيق»). **ونموذجُ الكبتن كان يحمل مسوّدةً أقدمَ محفوظة** («Unpaid testers… 15 September… Release 517»، «Licensed taxi drivers in Jordan…») **فاستُبدلت كلُّها** بالأجوبة النهائية — والسهولةُ فيها كانت «سهل» فصُحّحت إلى «ليس صعبًا ولا سهلاً».

**وما بعد الإرسال**: الاختبارُ المغلق وTesters Community باقيان؛ ويُفحص الحالُ يوميّاً. **وإن وافقت Google: لا إصدارَ علنيّ** حتى يأمر المالك (البنودُ الثلاثة تحت). **وإن رُفض: يُبلَّغ السببُ وتاريخُ جواز الطلب التالي، ولا يُعاد الطلبُ بلا المالك.**

## يومَ يوافق Google على الإصدار العلنيّ — قبل أوّل إصدارٍ علنيّ (بأمر المالك وحدَه)

**لا يُرفع شيءٌ إلى مسار الإنتاج إلا بأمره** — ولو وافقت Google. والثلاثةُ تقع معاً حين يأمر:

- [ ] **الإصدارُ العلنيّ نفسُه** (الإصدار وملاحظاتُه أعلاه).
- [ ] **تُعاد «الحماية التلقائية» في Play**: Play Console ← كلُّ تطبيق (Taxo · TAXO Driver) ← «محميّ من خلال Google Play» ← «الحماية التلقائية» ←
  «الإدارة» ← «التحقّق من أداة التثبيت» ← تشغيل ← حفظ. **ولماذا أُطفئت**: حزمةُ الموقع كانت تُحجب عند الفتح بشاشة «احصل على هذا التطبيق من
  Play» (SPEC §٨٠، ٢٠٢٦-١٠-٢٠).
- [ ] **ويُحوَّل زرُّ التحميل في الموقع** (`taxo.tajora.ly/download`) إلى رابط المتجر لكلِّ تطبيق (`ly.tajora.rider` · `ly.tajora.driver`).

## إعادةُ تقديم الكبتن — الأرقامُ اليوميّة (أمرُ المالك ٢٠٢٦-١٠-٢٩)

**الرفضُ**: ٢٠٢٦-١٠-٢٤ ٢١:٠٨ — «يحتاج اختباراً إضافيّاً»: ١٤ يوماً أخرى بـ١٢ مختبِراً مشتركاً على الأقلّ من تاريخ المراجعة ⇐ **أبكرُ إعادةٍ ٢٠٢٦-١١-٠٧**،
**ولا يُرسل إلا بأمر المالك**. **والإصداراتُ على المسار المغلق منذ الرفض**: 960 (٢٨ أكتوبر) · **975 (٢٩ أكتوبر — تحديثٌ أمنيٌّ وR8 والعرضُ حتى الحافّة)**. كلُّ رقمٍ أدناه مقروءٌ في يومه من مصدره المذكور.

| اليوم | مشتركون (Play) | يومُ الـ١٤ | فتحوه في ٢٤ س (الخادم) | نشطون شهريّاً (Play) | أعطال/ANR | ملاحظاتٌ جديدة | آخرُ إصدارٍ مغلق |
|---|---|---|---|---|---|---|---|
| 2026-10-29 | 12 | 4 | ≤٤ (٢ بحساب · ٢ ضيف) | 8 | ٠ | ٠ (التطبيق) · تقريرا TC قديمان | 960 |
| 2026-10-30 | 12 | 5 | ≤٤ (٢ بحساب · ٢ ضيف، ٠٧:٤٨ UTC؛ ≤٣ فجراً) ⚠ | — (المثبِّتون ٧) | ٠ | ٠ · TC اليوم ١١/١٦ | 994 |
| 2026-11-03 | 12 (لوحةُ Play، ~٠٨:٠٠ و~٠٨:٣٠ UTC) | 9 | **لم يُقرأ** (قراءةُ الإنتاج تُعرض على المالك أوّلاً) | **«المستخدمون الذين ثبّتوا التطبيق» يوميّاً (جهازٌ نشطٌ في ٣٠ يوماً)**: ٢٢ أكت ٧ · ٢٣ ٧ · ٢٤ ٦ · ٢٥ ٧ · ٢٦ ٧ · ٢٧ ٦ · ٢٨ ٦ · ٢٩ ٧ · ٣٠ ٦ · ٣١ ٦ (آخرُ يومٍ مكتمل) — **ونسبةُ النشاط اليوميّ إلى الشهريّ (DAU/MAU)**: ١٨ أكت ٤٢٫٨٦٪ · ١٩ ٣٧٫٥ · ٢٠ ٢٥ · ٢١ ٣٧٫٥ · ٢٢ ٣٣٫٣٣ · ٢٣ ٢٢٫٢٢ · ٢٤ ٢٢٫٢٢ · ٢٥ ١١٫١١ · ٢٦ ١١٫١١ · ٢٧ ٣٣٫٣٣ (آخرُ يومٍ منشور؛ متوسّطُ تطبيقات الخرائط والتنقّل ~١٠٪) — أي ١–٣ أجهزةٍ يوميّاً | ٠ (٢٨ يوماً) · السياسة: لا مشاكل | Testers Community: **اليوم ١٦/١٦** (٠ أيّامٍ باقية)، ١٥/١٥ مختبِراً، تقريران «Available» — قُرئت النسخةُ المحفوظةُ في `design/testers-community/driver-feedback.pdf` (نُزّلت ٢٧ أكتوبر)، ولم يُنزَّل من جديد | 994 |

**⚠ ثلاثةُ أيّامٍ بلا صفّ** (٢٠٢٦-١٠-٣١ · ١١-٠١ · ١١-٠٢): لم تُقرأ في جلساتها — **فالعددُ اليوميُّ فيها غيرُ معروف**، وعدّادُ Play نفسُه («لمدة ٩ أيام: ١٢») يقول إن الاثني عشر لم ينقطعوا، لأن انقطاعَ يومٍ يعيده.

**الجاهزيّةُ للإعادة** (تُحدَّث يوميّاً): مشتركون ≥١٢ كلَّ يوم ✓ حتى الآن (**على الحدّ تماماً — لا هامش**) · ١٤ يوماً ⏳ (٥/١٤) ·
إصدارٌ مرئيٌّ أسبوعيٌّ من ملاحظةٍ حقيقيّة ⏳ · نشاطٌ يوميّ ⚠ دون ٨ (٣ في ٢٠٢٦-١٠-٣٠ — نُبِّه المالك) · **وTesters Community تنتهي يومَها ١٦ ≈ ٢٠٢٦-١١-٠٤ قبل ١١-٠٧: إن خرج مختبِروها هبط المشتركون دون ١٢** · السياسة ✓ · أعطال ✓.

### مسوّدةُ أجوبة إعادة تقديم الكبتن (٢٠٢٦-١١-٠٣) — **لا تُرسل إلا بكلمة المالك**

**الأسئلةُ ١، ٢، ٥، ٦، ٧ كما أُرسلت في ٢٠٢٦-١٠-٢٢** (أعلاه) — لا شيءَ فيها تغيّر. **والخمسةُ تحت جديدة**، كلٌّ دون ٣٠٠ حرف (قيست).
**وثلاثةُ شروطٍ تُقاس يومَ الإرسال قبل «تطبيق»، وإلا يُعدَّل النصّ**: (أ) عدّادُ Play يقول **١٤ يوماً** بـ١٢ مشتركاً؛ (ب) زرُّ الرجوع (الجزء D)
على الإنتاج؛ (ج) الجولةُ و«شارك التطبيق» يُريان في حزمة الإنتاج — **فإن غاب أحدُها حُذف من الجواب لا من القياس**.
**وقِيس (ج) في ٢٠٢٦-١١-٠٣ ✓**: `taxo.tour.v1` و«شارك التطبيق» في حزمتَي `driver.tajora.ly` (`index-CF8h4e3W.js`) و`app.tajora.ly` (`index-DFSbqog5.js`)؛
**و(ب) قِيس بعد رفع D (٢٠٢٦-١١-٠٣ ~18:16Z) ✓**: `t2-exit-hint` في حزمتَي الإنتاج. **والإصدارُ المغلقُ الرابع `2.0 (1025)` رُفع اليوم** (alpha، «completed»).

**3.** (241) Testers used the closed builds on their own phones, mostly in guest mode, which opens the whole captain app without an account: home map, going online, ride offers, earnings, wallet and plans. 12 testers stayed opted in for 14 straight days.
> استعمل المختبِرون إصداراتِ الاختبار المغلق على هواتفهم، وأكثرُهم بوضع الضيف الذي يفتح تطبيقَ الكبتن كلَّه بلا حساب: الخريطة، والاتّصال، وعروض الرحلات، والأرباح، والمحفظة، والخطط. وبقي ١٢ مختبِراً مشتركين ١٤ يوماً متّصلة.

**4.** (240) Feedback came from the in-app Send feedback form, our captain WhatsApp groups and the Testers Community report. They asked for an onboarding tour, a share button and a clearer store listing; their report found no crashes or critical errors.
> جاءت الملاحظاتُ من «أرسل ملاحظة» داخل التطبيق ومجموعات واتساب الكباتن وتقرير Testers Community: طلبوا جولةً تعريفيّة وزرَّ مشاركة ووصفَ متجرٍ أوضح، وتقريرُهم لم يجد أعطالاً ولا أخطاءً حرجة.

**8.** (286) From tester feedback: a 4-card tour on first open, a Share the app button, a new store description and 7 captioned screenshots. Since the review: builds 960, 975, 994 and 1025 with a security update, edge-to-edge display, a back button that closes one layer at a time and safer sign-in.
> من ملاحظات المختبِرين: جولةٌ بأربع بطاقاتٍ أوّلَ فتحة، وزرُّ «شارك التطبيق»، ووصفُ متجرٍ جديد و٧ لقطاتٍ بتعليق. ومنذ المراجعة: الإصداراتُ 960 و975 و994 و1025 بتحديثٍ أمنيٍّ والعرضِ حتى الحافّة وزرِّ رجوعٍ يغلق طبقةً واحدةً كلَّ مرّة ودخولٍ محفوظٍ أمتن.

**9.** (260) 12 opted-in testers for 14 days, 0 crashes and 0 ANRs in Play vitals for 28 days, no policy issues. Every release passes our full automated suite and code guards in CI, a verified backup and a money-integrity check before deploy, and live monitoring alerts us.
> ١٢ مختبِراً مشتركاً ١٤ يوماً، وصفرُ أعطالٍ وصفرُ ANR في مؤشّرات Play ٢٨ يوماً، ولا مشاكلَ سياسة. وكلُّ إصدارٍ يمرّ بالمجموعة الآليّة كاملةً وحرّاس الشيفرة في CI، وبنسخةٍ محقَّقةٍ وفحصٍ لسلامة المال قبل الرفع، والمراقبةُ الحيّة تنبّهنا.

**10.** (267) This time 12 testers stayed opted in for the full 14 days, and we shipped four closed builds after the review (960, 975, 994, 1025), each with real changes and honest notes. Guest mode opens every screen without an account, and each fix was checked on the live build.
> هذه المرّةَ بقي ١٢ مختبِراً مشتركين الأيّامَ الأربعةَ عشر كاملة، وأصدرنا بعد المراجعة أربعةَ إصداراتٍ مغلقة (960 و975 و994 و1025) بتغييراتٍ حقيقيّةٍ وملاحظاتٍ صادقة. ووضعُ الضيف يفتح كلَّ شاشةٍ بلا حساب، وكلُّ إصلاحٍ تُحقِّق منه على الإصدار الحيّ.

**والسهولة (٢)**: «ليس صعبًا ولا سهلاً» كما كانت — **والعدُّ على الحدّ تماماً (١٢) يشهد أنها ليست «سهلة»**.


### نصُّ الإرسال لإعادة تقديم الكبتن (٢٠٢٦-١١-٠٥) — **يُرسل في ٧ أو ٨ نوفمبر بأمر المالك، بعد قياس أرقامه يومَها**

**هذا هو النصُّ الذي يُلصق في النموذج سؤالاً سؤالاً**، مجموعاً من مسوّدة ١١-٠٣ ونهائيّات ١١-٠٤. **و٥ بلا ذكرٍ لسوقٍ غير الأردن والجزائر**
(قاعدةٌ دائمة). **وما يُقاس يومَ الإرسال قبل «تطبيق»**: عدّادُ Play (الأيّامُ والمشتركون) وأعطالُ ٢٨ يوماً وآخرُ إصدارٍ مغلق — **فإن خالف رقمٌ النصَّ
عُدّل الرقمُ لا القياس**، وبقي كلُّ جوابٍ دون ٣٠٠ حرف.

1. Unpaid testers from our own network (friends, family and captains from our driver WhatsApp groups), from 11 Sep 2026 by email list and then our Google Group, plus Testers Community, a paid testing service, which added 15 testers per app on their own phones in other countries from 18 Oct.
2. ليس صعبًا ولا سهلاً
3. Testers used the closed builds on their own phones, mostly in guest mode, which opens the whole captain app without an account: home map, going online, ride offers, earnings, wallet and plans. 12 testers stayed opted in for 14 straight days.
4. Feedback came from the in-app Send feedback form, our captain WhatsApp groups and the Testers Community report. They asked for an onboarding tour, a share button and a clearer store listing; their report found no crashes or critical errors.
5. Licensed drivers (captains) in Jordan and Algeria who want to earn by accepting nearby ride requests, with the fare shown before accepting, clear earnings, a wallet with withdrawals and simple subscription plans.
6. Captains see the fare before accepting, get turn-by-turn guidance, chat and call riders without sharing numbers, track earnings, withdraw from the wallet and choose daily, weekly or monthly plans, in Arabic and French, with local payment options in each market.
7. ‫10 آلاف - 100 ألف
8. Since the review we shipped builds 960, 975, 994 and 1025: a security update, edge-to-edge display, a one-layer back button, sign-in kept if the app is killed, and a server fix so captains who also ride get ride offers. From feedback: a 4-card tour, a Share button and a new store listing.
9. 12 opted-in testers for 14 days, 0 crashes and 0 ANRs in Play vitals for 28 days, no policy issues. Every release passes our full automated suite and code guards in CI, a verified backup and a money-integrity check before deploy, and live monitoring alerts us.
10. This time 12 testers stayed opted in for the full 14 days, and we shipped four closed builds after the review (960, 975, 994, 1025), each with real changes and honest notes. Testers tried every screen in guest mode, and each fix was checked on the live closed build.

> **وسطرُ «كبتنٌ هو راكبٌ أيضاً» في ٨ (أمرُ المالك ٢٠٢٦-١١-٠٦)**: مقبسُ الكبتن كان يسقط لمن يحمل الدورين فلا يصله طلب — قائمٌ على الإنتاج منذ ٢٠٢٦-٠٨-١٩،
> وأُصلح في 41c96e0f ورُفع في 6ab90e1e (٢٠٢٦-١١-٠٦). وهو إصلاحُ خادمٍ يبلغ كلَّ الإصداراتِ بلا حزمةٍ جديدة؛ **ويُذكر في ملاحظات أوّلِ إصدارٍ مغلقٍ قادمٍ للكبتن**:
> «إصلاح: الكبتن الذي يستعمل التطبيقَ راكباً أيضاً تصله طلباتُ الرحلات الآن» / "Fix: captains who also ride with Taxo now receive ride offers."
