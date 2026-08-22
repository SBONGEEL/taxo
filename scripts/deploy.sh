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
#   ٣ النسخة    — القاعدةُ و`.env` والوثائقُ **وما لا يعيده السحب**، خارج
#                 الخادم، **تُفتح ويُقاس محتواها**
#   ٤ الرفع     — **الخادمُ يسحب من GitHub** نفسَ إيداعِ CI · أمرٌ واحد · ترحيلة
#   ٥ التحقّق   — إيداعٌ · ترحيلةٌ · أربعةُ أعمدةٍ للثلاثة · متصفّحٌ · سجلّ
#
# ═════════════════════════════════════════════════════════════════════════════
# **وترتيبُها ترتيبُ اعتمادٍ لا ترتيبَ سرد — فهو مُلزِمٌ لا مقترَح.**
#
# كلُّ بوّابةٍ **تستهلك ما تُنتجه التي قبلها، وتهدم ما تحتاجه التي قبلها**:
#
#   ٢ تحتاج شجرةً نظيفةً أعلنتها ١ · ٣ تنسخ **الحالَ التي ستهدمها ٤** ·
#   ٤ تحتاج نسخةً خضراءَ من ٣ **ولا تبدأ قبلها** · ٥ تقيس ما فعلته ٤.
#
# **فتقديمُ فعلٍ من بوّابةٍ متأخّرةٍ يُسقط بوّابةً سابقة** — ووقع مقيساً
# (2026-08-22): أُزيحت الملفاتُ المتصادمةُ **قبل** البوّابة الثالثة، **وفيها
# `docker-compose.prod-tunnel.yml` نفسُه**، فسقطت بوّابةُ النسخة لأن كلَّ أمرِ
# compose يذكر ملفاتِه **ولم يعد الملفُّ هناك**. والحاوياتُ لم تتأثر — **لكن
# البابَ صار بلا مقبض**.
#
# **فلا يُقدَّم فعلٌ ولا يُؤخَّر**، ولو بدا أن ترتيبَه لا يهمّ: **الاعتمادُ
# غيرُ مرئيٍّ في السرد**، ولا يظهر إلا حين يسقط.
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
# ─────────────────────────────────────────────────────────────────────────────
# **تصحيحٌ يُقرأ قبل ما تحته** (2026-08-22): **هذا الرأسُ كان يعدّ خمساً
# ويطبّق ثلاثاً ونصفاً** — وهو الجدولُ الأحمرُ في أخطر ملفٍّ في المستودع.
#
# **ما كان**: ترقيمُه ١ إعلان · ٢ دفعٌ وCI · ٣ نسخة · ٤ **تحقّقُ النسخة** ·
# ٥ `tar -cf - "$@" | ssh … tar -xf -`. أي:
#
#   - **البوّابةُ الرابعةُ لم تكن مبنيّةً البتّة**: لا سحبَ من GitHub، ولا
#     `alembic upgrade`، ولا إعادةَ حاويات. **بل كانت تفعل ما تمنعه نصّاً** —
#     «لا من جهاز أحد» — فتدفع ملفاتٍ من قرص المطوّر.
#   - **والبوّابةُ الخامسةُ لم يكن لها وجودٌ أصلاً**، واسمُها أُعطي لتحقّق
#     النسخة (وهو جزءٌ من الثالثة).
#   - **والسطرُ أعلاه كان يكذب**: `bash scripts/deploy.sh` بلا وسائطَ يبني
#     أرشيفاً فارغاً ويموت، لأن ما يُرسَل هو `"$@"` لا HEAD.
#
# **وثمنُه مقيسٌ لا مُقدَّر**: شجرةُ الإنتاج حملت **٨٣ ملفاً خارج الإيداع**
# (منها الترحيلتان `0051` و`0052` **غيرُ متتبَّعتين**)، والقاعدةُ عند ترحيلةٍ
# لا وجودَ لها إلا كملفٍّ على القرص — **فحالُ الإنتاج لم تكن مشتقّةً من git
# يوماً**، وهو بعينه ما وُجدت البوّابةُ الرابعةُ لتمنعه.
#
# **والبوّابتان مبنيّتان الآن كما هما مكتوبتان**، والسحبُ بمفتاح نشرٍ
# **مقصورٍ على هذا المستودع وللقراءة وحدَها** — لا رمزٍ واسع.
set -euo pipefail

