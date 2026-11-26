# أمرُ المالك ٢٠٢٦-١١-٢٦ — أمرٌ واحدٌ كامل (تسعة بنود)

> **نصُّ الأمر كما وصل** (بالإنجليزيّة)، ثمّ أين كُتبت قراراتُه. والمطلقاتُ والبوّاباتُ فوقه كما هي.

ONE complete order. The P0 request-delivery fix stays first priority if anything of it is still open. Continue without stopping, and send ONE report in Arabic.

1. Ride-request tone: we ALREADY have the TAXO «بيب بيب تاكسو» tone. Do not make a new one. Make sure it is used for every ride request and plays LOUD everywhere:
   - foreground, background, app closed, bubble showing, screen locked: a high-priority notification channel that uses this tone (if the current channel has a different or default sound, create a NEW channel ID with this tone), full-screen intent for the request, plus vibration;
   - repeated until the captain accepts, declines, or the request expires; stops immediately then; never plays when the captain is offline;
   - plays even on silent/vibrate while the captain is ONLINE (alarm audio stream), with a setting «رنين الطلب حتى في الوضع الصامت» ON by default that the captain can turn off, and a test button «جرّب النغمة»;
   - if the tone file is quiet, raise its loudness without distortion.
   Tell me why it did not ring in the background before.
2. End-of-ride payment flow (my decision), professional and clean in both apps:
   - REMOVE the rider's «تم الدفع» button completely. Only the captain confirms payment with «تم الاستلام».
   - Rider's end-of-ride screen: the fare amount large and clear, the payment method, the captain rating (stars + optional comment), and the tip (quick choices + custom amount; the tip is added to the amount shown).
   - If the method is CliQ: show the captain's CliQ alias (and his name as registered) in a clear card with a «نسخ» button and a short line «حوّل المبلغ من تطبيق بنكك عبر كليك», plus the exact amount to transfer (fare + tip) with its own copy button.
   - If cash: «ادفع للكابتن نقداً» with the amount (fare + tip).
   - If wallet: charged automatically as today, the screen only shows the result.
   - Captain's end-of-ride screen: the amount to collect (fare + tip), the method, and a big «تم الاستلام» button; plus «لم أستلم المبلغ» which opens a simple report to support (no money change by itself).
   - The ride closes and is recorded exactly as today when the captain presses «تم الاستلام»; no change to money rules, fares, commission or the ledger logic. If the captain does not confirm within a time set in the panel, remind him; never auto-confirm.
   - Same design language as the rest of TAXO, both themes, Arabic RTL, Latin numerals, «كابتن».
3. Wording across the WHOLE project: every singular «كبتن» / «الكبتن» (with all prefixes and suffixes) becomes «كابتن» / «الكابتن»; the plural «كباتن» stays. In every user-facing Arabic text: both apps, the admin panel, the website, notifications and push texts, SMS/WhatsApp/email and OTP templates, policies and terms (same meaning, no re-acceptance), store listings, the Digistore24 sales and thank-you pages, the captain WhatsApp group texts (with the Note 20, phone rule), and the on-screen text of the videos if possible without new voice-over. Do NOT change code identifiers, database fields, API names, file names or translation keys. Update French only if needed. Give me the count of changes per area.
4. Google Play, driver app: rename the listing to «TAXO Driver» (Arabic listing too) and the launcher label to match. Update the closed-testing track so testers are not stuck on an older build (update it to the newest release or pause it, whichever is safe); never harm the production release.
5. Store images for BOTH apps: new portrait screenshots from the REAL current apps (after items 1–3) with the test captain and test rider only, clean demo data (no real names, numbers, plates or addresses; Jordan default):
   - driver (6–8): home with map, online button and «سيارتك», a ride request, navigation, the «تم الاستلام» screen, earnings, wallet, the bubble, the widgets, the launch-campaign banner;
   - rider (6–8): home with map and «إلى أين؟», categories, fare before the ride, the captain on the way, trip tracking, the end-of-ride screen (rating, tip, CliQ details), wallet/TAXO cards.
   Short Arabic caption on each in TAXO style (orange/black, TAXO 3D cars where it fits), Latin numerals, «كابتن». No promised earnings, no card payment in driver images, no offers with unset values. Refresh the feature graphic (1024×500) for each app. French versions if a French listing exists. Upload them to Play Console (replace the old ones) and save copies in my Desktop «TAXO-store-images\driver» and «TAXO-store-images\rider».
