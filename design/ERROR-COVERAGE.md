# جدولُ تغطية الأخطاء — كلُّ شاشةٍ وكلُّ مسار

> **مولَّدٌ من الشيفرة لا مكتوبٌ باليد** (`scratchpad/map_errors.py`)، ويُعاد توليدُه بعد أي
> تغييرٍ في المسارات أو أصناف الخطأ. والعقدُ نفسُه في `SPEC.md` القسم ١٧.

## المنهج، وحدودُه معلَنة

الأخطاءُ لكل مسار **مُستخرَجةٌ من الشجرة النحوية**: يُمشى من معالِج المسار إلى ما يستدعيه
(بعمق ٣)، ويُحلّ كلُّ نداءٍ **عبر استيرادات ملفه** — `alias.func()` إلى الوحدة التي استوردها
ذلك الملفُّ بذلك الاسم، والنداءُ المجرّدُ داخل وحدته وحدَها.

**وأولُ نسخةٍ من هذا المولِّد كانت تكذب**، والدرسُ يُكتب لا يُخفى: كانت تربط النداءَ بالاسم
وحدَه، فاصطدم `get` و`create` و`record` عبر عشرات الوحدات، فنُسب إلى `GET /config` خطأُ
«إثباتِ رمز الاسترداد». **وجدولٌ فيه أسطرٌ كاذبةٌ أسوأُ من لا جدول**: يُقرأ مرةً فيُكتشف
كذبُه فيُهمل كلُّه — وهي قاعدةُ الحرّاس في هذا المشروع نفسِها.

**وما لا يُحلّ لا يُخمَّن**: نداءٌ عبر كائنٍ أو دالةٍ تُمرَّر متغيّراً لا يظهر هنا، ويبقى
محكوماً بالأخطاء العامة أدناه. فاقرأ الجدولَ «هذه الأخطاءُ ممكنةٌ قطعاً»، لا «وهذه وحدَها».

## الأخطاء العامة — تسري على كل مسار، فلا تُكرَّر ٢١٨ مرة

| الرمز | الحالة | الرسالة العربية | متى | الحالة قبل |
|---|---|---|---|---|
| `validation_error` | ٤٢٢ | من السجل المركزي بحسب الحقل | جسمٌ يخالف المخطط | **`[object Object]` ولا سطرَ في السجل** — لا معالجَ أصلاً |
| `invalid_token` | ٤٠١ | جلسة غير صالحة أو منتهية | توكنٌ منتهٍ أو مزوَّر | ✅ كانت تُعرض |
| `permission_denied` | ٤٠٣ | لا تملك صلاحية هذا الإجراء | دورٌ لا يملك المسار | ✅ |
| `not_found` | ٤٠٤ | غير موجود | مسارٌ غيرُ موجود | **`Not Found` بالإنجليزية** |
| `method_not_allowed` | ٤٠٥ | طلبٌ غير مدعوم | طريقةٌ خاطئة | **إنجليزية** |
| `rate_limited` | ٤٢٩ | محاولات كثيرة — حاول لاحقاً | تجاوزُ سقف | ✅ (ومعها `Retry-After`) |
| `server_error` | ٥٠٠ | خطأٌ في الخادم — أعد المحاولة | استثناءٌ غيرُ متوقَّع | **إنجليزية** |
| `network_offline` | — | لا اتصال بالإنترنت — تحقّق من شبكتك ثم أعد المحاولة | الجهازُ بلا شبكة | **رسالةٌ واحدةٌ للأربع** |
| `network_timeout` | — | الخادم لا يستجيب — انتهت المهلة. أعد المحاولة | تجاوزُ مهلةِ الصنف | **لم تكن موجودة** |
| `network_unreachable` | — | تعذّر الوصول إلى الخادم — أعد المحاولة بعد قليل | الشبكةُ قائمةٌ والخادمُ لا يُبلَغ | **رسالةٌ واحدةٌ للأربع** |
| `network_unexpected` | — | ردٌّ غير متوقَّع من الخادم — أعد المحاولة | ردٌّ وصل ولم يُقرأ | **لم تكن موجودة** |

## أصنافُ الخطأ في السجل المركزي (93)