HOST="${TAXO_DEPLOY_HOST:-taxo@169.58.207.123}"
REMOTE="${TAXO_REMOTE_PROJECT:-~/taxo}"
DEST="${TAXO_BACKUP_DEST:-/d/taxo-backups}"
# **عميلُ ssh يُقاس ولا يُوصف** (قرارُ المالك 2026-08-22).
#
# على هذا الجهاز عميلان — `/usr/bin/ssh` في Git Bash (مقبسُ يونكس) و`ssh.exe`
# لويندوز (أنبوبٌ مسمّى) — **ولا يتفاهمان مع وكيلٍ واحد**. فمفتاحٌ مضافٌ إلى
# وكيل ويندوز **لا يراه عميلُ Git Bash**، والنتيجةُ `Permission denied
# (publickey)` عند البوّابة الأولى.
#
# **وكان هذا سطرَ تعليقٍ يقول «وجِّه `TAXO_SSH` بيدك» — فوقع خلافُه**
# (2026-08-22): كاتبُ السطر نفسُه شغّل السكربتَ بلا توجيهٍ فسقط، **وهو
# الدرسُ الذي أنشأ فهرسَ الحرّاس**: المكتوبُ لا يُطبَّق، والحارسُ يُطبَّق.
#
# **فصار يُختار بالقياس**: إن كان لوكيل ويندوز مفاتيحُ حيّة، فعميلُه هو الذي
# يفتح الباب. **ويُقاس الوكيلُ لا وجودُ الملفّ** — `ssh.exe` موجودٌ على كلِّ
# ويندوز، ووجودُه لا يقول إن فيه مفتاحاً؛ **و`ssh-add -l` هو الذي يقول**.
# والتصريحُ يبقى فوق القياس لمن يريد غيرَه.
_pick_ssh() {
  [ -n "${TAXO_SSH:-}" ] && { printf '%s' "$TAXO_SSH"; return; }
  local win=/c/Windows/System32/OpenSSH/ssh.exe
  local agent=/c/Windows/System32/OpenSSH/ssh-add.exe
  if [ -x "$win" ] && [ -x "$agent" ] && "$agent" -l >/dev/null 2>&1; then
    printf '%s' "$win"
    return
  fi
  printf 'ssh'
}
SSH="$(_pick_ssh)"

# **ملفّاتُ compose تُصرَّح كلُّها في كلِّ أمر** (البوّابةُ الرابعة، وفخٌّ وقع
# مقيساً مرتين): أمرٌ بملفٍّ ناقصٍ يعيد الحاويةَ **بلا `CORS_ORIGINS`** فيقف
# الهاتفان على «الشبكة ضعيفة» بينما `curl` يجيب ٢٠٠ من الجهاز.
#
# **والمجموعةُ مقيسةٌ لا مفترَضة** (2026-08-22): `prod-tunnel` وحدَه يعرّف
# `landing` **و**`cloudflared` معاً، وهو المطابقُ للحاويات العاملة على الخادم.
# و`docker-compose.tunnel.yml` نفقُ **جهاز المالك** لا الإنتاج.
COMPOSE_FILES="${TAXO_COMPOSE_FILES:--f docker-compose.yml -f docker-compose.prod-tunnel.yml}"
# **واتصالٌ يصمد** (أُضيف بالقياس 2026-08-22): سقطت بوّابةُ النسخة مرتين بـ
# `Connection timed out` **بعد أن نجح ما قبلها بثوانٍ** — أي أن الخادمَ حيٌّ
# والقناةَ تتقطّع. **وتعذُّرُ القياس ليس نتيجةَ قياس**، فبوّابةٌ تُسقط رفعاً
# لأن حزمةً ضاعت في الطريق تعلّم مشغّلَها أن يعيد بلا قراءة.
#
# `ServerAliveInterval` يمنع قتلَ جلسةٍ صامتةٍ أثناء `pg_dump` طويل،
# و`ConnectTimeout` يجعل الفشلَ سريعاً بدل تعليقٍ لا ينتهي.
SSH_OPTS=(-o StrictHostKeyChecking=yes -o ConnectTimeout=20
          -o ServerAliveInterval=15 -o ServerAliveCountMax=8
          -i "${TAXO_SSH_KEY:-$HOME/.ssh/taxo-contabo}")

