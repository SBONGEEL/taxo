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
# **عميلُ ssh يُصرَّح ولا يُثبَّت** (قرارُ المالك 2026-08-21): على هذا الجهاز
# عميلان — `/usr/bin/ssh` في Git Bash (مقبسُ يونكس) و`ssh.exe` لويندوز (أنبوبٌ
# مسمّى) — **ولا يتفاهمان مع وكيلٍ واحد**. فمن فعّل خدمةَ ويندوز يوجّه هنا:
#
#   TAXO_SSH=/c/Windows/System32/OpenSSH/ssh.exe bash scripts/deploy.sh …
SSH="${TAXO_SSH:-ssh}"
SSH_OPTS=(-o StrictHostKeyChecking=yes -i "${TAXO_SSH_KEY:-$HOME/.ssh/taxo-contabo}")

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

REMOTE_SHA="$("$SSH" "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && git rev-parse HEAD 2>/dev/null" || true)"
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

# **جدولُ مالٍ يوقف هنا — ويُقاس ما سيقع لا ما في المدى** (صُحّح 2026-08-22).
#
# **كانت تقيس مدى الإيداعات**: أيُّ إيداعٍ بين الخادم وHEAD مسَّ ملفَّ ترحيلةٍ
# أو نموذجاً فيه اسمُ جدولِ مال. **وقِيس أنها تصيح حيث لا خطر**: شجرةُ الخادم
# متأخّرةٌ ٧٣ التزاماً، والترحيلتان المُبلَّغُ عنهما **مطبَّقتان على الإنتاج
# سلفاً** (`alembic_version = 0052`)، **والأمرُ لا يرسل ملفَّ خلفيةٍ واحداً**.
#
# **وبوّابةٌ تصيح حيث لا خطر تعلّم مشغّلَها التجاوز** — فتُفرَّغ المطلقةُ من
# داخلها. **وذلك أخطرُ من بوّابةٍ غائبة**: الغائبةُ تتركك حيث كنت، وهذه
# **تُفقد الثقةَ بصياحها حين يكون في محلّه**.
#
# **فالقياسُ صار سؤالين لا واحد:**
#   ١) أثمّة ترحيلةٌ **معلَّقة**؟ — رأسُ القاعدة على الخادم مقابل الشجرة.
#   ٢) وهل ما يُرسَل **في هذه الدفعة** يمسّ نموذجاً أو ترحيلة؟
# **وسكوتُ الاثنين معاً هو الجواب**، وإلّا وقف.
PENDING="$("$SSH" "${SSH_OPTS[@]}" "$HOST"   "cd $REMOTE && docker compose exec -T db psql -U taxo -d taxo -tAc 'SELECT version_num FROM alembic_version;' 2>/dev/null"   | tr -d '
 ' || true)"
TREE_HEAD="$(ls backend/alembic/versions/ | sort | tail -1 | cut -d_ -f1)"
if [ -z "$PENDING" ]; then
  say "  ترحيلة  : **رأسُ القاعدة غيرُ مقروء** — يُعامَل كأن ثمّة معلَّقاً"
  MIGRATION_PENDING=1
elif [ "$PENDING" = "$TREE_HEAD" ]; then
  say "  ترحيلة  : لا معلَّقَ — القاعدةُ عند $PENDING والشجرةُ عند $TREE_HEAD"
  MIGRATION_PENDING=0
else
  say "  ترحيلة  : **معلَّقة** — القاعدةُ عند $PENDING والشجرةُ عند $TREE_HEAD"
  MIGRATION_PENDING=1
fi

# **ما يُرسَل في هذه الدفعة** — الوسائطُ نفسُها لا مدى الإيداعات
SENT="$(printf '%s
' "$@" | tr -d ' ')"
SENT_HITS="$(git diff "${REMOTE_SHA:-HEAD~1}..$HEAD_SHA" --name-only -- $SENT 2>/dev/null   | grep -E 'alembic/versions/|models/' || true)"

MONEY_HITS=""
if [ "$MIGRATION_PENDING" -eq 1 ] || [ -n "$SENT_HITS" ]; then
  MONEY_HITS="$(printf '%s
