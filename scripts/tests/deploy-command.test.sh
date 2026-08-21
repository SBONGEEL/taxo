#!/usr/bin/env bash
# **ما يُقاس هنا الرفضُ لا النجاح** (شرطُ المالك 2026-08-21).
#
# **نجاحُ السحب لا يقول شيئاً عمّا يُرفض** — ومفتاحٌ مقيَّدٌ قيمتُه كلُّها في
# ما لا يفتحه. فالاختبارُ يطرق المغلِّفَ بأوامرَ أخرى ويشترط الردَّ.
#
# **ولا يُطرق الخادمُ ولا الشبكة**: كلُّ حالةٍ ترتدّ **قبل** أن يُنادى
# `pull-release.sh`، فالفشلُ هنا فشلُ حراسةٍ لا فشلُ اتصال.
set -uo pipefail
cd "$(dirname "$0")/../.."

WRAPPER=scripts/deploy-command.sh
pass=0; fail=0

refuses() { # وصفٌ · الأمرُ الوارد
  local label="$1" cmd="$2" out code
  out="$(SSH_ORIGINAL_COMMAND="$cmd" TAXO_RELEASE_TOKEN=x bash "$WRAPPER" 2>&1)"; code=$?
  if [ "$code" -eq 42 ]; then
    printf '  ✓ رُفض: %s\n' "$label"; pass=$((pass+1))
  else
    printf '  ✗ **لم يُرفض**: %s (خروج %s)\n     %s\n' "$label" "$code" "${out:0:120}"; fail=$((fail+1))
  fi
}

printf '\n  مفتاحُ النشر — ما لا يفتحه\n\n'

refuses "صدفةٌ تفاعلية (بلا أمر)"            ""
refuses "أمرُ صدفةٍ صريح"                    "bash"
refuses "قراءةُ الأسرار"                     "cat .env"
refuses "قراءةُ القاعدة"                     "docker compose exec db psql -U taxo"
refuses "سحبٌ ثم أمرٌ ثانٍ بفاصلة"           "pull-release v1.0.0; cat .env"
refuses "سحبٌ ثم أمرٌ ثانٍ بـ&&"              "pull-release v1.0.0 && cat .env"
refuses "وسيطٌ زائد"                         "pull-release v1.0.0 extra"
refuses "بلا وسم"                            "pull-release"
refuses "وسمٌ مسار"                          "pull-release ../../etc/passwd"
refuses "وسمٌ بخيارِ curl"                   "pull-release -o/tmp/x"
refuses "وسمٌ بشكلٍ غيرِ مقبول"               "pull-release latest"
refuses "فعلٌ آخرُ يبدأ بنفس الحروف"          "pull-release-all v1.0.0"

printf '\n  ✓ %s رفضاً · ✗ %s\n\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1

# **والاتجاهُ الثاني**: أمرٌ سليمُ الشكل **يتجاوز الحراسة** — ويُقاس بأنه بلغ
# `pull-release.sh` (فيسقط على الشبكة/الرمز)، **لا بأنه رُفض**. وبغير هذا
# يكون الحارسُ «يرفض كلَّ شيء» وهو ليس حارساً بل باباً مغلقاً.
out="$(SSH_ORIGINAL_COMMAND="pull-release v9.9.9" TAXO_RELEASE_TOKEN=not-a-real-token bash "$WRAPPER" 2>&1)"; code=$?
if [ "$code" -eq 42 ]; then
  printf '  ✗ **الشكلُ السليمُ رُفض أيضاً** — هذا بابٌ مغلقٌ لا حارس.\n'; exit 1
fi
printf '  ✓ الشكلُ السليمُ يمرّ الحراسةَ ويصل السحبَ (خروج %s — شبكةٌ أو رمز، لا رفض)\n\n' "$code"
