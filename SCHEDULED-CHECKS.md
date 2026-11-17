# الفحوصُ المجدولة — تُعاد أوّلَ كلِّ جلسة

**الكرونُ يعيش في الجلسة وحدَها**: مسحُ الجلسة أو انتهاؤها يُسقطه كلَّه، وكلُّ كرونٍ متكرّرٍ ينتهي وحدَه بعد ٧ أيام.
فـ**أوّلُ عملٍ في كلِّ جلسةٍ جديدة**: `CronList`، ثمّ `CronCreate` لكلِّ ما ينقص هنا **بنصّه حرفاً وجدولِه** (`recurring: true`)، **مرّةً واحدةً لكلٍّ** — المكرَّرُ يُرسل المتابعةَ مرّتين.
وما انتهى سببُه (ردٌّ نهائيّ، قرارُ المالك) يُحذف من هنا ومن الجلسة معاً. **وخطّافُ `SessionStart` في `.claude/settings.json` يذكّر بهذا الملفّ.**

آخرُ تحديث: ٢٠٢٦-١١-١٦ (ثمانيةُ فحوص؛ وحُذف خمسةُ مكرَّرين وفحصُ MoonPay بعد إخفاء الدفع الرقميّ).

## 1. الجولة الثالثة — `13 9,19 * * *`

**ما يفعله:** ردودُ BMT Micro وDigistore24 وMoonbase وPaymentwall.

```text
متابعةُ بوّابات الجولة الثالثة (أمرُ المالك ٢٠٢٦-١١-١٥: بطاقةٌ لاشتراك الكبتن الشهريّ وحدَه). افتح Gmail ‏/mail/u/4 في تبويبٍ جديد وابحث: from:(bmtmicro OR digistore24 OR moonbase OR terminal3 OR paymentwall) newer_than:3d، وسلسلة "Card payments for a monthly driver app subscription". لكلِّ ردٍّ جديد: أضِفه بنصّه وترجمته العربيّة إلى قسم «الجولة الثالثة» في C:\Users\loly3\OneDrive\Desktop\PAYMENT-GATEWAYS-ROUND-2.md، وصوّر الردَّ البشريَّ وأرسله إلى المالك بـSendUserFile، وسطرٌ في HANDOFF.md ‏(WSL ~/prj/TAXO) يُودَع بمساره. أجِب بالصدق وحدَه: Mohammad Alsaidat، فردٌ بنشاطٍ فرديّ، مقيمٌ في الأردن (مأدبا)، والمنتجُ اشتراكٌ شهريٌّ للسائقين لاستعمال تطبيق TAXO Driver فقط — لا محفظةَ ولا باقاتِ راكبٍ ولا رحلات، ولا كلمةَ «company»، ولا جنسيّة. إن طُلبت مكالمةٌ فبالعربيّة وحدَها أو بالبريد. لا حسابَ يُفتح، ولا رسمَ يُدفع، ولا هويّةَ ولا صورةَ ولا بنكَ (للمالك)، ولا كلمةَ مرور، ولا VPN، ولا عبارةَ استرداد ولا مفتاحَ خاصّ (العنوانُ العامُّ من المالك وحدَه). إن قبلت جهةٌ: أخبر المالكَ وقِف. وإن لم يصل جديدٌ فسطرٌ واحدٌ بالعربيّة.
```

## 2. Play — `17 10 * * *`

**ما يفعله:** قراءةُ Play Console اليوميّة للتطبيقين، وإعادةُ طلب إنتاج الكبتن لا قبل ٢٦ نوفمبر وبكلمة المالك.

