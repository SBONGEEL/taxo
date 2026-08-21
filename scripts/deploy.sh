#!/usr/bin/env bash
# **بابُ النشرِ الوحيدُ إلى الإنتاج — ويرفض البدءَ بلا نسخةٍ محقَّقة.**
#
# القاعدةُ في `CLAUDE.md` (قرارُ المالك 2026-08-21): كلُّ تحديثٍ تسبقه نسخة.
# **وهذا البابُ هو ما يجعلها تُطبَّق** بدل أن تُتذكَّر — وهو الفرقُ نفسُه الذي
# أنشأ `suite.sh`: قاعدةٌ مكتوبةٌ لم تمنع الفخَّ، وحارسٌ منعه.
#
# وثلاثةُ شروطٍ فيه ليست تفصيلاً:
#
# ١) **النسخةُ تسبق الرفعَ لا تليه.** فلا تُنقل ملفاتٌ قبل أن تكتمل النسخةُ
#    وتُقاس — ونسخةٌ بعد الرفع تحفظ ما بعد العطب لا ما قبله.
# ٢) **وتُنقل خارجَ الخادم.** الخادمُ الذي تحتاج النسخةَ بسببه هو الذي يسقط،
#    ونسخةٌ عليه وحدَه تسقط معه.
# ٣) **ولا تُقرأ ناجحةً حتى تُفتح.** «انتهى النقل» ليس «الملفُّ سليم»: قرصٌ
#    ممتلئٌ أو إذنٌ مرفوضٌ ينهي النقلَ بلا استثناء — وهو درسُ `core/storage.save`
#    بعينه. فيُقاس الحجمُ **ويُفتح المحتوى فعلاً** (`gzip -t` ثم قراءةُ رأس
#    الـSQL) قبل أن يُقال «محقَّقة».
#
# الاستعمال:
#   bash scripts/deploy.sh <ملفّ|مجلد> [ملفّ|مجلد ...]
#   TAXO_DEPLOY_HOST=taxo@169.58.207.123 bash scripts/deploy.sh landing/config.js
set -euo pipefail

HOST="${TAXO_DEPLOY_HOST:-taxo@169.58.207.123}"
REMOTE="${TAXO_REMOTE_PROJECT:-~/taxo}"
DEST="${TAXO_BACKUP_DEST:-/d/taxo-backups}"
SSH_OPTS=(-o StrictHostKeyChecking=yes -i "$HOME/.ssh/taxo-contabo")

say() { printf '%s\n' "$*"; }
die() { printf '\n✗ %s\n' "$*" >&2; exit 1; }

[ "$#" -gt 0 ] || die "لا شيءَ لرفعه. الاستعمال: bash scripts/deploy.sh <مسار> [...]"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOCAL="$DEST/pre-deploy-$STAMP"
mkdir -p "$LOCAL"

say "══ ١) النسخةُ قبل الرفع — $STAMP"

# القاعدة: تفريغٌ مضغوطٌ يُكتب إلى المخرج القياسي فيصل هنا مباشرةً، فلا يبقى
# على الخادم نسخةٌ ثانيةٌ تُنسى ولا يُملأ قرصُه.
say "  · القاعدة…"
ssh "${SSH_OPTS[@]}" "$HOST" \
  "cd $REMOTE && docker compose exec -T db pg_dump -U taxo -d taxo --no-owner | gzip -9" \
  > "$LOCAL/taxo.sql.gz" || die "تعذّر تفريغُ القاعدة — لا رفع."

say "  · الأسرار ومجلد الوثائق…"
ssh "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && tar -czf - .env" \
  > "$LOCAL/env.tar.gz" || die "تعذّرت نسخةُ .env — لا رفع."
# **الوثائقُ قد لا تكون موجودةً بعدُ على إنتاجٍ جديد**، والغيابُ يُقال ولا يُسكت
if ssh "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && test -d backend/var/documents"; then
  ssh "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && tar -czf - backend/var/documents" \
    > "$LOCAL/documents.tar.gz" || die "تعذّرت نسخةُ الوثائق — لا رفع."
else
  say "    (لا مجلدَ وثائقَ على الخادم بعد — يُسجَّل ولا يُسكت عنه)"
  : > "$LOCAL/documents.absent"
fi

say "══ ٢) التحقّق — نسخةٌ لم تُفتح ليست نسخة"
# **ولكلِّ ملفٍّ سؤالٌ عن محتواه لا عن حجمه.** الحجمُ وكيلٌ فاسدٌ في الاتجاهين:
# قِيس هنا أنه يرفض تفريغاً سليماً صغيراً، وهو أيضاً يقبل أرشيفاً سليمَ الغلاف
# يحمل رسالةَ خطأٍ بدل البيانات. **فالحجمُ يكشف الفراغَ وحدَه، والمحتوى يحكم.**
FAIL=0
check() { # اسمُ الملف · وصفٌ · أمرُ فحصِ المحتوى
  local file="$LOCAL/$1" label="$2"; shift 2
  if [ ! -s "$file" ]; then say "  ✗ $label — غائبٌ أو فارغ"; FAIL=1; return; fi
  if ! gzip -t "$file" 2>/dev/null; then say "  ✗ $label — لا يُفتح"; FAIL=1; return; fi
  if ! "$@" >/dev/null 2>&1; then
    say "  ✗ $label — يُفتح ومحتواه ليس ما نتوقّع"; FAIL=1; return
  fi
  say "  ✓ $label — يُفتح ومحتواه صحيح ($(wc -c < "$file" | tr -d " ") بايت)"
}

sql_is_a_dump() {
  gzip -dc "$LOCAL/taxo.sql.gz" | grep -q "PostgreSQL database dump" || return 1
  local n; n=$(gzip -dc "$LOCAL/taxo.sql.gz" | grep -c "^CREATE TABLE" || true)
  say "    (جداولُ التفريغ: $n)"
  [ "$n" -ge 20 ]
}
tar_holds() { tar -tzf "$1" 2>/dev/null | grep -q "$2"; }

check taxo.sql.gz "القاعدة" sql_is_a_dump
check env.tar.gz  "الأسرار" tar_holds "$LOCAL/env.tar.gz" '^\(\./\)\?\.env$'
if [ -f "$LOCAL/documents.tar.gz" ]; then
  check documents.tar.gz "الوثائق" tar_holds "$LOCAL/documents.tar.gz" "documents"
fi

[ "$FAIL" -eq 0 ] || die "النسخةُ لم تُحقَّق — **لا رفع**. قف واسأل المالك."

say "  ⇒ النسخةُ المحقَّقة: $LOCAL"

say "══ ٣) الرفع"
tar -cf - "$@" | ssh "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && tar -xf -" \
  || die "فشل الرفعُ — والنسخةُ في $LOCAL"
for p in "$@"; do say "  ✓ $p"; done

say ""
say "✓ رُفع بعد نسخةٍ محقَّقة."
say "  النسخة : $LOCAL"
say "  وقتُها : $STAMP (UTC)"
say "  حجمُها : $(du -sh "$LOCAL" | cut -f1)"
say ""
say "  **يُذكر هذا الثلاثيُّ في تقرير الرفع** (قاعدةُ CLAUDE.md الأولى)."
