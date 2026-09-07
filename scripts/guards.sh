#!/usr/bin/env bash
# **بابٌ واحدٌ لكلِّ حارسٍ ساكن** — كـ`suite.sh` للمجموعة و`deploy.sh` للرفع.
#
# **العلّةُ مقيسةٌ لا مفترضة** (2026-09-01): `check:money-math` بقي **أحمرَ على
# `master` عبر إيداعين** — مفتاحُه `ملف:سطر` أزاحته تعديلاتٌ في ملفٍّ آخر،
# **والحارسُ فعل ما بُني له**، لكنّ أحداً لم يشغّله. وقيل في التقريرين
# «الحرّاسُ خضر» — **عن حارسٍ لم يُشغَّل**.
#
# **ولمَ لا يكفي CI**: الحرّاسُ الثلاثةُ **مشغَّلون في CI فعلاً** ضمن
# `npm run build` لكلِّ تطبيق. **لكنّ CI لا يعمل إلا على دفعٍ، وهذا المشروعُ
# لا يدفع** (قرارُ المالك في كلِّ جولة) — **فبوّابةٌ خلف بابٍ لا يُفتح ليست
# بوّابة**. فالمخرجُ بابٌ محلّيّ.
#
# **والسريعُ وحدَه هنا**: كلُّ حارسٍ ساكنٍ يقرأ الشجرة. **ولا `vite build` ولا
# `tsc`** — دقائقُ في كلِّ إيداع تجعل الخطّافَ يُتجاوَز بـ`--no-verify`،
# **وحارسٌ يُتجاوَز أسوأُ من حارسٍ غائبٍ لأنه يُقرأ قائماً**. والبناءُ يبقى في
# CI وفي `build-channel.mjs`.
#
#     bash scripts/guards.sh            # الكلّ
#     bash scripts/guards.sh --quiet    # الأسطرُ الحمراءُ وحدَها
set -uo pipefail
cd "$(dirname "$0")/.."

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

red=0
run() { # run <اسم> <أمر...>
  local name="$1"; shift
  local out
  if out="$("$@" 2>&1)"; then
    [ "$QUIET" -eq 1 ] || printf '%s\n' "$out" | tail -1
  else
    red=$((red + 1))
    printf '\n✗ %s\n' "$name" >&2
    printf '%s\n' "$out" | tail -20 >&2
  fi
}

# ── الجذر: الحرّاسُ الذين لا يخصّون تطبيقاً بعينه ──────────────────────────
run "check:docs"            node tools/check-docs.mjs
run "check:money-math"      node tools/check-money-math.mjs
run "check:money-visible"   node tools/check-money-visible.mjs
run "check:published-readers" node tools/check-published-readers.mjs
run "check:destinations"    node tools/check-destinations.mjs
run "check:fields"          node tools/check-fields.mjs
run "check:storefront-card" node tools/check-storefront-card.mjs
run "check:update-gate"     node tools/check-update-gate.mjs
run "check:ci-timeouts"     node tools/check-ci-timeouts.mjs
run "check:env-leak"        node tools/check-env-leak.mjs
run "check:exec-bit"        node tools/check-exec-bit.mjs
run "check:enum-coverage"   node tools/check-enum-coverage.mjs

# ── لكلِّ تطبيقٍ حرّاسُه الساكنون ───────────────────────────────────────────
for app in customer-app driver-app admin-panel; do
  [ -d "$app" ] || continue
  # **و`check:sheet` أُضيف 2026-09-03 بعد أن عاش أحمرَ إيداعاً كاملاً**: كان
  # في `npm run build` لتطبيق الراكب وحدَه **وليس في هذا الباب** — والمشروعُ
  # لا يدفع فلا CI. فبقي `src/lib/update-gate.tsx` من البند ٨ أحمرَ ولم
  # يشغّله أحد، **وهو عينُ درس `check:money-math`** المكتوبِ في رأس هذا الملفّ.
  for g in check:scale check:enums check:digits check:slot check:sheet check:flags \
           check:config check:doors check:contract check:money check:readers; do
    # **ولا يُخترع حارسٌ لتطبيقٍ لا يملكه** — تُقرأ سكربتاتُه من `package.json`
    node -e "process.exit(require('./$app/package.json').scripts['$g']?0:1)" || continue
    run "$app · $g" npm --prefix "$app" run --silent "$g"
  done
  node -e "process.exit(require('./$app/package.json').scripts['check:rtl']?0:1)" \
    && run "$app · check:rtl" npm --prefix "$app" run --silent check:rtl
  node -e "process.exit(require('./$app/package.json').scripts['check:client-doors']?0:1)" \
    && run "$app · check:client-doors" npm --prefix "$app" run --silent check:client-doors
done

# ── وحرّاسُ الموقع — **كانا خارج هذا الباب** (أُضيفا ٢٠٢٦-٠٩-٠٦) ───────────
#
# **`site` ليس في حلقة التطبيقات** لأنه ليس React، **فسقط حارساه من الكنس**:
# `check:site` و`check:commission-text` يعملان في `npm run build` وحدَه.
# **وسطرُ «كلُّ الحرّاس الساكنين خضر» كان يَعِد بأكثر ممّا فحص** — وهو عينُ
# درس `check:sheet` المكتوبِ فوق، **مكرَّراً بعد ثلاثة أيام**.
#
# **وحلقةٌ ثانيةٌ لا شرطٌ في الأولى**: أسماءُ حرّاس الموقع ليست أسماءَ حرّاس
# التطبيقات، **ودمجُهما يجعل كلَّ اسمٍ يُجرَّب على كلِّ حزمة**.
if [ -d site ]; then
  for g in check:site check:commission-text; do
    node -e "process.exit(require('./site/package.json').scripts['$g']?0:1)" || continue
    run "site · $g" npm --prefix site run --silent "$g"
  done
fi

if [ "$red" -gt 0 ]; then
  printf '\n✗ %d حارساً أحمر — ولا إيداعَ فوق أحمر.\n' "$red" >&2
  exit 1
fi
printf '\n✓ كلُّ الحرّاس الساكنين خضر.\n'
exit 0
