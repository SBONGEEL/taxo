# TAXO — الخلفية (المراحل 1–4)

المرجع الوحيد للمشروع هو [SPEC.md](SPEC.md). هذا الملف يشرح تشغيل ما أُنجز من
القسم 16:

- **المرحلة 1:** البنية التحتية + هيكل FastAPI + Alembic + جداول
  `users`/`drivers`/`vehicles` + المصادقة بهاتف وكلمة مرور مع JWT.
- **المرحلة 2:** الإعدادات per-country (`pricing_rules`, `feature_flags`,
  `commission_settings`, `subscription_plans`) + جدول `provider_credentials`
  المشفّر مع CRUD إداري وseed لتوكنات Mapbox وTelr Sandbox + `GET /config`.
- **المرحلة 3:** جدول `rides` + التسعير عبر Mapbox Directions من الخلفية حصراً
  + endpoints الطلب والانتقالات بين الحالات.
- **المرحلة 4:** حضور الكباتن على Redis GEO + خوارزمية التوزيع (الأقرب أولاً،
  مهلة 20 ثانية، 5 محاولات أو دقيقتان) + مقابس WebSocket للتتبع والأحداث +
  مراقبة انقطاع الكبتن أثناء الرحلة.

## المتطلبات

Docker Desktop فقط. (المنافذ: 5432 لقاعدة البيانات، 6379 لـ Redis، **8001** للـ API.)

## التشغيل

```bash
cp .env.example .env.local   # ثم املأ القيم — الملف موجود مسبقاً ومعبّأ محلياً
docker compose up -d --build
```

عند الإقلاع يشغّل الحاوية `alembic upgrade head` تلقائياً ثم uvicorn.

- فحص الصحة: <http://localhost:8001/health>
- توثيق تفاعلي: <http://localhost:8001/docs>

### بذر إعدادات التطوير

```bash
docker compose run --rm --no-deps \
  -e DATABASE_URL="postgresql+asyncpg://taxo:taxo@db:5432/taxo" \
  -e REDIS_URL="redis://redis:6379/0" \
  backend python -m scripts.seed
```

يملأ إعدادات ليبيا والأردن (تسعير، مفاتيح ميزات، عمولة صفر معطّلة، خطط اشتراك)،
ويكتب توكنات Mapbox وTelr Sandbox **مشفّرة** في `provider_credentials` قارئاً
إياها من `.env.local` لمرة واحدة، وينشئ حساب المشرف الأول من
`BOOTSTRAP_ADMIN_PHONE`/`BOOTSTRAP_ADMIN_PASSWORD` (خارج بيئة الإنتاج فقط).
السكربت idempotent ولا يلمس أي صف موجود.

## الاختبارات

```bash
docker compose run --rm --no-deps \
  -e DATABASE_URL="postgresql+asyncpg://taxo:taxo@db:5432/taxo" \
  -e REDIS_URL="redis://redis:6379/0" \
  backend pytest -q
```

الاختبارات تُنشئ قاعدة `taxo_test` وتستخدم Redis رقم 15، ثم تنظّف بعدها —
لا تلمس بيانات التطوير. مخطط قاعدة الاختبار يُبنى بـ `alembic upgrade head`
(لا `create_all`)، و`tests/test_migrations.py` يفشل إن انحرفت الموديلات عن
الترحيلات أو نسيت ترحيلة إسقاط أنواع ENUM في `downgrade`.

## الـ endpoints المتاحة الآن