| الرمز | الحالة | الرسالة العربية |
|---|---|---|
| `account_blocked` | 403 | هذا الحساب محظور |
| `account_not_registered` | 404 | لا يوجد حساب بهذا الرقم — أنشئ حساباً أولاً |
| `advance_not_allowed` | 409 | لا تنطبق عليك شروط السلفة |
| `advance_unavailable` | 409 | السلف غير متاحة الآن |
| `already_rated` | 409 | سبق أن قيّمت هذه الرحلة |
| `backup_already_running` | 409 | نسخةٌ احتياطيةٌ قيد الأخذ الآن |
| `badge_already_granted` | 409 | الشارة ممنوحةٌ لهذا الكبتن |
| `badge_not_found` | 404 | الشارة غير موجودة |
| `booking_not_allowed` | 409 | لا يمكن تنفيذ هذا الطلب على الحجز |
| `cancel_reason_not_applicable` | 409 | سبب الإلغاء لا ينطبق على هذه الرحلة |
| `cancellation_charge_not_open` | 409 | هذا الرسم لم يعد معلّقاً |
| `cancellation_debt_blocked` | 402 | عليك رسومُ إلغاءٍ غيرُ مسدَّدة — اشحن محفظتك ليُخصم المستحق ثم أعد الطلب |
| `card_gateway_error` | 502 | تعذّر إتمام العملية عند مزود الدفع |
| `card_gateway_unavailable` | 503 | الدفع بالبطاقة غير متاح الآن — اختر طريقة دفع أخرى. |
| `cliq_acquirer_error` | 502 | تعذّر إتمام العملية عند مزود كليك |
| `cliq_acquirer_unavailable` | 503 | الشحن عبر كليك غير متاح الآن — جرّب طريقة أخرى. |
| `conflict` | 409 | تعارض في البيانات |
| `credentials_encryption_unavailable` | 500 | مفتاح تشفير بيانات المزودين غير مضبوط |
| `deactivation_blocked` | 409 | لا يمكن إلغاء التفعيل الآن |
| `document_file_missing` | 404 | تعذّر العثور على ملف المستند |
| `document_too_large` | 413 | حجم الملف أكبر من المسموح |
| `documents_incomplete` | 409 | لا يُعتمد الكبتن قبل اعتماد مستنداته المطلوبة |
| `feature_disabled` | 403 | هذه الميزة غير مفعّلة في بلدك |
| `feature_not_available` | 501 | هذه الميزة غير مفعّلة بعد |
| `firebase_auth_unavailable` | 503 | التحقق من رقم هاتفك غير متاح حالياً. حاول بعد قليل. |
| `insufficient_balance` | 409 | الرصيد غير كافٍ |
| `invalid_credentials` | 401 | رقم الهاتف أو كلمة المرور غير صحيحة |
| `invalid_id_token` | 401 | رمز التحقق غير صالح أو انتهت صلاحيته |
| `invalid_input` | 422 | بيانات غير صالحة |
| `invalid_otp` | 401 | رمز التحقق غير صحيح أو انتهت صلاحيته |
| `invalid_payment_transition` | 409 | لا يمكن تنفيذ هذا الإجراء على حالة الدفعة الحالية |
| `invalid_ride_transition` | 409 | لا يمكن تنفيذ هذا الإجراء على حالة الرحلة الحالية |
| `invalid_status_transition` | 409 | لا يمكن تنفيذ هذا الإجراء على حالة الطلب الحالية |
| `invalid_token` | 401 | جلسة غير صالحة أو منتهية |
| `invalid_totp` | 401 | رمز التحقق الثنائي غير صحيح أو انتهت صلاحيته |
| `invalid_webhook_signature` | 400 | توقيع إشعار الدفع غير صالح |
| `mission_exists` | 409 | لهذا المعيار مهمةٌ في هذا الشهر |
| `mission_not_found` | 404 | المهمة غير موجودة |
| `multi_stop_unavailable` | 409 | تعدد الوجهات غير مفعّل في هذه الدولة |
| `no_open_pause` | 404 | لا توجد وقفةٌ مفتوحة |
| `not_found` | 404 | العنصر غير موجود |
| `pause_already_open` | 409 | ثمّة وقفةٌ مفتوحةٌ بالفعل |
| `payout_failed` | 502 | تعذّر تنفيذ التحويل عند المزود |
| `payout_unavailable` | 503 | التحويل الآلي غير مهيأ — راجع عقد payout في لوحة الإدارة |
| `permission_denied` | 403 | لا تملك صلاحية هذا الإجراء |
| `phone_already_registered` | 409 | رقم الهاتف مسجّل مسبقاً |
| `phone_not_verified` | 403 | يجب إثبات ملكية رقم الهاتف أولاً |
| `pricing_rule_missing` | 409 | لا توجد تسعيرة معتمدة لهذه الفئة في بلدك |
| `promo_already_used` | 409 | استعملتَ هذا العرض سابقاً |
| `promo_exhausted` | 404 | انتهت صلاحية هذا العرض |
| `promo_invalid` | 404 | رمز الخصم غير صالح |
| `promo_unavailable` | 403 | الكوبونات غير مفعّلة في بلدك |
| `push_failed` | 502 | تعذّر إرسال الإشعار |
| `push_unavailable` | 503 | خدمة الإشعارات غير مهيأة — راجع عقد FCM في لوحة الإدارة |
| `rate_limited` | 429 | محاولات كثيرة — حاول لاحقاً |
| `rating_not_allowed` | 409 | لا يمكن تقييم هذه الرحلة |
| `referral_code_unknown` | 404 | رمز الإحالة غير صحيح |
| `referral_not_allowed` | 409 | لا يمكن استخدام رمز الإحالة |
| `ride_already_active` | 409 | لديك رحلة جارية بالفعل |
| `ride_already_paid` | 409 | هذه الرحلة لها دفعة قائمة تغطي قيمتها |
| `ride_not_payable` | 409 | لا يمكن الدفع قبل اكتمال الرحلة |
| `ride_offer_expired` | 409 | انتهت مهلة هذا الطلب أو عُرض على كبتن آخر |
| `ride_sharing_gender_choice_required` | 422 | طلبك يحدّد جنس الكبتن — المشاركة فيه اختيارٌ منفصل تختارينه بنفسك |
| `ride_sharing_unavailable` | 422 | مشاركة الرحلة غير متاحة في بلدك الآن |
| `routing_failed` | 502 | تعذّر حساب المسار بين النقطتين |
| `routing_unavailable` | 503 | تعذّر حساب المسار الآن. حاول بعد قليل. |
| `scheduled_rides_unavailable` | 403 | الرحلات المجدولة غير مفعّلة في بلدك |
| `share_group_unavailable` | 409 | لم تعد هذه الرحلة قابلة للمشاركة |
| `sms_send_failed` | 502 | تعذّر إرسال الرسالة القصيرة |
| `sms_unavailable` | 503 | تعذّر إرسال رمز التحقق الآن. حاول بعد قليل. |
| `subscription_already_purchased` | 409 | هذه العملية نُفّذت بالفعل |
| `tip_already_given` | 409 | سبق أن أضفت بقشيشاً لهذه الرحلة |
| `tip_not_allowed` | 409 | لا يمكن إضافة بقشيش لهذه الرحلة |
| `tips_unavailable` | 403 | البقشيش غير مفعّل في بلدك |
| `totp_already_enrolled` | 409 | للحساب تحققٌ ثنائيٌّ مسجّل — أطفئه أولاً |
| `totp_enforcement_active` | 409 | لا يمكن إطفاء التحقق الثنائي وهو مُلزَمٌ على دورك |
| `totp_enrollment_required` | 403 | الدخول إلى اللوحة يستلزم تسجيل التحقق الثنائي أولاً |
| `totp_not_enrolled` | 409 | لا يوجد تحقق ثنائي مسجّل على هذا الحساب |
| `totp_recovery_proof_required` | 409 | أثبت أن رمز الاسترداد يعمل قبل إلزام الجميع بالتحقق الثنائي |
| `unsupported_document` | 422 | نوع الملف غير مدعوم — الصور (JPEG/PNG/WebP) وملفات PDF فقط |
| `verification_channel_unavailable` | 400 | قناة التحقق المطلوبة غير متاحة لهذا الرقم |
| `verification_send_failed` | 502 | تعذّر إرسال رمز التحقق |
| `verification_unavailable` | 503 | التحقق من رقم هاتفك غير متاح حالياً. حاول بعد قليل. |
| `wallet_frozen` | 403 | المحفظة مجمّدة — راجع الدعم |
| `wallet_limit_exceeded` | 409 | تجاوزت الحد المسموح |
| `weak_password` | 422 | كلمة المرور ضعيفة — اختر غيرها |
| `whatsapp_send_failed` | 502 | تعذّر إرسال رمز واتساب |
| `whatsapp_unavailable` | 503 | تعذّر إرسال الرمز عبر واتساب الآن. جرّب طريقة أخرى. |
| `women_service_unavailable` | 409 | خدمة التوصيل النسائي غير مفعّلة في هذه الدولة |