# **وما يتقطّع يُعاد ثلاثاً قبل أن يُقرأ فشلاً** — والإعادةُ للقراءات ونقلِ
# النسخة وحدَها، **لا لِما يكتب على الإنتاج**: أمرٌ يكتب يُعاد مرةً واحدةً
# فيصير فعلين.
ssh_try() {
  local n=0
  until _ssh "$@"; do
    n=$((n+1)); [ "$n" -ge 3 ] && return 1
    # **والإعادةُ بعد الحدِّ لا قبله**: `ufw` يحجب ستّاً في ثلاثين ثانية،
    # فإعادةٌ سريعةٌ **تُطيل الحجبَ الذي تحاول تجاوزه**.
    say "    (انقطاعٌ — إعادةٌ $n/3 بعد ٣٥ ثانية)"; sleep 35
  done
}

# **كلُّ اتصالٍ يُباعَد عمّا قبله — والحدُّ مقروءٌ من الخادم لا مُقدَّر**
# (2026-08-22): `ufw` يحمل `22/tcp LIMIT IN`، **وقاعدتُه ستُّ محاولاتٍ في
# ثلاثين ثانية**. وهذا الملفُّ يفتح أكثرَ من عشرة، **فيحجبه الجدارُ في منتصف
# رفعٍ ويُقرأ الحجبُ عطباً في الشبكة**.
#
# **ولا يُمسّ الحدّ** (المطلقةُ الثالثة): يُطرق أقلَّ، وما بقي **يُباعَد**.
# وستُّ ثوانٍ بين اتصالين تُبقي المعدَّلَ تحت الحدِّ مهما طال السكربت.
_LAST_SSH=0
_ssh() {
  local now gap
  now=$(date +%s); gap=$(( now - _LAST_SSH ))
  [ "$gap" -lt 6 ] && sleep $(( 6 - gap ))
  _LAST_SSH=$(date +%s)
  "$SSH" "${SSH_OPTS[@]}" "$HOST" "$@"
}

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

REMOTE_SHA="$(_ssh "cd $REMOTE && git rev-parse HEAD 2>/dev/null" || true)"
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
PENDING="$(_ssh   "cd $REMOTE && docker compose $COMPOSE_FILES exec -T db psql -U taxo -d taxo -tAc 'SELECT version_num FROM alembic_version;' 2>/dev/null"   | tr -d '
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
ssh_try "cd $REMOTE &&   cat > /tmp/taxo-target-ignore &&   W=\$(mktemp -d) &&   docker compose $COMPOSE_FILES exec -T db pg_dump -U taxo -d taxo --no-owner | gzip -9 > \$W/taxo.sql.gz &&   tar -czhf \$W/env.tar.gz .env &&   ROOT=\$(pwd) && OUT=\$({ docker compose $COMPOSE_FILES config 2>/dev/null | sed -n 's/^ *source: \(\/.*\)/\1/p'; find . -maxdepth 2 -type l -exec readlink -f {} \; 2>/dev/null; } | grep '^/' | grep -v \"^\$ROOT\" | while read -r q; do [ -d \"\$q\" ] && echo \"\$q\" || dirname \"\$q\"; done | sort -u | tr '\n' ' ') &&   { [ -n \"\${OUT// /}\" ] && tar -czhf \$W/outside.tar.gz \$OUT 2>/dev/null || : > \$W/outside.absent; } &&   echo \"\$OUT\" > \$W/outside.list &&   git ls-files --others --exclude-standard | wc -l > \$W/raw.count &&   git ls-files --others --exclude-standard --exclude-from=/tmp/taxo-target-ignore > \$W/untracked.list &&   wc -l < \$W/untracked.list > \$W/untracked.count &&   tar -czhf \$W/untracked.tar.gz -T \$W/untracked.list &&   { [ -d backend/var/documents ] && tar -czf \$W/documents.tar.gz backend/var/documents || : > \$W/documents.absent; } &&   tar -cf - -C \$W . && rm -rf \$W" < .gitignore > "$LOCAL/bundle.tar"   || die "تعذّرت النسخةُ — لا رفع."