6. Riders on the old version 772 (old signing key, cannot update from Google Play) — my decision: show them a simple, friendly Arabic in-app message: uninstall once and install TAXO from Google Play; their account stays, they only sign in again. With a button that opens the rider app's Google Play page. Show it only on version 772 and any other build signed with the old key, once per app open, with «لاحقاً» allowed. Report how many riders saw it and how many moved to the Play version within 7 days.
7. Ship everything: deploy server/web changes through the five gates, then a new release of BOTH apps on Google Play to production 100% (no staged rollout), and update the website download files (same Play signing key).
8. Test on MY Note 20 (adb -s with its serial, the phone rule: tap only when a TAXO app is in front and the screen has been still for 2 minutes; never touch other apps or personal data):
   - update both TAXO apps on it to the new releases;
   - use ONLY the test captain and test rider. If a real account is signed in on the Note 20, do not use it and do not sign it out; tell me and wait for me to sign in the test accounts myself;
   - test: a ride request reaches the test captain in the foreground, in the background with the bubble, with the app closed and with the screen locked, and the «بيب بيب تاكسو» tone rings loud each time (also on silent); accept/decline stops it; a full test ride to the end with CliQ and with cash: the rider sees amount, rating, tip and the CliQ details with copy buttons, has NO «تم الدفع» button, and the captain closes it with «تم الاستلام»; the rider bubble works; the home screen layout is clean; «كابتن» shows everywhere; record a short screen video and audio as proof.
   Then restore the phone settings you changed.
9. Report in Arabic: the P0 root cause and status, why the tone did not ring before, the new end-of-ride screens (screenshots), the counts of wording changes, the published versions and links, the old-version message numbers, the Note 20 test results with the proof files, and anything Google asks for.

Conditions: no change to fares, subscription prices, commission, money tables or the ledger logic. Do not turn on any rider offer or the captain-pays-discount rule. Never type my passwords or codes; if Play Console asks for a sign-in or code, stop and tell me. No paid tools. Never print secrets. Never skip a deploy gate. Never touch the S21 unless its lock is free and only with the phone rule. Do not touch the Fawri project or the iOS agent's work.

## أين كُتب

- البند ١ ⇐ SPEC §١١٥ · البند ٦ ⇐ SPEC §١١٦ · البند ٢ ⇐ SPEC §١١٧ · البند ٣ ⇐ SPEC §١١٨ · البند ٤ ⇐ SPEC §١١٩.
- **S21**: القاعدةُ في CLAUDE.md (قرارُ المالك ٢٢/١١) أعلى — S21 لوكيل Fawri ولا يلمسه وكيلُ TAXO؛ **الاختبارُ على Note 20 وحدَه**.
- **«مفاتيحُ الترجمة لا تتغيّر»**: في هذا المشروع **المفتاحُ هو النصُّ العربيُّ نفسُه** (`tr("…")` و`fr.json`) — فتغييرُ النصِّ المعروض
  يغيّر المفتاحَ في موضعيه معاً، ولا مفتاحَ غيرُه يُمسّ. والمعرّفاتُ (`captain`/`driver`) وأسماءُ الحقول والملفّات لا تُمسّ.


## قرارُ المالك ٢٦/١١ — إعادةُ الرفع 18 (بعد سقوطه في البوّابة الرابعة 02:25Z)

نصُّه: «أعد الرفع 18 كما هو (الخيار ١) من البوّابة الأولى: نسخةٌ جديدة، واقرأ رقمَ الترحيلة بنفسك، وطبّق 0191 إن لم تكن مطبّقة،
وأعد بناء الحاويات وتشغيلها، وتحقّق من كلّ شيء (الخلفيةُ والعمّالُ على الصور الجديدة، والموقعُ يُظهر «كابتن»، والصحّة، والسجلّ).
**إن انقطع الاتّصالُ ثانيةً فأعد تلك الخطوةَ مرّةً واحدة؛ وإن سقطت ثانيةً فارجع إلى 95add0be بطريق النسخة المحقَّقة وأخبرني.**
الذاكرة: إن قلّت بسبب بناء مشروعٍ آخر فانتظر وأعد الفحصَ كلَّ ٢٠ دقيقة، ولا توقف المشروعَ الآخر. ثمّ أكمل بقيّةَ الأمر وتقريرٌ واحدٌ بالعربيّة.
ولا تتخطَّ بوّابة.»
