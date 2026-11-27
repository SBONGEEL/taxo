# أمرُ المالك ٢٠٢٦-١١-٢٦ — Freemius بوّابةُ بطاقةٍ احتياطيّةٌ لاشتراك TAXO Driver

> **النصُّ كما قاله المالك** (بالإنجليزيّة، حرفاً):
>
> Freemius (my decision): register now as a BACKUP card gateway for the TAXO Driver subscription, build it, deploy it, add its
> switch in the panel, and do not stop until it works.
>
> 1. Registration: register on Freemius now, in my already signed-in browser, using my Google account sign-in if they offer it
>    (free plan only, no card). Truthful details: individual with a sole activity, «Mohammad Alsaidat», Madaba, Jordan, product
>    «TAXO Driver» subscription only (no rider payments, no wallet top-ups). Never type my passwords or codes; if a password,
>    2-step code, identity document, bank/payout or tax form is needed, stop at that field and give me exact simple steps, then
>    continue the rest when I tell you it is done. Save any API keys and webhook secrets only in the secrets folders,
>    /home/taxo/secrets (mode 600) and the KeePass vault, never printed.
> 2. Products: create the plans mirroring the CURRENT panel prices exactly (X1 3 JOD → 4.25 USD, X7 17 JOD → 24.00 USD, X30 45 JOD
>    → 63.50 USD with «TAXO MAN 45», X30-FULL 60 JOD → 84.50 USD), TAXO pays the fee. Never invent or change a price.
> 3. Build: an extra gateway on the existing gateway template — hosted checkout, verified webhooks, credit once through the ledger
>    with audit, PENDING/APPROVED/REFUNDED; website build only (never in the Play build); the same card-only screen, the same price
>    guard, the same «سيتم خصم القيمة من البطاقة بما يعادلها بالدولار» note, Jordan only (Libya/Algeria refused by the server).
> 4. Panel switch: in «الحملات والعروض» or the payments settings per country, add «بوابة الدفع بالبطاقة» with: OFF / Digistore24 /
>    Freemius. The captain sees only the selected one. Audit every change.
> 5. Test in Freemius sandbox/test mode with the test captain: purchase, webhook verified, credited once (repeat the webhook, no
>    double credit), cancel, refund reversed. Screenshots.
> 6. Deploy through the five gates (low memory allowed, one heavy task at a time). Then: when the Freemius account is live and the
>    test passed, set Jordan's card gateway to Freemius automatically if Digistore24 is still not approved; if Digistore24 gets
>    approved first, keep Digistore24 and leave Freemius ready as the backup. Watch the first real purchases for 30 minutes; if
>    anything is wrong, switch it OFF at once.
> 7. Report in Arabic: registration status and what I must do myself, the fee comparison with Digistore24 (3/17/45/60 JOD), test
>    results, and the panel steps.
>
> Conditions: no change to fares, subscription prices, commission or money tables. You never create real subscriptions. No
> payments, no paid plans, no card details. Truthful only; «فرد بنشاط فردي», never «شركة». Never skip a deploy gate. Do not touch
> the Fawri project or the iOS agent's work.

## ما بُني وكيف (وكيلُ التطبيقات، ٢٠٢٦-١١-٢٧)

- **المحوِّل** `backend/app/services/payment_gateways/freemius.py` على قالب Digistore24: صفحةٌ مستضافة (`checkout.freemius.com`)،
  إشعارٌ موقَّعٌ بـHMAC-SHA256 للجسم الخامّ (`x-signature`)، **والدولارُ من `digistore24.PRICE_MAP` نفسِه** فلا يفترق سعرا البوّابتين.
- **الربطُ بالبريد** (`services/freemius_link.py`): **صفحةُ Freemius لا تحمل حقلاً حرّاً يعود في الإشعار** (قِيس في شيفرتهم الرسميّة:
  `CheckoutPopupOptions` بلا `custom` ولا `metadata`)، فالبريدُ يُملأ من الحساب للقراءة وحدَها والإشعارُ يحمله، ويُكتب معرّفُ الدفعة على
  الطلب (`fs:<id>`) فلا تربط إعادةُ الإشعار طلباً ثانياً. **وحسابٌ بلا بريدٍ يُقال له أن يضيفه** (`requires_email`).