## المسارات (218)

«الأخطاء الخاصة» = ما يُضاف إلى الأخطاء العامة أعلاه. و«—» تعني: لا خطأَ خاصّاً وُجد،
فالمسارُ محكومٌ بالعامة وحدَها.

### `admin_backups`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/backups` | GET | — |
| `/admin/backups/download/{token}` | GET | `not_found` 404 |
| `/admin/backups/run` | POST | `backup_already_running` 409 · `invalid_input` 422 |
| `/admin/backups/settings` | PUT | `invalid_input` 422 |
| `/admin/backups/{name}/download-token` | POST | `not_found` 404 · `permission_denied` 403 |
| `/admin/campaigns/settings/{country_code}` | PUT | `invalid_input` 422 |
| `/admin/referrals/settings` | PUT | `invalid_input` 422 |
| `/admin/sharing/settings` | PUT | `invalid_input` 422 |

### `admin_campaigns`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/campaigns` | GET | — |
| `/admin/campaigns` | POST | `feature_not_available` 501 · `invalid_input` 422 |
| `/admin/campaigns/settings/{country_code}` | GET | — |
| `/admin/campaigns/test-push` | POST | `credentials_encryption_unavailable` 500 · `push_unavailable` 503 |
| `/admin/campaigns/{campaign_id}` | PATCH | `conflict` 409 · `feature_not_available` 501 · `invalid_input` 422 · `not_found` 404 |
| `/admin/campaigns/{campaign_id}/cancel` | POST | `conflict` 409 · `not_found` 404 |
| `/admin/campaigns/{campaign_id}/deliveries` | GET | — |

### `admin_cancellations`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/cancellation-charges` | GET | — |
| `/admin/cancellation-charges/{charge_id}/waive` | POST | `cancellation_charge_not_open` 409 · `invalid_input` 422 · `not_found` 404 |
| `/admin/cancellation-charges/{charge_id}/write-off` | POST | `cancellation_charge_not_open` 409 · `invalid_input` 422 · `not_found` 404 |

### `admin_live_map`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/live/map` | GET | — |

### `admin_missions`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/badges` | GET | — |
| `/admin/badges` | POST | `conflict` 409 |
| `/admin/drivers/{driver_id}/badges` | GET | — |
| `/admin/drivers/{driver_id}/badges` | POST | `badge_already_granted` 409 · `badge_not_found` 404 · `invalid_input` 422 · `not_found` 404 |
| `/admin/drivers/{driver_id}/badges/{badge_id}/revoke` | POST | `badge_not_found` 404 · `invalid_input` 422 |
| `/admin/levels` | GET | — |
| `/admin/levels/{level}` | PUT | `invalid_input` 422 |
| `/admin/missions` | GET | — |
| `/admin/missions` | POST | `invalid_input` 422 · `mission_exists` 409 |
| `/admin/missions/{mission_id}` | PATCH | `invalid_input` 422 · `mission_not_found` 404 |

### `admin_payments`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/payments` | GET | — |
| `/admin/payments/{payment_id}/refund` | POST | `card_gateway_unavailable` 503 · `insufficient_balance` 409 · `invalid_input` 422 · `invalid_payment_transition` 409 · `not_found` 404 · `permission_denied` 403 |
| `/admin/payments/{payment_id}/resolve` | POST | `insufficient_balance` 409 · `invalid_payment_transition` 409 · `not_found` 404 |

### `admin_promo`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/promo-codes` | GET | — |
| `/admin/promo-codes` | POST | `conflict` 409 |
| `/admin/promo-codes/{promo_id}` | DELETE | `conflict` 409 · `not_found` 404 |
| `/admin/promo-codes/{promo_id}` | PATCH | `not_found` 404 |

