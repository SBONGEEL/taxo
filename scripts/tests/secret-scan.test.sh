#!/usr/bin/env bash
# **ماسحُ الأسرار في `deploy.sh` — يُقاس في الاتجاهين** (قاعدةُ كلِّ حارس؛ قرارُ المالك ٢٠٢٦-١٠-٠٨، `design/APPROVALS-62.md` §١٠):
# كلُّ استثناءٍ في `BENIGN_RE` **يمرّ شكلُه**، **وسطرٌ يحمل سرّاً حقيقيّاً بالشكل نفسِه يُمسك**. وواحدٌ منهما وحدَه لا يكفي:
# استثناءٌ يمرّر السليمَ ولا يُسأل عن السرّ بابٌ مفتوح، وماسحٌ يصيح على السليم يُطفأ فيسقط معه ما يمسكه حقّاً.
#
# **والعيّناتُ تُركَّب وقتَ التشغيل** من أجزاءٍ لا يقرؤها الماسحُ سرّاً — فهذا الملفُّ نفسُه يمرّ تحت الماسح الذي يختبره في كلِّ رفع.
# **والتعبيران يُقرآن من `deploy.sh` نفسِه** ولا يُنسخان هنا: نسخةٌ ثانيةٌ تفترق عن الأولى ولا يشكو أحد.
# **وكلُّ عيّنةٍ سليمةٍ يُشترط أن يطابقها شكلُ السرّ أوّلاً** — وإلا مرّت لأن الماسحَ لم يرها، لا لأن الاستثناءَ أعفاها.
#
# **وحدٌّ قائمٌ قبل هذه الثلاثة ومكتوب**: الاستثناءُ يُعفي **السطرَ كلَّه** إن طابق في أيِّ موضعٍ منه (`grep -v`) — فسرٌّ وتعبيرٌ سليمٌ
# في سطرٍ واحدٍ يمرّان معاً. **لا يقيسه هذا الاختبار**، ويقول ذلك.
#
#     bash scripts/tests/secret-scan.test.sh      # من WSL ومن Git Bash
set -uo pipefail
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
eval "$(grep -E '^(SECRET_RE|BENIGN_RE)=' "$SRC/scripts/deploy.sh")"
if [ -z "${SECRET_RE:-}" ] || [ -z "${BENIGN_RE:-}" ]; then
  echo "✗ secret-scan — لم يُقرأ التعبيران من scripts/deploy.sh"; exit 1
fi

fail=0
# **«يُمسك» كما في `deploy.sh` حرفاً**: يطابق شكلَ السرّ ولا يطابق استثناءً
caught()  { printf '%s\n' "$1" | grep -E "$SECRET_RE" | grep -qvE "$BENIGN_RE"; }
flagged() { printf '%s\n' "$1" | grep -qE "$SECRET_RE"; }
passes() {
  if ! flagged "$2"; then echo "  ✗ $1 — لا يطابقه شكلُ السرّ أصلاً، فلا يختبر استثناءً"; fail=1
  elif caught "$2"; then echo "  ✗ $1 — سليمٌ أُمسك"; fail=1
  else echo "  ✓ $1 — يمرّ"; fi
}
held() {
  if caught "$2"; then echo "  ✓ $1 — يُمسك"; else echo "  ✗ $1 — سرٌّ مرّ"; fail=1; fi
}

# أجزاءٌ تُركَّب — لا كلمةَ مفتاحيّةً حرفيّةً في سطرٍ من هذا الملفّ
PW="pass""word"; UP="PASS""WORD"; SC="sec""ret"; TK="tok""en"; AK="api_""key"
RND="Xk29fP0qLm7Zt3Rw"

echo "الأصل — ما كان يُمسك قبل الاستثناءات يبقى ممسوكاً:"
held   "مفتاحٌ خاصّ"                       "-----BEGIN RSA PRIV""ATE KEY-----"
held   "مفتاحٌ بقيمةٍ مقتبسة"               "${AK} = \"${RND}\""
held   "متغيّرُ بيئةٍ بقيمة"                "DB_${UP}=${RND}"

echo "(أ) الإسنادُ من تعبيرٍ لا من قيمة:"
passes "حقلُ طلبٍ يُمرَّر"                  "new_${PW}=payload.new_${PW},"
passes "إعدادٌ يُقرأ"                       "${SC} = settings.turn_shared_${SC}"
passes "مسارٌ يُبنى"                        "const ${TK^^}S = join(ROOT, \"x.css\")"
held   "قيمةٌ تبدأ باسم الكائن ولا نقطةَ بعده" "${SC} = settings${RND}"
held   "رمزٌ عارٍ مقاطعُ بنقاط"              "${TK} = eyJ${RND}.eyJ${RND}.${RND}"
held   "كائنٌ خارج القائمة المسمّاة"         "${SC} = vault${RND}.value"

echo "(ب) حشوُ سلسلةٍ منسَّقةٍ من مُعرِّف:"
passes "مُعرِّفٌ بين قوسين"                  "f\"TAXO_TEST_RIDER_${UP}={rider_${PW}}\","
held   "قيمةٌ حرفيّةٌ قبل الحشو"             "f\"TAXO_TEST_RIDER_${UP}=${RND}{x}\","
held   "قيمةٌ حرفيّةٌ بين القوسين"           "f\"TAXO_TEST_RIDER_${UP}={'${RND}'}\","

echo "(ج) ثابتٌ يسمّي الشيءَ نفسَه، ورمزا الإكمال:"
passes "اسمُ سببٍ يبدأ بالكلمة"              "REVOKE_${UP}_CHANGED = \"${PW}_changed\""
passes "رمزُ الإكمال للجديدة"                "${PW}: \"new-${PW}\","
passes "رمزُ الإكمال للحاليّة"               "${PW}: \"current-${PW}\","
held   "عبارةُ مرورٍ بشرطاتٍ سفليّة"          "DB_${UP} = \"correct_horse_battery_staple\""
held   "تبدأ بالكلمة وتطول"                  "DB_${UP} = \"${PW}_is_horse_battery\""
held   "عبارةٌ بشرطاتٍ عاديّة"               "${PW}: \"correct-horse-battery\","
held   "رمزُ الإكمال ومعه زيادة"             "${PW}: \"new-${PW}-${RND}\","

if [ "$fail" -ne 0 ]; then echo "✗ secret-scan — انظر ما فوق"; exit 1; fi
echo "✓ secret-scan — الاستثناءاتُ تمرّ أشكالُها، والأسرارُ بأشكالها تُمسك"