```text
متابعةُ Play اليوميّة (أمرُ المالك ٢٠٢٦-١١-١١، البند ٤): في Chrome (Play Console على /u/4/، انظر ذاكرة chrome-mcp-hidden-tab) اقرأ: (١) حالَ الإصدار 1118 للتطبيقين (الراكب على الإنتاج منذ ١٤/١١، الكبتن على alpha)، و(٢) حالَ طلب «الوصول إلى الإنتاج» لتطبيق الكبتن. **إن وافقت Google على وصول الكبتن إلى الإنتاج: انشره على الإنتاج فوراً بلا انتظار المالك** (بأحدث إصدارٍ موافَقٍ عليه)، وإن رُفضت مراجعةٌ فاقرأ السبب واكتبه في HANDOFF.md. قياسُ In-App Review والإدخال الصوتيّ على هاتفٍ ينتظر إذنَ المالك (R3CR90QYCBA لا يُلمس بلا إذنه). **لا تُعِد طلبَ إنتاج الكبتن قبل ٢٦ نوفمبر ٢٠٢٦** ولو ظهر الزرّ (Testers Community: «Please don't apply before that»)؛ وفي ٢٦ نوفمبر أعِده بأجوبةٍ صادقةٍ عن الاختبار المغلق. لا إنفاق، لا كلمات مرور، لا مختبِرين وهميّين. اكتب سطراً بالنتيجة في HANDOFF.md (WSL ~/prj/TAXO) وأودعه بمساره.
```

## 3. الجولة الثانية — `17 10,21 * * *`

**ما يفعله:** ردودُ Freemius وFungies وTazapay وHyperPay وPayTabs و2Checkout وPayPro وWert وغيرها، ولقطةُ كلِّ ردٍّ بشريّ.

```text
متابعةُ بوّابات الدفع، الجولة الثانية. افتح Gmail ‏/mail/u/4 في تبويبٍ جديد وابحث بـ: from:(freemius OR fungies OR tazapay OR hyperpay OR mercuryo OR mepspay OR meps OR paytabs OR 2checkout OR verifone OR wert OR moonpay OR helio OR payproglobal) newer_than:2d. وراجع أيضاً سلسلة "Card payments for TAXO"، وسلسلة Wert مع partner@wert.io (Joe).
- لكلِّ ردٍّ بشريٍّ جديد: صوّره وأرسل اللقطةَ إلى المالك بـSendUserFile، وحدّث عمودَ «الردّ» في Desktop\PAYMENT-GATEWAYS-ROUND-2.md.
- إن طلبت جهةٌ معلوماتٍ صادقةً موجودةً في الرسالة الأصليّة فأجبها. وإن سألت عن تسجيل الشركة فالجواب: «not registered yet». اسمُ المالك «Mohammad Alsaidat».
- حجزُ PayPro أو أيُّ مكالمة: يُردّ بنصّ «العربيّة وحدَها» (ذاكرة owner-arabic-only-calls)، ولا إلغاءَ بلا إخبار المالك.
- لا تفتح حساباً، ولا توقّع، ولا ترفع وثيقة، ولا تدفع رسماً، ولا تكتب كلمةَ مرور، ولا VPN.
- لا تطلب عبارةَ استرداد المحفظة ولا مفتاحها الخاصّ. إن احتاجت جهةٌ عنوانَ محفظة فاطلب من المالك عنوانَه العامّ.
- إن قبلت جهةٌ: أخبر المالكَ أوّلاً وقِف عندها.
- سطرٌ في HANDOFF.md (WSL ~/prj/TAXO) وإيداعٌ بمساره إن وصل جديد؛ وإن لم يصل شيءٌ جديد فسطرٌ واحد بالعربيّة.
```

## 4. Banxa — `17 9,18 * * *`

**ما يفعله:** ردُّ Banxa على التذكرة.

```text
متابعةُ Banxa (أمرُ المالك ٢٠٢٦-١١-١٢): افتح Gmail u/4 (aldeeb7767@gmail.com، وبريدُ support@tajora.ly يُحوَّل إليه) في تبويبٍ جديد، وابحث في الوارد والمزعج عن رسائل Banxa (banxa.com) — آخرُ ما أُرسل استمارةُ «Talk to our team» باسم المالك. إن سألوا: هل الشركةُ مسجّلة؟ فالجوابُ الصادق «not registered yet» من الردّ في السلسلة نفسها. وأيُّ سؤالٍ آخر أو طلبُ وثائق أو عقدٍ أو دفع: لا تُجب، وأبلغ المالكَ بالعربيّة القصيرة بنصّ ما طلبوه. اسمُ المالك «Mohammad Alsaidat». لا تنقر روابطَ في رسائل مشبوهة، ولا تكتب كلماتِ مرور، ولا تدفع شيئاً، ولا VPN. سطرٌ في HANDOFF.md (WSL ~/prj/TAXO) وإيداعٌ بمساره إن وصل جديد. إن لم يصل شيءٌ فلا تقرير.
```