### `admin_providers`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/providers` | GET | `credentials_encryption_unavailable` 500 |
| `/admin/providers/whatsapp/session` | GET | `whatsapp_unavailable` 503 |
| `/admin/providers/whatsapp/session/logout` | POST | `whatsapp_unavailable` 503 |
| `/admin/providers/{credential_id}` | DELETE | `not_found` 404 |
| `/admin/providers/{credential_id}/activate` | POST | `credentials_encryption_unavailable` 500 · `not_found` 404 |
| `/admin/providers/{credential_id}/deactivate` | POST | `credentials_encryption_unavailable` 500 · `not_found` 404 |
| `/admin/providers/{credential_id}/test` | POST | `credentials_encryption_unavailable` 500 · `not_found` 404 |
| `/admin/providers/{provider_key}` | PUT | `conflict` 409 · `credentials_encryption_unavailable` 500 · `invalid_input` 422 |

### `admin_referrals`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/referrals` | GET | — |
| `/admin/referrals/settings` | GET | `invalid_input` 422 |
| `/admin/referrals/summary` | GET | — |
| `/admin/sharing/settings` | GET | `invalid_input` 422 |

### `admin_rides`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/rides` | GET | — |
| `/admin/rides/{ride_id}` | GET | `not_found` 404 |
| `/rides/{ride_id}` | GET | `not_found` 404 |

### `admin_security`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/security` | GET | — |
| `/admin/security` | PUT | `invalid_input` 422 · `totp_recovery_proof_required` 409 |

### `admin_settings`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/settings/advances` | GET | — |
| `/admin/settings/advances/{country_code}` | PATCH | `conflict` 409 |
| `/admin/settings/audit-logs` | GET | — |
| `/admin/settings/cancellation` | GET | — |
| `/admin/settings/cancellation/{country_code}` | PATCH | `conflict` 409 |
| `/admin/settings/commission` | GET | — |
| `/admin/settings/commission/{country_code}` | PATCH | `conflict` 409 |
| `/admin/settings/feature-flags` | GET | — |
| `/admin/settings/feature-flags` | PUT | `conflict` 409 · `invalid_input` 422 |
| `/admin/settings/otp` | GET | — |
| `/admin/settings/otp/exhausted` | GET | — |
| `/admin/settings/otp/{country_code}` | PATCH | `conflict` 409 |
| `/admin/settings/payments` | GET | — |
| `/admin/settings/payments/{country_code}` | PATCH | `conflict` 409 |
| `/admin/settings/pricing` | GET | — |
| `/admin/settings/pricing` | POST | `conflict` 409 |
| `/admin/settings/pricing/{rule_id}` | DELETE | `conflict` 409 · `not_found` 404 |
| `/admin/settings/pricing/{rule_id}` | PATCH | `conflict` 409 · `not_found` 404 |
| `/admin/settings/subscription-plans` | GET | — |
| `/admin/settings/subscription-plans` | POST | `conflict` 409 |
| `/admin/settings/subscription-plans/{plan_id}` | DELETE | `conflict` 409 · `not_found` 404 |
| `/admin/settings/subscription-plans/{plan_id}` | PATCH | `conflict` 409 · `not_found` 404 |
| `/admin/settings/wallet` | GET | — |
| `/admin/settings/wallet/{country_code}` | PATCH | `conflict` 409 |

### `admin_stats`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/stats/overview` | GET | — |
| `/admin/stats/reports` | GET | — |

### `admin_subscriptions`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/subscriptions` | GET | — |
| `/admin/subscriptions` | POST | `conflict` 409 · `invalid_input` 422 · `not_found` 404 · `permission_denied` 403 · `subscription_already_purchased` 409 |

### `admin_users`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/drivers` | GET | — |
| `/admin/drivers/advances` | GET | — |
| `/admin/drivers/advances` | POST | `advance_not_allowed` 409 · `advance_unavailable` 409 · `insufficient_balance` 409 · `invalid_input` 422 · `not_found` 404 · `permission_denied` 403 |
| `/admin/drivers/advances/{advance_id}/writeoff` | PATCH | `advance_not_allowed` 409 · `not_found` 404 |
| `/admin/drivers/deactivations` | GET | — |
| `/admin/drivers/deactivations/{request_id}` | PATCH | `deactivation_blocked` 409 · `invalid_input` 422 · `not_found` 404 |
| `/admin/drivers/{driver_id}/activate` | POST | `documents_incomplete` 409 · `invalid_input` 422 · `not_found` 404 · `phone_not_verified` 403 |
| `/admin/drivers/{driver_id}/advance-cap` | PUT | `not_found` 404 |
| `/admin/drivers/{driver_id}/approve` | POST | `documents_incomplete` 409 · `not_found` 404 · `phone_not_verified` 403 |
| `/admin/drivers/{driver_id}/documents` | GET | `not_found` 404 |
| `/admin/drivers/{driver_id}/documents/{document_id}/file` | GET | `document_file_missing` 404 · `not_found` 404 |
| `/admin/drivers/{driver_id}/documents/{document_id}/review` | POST | `conflict` 409 · `not_found` 404 |
| `/admin/drivers/{driver_id}/gender` | PUT | `invalid_input` 422 · `not_found` 404 |
| `/admin/drivers/{driver_id}/reject` | POST | `not_found` 404 |
| `/admin/drivers/{driver_id}/suspend` | POST | `invalid_input` 422 · `not_found` 404 |
| `/admin/users` | GET | — |
| `/admin/users/{user_id}/block` | POST | `invalid_input` 422 · `not_found` 404 |
| `/admin/users/{user_id}/unblock` | POST | `invalid_input` 422 · `not_found` 404 |