' "$CHANGED" | grep -E 'alembic/versions/|models/'     | xargs -r git diff "$REMOTE_SHA..$HEAD_SHA" -- 2>/dev/null     | grep -oE "$MONEY_TABLES" | sort -u | tr '
' ' ' || true)"
fi
if [ -n "${MONEY_HITS// /}" ] && [ "${TAXO_MONEY_OK:-0}" != "1" ]; then
  say "  مالٌ    : **يمسّ** — $MONEY_HITS"
  die "رفعٌ يمسّ جدولَ مالٍ يقف لإذن المالك (المطلقةُ الثانية). اعرضه ثم أعد التشغيل بـTAXO_MONEY_OK=1."
fi
if [ -n "${MONEY_HITS// /}" ]; then
  say "  مالٌ    : **يمسّ** — $MONEY_HITS · **مأذونٌ صراحةً** (TAXO_MONEY_OK=1)"
else
  say "  مالٌ    : لا ترحيلةَ معلَّقةٌ ولا ملفَّ مالٍ في ما يُرسَل"
fi

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
# **السرُّ قيمةٌ لا اسمُ حقل** (صُحّح 2026-08-22): كان النمطُ يمسك
# `secret[[:space:]]*[:=]` مجرَّداً، **فأوقف الرفعَ على سطرِ توثيقٍ يقول
# `secret=True`** — وهو اسمُ خاصيّةٍ لا سرّ. **وبوّابةٌ تصيح حيث لا خطر تعلّم
# مشغّلَها التجاوز** (الدرسُ المسجَّل في الفهرس قبل ساعة، ووقع ثانيةً في
# البوّابة التالية).
#
# **فصار يشترط قيمةً تشبه اعتماداً**: ستةَ عشرَ محرفاً فأكثر من أبجدية
# الرموز. **ولا يُضعِف الحارس**: رمزٌ حقيقيٌّ لا يكون `True` ولا `bool`، ومفتاحٌ
# خاصٌّ و`Bearer` يبقيان كما هما.
SECRET_RE='BEGIN [A-Z ]*PRIVATE KEY|(api[_-]?key|secret|token|password)[[:space:]]*[:=][[:space:]]*"?'"'"'?[A-Za-z0-9_/+.-]{16,}|(password|passwd|pwd)[[:space:]]*[:=][[:space:]]*"[^"]{12,}"|Bearer [A-Za-z0-9._-]{20,}'
# **وما يُنتج سرّاً أو يقرؤه ليس سرّاً** (وُسِّع 2026-08-22): وقعت ثلاثةُ
# بلاغاتٍ كاذبةٍ متتالية — `secret=True` في توثيق، و`token = secrets.token_urlsafe(32)`
# **وهو مولِّدٌ لا قيمة**، و`const token = env.GITHUB_TAXO_TOKEN` **وهو قراءةٌ
# من بيئة**. **وكلُّ بلاغٍ كاذبٍ يدفع نحو التجاوز** — والدرسُ مسجَّلٌ مرتين
# في الفهرس، فلا يُترك يتكرر ثالثةً.
BENIGN_RE='example|placeholder|getenv|environ|process\.env|secrets\.|token_urlsafe|randbytes|uuid|env\.[A-Za-z_]|ENV\[|import\.meta|<[a-z]|\$\{'
LEAKS="$(git diff "${REMOTE_SHA:-HEAD~1}..$HEAD_SHA" 2>/dev/null | grep -E "^\+" | grep -nE "$SECRET_RE" | grep -vE "$BENIGN_RE" | head -5 || true)"
if [ -n "$LEAKS" ]; then
  say "$LEAKS"
  die "سرٌّ في ما يُدفع — **قف ولا تنظّف**. التاريخُ يبقى حاملاً له، والتنظيفُ يخفي أنه كان."
fi
say "  السرّ   : لا شيءَ في ما يُدفع"

git push origin HEAD || die "تعذّر الدفع."
git push origin --tags || true
say "  الدفع   : تمّ"