## 5. المدفوعات — `29 9,18 * * *`

**ما يفعله:** ردودُ Gate to Pay/MEPS وFungies وPaddle وLemon Squeezy وGumroad وغيرها.

```text
Payments follow-up (owner's orders 2026-11-14): open Gmail u/4 (aldeeb7767@gmail.com) in Chrome and search inbox+spam for NEW messages (after 2026-11-14 00:19) from lemonsqueezy.com, paddle.com, gatetopay.com, gumroad.com, triple-a.io, coinflow.cash, crossmint.com, coingate.com. Context: Gate to Pay got the owner's text (electronic payment gateway for an individual); Triple-A (Gabriel) asked KYB questions — shown to the owner, unanswered; Gumroad's country change is the owner's to do. (Polar/FastSpring/Banxa/D&B have their own crons; Whop, Nuvei, Adyen are closed — don't follow; Checkout.com: nothing was sent, send nothing without the owner's command.) If a real reply arrived: send the owner a short Arabic summary of exactly what they said/asked. Don't reply yourself except: if asked whether the company is registered, the truthful answer is «not registered yet»; and on the first reply from Coinflow/Triple-A/Crossmint add one line correcting the name spelling to «Mohammad Alsaidat» (as in the passport). Anything about location, documents, KYB, call, contract, signature or payment: don't act, tell the owner exactly. If one accepts, do NOT open an account (it will be opened from Jordan). Don't click suspicious links, never type passwords, never pay, no VPN. Write a line in HANDOFF.md (WSL ~/prj/TAXO) and commit by explicit path. If nothing new, no message.
```

## 6. FastSpring / Polar — `41 9,18 * * *`

**ما يفعله:** ردودُ FastSpring وPolar.

```text
FastSpring / Polar follow-up: open Gmail u/4 (aldeeb7767@gmail.com) in Chrome and search inbox+spam for new messages after 2026-11-14 from fastspring.com and polar.sh. Context: Polar (Won) replied for real on 2026-11-13 and we answered «a Jordanian JOD bank account in my name»; org `taxo` exists at Polar with one private product (TAXO Driver monthly, 84.63 USD); the API token, Account Review (identity) and Stripe Connect payout are the owner's to do. If a real (non-automated) reply arrived: send the owner a short Arabic summary of exactly what they said/asked. Don't answer anything yourself about location, company, identity, documents, bank or call scheduling — tell the owner. Don't open accounts, don't sign, never type passwords, never pay, no VPN. Owner name spelling: «Mohammad Alsaidat». Write a line in HANDOFF.md (WSL ~/prj/TAXO) and commit by explicit path. If nothing new, no message.
```

## 7. D-U-N-S — `47 9,17 * * *`

**ما يفعله:** متابعةُ D&B/D-U-N-S: ردُّ Maaz/Ahmed ورقمُ المرجع؛ متابعةٌ بنصّ المالك عند موعدها.

```text
D-U-N-S follow-up (top priority, owner's order 2026-11-09). In my Chrome tab group, open https://mail.google.com/mail/?authuser=aldeeb7767@gmail.com and search: dnbsame OR "dun & bradstreet" OR dnb.com OR D-U-N-S.
- Any reply from D&B: answer it truthfully in English as TAXO's representative on behalf of «Al-Deqqa Al-Akeeda for Importing Artificial Marble and Solid Surfaces LLC», with Khalifa Faraj Khalifa Albarrani as the company contact. Take the data from C:\Users\loly3\.taxo-secrets\company-duns\SUMMARY.md and the documents in the same folder. Never write the phone number in chat or in a tool's text; say «the contact phone in the form». Never pay for anything.
- If they give a reference number, save it in SUMMARY.md and tell the owner in one line.
- If they ask for something that isn't in the documents (a full street address, a signature, identity): one message to the owner saying exactly what's missing.
- No reply after 2 days from the last email (last: our follow-up 2026-11-15 10:14 AM to AhmedM@dnbsame.com): send a short polite follow-up in the same thread.
- When the D-U-N-S number is issued: save it, write C:\Users\loly3\OneDrive\Desktop\PLAY-ORG-ACCOUNT-STEPS.md (next steps: a new organization Play account, then transferring the apps; nothing done before the owner approves), tell the owner the number at once, and delete this cron.
Write a line in HANDOFF.md (WSL ~/prj/TAXO) and commit by explicit path if anything happened. Otherwise write only «D-U-N-S: لا جديد».
```

