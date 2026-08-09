# TAXO — الخلفية (المرحلة 1)

المرجع الوحيد للمشروع هو [SPEC.md](SPEC.md). هذا الملف يشرح تشغيل ما أُنجز من
**المرحلة 1** فقط من القسم 16: البنية التحتية + هيكل FastAPI + Alembic +
جداول `users`/`drivers`/`vehicles` + المصادقة بهاتف وكلمة مرور مع JWT.

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
| GET | `/api/v1/auth/method` | طريقة الدخول الحالية (`password` أو `otp`) |
| POST | `/api/v1/auth/register` | تسجيل راكب أو كبتن |
| POST | `/api/v1/auth/login` | دخول بهاتف + كلمة مرور |
| POST | `/api/v1/auth/refresh` | تدوير التوكن |
| POST | `/api/v1/auth/logout` | إبطال جلسة الجهاز الحالي |
| GET | `/api/v1/auth/me` | بيانات المستخدم الحالي |
| GET | `/api/v1/drivers/me` | ملف الكبتن + مركباته + مستنداته |
| GET/POST | `/api/v1/drivers/me/vehicles` | مركبات الكبتن |

## الأسرار

- `.env.local` يحوي **أسرار البنية التحتية فقط** (DB, Redis, JWT, مفتاح التشفير)
  وهو مُدرج في `.gitignore` ولا يدخل Git أبداً.
- توكنات Mapbox/Telr موجودة فيه مؤقتاً كمصدر لـ seed script التطوير المحلي؛
  المصدر الرسمي لها من المرحلة 2 هو جدول `provider_credentials` المشفّر
  الذي يُدار من صفحة العقود (القسم 15 من SPEC).

## ملاحظات معمارية

- **المصادقة عبر واجهة موحّدة** (`app/services/auth/`): `PasswordAuthStrategy`
  فعّالة الآن، و`OtpAuthStrategy` جاهزة كنقطة تبديل. عند تفعيل مزود SMS تتحول
  كل المسارات لـ OTP دون تغيير أي endpoint (التنفيذ الفعلي في المرحلة 8).
- **الهاتف مُعرّف الدخول** ويُخزَّن دائماً بصيغة E.164 بعد التطبيع
  (`+962…` / `+218…`)، فلا يمكن تسجيل نفس الرقم بصيغتين.
- **JWT**: access قصير العمر + refresh مسجّل في Redis مع تدوير لمرة واحدة —
  إعادة استخدام توكن مستهلَك مرفوضة، وتسجيل الخروج يُبطل الجلسة فوراً.
- **Rate limiting** على الدخول لكل رقم ولكل IP، وعلى التسجيل لكل IP.
- Python 3.12 داخل الحاوية: أحدث إصدار تدعمه كل الاعتماديات الملزمة
  (asyncpg, SQLAlchemy 2, Celery) وفق قيد SPEC.

## لم يُنفَّذ بعد (مراحل لاحقة من القسم 16)

`provider_credentials` والإعدادات (2) · الرحلات والتسعير (3) · التوزيع
وWebSockets (4) · المحافظ (5) · الدفع (6) · الاشتراكات (7) · طبقة المزودين (8)
· التطبيقات الثلاثة (9-11).