### `admin_wallets`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/admin/topups` | GET | — |
| `/admin/topups/{request_id}/confirm` | POST | `insufficient_balance` 409 · `invalid_input` 422 · `invalid_status_transition` 409 · `not_found` 404 · `permission_denied` 403 · `wallet_frozen` 403 |
| `/admin/topups/{request_id}/reject` | POST | `invalid_status_transition` 409 · `not_found` 404 |
| `/admin/wallets/{user_id}` | GET | `not_found` 404 · `permission_denied` 403 |
| `/admin/wallets/{user_id}/adjustments` | POST | `insufficient_balance` 409 · `invalid_input` 422 · `not_found` 404 · `permission_denied` 403 |
| `/admin/wallets/{user_id}/freeze` | POST | `not_found` 404 · `permission_denied` 403 |
| `/admin/wallets/{user_id}/topups` | POST | `feature_disabled` 403 · `insufficient_balance` 409 · `invalid_input` 422 · `invalid_status_transition` 409 · `not_found` 404 · `permission_denied` 403 · `wallet_frozen` 403 |
| `/admin/wallets/{user_id}/transactions` | GET | `not_found` 404 · `permission_denied` 403 |
| `/admin/wallets/{user_id}/unfreeze` | POST | `not_found` 404 · `permission_denied` 403 |
| `/admin/withdrawals` | GET | — |
| `/admin/withdrawals/{request_id}/approve` | POST | `invalid_status_transition` 409 · `not_found` 404 |
| `/admin/withdrawals/{request_id}/paid` | POST | `insufficient_balance` 409 · `invalid_input` 422 · `invalid_status_transition` 409 · `not_found` 404 · `permission_denied` 403 |
| `/admin/withdrawals/{request_id}/payout` | POST | `insufficient_balance` 409 · `invalid_input` 422 · `invalid_status_transition` 409 · `not_found` 404 · `payout_failed` 502 · `payout_unavailable` 503 |
| `/admin/withdrawals/{request_id}/reject` | POST | `invalid_status_transition` 409 · `not_found` 404 |

### `auth`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/auth/challenge` | POST | `verification_channel_unavailable` 400 · `invalid_input` 422 · `rate_limited` 429 · `sms_unavailable` 503 · `verification_send_failed` 502 · `whatsapp_unavailable` 503 |
| `/auth/login` | POST | `account_blocked` 403 · `invalid_credentials` 401 · `invalid_input` 422 · `rate_limited` 429 · `wrong_app_for_role` 403 |
| `/auth/login/totp` | POST | `credentials_encryption_unavailable` 500 · `invalid_input` 422 · `invalid_token` 401 · `invalid_totp` 401 · `rate_limited` 429 · `totp_not_enrolled` 409 · `wrong_app_for_role` 403 |
| `/auth/logout` | POST | — |
| `/auth/me` | GET | — |
| `/auth/me` | PATCH | `invalid_input` 422 |
| `/auth/me/totp` | DELETE | `invalid_input` 422 · `invalid_totp` 401 · `totp_enforcement_active` 409 · `totp_not_enrolled` 409 |
| `/auth/me/totp` | GET | — |
| `/auth/me/totp/confirm` | POST | `credentials_encryption_unavailable` 500 · `invalid_totp` 401 · `totp_already_enrolled` 409 · `totp_not_enrolled` 409 |
| `/auth/me/totp/enroll` | POST | `credentials_encryption_unavailable` 500 · `totp_already_enrolled` 409 |
| `/auth/me/totp/recovery/verify` | POST | `invalid_totp` 401 · `totp_not_enrolled` 409 |
| `/auth/me/verify-phone` | POST | `firebase_auth_unavailable` 503 · `invalid_id_token` 401 · `invalid_otp` 401 · `rate_limited` 429 · `verification_unavailable` 503 |
| `/auth/method` | GET | — |
| `/auth/password-reset` | POST | `firebase_auth_unavailable` 503 · `invalid_id_token` 401 · `invalid_input` 422 · `invalid_otp` 401 · `not_found` 404 · `weak_password` 422 · `weak_password` 422 · `weak_password` 422 · `rate_limited` 429 · `verification_unavailable` 503 |
| `/auth/password-reset/challenge` | POST | `verification_channel_unavailable` 400 · `invalid_input` 422 · `rate_limited` 429 · `sms_unavailable` 503 · `verification_send_failed` 502 · `whatsapp_unavailable` 503 |
| `/auth/refresh` | POST | `invalid_token` 401 |
| `/auth/register` | POST | `firebase_auth_unavailable` 503 · `invalid_id_token` 401 · `invalid_input` 422 · `invalid_otp` 401 · `weak_password` 422 · `weak_password` 422 · `weak_password` 422 · `phone_already_registered` 409 · `rate_limited` 429 · `referral_code_unknown` 404 · `referral_not_allowed` 409 · `verification_unavailable` 503 · `wrong_app_for_role` 403 |

### `bookings`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/me/bookings` | GET | — |
| `/me/bookings` | POST | `booking_not_allowed` 409 · `scheduled_rides_unavailable` 403 · `invalid_input` 422 · `pricing_rule_missing` 409 · `routing_unavailable` 503 · `women_service_unavailable` 409 |
| `/me/bookings/{booking_id}` | DELETE | `booking_not_allowed` 409 · `not_found` 404 |

