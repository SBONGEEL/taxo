#!/usr/bin/env bash
# **بوّابةُ الفرع — تُقاس في الاتجاهين** (قاعدةُ كلِّ حارس، قرارُ المالك ٢٠٢٦-٠٨-٢٠):
# **تمسك فرعاً غيرَ `master`، وتصمت على `master`** — وواحدٌ منهما وحدَه لا يكفي.
#
# **ولا يُطرق الخادمُ ولا الشبكة ولا يُدفع شيء**: كلُّ حالةٍ تجري في مستودعٍ
# مؤقّتٍ يُبنى هنا ويُحذف، **بلا `origin`**، و`ssh`/`ssh.exe`/`curl`/`scp`/`rsync`
# مستبدَلةٌ بشواهدَ تكتب سطراً في سجلٍّ ثمّ تفشل — **فنداءٌ واحدٌ لها يُقرأ في
# السجلّ**. و`TAXO_SSH` يشير إلى الشاهد نفسِه فلا يُنادى عميلُ ويندوز،
# و`TAXO_DEPLOY_DETACHED=1` يمنع `deploy-here.sh` أن يُطلق عمليةً مستقلّةً لا
# ترث الشواهد. **و`--announce` حيث يُسمح بالمرور**: البوّابةُ الأولى وحدَها.
#
# **وما يُقاس في رفض `deploy.sh` ثلاثة**: خروجٌ بـ١ · **ولا سطرَ «الإعلان»**
# (لم تبدأ بوّابة) · **وسجلُّ الشبكة فارغ** (لم يُنادَ الخادم). **والحالةُ
# المقابلةُ على `master` تملأ السجلّ** — فيُرى أن البوّابةَ هي ما منعه، لا
# أن السكربتَ لا يطرق أصلاً.
#
#     bash scripts/tests/deploy-branch-gate.test.sh      # من WSL ومن Git Bash
set -uo pipefail
SRC="$(cd "$(dirname "$0")/../.." && pwd)"

# **ويُشغَّل من خطّاف الإيداع** (`scripts/guards.sh`) — **وهناك يصدّر git
# `GIT_INDEX_FILE` و`GIT_DIR`**، فإيداعٌ في مستودعٍ مؤقّتٍ يكتب في **فهرس
# الإيداع الجاري** لا في فهرسه. فتُنزع قبل أن يُنادى git على غير هذه الشجرة.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_OBJECT_DIRECTORY \
      GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0
ok()  { printf '  ✓ %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  ✗ **%s**\n     %s\n' "$1" "${2:-}"; fail=$((fail+1)); }

# ── شواهدُ الشبكة ──────────────────────────────────────────────────────────
mkdir -p "$TMP/bin"
NET="$TMP/network.log"
: > "$NET"
for t in ssh ssh.exe curl scp rsync; do
  printf '#!/usr/bin/env bash\nprintf "%%s %%s\\n" %q "$*" >> %q\nexit 1\n' "$t" "$NET" > "$TMP/bin/$t"
  chmod +x "$TMP/bin/$t"
done
SANDBOX=(env PATH="$TMP/bin:$PATH" TAXO_SSH="$TMP/bin/ssh" TAXO_SSH_GAP=0
         TAXO_DEPLOY_DETACHED=1 GIT_TERMINAL_PROMPT=0)

# ── مستودعٌ مؤقّتٌ على master، فيه أبوابُ الرفع كما هي في الشجرة ──────────
G=(-c user.email=gate@test -c user.name=gate -c commit.gpgsign=false)
make_repo() { # make_repo <دليل>
  mkdir -p "$1/scripts"
  cp "$SRC/scripts/deploy-branch-gate.sh" "$SRC/scripts/deploy.sh" \
     "$SRC/scripts/deploy-here.sh" "$1/scripts/"
  git -C "$1" init -q
  git -C "$1" symbolic-ref HEAD refs/heads/master
  git -C "$1" "${G[@]}" add -A
  git -C "$1" "${G[@]}" commit -q -m one
  git -C "$1" "${G[@]}" commit -q --allow-empty -m two
}
MASTER="$TMP/live";   make_repo "$MASTER"
OTHER="$TMP/redesign"; make_repo "$OTHER"; git -C "$OTHER" checkout -q -b redesign
DETACHED="$TMP/detached"; make_repo "$DETACHED"; git -C "$DETACHED" checkout -q --detach
NOREPO="$TMP/norepo"; mkdir -p "$NOREPO"

GATE="$SRC/scripts/deploy-branch-gate.sh"
printf '\n  بوّابةُ الفرع — الباب نفسُه\n\n'

# ١) الصمتُ على السليم
if out="$(bash "$GATE" "$MASTER" 2>&1)" && [ -z "$out" ]; then ok "master يمرّ صامتاً"
else bad "master لم يمرّ صامتاً" "$out"; fi