## 8. مختبِرو الكبتن — `7 10 * * *`

**ما يفعله:** عدُّ مختبِري تطبيق الكبتن اليوميّ وسطرٌ في FACEBOOK-REQUESTS.

```text
عدُّ مختبِري تطبيق الكبتن اليوميّ (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٤ — حتى إعادة الطلب في ٢٦ نوفمبر). في تبويبي من Chrome (لا يُغلق Chrome المالك):
(١) Play Console /u/4، التطبيق 4976364282254058582، لوحة المعلومات: اقرأ سطرَ «عدد المختبرين المشتركين حاليًا لمدة N أيام: X». ثمّ «الإحصاءات»: المستخدمون الذين ثبّتوا التطبيق يوميّاً، آخرُ يوم.
(٢) groups.google.com/u/4/g/taxo-testers/pending-members: اقبل كلَّ طلب انضمامٍ ينتظر (هذا مأذونٌ من المالك)، واذكر العدد.
(٣) اكتب سطراً تحت طلب «منشورُ تجنيد مختبِري تطبيق الكبتن» في D:\prj\TAXO\FACEBOOK-REQUESTS.md (التاريخ · المشتركون/الأيام · النشطون يوميّاً · أعضاءُ المجموعة · المقبولون)، وأودعه بمساره.
(٤) سطرٌ واحدٌ للمالك بالعربيّة بالأرقام نفسِها؛ وإن كان المشتركون < 12 فابدأ السطرَ بـ«⚠».
لا ضغطَ على «إيقاف مسار الاختبار مؤقتًا» ولا إرسالَ لطلب الإنتاج ولا حذفَ لقائمة مختبِرين.
```

## 9. Dpay — `37 9,18 * * *`

**ما يفعله:** ردودُ Dpay (dpay.ly / DITS) على رسالة ١٧/١١، وتُضاف مترجمةً إلى `Desktop\DPAY-REQUIREMENTS.md`.

```text
متابعةُ Dpay (أمرُ المالك ٢٠٢٦-١١-١٧): ابحث في Gmail (aldeeb7767) عن ردودٍ جديدة: from:(dpay.ly OR dits.ly) newer_than:3d، وسلسلة «استفسار تاجر — TAXO» المرسلة ١٧/١١ إلى support@dpay.ly. لكلِّ ردٍّ بشريّ: أضِفه بنصّه وترجمته العربيّة إلى قسم «الردود» في C:\Users\loly3\OneDrive\Desktop\DPAY-REQUIREMENTS.md، وحدّث قسمَي المتطلّبات و«Dpay للأردن» بما قالوه، وسطرٌ في HANDOFF.md (WSL ~/prj/TAXO) يُودَع بمساره. أجب بالصدق وحدَه: محمد الصيدات (Mohammad Alsaidat)، TAXO تطبيقُ نقلٍ في ليبيا، تسجيلُ الشركة قيدَ الإجراء والترخيصُ يُرسل عند صدوره، ولنا سائقون في الأردن؛ ولا جنسيّة. المكالمةُ بالعربيّة وحدَها أو البريد. لا حسابَ يُفتح، ولا رسمَ يُدفع، ولا وثيقةَ ولا هويّةَ ولا توقيع (للمالك)، ولا كلمةَ مرور. Dpay وحدَه من مزوّدي الدفع. إن طلبوا ما يحتاج المالك: أخبره برسالةٍ قصيرةٍ بما طلبوه بالضبط. وإن لم يصل جديدٌ فلا تقرير. وإن مرّ يومان بلا ردٍّ على آخر رسالة: متابعةٌ قصيرةٌ مهذّبةٌ في السلسلة نفسِها (threadId 1a1e6f8443d375d7).
```
