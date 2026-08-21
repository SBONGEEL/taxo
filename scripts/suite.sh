#!/usr/bin/env bash
# تشغيلُ مجموعة الاختبارات — **بابٌ واحد، ويفشل بنصٍّ يسمّي السبب**.
#
# **العلّةُ التي بُني لها** (٢٠٢٦-٠٨-٢٠): درسٌ مكتوبٌ في `CLAUDE.md` لم يمنع
# وقوعَه، بينما `check:enums` أوقف البناءَ في الجلسة نفسِها. **المكتوبُ لا
# يُطبَّق، والحارسُ يُطبَّق** — فصار هذا حارساً.
#
# **وما وقع بالضبط، مقيساً لا مستنتَجاً**: مُهلةٌ انتهت فقتلت **عميلَ** compose،
# **والحاويةُ بقيت تعمل** — لأن قتلَ العميل لا يقتل ما بدأه. فظلّت تمسك
# `taxo_test` مفتوحةً، وكلُّ تشغيلٍ بعده يفشل عند التهيئة بـ`DROP DATABASE …
# being accessed by other users` — **١٠٧٦ خطأً بنصٍّ واحد**، تُقرأ كارثةً في
# الكود وهي بيئةٌ متسخة.
#
# **وقد شُخِّص أولاً خطأً** بأنه «`run` يرث `restart: unless-stopped`» — وهو
# درسٌ مكتوبٌ في `CLAUDE.md`. والقياسُ نفاه: `RestartPolicy=no` على حاويةِ
# التشغيل نفسِها. **فمطابقةُ العَرَض بدرسٍ محفوظٍ ليست تشخيصاً** — وهي العلّةُ
# التي يحرسها هذا الملف مرتين: مرةً بمنع الحالة، ومرةً بتسميتها حين تقع.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 2

# **وملفُّ البيئة يُصرَّح ولا يُثبَّت**: محلياً `.env.local`، وفي CI ملفٌّ
# مولَّدٌ للتشغيل — فالبابُ واحدٌ في البيئتين، ولا تفترق مجموعتان.
#
# **وكان هذا السطرُ يصف ما ليس كذلك** (صُحّح 2026-08-21): التصريحُ يحكم
# `--env-file` وحدَه، **و`docker-compose.yml` كان يثبّت `.env.local` في
# `env_file` لأربع خدمات** — فيقف compose على استنساخٍ نظيفٍ مهما صرّح
# المستدعي، **وهو ما أحمرَّ به CI**. فصار الاسمُ يحكم الموضعين
# (`${TAXO_ENV_FILE:-.env.local}` في compose نفسِه). **وتوثيقٌ يصف ما ليس
# كذلك يصرف القارئَ عن موضع العطب** — من عائلة الجدول الأحمر.
ENV_FILE="${TAXO_ENV_FILE:-.env.local}"
OUT="backend/.suite.out"
DB_URL="postgresql+asyncpg://taxo:taxo@db:5432/taxo"
REDIS_URL="redis://redis:6379/0"

dc() { docker compose --env-file "$ENV_FILE" "$@"; }

fail() { printf '\n✗ %s\n' "$1" >&2; shift; for line in "$@"; do printf '  %s\n' "$line" >&2; done; exit 1; }

# ── ١) حاوياتٌ شاردةٌ من تشغيلٍ سابق ───────────────────────────────────────
# **الاسمان معاً** — وهذا قِيس في استعمالٍ حقيقيّ (2026-08-20): قُتل تشغيلٌ
# فبقيت حاويتُه، **واسمُها `taxo-suite-run-…`** (هذا الملفُّ يسمّيها) بينما كان
# المُرشِّحُ يبحث عن `taxo-app-backend-run` وحدَه — فأمسكها فحصُ الجلسات لا فحصُ
# الحاويات. **وحارسٌ بنصفين يمسك بنصفِه الثاني هو حارسٌ سقط نصفُه صامتاً.**
strays=$(docker ps --filter "name=taxo-suite-run" --filter "name=taxo-app-backend-run"   --format '{{.Names}} ({{.Status}})')
if [ -n "$strays" ]; then
  fail "تشغيلُ اختباراتٍ سابقٌ ما زال يعمل — ولن يُدرَج تشغيلٌ ثانٍ فوقه." \
       "$strays" \
       "" \
       "وهو ما يمسك \`taxo_test\` فيفشل هذا التشغيلُ كلُّه عند التهيئة." \
       "أزِلْه ثم أعد:  docker rm -f \$(docker ps -q --filter name=taxo-suite-run --filter name=taxo-app-backend-run)"
fi

# ── ٢) جلساتٌ ما زالت على قاعدة الاختبار ──────────────────────────────────
held=$(dc exec -T db psql -U taxo -d postgres -tAc \
  "SELECT count(*) FROM pg_stat_activity WHERE datname='taxo_test';" 2>/dev/null | tr -d '\r ')
if [ -n "$held" ] && [ "$held" != "0" ]; then
  fail "قاعدةُ الاختبار ممسوكةٌ بـ$held جلسة، و\`DROP DATABASE\` سيفشل." \
       "لا تقرأ ما سيأتي على أنه عطبٌ في الكود: الخطأُ واحدٌ يتكرر بعدد الاختبارات." \
       "لتحريرها:  docker compose --env-file $ENV_FILE exec -T db \\" \
       "             psql -U taxo -d postgres -c \"SELECT pg_terminate_backend(pid) \\" \
       "             FROM pg_stat_activity WHERE datname='taxo_test';\""
fi

# ── ٣) التشغيل — **والحاويةُ تُقتل معنا لا بعدنا** ─────────────────────────
# اسمٌ معلومٌ سلفاً، فمقاطعةٌ بـCtrl-C أو مهلةٌ تنتهي تجد ما تحذفه. وبغيره
# تبقى الحاويةُ تعمل بعد أن يذهب من بدأها — وهي الحالُ التي أنشأت هذا الملف
NAME="taxo-suite-run-$$"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT INT TERM

printf '→ المجموعةُ تعمل… (النتيجةُ تُكتب في %s فتبقى بعد الحاوية)\n' "$OUT"
dc run --rm --no-deps --name "$NAME" \
  -e DATABASE_URL="$DB_URL" -e REDIS_URL="$REDIS_URL" \
  backend sh -c "pytest -q ${*:-} > /app/.suite.out 2>&1; echo EXIT=\$? >> /app/.suite.out"
code=$?

tail -n 3 "$OUT" 2>/dev/null
verdict=$(grep -c '^EXIT=0$' "$OUT" 2>/dev/null || true)
if [ "$verdict" != "1" ]; then
  printf '\n✗ المجموعةُ لم تنتهِ بنجاح — اقرأ %s كاملاً.\n' "$OUT" >&2
  printf '  وإن كان الخطأُ واحداً يتكرر عند التهيئة فالسببُ بيئةٌ لا كود.\n' >&2
  exit "${code:-1}"
fi
printf '\n✓ المجموعةُ خضراء.\n'
