# SPEC-DELIVERY.md — توسعة TAXO للتوصيل

| البند | القيمة |
|---|---|
| النسخة | 0.2 — مسودة للمراجعة، **صُحِّحت أسماؤها على الشجرة** (المرحلة 0، 2026-09-19) |
| التاريخ | 2026-09-19 (0.1: 2026-09-18) |
| الحال | §D0 موقَّع · §D1 بعضه موقَّع (✓) والباقي بانتظار المالك · §D11 أسئلة مفتوحة |
| الشجرة المقيسة | إيداع `5eadb43`، ترحيلة `0071`. كل اسم في الملف إمّا **قائم** (ومعه موضعه) أو **يُبنى** (جديد صراحةً) — وقائمة "يُبنى" كاملةً في §D20 |
| العلاقة بـ SPEC.md | يرث كل قواعده (§4 المال، §5 الاستعلامات، §17 الأخطاء، §22 سياق الفعل، §18.1 النشر) ولا يعدّل فيه حرفاً. عند التعارض يغلب SPEC.md إلا حيث ينصّ هذا الملف على استثناء موقَّع باسمه |
| المسار | يُوضع في جذر المشروع بجانب SPEC.md |

المسمّيات: TAXO MARKET (تطبيق الزبون — متاجر متعددة الفئات لا مطاعم فقط، وقسم المطاعم داخله باسم **TaxoEat**) · TAXO MERCHANT (تطبيق التاجر: مطعم أو متجر) · TAXO DRIVER (تطبيق الكبتن القائم) · اللوحة (لوحة الإدارة القائمة). اسم المنصّة يُكتب TAXO باللاتينية في كل موضع، والأرقام لاتينية في كل الشاشات.

---

## §D0 القرارات المؤسِّسة (موقَّعة)

1. **حساب الزبون مستقل تماماً عن حساب الراكب** — بيانات ومحفظة وسجلّ وإشعارات مستقلة (شكل الاستقلال في §D1.4).
2. **الربح من التجار**: عمولة على كل طلب أولاً، و**لا اشتراك على التجار مبدئياً** — التسجيل والخدمة مجاناً مدةً يحدّدها المالك؛ والاشتراك مبنيّ في النموذج ومطفأ (§D1.9).
3. **وضع التوصيل حصري**: كبتن في وضع التوصيل لا تصله رحلات، مع استثناء يُفعَّل من اللوحة.
4. الكبتن يبدّل بين الركاب والتوصيل **من الواجهة نفسها بكبسة زر**، ووضع التوصيل يفتح صفحة خاصة بعمل التوصيل وعدد الطلبات.
5. التوصيل عبر **كباتن TAXO DRIVER أنفسهم** — لا أسطول ولا تطبيق توصيل منفصل.
6. الزبون يطلب من **المطاعم والمتاجر المسجّلة**، بمحفظة، ويرى **مراحل التحضير** و**تتبّع الكبتن**.
7. **اشتراك واحد للكبتن يغطّي الركاب والتوصيل معاً** — لا اشتراك ثانٍ ولا رسم إضافي ولا عمولة على دخل التوصيل. هذا الفارق المعلَن عن المنافسين، ويُكتب في شاشة الترحيب وفي صفحة الاشتراك بنصّ صريح.
8. **رسوم خدمة رمزية على الزبون** ممكنة في النموذج، افتراضها صفر، تُضبط من اللوحة لكل دولة وتُعرض بنداً مستقلاً في الفاتورة (§D1.9).
9. **الإطلاق الأول في الأردن** — كل قرار في هذا الملف يُقاس بسوق الأردن أولاً؛ وليبيا بعده بالمفاتيح نفسها (§D9 و§D13).
10. **المبدأ العام**: كل النسب تبدأ من أدنى ما يمكن (أو صفر) ليسهل الدخول على الجميع، ثم يرفعها المالك من اللوحة وحده — فالنموذج يبني **الأدوات** لا القيم، ولا رقم مكتوب في الكود.

---

## §D1 القرارات الافتراضية — بانتظار توقيع المالك

| # | القرار | الافتراض | البديل | أثره على النموذج | ✓ |
|---|---|---|---|---|---|
| 1 | سريان المال | **موقَّع (2026-09-19)**: طلب الكاش — الكبتن يدفع `merchant_net` نقداً عند الاستلام ويقبض `total` من الزبون، وما قبضه نيابةً (عمولة المتجر + رسوم الخدمة) **صفّا دَين في `driver_debts`** بمصدرين مسمّيين، يحكمهما `debt_blocked` و`driver_debt_ceiling` القائمان ويُحصَّلان من أرباح لاحقة كما يُحصَّل `ride_commission`. طلب المحفظة — الكبتن **لا يدفع للمطعم شيئاً**، و`merchant_net` يُقيَّد مستحقاً للتاجر على TAXO ويُسوّى دورياً (§D18.2). ولا دَين بين الكبتن والتاجر في أي حال (§D18.3) | — | لا رصيد سالب في أي محفظة (قيد `wallet_balance_non_negative`، `models/wallet.py:111`) | ☑ |
| 2 | رسوم التوصيل | أساس + للكيلومتر لكل دولة من اللوحة، بحدّ أدنى وأقصى، **للكبتن كاملة** بلا حصة لـTAXO (تطبيقاً لقرار §D0.7) | حصة لـTAXO منها بنسبة من اللوحة | إعداد `delivery_commission_percent` لا يُعلَن الآن (§22.0) — ولا وجود له في `delivery_settings` (§D2) | ☐ |
| 8 | دخل التوصيل | **موقَّع (2026-09-19)**: `billing_mode` مفتاح في اللوحة بقيمه الأربع يضبطه المالك وقتما شاء؛ وقيمة الصفّ عند إنشاء الجدول `commission_only` مع `merchant_commission_percent = 0` ورسوم خدمة صفر — فالأثر الفعلي مجّاني والمفتاح بيد المالك بلا نشر (§D1.9) | — | النموذج يبني الأدوات لا القيم | ☑ |
| 3 | الإسناد | **موقَّع (2026-09-19)**: "حلقة ثانية للطلبات تعيد استعمال الأجزاء النقيّة — `geo.nearby` و`_eligible_levels` والتبريد و`DispatchRules` — وقفل العرض نفسه `dispatch:driver_offer:{driver_id}` كي لا يجتمع على الكبتن عرض رحلة وعرض طلب". والحصرية شرط واحد في `_eligible_levels` (§D1.3، §D4) | — | حلقة `_run` القائمة مربوطة بالرحلة من أولها إلى آخرها، فالقول القديم "لا كود إسناد جديد" كان خطأً في الملف | ☑ |
| 4 | حساب الزبون | **موقَّع (2026-09-19): حساب منفصل تماماً بمفتاح مركّب `(phone, account_kind)`** — لا `(phone, app)` لأن الراكب والكبتن حساب واحد عبر تطبيقين. التفصيل والعلّة والتوقيت في §D1.4 و§D6.1، والتنفيذ في المرحلة 1-أ (§D9.1) | — | يُسقط القيد الفريد على `users.phone` وعلى البريد المُثبَت ويحلّ محلّهما مركّبان | ☑ |
| 5 | المطعم | **موقَّع**: تاجر ← فروع من البداية؛ تسجيل ذاتي باعتماد على مسار وثائق الكباتن؛ حساب واحد للتاجر | — | — | ☑ |
| 6 | القائمة | **موقَّع**: أقسام + أصناف + مجموعات خيارات (فردي/متعدد، فرق سعر) من البداية؛ وتجميد الاسم والسعر والخيارات على سطور الطلب لحظة إنشائه | — | — | ☑ |
| 7 | الأسماء | TAXO MARKET: `ly.tajora.market` · market.tajora.ly — **TaxoEat قسمٌ داخل التطبيق لا تطبيق** (§D1.8): بلا معرّف حزمة ولا نطاق ولا نكهة — TAXO MERCHANT: `ly.tajora.merchant` · merchant.tajora.ly — تطبيقان جديدان في `channels.json`. **وشكل الملف في الشجرة**: `channels.{public,…}.apps.{customer-app,driver-app,admin-panel}` مع `baseAppId` لكل تطبيق — فالإضافة مفتاحا تطبيق تحت **كل** قناة ومدخلان في `baseAppId`، لا "نكهة" بالمعنى الأندرويدي. ومعهما قيمتان جديدتان في `ClientApp` (اليوم `rider · driver · panel`، `models/enums.py`) — §D2 | — | — | ☐ |

### §D1.1 سريان المال بالتفصيل

يُعرَّف لكل طلب: `subtotal` (الأصناف) · `commission_amount = round(subtotal × commission_percent_at_order, 3)` (على التاجر) · `merchant_net = subtotal − commission_amount` · `delivery_fee` (للكبتن كاملة) · `service_fee` (على الزبون، افتراضه 0.000) · `total = subtotal + delivery_fee + service_fee`.

| الطلب | عند الإنشاء (`placed`) | عند الاستلام من المطعم | عند التسليم للزبون | ما يُكتب عند التسليم | صافي TAXO |
|---|---|---|---|---|---|
| كاش | لا قيد | الكبتن يدفع `merchant_net` نقداً | الكبتن يقبض `total` نقداً ويحتفظ بـ`delivery_fee` منه | **صفّا دَين** في `driver_debts` لا قيدان في المحفظة: مصدر `store_commission` بمبلغ `commission_amount`، ومصدر `service_fee` بمبلغ `service_fee` (الصفر لا يُنشئ صفّاً — قيد `driver_debt_amount_positive`). يُعرضان للكبتن: **"عمولة المتجر — محصَّلة نقداً"** و**"رسوم خدمة — محصَّلة نقداً"** | `commission_amount` + `service_fee` |
| محفظة | محفظة الزبون: **خصم `total` كاملاً** بقيد `delivery_order_payment` (يُبنى) — لا حجز | **لا يدفع شيئاً**، ويُكتب له صراحةً "لا تدفع شيئاً" | لا نقد | محفظة الكبتن: +`delivery_fee` بقيد `delivery_earning` (يُبنى)؛ محفظة التاجر (`merchant`): +`merchant_net` بقيد دائن في `wallet_transactions` (§D6، قرار Q20) | `commission_amount` + `service_fee` |

**ومصادر الدَّين الثلاثة** (قرار المالك 2026-09-19) قيم جديدة في `DriverDebtSource` (اليوم عضو واحد: `ride_commission`، `models/enums.py:199`): `store_commission` · `service_fee` · `goods_price` — **والثالث محجوز لبند الدفع المؤجَّل (§D18.5) ولا يُكتب الآن**. التفريق بالمصدر يجعل الكشف والسقوف تقرأ كل نوع باسمه.

**وتحصيلها بالآلية القائمة حرفياً**: `debts.collect_from_balance` يُنادى حين يدخل مال محفظة الكبتن، ويحصّل **صفّاً كاملاً فأكمل من الأقدم** بقيد `commission` (`services/debts.py:161-212`)، والمنع بـ`debts.refresh_block` فوق `payment_settings.driver_debt_ceiling` (و`NULL` = لا سقف). ويلزم في `driver_debts` عمود `delivery_order_id` وقيد تفرّد `(delivery_order_id, source)` — القيد القائم `driver_debt_once_per_payment` على `(payment_id, source)` ولا دفعةَ `payments` للطلب.

- المطعم يرى على شاشة الطلب بنداً واحداً بالخط الكبير: **"المستحق نقداً من الكبتن: X.XXX"** = `merchant_net` — لا نزاع عند التسليم لأن الرقم مكتوب قبل أن يصل الكبتن.
- المطعم يرى في التقرير: الأصناف · العمولة · الصافي، لكل طلب ولكل يوم (يوم الدولة بمنطقة وقتها).
- **سقف التعرّض النقدي للكبتن**: `cash_exposure_cap = min(computed, drivers.cash_exposure_cap_override)` بشكل سقف السلفة (قيمة محسوبة لا عمود)؛ الطلب لا يُعرض على كبتن يتجاوز مجموع `merchant_net` لطلبات الكاش الجارية معه سقفه، ويُقرأ معه `cash_on_hand_limit` الذي يعلنه الكبتن (§D4) والأدنى يحكم.
  - **ما أُثبت من الشجرة**: سقف السلفة `advances.cap_for` (`services/advances.py:392`) = `min(computed, drivers.advance_cap_override)`، و**`computed` ليس من المستوى**: هو سعر الخطة اليومية النشطة (`advances.daily_plan_price`) × مضاعف يبدأ 100% ويزيد `growth_percent_per_repaid` لكل سلفة مسدَّدة حتى `max_multiplier_percent` (`advance_settings`). والتخصيص الإداري يخفض ولا يرفع، و`NULL` لا تخصيص وصفرٌ منع.
  - فقاعدة `computed` لسقف النقد **لم تُقرَّر**: نسخ `cap_for` حرفياً يجعل سقف النقد = سقف السلفة. سؤال §D11-Q21.
  - وأقرب ما في الشجرة إليه: `payment_settings.driver_debt_ceiling` + `drivers.debt_blocked` (الترحيلة `0061`) — سقف على **الدَّين القائم** لا على النقد الجاري، ويبقى كما هو.
- **تسمية البنود على الكبتن شرطٌ لا تجميل** (§D0.7): ما يُخصم منه ليس عمولةً عليه بل مالٌ قبضه نيابةً عن غيره. فلا تظهر في تطبيقه ولا كشفه كلمة "عمولتك" ولا "عمولة على أرباحك"، وصفحة أرباح التوصيل تبدأ بسطر ثابت: **"لا عمولة على دخل التوصيل — اشتراكك يغطّي الركاب والتوصيل"**. ويختبر اختبار أن مجموع ما يُخصم من الكبتن في أي طلب = `commission_amount` + `service_fee` بالضبط، أي صفرٌ من جيبه.
- **الكبتن لا يموّل طلبات المحفظة من جيبه**: في طلب المحفظة الزبون دفع لـTAXO سلفاً، فلا معنى لأن يخرج الكبتن نقداً من جيبه ليستردّه لاحقاً. التاجر يُقيَّد له المبلغ ويُسوّى دورياً (§D18) — وهذا يخفض حاجة الكبتن إلى النقد ويُبقي سقف التعرّض النقدي محصوراً في طلبات الكاش وحدها.
- المال لا يُمثَّل برصيد سالب: ما على الكبتن يصير صفّ دَين (`driver_debts`)، وما على TAXO للتاجر يصير قيداً دائناً في محفظته `merchant` (§D6) — لأن المحفظة لا تقبل السالب (`wallet_balance_non_negative`، وقرار المالك القائم "لا رصيد سالب في المحفظة إطلاقاً" المنقول في رأس `services/debts.py`). **ولا يُكتب في هذا الملف "المحفظة بنك تسمح بالسالب" في أي موضع.**

### §D1.2 رسوم التوصيل

`delivery_fee = clamp(delivery_base_fee + delivery_per_km × distance_km, delivery_min_fee, delivery_max_fee)`، والمسافة من Mapbox Directions (الفرع ← الزبون) بالوحدة القائمة في الرحلات (`services/directions.py`)، وتُجمَّد على الطلب لحظة إنشائه (`distance_km`, `delivery_fee`). فوق `delivery_max_distance_km` يُرفض الطلب بخطأ `out_of_delivery_radius`. الإعدادات الخمسة لكل دولة في `delivery_settings` (يُبنى، §D2).

### §D1.3 الإسناد

#### كيف يعمل إسناد الرحلات اليوم — مُثبَت من الشجرة (2026-09-19)

الوحدة: **`backend/app/services/dispatch.py`**، وقواعدها في `services/dispatch_settings.py` وجدول `dispatch_settings` (الترحيلة `0062`)، والحضور في `services/geo.py`.

| البند | السلوك كما هو |
|---|---|
| المُطلِق | `dispatch.start(ride_id)` **بعد** الـcommit — من `routers/rides.py:152` ومن `services/bookings.py:470` (الرحلات المجدولة). مهمّة asyncio داخل عملية التطبيق لا Celery، ويوقفها `dispatch.stop` عند إلغاء الراكب |
| القواعد | تُقرأ **مرّةً عند البدء** من `dispatch_settings` لكل دولة (`rules_for`)، وغياب الصفّ = `DEFAULTS`: النمط `sequential`، مهلة العرض **7 ث** (`offer_timeout_seconds`)، **5** محاولات (`max_attempts`)، سقف كلّي **120 ث** (`total_timeout_seconds`)، تبريد **30 ث** (`cooldown_seconds`)، دفعة البثّ **4** (`broadcast_batch_size`) |
| النمط | `sequential`: الأقرب المؤهَّل وحده. `broadcast`: أول 4 معاً، وأول من يقبل يأخذ (الفصل بقفل صفّ الرحلة في `searching → accepted`) |
| البحث | `geo.nearby` على `geo:drivers:{country}` في Redis GEO: **3 كم** ثم **7 كم** (`SEARCH_RADIUS_KM` / `MAX_SEARCH_RADIUS_KM`)، و**10 كم** في الطلب المجنَّس (`GENDERED_MAX_SEARCH_RADIUS_KM`، `geo.py:33-38`). ويُصفّى بفئة المركبة من `geo:presence:{driver_id}` |
| الأهلية | `_eligible_levels` (`dispatch.py:355-441`) — استعلام واحد: `status = approved` · `is_online` · `current_ride_id IS NULL` · `advance_blocked = false` · `cancellation_carry_blocked = false` · `debt_blocked = false` · مركبة من الفئة · اشتراك سارٍ (`subscriptions.covered_driver_ids_subquery`) · بلا رحلة في `ACTIVE_DRIVER_STATUSES` · ومطابقة الجنس إن كانت `women_service_enabled` مشتعلة. **وخريطة الراكب تقرأ الدالة نفسها** (`eligible_driver_ids`) |
| الترتيب | الأقرب أولاً، ومع أكثر من مرشَّح يُطرح **خصم المستوى بالأمتار** (`missions.discounts_for`، `level_settings.discount_meters` بسقف `MAX_LEVEL_DISCOUNT_METERS = 100`) — `dispatch.py:527-540` |
| قفل العرض | `dispatch:driver_offer:{driver_id}` يُكتب بـ`NX` وبعمر المهلة (`_reserve_offer`) — فلا يُعرض على كبتن طلبان في آن؛ ومعه `dispatch:offer:{ride_id}` و`dispatch:broadcast:{ride_id}` و`dispatch:driver_offer_km:{driver_id}` |
| الرفض والصمت | إشارة في `dispatch:signal:{ride_id}` توقظ الحلقة؛ الرافض والصامت يدخلان **تبريداً 30 ث** (`dispatch:cooled:{ride_id}`) لا استبعاداً دائماً، والمحجوز بعرض آخر يُبرَّد كذلك |
| الانتهاء | بعد 5 محاولات أو 120 ث: `no_driver_found`. وغياب أي كبتن قريب لا يُحتسب محاولة (انتظار 3 ث، `IDLE_POLL_SECONDS`) |
| سجلّ العروض | **لا يوجد**: `ride_offers` رُفض في المرحلة 4 بحكم §5-ج من SPEC.md |
| الاستعادة | `pending_offer_frame` يعيد بطاقة العرض لكبتن عاد من انقطاع بمهلتها المتبقّية من `TTL` |

**وما يجعل "فلتراً واحداً" خطأً**: حلقة `_run` (`dispatch.py:707-887`) مربوطة بالرحلة في كل خطوة — قفل صفّ `Ride`، وحالة `RideStatus.SEARCHING`، و`rides_service.mark_searching`، وحمولة `RideOut`، و`notifications.publish_ride_offer`، ومسار `accept_ride`، ومفاتيح Redis بـ`ride_id`.

#### ما يُبنى للتوصيل (القرار الموقَّع §D1 #3)

- **حلقة ثانية للطلبات** في `services/delivery_orders.py` (أو وحدة إسناد بجوارها) تعيد استعمال الأجزاء النقيّة: `geo.nearby` · شروط `_eligible_levels` · التبريد (`cool_down`/`cooled_drivers` بمفاتيح الطلب) · `DispatchRules` و`rules_for` · وقفل العرض **نفسه** `dispatch:driver_offer:{driver_id}` — فكبتن معروض عليه رحلة لا يُعرض عليه طلب، والعكس.
- **الحصرية شرط واحد** يُضاف إلى مصفوفة `conditions` في `_eligible_levels`: الكبتن في `delivery_mode` لا يُرشَّح لرحلة إلا بالاستثناء وبلا طلب جارٍ (§D4). وبما أن خريطة الراكب تقرأ الدالة نفسها، **يختفي كبتن التوصيل منها نتيجةً مقصودة** (§D4).
- وشروط الطلب في حلقته: في `delivery_mode` (أو بالاستثناء) · ضمن `delivery_dispatch_radius_km` من الفرع · دون سقف النقد لطلبات الكاش · عدد طلباته الجارية دون `max_concurrent_orders`.
- الترتيب والنمط والمهلة والتبريد **من `dispatch_settings` نفسه** — لا إعداد إسناد ثانٍ للتوصيل ما لم يُقرَّر (§22.0).
- توقيت الإسناد: عند **قبول المطعم** (`accepted`) مع `expected_ready_at` في العرض ليوقّت الكبتن وصوله. إن بلغ الطلب `ready` ولم يُسند خلال `ready_unassigned_alert_min` يُنبَّه المشرف ويُخبر الزبون "جارٍ البحث عن كبتن".
- كل عرض صفٌّ في `delivery_assignments` (قبول/رفض/مهلة)، **يُكتب بعد إرسال العرض وخارج مسار الترتيب** (قرار المالك 2026-09-19). وبقي سؤالاً: §5-ج من SPEC.md يسمّي نافذة التوزيع "حتى قبول العرض" مساراً حرجاً — فالكتابة بعد الإرسال ما زالت داخل النافذة بنصّها (§D11-Q22).

### §D1.4 حساب الزبون