### `card_payments`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/payments/card/mock/{cart_id}` | POST | `card_gateway_unavailable` 503 · `feature_not_available` 501 · `not_found` 404 · `permission_denied` 403 |
| `/payments/card/orders/{cart_id}` | GET | `card_gateway_unavailable` 503 · `not_found` 404 |
| `/payments/card/webhook` | POST | `card_gateway_unavailable` 503 · `credentials_encryption_unavailable` 500 · `invalid_webhook_signature` 400 · `not_found` 404 · `rate_limited` 429 |
| `/payments/cards` | GET | — |
| `/payments/cards/{card_id}` | DELETE | `not_found` 404 |
| `/payments/cards/{card_id}/default` | POST | `not_found` 404 |

### `config`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/config` | GET | `credentials_encryption_unavailable` 500 |

### `devices`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/me/devices` | GET | — |
| `/me/devices` | PUT | `invalid_input` 422 |
| `/me/devices/{device_id}` | DELETE | — |
| `/me/notification-preferences` | GET | — |
| `/me/notification-preferences` | PUT | — |

### `drivers`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/drivers/me` | GET | — |
| `/drivers/me` | PATCH | — |
| `/drivers/me/advances` | GET | — |
| `/drivers/me/advances` | POST | `advance_not_allowed` 409 · `advance_unavailable` 409 · `insufficient_balance` 409 · `invalid_input` 422 · `permission_denied` 403 |
| `/drivers/me/advances/repay` | POST | `insufficient_balance` 409 · `invalid_input` 422 · `not_found` 404 · `permission_denied` 403 |
| `/drivers/me/deactivation` | DELETE | `not_found` 404 |
| `/drivers/me/deactivation` | GET | — |
| `/drivers/me/deactivation` | POST | `deactivation_blocked` 409 |
| `/drivers/me/documents` | GET | — |
| `/drivers/me/documents/{doc_type}` | PUT | `conflict` 409 · `document_too_large` 413 · `rate_limited` 429 · `unsupported_document` 422 |
| `/drivers/me/documents/{document_id}/file` | GET | `document_file_missing` 404 · `not_found` 404 |
| `/drivers/me/earnings` | GET | — |
| `/drivers/me/location` | POST | `conflict` 409 · `permission_denied` 403 · `rate_limited` 429 |
| `/drivers/me/offline` | POST | — |
| `/drivers/me/online` | POST | `conflict` 409 · `permission_denied` 403 |
| `/drivers/me/vehicles` | GET | — |
| `/drivers/me/vehicles` | POST | `conflict` 409 |
| `/drivers/me/vehicles/{vehicle_id}` | PATCH | `conflict` 409 · `not_found` 404 |
| `/drivers/nearby` | GET | — |

### `missions`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/drivers/me/progress` | GET | — |

### `notifications`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/me/notifications` | GET | — |
| `/me/notifications/read` | POST | — |
| `/me/notifications/unread-count` | GET | — |

### `payments`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/payments/{payment_id}/cliq-reference` | POST | `conflict` 409 · `invalid_input` 422 · `invalid_payment_transition` 409 · `not_found` 404 |
| `/payments/{payment_id}/confirm` | POST | `insufficient_balance` 409 · `invalid_payment_transition` 409 · `not_found` 404 · `permission_denied` 403 |
| `/payments/{payment_id}/dispute` | POST | `invalid_input` 422 · `invalid_payment_transition` 409 · `not_found` 404 · `permission_denied` 403 |
| `/rides/{ride_id}/payments` | GET | `not_found` 404 |
| `/rides/{ride_id}/payments` | POST | `feature_disabled` 403 · `insufficient_balance` 409 · `invalid_input` 422 · `not_found` 404 · `ride_already_paid` 409 · `ride_not_payable` 409 · `wallet_frozen` 403 |

### `places`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/me/places` | GET | — |
| `/me/places` | POST | `conflict` 409 · `not_found` 404 |
| `/me/places/{place_id}` | DELETE | `not_found` 404 |
| `/me/places/{place_id}` | PATCH | `conflict` 409 · `not_found` 404 |

### `referrals`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/me/referrals` | GET | — |

### `rides`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/rides` | POST | `cancellation_debt_blocked` 402 · `invalid_input` 422 · `multi_stop_unavailable` 409 · `not_found` 404 · `pricing_rule_missing` 409 · `promo_invalid` 404 · `promo_unavailable` 403 · `ride_already_active` 409 · `routing_unavailable` 503 · `ride_sharing_gender_choice_required` 422 · `ride_sharing_unavailable` 422 · `women_service_unavailable` 409 |
| `/rides/estimate` | POST | `pricing_rule_missing` 409 · `routing_failed` 502 · `routing_unavailable` 503 |
| `/rides/me` | GET | — |
| `/rides/me/active` | GET | — |
| `/rides/promo/validate` | POST | `promo_already_used` 409 · `promo_exhausted` 404 · `promo_invalid` 404 · `promo_unavailable` 403 |
| `/rides/{ride_id}/accept` | POST | `invalid_ride_transition` 409 · `not_found` 404 · `permission_denied` 403 · `ride_already_active` 409 · `ride_offer_expired` 409 · `routing_failed` 502 · `routing_unavailable` 503 |
| `/rides/{ride_id}/arrive` | POST | `invalid_ride_transition` 409 · `not_found` 404 · `pause_already_open` 409 · `permission_denied` 403 |
| `/rides/{ride_id}/cancel` | POST | `cancel_reason_not_applicable` 409 · `invalid_ride_transition` 409 · `not_found` 404 · `permission_denied` 403 · `pricing_rule_missing` 409 |
| `/rides/{ride_id}/complete` | POST | `invalid_ride_transition` 409 · `not_found` 404 · `permission_denied` 403 · `pricing_rule_missing` 409 |
| `/rides/{ride_id}/decline` | POST | `ride_offer_expired` 409 |
| `/rides/{ride_id}/driver/photo` | GET | `document_file_missing` 404 · `not_found` 404 |
| `/rides/{ride_id}/pause` | POST | `invalid_input` 422 · `not_found` 404 · `pause_already_open` 409 |
| `/rides/{ride_id}/ratings` | GET | `not_found` 404 |
| `/rides/{ride_id}/ratings` | POST | `already_rated` 409 · `not_found` 404 · `rating_not_allowed` 409 |
| `/rides/{ride_id}/reroute` | POST | `not_found` 404 · `routing_failed` 502 · `routing_unavailable` 503 |
| `/rides/{ride_id}/resume` | POST | `no_open_pause` 404 · `not_found` 404 |
| `/rides/{ride_id}/route-line` | GET | `not_found` 404 · `routing_failed` 502 · `routing_unavailable` 503 |
| `/rides/{ride_id}/start` | POST | `invalid_ride_transition` 409 · `not_found` 404 · `permission_denied` 403 |
| `/rides/{ride_id}/stops/{stop_id}/arrive` | POST | `invalid_ride_transition` 409 · `not_found` 404 · `permission_denied` 403 |
| `/rides/{ride_id}/stops/{stop_id}/resume` | POST | `invalid_ride_transition` 409 · `not_found` 404 · `permission_denied` 403 |
| `/rides/{ride_id}/tip` | GET | `not_found` 404 |
| `/rides/{ride_id}/tip` | POST | `insufficient_balance` 409 · `invalid_input` 422 · `not_found` 404 · `permission_denied` 403 · `tip_already_given` 409 · `tip_not_allowed` 409 · `tips_unavailable` 403 · `wallet_frozen` 403 |

