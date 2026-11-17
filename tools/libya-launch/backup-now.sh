#!/usr/bin/env bash
# نسخةٌ قبل افتتاح ليبيا — البوّابةُ ٣ و٤ من scripts/deploy.sh حرفاً (مستخرَجةٌ آليّاً)، بلا رفع.
set -uo pipefail
HOST=taxo@169.58.207.123; REMOTE='~/taxo'; DEST=/d/taxo-backups
COMPOSE_FILES='-f docker-compose.yml -f docker-compose.prod-tunnel.yml'
say() { printf '%s\n' "$*"; }
die() { printf '\n✗ %s\n' "$*" >&2; exit 1; }
ssh_try() { /c/Windows/System32/OpenSSH/ssh.exe -i "$HOME/.ssh/taxo-contabo" -o IdentitiesOnly=yes -o ConnectTimeout=30 "$HOST" "$@"; }
cd //wsl.localhost/Ubuntu-24.04/home/loly3/prj/TAXO
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOCAL="$DEST/$STAMP"
mkdir -p "$LOCAL" || die "تعذّر إنشاءُ مجلد النسخة: $LOCAL"

say "══ ٣) النسخةُ قبل الرفع — $STAMP"

# **النسخةُ كلُّها في اتصالٍ واحد — لأن الاتصالَ نفسَه محدود** (قرارُ القياس
# 2026-08-22). `ufw` على الخادم يحمل `22/tcp LIMIT IN`، **وحدُّه ستُّ محاولاتٍ
# في ثلاثين ثانية**؛ وهذا السكربتُ كان يفتح أكثرَ من عشرين، **و`ssh_try`
# يضاعفها بإعاداته** — فيحجب الجدارُ الناريُّ من يرفع، ويُقرأ الحجبُ
# «شبكةٌ رديئة». **وقد كُتب ذلك مرتين في تقرير، وكان تشخيصاً بلا قياس.**
#
# **ولا يُمسّ الحدّ**: المطلقةُ الثالثة تمنع إلغاءَ حدٍّ أمنيٍّ أثناء رفعٍ مهما
# أعاق — **والحلُّ أن نطرق أقلَّ لا أن نفتح البابَ أوسع**. و`ControlMaster`
# غيرُ مدعومٍ في ssh ويندوز (قِيس: `getsockname failed: Not a socket`)، فالسبيلُ
# **أمرٌ واحدٌ يُنتج أرشيفاً واحداً** يحمل الأربعةَ.
say "  · الأربعةُ في اتصالٍ واحد…"
ssh_try "cd $REMOTE &&   cat > /tmp/taxo-target-ignore &&   W=\$(mktemp -d) &&   docker compose $COMPOSE_FILES exec -T db pg_dump -U taxo -d taxo --no-owner | gzip -9 > \$W/taxo.sql.gz &&   tar -czhf \$W/env.tar.gz .env &&   ROOT=\$(pwd) && OUT=\$({ docker compose $COMPOSE_FILES config 2>/dev/null | sed -n 's/^ *source: \(\/.*\)/\1/p'; find . -maxdepth 2 -type l -exec readlink -f {} \; 2>/dev/null; } | grep '^/' | grep -v \"^\$ROOT\" | while read -r q; do [ -d \"\$q\" ] && echo \"\$q\" || dirname \"\$q\"; done | sort -u | tr '\n' ' ') &&   { [ -n \"\${OUT// /}\" ] && tar -czhf \$W/outside.tar.gz \$OUT 2>/dev/null || : > \$W/outside.absent; } &&   echo \"\$OUT\" > \$W/outside.list &&   git ls-files --others --exclude-standard | wc -l > \$W/raw.count &&   git ls-files --others --exclude-standard --exclude-from=/tmp/taxo-target-ignore > \$W/untracked.list &&   wc -l < \$W/untracked.list > \$W/untracked.count &&   { [ -s \$W/untracked.list ] && tar -czhf \$W/untracked.tar.gz -T \$W/untracked.list || : > \$W/untracked.absent; } &&   docker compose $COMPOSE_FILES exec -T db psql -U taxo -d taxo -tAc 'SELECT count(*) FROM driver_documents;' 2>/dev/null | tr -d ' \r\n' > \$W/docs.rows; { docker compose $COMPOSE_FILES run --rm --no-deps -T --entrypoint tar backend -czf - -C /app/var/documents . 2>/dev/null > \$W/documents.tar.gz || : > \$W/documents.absent; } &&   tar -cf - -C \$W . && rm -rf \$W" < .gitignore > "$LOCAL/bundle.tar"   || die "تعذّرت النسخةُ — لا رفع."