| الطريقة | المسار | الوصف |
|---------|--------|-------|
| GET | `/health` | حالة التطبيق + DB + Redis |
| GET | `/api/v1/config` | إعدادات عامة للواجهات (بلا مصادقة) |
| GET | `/api/v1/auth/method` | طريقة الدخول الحالية (`password` أو `otp`) |
| POST | `/api/v1/auth/register` | تسجيل راكب أو كبتن |
| POST | `/api/v1/auth/login` | دخول بهاتف + كلمة مرور |
| POST | `/api/v1/auth/refresh` | تدوير التوكن |
| POST | `/api/v1/auth/logout` | إبطال جلسة الجهاز الحالي |
| GET | `/api/v1/auth/me` | بيانات المستخدم الحالي |
| GET | `/api/v1/drivers/me` | ملف الكبتن + مركباته + مستنداته |
| GET/POST | `/api/v1/drivers/me/vehicles` | مركبات الكبتن |
| POST | `/api/v1/drivers/me/online` · `/offline` | مفتاح الاتصال في تطبيق الكبتن |
| POST | `/api/v1/drivers/me/location` | بثّ موقع (بديل REST للمقبس) |
| GET | `/api/v1/drivers/nearby` | سيارات قريبة مجهّلة لخريطة الراكب |
| POST | `/api/v1/rides/estimate` | سعر مقدّر قبل الطلب |
| POST | `/api/v1/rides` | طلب رحلة (يبدأ التوزيع فوراً) |
| GET | `/api/v1/rides/me` · `/me/active` | سجل الرحلات وآخر حالة جارية |
| GET | `/api/v1/rides/{id}` | تفاصيل رحلة (بفحص الملكية) |
| POST | `/api/v1/rides/{id}/accept` · `/decline` | قبول الطلب المعروض أو رفضه |
| POST | `/api/v1/rides/{id}/arrive` · `/start` · `/complete` | انتقالات الكبتن |
| POST | `/api/v1/rides/{id}/cancel` | إلغاء من الراكب أو الكبتن |
| WS | `/api/v1/ws/driver` | بثّ موقع الكبتن + بطاقات الطلبات + الأحداث |
| WS | `/api/v1/ws/rider` | سيارات الخريطة + موقع الكبتن المُسنَد + الأحداث |
| GET/POST/PATCH/DELETE | `/api/v1/admin/settings/pricing` | تسعيرة كل فئة في كل دولة |
| GET/PUT | `/api/v1/admin/settings/feature-flags` | مفاتيح الميزات per-country |
| GET/PATCH | `/api/v1/admin/settings/commission` | تفعيل العمولة ونسبتها |
| GET/POST/PATCH/DELETE | `/api/v1/admin/settings/subscription-plans` | خطط اشتراك الكباتن |
| GET | `/api/v1/admin/settings/audit-logs` | سجل التدقيق الإداري |
| GET | `/api/v1/admin/providers` | بطاقات المزودين + العقود المحفوظة (مقنّعة) |
| PUT | `/api/v1/admin/providers/{provider_key}` | حفظ عقد مزود |
| POST | `/api/v1/admin/providers/{id}/activate` · `/deactivate` | تفعيل العقد وتعطيله |
| DELETE | `/api/v1/admin/providers/{id}` | حذف عقد |

القراءة من `/admin/settings/*` متاحة لـ `admin` و`support`؛ الكتابة لـ `admin`
وحده. صفحة العقود `/admin/providers` لـ `admin` حصراً (SPEC القسم 13/8).

## الأسرار

- `.env.local` يحوي **أسرار البنية التحتية فقط** (DB, Redis, JWT, مفتاح
  `CREDENTIALS_ENCRYPTION_KEY`) وهو مُدرج في `.gitignore` ولا يدخل Git أبداً.
- توكنات Mapbox/Telr موجودة فيه كمدخل لـ `scripts/seed.py` وحده؛ المصدر الرسمي
  لها هو جدول `provider_credentials` المشفّر الذي يُدار من صفحة العقود.
- مزودو SMS وFCM وpayout وCliQ الآلي تُدخل عقودهم من اللوحة مباشرة — لا مكان
  لهم في البيئة إطلاقاً.

## ملاحظات معمارية

- **المصادقة عبر واجهة موحّدة** (`app/services/auth/`): `PasswordAuthStrategy`
  فعّالة الآن، و`OtpAuthStrategy` جاهزة كنقطة تبديل. `sms_provider_enabled()`
  تقرأ حالة عقد SMS من `provider_credentials`، فتفعيل العقد من اللوحة يحوّل كل
  المسارات إلى OTP دون تغيير أي endpoint (التنفيذ الفعلي في المرحلة 8).