### `subscriptions`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/subscriptions` | POST | `conflict` 409 · `feature_disabled` 403 · `insufficient_balance` 409 · `invalid_input` 422 · `not_found` 404 · `permission_denied` 403 · `subscription_already_purchased` 409 · `wallet_frozen` 403 |
| `/subscriptions/card` | POST | `card_gateway_unavailable` 503 · `conflict` 409 · `feature_disabled` 403 · `not_found` 404 · `permission_denied` 403 · `rate_limited` 429 |
| `/subscriptions/me` | GET | — |
| `/subscriptions/me/history` | GET | — |
| `/subscriptions/plans` | GET | — |

### `wallet`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/wallet/me` | GET | `permission_denied` 403 |
| `/wallet/me/driver` | GET | — |
| `/wallet/me/topups` | GET | — |
| `/wallet/me/topups` | POST | `feature_disabled` 403 · `invalid_input` 422 · `permission_denied` 403 · `wallet_frozen` 403 |
| `/wallet/me/topups/card` | POST | `card_gateway_unavailable` 503 · `feature_disabled` 403 · `not_found` 404 · `permission_denied` 403 · `rate_limited` 429 · `wallet_frozen` 403 |
| `/wallet/me/topups/cliq` | POST | `cliq_acquirer_unavailable` 503 · `feature_disabled` 403 · `invalid_input` 422 · `permission_denied` 403 · `rate_limited` 429 · `wallet_frozen` 403 |
| `/wallet/me/topups/cliq/{cart_id}` | GET | `cliq_acquirer_unavailable` 503 · `insufficient_balance` 409 · `not_found` 404 |
| `/wallet/me/transactions` | GET | `permission_denied` 403 |
| `/wallet/me/transfers` | POST | `feature_disabled` 403 · `insufficient_balance` 409 · `invalid_input` 422 · `not_found` 404 · `permission_denied` 403 · `wallet_frozen` 403 · `wallet_limit_exceeded` 409 |
| `/wallet/me/withdrawals` | GET | — |
| `/wallet/me/withdrawals` | POST | `insufficient_balance` 409 · `invalid_input` 422 · `wallet_frozen` 403 · `wallet_limit_exceeded` 409 |
| `/wallet/transfer/recipient` | GET | `feature_disabled` 403 · `not_found` 404 · `rate_limited` 429 |

### `؟`

| المسار | الطريقة | الأخطاء الخاصة (الرمز — الحالة) |
|---|---|---|
| `/health` | GET | — |

## الشاشات

و«—» تعني **لا ينطبق**: شاشةُ قراءةٍ بلا نموذجٍ لا يُطلب منها وسمُ حقل.

`تحقّقٌ فوري` = فحصٌ قبل الإرسال بالقواعد المنشورة · `وسمُ الحقل` = تعليمُ الحقل الذي
سمّته الخلفيةُ ونقلُ التركيز إليه · `رسالةُ الخلفية` = تُعرض كما هي لا تُستبدل بنصٍّ عام.

### تطبيق الكبتن (`driver-app`) — 25 شاشة