tar -xf "$LOCAL/bundle.tar" -C "$LOCAL" && rm -f "$LOCAL/bundle.tar"   || die "النسخةُ وصلت ولا تُفتح — لا رفع."

RAW_N="$(tr -d ' 
' < "$LOCAL/raw.count" 2>/dev/null || echo 0)"
UNTRACKED_N="$(tr -d ' 
' < "$LOCAL/untracked.count" 2>/dev/null || echo 0)"
say "    ما خارج الشجرة: $(tr -d '
' < "$LOCAL/outside.list" 2>/dev/null)"
# **وتُعلَن التصفيةُ بأثرها لا بوقوعها**: `--exclude-from` على ملفٍّ فارغٍ
# **ينجح ولا يستبعد شيئاً** — وقعت مقيسةً، ولم يكشفها إلا رقمٌ مطبوع.
if [ "${RAW_N:-0}" = "0" ]; then
  # **وصفرٌ هنا هو الحالُ المقصودةُ لا عطب**: شجرةٌ لا ملفَّ فيها خارجَ git
  # **مشتقّةٌ من الإيداع بالكامل** — وهو ما وُجدت البوّابةُ الرابعةُ لأجله.
  # **وحارسٌ يقرأ بلوغَ الهدف فشلاً** أسوأُ من غيابه: يوقف رفعاً لأن ما قبله نجح.
  say "    غيرُ المتتبَّع: **لا شيء** — الشجرةُ مشتقّةٌ من git بالكامل"
elif [ "${RAW_N:-0}" = "${UNTRACKED_N:-0}" ]; then
  say "    غيرُ المتتبَّع: $UNTRACKED_N — **لم تستبعد التصفيةُ شيئاً** (أوصلت قواعدُ التجاهُل؟)"
else
  say "    غيرُ المتتبَّع: $UNTRACKED_N (استُبعد $((RAW_N - UNTRACKED_N)) مخرجَ بناء)"
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

# **ويُقاس المحتوى لا اسمُ المدخل** (2026-08-22): الفحصُ القديم كان
# `tar_holds … '\.env$'` — **ووصلةٌ رمزيةٌ مدخلٌ اسمُه `.env`**، فمرّ أرشيفٌ
# لا سرَّ فيه ووُصف «محتواه صحيح». **فالاسمُ يقول إن الشيءَ مذكور، والمحتوى
# يقول إنه هناك** — وهي قاعدةُ «حقلٌ يُعلن ولا يقيس» في ثوب النسخة.
#
# **والعتبةُ أسطرٌ لا بايتات**: أرشيفٌ فيه وصلةٌ يزن مئةَ بايتٍ ويقرأه من يعدّ
# الأحجامَ سليماً.
env_carries_secrets() {
  local lines
  lines=$(gzip -dc "$LOCAL/env.tar.gz" 2>/dev/null | tar -xO 2>/dev/null | grep -cE '^[A-Z][A-Z0-9_]+=.' || true)
  say "    (أسطرُ إعدادٍ حقيقية: ${lines:-0})"
  [ "${lines:-0}" -ge 5 ]
}

