# Python 3.12: أحدث إصدار تدعمه كل الاعتماديات الملزمة (asyncpg, SQLAlchemy 2, Celery)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# `postgresql-client` للنسخ الاحتياطي، و`gnupg` لتشفير الأرشيف قبل أن يغادر
# الخادم (قرارُ المالك ٤).
#
# **والنسخةُ تُطابق الخادمَ بالضبط: ١٦** — لا أحدثَ ولا أقدم.
#
# أقدمُ من الخادم يرفض العملَ أصلاً («server version mismatch») فتكون النتيجةُ
# **نسخةً لم تُؤخذ**. وأحدثُ يُنتج دمباً سليماً — **لكنّ `pg_restore` منه يُصدر
# `SET transaction_timeout`، وهو إعدادٌ لا يعرفه خادمُ ١٦**، فترتدّ كلُّ استعادةٍ
# بخطأٍ ورقمِ خروجٍ غيرِ صفر وهي ناجحة. وذلك يُعلّم المالكَ تجاهلَ الخطأ، ثم
# يتجاهله يومَ يصدق — وهو ما تمنعه الخطةُ بنصِّها: **لا فشلَ صامتاً ولا نجاحَ
# يُقرأ فشلاً**. وقد وقع الاثنان هنا فعلاً قبل التثبيت.
#
# **والاسمُ الرمزيُّ يُقرأ من الصورة لا يُكتب بيد**: أوّلُ محاولةٍ ثبّتت
# `bookworm` على صورةِ `trixie` فانهار حلُّ الاعتماديات (`libpq5` مكسور).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
         -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release; echo "$VERSION_CODENAME")-pgdg main" \
         > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