# ٢-٥) الإمساك — وكلُّ رفضٍ يسمّي سببَه
expect_refuse() { # وصف · نصٌّ يُنتظر في الرفض · وسائطُ البوّابة...
  local label="$1" want="$2"; shift 2
  local out code
  out="$(bash "$GATE" "$@" 2>&1)"; code=$?
  if [ "$code" -eq 1 ] && printf '%s' "$out" | grep -qF -- "$want"; then ok "$label"
  else bad "$label" "خروج $code · ${out:0:160}"; fi
}
expect_refuse "فرعٌ غيرُ master يُرفض ويُسمّى"     "«redesign»"      "$OTHER"
expect_refuse "رأسٌ منفصلٌ يُرفض ويُسمّى"          "رأسٍ منفصل"      "$DETACHED"
expect_refuse "دليلٌ ليس مستودعاً يُرفض بنصِّ git" "git لم يقرأ"     "$NOREPO"
expect_refuse "نداءٌ بلا دليلٍ يُرفض"               "لا دليلَ"
expect_refuse "كلُّ دليلٍ يُسأل لا الأوّلُ وحدَه"   "«redesign»"      "$MASTER" "$OTHER"

printf '\n  deploy.sh — يقف قبل الإعلان ولا يطرق الخادم\n\n'

deploy_refuses() { # وصف · دليلُ التشغيل · مسارُ السكربت
  local label="$1" cwd="$2" script="$3" out code t0 t1
  : > "$NET"
  t0=$(date +%s)
  out="$(cd "$cwd" && "${SANDBOX[@]}" bash "$script" 2>&1)"; code=$?
  t1=$(date +%s)
  if [ "$code" -ne 1 ]; then bad "$label" "خروج $code لا ١ · ${out:0:160}"
  elif printf '%s' "$out" | grep -qF "الإعلان"; then bad "$label" "بدأت البوّابةُ الأولى قبل الرفض"
  elif [ -s "$NET" ]; then bad "$label" "نُودي الخادم: $(head -1 "$NET")"
  elif ! printf '%s' "$out" | grep -qF "لا رفعَ إلا من master"; then bad "$label" "رفضٌ بنصٍّ آخر: ${out:0:160}"
  else ok "$label ($((t1 - t0))ث · صفرُ نداءٍ للشبكة)"; fi
}
deploy_refuses "من شجرة redesign"                          "$OTHER"  "$OTHER/scripts/deploy.sh"
deploy_refuses "سكربتُ master منادًى من داخل redesign"     "$OTHER"  "$MASTER/scripts/deploy.sh"
deploy_refuses "سكربتُ redesign منادًى من داخل master"     "$MASTER" "$OTHER/scripts/deploy.sh"
deploy_refuses "من رأسٍ منفصل"                              "$DETACHED" "$DETACHED/scripts/deploy.sh"

# **والاتجاهُ الثاني لـdeploy.sh**: على master يمرّ البوّابةَ صفر ويبدأ الإعلان
# **ويطرق الشاهد** — فيُرى أن السكربتَ يطرق حين يُسمح له، وأن صمتَ السجلِّ
# أعلاه من البوّابة لا من غيرها. ويقف بعدها لأن الشاهدَ لا يجيب (`--announce`
# فلا دفعَ ولو أجاب).
: > "$NET"
out="$(cd "$MASTER" && "${SANDBOX[@]}" bash "$MASTER/scripts/deploy.sh" --announce 2>&1)"
if printf '%s' "$out" | grep -qF "الإعلان" && [ -s "$NET" ] && ! printf '%s' "$out" | grep -qF "لا رفعَ إلا من master"; then
  ok "على master: البوّابةُ صامتة، والإعلانُ بدأ، والشاهدُ طُرق ($(wc -l < "$NET") نداء)"
else
  bad "على master لم يبلغ الإعلان" "${out:0:200}"
fi

printf '\n  deploy-here.sh — يقف قبل الإطلاق المستقلّ\n\n'

: > "$NET"
out="$(cd "$OTHER" && "${SANDBOX[@]}" bash "$OTHER/scripts/deploy-here.sh" --announce 2>&1)"; code=$?
if [ "$code" -eq 1 ] && printf '%s' "$out" | grep -qF "لا رفعَ إلا من master" \
   && ! printf '%s' "$out" | grep -qF "أُطلقت" && [ ! -s "$NET" ]; then
  ok "من شجرة redesign: يُرفض بالفرع قبل كلِّ شيء"
else
  bad "deploy-here.sh من redesign" "خروج $code · ${out:0:200}"
fi

# **والاتجاهُ الثاني**: على master تمرّ البوّابة — **وما يليها يختلف بالصدفة**:
# WSL ترفضها البوّابةُ التالية بعلّتها، وGit Bash يبلغ الإعلان.
: > "$NET"
out="$(cd "$MASTER" && "${SANDBOX[@]}" bash "$MASTER/scripts/deploy-here.sh" --announce 2>&1)"
if printf '%s' "$out" | grep -qF "لا رفعَ إلا من master"; then
  bad "deploy-here.sh على master رفضه الفرع" "${out:0:200}"
elif printf '%s' "$out" | grep -qF "WSL لا تصلح" || printf '%s' "$out" | grep -qF "الإعلان"; then
  ok "على master: بوّابةُ الفرع صامتة، وما بعدها يحكم ($(printf '%s' "$out" | grep -qF 'WSL لا تصلح' && echo 'رفضُ WSL بعلّته' || echo 'الإعلانُ بدأ'))"
else
  bad "deploy-here.sh على master: نصٌّ غيرُ منتظَر" "${out:0:200}"
fi

printf '\n  ✓ %s · ✗ %s\n\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