# **CI على استنساخٍ نظيف — ويُنتظر، ولا يُقرأ آخرُ تشغيلٍ عابر.**
#
# **وكان هنا سطرٌ يموت** بحجّة «حتى يوجد المستودعُ وأسرارُه»، **وقد وُجدا** —
# فبقي يمنع البابَ الذي كُتب ليحرسه، **ويدفع من يجده إلى طريقٍ حوله**. وهو
# الصنفُ المسجَّل في `CLAUDE.md`: شرطٌ زالت علّتُه ولم يُنزَع.
#
# **والتشغيلُ يُطابَق بالإيداع لا بالأحدثية**: `head_sha` هو الشرط — فتشغيلٌ
# أخضرُ لإيداعٍ آخرَ لا يقول شيئاً عمّا نرفعه، **وهو بالضبط ما تحرسه البوّابةُ
# الخامسة حين تقارن إيداعَ الخادم بإيداع CI**.
say "  CI      : يُنتظر التشغيلُ لإيداع ${HEAD_SHA:0:8}…"

# **بالرمز الدقيق لا بـ`gh`** (المواصفة §27.9): `gh` يستعمل ما دخل به صاحبُه —
# وقد يكون رمزَ حسابٍ واسعاً، وهو بعينه ما ابتعد عنه قرارُ المالك. وهنا نداءٌ
# قرائيٌّ واحدٌ بالرمز المحصور في هذا المستودع.
#
# **وغيابُ الرمز يوقف ولا يُسكت عنه**: بلا قراءةِ CI **لا تُقطع البوّابة**،
# وتخطّيها بحجّة «تعذّرت القراءة» هو الطريقُ حول الباب.
[ -n "${GITHUB_TAXO_TOKEN:-}" ] || die "لا رمزَ لقراءة CI (\$GITHUB_TAXO_TOKEN) — البوّابةُ الثانيةُ لا تُقطع."
REPO="${TAXO_GITHUB_REPO:-SBONGEEL/taxo}"

ci_state() { # يطبع: <الحال> <الرابط> لتشغيل هذا الإيداع وحدَه
  curl -sS -H "Authorization: Bearer $GITHUB_TAXO_TOKEN"        -H "Accept: application/vnd.github+json"        "https://api.github.com/repos/$REPO/actions/runs?head_sha=$HEAD_SHA&per_page=10"   | python3 -c "
import json,sys
try: runs = json.load(sys.stdin).get('workflow_runs', [])
except Exception: runs = []
# **التشغيلُ يُطابَق بالإيداع لا بالأحدثية**: أخضرُ لإيداعٍ آخرَ لا يقول شيئاً
# عمّا نرفعه — وهو ما تحرسه البوّابةُ الخامسة حين تقارن إيداعَ الخادم بـCI.
runs = [r for r in runs if r.get('name') == 'CI'] or runs
print('' if not runs else f\"{runs[0].get('conclusion') or runs[0].get('status')} {runs[0].get('html_url','')}\")
" 2>/dev/null
}

CI_STATE=""; CI_URL=""
for _ in $(seq 1 120); do   # ٤٠ دقيقةً بحدٍّ أقصى — مهلةُ الوظيفتين ٣٠+٢٠
  read -r CI_STATE CI_URL <<<"$(ci_state)"
  case "$CI_STATE" in
    success) break ;;
    failure|cancelled|timed_out|action_required|startup_failure)
      die "CI أحمرُ ($CI_STATE) — **يقف كلُّ شيءٍ هنا**. التشغيل: ${CI_URL:-<لا رابط>}" ;;
  esac
  sleep 20
done
[ "$CI_STATE" = "success" ] || die "CI لم يخضرَّ في المهلة (آخرُ حالٍ: ${CI_STATE:-<لا تشغيلَ لهذا الإيداع>}). التشغيل: ${CI_URL:-—}"
say "  CI      : أخضر — ${CI_URL:-}"

# **`STAMP` و`LOCAL` لم يكونا معرَّفَين قط** (صُحّح 2026-08-22): نصفُ البابِ
# هذا كان **خلف `die` لا يُتجاوَز**، فلم يُشغَّل مرةً واحدة — **وكودٌ لا
# يُشغَّل لا يُختبَر**. وهو نفسُه صنفُ «شرطٍ زالت علّتُه»: السطرُ الميتُ لم
# يحرس شيئاً، **وأخفى تحته نصفَ بابٍ ناقص**.
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOCAL="$DEST/$STAMP"
mkdir -p "$LOCAL" || die "تعذّر إنشاءُ مجلد النسخة: $LOCAL"

