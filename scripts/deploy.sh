#!/usr/bin/env bash
# **بابُ الرفعِ الوحيدُ إلى الإنتاج — خمسُ بوّابات، ما لم تخضرَّ واحدةٌ لا تبدأ
# التي بعدها** (قرارُ المالك 2026-08-21؛ النصُّ كاملاً في رأس `CLAUDE.md`).
#
# **ولمَ بابٌ لا قاعدةٌ تُتذكَّر**: القاعدةُ كانت مكتوبةً في هذا المستودع مراراً
# ووقع خلافُها مراراً — وهو الدرسُ الذي أنشأ فهرسَ الحرّاس: **المكتوبُ لا
# يُطبَّق، والحارسُ يُطبَّق.**
#
#   ١ الإعلان   — كم التزاماً · ترحيلة؟ · جدولُ مال؟ · **طريقُ الرجوع**
#   ٢ الدفعُ وCI — شجرةٌ نظيفة · مسحُ سرّ · دفعٌ · CI أخضرُ على استنساخٍ نظيف
#   ٣ النسخة    — القاعدة و`.env` والوثائق، خارج الخادم، **تُفتح ويُقاس محتواها**
#   ٤ الرفع     — **الخادمُ يسحب من GitHub** نفسَ إيداعِ CI · أمرٌ واحد · ترحيلة
#   ٥ التحقّق   — إيداعٌ · ترحيلةٌ · أربعةُ أعمدةٍ للثلاثة · متصفّحٌ · سجلّ
#
# **وثلاثُ مطلقاتٍ فوقها**: لا رفعَ بلا نسخةٍ محقَّقة · ولا رفعَ يمسّ جدولَ مالٍ
# بلا إذنِ المالك · **ولا إلغاءَ لحارسٍ أو حدٍّ أمنيٍّ أثناء رفع** مهما أعاق.
#
# **وسقوطُ أيِّ مرحلةٍ وقوفٌ عندها**: لا إكمالَ، ولا إصلاحَ على الإنتاج — يُعرض
# ما سقط وطريقُ الرجوع، والقرارُ للمالك.
#
#   bash scripts/deploy.sh                 # يرفع HEAD بعد المرور بالخمس
#   bash scripts/deploy.sh --announce      # البوّابةُ الأولى وحدَها (إعلانٌ بلا رفع)
#
set -euo pipefail

HOST="${TAXO_DEPLOY_HOST:-taxo@169.58.207.123}"
REMOTE="${TAXO_REMOTE_PROJECT:-~/taxo}"
DEST="${TAXO_BACKUP_DEST:-/d/taxo-backups}"
SSH_OPTS=(-o StrictHostKeyChecking=yes -i "$HOME/.ssh/taxo-contabo")

say() { printf '%s\n' "$*"; }
die() { printf '\n✗ %s\n' "$*" >&2; exit 1; }

[ "$#" -ge 0 ] || true

MONEY_TABLES='wallet_transactions|payments|driver_subscriptions|driver_advances|ride_cancellation_charges|withdrawal_requests|wallet_topup_requests|tips|promo_codes|subscription_offers'
ANNOUNCE_ONLY=0
[ "${1:-}" = "--announce" ] && ANNOUNCE_ONLY=1

# ═══════════════════ ١) الإعلان ═══════════════════
say "══ ١) الإعلان"
HEAD_SHA="$(git rev-parse HEAD)"
[ -z "$(git status --porcelain)" ] || die "شجرةٌ غيرُ نظيفة — يُودَع قبل الرفع (البوّابة ٢)."

REMOTE_SHA="$(ssh "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && git rev-parse HEAD 2>/dev/null" || true)"
if [ -n "$REMOTE_SHA" ] && git cat-file -e "$REMOTE_SHA^{commit}" 2>/dev/null; then
  COUNT="$(git rev-list --count "$REMOTE_SHA..$HEAD_SHA")"
  CHANGED="$(git diff --name-only "$REMOTE_SHA..$HEAD_SHA")"
  say "  الإيداع : ${REMOTE_SHA:0:8} ← ${HEAD_SHA:0:8}  ($COUNT التزاماً)"
else
  # **إيداعُ الخادمِ مجهولٌ ⇒ لا يُقاس الفرق**، ولا يُخمَّن: يُعلَن أنه غيرُ معروف
  COUNT="?"; CHANGED="$(git diff --name-only HEAD~1..HEAD)"
  say "  الإيداع : الخادمُ عند ${REMOTE_SHA:-<مجهول>} — الفرقُ غيرُ مقيس"
fi

MIGRATIONS="$(printf '%s
' "$CHANGED" | grep -c 'alembic/versions/' || true)"
say "  ترحيلة  : ${MIGRATIONS:-0}"

