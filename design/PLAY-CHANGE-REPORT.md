# TAXO — Change report since the closed test began / تقريرُ التغييرات منذ بدء الاختبار المغلق

**Period / الفترة**: 11 September – 22 October 2026. **Sources / المصادر**: git history (agent and master branches), `SPEC.md` §61–§82,
`STATE.md`, the deploy logs (`taxo-deploy-logs`), Play Console (bundle explorer, tracks, dashboard) and Testers Community.
Every date and version below is read from those sources; nothing is estimated.

---

## 1. Closed-test history / تاريخُ الاختبار المغلق

| Date | Event | الحدث |
|---|---|---|
| 7 Sep | Rider builds 493 and 496 (1.0) uploaded | رُفعت حزمتا الراكب 493 و496 |
| 11 Sep | Captain builds 516 and 517 (1.1); closed test opens to an email list of testers | حزمتا الكبتن 516 و517؛ ويبدأ الاختبار المغلق بقائمة بريد |
| 15 Sep | First members accepted into our Google Group of testers (friends, family, captains from our driver WhatsApp groups) | قبولُ أوائل أعضاء مجموعة Google للمختبِرين |
| 14 Oct | **867 (2.0)** — the TAXO 2.0 redesign, both apps | **867** — تصميمُ TAXO 2.0 للتطبيقين |
| 16 Oct | **874** — guest mode (try every screen without an account) | **874** — وضعُ الضيف |
| 16 Oct | **877** — Android 7+ support (minSdk 24) | **877** — دعمُ Android 7 فما فوق |
| 17 Oct | **911** | **911** |
| 18 Oct | **918**; Testers Community joins: 15 testers per app, 16-day programme | **918**؛ وتنضمّ Testers Community بخمسة عشر مختبِراً لكلِّ تطبيق |
| 19 Oct | **929** — website download now serves Play-signed APKs, so website installs take Play updates | **929** — حزمُ الموقع بتوقيع Play |
| 20 Oct | **932** — current closed-test build; Play's three closed-test conditions met for both apps | **932** — الإصدارُ الحاليّ؛ وشروطُ Play الثلاثة مستوفاةٌ للتطبيقين |
| 22 Oct | Testers Community day 4 of 16, reports 0 of 2 so far | Testers Community في يومه الرابع من ١٦، ولا تقريرَ بعد |

**Track**: closed (alpha), 178 countries/regions. **Feedback channels**: in-app «Send feedback» with screenshot, captain WhatsApp
groups, Testers Community. **Play's app-testing feedback page has no entries** for either app at the time of writing.

---

## 2. Rider app / تطبيقُ الراكب

| Date | Version | What changed / ما تغيّر | Why / لماذا |
|---|---|---|---|
| Sep–Oct | 867 | TAXO 2.0 design: home, booking, ride, history, wallet screens rebuilt on one design system; Arabic RTL and Latin digits everywhere · إعادةُ بناء الشاشات على نظام تصميمٍ واحد | Consistency and clarity · الاتّساق والوضوح |
| Oct | 867 | Trip chat and in-app calls without exposing phone numbers; call recording only after a clear notice · المحادثة والمكالمة بلا كشف الأرقام | Safety and privacy · السلامة والخصوصية |
| Oct | 867 | Arrival time, «captain is approaching» alerts, voice guidance, «open in Google Maps» · زمنُ الوصول وتنبيهُ اقتراب الكبتن | Fewer missed pickups · التقاطٌ أدقّ |
| 15–16 Oct | 874 | Guest mode: the full app without an account (demo data, no real ride or payment) · وضعُ الضيف | Lets anyone, including reviewers, try every screen · ليجرّب أيُّ أحدٍ كلَّ شاشة |
| 15 Oct | 874 | French interface for Algeria; French-only defects fixed · الواجهةُ الفرنسيّة | Algeria launch · فتحُ الجزائر |
| 16 Oct | 877 | Android 7+ (minSdk 24) · دعمُ Android 7 | More devices in our markets · أجهزةٌ أكثر |
| 16 Oct | server | The «go to payment» sheet no longer reappears after paying; the bottom bar no longer disappears · لا تعود نافذةُ الدفع بعده | Bug from testing · عطبٌ من الاختبار |
| 18 Oct (built) | server | Policy consent screen: when a policy changes materially, users accept the new version before continuing · شاشةُ الموافقة على السياسات المحدّثة | Informed consent · موافقةٌ واعية |
| 22 Oct | server | Market screens and wallet show the right state of every payment (received and processing · not confirmed · cancelled) · حالُ كلِّ دفعةٍ بوضوح | Owner's payment rule · قاعدةُ المالك |

## 3. Captain app / تطبيقُ الكبتن