- **قرار المالك (2026-09-19، §D1 #4): حساب الزبون منفصل تماماً** — صفٌّ مستقل في `users` بمفتاح مركّب **`(phone, account_kind)`**، و`account_kind ∈ {taxo, market, merchant}` (التاجر نوع ثالث — §D1.5، Q40). **لا `(phone, app)`**: الراكب والكبتن **حساب واحد عبر تطبيقين** (§21 و§23 من SPEC.md)، ومفتاح بالتطبيق يشقّهما.
- **ما اشتراه المالك بالثمن**: كلمة مرور منفصلة · حظر منفصل (`is_blocked`) · تجميد منفصل · سجلّ ومحفظة وإشعارات وصندوق وارد ورموز أجهزة وبطاقات محفوظة **لا تلتقي** — لأنها كلّها معلّقة بـ`user_id` وهو غيرٌ في الحسابين. **وثمنه**: إسقاط قيدين فريدين قائمين، ودخول يسأل "أيّ حساب؟"، وثغرة رمز تحقق تُغلق أولاً (§D7)، وزرّ تبديل راكب↔زبون **مستحيل بالبناء** (وهو مؤجَّل أصلاً، §D10).
- **وعلّة توقيته**: المشروع في **اختبار مغلق** — لا مستخدمين حقيقيين، وكل صفوف الإنتاج بيانات اختبار من إنشاء المالك. **فالثمن اليوم أدنى ما يكون**؛ وتأجيله إلى ما بعد الإطلاق يعني ترحيل حسابات حقيقية بلا توقّف وبلا أن يفقد أحد كلمة مروره — عملٌ أثقل وخطرُه على ناس.
- التسجيل من TAXO MARKET بمسار OTP/كلمة المرور القائم، **مع `account_kind = market`**؛ والحساب يحمل دور `customer` (قيمة جديدة في `user_role`) لا `rider`.
- الاستقلال = محفظة بغرض `customer` على حساب `market`، وسجلّ طلبات وعناوين وإشعارات خاصة، **ولا صلة في النموذج بحساب الراكب** بالرقم نفسه — ولا يظهر في TAXO MARKET أي أثر لكونه راكباً.
- المحفظة تُعلَن بسياق الفعل (§22): `wallet.owner_type_for(user, declared=…)` هو الباب القائم، ونداء من TAXO MARKET يعلن `customer`.
- شحن محفظة الزبون بقنوات `TopupMethod` القائمة (`cliq` · `cash` · `card`) وبلا سحب. شحن CliQ الآلي يمرّ بـ`provider_orders` بغرض `wallet_topup`، ويُختم نوع المحفظة في `provider_orders.opened_from_app` (`services/cliq_topups.py:130`).
- **لا حجز**: الطلب بالمحفظة يُخصم كاملاً لحظة `placed` ويُردّ بـ`refund` القائم (§D6).
- ومفتاح التفرّد في الدفتر `(owner_id, idempotency_key)` (`models/wallet.py:114`) مشترك بين محافظ الشخص الواحد، فمفاتيح قيود الطلب تحمل بادئة الطلب (`delivery_order:{id}:…`) كي لا تتصادم مع قيد رحلة للشخص نفسه.
- زرّ التبديل راكب↔زبون: **لا يُبنى** في الإصدار الأول (D10).

### §D1.5 التاجر والفروع

- **التاجر ليس مطعماً بالضرورة**: الفئة حقل على التاجر تفرز بها الواجهة وتُصنَّف بها التقارير، ولا تغيّر دورة حياة الطلب ولا نموذج المال. المطعم والمقهى والحلويات والمخبز والبقالة تجّار بالنموذج نفسه؛ ما يختلف مبيَّن في §D10.
- **الأقسام**: الفئات تُجمَّع في أقسام داخل TAXO MARKET، أولها **TaxoEat** (مطعم · مقهى · مخبز · حلويات)، وما بقي تحت أقسامه بأسمائها الوصفية حتى تُسمّى (§D11-Q11). القسم يُشتقّ من الفئة ولا يُخزَّن (§22.0)، والخريطة (فئة ← قسم) مصدر واحد تقرأه الخلفية والتطبيق تحت check:enums.
- **متجر TAXO الغذائي**: تاجر في الجداول نفسها بعلامة `owned_by_taxo`، فلا كود خاص به — أثرها في §D11-Q9 وحده (العمولة والاشتراك).

- `merchants` (الكيان التجاري، مالكه مستخدم بدور `merchant`) ← `branches` (موقع، ساعات، توفّر). القائمة على مستوى التاجر، والتوفّر والساعات على الفرع.
- **حساب التاجر نوع ثالث (قرار المالك 2026-09-19، Q40)**: `account_kind ∈ {taxo, market, merchant}`. **العلّة**: التاجر يدخل من تطبيقه بكلمة مروره، وحظره وتجميده لا يمسّان حسابه الشخصي كراكب؛ والقيمة تُكتب في ترحيلة 1-أ نفسها، فثمنها الآن صفر، بينما إضافتها لاحقاً ترحيلة ثانية على الجدول نفسه.
- **تعدّد المتاجر للشخص الواحد (قرار المالك 2026-09-19، Q34)**: **لا قيد فريد على `merchants.owner_user_id`** — الشخص قد يملك أكثر من نشاط. **والمشرف يقرّر عند الإنشاء**: نشاطان مستقلان (تاجران، لكلٍّ قائمته ودوريته وكشفه وتسويته) أم نشاط واحد بفرعين (تاجر واحد وفرعان). **وأثره على مفتاح المحفظة لم يُحسم بعد** — الخياران بالأرقام في §D6 (Q38).
- التسجيل الذاتي من TAXO MERCHANT: بيانات التاجر + أول فرع + وثائق **على شكل مسار وثائق الكباتن** — وما أُثبت منه:
  - **الجدول خاصّ بالكبتن**: `driver_documents` بعمود `driver_id` وقيد `(driver_id, doc_type)` و`DocumentType` لأنواع الكبتن — **لا `subject_type`**. فـ`merchant_documents` جدول جديد بالشكل نفسه (`file_path` · `content_type` · `size_bytes` · `review_status` · `review_note` · `reviewed_by` · `reviewed_at`).
  - **الحفظ**: `core/storage.save(reader, folder=…)`، والسقف `settings.document_max_bytes = 2 * 1024 * 1024` (`core/config.py:74`). **ولا جدول رفع عامّاً** (`uploads` غير موجود): الملف مسار نصّي على الصفّ الذي يملكه.
  - **الضغط** 1600/0.8: `MAX_EDGE`/`QUALITY` في `driver-app/src/lib/shrink.ts:22,25` — في تطبيق الكبتن وحده، فينسخه TAXO MERCHANT أو يُرفع إلى مكان مشترك (قرار بناء في المرحلة 3).
  - **عارض الصور في اللوحة**: `DocumentPreview` دالّة محلّية في `admin-panel/src/screens/Drivers.tsx:141` تأخذ `driverId` — ليست مكوّناً مشتركاً. استعمالها للتاجر يعني استخراجها مكوّناً، وهو مسّ لشاشة الكباتن.
- **الوثائق (قرار موقَّع)**: هوية المالك وصورة واجهة المحل **إلزاميتان**، والسجل التجاري **اختياري** — لأن كثيراً من المطاعم الصغيرة بلا سجل، وفرضه يقفل باباً واسعاً. **وهذا افتراض الأردن الأول لا ثابت في الكود** (القرار التالي).
- **الوثائق تختلف لكل دولة وتُضبط من اللوحة (قرار المالك 2026-09-19، Q8)**: قائمة أنواع وثائق التاجر **لكل دولة**، ولكل نوع اسمه وإلزاميّته.
  - **كيف تُعرَّف أنواع وثائق الكبتن اليوم — مُثبَت**: **تعداد في الكود لا صفوف في القاعدة**. `DocumentType` (`models/enums.py:58`) أحد عشر عضواً، وعمود `driver_documents.doc_type` نوع postgres `document_type`؛ والإلزامية ثابت في الكود `REQUIRED_DOCUMENT_TYPES` (`models/driver.py:277`) ودالّة `required_document_types` (`:286`) تضيف `profile_photo` بشرط الجنس؛ **ولا شيء لكل دولة**؛ والأسماء العربية مرايا في التطبيقات (`DOC_LABEL` في `admin-panel/src/screens/Drivers.tsx:97`) تحت `check:enums`.
  - **فالضبط من اللوحة لكل دولة تغيير في النمط** لا امتداد له: الأنواع تصير **صفوفاً** في جدول جديد `merchant_document_types` (`country_code` · `key` · `name` · `required` · `is_active` · `sort_order`)، و`merchant_documents.doc_type` يصير مرجعاً إليه **لا تعداد postgres**؛ والاسم العربي يأتي من الصفّ لا من مرآة في التطبيق — **فلا يحرسه `check:enums`**، ويُحرس بدلاً منه باختبار أن كل نوع إلزامي لدولة التاجر له وثيقة معتمدة قبل `active`.
  - **الكلفة التقديرية**: جدول وترحيلة · باب قراءة للتطبيق (أنواع دولته) · بابا لوحة (قائمة + إنشاء/تعديل/إيقاف، تحت `check:doors`) · شاشة في اللوحة · شرط الاعتماد يقرأ الصفوف · بذرة الأردن بالافتراض أعلاه — نحو **7–9 ملفات و15–20 اختباراً** في المرحلة 1. **ونوع يُوقَف لا يُحذف** ما دامت وثائق قائمة تشير إليه.
  - **ولا يمسّ وثائق الكباتن**: تبقى تعداداً كما هي.
- الحالات: `pending_review → active → suspended` و`rejected`؛ الإيقاف بسبب مكتوب يراه التاجر بالعربية.
- شرط الظهور للزبون: `active` **و**اشتراك سارٍ — **إن شمله `billing_mode`** (مطفأ في الإطلاق، §D1.9) — **و**فرع مفتوح الآن.

### §D1.9 نموذج الدخل والمجّانية المؤقتة

`billing_mode` لكل دولة من اللوحة، وقيمه: `commission_only` · `subscription_only` · `both` · `free` (لا عمولة ولا اشتراك — للإطلاق).

**قرار المالك (2026-09-19، §D1 #8)**: `billing_mode` **مفتاح في اللوحة بقيمه الأربع، يضبطه المالك وقتما شاء** (بالزوج المؤجَّل أدناه). **وقيمة الصفّ عند إنشاء الجدول**: `billing_mode = commission_only` مع `merchant_commission_percent = 0` و`service_fee_fixed = service_fee_percent = service_fee_max = 0` — **فالأثر الفعلي يوم الإطلاق مجّاني، والمفتاح بيد المالك بلا نشر**. **النموذج يبني الأدوات لا القيم، ولا رقم مكتوب في الكود**: الأصفار قيم صفّ يكتبه المالك من اللوحة أو تبذره الترحيلة، لا ثوابت في وحدة تُقرأ بدل الصفّ (و`DEFAULTS` في وحدة `delivery_settings` — على نمط `dispatch_settings` — تحمل الأصفار نفسها لسوقٍ بلا صفّ، فلا يُفتح بالسكوت شيءٌ غير المجّاني). الاشتراك **مبنيّ ومطفأ**: الجداول والمسارات قائمة من المرحلة 1، ولا تُعرض شاشة اشتراك للتاجر ما دام الوضع لا يشمله (§22.0 — لا باب بلا زرّ، ولا زرّ لما لا يعمل).

| البند | من | الافتراض عند الإطلاق | الضابط |
|---|---|---|---|
| عمولة التاجر | التاجر | `merchant_commission_percent` لكل دولة، تبدأ منخفضة، وتُجمَّد على الطلب لحظة `placed` | إعداد الدولة، أو `commission_percent_override` لتاجر بعينه، أو `free_until` (تاريخ) فالعمولة صفر قبله |
| اشتراك التاجر | التاجر | **مطفأ** (`billing_mode = commission_only`) | مفتاح الدولة؛ وإشعاله لاحقاً يخضع لقاعدة الوعد أدناه |
| رسوم خدمة | الزبون | `service_fee` = ثابت + نسبة من `subtotal`، **افتراضهما صفر**، بحدّ أقصى | إعداد الدولة؛ وتُعفى منها طلبات بلا حدّ أدنى إن أُريد |
| رسوم التوصيل | الزبون | تذهب للكبتن كاملة | §D1.2 |
| الكبتن | — | **لا شيء**: لا اشتراك ثانٍ ولا عمولة ولا حصة من رسوم التوصيل | §D0.7 |

**قاعدة الوعد (امتداد §25.11 من SPEC.md)**: من دخل على شرطٍ يبقى عليه حتى يُعلَن غيره. **ولا جدول إعدادات بإصدارات** (قرار المالك 2026-09-19) — ثلاث طبقات:

1. **النسبة مجمَّدة على كل طلب**: `commission_percent_at_order` لحظة `placed`، فلا يتأثر طلب جارٍ. (نظيرها في الرحلات `rides.commission_percent_at_ride`، ويُحسم هناك عند القبول لا الإنشاء بحكم §25.11؛ وهنا التاجر معروف عند الإنشاء فلا انحراف.)
2. **`free_until` على التاجر تُحترم** ولا تُلغى بتغيير إعداد الدولة ولا بإشعال `billing_mode`.
3. **الضابط المالي لا يتغيّر إلا بزوج مؤجَّل** (قرار المالك 2026-09-19، Q26 — **قاعدة واحدة للثلاثة**): كل ضابط مالي على صفّ الدولة في `delivery_settings` يتغيّر بـ**قيمة تالية + تاريخ سريان**، **تسريه مهمة beat** عند حلول التاريخ فتنقل القيمة التالية إلى الحالية وتمحو الزوج، **ويسبقه إشعار للتجّار بمدة `billing_change_notice_days`** (عدد، لا آلية تمنع الحفظ). والضوابط المالية ثلاثة:

| الضابط | القيمة الحالية | الزوج المؤجَّل |
|---|---|---|
| العمولة | `merchant_commission_percent` | `next_commission_percent` + `next_commission_effective_from` |
| رسوم الخدمة (أعدادها الثلاثة تتغيّر معاً) | `service_fee_fixed` · `service_fee_percent` · `service_fee_max` | `next_service_fee_fixed` · `next_service_fee_percent` · `next_service_fee_max` + `next_service_fee_effective_from` |
| نموذج الدخل | `billing_mode` | `next_billing_mode` + `next_billing_mode_effective_from` |

وما يسري على طلبٍ هو القيمة الحالية لحظة `placed` ثم تُجمَّد عليه (الطبقة 1). (وقد كانت 0.1 تقول "التغيير الفوري ممنوع بالنموذج" — سقط بقرار المالك.)

**العرض للتاجر**: بطاقة في تطبيقه تقول حالته اليوم بلغة صريحة — "مجاناً حتى 2026-12-31" أو "عمولة 8% لكل طلب، بلا اشتراك" — ومصدرها الإعدادات نفسها التي يحاسب بها الخادم (مصدر واحد يمرّ به البابان، الشكل الثامن).

**العرض للزبون**: `service_fee` بندٌ مستقل في الفاتورة باسمه، لا مضموم إلى رسوم التوصيل ولا إلى سعر الأصناف — وصفره لا يُعرض سطراً فارغاً.

### §D1.8 TaxoEat — قسم المطاعم

- **قسم داخل TAXO MARKET لا تطبيق مستقل**: تطبيق واحد للزبون، وحساب واحد، ومحفظة واحدة، وسلة من تاجر واحد كما في §D10. TaxoEat واجهة وهوية لقسم، وليست قناة في channels.json ولا نطاقاً ولا حزمة.
- ما يخصّه بصرياً: اسم القسم وشعاره وبانره على الشاشة الرئيسية، وتصفّح بالمطبخ (شاورما، برجر، بيتزا…) إن أُضيف وسمٌ للمطبخ لاحقاً.
- ما لا يخصّه: لا عمولة مختلفة ولا رسوم توصيل مختلفة ولا دورة حياة مختلفة — هذه كلها لكل دولة وتاجر لا لكل قسم. إن أُريد اختلافها يوماً فهو تغيير في §D2 لا في التسمية.
- **الشاشة الأولى للزبون (قرار موقَّع)**: تفتح على **كل المتاجر المفتوحة القريبة** مرتَّبة بالمسافة، وشريط أقسام ثابت في الأعلى (الكل · TaxoEat · …) يفلتر القائمة في مكانها بلا شاشة وسيطة. العلّة: الطلب المتكرّر يصل بنقرة واحدة، والقسم فلتر لا بوابة.
- ما يترتّب عليه: التصفية على الخادم بمعامل `section` على مسار قائمة المتاجر (لا فلترة في العميل بعد جلب الكل)، والفلتر المختار يُحفظ للجلسة لا للحساب، و"الكل" هو الافتراض دائماً.
- الاسم يُكتب `TaxoEat` هكذا (بلا مسافة) في كل موضع؛ وهو الاستثناء الوحيد من قاعدة كتابة الاسم TAXO بحروف كبيرة، لأنه اسم قسم لا اسم المنصّة.

### §D1.6 القائمة

`menu_categories → menu_items → item_option_groups (min_select, max_select) → item_options (price_delta)`؛ التوفّر لكل فرع في `branch_item_availability`؛ صور الأصناف عبر `core/storage.save` مساراً على الصفّ (`image_path`). عند الطلب تُجمَّد على `delivery_order_items`: اسم الصنف، سعره، والخيارات المختارة بأسمائها وفروقها (jsonb) — الفاتورة لا تتغيّر إن عدّل المطعم قائمته بعدها.

---

## §D2 نموذج البيانات

اصطلاحات: أعمدة المال `NUMERIC(12,3)` (`MONEY` في `models/base.py`) بصيغة §4 وتحت الحارس الكانس (§D8)؛ الأزمنة UTC؛ كل جدول له `country_code` مباشرة أو عبر تاجره؛ المعرّفات UUID (`UUIDMixin`). **التسمية** (قرار المالك 2026-09-19): كل ما يخصّ الطلب يُسمّى `delivery_order` — لأن "order" في الشجرة اليوم تعني `provider_orders` (`services/order_maintenance.py`، `/cliq-claims/{order_id}`)، ولا يُلمس `provider_orders` ولا مساراته إلا بما نصّ عليه §D2 أدناه.

الجداول القائمة **تُستعمل ولا تُكرَّر**: `users` · `user_roles` · `drivers` · `wallet_transactions` (الدفتر) · `driver_debts` · `provider_orders` · `admin_audit_logs` · وجداول الإعداد المتخصّصة لكل دولة (`commission_settings` · `payment_settings` · `dispatch_settings` · `wallet_settings` · `notification_settings` …). **وغير موجود في الشجرة**: جدول رفع عامّ (`uploads`) — الملفات مسارات على صفوفها؛ وجدول إعدادات عامّ لكل دولة — كل مجال جدوله. وقبل أي عمود جديد: هل يعرف الصفّ الجواب فعلاً؟ (§22.0)

### التاجر والقائمة (كلّها تُبنى)

| الجدول | الأعمدة الأساسية | ملاحظات |
|---|---|---|
| `merchants` | id · owner_user_id→users · name · legal_name · country_code · status(pending_review/active/suspended/rejected) · category(restaurant/cafe/bakery/grocery/sweets/pharmacy/other) · owned_by_taxo(bool, false) · logo_path · cover_path · description · public_phone · commission_percent_override(null) · free_until(null — عمولة صفر قبله) · cash_accepted(true) · wallet_accepted(true) · min_order_amount(0.000، §D13.1-14) · settlement_cycle(إلزامي بلا افتراض، §D19.3) · approved_at · approved_by · suspended_reason · created_at | العمولة الفعلية = override ?? `delivery_settings.merchant_commission_percent`، وصفر قبل `free_until`؛ والفئات كلها مستعملة من الإصدار الأول (§D1.5) |
| `merchant_documents` | id · merchant_id · doc_type · file_path · content_type · size_bytes · review_status · review_note · reviewed_by · reviewed_at | **جدول جديد**: `driver_documents` القائم خاصّ بالكبتن (`driver_id`، لا `subject_type`) |
| `branches` | id · merchant_id · name · address_text · location (`geography(POINT)` بفهرس مكاني — PostGIS قائم، الترحيلة `0001`) · phone · opening_hours(jsonb أسبوعي بمنطقة وقت الدولة) · status(active/paused/closed) · delivery_radius_km(null→إعداد الدولة) · prep_time_default_min · created_at | `is_open_now` تُشتقّ ولا تُخزَّن |
| `menu_categories` | id · merchant_id · name · sort_order · is_active | |
| `menu_items` | id · merchant_id · category_id · name · description · base_price · image_path · is_active · sort_order · prep_time_min(null) · available_from/available_to(null — قائمة موقوتة، §D14.أ-4) · sold_out_until(null — زرّ "نفد الصنف"، يُمحى أول يوم الدولة التالي) | |
| `branch_item_availability` | (branch_id, item_id) PK · is_available | غيابُ الصفّ = متوفّر |
| `item_option_groups` | id · item_id · name · min_select · max_select · sort_order | `required` = min_select ≥ 1 |
| `item_options` | id · group_id · name · price_delta · is_available · sort_order | |
| `merchant_subscription_plans` | id · country_code · name · duration_type(daily/weekly/monthly — `SubscriptionDurationType` القائم) · price · currency · is_active | **جدول جديد** (قرار المالك 2026-09-19)؛ `subscription_plans` لا يُلمس — وهو بلا عمود يقول لمن الخطة |
| `merchant_subscriptions` | **مبنيّ ومطفأ في الإطلاق (§D1.9)** — على شكل `driver_subscriptions` بأسمائه: merchant_id · plan_id→merchant_subscription_plans · starts_at · **expires_at** · **amount_paid** · list_price · payment_method · status · idempotency_key | أسماء 0.1 (`ends_at` · `price_at_purchase` · `provider_order_id`) لا وجود لها في `driver_subscriptions`: فيه `expires_at` و`amount_paid`، والربط بالدفع عبر `provider_orders.plan_id` لا عمود على الاشتراك |
| `merchant_devices` | كما في §D15.5 | يُبنى |
| `merchant_settlements` | كما في §D18.2، ومعه `channel` و`recorded_by` (§D18.4) | يُبنى |

### الطلب (كلّها تُبنى)

| الجدول | الأعمدة الأساسية | ملاحظات |
|---|---|---|
| `delivery_orders` | id · order_no(تسلسل لكل دولة، يُعرض بأرقام لاتينية) · fulfilment(delivery/pickup، §D14.أ-1) · drop_at_door(bool) · proof_photo_path · customer_user_id · merchant_id · branch_id · status · payment_method(cash/wallet) · country_code · currency · subtotal · commission_percent_at_order · commission_amount · merchant_net · delivery_fee · service_fee · discount(0.000، §D10) · distance_km · total · customer_location · customer_address_text · customer_note · driver_id(null) · assigned_at · delivery_code(4 أرقام) · delivery_code_attempts · expected_ready_at · printed_at · print_attempts (§D15.3) · placed_at · accepted_at · preparing_at · ready_at · picked_up_at · delivered_at · cancelled_at · cancelled_by(customer/merchant/driver/admin/system) · cancel_reason · undeliverable_reason · undeliverable_photo_path | كل المال مجمَّد لحظة `placed` |
| `delivery_order_items` | id · order_id · item_id(null عند حذف الصنف) · item_name · unit_price · qty · options(jsonb: [{group, option, price_delta}]) · line_total | لقطة لا مرجع |
| `delivery_order_events` | id · order_id · from_status · to_status · actor_type · actor_id · at · meta(jsonb) | المصدر الوحيد لخطّ الزمن في التطبيقات الثلاثة واللوحة |
| `delivery_assignments` | id · order_id · driver_id · offered_at · responded_at · response(accepted/declined/declined_no_cash/timeout) · exposure_at_offer | صفٌّ لكل عرض، يُكتب بعد الإرسال (§D1.3، §D11-Q22) |
| `customer_addresses` | id · user_id · label · address_text · location · is_default | |
| `delivery_order_ratings` | order_id PK · merchant_stars(1–5) · driver_stars(1–5) · tags(قائمة مغلقة، §D13.1-9) · comment(null) · at | زبون ← (مطعم، كبتن) فقط في الإصدار الأول |
| `delivery_order_disputes` | order_id · kind(undeliverable/merchant_cancel_after_accept/report) · opened_at · decided_option(من قائمة §D19) · reason · decided_by · decided_at | حالة `pending_review` على الطلب مصدرها هذا الصفّ (§D19) |

### الكبتن (أعمدة على `drivers` لا جدول جديد)

`delivery_mode(bool)` · `delivery_mode_since` · `delivery_exception_enabled(bool، من اللوحة)` · `max_concurrent_orders(1)` · `cash_exposure_cap_override(null)` · `cash_on_hand_limit(null، يعلنه الكبتن — §D4)`.

وهي أعمدة محضَّرة يقرؤها `_eligible_levels` في نافذة التوزيع بلا ضمّ (§5-ج)؛ **وكاتب كل عمود يُسمّى ويُختبر** بحكم §5-ج نفسه: `delivery_mode` يكتبه زرّ الكبتن وحده، والثلاثة الإدارية تكتبها اللوحة، و`cash_on_hand_limit` يكتبه الكبتن.

### المحافظ والدفتر والدَّين

- **`WalletOwnerType`** (اليوم `rider · driver`): تُضاف `customer` و`merchant`. **ومستحقّ التاجر على TAXO في محفظته ودفترها القائمين** (قرار المالك 2026-09-19، Q20) — لا جدول ثالث. التفصيل وما كشفه التثبيت في §D6.
- **`wallet_transactions`** يلزمه عمود جديد `delivery_order_id` (nullable، `RESTRICT`) على نمط `ride_id` و`advance_id` القائمين — كي يُعرف أيّ طلب يخصّه كل قيد (دفع الزبون، ردّه، أجر الكبتن، مستحقّ التاجر). **ويلزم قبل كتابته**: الدفتر لا يُعدَّل بعد الكتابة (مُشغّل الترحيلة `0006`)، فالعمود يُملأ لحظة القيد أو لا يُملأ أبداً.
- **`WalletTransactionType`** (القائم: `topup · ride_payment · ride_earning · commission · transfer_in · transfer_out · withdrawal · refund · subscription_payment · adjustment · tip · tip_payment · skin_purchase · referral_bonus · advance · advance_repayment · cancellation_fee · cancellation_compensation`):
  - **يُبنى**: `delivery_order_payment` (مدين على الزبون: `total` لحظة `placed`) · `delivery_earning` (دائن للكبتن: `delivery_fee` لطلب المحفظة عند `delivered`) · `delivery_compensation` (دائن للكبتن بقرار نزاع، §D19).
  - **يُستعمل القائم**: `refund` لكل ردّ على الزبون (إلغاء · رفض · انقضاء · ردّ إداري) — لا `order_refund`. و`commission` هو قيد تحصيل الدَّين القائم.
  - **سقط من 0.1** (بقرار المالك: لا حجز، ولا خصم من المحفظة للكاش): `order_hold` · `order_capture` · `order_release` · `merchant_commission_collected` · `service_fee_collected` · `undeliverable_reimbursement`.
  - وكل نوع جديد يدخل قيد `wallet_amount_sign_by_type` (`models/wallet.py:109`) بإشارته.
- **`DriverDebtSource`** (اليوم `ride_commission`): تُضاف `store_commission` · `service_fee` · `goods_price` (محجوز، §D18.5). ومع `driver_debts`: عمود `delivery_order_id` وقيد تفرّد `(delivery_order_id, source)`.
- **سداد الدَّين** (§D18.1): جدول `driver_debt_payments` يُبنى — `debt_id` · `amount` · `channel`(wallet/transfer/office) · `recorded_by` · `at` · مرجع القيد أو `provider_order`. **لماذا جدول**: `driver_debts.collected` مجموعٌ لا يعرف من أيّ قناة جاء كل جزء ولا من سجّله — فالصفّ لا يعرف الجواب (§22.0).

### التعدادات التي تحتاج ترحيلة قيمةٍ جديدة — وأثر كلٍّ منها

| التعداد (نوع postgres) | القيم الجديدة | الأثر |
|---|---|---|
| `user_role` (`UserRole`) | `customer` · `merchant` · `settlement_agent` | **النوع نفسه يحمل عمود الجسر `users.role`** (`models/user.py:31`) وجدول `user_roles`. و§22.5 من SPEC.md: العمود "يُقرأ للرجوع ولا يُكتب"، ويحرسه `test_no_path_writes_users_role`، ولم تُستوفَ شروط إسقاطه. فالحساب الجديد يُنشأ عبر `create_account` بصفّ في `user_roles`، ولا يُكتب دوره في `users.role`؛ و`has_role_clause` (ستة مواضع بقياس §22.5 في 2026-08-20) يبقى يضمّ العمود |
| `wallet_owner_type` (`WalletOwnerType`) | `customer` · `merchant` | **`wallet.owner_type_for` (`services/wallet.py:80`) يعدّ كل إعلان ليس `rider` محفظةَ كبتن** (`needed = RIDER if declared is RIDER else DRIVER`) — فيلزم تعديله إلى خريطة (غرض ← دور). ومعه `wallet_topup_requests.owner_type` و`provider_orders.opened_from_app` |
| `ClientApp` (`client_app`، عمود في `app_releases` منذ `0071`) | `market` · `merchant` | تعليق التعداد يقول "ثلاثةٌ لا أكثر" — يُحدَّث معه؛ وحراسة `core/app_scope.py` تمتدّ إلى تطبيقين |
| `provider_order_purpose` (`ProviderOrderPurpose`) | `merchant_subscription` | عمود ربط جديد وقيد جديد — §D2 "خطة التاجر في `provider_orders`" أدناه (قرار Q24). **وفرعٌ قائم يبتلع الغرض الجديد**: `card_payments.py:466-469` يعامل كل غرض ليس `ride_payment` ولا `subscription` **شحنَ محفظة** (`else: _credit_wallet_topup`)، فطلب بطاقة لاشتراك تاجر يُقيَّد شحناً بلا خطأ. يُحوَّل الفرع إلى تعداد صريح يرفض ما لا يعرفه |
| `driver_debt_source` | `store_commission` · `service_fee` · `goods_price` | لا أثر على المسارات القائمة |
| `wallet_transaction_type` | الثلاثة أعلاه | مع قيد الإشارة |

### خطة التاجر في `provider_orders` (قرار المالك 2026-09-19، Q24)

`merchant_subscription_plans` جدول مستقل، و**عمود ربط جديد** على `provider_orders`: `merchant_plan_id` → `merchant_subscription_plans` (nullable). **ولا يُمسّ `subscription_plans` ولا عمود `plan_id` القائم** (مفتاحه إلى `subscription_plans`، `models/provider_order.py:164`).

**القيد القائم يبقى حرفياً** — `provider_order_plan_matches_purpose`:
`(purpose::text = 'subscription') = (plan_id IS NOT NULL)`

**ويُضاف قيد نظيره**:
`(purpose::text = 'merchant_subscription') = (merchant_plan_id IS NOT NULL)` — باسم `provider_order_merchant_plan_matches_purpose`.

**لماذا يكفيان معاً لـ"كل غرض يشير إلى جدول خططه وحده"**:

| الغرض | `plan_id` | `merchant_plan_id` | من أيّ قيد |
|---|---|---|---|
| `subscription` | إلزامي | **فارغ** | الأول يلزم `plan_id`؛ الثاني طرفه الأيسر `false` فيلزم `merchant_plan_id IS NULL` |
| `merchant_subscription` | **فارغ** | إلزامي | الأول طرفه الأيسر `false` فيلزم `plan_id IS NULL`؛ الثاني يلزم `merchant_plan_id` |
| `ride_payment` · `wallet_topup` · `debt` | فارغ | فارغ | القيدان معاً |

فشرط "اشتراك يعني وجود `plan_id`" **يبقى صحيحاً بلا تعديل**: صفّ `merchant_subscription` يحقّقه (`false = false`)، ولا صفّ قائم يتغيّر.

**والمقارنة على النص (`purpose::text`) لا على قيمة التعداد** — للعلّة المكتوبة فوق القيد القائم نفسه (`models/provider_order.py:80-84`): postgres يرفض استعمال قيمة تعداد جديدة في المعاملة التي أضافتها، فالنصّ هو ما يجعل القيد يولد مع القيمة في ترحيلة واحدة.

**ومن يقرأ `plan_id` اليوم لا يرى طلب التاجر**: `subscriptions.activate_paid_order` و`cliq_subscriptions` يصفّيان بـ`purpose == SUBSCRIPTION` صراحةً (`cliq_subscriptions.py:106,158,221`). **والاستثناء فرع `card_payments.py:466` المذكور في جدول التعدادات أعلاه.**

### إعدادات الدولة — جدول جديد `delivery_settings` (قرار المالك 2026-09-19)

صفّ لكل دولة على نمط الجداول المتخصّصة القائمة (`dispatch_settings` مثالاً: صفّ غائب = افتراض مكتوب في وحدته). **ولا يُلمس جدول إعدادات قائم.**

`delivery_enabled` · `billing_mode` · `next_billing_mode` · `next_billing_mode_effective_from` · `merchant_commission_percent` · `next_commission_percent` · `next_commission_effective_from` · `service_fee_fixed` · `service_fee_percent` · `service_fee_max` · `next_service_fee_fixed` · `next_service_fee_percent` · `next_service_fee_max` · `next_service_fee_effective_from` · `billing_change_notice_days` · `delivery_base_fee` · `delivery_per_km` · `delivery_min_fee` · `delivery_max_fee` · `delivery_max_distance_km` · `delivery_dispatch_radius_km` · `merchant_accept_timeout_sec` · `ready_unassigned_alert_min` · `driver_cash_exposure_cap_default` · `merchant_subscription_grace_days` · `delivery_exception_default` · `customer_cash_block_after_undeliverable` · `dispute_decision_hours` (§D19).

- `merchant_plan_prices` **سقط** من القائمة: الأسعار صفوف في `merchant_subscription_plans`.
- **`delivery_enabled` عمود هنا لا `FeatureKey`** (قرار المالك 2026-09-19، Q23). **وعلّته**: بقية مفاتيح التوصيل في هذا الجدول، وقراءتها من بابين (`delivery_settings` و`feature_flags`) تصنع الشكل الثامن؛ ومفاتيح §24 من SPEC.md (`country_visible`) لإظهار **سوق كامل** لا لضبط خدمة داخله. وغياب صفّ الدولة = الافتراض المكتوب في وحدته، وافتراضه `false`.
- **النشر في `GET /config` بالطريقة القائمة — مُثبَتة**: كل قيمة لكل دولة من جدول متخصّص تُنشر **حقلاً مسمّىً** على `CountryConfigOut` (`schemas/config.py:11`)، يملؤه `country_config.build` من جدولها — كما يُملأ `cliq_alias` من `payment_settings` و`quiet_hours_*` من `notification_settings`. **لا عبر `features`**: ذاك القاموس `settings_service.get_flags` أي `feature_flags` وحدها. فـ`delivery_enabled` حقلٌ جديد على `CountryConfigOut` يقرؤه `build` من `delivery_settings`.
  - **والبانِي واحد لبابين**: `build` يخدم `GET /config` و`GET /admin/countries` معاً (رأس `services/country_config.py`)، فاللوحة ترى الحقل نفسه.
  - **وأثره على `check:config`**: الحارس يقارن أسماء حقول `CountryConfigOut` بمرآة `CountryConfig` في **كل** تطبيق يحمله (`scripts/check-config.mjs`) — فالحقل يُضاف إلى مرآة التطبيقات الثلاثة القائمة ولو لم يقرأه أحدها، وإلا احمرّ الحارس.
  - **ويُنشر ما تقرؤه التطبيقات وحده**: النسب الداخلية (عمولة التاجر، الزوج المؤجَّل) تُقرأ في اللوحة من بابها لا من `/config`.
- "يوم الدولة" و"أول يوم الدولة التالي": `stats.country_today` و`stats._zone` (منطقة الوقت من `notification_settings.timezone`) — قائمان.

---

## §D3 دورة حياة الطلب

`status ∈ {placed, accepted, preparing, ready, picked_up, pending_review, delivered, cancelled, rejected, expired}` — و`pending_review` حالة النزاع المؤقتة (§D19). تعيين الكبتن (`driver_id`, `assigned_at`) **محور مستقل**: يقع في أي لحظة بين `accepted` و`ready` ولا يقع قبل `accepted`؛ ويُسجَّل حدثاً `driver_assigned` في `delivery_order_events` لا حالةً.

كل انتقال يُقرَّر بسياق الفعل (§22): علاقة الفاعل بالطلب (زبونه / فرعه / كبتنه المعيَّن) لا دوره. كل انتقال **يقفل صفّ الطلب `for_update` قبل فحص الانتقال** (قاعدة CLAUDE.md)، ويكتب صفّ `delivery_order_events` ويرسل إشعار FCM لأطرافه. مصفوفة الانتقالات **مصدر واحد** تقرأه الخلفية والتطبيقات الثلاثة (الشكل الثامن)، والانتقال الممنوع يُرفض بـ`invalid_order_transition`.

**وترتيب الأقفال** (قاعدة CLAUDE.md: "إضافة قفل تعني إدخاله في الترتيب القائم لا اختراع ثانٍ"): صفّ الطلب يقف حيث يقف صفّ الرحلة — **أولاً** — ثم صفّ الكبتن، ثم قفل المحفظة الاستشاري **أخيراً**. **وصفوف `driver_debts` غير مذكورة في ترتيب CLAUDE.md** وإن كان `collect_from_balance` يقفلها (`outstanding_rows(..., for_update=True)`) — فموضعها يُثبَت من الشجرة في المرحلة 2 ويُعرض على المالك ليُكتب في CLAUDE.md، لا يُخترع هنا. ولا مسار يجمع صفّ رحلة وصفّ طلب معاً. ويُثبت ذلك اختبار تزامن في المرحلة 2.

| من → إلى | الفاعل | الشرط | الأثر المالي |
|---|---|---|---|
| — → placed | الزبون | الفرع active ومفتوح · التاجر ظاهر (§D1.5) · الأصناف والخيارات متوفّرة وصحيحة (min/max) · ضمن نصف قطر التوصيل · محفظة كافية إن wallet (وإلا `insufficient_balance`) · الزبون ليس محجوباً من الكاش إن cash | تجميد كل المال؛ wallet: **خصم `total` كاملاً** بقيد `delivery_order_payment` |
| placed → accepted | المطعم | — | يثبّت `expected_ready_at` (افتراضه prep_time) |
| placed → rejected | المطعم | سبب من قائمة | wallet: `refund(total)` |
| placed → expired | النظام (beat) | مرّت `merchant_accept_timeout_sec` بلا ردّ | wallet: `refund(total)` |
| placed → cancelled | الزبون | قبل القبول فقط | wallet: `refund(total)` |
| accepted → preparing | المطعم | — | — |
| accepted/preparing → ready | المطعم | — | يبدأ عدّاد `ready_unassigned_alert_min` |
| (accepted..ready) + driver_assigned | النظام | كبتن قبل العرض ضمن الفلاتر | `exposure_at_offer` يُسجَّل |
| ready → picked_up | الكبتن المعيَّن | `driver_id = الفاعل` · **cash**: تأكيد "دفعتُ للمطعم X.XXX" (`merchant_net`)؛ **wallet**: "استلمتُ" وحدها · قرب الفرع (≤ 300 م، تحذير لا منع) | — (النقد خارج الدفتر حتى التسليم) |
| picked_up → delivered | الكبتن المعيَّن | رمز التسليم من الزبون (4 أرقام) أو تأكيد الزبون من تطبيقه | cash: صفّا دَين `store_commission` + `service_fee` في `driver_debts`؛ wallet: `delivery_earning(delivery_fee)` للكبتن + `merchant_net` قيداً دائناً في محفظة التاجر `merchant` (§D6) |
| picked_up → pending_review (undeliverable) | الكبتن المعيَّن | سبب من قائمة + صورة إلزامية | لا شيء حتى القرار — ودَين الطلب المتنازع عليه خارج قاعدة اليوم التالي وسقف الدَّين (§D19) |
| pending_review → (قرار) | المشرف | خيار من قائمة §D19.1 + سبب مكتوب | أثر الخيار كما كُتب في §D19.1 |
| accepted..ready → cancelled | المطعم | سبب من قائمة | wallet: `refund(total)`؛ إن كان كبتن معيَّناً: خيار مشرف من §D19.2 |
| أي حالة غير نهائية → cancelled | المشرف | سبب مكتوب إلزامي | wallet: `refund` بما يقرّره، مسجَّل في `admin_audit_logs` |

قواعد إضافية:
- الحالات النهائية `delivered / cancelled / rejected / expired` لا تُغادَر؛ والتصحيح بعدها قيد مقابل من اللوحة بالباب القائم `POST /admin/wallets/{user_id}/adjustments` (قيد `adjustment`، `routers/admin_wallets.py:150`) — لا تحرير.
- رمز التسليم: أربعة أرقام تُولَّد عند `placed`، تُعرض للزبون بعد `picked_up`، وتُخزَّن نصّاً (لا تفتح باباً، وقيمتها تنتهي بتسليم الطلب). **لا مهلة له ولا انتهاء صلاحية** — يعيش مع الطلب حتى يُسلَّم، فرسالة الخطأ واحدة بسيطة: "الرمز غير صحيح". وثلاث محاولات خاطئة تُقفل الإدخال، وعندها الطريق البديل تأكيد الزبون من تطبيقه، مع تنبيه الإدارة.
- زبون بطلب كاش `undeliverable` مرتين خلال 30 يوماً يُحجب عن الكاش (`customer_cash_blocked`) بسبب يراه، ويرفعه المشرف — القيمة من الإعداد.
- الإلغاء بعد القبول من الزبون: **غير متاح** في الإصدار الأول (يطلبه من المطعم بالاتصال؛ الإلغاء بيد المطعم أو المشرف).
- الإشعارات: `placed` للتاجر بصوت متكرّر حتى الفتح؛ كل انتقال للزبون؛ العرض والانتقالات للكبتن.
- المسمّيات للفئات غير المطاعم: `preparing` تُعرض للزبون "جارٍ التجهيز" و`ready` "جاهز للاستلام" — نصّ العرض من الفئة، والحالة في الدفتر واحدة.

---

## §D4 وضع التوصيل في تطبيق الكبتن

إذن المالك بمسّ منطق قائم (القيد السابع) **محدود بهذا القسم**: ملف الإسناد (شرط الحصرية في `_eligible_levels`، والحلقة الثانية بجوار `_run` لا داخلها — §D1.3) والشاشة الرئيسية للكبتن (الزرّ والصفحة). **لا يتغيّر** أي سلوك للرحلات لكبتن ليس في وضع التوصيل، ويُثبت ذلك اختباران في الاتجاهين.

- **الزرّ**: في الشاشة الرئيسية، يبدّل `delivery_mode`. الدخول يشترط: متصل، معتمَد، اشتراك سارٍ (كالرحلات)، لا رحلة جارية. الخروج يشترط: لا طلب جارٍ (معيَّن أو مستلَم).
- **الزرّ والاشتراك**: فحص الاشتراك عند الدخول **جديد** — لا يوجد اليوم فحص اشتراك عند `go_online` (`services/drivers.py:75`)؛ الاشتراك يُفحص في التوزيع وحده (`covered_driver_ids_subquery`). فالرفض عند الزرّ خطأ جديد `driver_subscription_required` (§D7)، والتوزيع يبقى الحارس الثاني.
- **الحصرية**: `delivery_mode = true` ⇒ لا يدخل في إسناد الرحلات — **شرط واحد في مصفوفة `conditions` في `_eligible_levels`** (`dispatch.py:399`). **الاستثناء**: `delivery_exception_enabled` على الكبتن من اللوحة أو `delivery_exception_default` للدولة ⇒ تصله الرحلات **فقط** حين لا طلب جارٍ.
- **أثرها على خريطة الراكب نتيجةٌ مقصودة لا عرَض**: `drivers.nearby_available` وخريطة الراكب تقرأ `eligible_driver_ids` — الدالة نفسها — فكبتن التوصيل يختفي من خريطة الراكب في اللحظة التي يخرج فيها من إسناد الرحلات. وهذا ما يريده §D0.3: ما يُعرض "متاحاً" هو ما يُسنَد إليه (نصّ الالتزام في `dispatch.gender_match`). ولا يُبنى تصفية ثانية للخريطة.
- **صفحة التوصيل**: شارة بعدد الطلبات الجارية؛ لكل طلب: اسم المطعم والفرع وعنوانه · عنوان الزبون · المسافة · رسوم التوصيل · طريقة الدفع · **"تدفع للمطعم: X.XXX"** · **"تقبض من الزبون: X.XXX"** (كاش) · أزرار الانتقال بالترتيب: وصلتُ للمطعم → استلمتُ → وصلتُ للزبون → سلّمتُ (بالرمز). خريطة Mapbox بمسار الآن ← الفرع ← الزبون، و"افتح في قوقل ماب" كالرحلات.
- **العرض** على الكبتن: اسم المطعم · المسافة إلى الفرع ومنه إلى الزبون · الرسوم · `expected_ready_at` · طريقة الدفع · ومبلغان بالخط الكبير في طلبات الكاش: **"تدفع للمطعم: X.XXX"** و**"تقبض من الزبون: Y.YYY"**؛ ومهلة العرض كالرحلات. في طلبات المحفظة يُكتب صراحةً: **"لا تدفع شيئاً"** — لا يُترك السطر فارغاً فيظنّه الكبتن سهواً. ومهلة العرض "كالرحلات" تعني `dispatch_settings.offer_timeout_seconds` لدولته (افتراضها 7 ث، لا عشرون كما في نصوص قديمة).
- **نقدي معي الآن**: حقل يضبطه الكبتن بنفسه من صفحة التوصيل (`cash_on_hand_limit`)، فلا يصله طلب يتجاوز ما أعلنه. يُعدَّل بضغطة في أي وقت، ويُقرأ في المرشِّح مع السقف الإداري: الأدنى منهما يحكم. علّته: المنصّة لا تعرف كم في جيبه، وهو يعرف.
- **"لا نقد معي"** سبب رفض مسمّى في بطاقة العرض، **لا يُحسب عليه** في نسبة القبول ولا في عدّاد الإلغاء — وإلا تعلّم الكباتن أن يصمتوا بدل أن يرفضوا، فيضيع الطلب سبع ثوانٍ بلا فائدة.
- **عدّاد النقد الخارج اليوم** على صفحة التوصيل: كم دفع للمطاعم وكم قبض وكم بقي من سقفه — رقم واحد يراه قبل أن يقبل طلباً تالياً.
- `max_concurrent_orders = 1` افتراضاً؛ الرفع من اللوحة لكل كبتن، والدفعة الواحدة من فرع واحد فقط (D10 يوضّح ما لا يُبنى).
- **الأرباح**: بند "توصيل" مستقل عن الرحلات في المحفظة والكشف، وبند "عمولة TAXO — توصيل" يعرض `commission_amount` لكل طلب من القيمة المجمَّدة لا من الإعدادات، والشهر تقويمي (كقرار الرحلات).
- **الخريطة الحية** للراكب لا ترى كباتن التوصيل (نتيجة الحصرية أعلاه، لا كود ثانٍ)؛ خريطة المشرف (`services/live_map.py`) تراهم بأيقونة مميّزة.

---

## §D5 اللوحة

كل مسار إداري جديد له زرّ (`check:doors`، `admin-panel/scripts/check-doors.mjs`)، وكل فعل مالي أو اعتماد يُسجَّل في التدقيق القائم (`admin_audit_logs`، `services/audit.py`).

| القسم | الأبواب |
|---|---|
| التجار | القائمة بالحالة والدولة · بطاقة التاجر (وثائقه بعارض الصور — `DocumentPreview` مستخرَجاً من `Drivers.tsx` مكوّناً مشتركاً، §D1.5 —، فروعه، اشتراكه، عمولته الفعلية، دورية تسويته) · اعتماد/رفض بسبب · إيقاف/إعادة بسبب · تعديل `commission_percent_override` · إنشاء تاجر يدوياً (لمن لا يسجّل بنفسه) |
| الطلبات | قائمة حيّة بالفلاتر (حالة، دولة، تاجر، كبتن، طريقة دفع) · خطّ الزمن من `delivery_order_events` · إعادة إسناد يدوية · إلغاء بسبب · ردّ إلى محفظة الزبون بقيد `refund` القائم · قائمة `pending_review` وقرارات §D19 · تعليم زبون محجوب/غير محجوب من الكاش |
| الكباتن | مفتاح `delivery_exception_enabled` · `max_concurrent_orders` · `cash_exposure_cap_override` (يخفض ولا يرفع فوق المحسوب، كـ`advance_cap_override`) · طلبات التوصيل الجارية للكبتن · دَينه بمصادره (الشاشة القائمة `components/DriverDebts.tsx` تمتدّ بالمصادر الجديدة) |
| إعدادات الدولة | صفّ `delivery_settings` (§D2) · تفعيل التوصيل **للدولة** بعمود `delivery_enabled` (لا مدينة — §D10؛ ولا `feature_flags` — Q23) · `billing_mode` وقيم العمولة ورسوم الخدمة، وأزواجها المؤجَّلة الثلاثة (§D1.9) |
| المجّانية | `free_until` لتاجر بعينه أو لكل تجّار دولة دفعةً واحدة · قائمة من تنتهي مجّانيته خلال 7 أيام |
| الخريطة الحية | كباتن التوصيل بأيقونة مميّزة · الطلبات الجارية كعلامات (فرع ← زبون) |
| التقارير | بحسب القسم والفئة (TaxoEat مقابل غيره) · طلبات/يوم · إجمالي المبيعات · العمولة (من `commission_amount` المجمَّد) · رسوم التوصيل · نسب الإلغاء بحسب الطرف · أعلى التجار · أعلى الكباتن توصيلاً — بيوم الدولة |
| الاشتراكات | خطط التجار في `merchant_subscription_plans` لكل دولة (بند يخصّ المالك) · تسجيل دفعة يدوياً كما للكباتن (`subscriptions.record_manual` نظيره) · فترة السماح |
| الأجهزة والتسويات | مخزون `merchant_devices` وإسنادها وإبطالها (§D15.5) · دورات `merchant_settlements` وقراراتها (§D18.2) · سداد دَين الكبتن يدوياً بـ`channel` و`recorded_by` (§D18.1) |

---

## §D6 المال

- **الزبون** (قرار المالك 2026-09-19): محفظة بغرض `customer`، شحن بلا سحب بالطرق القائمة. **لا حجز ولا قبض ولا إفراج**: خصم `total` كاملاً لحظة `placed` بقيد `delivery_order_payment`، وردّ بقيد `refund` القائم عند الإلغاء أو الرفض أو الانقضاء أو الردّ الإداري. الرصيد غير الكافي يُرفض بـ`insufficient_balance` قبل إنشاء الطلب.
- **الكبتن**: كما في §D1.1 — ما قبضه نيابةً صفوف دَين في `driver_debts` لا رصيد سالب، بالحاجز القائم `debt_blocked` وسقفه `driver_debt_ceiling`، ويُحصَّل بـ`debts.collect_from_balance`. وتعويضه في النزاع بقيد `delivery_compensation` بقرار §D19.
- **التاجر**: في طلب الكاش قبض حقّه نقداً من الكبتن؛ وفي طلب المحفظة له على TAXO `merchant_net` يُسوّى دورياً (§D18.2).
  - **موضع مستحقّه — قرار المالك 2026-09-19 (Q20)**: **محفظة ودفتر معاً بالنمط القائم نفسه للكبتن، لا جدول ثالث**. غرض `merchant` في `WalletOwnerType`، وكل طلب محفظة يكتب عند `delivered` صفّاً دائناً في الدفتر القائم، والرصيد يُقرأ منه. ودورة `merchant_settlements` **تشير إلى صفوف فترتها ولا تحملها** (§D18.2).
  - **الدفتر كما هو في الشجرة**: جدول **`wallet_transactions`** (`models/wallet.py:104`)، حقوله: `owner_type` · `owner_id` (→ `users.id`، `RESTRICT`) · `type` · `amount` (موقَّع) · `balance_after` · `ride_id` · `advance_id` · `reference` · `created_by` · `idempotency_key` · `created_at`. **لا عمود رصيد في أي مكان**، والدفتر لا يُعدَّل ولا يُحذف (مُشغّل الترحيلة `0006`)؛ والتصحيح قيد `adjustment` مضاد.
  - **وقراءة الرصيد اليوم للكبتن**: `wallet.balance(session, owner_id, owner_type)` = `SUM(amount)` حيث `owner_id = users.id` و`owner_type` المعطى (`services/wallet.py:163`)، ورصيد الكبتن يُسأل بـ`driver.user_id` لا `driver.id` (رأس `models/wallet.py`). **هذه الدالة نفسها لا تفترض نوعاً** — تصلح لـ`merchant` كما هي.
  - **مفتاح المحفظة اليوم بالضبط — مُثبَت** (Q34/Q38):
    - **الرصيد** = `SUM(amount)` حيث `owner_id = :u AND owner_type = :t` — **مفتاحان** (`wallet.balance`، `services/wallet.py:163`). و`history` بالمفتاحين نفسيهما (`:182`)، و`record` يحسب `balance_after` بهما (`:247-258`).
    - **وبمفتاح واحد** (`owner_id` وحده): القفل الاستشاري (`lock_wallet`، `:141`) — يقفل **كل محافظ الشخص معاً**؛ وتفرّد `(owner_id, idempotency_key)` (`models/wallet.py:114`) و`find_by_idempotency_key` (`:206`) — مشتركان بين محافظ الشخص.
    - **وفي القاعدة**: مفتاح أجنبي `owner_id → users.id` بـ`RESTRICT` (`fk_wallet_transactions_owner_id_users`، الترحيلة `0006`)، وفهرس `(owner_type, owner_id, created_at)`.
    - **القرّاء**: **41 نداءً في 14 ملفاً** إلى `wallet.balance/balance_of/history/record/lock_wallet(s)/transfer` (`routers/admin_wallets.py` 3 · `routers/wallet.py` 4 · `advances` 3 · `cancellation` 6 · `card_payments` 1 · `cliq_topups` 1 · `debts` 2 · `payments` 7 · `referrals` 2 · `subscriptions` 2 · `tips` 3 · `topups` 1 · `vehicle_skins` 3 · `withdrawals` 3)، **واستعلامان مباشران** على الدفتر بالمفتاحين (`commission_view.py:92` و`earnings.py:87`، كلاهما `DRIVER`).
    - **فالأثر**: مالك نشاطين مستقلين بمفتاح اليوم له **محفظة `merchant` واحدة** يُجمع فيها رصيدا النشاطين، فتنكسر التسوية (دوريتان وكشفان على رصيد واحد).
  - **موقَّع (2026-09-19، Q38): الخيار (أ)** — عمود `wallet_transactions.merchant_id` → `merchants` (nullable) مع قيد `(owner_type = 'merchant') = (merchant_id IS NOT NULL)` وفهرس يضمّه.
    - **العلّة**: الخيار (ب) يُسقط المفتاح الأجنبي `owner_id → users.id` على **كل** المحافظ بما فيها الركاب والكباتن، فتضيع حماية "لا يُحذف حساب له حركة مال" (`RESTRICT`، الترحيلة `0006`) عن الجميع من أجل نوع واحد جديد — والبديل مُشغِّلٌ نكتبه بأيدينا محلّ ضمانة قائمة في القاعدة.
    - **الدوالّ الثلاث التي تُمسّ** (`services/wallet.py`)، وكلّها بمعامل اختياري `merchant_id: uuid.UUID | None = None` افتراضه سلوك اليوم:
      1. `balance(session, owner_id, owner_type, merchant_id=None)` (`:163`) — تضيف `WalletTransaction.merchant_id.is_not_distinct_from(merchant_id)` إلى شرطها؛
      2. `history(..., merchant_id=None)` (`:182`) — الشرط نفسه؛
      3. `record(..., merchant_id=None)` (`:230`) — تكتب العمود، وتحسب `balance_after` بـ`balance(..., merchant_id)`، وتشترط أن يُعطى `merchant_id` **إن وفقط إن** كان `owner_type = merchant` (قبل أن يرفضه القيد في القاعدة)، وأن يكون `merchants.owner_user_id = owner.id`.
      - **ولا يُمسّ**: `lock_wallet` (يبقى على الشخص — يسلسل محافظه كلّها، وهو أحوط لا أخطر) · `find_by_idempotency_key` وتفرّد `(owner_id, idempotency_key)` (مفاتيح الطلب ذات بادئة، §D1.4) · النداءات الـ41 القائمة · الاستعلامان المباشران.
    - **مسارات محافظ اللوحة** (`routers/admin_wallets.py`، بادئة `/admin`) — أربعة أبواب مفتاحها `user_id` اليوم:
      - `GET /wallets/{user_id}` (`:76`) و`GET /wallets/{user_id}/transactions` (`:83`): تعرض **كل محافظ الحساب** بطاقاتٍ (الخريطة أدناه)، وبطاقة لكل تاجر يملكه بـ`merchant_id` — لا محفظة واحدة من `owner_type_for` بلا إعلان كما اليوم (`:63`، `:98`).
      - `POST /wallets/{user_id}/adjustments` (`:155`): يأخذ المحفظة من الطلب (`payload.wallet`) — يضاف إليه `merchant_id` إلزامياً حين `wallet = merchant`.
      - `POST /wallets/{user_id}/freeze|unfreeze` (`:108`، `:119`): اليوم على الحساب كلّه (العطب 2 أدناه) — يبقى كذلك حتى يُقرَّر مخرجه.
      - `POST /wallets/{user_id}/topups` (`:249`): شحن نقدي من اللوحة — **لا يصلح لمحفظة التاجر** (لا شحن ذاتي لها في الخريطة)، فيُرفض إعلان `merchant` فيه.
  - **الخياران كما عُرضا للتوقيع** (يبقى الجدول سجلاً للقرار):

| | (أ) بُعد ثالث: `wallet_transactions.merchant_id` (فارغ لغير التجّار) | (ب) صاحب محفظة "متجر": `owner_id = merchants.id` حين `owner_type = merchant` |
|---|---|---|
| القاعدة | ترحيلة: عمود `merchant_id` → `merchants` (nullable) · قيد `(owner_type = 'merchant') = (merchant_id IS NOT NULL)` · فهرس يضمّه | ترحيلة: **حذف المفتاح الأجنبي `owner_id → users.id` عن كل الصفوف** (postgres لا يقبل مفتاحاً أجنبياً مشروطاً) — فحماية "حساب عليه حركة مالية لا يُحذف" تسقط عن محافظ الراكب والكبتن أيضاً، أو تُعاد بمُشغّل يُكتب |
| دوالّ `services/wallet.py` تُمسّ | **3**: `balance` · `history` · `record` (معامل اختياري `merchant_id=None`، والتصفية `IS NOT DISTINCT FROM`) | **1**: `record` يأخذ `owner: User` ويمرّره بـ`owner_type_for` (فحص دور) — فطريق التاجر دالّة جديدة أو توقيع جديد؛ و`balance` و`history` تعملان كما هما |
| النداءات القائمة (41) | **0** — الافتراض `None` = سلوك اليوم | **0** |
| الاستعلامان المباشران | **0** (كلاهما `DRIVER`) | **0** |
| القفل وتفرّد مفتاح التكرار | بلا تغيير — يبقيان على الشخص (مفاتيح الطلب ذات بادئة، §D1.4) | بلا تغيير — يصيران على المتجر تلقائياً |
| النموذج | بلا تغيير | علاقة `WalletTransaction.owner → User` (`models/wallet.py`) تكذب على صفوف التاجر — **لا قارئ لها اليوم** (بحثٌ: صفر)، لكنها تبقى إعلاناً خاطئاً يُصحَّح: **1** |
| أبواب اللوحة القائمة (`/admin/wallets/{user_id}`) | تُعطى معامل المتجر لمحفظة التاجر | لا تصلح لمحفظة التاجر (مفتاحها مستخدم) — باب جديد بمفتاح المتجر |
| **مجموع ما يُمسّ ممّا يعمل اليوم** | **3 دوالّ + ترحيلة تضيف قيداً** | **1 دالّة + 1 علاقة + ترحيلة تُسقط قيداً قائماً على كل المحافظ** |
| الخطر الباقي | استعلام تاجر ينسى `merchant_id` فيجمع النشاطين — يمسكه القيد مع اختبار | الحارس الأجنبي يسقط عن مال الراكب والكبتن، وهو حارس لم يُطلب إسقاطه |

  - **من يملك أيّ محفظة — الخريطة** (Q37):

| المحفظة (`owner_type`) | من يملكها | إعلانها في `owner_type_for` | ما يُحصر عليها |
|---|---|---|---|
| `rider` | من يحمل دور `rider` | `declared = rider` ⇐ دور `rider` | الشحن والتحويل (بين راكبين) والدفع للرحلات |
| `driver` | من يحمل دور `driver` | `declared = driver` ⇐ دور `driver` | الأرباح والسحب والسلفة والاشتراك والدَّين |
| `customer` | من يحمل دور `customer` — **على حساب `account_kind = market`** (§D1.4) | `declared = customer` ⇐ دور `customer` | الشحن والدفع للطلبات والردّ — **لا تحويل ولا سحب** |
| `merchant` | من يحمل دور `merchant` **ويملك التاجر المعني** (`merchants.owner_user_id`) | `declared = merchant` ⇐ دور `merchant` + ملكية التاجر (ومعها معرّف المتجر بحسب Q38) | مستحقّ الطلبات والتسوية والتصحيح والاشتراك — **لا تحويل ولا شحن ذاتي** |

    - **ولا محفظة لـ`settlement_agent`** ولا لـ`admin`/`support`.
    - **بلا إعلان** لا تُخمَّن المحفظة: حساب يحمل غرضين أو أكثر يرتدّ بـ`wallet_owner_undecided` (القائم) في كل باب — لا "أولُ متاح".
    - **واللوحة لحساب يحمل أكثر من محفظة**: تعرض **كل محافظه** بطاقاتٍ منفصلة (لكلٍّ رصيده وسجلّه وأزراره)، ولكل تاجر يملكه بطاقته. ولا تعرض محفظة "افتراضية" واحدة.
  - **عطبان قائمان في `owner_type_for` وما حوله — يُسمّيان ولا يُصلحان الآن**:
    1. **حساب راكب+زبون بلا إعلان يرجع محفظة الراكب صامتاً.** الموضع: `services/wallet.py:92` — `if rider: return RIDER` يسبق أيّ سؤال عن غيره، والدالّة لا تعرف `customer` أصلاً. **الأثر**: يكسر استقلال محفظة الزبون (§D1.4، §D0.1) — قيدٌ يُقصد به الزبون يُكتب على الراكب، وعرضٌ يُظهر رصيد الراكب لمن سأل عن الزبون، **بلا خطأ**. **والنداءات بلا إعلان اليوم خمسة** (بتحليل الشجرة النحوية لكل نداء إلى `record`/`balance_of`/`owner_type_for`، من 35): `routers/admin_wallets.py:63,98,137` · `services/cancellation.py:225` · `services/payments.py:409` — **والأخيران صحيحان اليوم بالصدفة** (سياقهما رحلة فالراكب هو المقصود)، وهو "الصحيح بالصدفة يستر الخاطئ بالبنية". **والمخرج المقترح**: أن ترتدّ الدالّة بـ`wallet_owner_undecided` متى حمل الحساب أكثر من غرض (لا فقط راكب+كبتن)، وأن تعلن النداءات الخمسة محفظتها صراحةً.
       - **نُفِّذ في 1-أ/2 (2026-09-19)، وقاس أسوأَ ممّا كُتب**: الاختبارات كُتبت أولاً فاحمرّت الخمسة، ومنها أن **حساباً بدورين (راكب+كبتن) لا يستطيع إلغاء رحلة مقبولة عليها رسم إلغاء أصلاً** — الإلغاء كلّه يرتدّ 409 `wallet_owner_undecided` من قراءة الرصيد في `cancellation.py:225`؛ **ولا دفعَ رحلته من محفظته** (`payments.py:409`). وما أُودع في 1-أ/2: `WALLET_ROLE` خريطةٌ كاملة على التعداد يحرسها اختبار، وأبواب اللوحة الثلاثة (`admin_wallets.py:63,98,137`) تقبل `wallet` اختيارياً والسكوت كما كان.
       - **ثم أُصلحت القراءتان بإذن المالك الصريح (2026-09-19)** — إذنٌ بمسّ منطق رحلاتٍ قائم (القيد السابع) **محصورٌ في هذا العطب وحده**، وفي إيداعٍ مستقلٍّ على شجرة WSL يقول إنه **عطبُ رحلاتٍ قائم لا عملُ توصيل**. والقياس: الاختبارُ بالدورين أحمرُ على الشيفرة القائمة (`wallet_owner_undecided` عند الإلغاء)، ثم — بإصلاح الإلغاء وحده — أحمرُ عند الدفع (السطر 134: 409 بدل 201)، ثم أخضرُ بالإصلاحين؛ واختبارا ذي الدور الواحد (راكبٌ وحده في المسارين، وكبتنٌ حاملٌ يُحصَّل منه، وكبتنٌ وحده يُرفض عند باب الدفع) **أخضران قبل الإصلاح وبعده**. **والكلفةُ الفعلية**: ملفّان (`payments.py` سطرٌ واحد، و`cancellation.py` متغيّرٌ واحدٌ للقراءة والكتابة) وملفُّ اختبارٍ بثلاثة اختبارات. **وكان المقترحُ قبل الإذن**:
         - `payments.py:409`: `wallet.balance_of(session, rider, declared=WalletOwnerType.RIDER)` — الإعلان نفسه الذي يكتبه قيد `confirm` بعده (`owner_type=RIDER`).
         - `cancellation.py:225`: متغيّر واحد `payer_wallet = DRIVER if charge.carrier_driver_id is not None else RIDER` تقرأ به القراءة **ويكتب به القيد `debit`** — فلا تفترق القراءة والكتابة.
         - **واختباراه مكتوبان وقِيسا أحمرَين ثم أخضرَين** (`test_a_dual_role_rider_pays_his_ride_from_his_rider_wallet` و`test_a_dual_role_payer_is_charged_from_the_wallet_the_ledger_names`)، ومحفوظان خارج الشجرة حتى يُقرَّر البند.
       - **أكان يقع على الإنتاج قبل الإصلاح؟ نعم — وليس من صياغة الإصلاح.** الاختبارات الخمسة احمرّت على الشيفرة **قبل أيّ تعديل فيها** (ما أُضيف قبل التشغيل الأحمر ملفّ الاختبار وحده). وأصل العطب اجتماعُ قراءتين بلا إعلان — `payments.py:409` (منذ `7296cd7`، 2026-08-10) و`cancellation.py:225` (منذ `35decf7`، 2026-08-16) — مع الإيداع `7bea224` (2026-08-19) الذي جعل الأدوار مجموعةً وحساب الدورين يرتدّ `wallet_owner_undecided`. **وكلّ وسوم الإصدار `v0.1.0`…`v0.2.2` تحتوي `7bea224`**، فكلّ نسخةٍ رُفعت إلى الإنتاج منها تحمل العطب. (أيّ إيداع يعمل على الإنتاج اليوم لم يُقس من هنا.)
       - **ومسارٌ ثالثٌ متأثّرٌ لم يُسمَّ في الإذن — مكتوبٌ لا مُصلَح**: `services/deactivation.py:128` (`_rider_wallet_balance`، يقرؤه `blockers` في إلغاء تفعيل الحساب — الترحيلة `0075`، على شجرة WSL وحدها) يقرأ رصيد محفظة الراكب **بلا إعلان**. فحسابٌ بالدورين يسأل «ما يمنع إغلاقَ حسابي؟» **يرتدّ 409 `wallet_owner_undecided` على الأرجح** — **بالقراءة لا بالقياس**. وإصلاحُه المقترح إعلانُ `WalletOwnerType.RIDER` في القراءة (اسمُها «رصيدُ الراكب»). **ويمسّ مالاً محتجزاً**، فلا يُصلح بلا قرار.

         **وبابان آخران بلا إعلانٍ — مقيسان ٢٠٢٦-٠٩-٢٠ ولا يُصلحان هنا**
         (لا تغييرَ في منطقٍ قائمٍ خارج ما تصفه الخطة): **`POST
         /admin/wallets/{id}/topups`** (`admin_wallets.create_staff_topup` ⇐
         `topups.create_confirmed`) **لا يقبل `wallet`**، فشحنُ حسابٍ بدورين من
         اللوحة يرتدّ ٤٠٩ — **وقِيس أثناء كتابة اختبارات الخطوة 6** حين تعذّر
         شحنُ حسابٍ بدورين، فصار الشحنُ في الاختبار **قبل منح الدور الثاني**.
         **وهو مالٌ لا يدخل**، من عائلة بابِ التجميد قبل 1-أ/2. **ويُصلح مع
         مسار منح الدور الثاني** كما يُصلح `deactivation.py:128`.

         **وسباقُ التجميد مع دفعةٍ جارية** (قرارُ المالك ٢٠٢٦-٠٩-٢٠): التجميدُ
         **فحصٌ لا قفل**، فتجميدٌ يقع بين الفحص وكتابة القيد لا يمنع تلك
         الدفعة. **قائمٌ قبل الخطوة 6 وبعدها بلا تغيير** — ويبقى بنداً مكتوباً،
         **ولا يُهرَّب إصلاحُه داخل خطوةٍ تمسّ عشرة مسارات مال**.

         **وقرارُ المالك ٢٠٢٦-٠٩-٢٠: يُترك مكتوباً ولا يُصلح الآن** — **لا طريقَ إليه**، لأن منحَ الدور الثاني لا مسارَ له في الشجرة (`create_account` وحده يكتب منحةً، دوراً واحداً، ويحرسه `test_no_route_grants_a_role`). **ولا يُسجَّل بنداً مستقلاً**: بندٌ مستقلٌّ بلا موعدٍ يُنسى، وهذا موعدُه معروف. **بل هو شرطٌ يسبق بناءَ مسار منح الدور الثاني** (**البند ٥ في ترتيب المالك**) — **فلا يُبنى ذلك الباب حتى يُصلح هذا معه في الإيداع نفسِه**، لأن أوّلَ حسابٍ يمرّ منه يبلغ الحالَ التي ترتدّ اليوم ٤٠٩. **والإصلاحُ المقترح بسطرٍ واحدٍ جاهزٍ يومَها**: في `services/deactivation.py:128` يُعلَن نوعُ المحفظة في القراءة — `wallet.balance_of(session, user, declared=WalletOwnerType.RIDER)` (اسمُ الدالّة «رصيدُ محفظة الراكب»، فالإعلانُ يقول ما تقوله التسمية)، ومعه اختبارٌ يحمرّ أوّلاً على الحال (أ). **ولا يُبحث عن الموضع يومَها**: هو هذا السطر بعينه.
       - **كم حساباً يجمع الدورين**: قاعدة التطوير **1** (قِيس 2026-09-19: `users.role` ∪ `user_roles`، راكب وكبتن معاً). **وقاعدة الإنتاج لم تُقس**: المطلقة الثانية في CLAUDE.md تشترط عرض أيّ أمر على قاعدة الإنتاج على المالك قبل تنفيذه ولو قراءةً — والأمر المقترح (قراءة محضة):
         `SELECT count(*) FROM users u WHERE (u.role='rider' OR EXISTS (SELECT 1 FROM user_roles g WHERE g.user_id=u.id AND g.role='rider')) AND (u.role='driver' OR EXISTS (SELECT 1 FROM user_roles g WHERE g.user_id=u.id AND g.role='driver'));`
    2. **`users.wallet_frozen` على الحساب لا على المحفظة.** الموضع: العمود على `users`، ويقرؤه `wallet.require_not_frozen` (`services/wallet.py:99`) في **عشرة مواضع** (`payments:405` · `subscriptions:467` · `tips:133` · `topups:158,213` · `withdrawals:205` · `card_payments:339` · `cliq_topups:104` · `wallet.transfer:366-367`)، ويكتبه باب اللوحة `routers/admin_wallets.py:138`. **الأثر**: تجميد محفظة التاجر يمنع الشخص نفسه من دفع رحلته راكباً وشراء اشتراكه كبتناً وسحب أرباحه — والعكس: تجميد محفظة راكبٍ مخالف يوقف تسوية متجره. **والمخرج المقترح**: التجميد صفةُ محفظة (`owner_type` ومعه معرّف المتجر بحسب Q38)، و`require_not_frozen` يأخذ المحفظة المعنيّة لا الحساب؛ والتجميد القائم على الحساب يبقى "تجميد كل المحافظ" صراحةً لمن أراده.
  - **وتعارضات أخرى كشفها التثبيت — تُسمّى ولا تُحلّ هنا**:
    - **`wallet_balance_non_negative`** (`models/wallet.py:111`) و`record` يرفض ما ينزل تحت الصفر بـ`insufficient_balance`: فـ"تحميل التاجر" (§D19.2) و"مستحقّ لـTAXO على التاجر" (§D18.6-C) يسقطان إن زادا على رصيده — **وكلاهما مكتوب في الملف قيداً على التاجر** (Q35).
    - **قيد صرف التسوية**: التسوية تُخرج المال من محفظة التاجر إليه — قيد مدين. `withdrawal` هو المدين القائم لخروج المال، **وثوابت CLAUDE.md تقول "only drivers have a withdrawal path"**. نوع جديد أم `withdrawal`؟ (Q36)
    - **`wallet.transfer`** يشترط دور `rider` للطرفين (`services/wallet.py:359`) — فمحفظة التاجر والزبون خارجه اليوم كما يجب؛ يُكتب اختبار يثبت ذلك ولا يُفترض (لا سؤال). **الاشتراك مطفأ في الإطلاق (§D1.9)**؛ وحين يُشعل يصير شرط ظهور: انتهى ⇒ يختفي عن الزبائن بعد `merchant_subscription_grace_days` (لا يُحذف ولا تتأثر طلباته الجارية). الأسعار لكل دولة من اللوحة.
- **الكبتن (§D0.7)**: اشتراكه القائم يغطّي الركاب والتوصيل معاً — لا صفّ اشتراك جديد ولا نوع خطة جديد ولا تحقّق ثانٍ؛ ودخول وضع التوصيل يشترط الاشتراك نفسه الذي تشترطه الرحلات. ويمنع اختبارٌ ظهور أي خصم على الكبتن غير المقبوض نيابةً.
- **الزبون**: `service_fee` تُجمَّد لحظة `placed` وتُردّ كاملة مع الطلب عند الإلغاء أو الردّ.
- **العمولة**: `merchant_commission_percent` للدولة، أو override التاجر، أو صفر إن كان `free_until` في المستقبل؛ تُجمَّد لحظة `placed` في `commission_percent_at_order`؛ التقارير والكشوف تقرأ المجمَّد فقط.
- **الصيغة**: كل عمود مال جديد بثلاث منازل، والحقول العشرية غير المالية (المسافات، النجوم، النِّسب) تُصنَّف في سجل الحارس الكانس (`NOT_MONEY` في `tests/money_format.py`) لا تُترك له — والقائمة في §D8.
- **الأداء** (§5-ج من SPEC.md): المسارات الحرجة المسمّاة هناك ثلاثة (نافذة التوزيع · الطلب والقبول · الحلقات)، وحلقة إسناد الطلب تدخل الأولى بنصّها؛ ما يُحتاج للتقرير يُقرأ من الأعمدة المجمَّدة، وتجميع التقارير في الخلفية (`services/stats.py`) لا في اللوحة.

---

### §D6.1 حساب الزبون — القياس الذي وُقِّع عليه §D1 #4 (2026-09-19)

**موقَّع: الخيار (ب) — حساب منفصل بمفتاح `(phone, account_kind)`.** وما اشتراه المالك بالثمن (كلمة مرور منفصلة، وحظر منفصل، وسجلّ ومحفظة وإشعارات لا تلتقي) وعلّة توقيته (الاختبار المغلق) مكتوبان في §D1.4. **والتنفيذ خطة المرحلة 1-أ (§D9.1)**. والقياس أدناه يبقى كما عُرض للتوقيع.

**وما صار بالتوقيع غيرَ لازم**: العطب 1 في §D6 (حساب راكب+زبون يرجع محفظة الراكب صامتاً) **لا يقع للزبون** — حساب `market` لا يحمل دور `rider`؛ ويبقى العطب قائماً في الدالّة لكل حساب يحمل أكثر من غرض (راكب+كبتن اليوم، والتاجر بحسب Q40). وفصل رموز الأجهزة وصندوق الإشعارات والتجميد عن حساب الراكب **يقع تلقائياً للزبون** لأنها معلّقة بـ`user_id` — انظر §D9.1 الخطوة 7.

#### ما يفترض "رقم واحد = مستخدم واحد" اليوم — مُثبَت

- **القيد**: `users.phone` — `String(20), unique=True, index=True, nullable=True` (`models/user.py:26-28`)؛ وتعليقه: "الهاتف هو مُعرّف الدخول". و`NULL` مسموح لحسابات اللوحة وحدها.
- **وقيدان فريدان آخران على الحساب**: البريد المُثبَت `uq_users_email_verified` (`lower(email)` حيث `email_verified_at IS NOT NULL`، `models/user.py:253`)، و`referral_code` فريد عالمياً (`:173`).
- **القراءات بمطابقة الرقم تامّة — أربع**:
  1. `services/auth/base.py:39` — `create_account`: وجود الرقم ⇒ `phone_already_registered` (`PhoneAlreadyRegistered`).
  2. `services/auth/password.py:111` — الدخول بكلمة المرور.
  3. `routers/auth.py:602` — `POST /auth/password-reset`.
  4. `routers/wallet.py:188` — مستقبِل التحويل يُعرف برقمه.
- **مفاتيح Redis بالرقم**:
  - الدخول: `login:phone:{phone}` (`routers/auth.py:369`)؛
  - رمز التحقق: `otp:code/attempts/cooldown:{phone}` (`services/otp.py:58-61`)؛
  - حدوده: `otp:req:window/day/signup:{phone}` · `otp:resend(:step):{phone}` · `otp:locked:{phone}` (`services/otp_limits.py:48-53`).
  - **تسع عائلات مفاتيح، وتعليق `otp.py:220` يعدّ `.format(phone=…)` في 38 موضعاً**.
- **إثبات الملكية بفايربيس**: `services/auth/firebase_identity.verify_phone_ownership` يعيد **رقماً** لا حساباً.
- **البحث الإداري بالرقم (`ilike`) — تسعة مواضع**: `routers/admin_users.py:139,417,800,937` · `services/admin_search.py:69,125` · `services/ride_log.py:136,142` · `services/vehicle_skins.py:192`. تعيد قوائم، فلا تنكسر، لكنها تُظهر للرقم الواحد صفّين في (ب).
- **زرّ التبديل** (`POST /auth/handoff` و`/handoff/exchange`، `routers/auth.py:822,846`، §23 من SPEC.md): ينقل **الحساب نفسه** بين تطبيقين؛ ولا يعبر بين حسابين.
- **حراسة التطبيق** (`core/app_scope.py`): العميل يعلن تطبيقه عند الدخول (`ClientApp`)، والخادم يرفض الدور الذي لا يخصّ ذلك التطبيق — **فالخادم يعرف التطبيق لحظة الدخول سلفاً**.
- **الاختبارات التي تمسّ ذلك**: `tests/test_auth.py` (يثبت `phone_already_registered`) · **17 ملف اختبار** تنادي مسارات الدخول والتسجيل والاستعادة · ملفّان يمسّان مفاتيح OTP · ملفّ للتبديل — من 133 ملف اختبار.

#### ما يتغيّر في كلٍّ

| الموضع | (أ) دور `customer` على الحساب نفسه، بمحفظة مستقلة | (ب) حساب منفصل بالرقم نفسه |
|---|---|---|
| **البديل التقني في (ب)** | — | **مفتاح مركّب `(phone, account_kind)` لا `(phone, app)`**: الراكب والكبتن **حساب واحد بتطبيقين** اليوم (§21، §23)، فـ`app` يشقّهما. `account_kind ∈ {taxo, market}` (والتاجر ثالثٌ إن شُمل)، ويُشتقّ عند الدخول من `ClientApp` المعلَن سلفاً |
| القاعدة | لا شيء على `users` | يُسقط `unique` على `users.phone` ويُستبدل بـ`unique(phone, account_kind)`؛ **ومثله `uq_users_email_verified`**؛ وعمود `account_kind` على `users` ويُملأ للقائم `taxo` |
| التسجيل | مستخدم قائم يسجّل من TAXO MARKET: **لا `phone_already_registered`** بل يُضاف له الدور بعد إثبات الرقم (والقرار: بكلمة مروره القائمة أم برمز؟) — **1 موضع** (`create_account`) + باب التسجيل | `create_account` يفحص `(phone, account_kind)` — **1 موضع** |
| الدخول: كيف يعرف الخادم أيّ حساب؟ | لا يسأل — حساب واحد، و`app_scope` يقبل `customer` في تطبيق السوق — **1 موضع** (`_ROLES`) | يقرأ `account_kind` من `ClientApp` المعلَن ويبحث بـ`(phone, account_kind)` — **2 موضعان** (`password.py:111`، و`app_scope`) + مفتاح `login:phone` (**1**) إن فُصل سقف كل حساب |
| استعادة كلمة المرور | بلا تغيير | `routers/auth.py:602` بالمفتاح المركّب — **1** |
| رمز التحقق الواصل إلى هاتف واحد لحسابين | لا مشكلة — حساب واحد | **الرمز يُربط اليوم بالرقم وحده** (`otp:code:{phone}`): رمزٌ طُلب لحساب السوق يصلح لاستعادة حساب الراكب ما دام الرقم نفسه. فالموضوع يصير `(phone, account_kind)` في **مفاتيح الرمز الثلاثة** (`otp.py:58-61`) ومستدعيها |
| حدود OTP المحسوبة بالرقم | بلا تغيير | **تبقى على الرقم** (الشريحة والكلفة واحدة) — لكن `otp_limits` و`otp` يشتركان في مُعامِل `phone` (38 موضعاً)، **فشقّ الرمز دون الحدود يعني فصل مُعامِلين كانا واحداً** — وهو ما يحذّر منه تعليق `otp.py:212-226` نفسه |
| البحث الإداري (9 مواضع) | بلا تغيير | لا ينكسر؛ يُضاف إلى النتيجة ما يميّز الحسابين — **عرضٌ في اللوحة** لا منطق |
| التحويل برقم المستقبِل | بلا تغيير (التحويل بين راكبين) | `routers/wallet.py:188` يحدّد `account_kind = taxo` — **1** |
| زرّ التبديل | لا يُبنى أصلاً (§D10) | **مستحيل بالبناء** — حسابان لا حساب يتنقّل |
| **مجموع المواضع القائمة التي تُمسّ** | **~3** (`create_account` · باب التسجيل · `app_scope._ROLES`) + خريطة المحافظ (مكتوبة سلفاً، Q37) | **~11 موضعاً مسمّى + ترحيلة تُسقط قيدين فريدين قائمين + فصل مُعامِل OTP (حتى 38 موضعاً)** |
| **الملفات القائمة التي تُمسّ** | ~3 | ~8–10 (`models/user.py` · `auth/base.py` · `auth/password.py` · `routers/auth.py` · `routers/wallet.py` · `core/app_scope.py` · `services/otp.py` · `services/otp_limits.py` · ترحيلة) |
| **الاختبارات** | ~10–15 جديداً، وتعديل `test_auth.py` (حالة "الرقم مسجَّل" تصير "يُضاف الدور") | ~25–35 جديداً، **ومراجعة الملفات الـ17** التي تنشئ حسابات بأرقام ثابتة (أيّها يفترض التفرّد) |

**وحدّ هذا القياس**: عدد "38" منقول من تعليق في الشجرة لا معدود بيدي؛ والأعداد التقديرية (ملفات واختبارات) تقدير لا قياس.

#### ما يفقده (أ) من "الاستقلال التام" — وما لا يُفصل في أيٍّ من الخيارين

| البند | في (أ) | في (ب) | يمكن فصله في (أ)؟ |
|---|---|---|---|
| **كلمة المرور** (`users.password_hash`) | **مشتركة حتماً** — حساب واحد | منفصلة | **لا** — إلا بأن يصير (أ) هو (ب) |
| **الحظر** (`users.is_blocked`) | **مشترك حتماً**: حظر الزبون يحظر الراكب والكبتن | منفصل | **لا** بلا حظرٍ لكل دور — تغيير نمط |
| **التجميد** (`users.wallet_frozen`) | مشترك **اليوم** (العطب 2 في §D6) | منفصل | **نعم** — بمخرج العطب 2 (التجميد صفة محفظة) |
| **الجلسات** (مفاتيح `refresh` بـ`user_id` في `services/token_service.py:21`، و`revoke_all_for_user`) | مشتركة: تسجيل الخروج من كل الأجهزة يُخرجه من التطبيقات كلّها | منفصلة | جزئياً — الرمز لكل تطبيق قائم (`app_scope`)، لكن الإبطال الجماعي على المستخدم |
| **العامل الثاني** (`user_totp`) | لا يخصّ الزبون (للّوحة) | — | — |
| **التدقيق** (`admin_audit_logs` بـ`user_id` الهدف) | مشترك: سجلّ الشخص واحد | منفصل | لا حاجة — يُفرز بنوع الفعل |
| **الاسم والصورة والبريد** (`users.name` · `photo_path` · `email`) | **مشتركة**: الزبون يرى اسم الراكب وصورته | منفصلة | بأعمدة لكل دور — تغيير نمط |
| **رموز الأجهزة** (`device_tokens`: `user_id` · `device_id` · `token` — **بلا عمود تطبيق**) | إشعار طلب الزبون يصل كل تطبيقات الشخص على الجهاز، ومنها تطبيق الراكب | منفصلة | **نعم** — عمود تطبيق على الرمز والإرسال يصفّي به |
| **صندوق الإشعارات** (`user_notifications`: `user_id` · `kind` · … — **بلا عمود تطبيق**) | مشترك | منفصل | **نعم** — بالعمود نفسه أو بـ`kind` |
| **البطاقات المحفوظة** (`saved_cards` بـ`user_id`) | مشتركة: بطاقة حفظها الراكب تظهر للزبون | منفصلة | نعم — بعمود محفظة/تطبيق |
| **الحذف وإلغاء التفعيل** (`services/deletion.py` · `deactivation_requests`) | حذف الحساب يحذف الراكب والزبون معاً | منفصل | لا — الحذف للحساب |
| **رمز الإحالة** (`referral_code` فريد عالمياً) | واحد | اثنان | — |
| **المحفظة والطلبات والعناوين** | **منفصلة** (`owner_type = customer` · جداول الطلب · `customer_addresses`) | منفصلة | — |

**وما لا يُفصل أيّاً كان الخيار**:
- **الرقم نفسه**: شريحة واحدة، فسقوف OTP وكلفة الرسائل وقناة التحقق (SMS/واتساب/فايربيس) تبقى على الرقم.
- **الشخص أمام القانون والتدقيق**: مشرفٌ يبحث بالرقم يجد الشخص في الحالين.
- **الجهاز**: هاتف واحد عليه التطبيقان.

---

## §D7 الأخطاء

كل خطأ باسمه وبسببه بالعربية في السجل المركزي القائم — أصناف `AppError` في `backend/app/core/exceptions.py` بجسم §17 `{code, message, field}`. **والأسماء أسماء الشجرة لا أسماء جديدة** (قرار المالك 2026-09-19): ما له صنف قائم يُستعمل، والجديد على نسق عائلته.

**`design/ERROR-COVERAGE.md`**: رأسه يقول إنه مولَّد من `scratchpad/map_errors.py` — **والمولِّد غير موجود في الشجرة** (بحثٌ عنه باسمه في المستودع كلّه: صفر). فإعادة التوليد **بند مستقل يُقرَّر** (يُبنى المولّد في `tools/` أو يُترك الجدول)، **لا خطوة مفترضة** في أي مرحلة.

### ⛔ ثغرة أمنية: رمز التحقق مربوط بالرقم لا بالحساب — **تُغلق قبل أي شاشة تسجيل للزبون**

**الثغرة**: مفتاح رمز التحقق اليوم **الرقم وحده** — `otp:code:{phone}` و`otp:attempts:{phone}` و`otp:cooldown:{phone}` (`services/otp.py:58-61`). فبعد §D1 #4 يصير للرقم الواحد حسابان، و**رمزٌ طُلب لحساب الزبون يصلح لاستعادة كلمة مرور حساب الراكب** (أو العكس): من يملك الشريحة لحظةً — أو يسجّل حساب زبون برقم غيره إن فُتح التسجيل بلا إثبات — يأخذ رمزاً صالحاً لحسابٍ ليس الذي طلبه. **وهي ثغرة استيلاء على حساب، لا بند تقني.**

**والإغلاق**:
- **يُضاف `account_kind` إلى مفاتيح الرمز الثلاثة** — `otp:code:{phone}:{kind}` وأختاها — ويُمرَّر من كل مستدعٍ (الطلب، والتسجيل، والاستعادة، وإثبات الرقم).
- **وتبقى حدود OTP على الرقم وحده** (`services/otp_limits.py:48-53` — ستّ عائلات): الشريحة واحدة والكلفة واحدة، وشقّها يضاعف السقف لمن يملك رقماً.
- **شرطٌ يسبق أي شاشة تسجيل للزبون**، ويُثبت باختبار يُكتب **قبل** الإصلاح فيحمرّ: رمزٌ صدر لـ`market` يُرفض في استعادة `taxo` بالرقم نفسه.
- **وحدُّ الإغلاق — إثباتُ Firebase**: `verification.verify` يقبل **رمزَ هوية Firebase** بديلاً عن الرمز (`services/auth/firebase_identity.verify_phone_ownership`)، وهو يُثبت **ملكيةَ الرقم** لا الحساب، **ولا يُستهلك** بعد استعماله. فإغلاقُ مفاتيح الرمز الثلاثة لا يغلق هذا الوجه: رمزُ هوية Firebase صدر في سياق الزبون يصلح في سياق الراكب ما دام صالحاً. **ويُقرَّر قبل شاشة تسجيل الزبون**: يُربط النوعُ بسياق التحقّق (ختمٌ في Redis بعمر قصير) أم يُقبل الحدُّ مكتوباً لأن حاملَ الرمز يملك الشريحة (§D11-Q43).

  **وقرارُ المالك ٢٠٢٦-٠٩-٢٠ — يُقبل مكتوباً اليوم، ويُغلق في المرحلة 5 قبل أوّل شاشة تسجيلٍ للزبون** (لا يُنفَّذ الآن):
  - **الحدُّ بوصفه، لا بتخفيفه**: إثباتُ ملكية الرقم عبر Firebase **غيرُ مربوطٍ بنوع الحساب، ولا يُستهلك بعد استعماله** — فإثباتٌ صدر لحسابٍ **يصلح لحسابٍ آخر بالرقم نفسِه**، ما دام صالحاً. وهو الوجهُ الباقي من ثغرة الرمز بعد أن أُغلقت مفاتيحُها الثلاثة (1-أ/5)، **ومداه ما يقبل `verification_token`**: التسجيل، والاستعادة، وإثباتُ الرقم.
  - **وعلّةُ قبوله اليومَ مكتوبةٌ لا مسكوتٌ عنها**: **لا حسابَ من نوعٍ آخرَ يوجد بعد** — كلُّ حسابٍ في القاعدة `taxo`، ولا تطبيقَ للزبون ولا للتاجر، **فلا حسابَ ثانياً بالرقم نفسِه ليُستولى عليه**. الثغرةُ تُولد يومَ تُفتح شاشةُ تسجيل الزبون، لا قبلَه.
  - **والإغلاقُ يومَها شيئان معاً**: **نوعُ الحساب يدخل في الإثبات** (الرمزُ يُقبل للنوع الذي صدر له وحدَه)، **وأحاديةُ الاستعمال** (ختمُ استهلاكٍ في Redis بعمر الإثبات، فلا يُقدَّم الإثباتُ نفسُه مرّتين). **والشرطان معاً لا أحدُهما**: الربطُ بلا استهلاكٍ يترك إثباتاً واحداً يفتح البابَ مراراً في نوعه، والاستهلاكُ بلا ربطٍ يترك أوّلَ استعمالٍ يقع على الحساب الخطأ.
  - **وموعدُه شرطٌ لا نيّة**: **المرحلة 5 (TAXO MARKET)، قبل شاشة التسجيل فيها** — على منوال «تُغلق قبل أيِّ شاشة تسجيلٍ للزبون» في رأس هذا البند، ويُثبت باختبارٍ يُكتب **قبل** الإصلاح فيحمرّ: إثباتُ Firebase صدر في سياق `market` يُرفض في استعادة `taxo` بالرقم نفسِه، **وإثباتٌ استُعمل مرّةً يُرفض في الثانية**.
- **ولا يُنشر `account_kind` في أي رسالة خطأ بما يكشف وجود حساب آخر بالرقم نفسه**: دخولٌ إلى السوق برقمٍ له حساب `taxo` وحده يُردّ بخطأ الاعتماد العامّ (`InvalidCredentials`) لا بـ"هذا حساب راكب"؛ والاستعادة لحساب غير موجود من هذا النوع تُردّ كما تُردّ اليوم لرقم لا حساب له — **ولا تُذكر كلمة "راكب" أو "زبون" في رسالة موجّهة لمن لم يثبت ملكيّة الحساب المعني**. (ورسائل `WrongAppForRole` في `core/app_scope.py` تسمّي الدور — وهي تقع بعد مطابقة كلمة المرور للحساب نفسه، فلا تكشف الحساب الآخر.)

### عطب قائم في الشجرة — **وإصلاحه شرط في المرحلة 1 قبل أي غرض جديد**

**`card_payments.py:466-469`** (تسوية طلب بطاقة مدفوع):

```
if order.purpose == RIDE_PAYMENT:  _settle_ride_payment
elif order.purpose == SUBSCRIPTION: _activate_subscription
else:                               _credit_wallet_topup
```

**الأثر**: **كل غرض لا يعرفه الفرع يُقيَّد شحناً للمحفظة بلا خطأ** — طلب بطاقة لاشتراك تاجر (`merchant_subscription`)، أو أي غرض يُضاف بعده، يصير مالاً في محفظة صاحب الطلب بدل ما دُفع لأجله، ولا يفشل شيء ظاهر (الشكل الثاني عشر: احتياطٌ يعمل ويخفي العطب). **والإصلاح — لا يُنفَّذ الآن**: تعداد الأغراض صراحةً (`wallet_topup` فرعٌ باسمه) ورفض المجهول بخطأ يُسجَّل، ويُكتب قبل ترحيلة قيمة `merchant_subscription` في المرحلة 1، ومعه اختبار يمرّر غرضاً مجهولاً ويتوقّع الرفض لا القيد.

### القائم — يُستعمل كما هو

| code | HTTP | الصنف | موضعه في الطلب |
|---|---|---|---|
| `insufficient_balance` | 409 | `InsufficientBalance` | طلب بالمحفظة والرصيد دون `total` (field: `payment_method`) — **لا `wallet_insufficient` ولا 402** |
| `not_found` | 404 | `NotFound` | طلب ليس الفاعل طرفاً فيه — **على نسق الرحلات**: `rides.get_ride_for_user` يردّ `NotFound("الرحلة غير موجودة")` لغير صاحبها ولا يكشف وجودها (§14). فـ`order_not_owned` (403) في 0.1 **سقط** |
| `permission_denied` | 403 | `PermissionDenied` | دور لا يملك الفعل أصلاً (مندوب يطلب ما ليس لتاجره) |
| `invalid_input` | 422 | `InvalidInput` | سبب إلزامي فارغ، أو خيار نزاع خارج القائمة |
| `rate_limited` | 429 | `RateLimited` | محاولات رمز التسليم إن قُرئت كحدّ معدّل — والنصّ أدناه يفضّل `delivery_code_locked` |

### يُبنى — على نسق العائلات القائمة

| code | HTTP | المعنى | field |
|---|---|---|---|
| `invalid_order_transition` | 409 | انتقال غير مسموح من الحالة الحالية — **نسق `invalid_ride_transition` / `invalid_status_transition` / `invalid_payment_transition`** (0.1 كانت `invalid_transition`) | `status` |
| `merchant_not_active` | 403 | التاجر غير معتمَد أو موقوف | — |
| `merchant_subscription_expired` | 403 | اشتراك التاجر منتهٍ (لا يقع ما دام الاشتراك مطفأ) | — |
| `driver_subscription_required` | 403 | دخول وضع التوصيل بلا اشتراك سارٍ — **جديد**: لا فحص اشتراك عند `go_online` اليوم (§D4) | — |
| `branch_closed` | 409 | الفرع مغلق الآن | `branch_id` |
| `item_unavailable` | 409 | صنف غير متوفّر في هذا الفرع | `items[i]` |
| `option_selection_invalid` | 422 | اختيار خيارات خارج min/max | `items[i].options` |
| `below_min_order_amount` | 422 | الأصناف دون الحدّ الأدنى للتاجر (§D13.1-14) | `items` |
| `out_of_delivery_radius` | 422 | العنوان خارج نطاق التوصيل | `address` |
| `customer_cash_blocked` | 403 | الكاش محجوب عن هذا الزبون | `payment_method` |
| `delivery_disabled_in_country` | 403 | التوصيل غير مفعَّل في هذه الدولة — يقرأ `delivery_settings.delivery_enabled` (قرار Q23)؛ **ولا يُستعمل `feature_disabled`** لأنه خطأ مفاتيح `feature_flags` | — |
| `order_report_window_closed` | 409 | مضت مهلة البلاغ على الطلب (§D13.1-6) | — |
| `pickup_not_available` | 409 | الاستلام الذاتي غير مفعَّل لهذا التاجر | `fulfilment` |
| `drop_at_door_not_allowed` | 409 | "اتركه عند الباب" ممنوع على الدفع نقداً | `drop_at_door` |
| `driver_not_in_delivery_mode` | 409 | فعل توصيل من كبتن خارج الوضع | — |
| `driver_has_active_order` | 409 | خروج من الوضع أو رحلة مع طلب جارٍ | — |
| `cash_cap_exceeded` | 409 | تجاوز سقف النقد (الإداري أو المعلَن) | — |
| `concurrent_orders_limit` | 409 | بلغ الحدّ الأقصى للطلبات الجارية | — |
| `delivery_offer_expired` | 409 | قبول عرض طلب انتهت مهلته — نسق `ride_offer_expired` (`RideOfferExpired`) | — |
| `delivery_code_invalid` | 422 | رمز التسليم غير صحيح | `delivery_code` |
| `delivery_code_locked` | 423 | ثلاث محاولات — بانتظار تأكيد الزبون | `delivery_code` |
| `merchant_accept_timeout` | 410 | انقضت مهلة القبول | — |
| `undeliverable_photo_required` | 422 | صورة إلزامية لتعليم الطلب غير قابل للتسليم | `photo` |

### يُبنى — الجهاز والطباعة (§D15)

| code | HTTP | المعنى | field |
|---|---|---|---|
| `device_provisioning_code_invalid` | 422 | رمز التجهيز خاطئ أو مستعمَل أو منتهٍ (بلا تفريق، كرسالة الرمز) | `code` |
| `device_revoked` | 401 | الجهاز أُبطل من اللوحة — جلسته ساقطة | — |
| `device_not_assigned` | 409 | جهاز بلا فرع يطلب طلبات | — |
| `print_ack_not_applicable` | 409 | إقرار طباعة لطلب ليس لفرع هذا الجهاز أو في حالة لا تُطبع | `order_id` |

### يُبنى — النزاع (§D19)

| code | HTTP | المعنى | field |
|---|---|---|---|
| `dispute_option_not_applicable` | 422 | خيار من قائمة نزاع لا تخصّ هذه الحالة (خيار §D19.2 على طلب undeliverable) | `option` |
| `dispute_reason_required` | 422 | قرار نزاع بلا سبب مكتوب | `reason` |
| `order_not_in_review` | 409 | قرار نزاع على طلب ليس في `pending_review` — نسق `invalid_order_transition` ويمكن أن يُطوى فيه | — |
| `settlement_not_pending` | 409 | تسجيل دفع أو إقرار على دورة تسوية ليست `pending` (§D18.2) | — |

وإقرار استلام من غير التاجر صاحب الدورة يُردّ بـ`not_found` القائم (نسق §14)، لا باسم جديد.

والرسالة النهائية بيد الوكيل بأسلوب السجل، والمذكَّر ليس افتراضاً صامتاً (`tests/test_label_gender.py`).

---

## §D8 الحرّاس

| الحارس | امتداده |
|---|---|
| `check:doors` (قائم، `admin-panel/scripts/check-doors.mjs`) | يمسح مسارات §D5 كلها — لا مسار بلا زرّ إلا بعلّة مكتوبة |
| `check:contract` (قائم، `tools/check-contract.mjs --app …`) | يمتدّ إلى التطبيقين الجديدين ومسارات الكبتن الجديدة — كل نداء يقابل فعلاً ومساراً |
| الحارس الكانس للمال (قائم، `backend/tests/money_format.py`) | انظر القائمة أدناه |
| `check:enums` (قائم، `scripts/check-enums.mjs` **في كل تطبيق**) | الاتحادات الجديدة: حالة الطلب · طريقة الدفع · `actor_type` · حالة التاجر · أسباب الإلغاء · أسباب undeliverable · خيارات النزاع (§D19) · علامات التقييم · فئة ← قسم (§D1.5) — اتحاد واحد بين الخلفية وكل تطبيق يقرؤه |
| `check:config` (قائم، `scripts/check-config.mjs` في كل تطبيق) | ما يُنشر من `delivery_settings` في `GET /config` له مرآة في التطبيق الذي يقرؤه، ولا حقل بلا مرآة (§D2) |
| `check:money` · `check:money-math` · `check:money-visible` (قائمة، `tools/`) | تمتدّ إلى التطبيقين: لا حساب مال في الواجهة، وكل قيمة مال تحسبها الخلفية تصل واجهة |
| **`check:transitions` (يُبنى)** | لكل خلية في مصفوفة §D3 اختباران: المسموح يمرّ، والممنوع يُرفض بـ`invalid_order_transition` أو `not_found` (لغير الطرف) باسمه؛ والمصفوفة ملف واحد يقرأه الطرفان |
| `tests/test_locks_have_tests.py` (قائم) | كل قفل صفّ جديد (الطلب، دورة التسوية، صفّ الدَّين) له اختبار تزامن |
| `tests/test_two_doors.py` (قائم) | بطاقة التاجر "حالتك اليوم" وما يحاسب به الخادم مصدر واحد (§D1.9) — حمولة متعددة الأبواب تُصنَّف فيه |
| `tests/test_migrations.py` (قائم) | كل ترحيلة قيمة تعداد (§D2) و`downgrade` لها |
| خطوة صفر | تصبح **خماسية**: admin-panel · customer-app · driver-app · وتطبيقا التوصيل — المبنيّ = ما تخدمه الحاوية = ما يصل عبر النفق (`check:served`) |
| البابان المحلّيان | `scripts/suite.sh` للمجموعة و`scripts/guards.sh` للحرّاس الساكنة — قائمان، ويُشغَّلان قبل كل إيداع |
| الاختبارات | خضراء قبل كل وسم؛ كل مرحلة تضيف اختباراتها ولا تعدّل اختباراً قائماً إلا بإذن |

**الحارس الكانس اليوم لا يلتقط هذه الأسماء المالية الجديدة** (قرار المالك: تُصنَّف في المرحلة 1). يلتقط ما في `MONEY_NAMES` أو ما ينتهي بـ`_amount · _fare · _price · _fee · _balance · _total · _budget · _bonus · _reward · _charge` (`MONEY_SUFFIXES`، `tests/money_format.py:37`)، ويستثني `NOT_MONEY = {discount_value, duration_min, distance_km}`:

| الاسم | لماذا يفلت | التصنيف المطلوب |
|---|---|---|
| `subtotal` · `total` | ليسا في `MONEY_NAMES` ولا ينتهيان بلاحقة (`_total` بشرطة) | مال |
| `merchant_net` | بلا لاحقة | مال |
| `price_delta` | ينتهي بـ`_delta` | مال |
| `delivery_per_km` | ينتهي بـ`_km` | مال |
| `service_fee_fixed` · `service_fee_max` | ينتهيان بـ`_fixed` / `_max` | مال |
| `driver_cash_exposure_cap_default` · `cash_exposure_cap_override` · `cash_on_hand_limit` · `exposure_at_offer` | بلا لاحقة مالية | مال |
| `next_commission_percent` · `merchant_commission_percent` · `service_fee_percent` · `commission_percent_at_order` · `commission_percent_override` | نسب | **ليست مالاً** — تُسمّى في `NOT_MONEY` صراحةً إن التقطها أحد الأنماط |
| `delivery_max_distance_km` · `delivery_dispatch_radius_km` · `delivery_radius_km` | مسافات | ليست مالاً |

وما يلتقطه الحارس سلفاً: `commission_amount` · `delivery_fee` · `service_fee` · `delivery_base_fee` · `delivery_min_fee` · `delivery_max_fee` · `unit_price` · `base_price` · `line_total` · `min_order_amount` · `deposit_amount` · `monthly_fee`.

---

## §D9 المراحل

لا تبدأ مرحلة قبل وسم سابقتها؛ متغيّر واحد في كل مرة؛ إيداع ووسم بعد المراجعة **بصيغة الوسوم القائمة `vX.Y.Z`** (آخرها في الشجرة `v0.2.2`) — وأسماء الوسوم المقترحة في 0.1 حُذفت بقرار المالك (2026-09-19). رقم الوسم يُختار عند الوسم لا يُكتب هنا.

| # | المرحلة | المدخلات | المخرج | القياس قبل الوسم |
|---|---|---|---|---|
| 0 | هذا الملف | قرارات §D0/§D1 | SPEC-DELIVERY.md مراجَع، §D11 مجابة | — |
| 1-أ | **مفتاح الحساب — لا شيء من التوصيل** (§D9.1) | §D1.4 · §D6 · §D6.1 · §D7 | `account_kind` وحذف القيدين الفريدين وإحلال المركّبين · الدخول والتسجيل والاستعادة بالمفتاح المركّب · مفاتيح الرمز الثلاثة · التجميد صفة محفظة · إصلاح `card_payments.py:466-469` · إصلاح `owner_type_for` والنداءات الخمسة بلا إعلان | خطوات §D9.1 وقياس كلٍّ منها؛ والمجموعة كاملة خضراء؛ ودخول الحسابات التجريبية القائمة على هاتف المالك يعمل كما كان |
| 1-ب | الخلفية: التاجر وقائمته + اللوحة | §D1.5 · §D1.6 · §D2 · §D5 (التجار، الإعدادات، الاشتراكات) | جداول التاجر والقائمة و`merchant_subscription_plans` والاشتراك بترحيلاتها · ترحيلات قيم التعداد (§D2) · `delivery_settings` · مسارات التاجر · شاشات اللوحة · تصنيف الأسماء المالية في الحارس الكانس (§D8) | تاجر يُنشأ من الـAPI، يرفع وثائقه، يُعتمد من اللوحة بعد عرض الصورة، يبني قائمة بخيارات، ينتهي اشتراكه فيختفي |
| 2 | الخلفية: الطلب | §D3 · §D1.1 · §D1.2 · §D1.3 · §D7 · §D19 · `check:transitions` | `delivery_orders` وتوابعها · مصفوفة الانتقالات · التسعير والتجميد · خصم المحفظة وردّها · صفوف الدَّين بمصادرها و`driver_debt_payments` · الحلقة الثانية وشرط الحصرية في الإسناد · مهلات beat (القبول، التنبيه، الزوج المؤجَّل) · الإشعارات | سيناريو §D16 كاملاً من الـAPI بلا تطبيقات: كبتن مبذور في وضع التوصيل، طلب كاش وطلب محفظة حتى `delivered`، ورفض وانقضاء وundeliverable بقرار نزاع، والدفتر وصفوف الدَّين تطابق §D1.1 قرشاً بقرش |
| 3 | TAXO MERCHANT + الجهاز | §D1.5 · §D3 · §D15 · §D14.أ (3،4) | تطبيق ويب + غلاف Capacitor **بكود أصلي** (§D15): تسجيل، وثائق، القائمة والتوفّر، زرّ "نفد الصنف"، القائمة الموقوتة، الساعات، استقبال الطلب بصوت وطباعة، الانتقالات، "المستحق نقداً"، **شاشة التقارير وإشعار FCM** (بديل تقرير واتساب المؤجَّل، §D10) | على جهاز: طلب مبذور يُطبع ويُقبل ويُحضَّر ويُعلَّم جاهزاً — والتطبيق مغلق مرّةً والشاشة مطفأة مرّة |
| 4 | وضع التوصيل في TAXO DRIVER | §D4 · §D17 | الزرّ، الحصرية والاستثناء، صفحة التوصيل، الانتقالات، الرمز، بند الأرباح، الدَّين بمصادره | على جهازين: كبتن في الوضع **لا** تصله رحلة حقيقية ولا يظهر على خريطة الراكب، وبالاستثناء تصله؛ استلام وتسليم بالرمز؛ دَينه ومحفظته تطابق §D1.1 |
| 5 | TAXO MARKET | §D1.4 · §D1.8 · §D3 · §D14.أ (1،2،5) | تطبيق ويب + غلاف: تسجيل، عناوين، شاشة أولى بكل المتاجر القريبة وشريط أقسام، تصفّح، سلة بخيارات، طلب، تتبّع الكبتن، رمز التسليم، محفظة، تقييم — **والإشعار بالمسار الأصلي** (§D15.0) | على جهاز: طلب حقيقي من مطعم على جهاز ثانٍ يوصله كبتن على جهاز ثالث |
| 6 | المال والتقارير والتسويات | §D6 · §D18 · §D5 (الطلبات، التقارير، الكباتن، التسويات) | الردّ من اللوحة، سقف النقد، حجب الكاش، دورات التسوية والمندوب، الكشوف، التقارير | كل شاشة مال تُفحص بالضغط من أول عنصر (الشكل التاسع)، والصيغة 0.000 في كل موضع |
| 7 | القنوات والنشر (**الأردن أولاً**) | §D1.7 · §D0.9 · §18.1 | تطبيقان في `channels.json` · نطاقان على النفق · تطبيقان في مشروع Firebase · صفحة التحميل · التوقيع · خطوة صفر الخماسية | جولة ثلاثة أجهزة (زبون + مطعم + كبتن) على النطاقات العامّة، وعيوبها تُصلح كلها قبل الوسم |

**علّة شقّ المرحلة 1 (قرار المالك 2026-09-19)**: نصفٌ (1-أ) يُثبت أن المفتاح الجديد يعمل **وأن ما يعمل اليوم لم ينكسر** — قبل أن يُبنى فوقه تاجر وقائمة وطلبات. فلو اجتمعا في وسم واحد لما عُرف أعطبُ دخولٍ سببُه المفتاح أم التاجر. ولكلٍّ وسمه بصيغة `vX.Y.Z`.

**ورخصة "البيانات بيانات اختبار" لها حدّ مكتوب**: هي قائمة ما دام المشروع في اختبار مغلق (لا مستخدم حقيقي؛ كل الصفوف من إنشاء المالك)، **وتنتهي عند أول مستخدم حقيقي**. بعده يعود كل تغيير في جدول المستخدمين إلى **قاعدة الترحيل المقيس**: العدد قبل = العدد بعد، وخريطة متطابقة (كل صفّ قديم يقابله صفّ جديد بمعرّفه)، و`downgrade` مُشغَّل لا مقروء. **ولا تُرخّص هذه الرخصة شيئاً ممّا تمنعه مطلقات CLAUDE.md** (§D9.1، "الطريقان").

علّة الترتيب: كل مرحلة تُقاس بما قبلها وحده — الطلب يُقاس من الـAPI قبل أن يوجد تطبيق، والمطعم قبل الكبتن لأن الكبتن يحتاج طلباً جاهزاً، والزبون آخراً لأنه الوحيد الذي لا يستطيع شيئاً قبل وجود مطعم وكبتن.

---

### §D9.1 خطة المرحلة 1-أ — مفتاح الحساب (تُكتب قبل أي كود، 2026-09-19)

**ولا شيء من التوصيل فيها**: لا تاجر ولا طلب ولا إعداد توصيل. ما يُبنى هنا يمسّ ما يعمل اليوم وحده، ويُقاس بأنه ما زال يعمل.

#### البنية الجديدة

- **نوع postgres جديد `account_kind`** بثلاث قيم: `taxo` (الراكب والكبتن واللوحة — كل حساب قائم) و`market` (الزبون) و`merchant` (التاجر — Q40، مقرَّر).
- **عمود `users.account_kind`** — `NOT NULL`، `server_default 'taxo'`. **ويُملأ بإضافة العمود نفسها**: postgres يكتب القيمة الافتراضية على كل صفّ قائم في الأمر نفسه، فلا `UPDATE` على أي صفّ.
- **الهاتف**: يُسقط الفهرس الفريد `ix_users_phone` (الترحيلة `0002`) ويحلّ محلّه **فهرس فريد `(phone, account_kind)`** وفهرسٌ عاديّ على `phone` للبحث. و`NULL` في الهاتف يبقى مسموحاً لحسابات اللوحة (postgres لا يعدّ `NULL` مكرَّراً).
- **البريد**: يُسقط `uq_users_email_verified` (`lower(email)` حيث `email_verified_at IS NOT NULL`) ويحلّ محلّه **`(lower(email), account_kind)` بالشرط نفسه**.
- **`referral_code`** يبقى فريداً عالمياً (`models/user.py:173`) — كل حساب رمزه.
- **كيف يُعرف النوع عند الدخول**: من `ClientApp` الذي يعلنه العميل **سلفاً** (`core/app_scope.py`): `rider`/`driver`/`panel` ⇒ `taxo`، والسوق ⇒ `market`. **و`app = None`** (عميل لم يُعلن: أدوات الفحص والحِزم الأقدم — مسموح اليوم، `schemas/auth.py:43,76,107,247`) ⇒ **`taxo`** — فكل حزمة مثبّتة اليوم تبقى تدخل كما تدخل.
- **وما يلزم إثباته صحّة البنية لا بقاء كل صفّ**: القيود تمنع المكرَّر من النوع نفسه وتقبل النوعين · الفهارس موجودة بأسمائها · الدخول والتسجيل والاستعادة تجد الحساب الصحيح بالمفتاح المركّب · والرمز لا يعبر بين النوعين. **وبقاء الصفوف القائمة يأتي مجّاناً** مع الطريق المختار أدناه، لا هدفاً يُقاس لذاته.

#### الطريقان — ترحيل الصفوف القائمة أم بذر قاعدة نظيفة (بالأرقام)

| | ترحيل (إضافة وإحلال) | بذر قاعدة نظيفة |
|---|---|---|
| ما يُنفَّذ | ترحيلة واحدة: `ADD COLUMN … DEFAULT 'taxo'` · إسقاط فهرسين · إنشاء فهرسين (وفهرس بحث) — **5 أوامر DDL** | إسقاط القاعدة أو **94 جدولاً**، ثم `alembic upgrade` من الصفر (**71 ملفّ ترحيلة**، حتى `0071`)، ثم `scripts/seed.py` |
| صفوف تُحذف | **0** | **كلّها** — ومنها `wallet_transactions` الذي يرفض `DELETE` بمُشغّل (الترحيلة `0006`)، فلا يُمحى إلا بإسقاط الجدول |
| صفوف تُعدَّل | 0 بأمر `UPDATE` (القيمة الافتراضية تُكتب مع العمود) | — |
| ما يعيده البذر | — | `seed.py` يبذر الإعدادات ومشرفاً واحداً (`seed_bootstrap_admin`)، و**لا يبذر** حسابات المالك التجريبية (راكب، كبتن بوثائقه ومركبته واعتماده واشتراكه)، ولا العقود المُدخلة من صفحة العقود خارج ما في البيئة |
| دخول هاتف المالك | **كما هو** — الصفّ نفسه وكلمة المرور نفسها والجلسة نفسها | **يسقط** — الحسابات تُعاد يدوياً، والجلسات تبطل، والكبتن يعيد وثائقه واعتماده |
| الرجوع | `downgrade` معكوس DDL — **يعمل ما دام لا رقمَ بحسابين** (أي قبل أول حساب `market`)، ويُقاس في دورة `upgrade → downgrade → upgrade` على قاعدة التطوير | النسخة الاحتياطية وحدها |
| مطلقات CLAUDE.md | لا تُمسّ: لا `UPDATE` ولا `DELETE` على جدول مال، ولا حذف صفّ | **تُخرق**: "ولا حذفَ صفٍّ على الإنتاج إطلاقاً"، و"لا UPDATE ولا DELETE يدوياً على أيِّ جدولِ مال" |

**فالبذر النظيف ليس أبسط هنا ولا أقلّ خطراً**: التغيير **إضافيّ** (عمود وقيدان يحلّان محلّ قيدين)، والترحيل يؤدّيه بخمسة أوامر بلا لمس صفّ، والبذر يحذف كل شيء ليعيد أقلّ ممّا حذف. **وهو فوق ذلك مغلق بمطلقات CLAUDE.md** التي لا تُوازَن بشيء — ورخصة "بيانات اختبار" لا تفتحه؛ فتحُه تعديلٌ في CLAUDE.md بيد المالك وحده، ولا يُقترح هنا. **والبذر النظيف صالحٌ لقاعدة التطوير وقاعدة الاختبار** (`taxo_test` تُبنى من الصفر في كل تشغيل للمجموعة أصلاً) — لا للإنتاج.

#### كل موضع يفترض "رقم واحد = مستخدم واحد" — وما يصير إليه

**مقيسٌ على شجرة WSL (`/home/loly3/prj/TAXO`، الرأس `5ccd009`، 2026-09-19)** — لا على نسخة ويندوز التي قِيس عليها الجدولُ أوّلَ مرّة. **وهي المرّةُ الثانية للشكل الثامنَ عشر** (`PATTERNS.md`، ٢٠٢٦-٠٩-٠٧): المرحلة 0 وخطةُ 1-أ وإيداعان كُتبت على `D:\prj\TAXO` المتأخّرة بـ99 إيداعاً، **وما أمسكها لم يكن قراءةَ شيفرة بل قياسُ قاعدة التطوير** (`alembic_version = 0075` والشجرةُ على `0071`). والفرقُ عن قياس ويندوز في آخر القسم.

| # | الموضع (WSL) | اليوم | يصير |
|---|---|---|---|
| 1 | `models/user.py:27` | `phone` بـ`unique=True` | `unique` يُنزع؛ و`UniqueConstraint("phone", "account_kind")` في `__table_args__` |
| 2 | `models/user.py:267` | `uq_users_email_verified` على `lower(email)` | على `(lower(email), account_kind)` بالشرط نفسه |
| 3 | `alembic/versions/0002_users_drivers_vehicles.py:35` | `ix_users_phone` فريد | ترحيلة جديدة **`0076`** (آخرُ رقمٍ فعليٍّ في WSL `0075_account_deactivation`) تُسقطه وتنشئ المركّب |
| 4 | `services/auth/base.py:39` (`create_account`) | وجود الرقم ⇒ `phone_already_registered` | وجود `(phone, kind)` ⇒ الخطأ نفسه |
| 5 | `services/auth/password.py:116` (الدخول) | `where(User.phone == phone)` | `where(phone, account_kind = kind_of(app))` |
| 6 | `routers/auth.py:643` (`POST /auth/password-reset`، الباب `:613`) | بالرقم | بالمفتاح المركّب، والنوع من `app` |
| 7 | `routers/auth.py:169` (`/challenge`) · `:243` (`/register`) · `:574` (`/password-reset/challenge`) · `:533` (`/me/verify-phone`)؛ ونداءات `verification.verify` في `:278` · `:548` · `:639` | يطلبون الرمز ويتحقّقون بالرقم | يمرّرون النوع إلى `verification` ← `otp.issue/verify` (`services/verification.py:309,355,390,478,508`) |
| 8 | `services/otp.py:58,59,61` | مفاتيح الرمز الثلاثة بالرقم | **بالرقم والنوع** — إغلاق الثغرة (§D7) |
| 9 | `services/otp_limits.py:48-53` | ستّ عائلات بالرقم | **بلا تغيير** |
| 10 | `routers/auth.py:410` (`login:phone:{phone}`) | سقف محاولات الدخول بالرقم | **بالرقم ونوع الحساب** (Q42) |
| 11 | `services/auth/firebase_identity.py:23` (`verify_phone_ownership`) | يعيد رقماً | بلا تغيير — **ولا يُربط بالنوع ولا يُستهلك** (حدٌّ للخطوة 5، يُكتب في §D7) |
| 12 | `routers/wallet.py:188` (مستقبِل التحويل) | بالرقم | `account_kind = taxo` |
| 13 | `core/app_scope.py:39` (`_ROLES`) | ثلاثة تطبيقات | + خريطة `ClientApp ⇒ account_kind`، و`None ⇒ taxo` |
| 14 | `scripts/seed.py:783` · `scripts/provision_round_captain.py:68` · `scripts/totp_reset.py:42` | بالرقم | `account_kind = taxo` صراحةً |
| 15 | البحث بالرقم (`ilike`) — **ثمانية مواضع**: `services/admin_search.py:69,125,157` · `routers/admin_users.py:801,938` · `services/ride_log.py:136,142` · `services/vehicle_skins.py:192` | قوائم | بلا تغيير في المنطق؛ ويُعرض النوع بجانب الرقم |
| 16 | `/auth/handoff` و`/handoff/exchange` (`routers/auth.py:863,887`) | الحساب نفسه بين تطبيقين | بلا تغيير — ويُختبر أنه لا يعبر بين نوعين |

**الفرقُ عن قياس نسخة ويندوز** (`D:\prj\TAXO` عند `5eadb43`):
- **لم يتغيّر موضعُه (7 صفوف)**: 3 · 4 · 8 · 9 · 11 · 12 · 14.
- **تغيّر سطرُه والمعنى واحد (8 صفوف)**: 1 (`26→27`) · 2 (`253→267`) · 5 (`111→116`) · 6 (`602→643`) · 7 (`168→169`، `207→243`، `533→574`، `492→533`، ونداءات `verification` كلُّها) · 10 (`369→410`) · 13 (`_ROLES` مسمّى بسطره `39`) · 16 (`822,846→863,887`).
- **تغيّر شكلُه (صفٌّ واحد، 15)**: كانت تسعة مواضع ⇒ **ثمانية**: **اختفى** `admin_users.py:139,417` (صارا يمرّان بالمساعد) و**ظهر** `admin_search.py:157` (المساعد نفسُه).
- **ولم يظهر موضعٌ جديدٌ يفترض التفرّد** في الإيداعات الـ99 بعد `5eadb43` (بحثٌ في الفرق عن `User.phone` و`phone ==` و`:{phone}`: سطرٌ واحد، هو مساعد البحث).

#### ترتيب العمل — خطوة خطوة، وما يُقاس بعد كلٍّ

**قبل الخطوة الأولى**: الشجرة نظيفة؛ والمجموعة كاملة خضراء بعدّها المسجَّل (`scripts/suite.sh` — آخر عدّ في HANDOFF 1356)؛ و`scripts/guards.sh` أخضر. **ومتغيّر واحد في كل خطوة، وإيداع بعد كلّ خطوة خضراء.**

1. **إصلاح `card_payments.py:466-469`** (أصغرها وأبعدها عن المفتاح): تعداد الأغراض صراحةً (`wallet_topup` فرعٌ باسمه) ورفض المجهول. **القياس**: اختبار يمرّر غرضاً لا يعرفه الفرع ويتوقّع الرفض لا القيد — يُكتب أولاً ويحمرّ؛ واختبارات الشحن بالبطاقة القائمة خضراء كما هي.
2. **`owner_type_for` والنداءات الخمسة**: الدالّة ترتدّ بـ`wallet_owner_undecided` متى حمل الحساب أكثر من غرض محفظة (لا راكب+كبتن وحدهما)، والنداءات الخمسة (`admin_wallets.py:63,98,137` · `cancellation.py:225` · `payments.py:409`) تعلن محفظتها. **القياس**: لكل نداء اختبار بحساب يحمل غرضين؛ و`test_user_roles.py` (حالات `wallet_owner_undecided` القائمة) أخضر بلا تعديل.
3. **الترحيلة**: `account_kind` والقيدان المركّبان (بعد جواب Q40). **القياس**: دورة `upgrade → downgrade → upgrade` خضراء على قاعدة التطوير؛ `tests/test_migrations.py` (النموذج = الترحيلة) أخضر؛ وعدد صفوف `users` قبل = بعد على قاعدة التطوير (قياس رخيص ولو شملته الرخصة)؛ واختبارات القيد: رقم بنوعين يُقبل، ورقم بنوع مكرَّر يُرفض، وبريد مُثبَت كذلك.
4. **الدخول والتسجيل والاستعادة بالمفتاح المركّب** (المواضع 4–7 و12–14): **القياس**: `app = None` يدخل حساب `taxo` كما اليوم؛ حساب `taxo` لا يُدخَل بإعلان السوق (خطأ اعتماد عامّ لا "هذا حساب راكب")؛ تسجيل `market` برقم له `taxo` يُقبل؛ و`test_auth.py` أخضر.
5. **مفاتيح الرمز الثلاثة** (الموضع 8) — **إغلاق الثغرة**: **القياس**: اختبار الثغرة يُكتب قبل الإصلاح فيحمرّ ثم يخضرّ؛ والحدود تبقى على الرقم (اختبار: طلبات النوعين تُعدّ في سقف واحد).
6. **التجميد صفة محفظة**: يُنقل من `users.wallet_frozen` إلى المحفظة (`owner_type`، ومعه `merchant_id` حين يأتي التاجر)، و`require_not_frozen` يأخذ المحفظة المعنيّة في مواضعه العشرة، وبابا اللوحة `freeze/unfreeze` يأخذانها. **هنا تمسّ الخطوة جدولاً مالياً؟** لا — التجميد ليس قيداً في الدفتر؛ لكنها **تمسّ عشرة مسارات مال**، فتُعرض على المالك قبل الإيداع (المطلقة الثانية في CLAUDE.md، "وأيُّ شكٍّ في أثر تغييرٍ على مالٍ قائم: يُوقَف ويُسأل"). **القياس**: اختبار لكل موضع من العشرة أن تجميد محفظة لا يمنع غيرها؛ واختبارات التجميد القائمة خضراء.

   **وتصحيحُ قياسٍ ٢٠٢٦-٠٩-٢٠ — كُتب هنا خطأً فيُصحَّح**: قيل إنها **ستّةُ ملفّاتٍ تجمّد عبر `users.wallet_frozen` مباشرةً**، **والقياسُ يقول غيرَ ذلك في الاثنين**: هي **سبعة** (`test_admin_riders` · `test_card_payments` · `test_cliq_topups` · `test_payments` · `test_wallet` · `test_wallet_admin` · `test_wallet_declared` — والسابعُ وُلد مع 1-أ/2 بعد كتابة هذا السطر)، **ولا واحدٌ منها يكتب العمود مباشرةً**: `grep` على `wallet_frozen` في `tests/` يعطي **خمسة أسطر، كلُّها توقُّعُ نصِّ خطأٍ أو حقلِ أرشيف، وصفرُ إسناد**. وكلُّها تجمّد **من باب اللوحة** `POST /admin/wallets/{id}/freeze`. **وأثرُ التصحيح على العمل**: ما يتغيّر فيها ليس سطرَ كتابةٍ يُستبدل، بل **إعلانُ المحفظة في النداء وتوقُّعُ أن الأخرى ما زالت تعمل** — وهو تعديلٌ أوسع، لأن كلَّ ملفٍّ منها يقيس مساراً ماليّاً كاملاً لا صفّاً في جدول.
   - **وأثرها على الصفوف القائمة**: من كان `wallet_frozen = true` يصير مجمَّد **كل** محافظه (لا يُخمَّن أيّها قُصد) — يُكتب في الترحيلة.
7. **رموز الأجهزة وصندوق الإشعارات**: **لا يلزم للزبون بعد التوقيع** — `device_tokens` فريدٌ على `(user_id, device_id)` و`token` (`models/device.py:38-39`)، و`device_id` مفتاح محلّي لكل تطبيق (`taxo.driver.device_id` / `taxo.device_id`)، و`user_notifications` بـ`user_id` — فحساب `market` صفوفه غير صفوف `taxo` تلقائياً. **ويبقى قائماً بين الراكب والكبتن** (حساب واحد بتطبيقين، بلا عمود تطبيق على الرمز): إشعار الكبتن يصل تطبيق الراكب على الجهاز نفسه. **وهو عطب قائم لا يخصّ التوصيل** — §D11-Q41: يُبنى في 1-أ أم يُكتب بنداً مستقلاً.
8. **الختام**: المجموعة كاملة و`guards.sh` خضراء؛ ثم الرفع بالبوّابات الخمس (`scripts/deploy.sh`)؛ ثم على هاتف المالك: دخول الراكب والكبتن بالحسابات القائمة، وطلب رمز واستعادة.

#### ما نُفِّذ من الخطة على شجرة WSL — وما قرّرتُه فيها (2026-09-19)

- **الخطوة 3** (`4f80e3c`): الترحيلة `0076` كما قِيست (§D9.1 أعلاه، والقياسُ في رسالة الإيداع).
- **الخطوة 4**: `app_scope.account_kind_for` خريطةٌ كاملةٌ على `ClientApp` و`None ⇒ taxo`؛ و`create_account` والدخولُ والاستعادةُ ومستقبِلُ التحويل والسكربتاتُ الثلاثة بالرقم والنوع؛ و`PasswordResetRequest` يقبل `app` اختيارياً؛ وسقفُ الدخول `login:phone:{kind}:{phone}` (Q42). **والجوابُ لحسابٍ غير موجودٍ من النوع المعلَن هو جوابُ الكلمة الخاطئة نفسُه** — فلا يُكشف حسابٌ آخر بالرقم.
- **الخطوة 5**: الرمزُ يُحفظ ويُتحقّق منه بالرقم والنوع في `otp.issue/verify`، وكلُّ مستدعٍ يمرّر النوع (`verification.challenge/verify/challenge_email/verify_email`، والأبوابُ السبعة في `routers/auth.py`، و`ChallengeRequest`/`EmailChallengeRequest` يقبلان `app`). **وقرارٌ من جنس الخطة**: النوعُ **لاحقةٌ للأنواع غير `taxo`** (`otp:code:{phone}:market`) و`taxo` بلا لاحقة — فمفتاحُ كلِّ حسابٍ قائمٍ هو هو حرفاً، **فلا يسقط رمزٌ في الطريق ساعةَ الرفع، ولا يُعدَّل مساعدٌ في الاختبارات** (`tests/helpers.py:761,975` تقرأ `COOLDOWN_KEY` بالرقم). **ووقع أثناءها ما يُكتب**: نداءُ قناة الرسائل في `verification.py` كان على سطرٍ واحد ففاتت عليه المطابقةُ الأولى — ولو بقي لبقيت رموزُ الرسائل كلُّها على مفتاح `taxo` وبقيت الثغرةُ مفتوحةً في القناة الأشيع؛ أمسكه عدُّ النداءات قبل الحفظ، والتصحيحُ يؤكّد أن كلَّ `otp.issue` يحمل النوع.
- **الخطوة 6 — مُنفَّذةٌ ومقيسة** (٢٠٢٦-٠٩-٢٠، بعد إقرار المالك للخطة):
  - **الشكل: `wallet_freezes`، صفٌّ للمجمَّدة وحدَها** — **ولا جدولَ محافظ في
    النظام أصلاً** (المحفظةُ مشتقّةٌ من الدفتر، ولا عمودَ رصيدٍ في أيِّ مكان)،
    فجدولُ محافظَ يُنشأ للتجميد **يخترع مصدرَ حقيقةٍ ثانياً يجب أن يوافق
    الدفترَ أبداً**. **ووجودُ الصفِّ هو التجميد**، ورفعُه حذفُه، والتاريخُ في
    `admin_audit_logs` كما كان. **ويتّسع بعمودٍ واحد** حين يأتي `merchant_id`
    (Q38): القيدُ الفريد `(user_id, owner_type)` ⇐ `(…, merchant_id)`.
  - **المواضعُ العشرة**، كلٌّ بمحفظته المسمّاة: `payments:421` و`tips:133`
    و`wallet.transfer:407` (المرسِل) و`wallet:409` (المستلِم) ⇒ `RIDER`؛
    و`subscriptions:476` و`withdrawals:206` ⇒ `DRIVER`؛ و`topups:178`
    و`card_payments:355` و`cliq_topups:114` ⇒ **المُعلَنة**؛ و`topups:226` ⇒
    **محفظةُ الطلب المختومةُ عليه**. **والموضعُ العاشر كان يقرأ العمودَ
    مباشرةً** لا من خلال الحارس — **بابان للفحص أحدُهما يُنسى**، فصارا باباً.
  - **وثلاثةٌ تغيّر ترتيبُ أخطائها** (`topups` و`card_payments` و`cliq_topups`):
    الفحصُ كان **قبل** `owner_type_for` فصار **بعده** — إذ لا يُسأل عن تجميد
    محفظةٍ قبل أن تُعرف أيُّها. **فحاملُ الدورين بلا إعلانٍ يرى الآن
    `wallet_owner_undecided` حيث كان يرى `wallet_frozen`**، وصاحبُ الدور
    الواحد لا يتغيّر عنده حرف.
  - **و`require_not_frozen` بقيت متزامنة**: الصفوفُ تأتي مع الحساب
    (`lazy="selectin"` على غرار `role_grants`) — **صفرُ استعلامٍ إضافيٍّ في أيِّ
    مسار مال**، **ودالّةُ فحصٍ يُنسى `await`ها تمرّ صامتة**. **وغيرُ المحمَّلة
    تصيح**: حسابٌ جاء من القاعدة بلا صفوفه لا يُقرأ «غيرَ مجمَّد».
  - **والترحيلة `0077` مقيسةٌ بدورةٍ كاملة**: صفُّ تجميدٍ لمحفظة راكبٍ على
    حسابٍ بدورين ⇒ `downgrade` ⇒ `wallet_frozen = true` على الحساب ⇒ `upgrade`
    ⇒ **صفّان: `rider` و`driver`** — فمن جُمِّد يبقى مجمَّداً على كلِّ محافظه.
    **والمجمَّدون صفرٌ في القاعدتين** يومَ نُفِّذت: التطوير **0 من 43**،
    والإنتاج **0 من 10** (استعلامُ قراءةٍ بإذن المالك ٢٠٢٦-٠٩-٢٠). فالترحيلةُ
    كتبت صفرَ صفٍّ في الاثنين، **والقاعدةُ لمن يأتي بعدُ**.
  - **والحُمرةُ مقيسةٌ بوجهين** (`tests/test_wallet_freeze_per_wallet.py`،
    16 اختباراً): شطبُ `require_not_frozen` ⇒ **10 حمراء**؛ وإرجاعُ `is_frozen`
    إلى «أمجمَّدٌ الحسابُ؟» ⇒ **11 حمراء**. **واتجاهٌ واحدٌ لا يكفي**: «تُمنع»
    تخضرّ بتجميدٍ يعمّ الحساب (وهو العطب)، و«تعمل» تخضرّ بحارسٍ مشطوب.
  - **واللوحةُ في الدفعة نفسِها**: `freezeWallet`/`unfreezeWallet` تُعلنان
    المحفظة، ودرجُ الراكب يجمّد **محفظةَ الراكب**. **ولمحفظة الكبتن زرُّها في
    درجه** — إذ كان زرُّ الراكب يجمّد الحساب كلَّه فيقع على الكبتن ضمناً،
    **فلو بقي وحدَه لَما بقي في اللوحة طريقٌ إلى محفظة الكبتن**: بابٌ بلا زرّ،
    ومحفظةٌ مشبوهةٌ لا يملك مشرفُ المال إيقافَها. و`check:doors` و`check:contract`
    وبناءُ الأنواع خضر.
  - **والمجموعةُ الكاملة بعده**: 1471 ناجحاً، صفرُ فاشل (1:21:56)، بلا إعادةِ تشغيلٍ واحدة.
- **الخطوة 7**: **لا شيءَ يُبنى** — بعد §D1 #4 رموزُ الأجهزة وصندوقُ الإشعارات للزبون منفصلةٌ بـ`user_id` بالبناء، وQ41 (الراكب↔الكبتن) أُخذ بافتراضه المكتوب: «لا يعطّل 1-أ» ⇒ بندٌ مستقلّ.

#### ما قد يكسر دخول حساب تجريبي قائم على هاتف المالك — وكيف يُمنع أو يُستعاد

| الخطر | لماذا | المنع | الاستعادة |
|---|---|---|---|
| حزمة مثبّتة لا تعلن تطبيقها | `app` اختياريّ اليوم | `None ⇒ taxo` (البنية أعلاه) واختبار له | — |
| رمز صدر قبل الرفع بمفتاح قديم | مفتاح الرمز يتغيّر | عمر الرمز قصير (`CODE_TTL_SECONDS`) | يُطلب رمز جديد |
| خطأ في خريطة `ClientApp ⇒ kind` يرسل الراكب إلى `market` | بحثٌ بنوع خاطئ لا يجد الحساب | اختبار لكل تطبيق قائم | `downgrade` (صالح ما دام لا حساب `market`) أو إصلاح وإعادة رفع |
| الجلسات القائمة | معلّقة بـ`user_id` (`token_service.py:21`) — لا تتغيّر | — | — |
| الترحيلة تسقط في منتصفها | DDL داخل معاملة واحدة في postgres | المعاملة تُرجع كلّها | النسخة المحقَّقة قبل الرفع (البوّابة الثالثة) |

**ولا خطوة في الخطة تكسر ما يعمل اليوم بلا مخرج** — بشرطين مكتوبين: أن يُجاب Q40 قبل الترحيلة (وإلا احتاجت قيمة التاجر ترحيلة ثانية، وهو مخرج لا كسر)، وأن يُعرض تغيير التجميد (الخطوة 6) على المالك قبل إيداعه. **وحدٌّ للرجوع يُقال صراحةً**: بعد أول حساب `market` برقم له حساب `taxo`، **`downgrade` الترحيلة يسقط** (القيد الفريد القديم لا يُعاد على رقم مكرَّر) — فالرجوع بعدها إصلاحٌ إلى الأمام لا ترحيلة عكسية.

#### الاختبارات

- **جديدة — نحو 35–45**:
  - القيود: 4؛
  - الدخول بالنوع و`app = None`: 6؛
  - عدم الكشف في الرسائل: 4؛
  - ثغرة الرمز والحدود المشتركة: 5؛
  - `card_payments`: 2؛
  - `owner_type_for` والنداءات الخمسة: 6؛
  - التجميد لكل محفظة في مواضعه العشرة: 10؛
  - التبديل لا يعبر بين نوعين: 1؛
  - دورة الترحيلة: 1.
- **قائمة تحتاج تعديلاً، ولماذا**:
  - ملفات التجميد — **سبعةٌ لا ستّة، ولا واحدٌ منها يكتب العمود مباشرةً** (تصحيحُ قياسٍ ٢٠٢٦-٠٩-٢٠، انظر الخطوة 6): كلُّها تجمّد **عبر باب اللوحة** `POST /admin/wallets/{id}/freeze`، فما يتغيّر فيها إعلانُ المحفظة في النداء وتوقُّعُ الأثر على محفظةٍ دون أختها — لا سطرُ كتابةٍ على `users`؛
  - `test_auth.py`: حالة `phone_already_registered` تبقى صحيحة **للنوع نفسه**، ويُضاف بجانبها أن النوع الآخر يُقبل — تعديلٌ بالإضافة لا تغيير توقّع؛
  - `test_user_roles.py`: إن وسّعت الخطوة 2 حالات `wallet_owner_undecided`.
- **قائمة لا تحتاج تعديلاً مع أنها تمسّ الرقم**: 19 بحثاً `where(User.phone == …)` في 11+ ملف اختبار — تنشئ حساباً واحداً لكل رقم، فيعيد البحث صفّاً واحداً كما اليوم ما دام الاختبار لا ينشئ نوعين بالرقم نفسه.

---

## §D13 مقتبسات من تطبيقات مشابهة

**السوق المستهدف بالإطلاق: الأردن (§D0.9)** — سوق ناضج فيه منافس مهيمن (طلبات) ومنافسون آخرون، فالزبون الأردني لن يجرّب تطبيقاً ناقصاً ولا يحتمل تجربة أدنى مما اعتاد. وليبيا (بريستو وأشباهها) سوق الخبرة لا سوق الإطلاق.

القاعدة في الاقتباس: يُؤخذ **السيناريو** لا الشكل، ويُفرز بمعيارين معاً — (١) هل غيابه يجعل التطبيق يبدو ناقصاً للزبون الأردني؟ (٢) هل يخدم الفارق الذي نبيعه (§D0.7 و§D1.9)؟ وما لا يجتاز الاثنين يؤجَّل مكتوباً لا يُنسى.

**الفارق المعلَن في الأردن** (يُكتب في التسويق وفي التطبيقات نفسها): الكبتن باشتراك واحد يعمل على الركاب والتوصيل بلا عمولة على أيٍّ منهما · والتاجر يدخل مجاناً بلا اشتراك وبعمولة أدنى من السوق · والزبون يدفع رسوم خدمة رمزية أو صفراً. أي أن المنافسة أوّلها على **الجانب العرضي** (كباتن وتجّار)، وهو الجانب الذي يملكه TAXO سلفاً بآلاف الكباتن.

### §D13.1 ما يدخل الإصدار الأول (مبنيّ في §D1–§D9 أو يُضاف إليها)

| # | السيناريو | من أين | القرار وموضعه |
|---|---|---|---|
| 1 | **متاجر تملكها المنصّة إلى جانب متاجر الشركاء** | بريستو تطلب "من مطاعمنا ومخازننا" | مبنيّ: `owned_by_taxo` في §D2 و§D11-Q9 — يثبّت أن فكرتك مجرَّبة في السوق نفسه |
| 2 | **محفظة + دفع نقدي + دفع إلكتروني في شاشة واحدة** | بريستو | مبنيّ في §D1.1 و§D6 |
| 3 | **تتبّع حيّ للكبتن ومراحل معلَنة** | الجميع | مبنيّ في §D3 و§D4 |
| 4 | **تغيير العنوان لحظة الطلب** (لا العنوان المحفوظ وحده) | بريستو | يُضاف إلى §D1.4: شاشة الطلب تسمح بعنوان جديد أو تعديل الموضع على الخريطة قبل الإرسال، والمحفوظ اختصار لا قيد |
| 5 | **فلترة وفرز المتاجر** (الأقرب · الأسرع · المفتوح الآن · بحث بالاسم) | بريستو 7.15 | يُضاف إلى §D1.8 مع شريط الأقسام، والفرز على الخادم |
| 6 | **بلاغ على الطلب بصور** (نقص · تلف · صنف خاطئ) | بريستو — وأشهر شكاواها أن البلاغ يُغلق بلا ردّ | يُبنى في §D5 و§D7: البلاغ خلال 24 ساعة بصور، وإغلاقه **يشترط سبباً مكتوباً يراه الزبون** بحكم قاعدة الأخطاء في المشروع؛ والقرار ثلاثة أزرار (ردّ كامل · ردّ جزئي · رفض بسبب) |
| 7 | **الوقت المتوقّع للوصول** معروضاً للزبون | الجميع | يُشتقّ من `expected_ready_at` + زمن المسار من Mapbox، ويُعرض مدىً (٢٥–٣٥ دقيقة) لا رقماً واحداً |
| 8 | **إعادة آخر طلب بنقرة** و**المفضّلة** | طلبات · جاهز | يُضاف إلى §D1.8: زرّ "اطلبه مرة أخرى" على آخر طلب، وقلب على التاجر — كلاهما بلا جدول جديد (الطلبات موجودة، والمفضّلة جدول ربط صغير) |
| 9 | **تقييم بعلامات جاهزة** لا نجوم عارية (سريع · ساخن · مغلَّف جيداً · كبتن مهذّب) | جاهز · كريم | يُضاف إلى `delivery_order_ratings`: عمود `tags` (نصوص من قائمة مغلقة تحت check:enums) |
| 10 | **إشعار للتاجر لا يُهمَل** (صوت متكرّر حتى الفتح) | الجميع، وهو أكثر ما يُشتكى منه | مبنيّ في §D3 |
| 11 | ~~**الإطلاق مدينةً مدينة**~~ | بريستو | **سقط إلى المؤجَّل** (قرار المالك 2026-09-19، §D10): لا مفهوم مدينة في النموذج (لا جدول ولا عمود مدينة في أي نموذج بالشجرة)، والتغطية محكومة بنصف قطر الفرع والتوزيع ووجود تاجر. والمفتاح يبقى **لكل دولة** كما في §24 من SPEC.md |
| 12 | **عروض إطلاق: توصيل مجاني أياماً + كاش باك** | بريستو | لا محرّك عروض الآن (§D10)، لكن `delivery_base_fee = delivery_per_km = delivery_min_fee = 0` و`service_fee_* = 0` **لدولة** كبسة زرّ في صفّ `delivery_settings` |
| 13 | **عرض الرسوم كلها قبل الدفع** (أصناف · توصيل · رسوم خدمة) بلا مفاجأة في الشاشة الأخيرة | طلبات وأشباهها، وأكثر ما يُشتكى منه في الأسواق الناضجة | مبنيّ في §D1.9؛ ورسوم الخدمة بند باسمه لا مضموم |
| 14 | **حدّ أدنى للطلب لكل تاجر** | الجميع | عمود `min_order_amount` على التاجر (افتراضه 0) — بلا هذا يرفض التاجر طلباتٍ يدوياً فتظهر إلغاءاته |

**فرزٌ للأردن بالذات**: ما يجعل التطبيق يبدو معتاداً هناك هو #3 و#7 و#13 و#6 (التتبّع، والوقت المتوقّع، ووضوح الرسوم، والبلاغ المسموع). وما يجعله يُختار هو §D1.9 وحده: أسعار أدنى لأن كلفة الجانب العرضي عندنا أدنى.

### §D13.2 مؤجَّل بقصد (مع علّته)

| السيناريو | من أين | لماذا يؤجَّل |
|---|---|---|
| تعديل الطلب بعد إرساله (إضافة/حذف صنف) | بريستو | يمسّ المال بعد تجميده: كل تعديل يعيد حساب العمولة والصافي ويغيّر ما يدفعه الكبتن للمطعم. البديل الآن: الإلغاء بيد المطعم |
| دردشة مع خدمة العملاء داخل التطبيق | بريستو 7.16 | الدردشة مؤجَّلة أصلاً في TAXO؛ والبلاغ بصور (#6) يغطّي الحاجة الأكثر |
| جدولة الطلب لوقت لاحق | طلبات · هنقرستيشن | يحتاج حجز كبتن مسبقاً وطابوراً زمنياً — بند مستقل |
| اشتراك للزبون (توصيل مجاني شهري) | talabat pro | يُبنى بعد أن يستقرّ حجم الطلبات، وإلا سعّرتَ ما لا تعرف كلفته |
| المفضّلة (قلب على التاجر) | الجميع | بند صغير لكنه ليس من الأربعة التي تُشترى بها التجربة؛ يلحق بأول تحديث بعد الإطلاق |
| **"اطلب أي شيء"** — الزبون يكتب طلبه نصاً والكبتن يشتريه | مرسول | أقوى فكرة في القائمة وأخطرها: تحلّ مشكلة "لا مطاعم مسجّلة بعد" يوم الإطلاق، لكنها تقلب نموذج المال (لا سعر معروف مسبقاً، والكبتن يدفع من جيبه بلا سقف). لها ملف مستقل إن أردتها |
| إكرامية للكبتن | كريم · الجميع | **مُثبَت: لا يُعاد استعماله بلا كود** — `tips.ride_id` إلزاميّ وفريد (`models/tip.py:45`)، فالبقشيش مربوط بالرحلة. يبقى بنداً مستقلاً (§D10) |
| رسوم خدمة على الزبون فوق التوصيل | الجميع | مصدر دخلك من التاجر بقرارك؛ وإضافتها لاحقاً إعداد واحد |

### §D13.3 ما لا يُقتبس عمداً

- **اسم مميَّز للكبتن** (PrestoMan وأشباهه): كبتنك واحد في الرحلات والتوصيل، وتسميته باسم ثانٍ تشقّ هويةً بُنيت سنة.
- **مستودعات المنصّة بمخزون حقيقي**: متجرك الغذائي تاجر في النموذج (§D1.5)، ولا يُبنى له جرد ولا شراء ولا مخزون (§D10).
- **رسوم مضاعفة وقت الذروة**: تُكسب بها دنانير وتُخسر بها الثقة في سوق يقارن بالسعر — وإن أُريدت فهي إعداد على رسوم التوصيل لا محرّك جديد.

## §D14 مقتبسات من التطبيقات العالمية

مصدر المسح: DoorDash · Uber Eats · Deliveroo · Wolt · Glovo · Rappi · Grab · Swiggy · Zomato. القاعدة: لا يُنقل شكلٌ، بل يُؤخذ السيناريو ويُحوَّر على ما يملكه TAXO ولا يملكه غيره — **أسطول كباتن قائم يعمل على الركاب والتوصيل بالاشتراك نفسه، ونظام مستويات ومهام وإحالة مبنيّ** — أمّا بوابة واتساب القائمة فـ**ترسل رمز التحقق وحده** (§D14.أ-7). ما يلي مفروز بثلاث طبقات، والطبقة (ب) هي ما لا يستطيع منافس في الأردن تقليده بسرعة.

### §D14.أ يدخل الإصدار الأول — رخيص وأثره كبير

| # | السيناريو | الأصل | التحوير لـTAXO |
|---|---|---|---|
| 1 | **الاستلام الذاتي** (اطلب وادفع واستلم من المتجر بلا رسوم توصيل) | DoorDash · Uber Eats · Zomato | `fulfilment = delivery \| pickup` على الطلب: لا كبتن ولا رسوم توصيل، والرمز نفسه يُستعمل للاستلام. يوسّع السوق بلا كلفة لوجستية، ويجعل التطبيق نافعاً في الأحياء التي لا كبتن فيها بعد |
| 2 | **"اتركه عند الباب" وصورة إثبات التسليم** | DoorDash · Uber Eats | خيار للزبون عند الطلب؛ وعندها التسليم بصورة إلزامية بدل رمز التسليم — ويُقفل على طلبات الكاش (لا تُترك على الباب طلبات تُقبض نقداً) |
| 3 | **زرّ "نفد الصنف" بنقرة** يوقف الصنف فوراً ويعيده تلقائياً أول اليوم التالي | Uber Eats · Deliveroo | أرخص ميزة في القائمة وأكثرها أثراً على الإلغاءات: التاجر لا يلغي طلباً لأنه لم يجد زرّاً |
| 4 | **قائمة موقوتة** (فطور/غداء/عشاء/ويكند) — نافذة توفّر لكل صنف أو قسم | Uber Eats · Swiggy | حقلان على الصنف (`available_from/to`) و"يوم الدولة" بمنطقة وقتها؛ بلا هذا يظهر الفطور ليلاً فيُلغى الطلب |
| 5 | **إشعار حيّ مستمر بمرحلة الطلب** على شاشة القفل | Live Activity (iOS) · Ongoing Notification (Android) | يرفع الإحساس بالجودة بلا كلفة تُذكر على أندرويد، والمراحل عندنا معلَنة سلفاً (§D3) |
| 6 | **تجميع طلبين لكبتن واحد من الفرع نفسه** | batching في الجميع | `max_concurrent_orders = 2` بشرطين: الفرع واحد، والوجهتان ضمن مسافة قصيرة؛ يرفع دخل الكبتن/الساعة دون أن يبرد الطعام |
| 7 | ~~**تقرير التاجر على واتساب** كل مساء~~ | dashboards التجار عالمياً | **انتقل إلى المؤجَّل** (قرار المالك 2026-09-19، §D10). العلّة من الشجرة: البوابة **لا تقبل نصّاً بقصد مكتوب** — `whatsapp-gateway/src/index.js`: "`POST /send` يأخذ الرمزَ ورقمَه" و"ولا بابَ يقبل نصّاً"، وقالبها قالب رمز (`otp-template-rules.json`، `required_variables: [code]`)، وواجهة الخلفية `send_code` لا `send` (`services/whatsapp/base.py`)، وقوالب Cloud API للمصادقة "لا تقبل نصّاً حرّاً" (SPEC §19). **وبديله في الإصدار الأول**: شاشة تقارير في TAXO MERCHANT (طلبات اليوم، المبيعات، العمولة، ما فاته ولماذا — بيوم الدولة، ومن تجميع الخلفية) وإشعار FCM مسائي يفتحها |
| 8 | **الإحالة للتجّار** (تاجر يحيل تاجراً فيُمدَّد إعفاؤه) | referral في الجميع | **ليس توصيلاً فحسب**: الإحالة القائمة (`referrals` · `referral_settings` · `services/referrals.py`) مكافأتها **مال** (`reward_amount` بقيد `referral_bonus`) بعد `required_rides` رحلة، و`referral_type` نصّ يُختم من التطبيق. "تمديد `free_until`" **نوع مكافأة جديد** وشرط تأهيل جديد (طلبات لا رحلات) — يُبنى، ولا يدخل الإصدار الأول ما لم يُقرَّر (§D11-Q27) |

### §D14.ب الطبقة المميِّزة — يملكها TAXO وحده (بعد الإطلاق مباشرة، ملف لكلٍّ)

| # | الفكرة | لماذا لا يقلّدها منافس | الكلفة |
|---|---|---|---|
| 1 | **اطلب وأنت في الرحلة** — الراكب في طريقه إلى البيت يطلب من التطبيق، ويُوقَّت الطلب ليصل مع وصوله (وجهة الرحلة معروفة وزمنها محسوب من Mapbox) | يحتاج أن تكون شركة رحلات وتوصيل في وقت واحد. طلبات لا تملك سيارات، وأوبر لا تملك حصة الأردن | متوسطة: ربط وجهة الرحلة بعنوان الطلب وتأخير الإسناد بزمن الوصول |
| 2 | **أرسل طرداً مع كبتن** (من نقطة إلى نقطة داخل المدينة، بلا متجر) | كباتنك يتنقّلون أصلاً؛ ولا يحتاج تاجراً ولا قائمة | صغيرة نسبياً: طلب بلا `merchant_id`، وسعره رسوم التوصيل وحدها، والمال لا يمرّ بالمنصّة |
| 3 | **توصيل بين المدن** مع كبتن مسافر (عمّان ← إربد) | **تصحيح من الشجرة**: `SPEC-RIDES-EXT` غير موجود في المستودع، ولا رحلات بين المدن مبنيّة (لا ذكر لها في الخلفية ولا في SPEC.md) — فهذا البند يفترض ما لم يُبنَ | متوسطة، ولا تبدأ قبل أن تُكتب الرحلات بين المدن وتُبنى |
| 4 | **نوبة ذروة يحجزها الكبتن** فتُعطى له أولوية العرض فيها | نظام المستويات والمهام مبنيّ عندك؛ وحلّ مشكلة "لا كباتن وقت الذروة" بلا دفع حوافز نقدية | متوسطة |
| 5 | **أولوية عرض بالمستوى** | — | **مبنيّ للرحلات سلفاً** (البند 53): الترتيب يطرح خصم المستوى بالأمتار (`level_settings.discount_meters`) بسقف `MAX_LEVEL_DISCOUNT_METERS = 100` — `dispatch.py:527-540`. **ويرثه الطلب بلا كلفة** إن أعادت الحلقة الثانية ترتيب `_ranked_candidates` نفسه (§D1.3)؛ فلا يُبنى هنا شيء |
| 6 | **سلة مشتركة برابط** (مكتب أو عائلة، كلٌّ يضيف أصنافه ثم يدفع واحد) | Uber Eats · Wolt — ولا أحد يقدّمها في الأردن بالعربية | متوسطة، وأثرها على متوسط قيمة الطلب كبير |

### §D14.ج مؤجَّل بعلّته

| السيناريو | الأصل | العلّة |
|---|---|---|
| تحسين المسار وتجميع الطلبات آلياً عبر فروع متعددة | DoorDash | يحتاج كثافة طلبات لا تملكها في الشهر الأول؛ وقبلها يخسر الطعام حرارته |
| مطابخ ظلّ وعلامات افتراضية | Deliveroo Editions | عملٌ عقاري لا برمجي |
| اشتراك الزبون (توصيل مجاني شهري) | DashPass · Uber One | لا تُسعِّر ما لا تعرف كلفته |
| توصيل في عشر دقائق ومخازن مصغّرة | Swiggy · Zomato · Getir | يحرق المال ويحتاج مخزوناً |
| رسوم ذروة ديناميكية | الجميع | §D13.3 — تُخسر بها الثقة في سوق يقارن بالسعر |
| إكرامية داخل التطبيق | الجميع | تلحق بعد أن يستقرّ الدفتر (§D10) |

## §D15 جهاز التاجر والطباعة الفورية (قرار موقَّع)

المالك يزوّد التجّار بجهاز يحمل TAXO MERCHANT: **طرفية كاشير أندرويد** بطابعة حرارية مدمجة (80 ملم)، بشاشتين (شاشة الموظّف وشاشة تواجه الزبون)، وNFC وماسح باركود، بنسختين — ثابتة على الكاونتر ومحمولة، **وأداؤهما واحد**، فالتطبيق واحد لهما ولا فرع في الكود بينهما. الطلب الوارد يُطبع إيصاله فوراً، وتُتابَع الأصناف والمراحل والفتح والإغلاق من الجهاز نفسه.

### §D15.0 ما في الشجرة اليوم عن الإشعار والكود الأصلي — مُثبَت (2026-09-19)

| البند | الحال |
|---|---|
| **نوع رسالة FCM** | الخلفية ترسل عبر HTTP v1 رسالة **تحمل الكتلتين معاً**: `notification` (عنوان ونصّ) **و**`data` (`services/push/fcm.py:129-152`). ولا رسالة `data` وحدها في أي مسار. و`high_priority` (أولوية `high` لأندرويد، `apns-priority: 10`) لعروض الرحلات وحدها (`services/push/base.py:46-54`) |
| **الاستقبال في التطبيقات** | **driver-app** و**admin-panel**: إضافة `@capacitor/push-notifications` 7.0.7 في `package.json` كليهما، ومعالجتها في driver-app في `driver-app/src/lib/push.ts` (`pushNotificationReceived` والتطبيق مفتوح · `pushNotificationActionPerformed` للنقر). وجدول الحالات في رأس الملف نفسه: **مفتوح ⇒ التطبيق يعالج ولا يرسم النظام شيئاً؛ في الخلفية أو مغلق ⇒ النظام يرسم سطراً في الشريط والنقر يفتح الوجهة** — أي لا يُنفَّذ كود التطبيق عند الوصول |
| **customer-app** | **بلا إضافة إشعارات أصلية**: يستعمل `firebase/messaging` الويبي (`customer-app/src/lib/firebase.ts:108-132`)، و`driver-app/src/lib/push.ts` يثبت بقياس S21 أن `Notification` و`PushManager` **غائبان في WebView أندرويد** فهذا المسار "يستحيل على الهاتف". فـ**TAXO MARKET يأخذ طريق driver-app لا طريق customer-app** |
| **خدمة رسائل أصلية** | **غير موجودة**: لا `FirebaseMessagingService` ولا `MESSAGING_EVENT` في أي بيان ولا ملف Java في التطبيقات الثلاثة |
| **كود أصلي قائم** | **موجود في driver-app وحده** (`driver-app/android/app/src/main/java/ly/tajora/driver/`): `OfferAlertPlugin` (Capacitor plugin: ورقة/فقاعة/ملء الشاشة/إشعار بأقصى أهمية لعرض الرحلة) و`OnlinePlugin` و**`OnlineService` — خدمة أمامية** (`foregroundServiceType="location"`) تبقي العملية حيّة والمقبس في الـWebView متصلاً **ما دام التطبيق لم يُزَح من قائمة المهامّ**؛ و`onTaskRemoved` يوقفها (تعليقها: "المقبس يعيش في الـWebView، وإزالة المهمّة تقتله"). customer-app وadmin-panel: `MainActivity` وحدها |

**فما يلزم للطباعة والتطبيق مغلق — مبنيّاً على ما وُجد لا على العموم:**

1. **رسالة `data` وحدها** للطلب الوارد: نوع رسالة جديد في `services/push/fcm.py` (اليوم كل رسالة تحمل `notification`، فيرسمها النظام ولا يُوقظ كود التطبيق حين يكون مغلقاً) — بأولوية `high` كعروض الرحلات.
2. **`FirebaseMessagingService` أصلية في TAXO MERCHANT** تستقبل تلك الرسالة والتطبيق مغلق، وتنادي الطباعة **بلا WebView** (Java يبني الإيصال ويرسله إلى SDK الطابعة)، ثم ترسل الإقرار `printed_at` إلى الخلفية بطلب HTTP أصلي — على مثال `OfferApi.java` القائم الذي ينادي الخلفية من Java.
3. **خدمة أمامية** على مثال `OnlineService` تبقي الجهاز "مستقبِلاً" طول الدوام، **ومعها حدّها المقيس**: لا تنجو من إزاحة التطبيق — فالمسار الأول (FCM `data`) هو الضمان، والمقبس تسريع لا بديل.
4. **والإضافة الأصلية ليست سابقة**: driver-app فيه Capacitor plugins مكتوبة ومسجَّلة في `MainActivity` — فالبناء يتبع نمطاً قائماً (0.1 كانت تقول "هذا التطبيق وحده فيه كود أصلي"، وهو خطأ).
5. **والفحص #1 في §D15.2 (GMS) شرط لكل ما سبق**: بلا خدمات قوقل لا FCM أصلاً، ويصير المقبس في خدمة أمامية الطريق الوحيد.

### §D15.1 ما يغيّره هذا في البنية

TAXO MERCHANT كان سيكون تطبيق ويب في غلاف Capacitor مثل التطبيقات الثلاثة القائمة. الجهاز يكسر ذلك في ثلاث نقاط:

1. **الطباعة**: الويب لا يطبع على طابعة حرارية — تلزم إضافة أصلية (Capacitor plugin) تنادي SDK المصنّع، أو ESC/POS إن أتاحه الجهاز، **وخدمة رسائل أصلية تطبع والتطبيق مغلق** (§D15.0). وهو كود أصلي يُبنى ويُوقَّع ويُختبر على الجهاز لا في المتصفح — على النمط القائم في driver-app.
2. **الاتجاه والمقاس**: شاشة أفقية عريضة على كاونتر، لا شاشة هاتف رأسية. الواجهة تُصمَّم أفقيةً أولاً (قائمة الطلبات يساراً وتفصيل الطلب يميناً في رؤية واحدة)، وتبقى عاملةً على هاتف عادي.
3. **التشغيل الدائم**: الجهاز موصول بالكهرباء ومفتوح طول الدوام، فالخطر ليس البطارية بل النوم والشاشة والسقوط الصامت عن الشبكة.

### §D15.2 خمسة تُفحص على جهاز واحد قبل الشراء بالجملة

كلٌّ منها يُبطل الخطة كلّها إن جاء سالباً، ولا يُعرف من كتالوج البائع:

| # | الفحص | إن جاء سالباً |
|---|---|---|
| 1 | **خدمات Google (GMS) موجودة؟** كثير من طرفيات الكاشير الصينية تُشحن بلا خدمات قوقل — فلا FCM ولا إشعار، والطلب لا يصل أصلاً | يلزم طريق ثانٍ للوصول: اتصال دائم (WebSocket) مع خدمة أمامية، وهو عمل إضافي كامل |
| 2 | **SDK الطابعة**: يعطيك البائع مكتبة وتطبيقاً تجريبياً؟ ويطبع العربية RTL بخطّ مقروء؟ | العربية على الطابعات الحرارية تُطبع صورةً لا نصّاً (نرسم الإيصال bitmap) — عمل إضافي مقيس، يُقرَّر قبل الشراء |
| 3 | **الإنترنت**: شريحة 4G أم واي-فاي فقط؟ | واي-فاي فقط يعني أن انقطاع النت في المطعم = طلبات لا تصل. الشريحة تستحق فرق السعر |
| 4 | **الطباعة والتطبيق مغلق أو الشاشة مطفأة** | يلزم ما في §D15.0: رسالة `data` وحدها (نوع جديد — اليوم كل رسالة تحمل `notification`) وخدمة رسائل أصلية وخدمة أمامية — تُقاس على الجهاز لا تُفترض |
| 5 | **نسخة الأندرويد** وتوافقها مع Capacitor والويب-فيو | جهاز بأندرويد قديم يسقط من القائمة مهما رخص |

**قاعدة**: لا تُشترى دفعة أجهزة قبل أن يُطبع إيصال عربي حقيقي من التطبيق على جهاز واحد، ويصل طلبٌ والشاشة مطفأة.

### §D15.3 قاعدة الطباعة: نتيجةٌ لا إثبات

الخادم لا يعدّ الطلب واصلاً لأنه أرسل إشعاراً، بل حين يقرّ الجهاز بالطباعة (`printed_at` على الطلب). وطلبٌ بلا إقرار يُعاد إرساله ويُنبَّه به المشرف، وتبقى الشاشة بصوتها المتكرّر الطريق الثاني دائماً. بغير هذه القاعدة تصمت الطابعة بلا أن يفشل شيء ظاهر — وهو الشكل الثاني عشر في ثوب جديد.

### §D15.4 ما يُبنى في المرحلة 3

- إضافة أصلية واحدة بواجهة واحدة `print(receipt)`، خلفها مزوّدان: SDK الجهاز، وESC/POS عبر بلوتوث لطابعة خارجية — يُختار من إعداد على الجهاز لا من الكود. **وقالب الإيصال يُبنى في Java** لا في الويب، لأن الطباعة والتطبيق مغلق لا WebView فيها (§D15.0)؛ والتطبيق المفتوح ينادي الإضافة نفسها فلا يكون للإيصال شكلان.
- `FirebaseMessagingService` ونوع رسالة `data` في الخلفية، وخدمة أمامية على مثال `OnlineService` (§D15.0).
- قالب إيصال واحد (عربي RTL بأرقام لاتينية، 80 ملم، ويدعم 58): رقم الطلب · الوقت · الأصناف بخياراتها وكمياتها · المجموع · **المستحق نقداً من الكبتن** · طريقة الدفع · اسم الزبون وآخر أربعة من رقمه وعنوانه المختصر.
- زرّ "إعادة طباعة" على كل طلب (الورق ينحشر والإيصال يضيع).
- شاشة "حالة الجهاز": الطابعة؟ الورق؟ الإشعارات مسموحة؟ الشبكة؟ آخر طباعة ناجحة متى؟ — تُقرأ من الجهاز لا من الإعدادات.
- `printed_at` و`print_attempts` على الطلب، وإعادة إرسال آلية عند غياب الإقرار.
- واجهة أفقية أولاً، والتطبيق يعمل كاملاً بلا طابعة على هاتف عادي (الطباعة ميزة جهاز لا شرط استعمال).
- **لا يُستعمل في الإصدار الأول**: الشاشة الثانية، وNFC، وماسح الباركود — موجودة في العتاد ولا نبني لها شيئاً (§22.0).

### §D15.5 الأجهزة يجهّزها TAXO لكل متجر متعاقد

الجهاز يصل التاجرَ **جاهزاً للعمل**، لا صندوقاً يُنصِّبه بنفسه. وهذا يغيّر ثلاثة أشياء في البناء:

- **طراز واحد مقياس**: ما دام الشراء بيدك فالأسطول كلّه طراز واحد اجتاز فحوص §D15.2 — فالإضافة الأصلية تُبنى على SDK واحد، ويُختبر التطبيق على جهاز واحد يمثّل الكلّ. تعدّد الطُرُز يضاعف العمل بلا مقابل.
- **دخول بلا كلمة مرور يكتبها التاجر**: الجهاز يُربط في اللوحة قبل تسليمه (رمز تجهيز لمرّة واحدة يمسحه المشرف أو يُدخله)، فيفتح على حساب الفرع مباشرة. لا يُسلَّم جهاز فيه اعتماد مكتوب على ورقة.
- **الجهاز مُلكك لا مُلك التاجر**: فله سجلّ وحال وإبطال عن بُعد.

جدول `merchant_devices`: id · serial · model · merchant_id(null) · branch_id(null) · status(in_stock/assigned/returned/lost/revoked) · assigned_at · last_seen_at · app_version · android_version · printer_ok(bool) · notes — **وشروط التعاقد على الجهاز**: `terms`(gift / deposit / rent / commission_deduction) · `deposit_amount` · `monthly_fee` · `min_term_months` · `terms_note`.

**الشروط تُختار لكل تاجر عند التجهيز لا مرّة واحدة للجميع** (قرار موقَّع): العرض يختلف باختلاف الفترة والموقع وحجم المتجر — هدية لتاجر تريده، وتأمين مسترجَع لآخر، وإيجار رمزي لثالث. الحقل يسجّل ما اتُّفق عليه، ويظهر في بطاقة التاجر وفي كشفه.

**حدّ الإصدار الأول**: الحقول **تسجّل الشرط ولا تنفّذه** — لا خصم آلي لإيجار ولا استقطاع تأمين. أي مال يتحرّك بسببها يُسجَّل يدوياً بقيد `adjustment` على محفظة التاجر عبر الباب القائم `POST /admin/wallets/{user_id}/adjustments` (بإعلان `wallet = merchant` حين يتّسع التعداد) — والمدين منه يخضع لحدّ Q35. الأتمتة بند مستقل يُقرَّر حين يتبيّن أي الصيغ غلبت عملياً؛ وبناؤها الآن بناءٌ لأربع صيغ قد تُستعمل واحدة منها. وشاشة في اللوحة: مخزون الأجهزة، الإسناد إلى فرع، الإبطال الفوري (يُسقط جلسة الجهاز فلا يقرأ طلباً بعدها)، وقائمة "أجهزة لم تُرَ منذ 24 ساعة" — فجهازٌ صامت يعني متجراً لا تصله طلبات وزبائن ينتظرون.

**الوضع المقيَّد (kiosk)**: الجهاز يفتح على التطبيق ولا يُستعمل لغيره — يُضبط عند التجهيز بإعدادات أندرويد لا بكود في التطبيق، ويُكتب في دليل التجهيز لا في الشجرة.

**دليل تجهيز مكتوب** (خارج الكود، في design/): الخطوات بالترتيب — ضبط الشبكة، إعفاء تحسين البطارية، السماح بالإشعارات، تثبيت الحزمة، الربط بالفرع، طباعة إيصال تجريبي، تسليم بورقة استلام. عشر دقائق لكل جهاز، وتكرارها بلا قائمة يعني جهازاً يخرج ناقصاً ويظهر عطبه في أول ليلة ذروة.

### §D15.6 متجر TAXO من اللوحة

قرار المالك: شاشة في لوحة الإدارة لا حساب تاجر. وشرطه ألّا يُكتب منطق ثانٍ: شاشات اللوحة تنادي **مسارات التاجر نفسها** بمعامل `merchant_id` وبحارس دور المشرف — مصدر واحد يمرّ به البابان (الشكل الثامن). ويمتدّ هذا تلقائياً إلى أي تاجر يحتاج المشرف تعديل قائمته.

## §D16 السيناريو المرجعي — من طلب الزبون إلى الاستلام

طلب كاش كامل، وهو الأصعب لأن المال يمرّ بيد الكبتن. الأرقام مثال لا قيم مقرَّرة. هذا السيناريو هو **نصّ الاختبار** للمرحلة 2 (من الـAPI) وللجولة في المرحلة 7 (على ثلاثة أجهزة).

**اللاعبون**: سارة (زبونة، عمّان) · مطعم أكرم للشورما، فرع الصويفية (جهاز كاشير TAXO) · الكبتن أحمد (في وضع التوصيل) · اللوحة.

**المال في هذا الطلب**: الأصناف 9.500 · العمولة 8% = 0.760 · صافي المطعم 8.740 · التوصيل 1.500 · رسوم الخدمة 0.250 · **الإجمالي 11.250**.

| # | اللحظة | ما يراه الزبون | ما يراه التاجر | ما يراه الكبتن | ما يجري في الخادم |
|---|---|---|---|---|---|
| 1 | 20:31 | تفتح TAXO MARKET على المتاجر المفتوحة القريبة مرتَّبة بالمسافة، وشريط الأقسام أعلاه (الكل · TaxoEat · …) | — | — | قائمة المتاجر: `active` + مفتوح الآن بتوقيت الأردن + ضمن نصف قطر التوصيل |
| 2 | 20:32 | تدخل "أكرم للشورما": الأقسام والأصناف، والمنفَد عليه علامة | — | — | الأصناف من قائمة التاجر، والتوفّر من الفرع، والموقوت خارج نافذته لا يظهر |
| 3 | 20:34 | تضيف: شاورما دجاج كبير ×2 (+ثوم، بلا مخلل) وعصير — الخيارات بفروق أسعارها ظاهرة | — | — | التحقق من `min_select/max_select` لكل مجموعة خيارات |
| 4 | 20:35 | السلة: الأصناف 9.500 · التوصيل 1.500 · رسوم الخدمة 0.250 · **الإجمالي 11.250** — كل رقم بسطره قبل الدفع | — | — | المسافة من Mapbox (الفرع ← العنوان)، والرسوم تُحسب ولا تُخزَّن بعد |
| 5 | 20:35 | تختار العنوان (أو تعدّله على الخريطة الآن)، والدفع نقداً، وتكتب "الرنّة عطلانة، اتصل" | — | — | فحص نصف القطر، وأن سارة غير محجوبة عن الكاش |
| 6 | **20:36 — placed** | "أُرسل الطلب إلى المطعم" + الوقت المتوقّع 25–35 دقيقة | **يُطبع الإيصال فوراً** والشاشة تصيح بصوت متكرّر | — | صفّ الطلب بكل المال **مجمَّداً**: النسبة، العمولة، الصافي، التوصيل، الرسوم؛ ورمز تسليم من أربعة أرقام؛ وFCM data إلى الجهاز |
| 7 | 20:36 | — | الجهاز يقرّ بالطباعة | — | `printed_at` يُكتب. لو لم يصل الإقرار: إعادة إرسال، ثم تنبيه المشرف — والشاشة تبقى الطريق الثاني |
| 8 | **20:37 — accepted** | "المطعم استلم طلبك" | يضغط "قبول" ويحدّد 15 دقيقة تحضيراً | — | `expected_ready_at = 20:52`، ويبدأ البحث عن كبتن |
| 9 | 20:37 | — | — | **عرض**: أكرم للشورما (1.2 كم) ← سارة (2.8 كم) · التوصيل 1.500 · **نقداً: تدفع 8.740 وتقبض 11.250** · جاهز 20:52 | الحلقة الثانية (§D1.3) بشروط `_eligible_levels` نفسها: معتمَد، متصل، غير محجوب (`advance_blocked` / `cancellation_carry_blocked` / `debt_blocked`)، اشتراكه سارٍ — وفوقها: في وضع التوصيل، ودون سقف النقد؛ والأقرب أولاً مع خصم المستوى؛ والمهلة `offer_timeout_seconds` (7 ث افتراضاً) |
| 10 | 20:37 | "الكبتن أحمد في الطريق" + اسمه ورقمه | "الكبتن أحمد — يصل 20:50" | يقبل خلال ثوانٍ | قفل العرض `dispatch:driver_offer:{driver_id}` يمنع أن يصله عرض رحلة في اللحظة نفسها؛ وصفّ `delivery_assignments` يُكتب بعد الإرسال |
| 11 | 20:40 | تتبّع الكبتن على الخريطة | يضغط "بدأ التحضير" | يتجه إلى الفرع | `preparing` + حدث في خطّ الزمن |
| 12 | 20:51 | "طلبك جاهز" | "جاهز" | وصل الفرع | `ready` — ولو لم يكن هناك كبتن بعد لبدأ عدّاد التنبيه |
| 13 | **20:53 — picked_up** | "الطلب في الطريق إليك" + إشعار حيّ على شاشة القفل | الشاشة تُغلق الطلب من قائمة الجاري | ورقة تأكيد: **"دفعتُ للمطعم 8.740"** → يضغط ويؤكّد | تحذير (لا منع) إن كان بعيداً عن الفرع أكثر من 300 م. لا قيد مالي بعد — النقد خارج الدفتر حتى التسليم |
| 14 | 21:02 | يصل الكبتن؛ تدفع 11.250 وتعطيه **رمز التسليم** الظاهر في تطبيقها | — | يدخل الرمز | ثلاث محاولات خاطئة ⇒ يُقفل الإدخال، والبديل تأكيد الزبون من تطبيقه، مع تنبيه المشرف |
| 15 | **21:02 — delivered** | "تمّ التسليم" + تقييم بعلامات جاهزة (سريع · ساخن · مغلَّف جيداً) | يظهر في تقرير اليوم: الأصناف 9.500 · العمولة 0.760 · **الصافي 8.740** | أرباحه: 1.500 توصيل **بيده نقداً** (لا قيد في محفظته) · ودَينان: عمولة المتجر 0.760 ورسوم خدمة 0.250 — **"محصَّلة نقداً"، ولا كلمة "عمولتك" في أي شاشة** | `delivered` · **صفّا دَين** في `driver_debts`: `store_commission` 0.760 و`service_fee` 0.250، يُحصَّلان بـ`debts.collect_from_balance` حين يدخل محفظته مال · دخل TAXO 1.010 |

**فحص المال في نهاية الطلب** (اختبار إلزامي): بيد الكبتن 11.250 − 8.740 = 2.510، منها 1.500 له و1.010 دَين لـTAXO في صفّين. أي أن الكبتن **لم يدفع من جيبه شيئاً ولم يُخصم من دخله شيء** — وهذا برهان §D0.7 بالأرقام لا بالكلام. ولا قيد في أي محفظة في طلب الكاش.

### §D16.1 الطريق نفسه بالمحفظة (قرار المالك 2026-09-19)

يتغيّر خمسة مواضع:

1. عند `placed`: **يُخصم 11.250 كاملاً** من محفظة سارة (`customer`) بقيد `delivery_order_payment` — لا حجز ولا قبض لاحق.
2. عند الاستلام: **الكبتن لا يدفع للمطعم شيئاً**، وبطاقته تقول "لا تدفع شيئاً"، وورقته "استلمتُ" وحدها.
3. عند التسليم: لا نقد، والرمز كما هو.
4. عند `delivered`: محفظة الكبتن **+1.500** (`delivery_earning`) — **لا 8.740**؛ ومحفظة التاجر **+8.740** بقيد دائن في `wallet_transactions` يُسوّى في دورته (§D18.2)؛ وTAXO تحتفظ بـ1.010 من المخصوم.
5. **لا دَين على الكبتن** في طلب المحفظة — لم يقبض شيئاً نيابةً عن أحد.

ولو أُلغي أو رُفض أو انقضى: قيد `refund` بـ11.250 إلى محفظة سارة، ولا شيء غيره.

### §D16.2 ما يكسر الطريق وأين يُمسك

| العطب | متى | ما يحدث |
|---|---|---|
| المطعم لا يردّ | بعد `merchant_accept_timeout_sec` | `expired` · إشعار لسارة · لا مال تحرّك |
| المطعم يرفض | قبل القبول | `rejected` بسبب من قائمة · الزبون يرى السبب |
| لا كبتن يقبل | بعد `ready` بـ`ready_unassigned_alert_min` | تنبيه للمشرف، وإعادة إسناد يدوية من اللوحة |
| صنف نفد بعد القبول | أثناء التحضير | لا تعديل على الطلب (§D10) — المطعم يلغي بسبب، أو يتصل بالزبون |
| الزبون غير موجود | بعد الاستلام | `pending_review` (undeliverable) بصورة إلزامية وسبب — والأثر بخيار المشرف من §D19.1 |
| الجهاز مطفأ أو صامت | أي لحظة | "أجهزة لم تُرَ منذ 24 ساعة" في اللوحة، والطلب لا يُقبل أصلاً فيُعرض المتجر مغلقاً |

## §D17 دورة حياة الكبتن في التوصيل

الكبتن ليس لاعباً جديداً: هو كبتن TAXO نفسه، بحسابه واشتراكه ومستواه ودَينه ومحفظته القائمة. فدورته هنا **امتدادٌ لدورته في الرحلات لا دورة ثانية**، وهذا القسم يصف ما يتغيّر فقط.

### §D17.1 الحالات الست وشروط الانتقال

| الحال | متى | ماذا يصله |
|---|---|---|
| غير مؤهّل | غير معتمَد · أو اشتراكه منتهٍ · أو محجوب (`debt_blocked` / `advance_blocked` / `cancellation_carry_blocked`) | لا شيء. وزرّ وضع التوصيل معطَّل بسببٍ مكتوب بالعربية يقول **أيّ** شرط سقط |
| مؤهّل، خارج الوضع | الحال الافتراضية | رحلات فقط |
| **في وضع التوصيل — فارغ** | ضغط الزرّ | طلبات فقط (والرحلات لا، بحكم §D0.3) |
| في وضع التوصيل — بطلب جارٍ | قبل عدد `max_concurrent_orders` | طلبات إضافية إن سمح الحدّ وسقف النقد |
| في وضع التوصيل — بلغ الحدّ | بلغ عدد الطلبات، أو مجموع ما سيدفعه للمطاعم بلغ سقف النقد في يده | لا شيء حتى يسلّم، **ويرى السبب على شاشته** لا صمتاً |
| بالاستثناء (من اللوحة) | `delivery_exception_enabled` | طلبات دائماً، ورحلات حين لا طلب جارٍ |

**الدخول** يشترط: متصل، ولا رحلة جارية. **الخروج** يشترط: لا طلب جارٍ (معيَّن أو مستلَم) — ويُعرض السبب لا يُعطَّل الزرّ صامتاً.

### §D17.2 يوم عمل

| الوقت | ما يجري | ما يُقاس |
|---|---|---|
| 18:00 | يفتح التطبيق، اشتراكه سارٍ (هو نفسه اشتراك الركاب — §D0.7) | لا اشتراك جديد ولا خطة ثانية؛ والزرّ يفحص **الاشتراك نفسه** عند الدخول (فحص جديد الموضع، §D4) |
| 18:05 | يضغط **وضع التوصيل**. يختفي فوراً من خريطة الراكب ومن إسناد الرحلات | اختبار: راكب يطلب رحلة قربه فلا تصله |
| 18:07 | يصله عرض: المطعم · المسافتان · الرسوم · **تدفع 8.740 / تقبض 11.250** · جاهز 20:52 | قفل العرض يمنع أن يصله عرض رحلة في اللحظة نفسها |
| 18:20 | سلّم. 1.500 بيده، وصفّا دَين بـ1.010 (`store_commission` + `service_fee`، **محصَّلة نقداً**) | مجموع صفوف الدَّين = ما قبضه نيابةً بالضبط |
| 20:40 | بلغ سقف النقد (ثلاثة طلبات كاش متتابعة) | لا تصله عروض، والشاشة تقول: "بلغتَ سقف النقد — سلّم طلباتك" |
| 21:30 | دَينه بلغ سقف الدَّين (`driver_debt_ceiling`) | `debt_blocked` يشتعل (`debts.refresh_block`) — وهو **الحاجز نفسه** في الرحلات، لا حاجز ثانٍ |
| 21:35 | يسدّد: تلقائياً حين يدخل محفظته مال (`collect_from_balance`، صفّاً كاملاً)، أو بمطالبة CliQ يعتمدها مشرف (§D18.1) | يُرفع الحجب **عند الصفر لا عند النزول تحت السقف** (`refresh_block`، قرار المالك القائم: "من سدَّد نصفَه بقي ممنوعاً") |
| 23:00 | يخرج من الوضع؛ لا طلب جارٍ فيُسمح | لو كان بيده طلب: يُمنع بسبب مكتوب |
| 23:59 | إغلاق يوم الدولة — **قاعدة اليوم التالي لا تُشعَل بعد** (§D18.1) | — |

### §D17.3 الدَّين هو المفصل

كل مال يقبضه الكبتن نيابةً عن غيره (عمولة المتجر + رسوم الخدمة) يصير **صفّ دَين** في `driver_debts` بمصدره المسمّى (`store_commission` / `service_fee`) — لا رصيداً سالباً، لأن المحفظة لا تقبل السالب. وهذا يعيد استعمال ما بُني للرحلات (الترحيلة `0061`، `services/debts.py`): الجدول، وسقفه `driver_debt_ceiling`، وحاجزه `debt_blocked`، وتحصيله من أرباح لاحقة — والجديد مصدران وعمود `delivery_order_id`.

وترتيب التحصيل القائم: **الدَّين قبل السلفة** (رأس `services/debts.py`: "الدَّينُ أوّلاً")، والأقدم أولاً بين صفوف الدَّين. فصفوف التوصيل تدخل الطابور نفسه بتاريخها.

ونتيجته المهمّة: **كبتن التوصيل يمكن أن يُحجب بسبب رحلاته، وكبتن الرحلات بسبب توصيله** — الدفتر واحد. وهذا مقصود: مالك واحد، ودَين واحد، وحاجز واحد. ويُكتب للكبتن في شاشة الحجب سببٌ يسمّي المصدر (رحلات/توصيل) كي لا يبحث عن علّة في المكان الخطأ.

### §D17.4 ما لا يتغيّر عن الرحلات

الاشتراك · المستويات والمهام · الإحالة · السلفة وسقفها · نقطة الوقوف · ساعات الهدوء · التقييم · الحظر والإيقاف · متجر المركبات. كلّها تعمل كما هي، ودخل التوصيل يدخل في حساباتها كدخل الرحلات — **إلا ما نُصّ عليه هنا**: لا عمولة على دخل التوصيل، ولا اشتراك ثانٍ، ولا حصة من رسوم التوصيل.

### §D17.5 ثلاثة أسئلة مفتوحة تخصّ الكبتن

| # | السؤال | الافتراض |
|---|---|---|
| A | هل تُحسب توصيلة في عدّاد المهام والمستويات كرحلة؟ | نعم — عمل واحد ومستوى واحد؛ والبديل (عدّاد مستقل) يشقّ النظام بلا سبب |
| B | إلغاء الكبتن لطلب بعد قبوله: كيف يُحسب عليه؟ **تصحيح من الشجرة**: `cancellation_carry_blocked` ليس عدّاد إلغاءات — هو حجب كبتن قبض رسم إلغاء نقداً لكبتن آخر ولم يحوّله (`design/CANCELLATION-FEE.md` §6-أ، تعليق `dispatch.py:408`). **ولا عدّاد إلغاءات للكبتن في النموذج**؛ ما يوجد `cancellation_rate` مجمَّعاً في تقرير `services/stats.py` | سؤال مفتوح (§D11-Q29) — والإلغاء بعد الاستلام ليس إلغاءً بل `undeliverable` (§D19.1) |
| C | كبتن في وضع التوصيل وسقف نقده صفر (كبتن جديد): يعمل على طلبات المحفظة فقط؟ | نعم — وهي مدخل آمن للكبتن الجديد، ويُكتب له ذلك صراحةً لا يُترك يستنتجه |

## §D18 التسويات: الكبتن مع TAXO، وTAXO مع التجّار (قرار موقَّع)

بعد هذا القسم صار في النموذج دفتران متقابلان: **ما على الكبتن لـTAXO** (عمولة ورسوم قبضها نقداً)، و**ما على TAXO للتاجر** (طلبات دفعها الزبون بالمحفظة). ولكلٍّ دورته وبابه.

### §D18.1 قاعدة اليوم التالي (الكبتن) — مقرَّرة مبدأً، **ولا تُشعَل بعد**

**المبدأ**: الكبتن لا يعمل اليوم التالي حتى يسدّد ما عليه. عند بداية يوم الدولة، كل دَين من يوم سابق يمنع العمل — في التوصيل **وفي الرحلات معاً**، لأن الحساب واحد.

#### مسار السداد اليوم — مُثبَت من الشجرة (2026-09-19)

| الطريق | كيف يعمل | من يعتمده | كم يستغرق |
|---|---|---|---|
| **تحصيل تلقائي من المحفظة** | `debts.collect_from_balance` (`services/debts.py:161`) يُنادى من تسوية كل رحلة يدخل مالها محفظة الكبتن (`services/payments.py:602,675`)، ويحصّل **صفّاً كاملاً فأكمل من الأقدم** ما دام الرصيد يغطّيه، بقيد `commission` | لا أحد — آلي | لحظي، **لكنه لا يقع إلا حين يدخل المحفظة مال**. وكبتن يعمل كاشاً وحده لا يدخل محفظته شيء (رأس `services/cliq_debts.py`: "فمن يعمل كاشاً وحدَه لا يدخل محفظتَه شيءٌ أبداً") |
| **زرّ "سدّد من محفظتي"** | **غير موجود**: لا مسار للكبتن يسدّد من رصيده بطلبه. مسارات دَينه ثلاثة فقط: `GET /drivers/me/debt` · `POST /drivers/me/debt/cliq` · `GET /drivers/me/debt/cliq` (`routers/drivers.py:620-661`)، وشاشته `driver-app/src/screens/Debt.tsx` فيها CliQ وحده | — | — |
| **مطالبة CliQ** | الكبتن يكتب المبلغ (جزئياً مقبول، ولا فوق دَينه) فيُفتح `provider_order` بغرض `debt` ومصدر `manual` (`services/cliq_debts.py`)، ثم يحوّل بنفسه | **مشرف** من اللوحة: `POST /admin/drivers/debts/claims/{order_id}/confirm` (`routers/admin_users.py:969`)، ثم `debts.apply_settlement` توزّع المبلغ على الصفوف من الأقدم | **غير محدود ولا مقيس**: لا مهلة ولا SLA ولا تنبيه في الشجرة — ينتظر حتى يفتح مشرف الشاشة. ويصير آلياً فقط إن أُدخل عقد القابض (`ProviderOrderSource.acquirer`) |
| **شطب** | `POST /admin/drivers/debts/{debt_id}/writeoff` بسبب مكتوب | مشرف | — |

**ورفع الحجب** يقع في المسار نفسه (`debts.refresh_block`): يُشعَل فوق `driver_debt_ceiling`، **ويُطفأ عند الصفر لا عند النزول تحت السقف**.

#### لذلك (قرار المالك 2026-09-19)

- **قاعدة اليوم التالي لا تُشعَل قبل وجود سداد لحظي من المحفظة بلا مشرف** — أي زرّ "سدّد من محفظتي" يحصّل فوراً. وقبله تكون القاعدة حبساً لا حافزاً: الكبتن الذي يريد السداد صباحاً ينتظر مشرفاً لا يُعرف متى يأتي.
- **المبلغ المتنازع عليه لا يُحتسب فيها** (ولا في سقف الدَّين — §D19): دَين مصدره طلب في `pending_review` خارج الحساب حتى يُبتّ. **وهذا يمسّ `refresh_block` و`outstanding_of` القائمين**: كلاهما يجمع كل صفّ `outstanding` اليوم بلا استثناء، فالاستثناء شرط يُضاف إليهما ويُختبر في الاتجاهين.
- وهي **أشدّ من سقف الدَّين القائم ولا تلغيه**: السقف يمنع التراكم داخل اليوم، والقاعدة تمنع ترحيل الدَّين إلى الغد؛ والحاجز واحد (`debt_blocked`) وله حين تُشعَل سببان — والشاشة تسمّي السبب.
- المنع يُعرض قبل وقوعه: تنبيه عند نهاية اليوم بما عليه ومهلته، ثم شاشة صريحة عند الحجب تقول المبلغ ومصدره (توصيل/رحلات) وطرق السداد.

#### ما يُحجز منذ اليوم الأول (قرار المالك 2026-09-19)

**كل سداد دَين وكل تسوية يحمل `channel` (`wallet` · `transfer` · `office`) و`recorded_by`** — كي تصير مكاتب التسوية لاحقاً قيمةً جديدة في `channel` لا بنيةً جديدة. وفي الشجرة اليوم **لا يحمل السداد أيّاً منهما**: `driver_debts.collected` مجموع، والتحصيل الآلي قيد `commission` بمفتاح `debt_collect:{id}`، ومطالبة CliQ صفّ `provider_orders` بمصدر `manual/acquirer`. فيُبنى `driver_debt_payments` (§D2) صفّاً لكل سداد، يكتبه كل طريق من الثلاثة، و`recorded_by` للآلي هو `NULL` معلَّلاً ("النظام") لا مستخدماً مخترعاً.

### §D18.2 دفتر التاجر ومندوب التسوية

كل طلب محفظة يُقيَّد `merchant_net` مستحقاً للتاجر في دفتره. والتسوية **دورة لها بداية ونهاية** لا تحويلاً عابراً:

| الخطوة | من | ما يُكتب |
|---|---|---|
| 1. الدورة | النظام | `merchant_settlements`: التاجر · الفترة (من/إلى بيوم الدولة) · المبلغ (= مجموع قيود `merchant` في الفترة) · الحال `open` — **والطلبات تُقرأ من قيود الفترة، لا تُحمل على الدورة** (Q20) |
| 2. الإصدار | المشرف | تُغلق الفترة وتصير `pending` بكشفٍ مطبوع أو مقروء من تطبيق التاجر — التاجر يرى **قبل** وصول المندوب كم له وعلى أي طلبات |
| 3. الزيارة | المندوب | يسجّل الدفع من تطبيقه/اللوحة: المبلغ · التاريخ · `channel` (`transfer` · `office` — والنقد باليد قيمة تُسمّى، §D11-Q30) · `recorded_by` · ملاحظة |
| 4. **الإقرار** | التاجر | يؤكّد الاستلام من جهازه، فتصير `settled`. **بلا إقرار التاجر لا تُغلق دورة** — وهي الحماية الوحيدة الحقيقية حين يحمل موظّف نقداً |
| 5. الخلاف | المشرف | `disputed` بسبب مكتوب، ولا تُحذف دورة ولا تُعدَّل: يُفتح تصحيح مقابل |

- دورية التسوية لكل تاجر (أسبوعية/نصف شهرية/شهرية) حقل على التاجر يُتَّفق عليه في العقد، لا قيمة عامة.
- **الدورة تشير إلى صفوف الدفتر ولا تحملها** (قرار المالك 2026-09-19، Q20): كل طلب محفظة كتب عند `delivered` قيداً دائناً بـ`merchant_net` في `wallet_transactions` (`owner_type = merchant`، `owner_id` = `merchants.owner_user_id`، `merchant_id` = التاجر — Q38، و`delivery_order_id` = الطلب). و`merchant_settlements` تحمل **حدود الفترة** (من/إلى بيوم الدولة) والتاجر والمبلغ والحال، **ولا تحمل الطلبات ولا نسخة من مبالغها**: صفوف الدورة = قيود `merchant` لصاحبها في فترتها، والمبلغ = مجموعها.
- **ولا تُعلَّم الصفوف "مسوّاة"**: الدفتر لا يُعدَّل (مُشغّل `0006`)، فلا يُكتب على القيد رقم دورته بعد كتابته. والصرف قيد مدين جديد على المحفظة نفسها يحمل مرجع الدورة (`reference`)، فيعود الرصيد إلى ما لم يُسوَّ بعد — وهو ما يُقرأ "المستحق الآن".
- **وتعارض يُسمّى**: جدول 0.1 أعلاه يقول إن الدورة تكتب "الطلبات الداخلة فيها" — وهو **حملٌ** لا إشارة، فيخالف القرار. المقصود بعده: تُقرأ الطلبات من قيود الفترة، ولا تُنسخ.
- المندوب **دور جديد** (`settlement_agent` — قيمة جديدة في `user_role`، §D2) صلاحيته ضيّقة — وفي الشجرة نموذج صلاحيات إداري (`admin_permissions`، الترحيلة `0070`) يُقرأ قبل أن يُبنى للمندوب نموذج ثانٍ: يرى تجّاره ودوراتهم المستحقة، ويسجّل دفعاً، ولا يرى شيئاً آخر ولا يعدّل قيمة دورة.
- كشف التاجر يُظهر لكل طلب: الأصناف · العمولة · الصافي · طريقة دفع الزبون — فالتاجر يقارن بإيصالاته المطبوعة، وهي عنده ورقاً.

### §D18.3 لا دَين بين الكبتن والتاجر — مبدأ لا تفصيل

**الكبتن لا يدين للتاجر بشيء في أي حال**، وهذا اختيار لا صدفة:

- طلب كاش: يدفع `merchant_net` نقداً لحظة الاستلام. لا استلام بلا دفع، فلا دَين.
- طلب محفظة: لا يدفع شيئاً، والمستحقّ على TAXO للتاجر لا على الكبتن.
- لا يُستلم طلب بلا نقد كافٍ: سقف التعرّض النقدي يمنع أن يُعرض على الكبتن طلبٌ لا يملك ثمنه (§D1.1).
- طلب غير قابل للتسليم بعد الاستلام: التاجر قبض حقّه سلفاً (أو قُيِّد له في طلب المحفظة)، والخسارة بين TAXO والزبون والكبتن بخيار المشرف (§D19.1) — والتاجر خارجها تماماً.

**العلّة**: لو دان الكبتن للتاجر لصارت العلاقات المالية حاصلَ ضرب (كل كبتن × كل تاجر) بدل جمعها (كباتن + تجّار)، ولاحتاج كل تاجر دفتراً لكل كبتن ونزاعاً مع كل كبتن، ولصار **التاجر** هو من يمنح الائتمان لا TAXO. أي نموذج "الدفع الآجل من المطعم" يُبنى لاحقاً يجب أن يعبر هذا الباب صراحةً، ويبقى خارج §D18 كلّه.

### §D18.4 مكاتب التسوية (بند مستقبلي مسجَّل)

مكاتب يأتي إليها الكباتن لتسوية ديونهم والتجّار لاستلام مستحقاتهم. **لا تُبنى الآن**، ويُكتب هنا شكلها كي لا يُبنى اليوم ما يمنع بناءها غداً.

**ثلاث خدمات على شبّاك واحد**:

| الخدمة | من | ما يجري |
|---|---|---|
| سداد دَين كبتن | الكبتن | يعطي الموظّف رقمه، يرى الموظّف المبلغ المستحق، يقبض ويسجّل — ويُرفع الحجب **لحظة التسجيل** لا بعد مراجعة، لأن النقد بيد الموظّف |
| صرف مستحقّ تاجر | التاجر (أو مندوبه بتفويض) | دورة تسوية `pending` تُصرف عند الشبّاك بدل زيارة المندوب، ويقرّ التاجر من جهازه كما في §D18.2 |
| شحن محفظة نقداً | الزبون · الراكب · الكبتن | نقدٌ يصير رصيداً في المحفظة — وهذه أنفعها تجارياً: تفتح المحفظة لمن لا بطاقة له ولا CliQ |

**الضوابط التي تجعل مكتب نقد آمناً** (وبغيابها يتحوّل المكتب إلى ثقب):

- **درج لكل مكتب بدفتر مستقلّ**: المكتب يقبض ويدفع، فله رصيد يُفتح مع الوردية ويُقفل في نهايتها. والفرق بين المسجَّل والمعدود يُكتب صفّاً باسمه (`cash_variance`) ولا يُبتلع بصمت.
- **إيصال مرقَّم** لكل عملية، والتسلسل لا فجوة فيه — الفجوة نفسها دليل.
- **إقرار الطرف الثاني**: الكبتن يرى السداد في تطبيقه لحظتها، والتاجر يقرّ بالاستلام من جهازه. طرفٌ واحد يسجّل ويؤكّد وحده = لا رقابة.
- **سقف يومي لما يصرفه المكتب** بلا موافقة مشرف، وفصلٌ بين من يسجّل ومن يقفل الوردية.
- **صلاحية ضيّقة**: موظّف المكتب يرى من أمامه وحده، ولا يفتح قائمة كباتن ولا تجّار.

**ما يتغيّر في التشغيل حين تُفتح**: المندوب يصير خياراً للتجّار البعيدين لا الطريق الوحيد، فتقلّ مخاطرة حمل النقد في الطريق؛ وقاعدة اليوم التالي تصير محتملة لكل كبتن لأن له باباً مفتوحاً للسداد صباحاً بلا انتظار مشرف.

**المحجوز اليوم لأجلها** — وهو كل ما يلزم الآن: كل سداد دَين (`driver_debt_payments`) وكل تسوية (`merchant_settlements` ودفعاتها) يحمل `channel` (`wallet` · `transfer` · `office`) و`recorded_by` منذ اليوم الأول (§D18.1). بهذين الحقلين تصير إضافة المكتب لاحقاً قيمةً جديدة في حقل قائم، لا بنيةً تُشقّ في دفتر فيه مال.

### §D18.5 الدفع المؤجَّل للمطعم — امتياز يُمنح بالسلوك (بعد المكاتب)

بند مستقبلي أقرّه المالك مبدأً، **لا يُبنى قبل فتح مكاتب التسوية** (§D18.4) لأن عائقه الحقيقي ليس الكود بل غياب باب سداد يومي مفتوح.

**الفكرة**: كبتن مؤهَّل يستلم طلب الكاش **بلا أن يدفع للمطعم**، فيُقيَّد `merchant_net` ديناً عليه مع العمولة والرسوم، ويسوّي في المكتب. وأثره بالأرقام (المثال نفسه): دَين الطلب يصير 9.750 بدل 1.010 — تسعة أضعاف، فالمنصّة هي الممولة لا الكبتن.

**شروطه الأربعة، ولا يُبنى بنقصان واحد منها**:

1. **امتياز لا قاعدة**: يُفتح بشكل سقف السلفة (`min(computed, override)`) — **وتصحيح من الشجرة**: `computed` في `advances.cap_for` ليس "المستوى والتاريخ" بل سعر الخطة اليومية × مضاعف ينمو بعدد السلف المسدَّدة؛ فمعيار "من عمل شهوراً وسدّد بانتظام" يحتاج قاعدة تُكتب حين يُبنى البند. حقلٌ على الكبتن لا نظام جديد.
2. **سقف يومي لما يحمله بلا سداد** (لا سقف لكل طلب): بلغه ⇒ يعود إلى الدفع الفوري في الطلب التالي، ويرى السبب على شاشته.
3. **خيار لا فرض**: من يريد الدفع الفوري يدفع ويبقى دَينه صغيراً — مفتاح في صفحة التوصيل، والافتراض الدفع الفوري.
4. **قاعدة اليوم التالي (§D18.1) تبقى كما هي**، وسحب الامتياز عقوبةُ التأخّر الأولى — لا غرامة مال.

**ما يجعله يعمل**: الامتياز يُمنح بالسلوك ويُسحب به، فيصير حافزاً على الانضباط أقوى من أي غرامة — وهو منطق نظام السلف القائم عندك حرفياً.

**ما يحجزه اليوم**: لا شيء زائد على §D18.4 — الحقلان `channel` و`recorded_by`، وأن يكون مصدر الدَّين مسمّى في `DriverDebtSource` (`store_commission` · `service_fee` · **`goods_price`** — والثالث لا يُكتب الآن) كي يُفرَّق بينها في الكشف وفي السقوف حين يأتي.

### §D18.6 ثلاثة أسئلة

| # | السؤال | الافتراض |
|---|---|---|
| A | سداد جزئي: يرفع الحجب أم لا؟ | لا — وهو **مبنيّ سلفاً لسقف الدَّين**: `refresh_block` يُطفئ عند الصفر لا قبله، والجزئي يُقبل (`apply_settlement`، مطالبة CliQ). وقاعدة اليوم التالي حين تُشعَل ترثه |
| B | كبتن انقطع وعليه دَين | الدَّين يبقى ولا يسقط بالوقت؛ ولا يُفتح له عمل حتى يسدّد. والشطب **باب قائم**: `POST /admin/drivers/debts/{debt_id}/writeoff` بسبب مكتوب (`debts.write_off`) |
| C | تاجر عليه مستحقّ لـTAXO (ردّ دفعة، تصحيح) في الاتجاه المعاكس | تُخصم من دورة التسوية التالية، والكشف يظهر السطرين معاً لا صافياً مبهماً |

## §D19 قرارات النزاع — قائمة مغلقة يختار منها المشرف (قرار موقَّع)

المالك قرّر ألّا تُحسم حالات الخلاف بقاعدة آلية، بل **يختار المشرف لكل حالة**. وشرط ذلك أن تكون الخيارات قائمة مغلقة، لكل خيار أثرٌ مالي مكتوب سلفاً — لا مبلغ يُكتب بحرية، ولا قرار بلا سبب مسجَّل. وإلا صار الدفتر رهن اجتهاد موظّف، وتعذّر تفسير رقم بعد شهر.

**القواعد الحاكمة لكل قرار نزاع**:
1. الخيار من قائمة، والسبب مكتوب إلزامي، والقرار يُسجَّل في التدقيق بمن اتّخذه ومتى.
2. **حالة مؤقتة قبل القرار**: الطلب يصير `pending_review` — والكبتن يواصل عمله، والدَّين المتنازع عليه لا يدخل في قاعدة اليوم التالي (§D18.1) ولا في سقف الدَّين، حتى يُبتّ. (وطلب undeliverable لا دَين له أصلاً — §D19.1؛ فالقاعدة تخصّ دَيناً نشأ بعد `delivered` ثم نوزع فيه، كبلاغ §D13.1-6.)
3. **مهلة بتّ** تُضبط من اللوحة، وتجاوزها يظهر في لوحة المشرف قائمةً بالمتأخّر — الكبتن لا يُترك معلّقاً بلا أجل.
4. لا خيار يُضاف بكود متفرّق: القائمة تعداد واحد تحت `check:enums` تقرأه اللوحة والخلفية.

### §D19.1 طلب غير قابل للتسليم (الكبتن دفع ولم يجد الزبون)

**تصحيح على قرار المالك 1 (2026-09-19)**: صفوف الدَّين تُكتب عند `delivered` وحدها، **فطلب undeliverable لا دَين له أصلاً** — الكبتن دفع `merchant_net` ولم يقبض شيئاً. فعبارة 0.1 "يُلغى دَين الطلب" لا مقابل لها، والأثر أدناه صُحِّح على ذلك **لطلب الكاش**. أمّا **طلب المحفظة** فالكبتن لم يدفع شيئاً والزبون خُصم منه `total` — فخياراته غير هذه، وهي سؤال §D11-Q31.

| الخيار (طلب كاش) | أثره في الدفتر | متى يناسب |
|---|---|---|
| تعويض كامل للكبتن | `delivery_compensation` = `merchant_net` + `delivery_fee` في محفظة الكبتن من TAXO؛ ولا صفّ دَين | الزبون لا يردّ والكبتن انتظر وصوّر |
| تعويض جزئي | `delivery_compensation` = `merchant_net` وحده | تقصير جزئي من الكبتن |
| الكبتن يأخذ الطلب بلا تعويض | لا قيد — يتحمّل هو ثمن البضاعة الذي دفعه | عنوان خاطئ من الكبتن، أو مخالفة إجراء |
| تحميل الزبون | يُعوَّض الكبتن كاملاً، ويُسجَّل المبلغ ديناً على الزبون — **ولا نموذج لدَين الزبون في الشجرة، ومحفظته لا تقبل السالب** (§D11-Q25) | زبون تكرّر منه، أو رقم صحيح ولم يردّ عمداً |
| إعادة المحاولة | الطلب يعود `picked_up` بمحاولة ثانية بعد اتصال المشرف بالزبون | خلل تواصل لا أكثر |

ومع كل خيار: مفتاح مستقلّ **"احجب الكاش عن هذا الزبون"** (`customer_cash_blocked`) بسبب يراه الزبون، يرفعه المشرف.

### §D19.2 المطعم يلغي بعد القبول والكبتن في الطريق

| الخيار | أثره | متى يناسب |
|---|---|---|
| تعويض الكبتن برسوم التوصيل الأساسية | `delivery_compensation` = `delivery_base_fee` (قيمة الدولة وقت القرار — §D11-Q32) في محفظة الكبتن من TAXO | الحال الغالبة |
| تعويض برسوم التوصيل كاملة | `delivery_compensation` = `delivery_fee` المجمَّدة | مسافة طويلة قطعها فعلاً |
| تحميل التاجر | التعويض نفسه، ويُقيَّد مديناً على محفظة التاجر (`merchant`) فيُنقص تسويته التالية — **ويسقط إن زاد على رصيده** (`wallet_balance_non_negative`، §D11-Q35) | تكرّر منه، أو ألغى بعد أن كان جاهزاً |
| لا تعويض | لا قيد | ألغي قبل أن يتحرّك الكبتن |

وفي كل الأحوال: عدّاد إلغاءات على التاجر ظاهر في بطاقته، وتنبيه للمشرف عند تجاوز حدّ يُضبط من اللوحة — فالقرار لكل حالة، لكن النمط يجب أن يُرى.

### §D19.3 دورية التسوية تُختار لكل تاجر بلا افتراض

`settlement_cycle` حقل إلزامي على التاجر (أسبوعي · نصف شهري · شهري · عند الطلب)، **ولا قيمة افتراضية**: لا يُعتمد تاجر قبل ضبطه، والشاشة تمنع الاعتماد وتقول السبب. علّته أن الافتراض الصامت في بند مالي يصير التزاماً لم يتّفق عليه أحد، ويُكتشف عند أول خلاف.

## §D10 ما لا يُبنى الآن

- طلبات مجدولة (توصيل في وقت لاحق).
- كوبونات وعروض على الطلبات (حقل `discount` يبقى 0.000 ويُحجز في النموذج).
- سلوكيات خاصة بالبقالة: البيع بالوزن، والبدائل عند نفاد صنف بعد القبول (المطعم/المتجر يلغي أو يتصل)، وجرد الكميات (`branch_item_availability` متوفّر/غير متوفّر لا عدد).
- سلة من أكثر من تاجر في طلب واحد.
- حسابات موظفين للفروع (حساب التاجر واحد).
- أكثر من طلب متزامن للكبتن من فروع مختلفة (الرفع من اللوحة يبقى لفرع واحد).
- الإلغاء الذاتي للزبون بعد القبول.
- تقييم ثنائي (المطعم أو الكبتن يقيّم الزبون).
- بقشيش كبتن التوصيل — بقشيش الرحلات لا يُعاد استعماله بلا كود (`tips.ride_id` إلزاميّ فريد)، فيبقى هنا.
- **الإطلاق لكل مدينة** (`delivery_enabled` لكل مدينة) — لا مفهوم مدينة في النموذج، والتغطية بنصف قطر الفرع والتوزيع ووجود تاجر؛ والمفتاح لكل دولة (§24). بقرار المالك 2026-09-19.
- **تقرير التاجر المسائي على واتساب** — البوابة لا تقبل نصّاً بقصد مكتوب (SPEC §19، `whatsapp-gateway/src/index.js`)؛ وفتح باب نصّ حرّ عليها قرار مستقل. البديل في الإصدار الأول شاشة تقارير + إشعار FCM (§D14.أ-7). بقرار المالك 2026-09-19.
- **إعادة توليد `design/ERROR-COVERAGE.md`** — المولّد غير موجود في الشجرة (§D7).
- زرّ التبديل راكب↔زبون.
- النموذجان (أ) و(ب) للكاش.
- حصة TAXO من رسوم التوصيل.
- إعلانات مدفوعة/ترتيب مميّز للتجار.
- المكالمات والدردشة داخل التطبيق (مؤجَّلة أصلاً في TAXO).
- السِمة النسائية: **لا تنطبق** على التوصيل (لا مطابقة تفضيل بين كبتن وزبون) — التطبيقان بهوية TAXO الأساسية.
- محرّك عروض للزبون (كوبونات، كاش باك، توصيل مجاني كحملة) — والمؤجَّل بعلّته في §D13.2.
- تطبيق TaxoEat مستقلاً بمعرّف ونطاق ونكهة خاصة (يبقى قسماً؛ فصله لاحقاً يعني قناةً سادسة وخطوة صفر سداسية).
- عمولة أو رسوم توصيل لكل قسم (لكل دولة وتاجر فقط).
- وسم المطبخ (شاورما/برجر/بيتزا) والتصفّح به.
- iOS (ملف مستقل).

---

## §D11 الأسئلة المفتوحة (تُجاب قبل المرحلة 2)

| # | السؤال | الافتراض إن لم يُجَب |
|---|---|---|
| ~~Q1~~ | **مقرَّر: قرار مشرف من قائمة §D19.1** | (افتراض 0.1 التاريخي: تعويض الكبتن من TAXO بعد مراجعة الصورة — والقيد اسمه الآن `delivery_compensation`، و`undeliverable_reimbursement` سقط) |
| ~~Q2~~ | **مقرَّر: قرار مشرف من قائمة §D19.2** | (افتراض 0.1 التاريخي: `delivery_base_fee` للكبتن من TAXO بقيد `delivery_compensation`، وعدّاد إلغاءات للتاجر 3 في 7 أيام ⇒ تنبيه مشرف) |
| Q3 | هل تُدفع رسوم التوصيل للكبتن بالكامل حتى للمسافة الصفرية (زبون بجوار الفرع)؟ | نعم، الحدّ الأدنى `delivery_min_fee` |
| Q4 | العمولة على `subtotal` أم على `subtotal + delivery_fee`؟ | على `subtotal` وحده |
| Q5 | مهلة قبول المطعم الافتراضية؟ | 180 ثانية، قابلة للضبط |
| Q6 | هل يرى الزبون رقم هاتف المطعم والكبتن؟ | المطعم: نعم (`public_phone`)؛ الكبتن: نعم بعد `assigned` كالرحلات |
| Q7 | هل يستطيع التاجر إيقاف استقبال الطلبات مؤقتاً بزرّ ("مشغول")؟ | نعم — `branches.status = paused` من تطبيقه |
| ~~Q8~~ | **مقرَّر 2026-09-19: الأنواع لكل دولة من اللوحة، لكل نوع اسمه وإلزاميّته — صفوف في `merchant_document_types` لا تعداد (§D1.5)**؛ والأردن بالافتراض المكتوب | هوية المالك + صورة الواجهة إلزاميتان، السجل التجاري اختياري |
| Q9 | متجر TAXO الغذائي: عمولته واشتراكه؟ | `owned_by_taxo = true` ⇒ معفى من الاشتراك، وعمولته تُحسب وتُقيَّد كالمعتاد لتبقى التقارير صادقة ثم تُطرح في تقرير واحد "داخلي"؛ وظهوره للزبون بلا ترتيب مميّز (الترتيب المدفوع في §D10) |
| Q13 | تسمية رسوم الزبون: "رسوم خدمة" أم "ضريبة"؟ | **رسوم خدمة**. "ضريبة" لفظ قانوني في الأردن (ضريبة المبيعات تُحصَّل وتُورَّد بشروط)، وكتابته على فاتورة بلا سندٍ يعرّضك لما لا يلزمك، ويُفهم أنه للدولة لا لك |
| Q15 | طراز الجهاز: الفحوص الخمسة في §D15.2 على جهاز واحد | لا شراء بالجملة قبل إيصال عربي حقيقي من التطبيق وطلبٍ يصل والشاشة مطفأة |
| Q19 | هل تشحن المكاتب محافظ الزبائن والركاب نقداً (حين تُفتح)؟ | نعم — أنفع ما فيها تجارياً، وتُبنى بدفتر الدرج نفسه |
| ~~Q18~~ | **مقرَّر: حقل إلزامي لكل تاجر بلا افتراض (§D19.3)** | نصف شهرية — تقصير الدورة يرضي التاجر ويكثّر زيارات المندوب، وإطالتها تراكم نقداً عند TAXO ومخاطرةً عند التاجر |
| ~~Q17~~ | شروط الجهاز | **مقرَّر: تُختار لكل تاجر عند التجهيز** (§D15.5) — أربع صيغ في حقل واحد، تختلف باختلاف العرض وقت التعاقد |
| ~~Q16~~ | البيع داخل المحل | **مقرَّر: الطلبات الواردة وحدها.** البيع الداخلي (كاشير كامل: جلسات، مرتجعات، درج نقد، تقارير وردية) خارج النطاق — وهو ورقة تفاوض لاحقة لا بند إصدار أول |
| Q14 | قيم الإطلاق في الأردن: نسبة عمولة التاجر، ورسوم الخدمة، ومدة المجّانية `free_until`؟ | كلها أعداد تُدخل من اللوحة يوم الإطلاق ولا تُكتب في الكود — والقرار يخصّك |
| Q12 | "اطلب أي شيء" (§D13.2): يُفتح ملفاً مستقلاً الآن أم يُترك بعد الإطلاق؟ | يُترك حتى تستقرّ المرحلة 7 |
| Q11 | أسماء بقية الأقسام داخل TAXO MARKET (البقالة، الصيدلية…) على غرار TaxoEat؟ | بلا أسماء تجارية الآن — أسماء وصفية عربية حتى تقرّر |
| Q10 | ~~من يزوّد قائمة متجر TAXO~~ | **مقرَّر: شاشة في لوحة الإدارة** — بشرط §D15.6: الشاشة تنادي مسارات التاجر نفسها بمعامل merchant_id، فالمنطق واحد والواجهة بابان |

### أسئلة نشأت من تثبيت الأسماء على الشجرة (المرحلة 0، 2026-09-19) — بلا تخمين

| # | السؤال | ما أُثبت | يعطّل |
|---|---|---|---|
| ~~Q20~~ | **مقرَّر 2026-09-19: محفظة `merchant` ودفتر `wallet_transactions` القائمان، لا جدول ثالث؛ والدورة تشير إلى صفوف فترتها (§D6، §D18.2)** — نصّ السؤال كان: أين يُقيَّد مستحقّ التاجر على TAXO (طلبات المحفظة، وتحميله في §D19.2، وردّه في §D18.6-C): رصيد محفظة بغرض `merchant` (قيد دائن عند `delivered`، ومدين عند التسوية) أم جدول دفتر مستقل؟ | المحفظة لا تقبل السالب، وتحميل التاجر قد يزيد على مستحقّه؛ و§D0 يقول محفظة التاجر "للاشتراك والتصحيحات فقط" | المرحلة 2 |
| Q21 | **قاعدة `computed` لسقف النقد** | لا قاعدة في الشجرة؛ `advances.cap_for` = سعر الخطة اليومية × مضاعف السداد، ونسخه يجعل سقف النقد = سقف السلفة | المرحلة 2 |
| Q22 | **`delivery_assignments` و§5-ج**: الكتابة بعد إرسال العرض ما زالت داخل "نافذة التوزيع حتى قبول العرض" بنصّ §5-ج، وهو ما رُفض لأجله `ride_offers`. استثناء موقَّع باسمه في §5-ج، أم تُكتب صفوف الدورة دفعةً واحدة بعد انتهائها (قبول/مهلة)؟ | قرار المالك: "بعد الإرسال وخارج مسار الترتيب" — وخارج الترتيب لا يعني خارج النافذة | المرحلة 2 |
| ~~Q23~~ | **مقرَّر 2026-09-19: عمود في `delivery_settings`، لا `FeatureKey`؛ ويُنشر حقلاً على `CountryConfigOut` (§D2)** — نصّ السؤال كان: `delivery_enabled`: عمود في `delivery_settings` أم مفتاح `FeatureKey` في `feature_flags` كنمط §24 ("مفتاح لكل دولة"، يُبدَّل من شاشة الإعدادات ويُسجَّل في التدقيق)؟ | القرار 7 يضعه مع مفاتيح §D2، ونمط الشجرة لإشعال ميزة لكل دولة هو `feature_flags` (وغيابه = مطفأ)، ومعه خطأ قائم `feature_disabled` | المرحلة 1 |
| ~~Q24~~ | **مقرَّر 2026-09-19: `merchant_plan_id` → `merchant_subscription_plans` وقيد نظير، و`plan_id` وقيده كما هما (§D2)** — نصّ السؤال كان: خطة التاجر في `provider_orders`: `plan_id` مفتاح إلى `subscription_plans`، وقيد `provider_order_plan_matches_purpose` يربطه بغرض `subscription`. عمود جديد `merchant_plan_id` وقيد مثله لغرض `merchant_subscription`؟ | القرار 12 يطلب "اشتراك التاجر مع قيد plan_id"، والقرار 13 يضع الخطط في جدول آخر — فـ`plan_id` نفسه لا يصلح | المرحلة 1 (الاشتراك مبنيّ ومطفأ) |
| Q25 | **دَين الزبون** (§D19.1 "تحميل الزبون"): لا نموذج لدَين راكب/زبون في الشجرة، ومحفظته لا تقبل السالب. جدول دَين للزبون، أم يسقط الخيار ويبقى حجب الكاش؟ | `driver_debts` خاصّ بالكبتن (`driver_id`) | المرحلة 2 |
| ~~Q26~~ | **مقرَّر 2026-09-19: قاعدة واحدة للثلاثة — زوج مؤجَّل + beat + إشعار بمدة رقمية (§D1.9)** — نصّ السؤال كان: إشعال `billing_mode` وتغيير رسوم الخدمة: يمرّان بزوج مؤجَّل كالعمولة، أم يسريان فوراً؟ | القرار 8 سمّى زوج العمولة وحده | المرحلة 1 (الأعمدة) |
| Q27 | **إحالة التجّار (§D14.أ-8)**: تدخل الإصدار الأول؟ | الإحالة القائمة مكافأتها مال بعد رحلات؛ "تمديد `free_until`" نوع مكافأة وشرط جديدان | لا يعطّل — يؤجَّل إن لم يُجَب |
| Q28 | **المفضّلة**: §D13.1-8 تدخلها الإصدار الأول و§D13.2 تؤجّلها — تناقض داخل الملف | — | المرحلة 5 |
| Q29 | **إلغاء الكبتن لطلب بعد قبوله** (§D17.5-B): بأيّ عدّاد يُحسب؟ | لا عدّاد إلغاءات للكبتن في النموذج؛ `cancellation_carry_blocked` شيء آخر | المرحلة 2 |
| Q30 | **`channel` لدفع المندوب للتاجر نقداً**: القرار 19 سمّى `wallet · transfer · office`، ودفع المندوب في الزيارة ليس أيّاً منها. قيمة رابعة (`agent_cash`)؟ | — | المرحلة 6 |
| Q31 | **undeliverable لطلب المحفظة**: الكبتن لم يدفع شيئاً والزبون خُصم منه `total`. ما خيارات المشرف؟ (ردّ للزبون كامل/ناقص، تعويض الكبتن بـ`delivery_fee`، قيد للتاجر وقد حضّر الطعام) | §D19.1 مكتوبة لطلب الكاش | المرحلة 2 |
| Q32 | **`delivery_base_fee` في تعويض §D19.2**: قيمة الدولة وقت القرار، أم تُجمَّد على الطلب عند `placed`؟ | الطلب يجمّد `delivery_fee` وحده | المرحلة 2 |
| ~~Q34~~ | **مقرَّر 2026-09-19: لا قيد فريد؛ والمشرف يقرّر عند الإنشاء نشاطين أم نشاطاً بفرعين (§D1.5)** — وأثره على مفتاح المحفظة Q38. نصّ السؤال كان: تاجر لكل مستخدم؟ مفتاح المحفظة `(users.id, owner_type)` يعطي محفظة `merchant` واحدة لكل مستخدم. فهل يُمنع أن يملك مستخدم أكثر من تاجر (قيد فريد على `merchants.owner_user_id`)، أم تُفرَّق المحافظ بغير ذلك؟ | §D1 #5 "حساب واحد للتاجر" لا يقول "تاجر واحد للحساب" | **المرحلة 1** (جدول `merchants`) |
| Q35 | **مدين على التاجر يزيد على رصيده** ("تحميل التاجر" §D19.2، "مستحقّ لـTAXO" §D18.6-C، تصحيح شروط الجهاز §D15.5): الدفتر يرفض السالب. يُحصر المدين في رصيده، أم يصير الباقي دَيناً على التاجر في جدول (كما فُعل للكبتن بـ`driver_debts`)؟ | `wallet_balance_non_negative` · `record` يرفع `insufficient_balance` | المرحلة 2 |
| Q36 | **قيد صرف التسوية**: نوع مدين جديد (`merchant_settlement`) أم `withdrawal` القائم؟ | ثوابت CLAUDE.md: "only drivers have a withdrawal path" | المرحلة 6 |
| ~~Q37~~ | **كُتبت الخريطة وعرض اللوحة والعطبان في §D6 (2026-09-19)**؛ ومعرّف المتجر فيها بحسب Q38 — نصّ السؤال كان: الخريطة (غرض ← دور) في `owner_type_for`: أيّ دور يملك أيّ محفظة — `customer` ← `customer`، `merchant` ← `merchant`، ومحفظة المندوب (`settlement_agent`) لا وجود لها؟ وما يعرضه باب اللوحة بلا إعلان لحساب يحمل أكثر من غرض | السطر 80 اليوم ثنائيّ؛ ولوحة المحافظ تنادي بلا إعلان في ثلاثة مواضع | **المرحلة 1** (ترحيلة القيم تُكتب معها) |
| ~~Q38~~ | **موقَّع 2026-09-19: الخيار (أ) — `merchant_id` على الدفتر وقيده وفهرسه (§D6)** — نصّ السؤال كان: مفتاح محفظة التاجر لمالك أكثر من نشاط: (أ) بُعد ثالث `merchant_id` على الدفتر، أم (ب) `owner_id = merchants.id`؟ — الجدول بالأرقام في §D6 | مفتاح اليوم `(owner_id, owner_type)` يعطي محفظة واحدة للشخص | **المرحلة 1** إن كُتبت ترحيلة `wallet_owner_type` فيها (البند 12)؛ وإلا فالمرحلة 2 |
| ~~Q39~~ | **موقَّع 2026-09-19: الخيار (ب) — `(phone, account_kind)` (§D1.4، §D6.1، والتنفيذ §D9.1)** — نصّ السؤال كان: §D1 #4 — حساب الزبون: (أ) دور `customer` على الحساب نفسه بمحفظة مستقلة، أم (ب) حساب منفصل بمفتاح `(phone, account_kind)`؟ — القياس في §D6.1، **ولا ترحيلة أدوار قبل التوقيع** | المالك يميل إلى (ب) | **المرحلة 1** (ترحيلة `user_role` و`wallet_owner_type` فيها) |
| ~~Q40~~ | **مقرَّر 2026-09-19: نوع ثالث `merchant` (§D1.5)** — نصّ السؤال كان: التاجر: نوع حساب ثالث (`account_kind = merchant`) أم دور `merchant` على حساب `taxo`؟** الأول يفصل كلمة مروره وحظره وتجميده وإشعاراته عن راكبه وكبتنه كالزبون؛ والثاني يُبقيها مشتركة (والتجميد بحسب الخطوة 6) | قيمة التعداد تُكتب في ترحيلة 1-أ | **1-أ** (قبل الترحيلة) |
| Q41 | **رموز الأجهزة وصندوق الإشعارات بين الراكب والكبتن** (حساب واحد بتطبيقين، بلا عمود تطبيق): يُفصلان في 1-أ أم بند مستقل؟ — للزبون لا يلزم بعد §D1 #4 | `models/device.py:38-39` · `user_notifications` بلا تطبيق | لا يعطّل 1-أ |
| ~~Q42~~ | **مقرَّر 2026-09-19: بالرقم ونوع الحساب (§D9.1 الموضع 10)** — نصّ السؤال كان: سقف محاولات الدخول `login:phone:{phone}`** (`routers/auth.py:369`): يبقى على الرقم (الشريحة واحدة، أحوط) أم لكل نوع؟ | حدود OTP تبقى على الرقم بقرار المالك | 1-أ (الخطوة 4) — وافتراض الخطة إبقاؤه على الرقم |
| ~~Q43~~ | **مقرَّر ٢٠٢٦-٠٩-٢٠: يُقبل الحدُّ مكتوباً اليوم، ويُغلق في المرحلة 5 قبل شاشة تسجيل الزبون — بالنوع في الإثبات وأحاديةِ الاستعمال معاً (§D7)** — نصّ السؤال كان: إثباتُ Firebase في ثغرة الرمز: يُربط بنوع الحساب أم يُقبل الحدُّ مكتوباً؟ | يُثبت الرقمَ ولا يُستهلك، **ولا حسابَ من نوعٍ آخرَ يوجد بعدُ ليُستولى عليه** | ~~الخطوة 5 من 1-أ~~ ⇐ **المرحلة 5** |
| Q44 | **`deactivation.py:128` بلا إعلان (§D6)**: يُصلح بإعلان `rider`؟ — **قِيس 2026-09-19**: `GET /account/deactivation` لحسابٍ **بدور الراكب ومنحةِ كبتنٍ بلا صفٍّ في `drivers`** يرتدّ **409 `wallet_owner_undecided`**؛ ولحسابٍ **له صفٌّ في `drivers` ومنحةُ راكب** يجيب **200** (`blockers: []`) — لأن القراءةَ لا تقع إلا حين `driver is None`. **والحالان كلاهما لا يبلغهما التطبيق اليوم**: لا بابَ يمنح دوراً ثانياً (`create_account` وحده يكتب منحةً، دوراً واحداً، ومعه صفُّ `drivers` للكبتن؛ ويحرسه `test_no_route_grants_a_role`) — **فكلُّ حسابٍ بدورين اليوم كُتب في القاعدة بيد**، وكذلك حالُ عطب الرحلات الذي أُصلح. — **ومقرَّرٌ ٢٠٢٦-٠٩-٢٠: يُترك مكتوباً ولا يُصلح الآن، وليس بنداً مستقلاً يُنسى، بل شرطٌ يسبق بناءَ مسار منح الدور الثاني (البند ٥ في ترتيب المالك)، وإصلاحُه المقترح بسطره في §D6** | ثالثُ مسارٍ بالعطب نفسِه، **ثابتٌ بالقياس في الحال (أ) وحدها** | لا يعطّل 1-أ |
| Q33 | **زرّ "سدّد من محفظتي"** (شرط إشعال قاعدة اليوم التالي، §D18.1): متى يُبنى — مع المرحلة 2، أم مع المرحلة 6، أم بند مستقل قبل الإطلاق؟ | غير موجود في الشجرة | لا يعطّل المرحلة 1 |

---

## §D12 ملاحظات للوكيل

- كل اسم جدول أو وحدة أو حارس مذكور هنا يُثبَت من الشجرة قبل الاستعمال؛ ما لا يطابق يُصحَّح في هذا الملف لا في الكود.
- لا يُكرَّر ما هو مبنيّ: المحافظ والدفتر، الرفع والضغط، الوثائق وعارضها، الإسناد، الإشعارات، provider_orders، إعدادات الدولة، التدقيق، عقد الأخطاء، حارس المال.
- قبل أي عمود أو إعداد أو إعلان جديد: هل يعرف الصفّ الجواب فعلاً؟ (§22.0). ما عرفه الصفّ يُشتقّ.
- قرار لم يُتَّخذ يُكتب سؤالاً في §D11 ولا يُخمَّن صامتاً؛ وأمرٌ يكرّر عملاً منجَزاً يوقف الوكيل ويسأل.
- كل مرحلة: اختباراتها خضراء، إيداع، وسم بصيغة الوسوم القائمة، ثم يقف للمراجعة؛ الدفع إلى الريموت بقرار المالك.
- لا يُشغَّل قياس مع بناء متزامن، ولا يُودَع على شجرة غير التي ستُودَع.

---

## §D20 كل اسم في هذا الملف لا وجود له في الشجرة (المرحلة 0، 2026-09-19)

**الطريقة**: استُخرج كل اسم بين علامتي `` ` `` في الملف (600 مقطع)، وبُحث عن كل معرّف فيه بكلمة كاملة (`git grep -w`) في `backend/app` و`backend/tests` و`backend/alembic` والتطبيقات الثلاثة (`src` و`android`) و`tools` و`scripts` و`whatsapp-gateway` و`channels.json` و`design`. **152 معرّفاً بلا أيّ نتيجة**، صُنّفت يدوياً هنا. **وحدّ الطريقة مكتوب**: معرّف يوجد في الشجرة **بمعنى آخر** (كـ`ends_at` في `models/storefront.py`) لا يلتقطه البحث، وقد صُحّح ما عُرف منه يدوياً (§D2: `merchant_subscriptions`).

### أ) يُبنى — أسماء جديدة مقصودة

- **جداول**: `merchants` · `merchant_documents` · `branches` · `menu_categories` · `menu_items` · `branch_item_availability` · `item_option_groups` · `item_options` · `merchant_subscription_plans` · `merchant_subscriptions` · `merchant_devices` · `merchant_settlements` · `delivery_orders` · `delivery_order_items` · `delivery_order_events` · `delivery_assignments` · `customer_addresses` · `delivery_order_ratings` · `delivery_order_disputes` · `delivery_settings` · `driver_debt_payments`.
- **أعمدة على `drivers`**: `delivery_mode` · `delivery_mode_since` · `delivery_exception_enabled` · `max_concurrent_orders` · `cash_exposure_cap_override` · `cash_on_hand_limit`. **وعلى `driver_debts`**: `delivery_order_id`.
- **أعمدة الجداول الجديدة** (كما في §D2 و§D15.5 و§D18): `owned_by_taxo` · `public_phone` · `commission_percent_override` · `free_until` · `min_order_amount` · `settlement_cycle` · `base_price` · `available_from`/`available_to` · `min_select`/`max_select` · `price_delta` · `commission_percent_at_order` · `commission_amount` · `merchant_net` · `delivery_fee` · `service_fee` · `unit_price` · `line_total` · `delivery_code` · `expected_ready_at` · `printed_at` · `print_attempts` · `drop_at_door` · `exposure_at_offer` · `recorded_by` · `deposit_amount` · `monthly_fee` · `min_term_months` · `terms_note` · `branch_id` · `actor_type`.
- **مفاتيح `delivery_settings`**: `billing_mode` (وقيمه `commission_only` · `subscription_only` …) · `merchant_commission_percent` · `next_commission_percent` · `next_commission_effective_from` · `service_fee_fixed` · `service_fee_percent` · `service_fee_max` · `billing_change_notice_days` · `delivery_base_fee` · `delivery_per_km` · `delivery_min_fee` · `delivery_max_fee` · `delivery_max_distance_km` · `delivery_dispatch_radius_km` · `delivery_radius_km` (على الفرع) · `merchant_accept_timeout_sec` · `ready_unassigned_alert_min` · `driver_cash_exposure_cap_default` · `merchant_subscription_grace_days` · `delivery_exception_default` · `customer_cash_block_after_undeliverable` · `dispute_decision_hours` · و`delivery_enabled` (عمود — Q23 مقرَّر).
- **قيم تعداد**: `customer` · `merchant` · `settlement_agent` (`user_role`) · `merchant_subscription` (`provider_order_purpose`) · `store_commission` · `goods_price` (و`service_fee` مصدراً، `driver_debt_source`) · `delivery_order_payment` · `delivery_earning` · `delivery_compensation` (`wallet_transaction_type`) · `market`/`merchant` (`ClientApp`) · حالات الطلب `picked_up` · `pending_review` وأخواتها.
- **وحدة ومسارات**: `services/delivery_orders.py` · المسارات تحت `/delivery`.
- **رموز أخطاء** (§D7): `invalid_order_transition` · `merchant_not_active` · `merchant_subscription_expired` · `driver_subscription_required` · `branch_closed` · `item_unavailable` · `option_selection_invalid` · `below_min_order_amount` · `out_of_delivery_radius` · `customer_cash_blocked` · `delivery_disabled_in_country` · `order_report_window_closed` · `pickup_not_available` · `drop_at_door_not_allowed` · `driver_not_in_delivery_mode` · `driver_has_active_order` · `cash_cap_exceeded` · `concurrent_orders_limit` · `delivery_offer_expired` · `delivery_code_invalid` · `delivery_code_locked` · `merchant_accept_timeout` · `undeliverable_photo_required` · `device_provisioning_code_invalid` · `device_revoked` · `device_not_assigned` · `print_ack_not_applicable` · `dispute_option_not_applicable` · `dispute_reason_required` · `order_not_in_review` · `settlement_not_pending`.
- **كود أصلي**: `FirebaseMessagingService` و`MESSAGING_EVENT` في TAXO MERCHANT (§D15.0).
- **حارس**: `check:transitions`.
- **قيم مشتقّة لا تُخزَّن**: `is_open_now` · `cash_exposure_cap`.
- **مقرَّر بعد المرحلة 0 (الجولة الثانية)**: `merchant_document_types` (Q8) · `next_service_fee_fixed` · `next_service_fee_percent` · `next_service_fee_max` · `next_service_fee_effective_from` · `next_billing_mode` · `next_billing_mode_effective_from` (Q26).
- **مقرَّر (Q38)**: `wallet_transactions.merchant_id` وقيده `(owner_type = 'merchant') = (merchant_id IS NOT NULL)` وفهرسه.
- **مقرَّر بعد المرحلة 0**: `merchant_plan_id` وقيده `provider_order_merchant_plan_matches_purpose` (Q24) · عمود `wallet_transactions.delivery_order_id` (Q20) · `delivery_enabled` عموداً (Q23).
- **مقترحات معلَّقة بأسئلة** (لا تُبنى قبل الجواب): `agent_cash` (Q30) · `merchant_settlement` نوع قيد (Q36).
- **مستقبلي مسجَّل لا يُبنى الآن**: `cash_variance` (§D18.4).
- **اسم عرض لا معرّف**: `TaxoEat`.

### ب) خطأ في الملف — كان في 0.1، **وصُحِّح في مواضعه**، ويبقى ذكره تاريخياً فقط

| الاسم في 0.1 | ما في الشجرة / ما حلّ محلّه |
|---|---|
| `wallet_insufficient` (402) | `insufficient_balance` (409) |
| `invalid_transition` | عائلة `invalid_*_transition` ⇒ `invalid_order_transition` |
| `order_not_owned` (403) | `not_found` (404) على نسق الرحلات |
| `order_hold` · `order_capture` · `order_release` | لا حجز — `delivery_order_payment` ثم `refund` |
| `order_refund` | `refund` القائم |
| `merchant_commission_collected` · `service_fee_collected` | صفوف `driver_debts` بمصدرَي `store_commission` / `service_fee` |
| `undeliverable_reimbursement` | `delivery_compensation` بقرار §D19 |
| `price_at_purchase` · `ends_at` · `provider_order_id` (على الاشتراك) | `amount_paid` · `expires_at` · الربط عبر `provider_orders.plan_id` |
| `merchant_plan_prices` | صفوف `merchant_subscription_plans` |
| `subject_type` (على جدول الوثائق) | غير موجود — `driver_documents` خاصّ بالكبتن |
| `uploads` · `*_upload_id` | غير موجود — مسارات `*_path` على الصفّ |
| `orders` · `order_items` · `order_events` · `order_ratings` | `delivery_orders` وأخواتها (قرار التسمية) |
| `delivery_commission_percent` | لا يُعلَن (§D1 #2) — ولا وجود له |
| `admin_override` (في صيغة سقف النقد) | `drivers.cash_exposure_cap_override` |
| `SPEC-RIDES-EXT` (§D14.ب-3) | **غير موجود في المستودع**، ولا رحلات بين المدن مبنيّة |
| "`computed` من المستوى والتاريخ" (سقف السلفة) | `advances.cap_for`: سعر الخطة اليومية × مضاعف السداد |
| `cancellation_carry` عدّاداً للإلغاء (§D17.5-B) | `cancellation_carry_blocked` حجبٌ لرسم إلغاء محمول، لا عدّاد |
| "فلتر واحد في الإسناد" | حلقة ثانية + شرط حصرية (§D1.3) |
| "بوابة واتساب تُرسل تقريراً" | ترسل رمز التحقق وحده (§D14.أ-7) |
| "هذا التطبيق وحده فيه كود أصلي" | driver-app فيه كود أصلي قائم (§D15.0) |
| "المحفظة بنك تسمح بالسالب" | `wallet_balance_non_negative` |
| وسوم `delivery-spec-reviewed` وأخواتها | صيغة `vX.Y.Z` |