- **دورةُ الدفع عند Freemius `lifetime`** — هي اسمُهم للدفعة الواحدة غير المتجدّدة (لا يوميَّ ولا أسبوعيَّ عندهم: دوراتُهم شهريٌّ وسنويٌّ
  ومدى الحياة). **ومدّةُ الاشتراك تحسبها TAXO من خطّتها** كما في Digistore24. ويُكتب اسمُ الخطّة عندهم بمدّتها («X1 · يوم واحد» …)
  فلا يظنّ الدافعُ أنه يشتري وصولاً دائماً.
- **«بوابة الدفع بالبطاقة»** في «الإعدادات العامة» لكلِّ دولة: مطفأة · Digistore24 · Freemius، **والخادمُ يُطفئ الأخرى** حين تُشعَل واحدة
  (`settings_service.set_flag`) بقيد تدقيقٍ لكلٍّ منهما. **ومفتاحُ Play لـDigistore24 خارجها** — وFreemius لا مفتاحَ له في Play.
- **الترحيلة `0194`** — قيمةُ تعدادٍ وصفُّ طريقةٍ للأردن ومفتاحٌ مطفأ؛ **لا جدولَ مال**.

## ما لم يقع بعد ولماذا

- **التسجيلُ عند Freemius لم يتمّ من هذا الجهاز**: `freemius.com` و`dashboard.freemius.com` و`checkout.freemius.com` تُجيب Cloudflare
  «Sorry, you have been blocked» (`403`، Ray ID `a60c1b5f6a7b13b0`) لاتصال هذا الحاسوب، **وعنوانُه يُقرأ ليبيّاً** (ipinfo: LY)؛
  و`api.freemius.com` يجيب `200`. **وخادمُ الإنتاج يبلغها كلَّها (`200`)** — فالحجبُ على هذا الاتصال وحدَه، لا على الكباتن في الأردن.
  **ولا تجاوزَ للحجب** (لا VPN ولا وسيط): التسجيلُ خطوةُ المالك من اتصالٍ أردنيّ، ثمّ يُكمل الوكيلُ ما بعده.
  **وأُعيد القياسُ ٢٠٢٦-١١-٢٧ من متصفّح المالك نفسِه**: الصفحةُ نفسُها (Ray ID `a60c42c479a6e28d`) — فالحجبُ على الاتصال لا على الأداة.
- **قبولُ Freemius المبدئيّ وصل** (Leo E. Fajardo، ٢٠٢٦-١١-٢٦ 19:24 EET، في سلسلة «Card payments for TAXO»): اشتراكُ TAXO Driver
  الشهريّ «eligible in principle»، **بشرط أن تبقى أجورُ الرحلات والعمولةُ ورصيدُ الراكب وشحنُ المحفظة ودفعاتُ الكباتن خارج Freemius كلُّها**،
  و«You can proceed with registration and integration». **ولا Apple Pay ولا Google Pay عندهم** (Leo ١٩/١١)، وصرفٌ بحوالةٍ بالدولار.
- **إنشاءُ الخطط**: واجهتُهم البرمجيّة بمفتاح المنتج **تقرأ الخطط ولا تُنشئها** (`/products/{id}/plans.json` قراءةٌ وحدَها؛ الإنشاءُ في
  `/developers/{dev}/products/{id}/plans.json` — مقروءٌ من أنواع `@freemius/sdk@0.5.0`). فـ`scripts/freemius_plans.py` يحاول، **وإن رُفض
  قال ذلك بنصّه** وأنشأها المالكُ من اللوحة بالأسماء والأسعار التي يطبعها.

## مقارنةُ الرسوم (قِيست ٢٠٢٦-١١-٢٧)

