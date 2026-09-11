#!/usr/bin/env bash
# **بابٌ واحدٌ لتشغيل الرفع على جهاز المطوّر** — والقاعدةُ التي تُتذكَّر تُنسى.
#
# **علّتُه مقيسةٌ لا مُقدَّرة** (٢٠٢٦-٠٩-١٠، وتفصيلُها في `COMMANDS.md`): سقط
# رفعٌ واحدٌ **ثلاثَ مرّاتٍ بثلاثة أسبابٍ مختلفة**، ولا واحدٌ منها عطبٌ في
# المشروع — كلُّها في **كيف يُشغَّل السكربت على هذا الجهاز**:
#
#   1. جسرُ WSL→`ssh.exe` يموت في منتصف تدفّقٍ ثنائيّ (البوّابة الثالثة).
#   2. Git Bash يقرأ شجرةَ WSL «٥١ تغييراً» وهي نظيفة (بتُّ التنفيذ وحدَه)،
#      **فتسقط البوّابةُ الأولى بقراءةٍ كاذبة**.
#   3. متتبِّعُ المهامّ يقتل العمليةَ عند ضغط الذاكرة **في منتصف البوّابة
#      الخامسة**، فتُترك الحالُ **نصفَ مطبَّقة**.
#
# **وعلاجُها الثلاثةُ كان مكتوباً في وثيقةٍ يقرؤها من يتذكّر أن يقرأها.** وهذا
# الملفُّ يجعلها **شرطاً يُطبَّق**: يضبط ما يُضبَط، **ويرفض ما لا يضمنه**،
# ولا يُصلح شيئاً في صمت.
#
# **وحدُّه مكتوبٌ لا مسكوتٌ عنه**: قِيست **مساراتُ رفضِه** وحدَها
# (٢٠٢٦-٠٩-١١) — **ولم يُقَس رفعٌ كاملٌ خلاله بعد**، ولا يُقرأ سكوتُه ضماناً.
#
#     bash scripts/deploy-here.sh [وسائطُ deploy.sh]
#
# ومتغيّراتُه: `TAXO_DEPLOY_DETACHED=1` تعني «أنا الابنُ المنفصل، لا تُعد
# الإطلاق»، و`TAXO_DEPLOY_LOG_DIR` يبدّل موضعَ السجلّ.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
LOG_DIR="${TAXO_DEPLOY_LOG_DIR:-$HOME/taxo-deploy-logs}"

die() {
  printf '\n✗ %s\n' "$1" >&2
  shift
  for line in "$@"; do printf '  %s\n' "$line" >&2; done
  exit 1
}

# ═══ ١) أيُّ صدفةٍ هذه؟ — **وWSL تُرفض بعلّتها لا بذوق** ═══════════════════
#
# **ولا يُرفض لينكسُ الحقيقيّ**: الخادمُ نفسُه لينكس، والرفضُ العريض يمنع ما
# وُضع ليحرسه.
KERNEL="$(uname -s)"
case "$KERNEL" in
  MINGW* | MSYS*)
    SHELL_KIND="Git Bash"
    ;;
  Linux)
    if grep -qi microsoft /proc/version 2>/dev/null; then
      die "WSL لا تصلح لتشغيل الرفع من هذا الجهاز." \
        "المفتاحان بعبارة مرور، و\`ssh.exe\` الخاصُّ بويندوز هو العميلُ الذي يملكهما." \
        "وجسرُ WSL→ssh.exe يموت في منتصف نقل \`bundle.tar\` — قِيس ثلاثَ مرّاتٍ بثلاثة وجوه." \
        "" \
        "افتح Git Bash ثم:  bash scripts/deploy-here.sh"
    fi
    SHELL_KIND="Linux"
    ;;
  *)
    die "نواةٌ غيرُ معروفة: $KERNEL — يُوقَف ولا يُخمَّن."
    ;;
esac