| Date | Version | What changed / ما تغيّر | Why / لماذا |
|---|---|---|---|
| Oct | 867 | TAXO 2.0 captain screens: home map, offer card, active ride, earnings, wallet, subscription · شاشاتُ الكبتن بالتصميم الجديد | Faster decisions on the road · قرارٌ أسرع |
| Oct | 867 | Auto-accept options, «captain approaching» notices, voice guidance · القبولُ التلقائيّ والإرشادُ الصوتيّ | Fewer missed rides · رحلاتٌ أقلّ ضياعاً |
| 15–16 Oct | 874 | Guest mode for captains (home, going online, offers, earnings) · وضعُ الضيف للكبتن | Reviewers and testers try without documents · تجربةٌ بلا وثائق |
| 16 Oct | 877 | Android 7+ · Android 7 | Older driver phones · هواتفُ السائقين الأقدم |
| 13–17 Oct | server | Subscription purchase by card (Chargily) in Algeria, daily/weekly/monthly plans and the «first week free» offer · الاشتراكُ بالبطاقة في الجزائر | Algeria launch · فتحُ الجزائر |
| 22 Oct | server | Subscription payment by BaridiMob/CCP transfer, reviewed manually · دفعُ الاشتراك بتحويل BaridiMob | A second local way to pay · طريقةٌ محلّيّةٌ ثانية |

## 4. Payments / الدفع

| Date | What changed / ما تغيّر |
|---|---|
| 13 Oct | Algeria market: payment methods per market, wallet top-up choices, rounding to 10 DZD, test accounts with test money only · سوقُ الجزائر وطرقُه |
| 15 Oct | Chargily live: Edahabia and CIB cards; the wallet is credited only from Chargily's signed confirmation · Chargily حيّ |
| 17 Oct | **41-step end-to-end check of the Chargily flow, one screenshot per step; 17 issues found and fixed** (wrong decimals, a red error for a user's own cancel, «continue payment» instead of a second page, the page language, the gateway customer…) · فحصٌ في 41 خطوة و17 إصلاحاً |
| 18 Oct | Payer name and phone shared with Chargily, turned on only after the Algeria privacy policy v4 said so · لا مشاركةَ قبل السياسة |
| 22 Oct | **Outage safety**: a health check before the payment page; a clear message in Arabic and French with «try again» and BaridiMob as an alternative; no failed or abandoned payment stays «pending»; only «Chargily says paid but not yet credited» is «processing», and reconciliation credits it exactly once; double taps open one page; owner alerts when the gateway is down and when it is back · الدفعُ بأمانٍ عند الانقطاع |
| 22 Oct | **BaridiMob/CCP transfer** for Algeria: RIP and the two name spellings with copy buttons, a TAXO reference, receipt + transfer number + date, 200–20,000 DZD, approval by the owner or a limited reviewer account with two-step verification · تحويلُ BaridiMob بمراجعة |

## 5. Safety and privacy / السلامة والخصوصية

| Date | What changed / ما تغيّر |
|---|---|
| 14 Oct | Full privacy policies and terms per market and app, in Arabic, French and English, written from the app's real behaviour · السياساتُ كاملةً بثلاث لغات |
| 18 Oct | Consent screen for updated policies (version tracking per user) · شاشةُ الموافقة |
| 18 Oct | Test accounts for testers cannot change their password or delete themselves; server reset available · حساباتُ التجربة محميّة |
| 22 Oct | Algeria privacy policy v5 (receipt image and transfer number for BaridiMob, reviewed by TAXO's payment reviewer who sees only a first name and a masked phone); users re-consent · سياسةُ الجزائر v5 |
| 22 Oct | Data safety form updated: «Files and docs» declared for PDF receipts · تحديثُ أمان البيانات |
| Ongoing | Owner account and payment reviewer require two-step verification; every money action is audited; the money ledger is append-only · العاملُ الثاني والتدقيق |

## 6. Performance and capacity / الأداءُ والسعة

| Date | What changed / ما تغيّر |
|---|---|
| 13 Oct | Production load test; adaptive location broadcasting; measured safe capacity **~350 captains and 700 riders online at once** · اختبارُ الحمل والسعة |
| 14 Oct | Background worker fixed (it took a full core on light load); capacity alarm at 70 % of safe capacity, with the live count on the admin home · العاملُ الخلفيّ وإنذارُ السعة |
| Every release | Six deploy gates: announcement, push and full CI, verified off-server backup, deploy from the CI-tested commit, live verification, money fingerprint before and after with zero difference · البوّاباتُ الستّ |

## 7. Admin and support / الإدارةُ والدعم

| Date | What changed / ما تغيّر |
|---|---|
| 15 Oct | Owner account with every permission and mandatory two-step verification · حسابُ المالك |
| 20–21 Oct | Owner alerts for every sign-up, payment, ride, complaint and rating, on the panel, the browser and the admin phone app, with per-category sounds · إشعاراتُ المالك |
| 22 Oct | Browser alerts (web keys), market switcher fixed on the owner's phone, the alerts menu fits phone screens · مفاتيحُ الويب والمبدّل وقائمةُ الجرس |
| 22 Oct | BaridiMob review page, owner settings card for the receiving account, and a limited reviewer role created by the owner · صفحةُ المراجعة ودورُ المراجع |
| Ongoing | In-app «Send feedback» with screenshot, support page, feedback inbox in the panel · «أرسل ملاحظة» وصندوقُها |

---

**Not in this report / ما ليس هنا**: internal guards, tests and tooling (hundreds of commits) are summarised by the six deploy gates
above; full detail is in `SPEC.md` and `STATE.md`.