| الشاشة | نداءات API | رسالةُ الخلفية | وسمُ الحقل | تحقّقٌ فوري |
|---|---|---|---|---|
| `Account` | — | ❌ | — | — |
| `Advances` | `requestAdvance` | ✅ | ❌ | ❌ |
| `CardReturn` | `getCardOrder` | ✅ | — | — |
| `Cards` | `deleteSavedCard`, `makeCardDefault` | ✅ | ❌ | ❌ |
| `Collect` | `confirmPayment`, `getRidePayments` | ✅ | ❌ | ❌ |
| `Deactivation` | `requestDeactivation` | ✅ | ❌ | ❌ |
| `Dispute` | `disputePayment`, `getRide`, `getRidePayments` | ✅ | ❌ | ❌ |
| `Earnings` | `getEarnings` | ✅ | — | — |
| `ForgotPassword` | `resetPassword`, `startPasswordResetChallenge` | ✅ | ✅ | ✅ |
| `Home` | `acceptRide`, `arriveAtStop`, `arriveRide`, `beginPause` +9 | ✅ | ❌ | ❌ |
| `Login` | `login` | ✅ | ✅ | ❌ |
| `Missions` | — | ✅ | — | — |
| `Notifications` | `listNotifications`, `markNotificationsRead` | ✅ | ❌ | ❌ |
| `Pending` | — | ❌ | — | — |
| `RateRider` | `rateRide` | ✅ | ❌ | ❌ |
| `Referrals` | — | ✅ | — | — |
| `Register` | `registerAccount`, `startSignupChallenge` | ✅ | ✅ | ✅ |
| `RegisterDocuments` | `addVehicle`, `updateDriver`, `uploadDocument` | ✅ | ✅ | ✅ |
| `RideDetails` | `confirmPayment`, `getRide`, `getRidePayments`, `listRideRatings` | ✅ | ❌ | ❌ |
| `Rides` | `listMyRides` | ✅ | — | — |
| `Settings` | `setNotificationPreferences`, `updateDriver` | ✅ | ❌ | ❌ |
| `Subscription` | `buySubscription`, `buySubscriptionWithCard`, `updateDriver` | ✅ | ❌ | ❌ |
| `Vehicle` | `updateVehicle`, `uploadDocument` | ✅ | ❌ | ❌ |
| `Wallet` | `listWalletTransactions`, `listWithdrawals` | ✅ | — | — |
| `Withdrawals` | `listWithdrawals` | ✅ | — | — |

### تطبيق الراكب (`customer-app`) — 20 شاشة

| الشاشة | نداءات API | رسالةُ الخلفية | وسمُ الحقل | تحقّقٌ فوري |
|---|---|---|---|---|
| `Account` | — | — | — | — |
| `Bookings` | `cancelBooking` | ✅ | ❌ | ❌ |
| `CardReturn` | `getCardOrder` | ✅ | — | — |
| `Cards` | `deleteSavedCard`, `setDefaultCard` | ✅ | ❌ | ❌ |
| `ForgotPassword` | `resetPassword`, `startPasswordReset` | ✅ | ✅ | ✅ |
| `Home` | `createBooking`, `getRouteLine`, `requestRide`, `updateMe` | ✅ | ❌ | ❌ |
| `Login` | `login` | ✅ | ✅ | ❌ |
| `Notifications` | — | ✅ | — | — |
| `Payment` | `getRide`, `getRidePayments`, `payRide` | ✅ | ❌ | ❌ |
| `Places` | `createPlace`, `deletePlace`, `updatePlace` | ✅ | ❌ | ❌ |
| `Profile` | `startChallenge`, `updateMe`, `verifyMyPhone` | ✅ | ❌ | ❌ |
| `Rating` | `addTip`, `getTipOptions`, `listRideRatings`, `rateRide` | ✅ | ❌ | ❌ |
| `Referrals` | — | ✅ | — | — |
| `Register` | `register`, `startChallenge` | ✅ | ✅ | ✅ |
| `RideDetails` | `getRide`, `getRidePayments`, `listRideRatings` | ✅ | — | — |
| `Rides` | `listMyRides` | ✅ | — | — |
| `Settings` | `setNotificationPreferences` | ✅ | ❌ | ❌ |
| `WalletHome` | `listTopups`, `listTransactions` | ✅ | — | — |
| `WalletTopup` | `checkCliqTopup`, `createCardTopup`, `createCliqTopup`, `createTopupRequest` | ✅ | ❌ | ❌ |
| `WalletTransfer` | `lookupRecipient`, `transfer` | ✅ | ❌ | ❌ |

### لوحة الإدارة (`admin-panel`) — 17 شاشة

| الشاشة | نداءات API | رسالةُ الخلفية | وسمُ الحقل | تحقّقٌ فوري |
|---|---|---|---|---|
| `Audit` | `listAuditLogs` | ✅ | — | — |
| `Campaigns` | `cancelCampaign`, `createCampaign`, `listDeliveries` | ✅ | ✅ | ❌ |
| `Disputes` | `listPayments`, `resolveDispute` | ✅ | ✅ | ❌ |
| `Drivers` | `activateDriver`, `approveDriver`, `getDriverDocuments`, `listDrivers` +4 | ✅ | ✅ | ❌ |
| `Finance` | `approveWithdrawal`, `confirmTopup`, `listTopups`, `markWithdrawalPaid` +2 | ✅ | ✅ | ❌ |
| `LiveMap` | `getLiveMap` | ✅ | — | — |
| `Login` | `login`, `loginWithTotp` | ✅ | ✅ | ❌ |
| `Overview` | `getOverview` | ✅ | — | — |
| `Pricing` | `createPricing`, `deletePricing`, `listPricing`, `updatePricing` | ✅ | ✅ | ❌ |
| `Providers` | `saveProviderCredential`, `testProviderCredential` | ✅ | ✅ | ❌ |
| `Reports` | `getReports` | ✅ | — | — |
| `Riders` | `blockUser`, `freezeWallet`, `getWallet`, `listUsers` +3 | ✅ | ✅ | ❌ |
| `Rides` | `getRide`, `listRides` | ✅ | — | — |
| `Security` | `confirmTotp`, `disableTotp`, `updateSecurityPolicy`, `verifyRecoveryCode` | ✅ | ✅ | ❌ |
| `Settings` | `getReferralSettings`, `getSharingSettings`, `setFeatureFlag`, `updateAdvanceSettings` +7 | ✅ | ✅ | ❌ |
| `Subscriptions` | `createPlan`, `deletePlan`, `listDrivers`, `listSubscriptions` +2 | ✅ | ✅ | ❌ |
| `Users` | `listUsers` | ✅ | — | — |