check taxo.sql.gz "القاعدة" sql_is_a_dump
check env.tar.gz  "الأسرار" env_carries_secrets
# **وما خارج الشجرة يُقاس بما لا يُعاد بناؤه، لا بأنه غيرُ فارغ** (قرارُ
# المالك 2026-08-22): القائمةُ محسوبةٌ (`docker compose config` + هدفُ كلِّ
# وصلة) **ولا مسارَ فيها مكتوبٌ بيد** — لكنّ حسابَها قد يضيق يوماً بتغيُّرِ
# تثبيتٍ في compose، **فيمرّ أرشيفٌ غيرُ فارغٍ وقد سقط منه ما يهمّ**.
#
# **وأخطرُ ما فيه بيانُ اعتماد النفق ومعرِّفُه**: ضياعُهما بلا نسخةٍ يعني
# **إعادةَ بناء النفق يدوياً** — وأربعةُ نطاقاتٍ تسقط حتى يفعل إنسانٌ ذلك.
# **فيُسمَّيان في الفحص لا في الجمع**: القائمةُ تُحسب، **والحدُّ الأدنى
# يُشترط**.
outside_carries_the_tunnel() {
  local names
  names=$(tar -tzf "$LOCAL/outside.tar.gz" 2>/dev/null | grep -cE 'cloudflared/.*\.json$|tunnel-id$' || true)
  say "    (بيانُ النفق ومعرِّفُه: ${names:-0} من ٢)"
  [ "${names:-0}" -ge 2 ]
}
if [ -f "$LOCAL/outside.tar.gz" ]; then
  check outside.tar.gz "ما خارج الشجرة" outside_carries_the_tunnel
fi
if [ -f "$LOCAL/untracked.tar.gz" ]; then
  check untracked.tar.gz "غيرُ المتتبَّع" tar_holds "$LOCAL/untracked.tar.gz" "."
fi
# **ووثائقُ الكباتن كانت تُنسخ من مسارِ مضيفٍ فارغ — والفحصُ يُخضِّره**
# (عطبٌ قِيس ٢٠٢٦-٠٩-٠٥، وعاش منذ بُنيت هذه البوّابة).
#
# **المقيس**: `driver_documents` في قاعدة الإنتاج **٣٧ صفّاً**، و
# `backend/var/documents` على قرص المضيف **صفرُ ملفّ** — لأن الوثائق تسكن
# **مجلَّداً مسمّى** (`taxo_documents` مُثبَّتاً على `/app/var/documents`)،
# لا مسارَ مضيفٍ مربوطاً. **فكان الأرشيفُ يحمل المجلَّدَ وحدَه، ١٢٤ بايت.**
#
# **وكان الفحصُ يقول «محتواه صحيح»** لأنه `tar_holds … "documents"` —
# **يطابق اسمَ المدخل**. وهو بحرفه الدرسُ المكتوبُ فوقه لأجل `.env`:
# «الاسمُ يقول إن الشيءَ مذكور، والمحتوى يقول إنه هناك». **كُتب للأسرار ولم
# يُطبَّق على الوثائق** — فعاش سبعةَ عشرَ يوماً يُعلِن خُضرةً وهو أعمى،
# **ووثائقُ هويةِ كباتنَ حقيقيّين بلا نسخةٍ طوالها**.
#
# **والفحصُ الآن يعدّ الملفّات ويقابلها بصفوف الجدول**: أرشيفٌ بلا ملفٍّ
# وجدولٌ فيه صفوفٌ **يُسقط الرفع**. **وصفرٌ في الطرفين حالٌ صحيحة** — تركيبٌ
# جديدٌ لا وثيقةَ فيه، **وحارسٌ يقرأ بلوغَ الحالِ الصحيحةِ فشلاً أسوأُ من
# غيابه**.
documents_carry_files() {
  local files rows
  files=$(tar -tzf "$LOCAL/documents.tar.gz" 2>/dev/null | grep -vc '/$' || true)
  rows=$(tr -d ' \r\n' < "$LOCAL/docs.rows" 2>/dev/null || echo "")
  say "    (ملفّاتٌ في الأرشيف: ${files:-0} · وصفوفُ driver_documents: ${rows:-<لم يُقرأ>})"
  # **رأسُ الجدولِ غيرُ مقروءٍ ⇒ لا يُقاس ⇒ لا يُخضَّر** — «غيابُ أداة القياس
  # يوقف ولا يُقرأ سلامة».
  [ -n "$rows" ] || return 1
  [ "$rows" -eq 0 ] && return 0
  [ "${files:-0}" -ge 1 ]
}
if [ -f "$LOCAL/documents.tar.gz" ]; then
  check documents.tar.gz "الوثائق" documents_carry_files
fi

[ "$FAIL" -eq 0 ] || die "النسخةُ لم تُحقَّق — **لا رفع**. قف واسأل المالك."

say "  ⇒ النسخةُ المحقَّقة: $LOCAL"