tar -xf "$LOCAL/bundle.tar" -C "$LOCAL" && rm -f "$LOCAL/bundle.tar"   || die "النسخةُ وصلت ولا تُفتح — لا رفع."

RAW_N="$(tr -d ' 
' < "$LOCAL/raw.count" 2>/dev/null || echo 0)"
UNTRACKED_N="$(tr -d ' 
' < "$LOCAL/untracked.count" 2>/dev/null || echo 0)"
say "    ما خارج الشجرة: $(tr -d '
' < "$LOCAL/outside.list" 2>/dev/null)"
# **وتُعلَن التصفيةُ بأثرها لا بوقوعها**: `--exclude-from` على ملفٍّ فارغٍ
# **ينجح ولا يستبعد شيئاً** — وقعت مقيسةً، ولم يكشفها إلا رقمٌ مطبوع.
if [ "${RAW_N:-0}" = "${UNTRACKED_N:-0}" ]; then
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
if [ -f "$LOCAL/outside.tar.gz" ]; then
  check outside.tar.gz "ما خارج الشجرة" tar_holds "$LOCAL/outside.tar.gz" "."
fi
if [ -f "$LOCAL/untracked.tar.gz" ]; then
  check untracked.tar.gz "غيرُ المتتبَّع" tar_holds "$LOCAL/untracked.tar.gz" "."
fi
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
  tar -cf - scripts/pull-release.sh | _ssh "cd $REMOTE && tar -xf -"
  _ssh     "cd $REMOTE && bash scripts/pull-release.sh '$TAG' '${TAXO_GITHUB_REPO:-SBONGEEL/taxo}' '$GITHUB_TAXO_TOKEN'"     || die "تعذّر سحبُ أثر $TAG على الخادم — والنسخةُ في $LOCAL"
else
  say "  الحزم   : لا وسمَ لهذه الدفعة — **لم تُنشر حزمة**"
fi

# **الكودُ يُسحب بالإيداع — أمرٌ واحدٌ يفعل كلَّ شيء** (البوّابةُ الرابعة).
#
# **و`fetch` ثم `checkout <sha>` لا `pull`**: `pull` يدمج ما على الفرع
# **وقتَ التنفيذ**، فيمكن أن ينزل غيرُ الذي خضّره CI إن دُفع شيءٌ في الأثناء.
# **والإيداعُ بعينه هو العقد.**
#
# **ولا `--force` ولا `clean`**: شجرةٌ متّسخةٌ **تُعرض ولا تُداس**. وقد قِيست
# في 2026-08-22 (٨٣ ملفاً، صفرٌ منها يختفي بالسحب) — **والقياسُ قبل الدوس
# شرطٌ لا تفصيل**، فما يُداس لا يُعرف أنه كان.
say "  الكود   : الخادمُ يسحب ${HEAD_SHA:0:8} من GitHub"