- **عقود المزودين مشفّرة at rest**: العمود `credentials` مظروف JSONB
  `{"v": 1, "ciphertext": "…"}` بمفتاح Fernet. الحقول السرية تُقنّع (`****`) في
  اللوحة ولا تخرج من الخلفية؛ العام بطبيعته (Mapbox pk) يُسلَّم عبر `GET /config`.
  إعادة إرسال `****` تُبقي القيمة المخزّنة كما هي.
- **تفعيل المزود يفعّل ميزته** تلقائياً لدولة عقده (Telr → `card_enabled`،
  CliQ acquirer → `cliq_enabled`) — وتعطيله أو حذفه يعطّلها.
- **الهاتف مُعرّف الدخول** ويُخزَّن دائماً بصيغة E.164 بعد التطبيع
  (`+962…` / `+218…`)، فلا يمكن تسجيل نفس الرقم بصيغتين.
- **JWT**: access قصير العمر + refresh مسجّل في Redis مع تدوير لمرة واحدة —
  إعادة استخدام توكن مستهلَك مرفوضة، وتسجيل الخروج يُبطل الجلسة فوراً.
- **Rate limiting** على الدخول لكل رقم ولكل IP، وعلى التسجيل لكل IP، وعلى بثّ
  الموقع عبر REST لكل كبتن (30 في الدقيقة — دورة البثّ 3 ثوانٍ أي 20).
- **المال** كله `NUMERIC(12,3)` والعملة تُشتق من الدولة (LY→LYD، JO→JOD) في
  الخلفية — لا تُقبل من العميل.
- **سجل تدقيق** لكل إجراء إداري في `admin_audit_logs`، يسجّل أسماء الحقول
  المتغيّرة فقط ولا يسجّل أي قيمة سرية.
- **التسعير في الخلفية حصراً**: `POST /rides` يعيد حساب السعر ولا يقرأ أي مبلغ
  من العميل، و`commission_percent_at_ride` تُجمَّد لحظة الإنشاء.
- **التوزيع طلبٌ لكبتن واحد في كل مرة**: العرض محفوظ في Redis، فلا يقبل الرحلةَ
  إلا من عُرضت عليه وضمن مهلته، ومهمة التوزيع تُوقظها إشارة القبول أو الرفض.
- **مواقع الكباتن في Redis لا في القاعدة** (تتغير كل 3 ثوانٍ)، وحضورها بعمر
  محدود فيسقط الصامت تلقائياً من التوزيع والخريطة.
- **مقابس WebSocket بلا حالة في الذاكرة**: البث يمر بـ Redis pub/sub، فيعمل
  النظام بأكثر من عامل uvicorn. المصادقة عبر `?token=` لأن المتصفح لا يسمح
  بترويسات في مصافحة WebSocket.
- **سيارات خريطة الراكب مجهّلة**: إحداثيات واتجاه وفئة فقط، بمعرّف بديل يتغير
  مع كل اتصال (SPEC القسم 10).
- **انقطاع الكبتن أثناء الرحلة** أكثر من 60 ثانية يُنبَّه له الطرفان
  (`driver_connection_lost` ثم `driver_reconnected`) — ولا تُنهى الرحلة آلياً
  أبداً (SPEC القسم 5).
- Python 3.12 داخل الحاوية: أحدث إصدار تدعمه كل الاعتماديات الملزمة
  (asyncpg, SQLAlchemy 2, Celery) وفق قيد SPEC.

## لم يُنفَّذ بعد (مراحل لاحقة من القسم 16)

المحافظ (5) · الدفع (6) · الاشتراكات (7) · استكمال طبقة المزودين وصفحة العقود في اللوحة واختبار الاتصال (8)
· التطبيقات الثلاثة (9-11) · ميزات Phase 2 (12) · التشغيل التجريبي (13).
