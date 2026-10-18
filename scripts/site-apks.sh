#!/usr/bin/env bash
# **حزمتا صفحة التحميل من Google Play نفسِه** (قرارُ المالك ٢٠٢٦-١٠-١٨، SPEC §٧٩) — **بعد كلِّ رفعٍ إلى Play**:
#
#   bash scripts/site-apks.sh <versionCode>
#
# **العلّةُ مقيسة**: Play يعيد توقيعَ الحزمة بمفتاحه (Play App Signing)، وكانت حزمتا الصفحة موقَّعتين بمفتاح الرفع — **الاسمُ واحدٌ
# والتوقيعان مختلفان، وأندرويد لا يحدّث تطبيقاً بتوقيعٍ آخر**: هاتفٌ ثبّت من الصفحة يُرفض تحديثُه من المتجر («التثبيتُ رُفض»).
# **فحزمةُ الصفحة الآن هي «الحزمةُ الشاملة» التي يولّدها Play ويوقّعها** — فتتحدّث من المتجر ويُثبَّت المتجرُ فوقها.
#
# **وما يفعله، بترتيبه — ويقف عند أوّل سقوط:**
#   ١) `play_api.py universal`: الحزمتان من Play **وتُقاس كلٌّ** (شهادةُ Play المسجَّلة · المعرّف · الرمز) ومعهما `manifest.json`.
#   ٢) الإصدارُ `v<اسم>.<رمز>` على GitHub **عند الإيداع الذي اشتُقّ منه الرمز** — يُنشأ إن غاب، وتُرفق الثلاثةُ إليه (فوق ما كان باسمها).
#   ٣) **الخادمُ يسحبها من الإصدار** (`scripts/pull-release.sh` — يقيس البصمتين بعد الكتابة) — **فلا تُرسل حزمةٌ من جهازٍ إلى الخادم**.
#   ٤) `play_api.py preflight`: ما تخدمه الصفحةُ **بتوقيع Play ورمزُه لا يعلو Play** — مقيسٌ من الصفحة نفسِها.
#
# **وهو تغييرٌ على الإنتاج** (ملفّا الصفحة وحدَهما — لا قاعدةَ ولا حاوية): **فبصمةُ المال قبله وبعده** كأيِّ تغيير.
# **والرمزُ لا يُطبع**: يُقرأ من ملفِّه إلى متغيّر — ولا `set -x` هنا.
set -euo pipefail

say() { printf '%s\n' "$*"; }
die() { printf '\n✗ %s\n' "$*" >&2; exit 1; }

VC="${1:?رمزُ الإصدار مطلوب — مثل 925}"
[[ "$VC" =~ ^[0-9]+$ ]] || die "رمزٌ غيرُ رقميّ: $VC"
cd "$(dirname "$0")/.."

REPO="${TAXO_GITHUB_REPO:-SBONGEEL/taxo}"
HOST="${TAXO_DEPLOY_HOST:-taxo@169.58.207.123}"
REMOTE="${TAXO_REMOTE_PROJECT:-~/taxo}"
if [ -z "${GITHUB_TAXO_TOKEN:-}" ]; then
  [ -r "$HOME/.taxo-secrets/github-taxo.token" ] || die "لا رمزَ GitHub (\$GITHUB_TAXO_TOKEN أو ~/.taxo-secrets/github-taxo.token)"
  GITHUB_TAXO_TOKEN="$(tr -d '\r\n' < "$HOME/.taxo-secrets/github-taxo.token")"
fi