say "══ ٣) النسخةُ قبل الرفع — $STAMP"

# القاعدة: تفريغٌ مضغوطٌ يُكتب إلى المخرج القياسي فيصل هنا مباشرةً، فلا يبقى
# على الخادم نسخةٌ ثانيةٌ تُنسى ولا يُملأ قرصُه.
say "  · القاعدة…"
"$SSH" "${SSH_OPTS[@]}" "$HOST" \
  "cd $REMOTE && docker compose exec -T db pg_dump -U taxo -d taxo --no-owner | gzip -9" \
  > "$LOCAL/taxo.sql.gz" || die "تعذّر تفريغُ القاعدة — لا رفع."

say "  · الأسرار ومجلد الوثائق…"
"$SSH" "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && tar -czf - .env" \
  > "$LOCAL/env.tar.gz" || die "تعذّرت نسخةُ .env — لا رفع."
# **الوثائقُ قد لا تكون موجودةً بعدُ على إنتاجٍ جديد**، والغيابُ يُقال ولا يُسكت
if "$SSH" "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && test -d backend/var/documents"; then
  "$SSH" "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && tar -czf - backend/var/documents" \
    > "$LOCAL/documents.tar.gz" || die "تعذّرت نسخةُ الوثائق — لا رفع."
else
  say "    (لا مجلدَ وثائقَ على الخادم بعد — يُسجَّل ولا يُسكت عنه)"
  : > "$LOCAL/documents.absent"
fi

say "══ ٤) التحقّق — نسخةٌ لم تُفتح ليست نسخة"
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

say "══ ٥) الرفع"

# **والحزمُ يسحبها الخادمُ من أثر الإصدار — لا تُرسل من هنا** (قرارُ المالك
# 2026-08-21). البوّابةُ الرابعةُ تقول «الخادمُ يسحب نفسَ ما خضّره CI»،
# **وإرسالُ حزمةٍ من جهازٍ ينقض ذلك من داخل الباب**: تمرّ بالبوّابات وهي لم
# تُبنَ فيما خضّرته.
#
# **وبلا وسمٍ لا حزمَ في هذه الدفعة، ويُقال صراحةً**: رفعُ كودٍ بلا إصدارٍ
# لا يُقرأ نشرةً للحزم.
TAG="$(git describe --tags --exact-match 2>/dev/null || true)"
if [ -n "$TAG" ]; then
  [ -n "${GITHUB_TAXO_TOKEN:-}" ] || die "لا رمزَ لسحب أثر الإصدار — والحزمُ لا تُرسل من هنا."
  say "  الحزم   : الخادمُ يسحب أثرَ $TAG"
  tar -cf - scripts/pull-release.sh | "$SSH" "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && tar -xf -"
  "$SSH" "${SSH_OPTS[@]}" "$HOST"     "cd $REMOTE && bash scripts/pull-release.sh '$TAG' '${TAXO_GITHUB_REPO:-SBONGEEL/taxo}' '$GITHUB_TAXO_TOKEN'"     || die "تعذّر سحبُ أثر $TAG على الخادم — والنسخةُ في $LOCAL"
else
  say "  الحزم   : لا وسمَ لهذه الدفعة — **لم تُنشر حزمة**"
fi

tar -cf - "$@" | "$SSH" "${SSH_OPTS[@]}" "$HOST" "cd $REMOTE && tar -xf -" \
  || die "فشل الرفعُ — والنسخةُ في $LOCAL"
for p in "$@"; do say "  ✓ $p"; done

say ""
say "✓ رُفع بعد نسخةٍ محقَّقة."
say "  النسخة : $LOCAL"
say "  وقتُها : $STAMP (UTC)"
say "  حجمُها : $(du -sh "$LOCAL" | cut -f1)"
say ""
say "  **يُذكر هذا الثلاثيُّ في تقرير الرفع** (قاعدةُ CLAUDE.md الأولى)."
