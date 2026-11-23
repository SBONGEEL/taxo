# Digistore24 لاشتراك الكبتن، ونسخةُ Huawei — التصميم (قرارا المالك ٢٠٢٦-١١-٢٣، البندان ٣ و٦)

> **الحال: مصمَّمان لم يُبنيا بعد** (الجلسةُ بلغت حدَّها بعد رفع كليك — انظر HANDOFF.md). **لا مالَ ولا عقدَ ولا حسابَ يُفتح**.

## Digistore24 — اشتراكُ الكبتن الشهريُّ وحدَه (البند ٣)

**على نمط القائم لا من الصفر**: `backend/app/services/payment_gateways/polar.py` (Polar، اشتراكُ الكبتن بالبطاقة) هو القالب —
`ProviderKey.DIGISTORE24` و`ProviderSpec` في `providers/registry.py` (حقولُ العقد: `product_id`، `ipn_passphrase`، `api_key`، `test_mode`)،
و`payment_gateways/digistore24.py` بـ`build_digistore24(values)`.

1. **الدفعُ المستضاف**: `POST /driver/subscriptions/digistore24/checkout` ⇐ صفُّ `provider_orders` (`provider=digistore24`، `status=pending`،
   **المبلغُ من سعر الاشتراك القائم — لا سعرَ جديد**) ⇐ رابطُ طلب Digistore24 (`https://www.digistore24.com/product/<product_id>?custom=<order_id>`)
   فيُفتح في المتصفّح الخارجيّ.
2. **الإشعار** (`POST /webhooks/digistore24`، IPN): **يُتحقّق من التوقيع** (`sha_sign` بعبارة IPN وفق مستندهم) قبل أيِّ قراءة؛ توقيعٌ خاطئٌ ⇐ ٤٠٣
   بلا كتابة. `event=on_payment` بـ`custom=<order_id>`: **قفلُ صفِّ الطلب** ثمّ **قفلُ صفِّ الكبتن** (الترتيبُ القائم: provider-order ثمّ driver)،
   والطلبُ `pending ⇒ paid` مرّةً واحدة، **ويُكتب صفُّ `driver_subscriptions` بعد وصول المال وحدَه** (لا حالةَ pending فيه — ثابتُ SPEC).
   **PENDING/APPROVED** حالتا `provider_orders` لا الاشتراك: `pending` حتى الإشعار، و`paid` (= APPROVED) بعده. الإشعارُ المكرَّر يُجاب ٢٠٠ بلا قيدٍ ثانٍ
   (مفتاحُ تكرارٍ `dg24:<order_id>`). `on_refund`/`on_chargeback` ⇐ يُسجَّل وينبَّه المالك **ولا يُلغى اشتراكٌ آليّاً** (قرارُ مال).
3. **المفتاح** `digistore24_subscription_enabled` لكلِّ دولة، غائبٌ = مطفأ؛ ويُخفى الزرُّ آليّاً بلا عقدٍ فعّال كالقائم.
4. **وضعُ الاختبار**: حقلُ `test_mode` في العقد، وطلبٌ تجريبيٌّ من لوحتهم حين يفتح المالكُ الحساب — **ويبقى المفتاحُ مطفأً حتى كلمته**.
5. **الاختبارات**: توقيعٌ صحيحٌ وخاطئ، تكرارُ الإشعار، **تزامنُ إشعارين** (`asyncio.gather`) ⇐ اشتراكٌ واحد، ويسقط بحذف القفل.

## نسخةُ Huawei (البند ٦)

**نكهةٌ رابعة** في `productFlavors` للتطبيقين: `huawei` **بلا لاحقة** (أسماءُ الحزم نفسُها `ly.tajora.rider`/`ly.tajora.driver` كما أمر المالك)،
وتُوقَّع بمفتاح الرفع المحفوظ. **ولا تمسّ `public`** (Play والموقع):
- **Firebase يُستبعد منها وحدَها**: `huaweiImplementation "com.huawei.hms:push:<إصدار>"` و`agconnect-services.json` في `src/huawei/`
  (يُنزَّل من حساب AppGallery — **ينتظر حسابَ المالك**)، وتبعيّاتُ Firebase/Play Services بـ`publicImplementation` بدل `implementation`.
- **الإشعارات**: خدمةٌ في `src/huawei/java/…/HmsPushService.java` تمرّر الرسالةَ إلى المسار نفسِه الذي يستعمله FCM (الرنينُ فوق القفل، القنوات)،
  ورمزُ الجهاز يُسجَّل في `device_tokens` بنوعٍ جديد `hms` — **ويحتاج مزوّدَ إرسالٍ في الخلفيّة** (`push/hms.py`) خلف عقده.
- **الموقع**: `LocationManager` في أندرويد (لا Fused) حين تغيب خدمات Google — يُفحص ما يستعمله التطبيقُ اليوم أوّلاً.
- **التحديثات**: لا نافذةَ Play؛ فحصُ «الإصدار الإلزاميّ» القائم في اللوحة بمصدر `huawei`.
- **الاختبار**: محاكٍ بصورة AOSP **بلا Google APIs** (على D، ذاكرة `emulator-shell-proof`)، كلُّ شيءٍ عدا الإشعارات؛ **وقبل أيِّ إصدارٍ** يُقاس أنّ
  `assemblePublicRelease` يُخرج الحزمةَ نفسَها بايتاً بلا HMS (`apkanalyzer` / قائمةُ الملفّات).