# **الإيداعُ الذي رمزُه هذا** — الرمزُ عددُ الإيداعات (`build.gradle`)، فالإيداعُ رقم VC في التاريخ. **وعلى master وحدَه**
git fetch -q origin master
SHA="$(git rev-list --reverse origin/master | sed -n "${VC}p")"
[ -n "$SHA" ] || die "لا إيداعَ رقمُه $VC على origin/master — أرُفع ما لم يُدمج؟"
NAME="$(grep -m1 -oE 'versionName "[^"]+"' customer-app/android/app/build.gradle | cut -d'"' -f2)"
TAG="v${NAME}.${VC}"
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "وسمٌ لا يقبله بابُ الخادم: $TAG"
say "══ حزمتا الصفحة من Play — رمز $VC · إيداع ${SHA:0:8} · وسم $TAG"

OUT="landing/downloads"
mkdir -p "$OUT"
say "── ١) من Play"
TAXO_RELEASE_TAG="$TAG" python3 scripts/play_api.py universal "$VC" "$OUT" < /dev/null

say "── ٢) الإصدار على GitHub"
api() { curl -fsS -H "Authorization: Bearer $GITHUB_TAXO_TOKEN" -H "Accept: application/vnd.github+json" "$@"; }
code="$(curl -sS -o /tmp/site-apks-rel.json -w '%{http_code}' -H "Authorization: Bearer $GITHUB_TAXO_TOKEN" \
        -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$REPO/releases/tags/$TAG")"
if [ "$code" = "404" ]; then
  body="$(python3 -c 'import json,sys; print(json.dumps({"tag_name": sys.argv[1], "target_commitish": sys.argv[2], "name": sys.argv[1],
    "body": "حزمتا صفحة التحميل **من Google Play بتوقيعه** (رمز " + sys.argv[3] + "، SPEC §٧٩). والتجريبيّتان يرفقهما CI."}))' "$TAG" "$SHA" "$VC")"
  api -X POST "https://api.github.com/repos/$REPO/releases" -d "$body" > /tmp/site-apks-rel.json
  say "  ✓ أُنشئ $TAG عند ${SHA:0:8}"
elif [ "$code" = "200" ]; then
  say "  ✓ $TAG قائم"
else
  die "قراءةُ الإصدار $TAG أجابت $code"
fi
REL_ID="$(python3 -c 'import json; print(json.load(open("/tmp/site-apks-rel.json"))["id"])')"
for f in taxo-rider.apk taxo-driver.apk manifest.json; do
  old="$(api "https://api.github.com/repos/$REPO/releases/$REL_ID/assets?per_page=100" |
         python3 -c 'import json,sys; print(next((str(a["id"]) for a in json.load(sys.stdin) if a["name"] == sys.argv[1]), ""))' "$f")"
  [ -z "$old" ] || api -X DELETE "https://api.github.com/repos/$REPO/releases/assets/$old" > /dev/null
  type="application/vnd.android.package-archive"; [ "$f" = manifest.json ] && type="application/json"
  api -X POST -H "Content-Type: $type" --data-binary "@$OUT/$f" \
      "https://uploads.github.com/repos/$REPO/releases/$REL_ID/assets?name=$f" > /dev/null
  say "  ✓ $f رُفع إلى $TAG ($(stat -c%s "$OUT/$f") بايت)"
done
rm -f /tmp/site-apks-rel.json

say "── ٣) الخادمُ يسحب $TAG"
# **عميلُ ssh وكيلِ ويندوز حين يحمل المفتاح** — القياسُ نفسُه في `deploy.sh` (`_pick_ssh`)، **وstdin من /dev/null** (ذاكرةُ التعليق)
SSH=ssh
for root in /c/Windows/System32/OpenSSH /mnt/c/Windows/System32/OpenSSH; do
  if [ -x "$root/ssh.exe" ] && "$root/ssh-add.exe" -l >/dev/null 2>&1; then SSH="$root/ssh.exe"; break; fi
done
"$SSH" -o StrictHostKeyChecking=yes -o ConnectTimeout=20 -o ServerAliveInterval=15 -i "${TAXO_SSH_KEY:-$HOME/.ssh/taxo-contabo}" \
  "$HOST" "cd $REMOTE && bash scripts/pull-release.sh '$TAG' '$REPO' '$GITHUB_TAXO_TOKEN'" < /dev/null \
  || die "تعذّر سحبُ $TAG على الخادم — الصفحةُ على ما كانت"

say "── ٤) ما تخدمه الصفحةُ الآن"
sleep 5
python3 scripts/play_api.py preflight < /dev/null