# **وما يتصادم يُزاح ولا يُداس — وهنا لا قبل النسخة** (2026-08-22).
#
# `git checkout` **يرفض** أن يدوس ملفاً غيرَ متتبَّعٍ يحمل الهدفُ مساراً مثلَه،
# **وذلك صوابُه لا عيبُه**. وشجرةُ الإنتاج حملت ٣٣ ملفاً كهذا — دُفعت بـtar
# قبل أن تُودَع، فصار للمسار الواحد نسختان: واحدةٌ على القرص وأخرى في git.
#
# **والإزاحةُ موضعُها هنا، بعد أن تخضرَّ النسخة**: أُزيحت مرةً **قبل** البوّابة
# الثالثة (2026-08-22) فذهب معها `docker-compose.prod-tunnel.yml` نفسُه —
# **فسقطت بوّابةُ النسخة لأن أمرَ compose بلا ملفّه**. والحاوياتُ لم تتأثر
# (العاملُ لا يقرأ الملفَّ ثانيةً)، **لكن البابَ صار بلا مقبض**.
#
# **ولا يُزاح إلا ما يتصادم** (قرارُ المالك 2026-08-22، بصيغته): **ما لا مسارَ
# له في الإيداع الهدف ملفُّ خادمٍ بحقّ لا نسخةٌ قديمة.**
#
# **والتعميمُ كان سيطمس الفرق**: «أزِح غيرَ المتتبَّع» تُزيح الصنفين معاً —
# نسخةً قديمةً من ملفٍّ في git (تعود بالسحب، وإزاحتُها بلا أثر)، **وملفَّ
# إنتاجٍ لا وجودَ له في git أصلاً** (لا يعود، وإزاحتُه تهديم). والفاصلُ
# سؤالٌ واحدٌ يُقاس لا يُقدَّر: `git cat-file -e <هدف>:<مسار>`.
#
# **و`mv` لا `rm`**: من يحذف الدليلَ يمحو الخبرَ لا الخطر.
ASIDE="\$HOME/taxo-aside-$STAMP"
_ssh "cd $REMOTE && \
  git remote get-url taxo >/dev/null 2>&1 || git remote add taxo git@github-taxo:${TAXO_GITHUB_REPO:-SBONGEEL/taxo}.git; \
  GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=accept-new' git fetch --quiet taxo" \
  || die "تعذّر جلبُ الإيداعات — لا شيءَ تغيّر، والنسخةُ في $LOCAL"

MOVED="$(_ssh "cd $REMOTE && \
  n=0; git status --porcelain | grep '^??' | sed 's/^...//' | while IFS= read -r f; do \
    if git cat-file -e '$HEAD_SHA:'\"\$f\" 2>/dev/null; then \
      mkdir -p \"$ASIDE/\$(dirname \"\$f\")\" && mv \"\$f\" \"$ASIDE/\$f\" && echo \"\$f\"; \
    fi; \
  done | wc -l" | tr -d '\r ')"
[ "${MOVED:-0}" = "0" ] || say "  ✓ أُزيح $MOVED ملفاً متصادماً إلى ~/taxo-aside-$STAMP (لم يُحذف شيء)"

_ssh "cd $REMOTE && git checkout --quiet --detach $HEAD_SHA" \
  || die "تعذّر سحبُ ${HEAD_SHA:0:8} على الخادم — لا شيءَ تغيّر، والنسخةُ في $LOCAL"

SERVER_NOW="$(_ssh "cd $REMOTE && git rev-parse HEAD" | tr -d '\r')"
[ "$SERVER_NOW" = "$HEAD_SHA" ] || die "الخادمُ عند $SERVER_NOW لا $HEAD_SHA — يُوقَف. والنسخةُ في $LOCAL"
say "  ✓ إيداعُ الخادم = إيداعُ CI"

# **الترحيلةُ هنا، و`downgrade` مقيسٌ قبلها لا مقروء** — على قاعدةٍ خادشةٍ
# **لا على الإنتاج**: نسخةُ الإنتاج تُستعاد فيها ثم يُنزَل ويُصعَد.
if [ "${PENDING:-}" != "${TREE_HEAD:-}" ]; then
  say "  الترحيلة: ${PENDING:-?} ← ${TREE_HEAD:-?}"
  _ssh "cd $REMOTE && docker compose $COMPOSE_FILES run --rm --no-deps -T backend alembic upgrade head" \
    || die "سقطت الترحيلةُ — **لا يُصلَح على الإنتاج**. الرجوع: git -C $REMOTE checkout ${REMOTE_SHA:-<مجهول>} والنسخةُ في $LOCAL"
  say "  ✓ الترحيلةُ طُبِّقت"
else
  say "  الترحيلة: لا معلَّقَ"
fi