# ═══ ٢) `core.fileMode` بالبيئة لا بتعديل إعداد ════════════════════════════
#
# **و`git -c` لا ينفع**: `deploy.sh` ينادي `git` مباشرةً، فلا يرث الوسيط.
# **وتعديلُ `.git/config` يبقى بعد الجولة** فيخفي تغييراً حقيقياً في بتِّ
# التنفيذ غداً — والبيئةُ تزول مع العملية.
if [ "$SHELL_KIND" = "Git Bash" ]; then
  export GIT_CONFIG_COUNT=1
  export GIT_CONFIG_KEY_0=core.fileMode
  export GIT_CONFIG_VALUE_0=false
fi

# ═══ ٣) الشجرةُ نظيفةٌ — **تُقاس بعد الضبط لا قبله** ═══════════════════════
cd "$ROOT"
DIRTY="$(git status --porcelain | wc -l | tr -d ' ')"
if [ "$DIRTY" != "0" ]; then
  git status --porcelain | head -20 >&2
  die "الشجرةُ ليست نظيفة — $DIRTY سطراً." \
    "والبوّابةُ الأولى ترفض، فلا يُبدأ رفعٌ فوق عملٍ غيرِ مودَع."
fi

# ═══ ٤) ما يُقاس ويُطبع ولا يُحكم عليه ═════════════════════════════════════
#
# **عميلُ ssh يُطبع لا يُمنع**: من غيّر ترتيبَ `PATH` قصداً يرى ما يشغّله،
# **وحارسٌ يصيح على سليمٍ يُطفأ فيسقط معه ما يمسكه حقاً**.
printf '  الصدفة      %s (%s)\n' "$SHELL_KIND" "$KERNEL"
printf '  الشجرة      %s — نظيفة\n' "$ROOT"
printf '  ssh         %s\n' "$(command -v ssh || echo '(لا ssh في PATH)')"
printf '  fileMode    %s\n' "${GIT_CONFIG_VALUE_0:-(لم يُضبط — ليس Git Bash)}"

# ═══ ٥) عمليةٌ مستقلّةٌ خارج متتبِّع المهامّ ════════════════════════════════
#
# **والمشغّلُ ملفٌّ لا سطرٌ مقتبَس**: وسائطُ `Start-Process` تُعاد اقتباسُها،
# وسطرٌ فيه `&&` و`>` **مات صامتاً بلا سجلّ** حين جُرِّب.
if [ "$SHELL_KIND" = "Git Bash" ] && [ "${TAXO_DEPLOY_DETACHED:-0}" != "1" ]; then
  mkdir -p "$LOG_DIR"
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  LOG="$LOG_DIR/deploy-$STAMP.log"
  RUNNER="$LOG_DIR/run-$STAMP.sh"

  {
    printf '#!/usr/bin/env bash\n'
    printf 'export TAXO_DEPLOY_DETACHED=1\n'
    printf 'export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.fileMode GIT_CONFIG_VALUE_0=false\n'
    printf 'exec %s' "$(printf '%q' "$HERE/deploy-here.sh")"
    for arg in "$@"; do printf ' %s' "$(printf '%q' "$arg")"; done
    printf ' > %s 2>&1\n' "$(printf '%q' "$LOG")"
  } >"$RUNNER"
  chmod +x "$RUNNER"

  RUNNER_WIN="$(cygpath -w "$RUNNER" 2>/dev/null || printf '%s' "$RUNNER")"
  printf '\n  السجلّ      %s\n' "$LOG"
  printf '  المشغّل     %s\n' "$RUNNER"
  powershell.exe -NoProfile -NonInteractive -Command \
    "Start-Process -FilePath 'bash.exe' -ArgumentList '$RUNNER_WIN' -WindowStyle Hidden" \
    >/dev/null

  printf '\n  أُطلقت عمليةٌ مستقلّة. تابعها:\n    tail -f %s\n' "$LOG"
  exit 0
fi

# ═══ ٦) وهنا وحدَه يبدأ الرفع ═══════════════════════════════════════════════
printf '\n'
exec bash "$HERE/deploy.sh" "$@"