# **جدولُ مالٍ يوقف هنا** — ويُقاس في الترحيلات وفي النماذج معاً
MONEY_HITS="$(printf '%s
' "$CHANGED" | grep -E 'alembic/versions/|models/'   | xargs -r git diff "$REMOTE_SHA..$HEAD_SHA" -- 2>/dev/null   | grep -oE "$MONEY_TABLES" | sort -u | tr '
' ' ' || true)"
if [ -n "${MONEY_HITS// /}" ]; then
  say "  مالٌ    : **يمسّ** — $MONEY_HITS"
  die "رفعٌ يمسّ جدولَ مالٍ يقف لإذن المالك (المطلقةُ الثانية). اعرضه ثم أعد التشغيل بـTAXO_MONEY_OK=1."
fi
say "  مالٌ    : لا يمسّ جدولَ مالٍ"

# **طريقُ الرجوع يُعلَن أو لا يبدأ الرفع**
say "  الرجوع  : git -C $REMOTE checkout ${REMOTE_SHA:-<مجهول>} ثم إعادةُ الحاويات"
say "            والنسخةُ في البوّابة ٣ تعيد القاعدةَ إن لزم — دقائقُ معدودة"
[ -n "$REMOTE_SHA" ] || die "لا طريقَ رجوعٍ مقيس (إيداعُ الخادم مجهول) — **لا يبدأ الرفع**."

[ "$ANNOUNCE_ONLY" -eq 1 ] && { say ""; say "✓ إعلانٌ فقط — لم يُرفع شيء."; exit 0; }

# ═══════════════════ ٢) الدفعُ وCI ═══════════════════
say "══ ٢) الدفعُ وCI"
git remote get-url origin >/dev/null 2>&1 || die "لا مستودعَ بعيد — البوّابةُ الثانية لا تُقطع. (انظر §الحاجة في التقرير)"

# **مسحُ ما يُدفع عن سرّ — ووجدانُه يوقف ولا يُنظَّف**: التنظيفُ يخفي أنه كان
# هناك، والتاريخُ يبقى حاملاً له.
# النمطُ في متغيّرٍ مستقلٍّ لا في سطرٍ مُقتبَسٍ مرتين — الاقتباسُ المُعشَّشُ هو
# ما كسر هذا السطرَ أولَ مرة.
SECRET_RE='BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key[[:space:]]*[:=]|secret[[:space:]]*[:=]|Bearer [A-Za-z0-9._-]{20,}'
BENIGN_RE='example|placeholder|getenv|environ|process\.env'
LEAKS="$(git diff "${REMOTE_SHA:-HEAD~1}..$HEAD_SHA" 2>/dev/null | grep -E "^\+" | grep -nE "$SECRET_RE" | grep -vE "$BENIGN_RE" | head -5 || true)"
if [ -n "$LEAKS" ]; then
  say "$LEAKS"
  die "سرٌّ في ما يُدفع — **قف ولا تنظّف**. التاريخُ يبقى حاملاً له، والتنظيفُ يخفي أنه كان."
fi
say "  السرّ   : لا شيءَ في ما يُدفع"

git push origin HEAD || die "تعذّر الدفع."
git push origin --tags || true
say "  الدفع   : تمّ"
die "CI لم يُقس بعد — هذا الحدُّ يُكمَل حين يوجد المستودعُ وأسرارُه (انظر التقرير)."

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

# **ولا `grep -q` في أنبوبٍ تحت `pipefail`** — وهذا وقع مقيساً 2026-08-21:
# `grep -q` يخرج عند أول تطابق، فيتلقّى `gzip` إشارةَ SIGPIPE ويعود بـ141،
# و`pipefail` يجعل الأنبوبَ كلَّه فاشلاً — **فرُفضت نسخةٌ سليمةٌ فيها ٥٧ جدولاً**.
# وأخطرُ ما فيه أنه **سباق**: مع مخرجٍ صغيرٍ ينتهي المُنتِجُ قبل أن يخرج `grep`
# فيمرّ، ومع مخرجٍ كبيرٍ يسقط. فحارسٌ حكمُه يتبدّل بحجم ما يقرأ ليس حارساً.
# و`grep -c` يقرأ حتى النهاية، فلا إشارةَ ولا سباق.
sql_is_a_dump() {
  local header tables
  header=$(gzip -dc "$LOCAL/taxo.sql.gz" | grep -c "PostgreSQL database dump" || true)
  tables=$(gzip -dc "$LOCAL/taxo.sql.gz" | grep -c "^CREATE TABLE" || true)
  say "    (ترويسة: ${header:-0} · جداول: ${tables:-0})"
  [ "${header:-0}" -ge 1 ] && [ "${tables:-0}" -ge 20 ]
}

tar_holds() { [ "$(tar -tzf "$1" 2>/dev/null | grep -c "$2" || true)" -ge 1 ]; }

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