- **Digistore24**: ‏7.9% + 1$ لكلِّ عمليّة شاملاً الدفع (Lorenz، تذكرة #4158620)، **ويُحجز 10% ضماناً ٦٠ يوماً**.
- **Freemius**: ‏3.8% + 0.50$ لكلِّ عمليّةٍ ناجحة **فوق رسم بوّابة الدفع** (صفحةُ أسعارهم ومدوّنتُهم «Freemius pricing update» — لم تُفتح
  الصفحةُ من هنا لأنها محجوبة، وقُرئت من نتائج البحث)، **ورسمُ البوّابة متغيّرٌ بالبطاقة والبلد ويقدّرونه هم بمتوسّط 3.5%** — فالمجموعُ
  التقديريّ ≈ 7.3% + 0.50$. لا رسمَ صرفٍ ولا تحويلِ عملةٍ منهم.

| ما يدفعه الكابتن | الدولار | Digistore24 | Freemius (تقديرٌ بمتوسّطهم) |
|---|---:|---:|---:|
| 3 د.أ (X1) | 4.25 | 1.34$ (31.4%) | ≈ 0.81$ (19.1%) |
| 17 د.أ (X7) | 24.00 | 2.90$ (12.1%) | ≈ 2.25$ (9.4%) |
| 45 د.أ (X30، «TAXO MAN 45») | 63.50 | 6.02$ (9.5%) | ≈ 5.14$ (8.1%) |
| 60 د.أ (X30-FULL) | 84.50 | 7.68$ (9.1%) | ≈ 6.67$ (7.9%) |

## أمرُ المالك ٢٠٢٦-١١-٢٧ — الإكمالُ في جلسته المفتوحة

> **النصُّ كما قاله المالك** (بالإنجليزيّة، حرفاً):
>
> Freemius account is now open and signed in on my computer browser (I signed in myself). Do everything else yourself in that open
> session, without stopping:
> 1. Work in the already-open Freemius tab/session. Do not sign out, do not change the account email or password, and do not open
>    security settings.
> 2. If the onboarding asks: account type Individual, name Mohammad Alsaidat, Madaba, Jordan, address Al-Khattabiya Street, Madaba,
>    96704, Jordan. Truthful only: "individual with sole activity", never "company".
> 3. Create the product if it does not exist: "TAXO Driver", type SaaS, website https://taxo.tajora.ly, free Freemius plan, no card.
> 4. Read the product ID and keys and store them only in the secrets places (C:\Users\loly3\.taxo-secrets\, /home/taxo/secrets mode
>    600, KeePass); list their places in SECRETS-INDEX.md. Never print them.
> 5. Create the four plans at the approved prices only: 4.25 / 24.00 / 63.50 / 84.50 USD, matching X1 / X7 / X30 / X30-FULL. No other
>    prices.
> 6. Set the webhook to https://api.tajora.ly/api/v1/payment-requests/webhook/freemius and verify the signature.
> 7. Test in sandbox only with a test account: payment, then the subscription is added once, then back to the app with the paid
>    notice. No real cards, no real money.
> 8. Deploy Freemius through the five gates (low memory allowed). Set the panel switch "بوابة الدفع بالبطاقة" for Jordan by this
>    rule: if Digistore24 is still not approved, switch to Freemius after the sandbox test passes; if Digistore24 is approved, keep
>    Digistore24 with Freemius as backup.
> Stop and tell me only if you hit: a password, OTP or 2FA prompt; a legal terms or agreement checkbox (I tick it myself); identity,
> bank, payout or tax steps; any paid plan or card request. Leave those steps to me.
> Continue the other open tasks after this. One report in Arabic. Never print secrets.

**ما تمّ (٢٠٢٦-١١-٢٧، وكيلُ التطبيقات)**: المتجرُ «TAXO» (22949) ومنتجُ «TAXO Driver» (46510، SaaS، الموقعُ مضبوط)، **وأربعُ خططٍ بدفعةٍ واحدة
بالأسعار حرفاً مقيسةً من واجهتهم** (X1 ‏4.25$ · X7 ‏24.00$ · X30 ‏63.50$ «TAXO MAN 45» · X30-FULL ‏84.50$؛ والمعرّفُ `x30_full` لأن الشرطةَ
تُرفض، والأقواسُ في العنوان تُرفض)، **والمفاتيحُ في `.taxo-secrets/freemius/` والخزنة** — **والمفتاحُ السرّيُّ ورمزُ الـAPI جُدِّدا قبل أيِّ
استعمال** بعد ظهور جزءٍ منهما في أداة قراءة الصفحة — والإشعارُ 9985 إلى العنوان المطلوب. **ولم تظهر خطوةٌ من الأربع التي يقف عندها الأمر.**

## قرارُ المالك ٢٠٢٦-١١-٢٧ — الاسترداد: بندٌ في الشروط، لا سطرٌ على شاشة الدفع

> **النصُّ كما قاله المالك** (بالإنجليزيّة، حرفاً):
>
> Correction to my last command (refund policy): do NOT add any refund line on the card payment screen. Cancel that item.
> 1. Keep the Freemius refund setting as "no refund". Do not change it.
> 2. Put the no-refund clause only in the TAXO terms and policies page (captain terms, payments section), in Arabic, French and
>    English, as a normal clause among the others: subscriptions paid by card are non-refundable after payment. No banner, no
>    highlight, no popup.
> 3. On the card payment screen keep only a small, plain "الشروط والسياسات" link (if one already exists, leave it as is). No refund
>    wording on the screen.
> 4. Double charge or a subscription that did not activate is a technical error, not a refund: log it in the panel for me to handle
>    manually. Never refund or move money yourself.
> 5. Record the decision in STATE.md and the Freemius design file.
> Commit with the pending Freemius fix after the running deploy ends. Do not interrupt the running deploy. Continue the planned steps.
> One report in Arabic.

**وكيف نُفّذ:**

1. **إعدادُ الاسترداد في Freemius على «No refunds»** كما وجدناه — لم يُمسّ.
2. **البندُ** (`backend/scripts/policies_card_refund_jo.py`): سطرٌ عاديٌّ آخرَ بنود القسم ٥ من **شروط كابتن الأردن** بلغاتها الثلاث —
   «- الاشتراكاتُ المدفوعةُ بالبطاقة المصرفيّة لا تُستردّ بعد الدفع.» · «- Subscriptions paid by bank card are non-refundable after
   payment.» · «- Les abonnements payés par carte bancaire ne sont pas remboursables après le paiement.» — نسخةٌ جديدةٌ منشورةٌ
   **بلا إعادة موافقة** («no popup»)، والسابقةُ مؤرشفة. **والأردنُّ وحدَه**: البطاقةُ الاحتياطيّةُ وDigistore24 له وحدَه، وشروطُ الجزائر
   وليبيا لا تُمسّ. **ويُنشر قبل رفع Freemius** لأن الموقعَ يخبز النصَّ المنشورَ وقت البناء والبوّابةُ الخامسةُ تقارن المخبوزَ بالمنشور.
3. **شاشةُ الدفع بالبطاقة** (`CardPayT2.tsx`): لم يكن عليها رابط، **فأُضيف رابطٌ صغيرٌ عاديٌّ «الشروط والسياسات»** بلون السطر الخفيف يفتح
   صفحةَ شروط الكابتن لبلده — **ولا كلمةَ استرداد على الشاشة**.
4. **الدفعُ المكرَّرُ والاشتراكُ الذي لم يُفعَّل في اللوحة**: «دفعةٌ وصلت ولم تُفعَّل» (`payment_stuck`) و«دفعٌ مكرَّر» (`payment_extra`)
   **كانا تنبيهين في جرس اللوحة**؛ **ودفعةُ Freemius التي لا طلبَ يطابقها** (بريدٌ بُدّل في صفحتهم، أو دفعةٌ ثانيةٌ على صفحةٍ أخذت الأولى
   طلبَها) **كانت سطرَ سجلٍّ لا يراه أحد** — فصارت تنبيهاً «دفعةٌ وصلت ولا طلبَ يطابقها — تُعالَج يدويّاً» (`payment_unmatched`) بمعرّف
   الدفعة عند Freemius. **ولا ردَّ مالٍ ولا نقلَه آليّاً في أيٍّ منها**؛ والدفعُ المكرَّرُ على طلبين يبقى كما بُني (§٨٢-أ/٢: مبلغُ الثاني
   في محفظة الكابتن ولا يُفعَّل اشتراكٌ ثانٍ) ويُرى في الجرس — **وما يُردّ إلى بطاقةٍ قرارُ المالك من لوحة Freemius**، وإشعارُ الاسترداد
   عندها يعكس ما قُيِّد بقيودٍ مقابلة.