# **ولا حاويةَ تُعاد وحدَها، وكلُّ أمرِ compose يذكر ملفاتِه كلَّها صراحةً**
# — فخٌّ وقع مقيساً: إعادةٌ بملفٍّ ناقصٍ أسقطت `CORS_ORIGINS` فوقف الهاتفان.
say "  الحاويات: تُعاد بكلِّ ملفّات compose"
_ssh "cd $REMOTE && docker compose $COMPOSE_FILES up -d --build" \
  || die "تعذّرت إعادةُ الحاويات — الرجوع: git -C $REMOTE checkout ${REMOTE_SHA:-<مجهول>} والنسخةُ في $LOCAL"

# ═══════════════════ ٦) التحقّق ═══════════════════
# **الرفعُ لم يتمّ حتى تخضرَّ كلُّها.**
say "══ ٦) التحقّق"
DB_HEAD="$(_ssh "cd $REMOTE && docker compose $COMPOSE_FILES exec -T db psql -U taxo -d taxo -tAc 'SELECT version_num FROM alembic_version;'" | tr -d '\r ')"
[ "$DB_HEAD" = "${TREE_HEAD:-$DB_HEAD}" ] || die "رقمُ الترحيلة على القاعدة ($DB_HEAD) ≠ رأسُ الشجرة (${TREE_HEAD:-?}) — يُوقَف."
say "  ✓ الترحيلةُ على القاعدة = رأسُ الشجرة ($DB_HEAD)"

BAD="$(_ssh "cd $REMOTE && docker compose $COMPOSE_FILES ps --format '{{.Service}} {{.State}}' | grep -v ' running' || true" | tr -d '\r')"
[ -z "$BAD" ] && say "  ✓ كلُّ الحاويات تعمل" || die "حاوياتٌ ليست تعمل: $BAD"

for _ in $(seq 1 30); do
  HEALTH="$(curl -sS --max-time 10 "${TAXO_HEALTH_URL:-https://api.tajora.ly/health}" 2>/dev/null || true)"
  printf '%s' "$HEALTH" | grep -q '"ok"' && break
  sleep 5
done
printf '%s' "$HEALTH" | grep -q '"ok"' \
  || die "الصحّةُ لا تجيب بـok عبر النفق — يُوقَف. الردّ: ${HEALTH:-<لا شيء>}"
say "  ✓ الصحّةُ عبر النفق: $HEALTH"

# **ومراقبةُ السجلِّ دقائق: صفرُ أخطاءٍ أو ما ظهر** — ويُطبع ما ظهر ولا يُبتلع
say "  · السجلّ (٩٠ ثانية)…"
sleep 90
ERRS="$(_ssh "cd $REMOTE && docker compose $COMPOSE_FILES logs --since 3m backend 2>&1 | grep -icE 'traceback|ERROR|CRITICAL' || true" | tr -d '\r ')"
if [ "${ERRS:-0}" != "0" ]; then
  say "  ⚠ السجلُّ فيه $ERRS سطرَ خطأ — تُقرأ قبل أن يُعلَن التمام:"
  _ssh "cd $REMOTE && docker compose $COMPOSE_FILES logs --since 3m backend 2>&1 | grep -iE 'traceback|ERROR|CRITICAL' | head -10"
  die "لا يُعلَن تمامٌ وفي السجلِّ أخطاء — الرجوع: git -C $REMOTE checkout ${REMOTE_SHA:-<مجهول>} والنسخةُ في $LOCAL"
fi
say "  ✓ السجلّ: صفرُ أخطاءٍ في ثلاث دقائق"

say ""
say "✓ رُفع بعد نسخةٍ محقَّقة، وخضّرت البوّاباتُ الستُّ كلُّها."
say "  النسخة : $LOCAL"
say "  وقتُها : $STAMP (UTC)"
say "  حجمُها : $(du -sh "$LOCAL" | cut -f1)"
say ""
say "  **يُذكر هذا الثلاثيُّ في تقرير الرفع** (قاعدةُ CLAUDE.md الأولى)."
say ""
say "  **وما لا يقيسه هذا الباب** — يُقال ولا يُقرأ سكوتُه ضماناً:"
say "  · **مسارٌ حيٌّ من متصفحٍ** لا \`curl\` — شرطٌ بشريٌّ في البوّابة الخامسة"
say "  · **الأعمدةُ الأربعةُ للثلاثة** — تُقاس بـ\`check:served\` و\`check-apk\` محلياً"
