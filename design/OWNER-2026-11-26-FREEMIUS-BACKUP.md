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
