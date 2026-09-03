#!/usr/bin/env bash
# **يُشغَّل على الخادم**: يسحب حزمَ إصدارٍ بعينه من GitHub إلى صفحة التنزيل.
#
# **ولمَ على الخادم لا من جهازٍ يرسل**: البوّابةُ الرابعةُ تقول «الخادمُ يسحب
# نفسَ ما خضّره CI». **وحزمةٌ تُرسل من جهازٍ تنقض ذلك من داخل الباب** — تمرّ
# بالبوّابات وهي لم تُبنَ فيما خضّرته، فيبقى «ما تخدمه الصفحةُ» بلا نسبٍ إلى
# شجرةٍ خضراء.
#
# **وملفٌّ لا سطرٌ مُعشَّشٌ في `ssh`**: أولُ صياغةٍ كانت أمراً واحداً بعلامات
# اقتباسٍ أربع طبقات — **وما لا يُقرأ لا يُراجَع**، والباب يُقرأ أكثرَ مما
# يُشغَّل.
#
#   bash scripts/pull-release.sh <tag> <repo> <token>
set -euo pipefail

TAG="${1:?الوسم مطلوب}"
REPO="${2:?المستودع مطلوب}"
TOKEN="${3:?الرمز مطلوب}"
DEST="${4:-landing/downloads}"

api() { curl -fsS -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" "$@"; }

RELEASE="$(api "https://api.github.com/repos/$REPO/releases/tags/$TAG")"
mkdir -p "$DEST"

for name in taxo-rider.apk taxo-driver.apk manifest.json; do
  url="$(printf '%s' "$RELEASE" | python3 -c "
import json,sys
assets = json.load(sys.stdin).get('assets', [])
hit = [a for a in assets if a['name'] == '$name']
print(hit[0]['url'] if hit else '')
")"
  [ -n "$url" ] || { printf '✗ لا أثرَ باسم %s في الإصدار %s\n' "$name" "$TAG" >&2; exit 1; }
  curl -fsSL -H "Authorization: Bearer $TOKEN" -H "Accept: application/octet-stream" \
       "$url" -o "$DEST/$name.part"
  mv "$DEST/$name.part" "$DEST/$name"
  printf '  ✓ %s\n' "$name"
done

# **والتحقّقُ بعد الكتابة لا قبلها** (قاعدةُ `core/storage.save`): نقلٌ انتهى
# ليس ملفاً وصل — فتُقاس البصمةُ من القرص وتُقارَن بما يقوله البيانُ نفسُه.
python3 - "$DEST" <<'PY'
import hashlib, json, sys, pathlib
dest = pathlib.Path(sys.argv[1])
manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
bad = []
for app in manifest["apps"]:
    path = dest / app["file"]
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != app["sha256"]:
        bad.append(f"{app['file']}: على القرص {got[:10]} والبيانُ {app['sha256'][:10]}")
if bad:
    print("✗ ما نزل ليس ما يقوله البيان:", *bad, sep="\n  ")
    raise SystemExit(1)
print(f"  ✓ البصمتان تطابقان البيان — إيداع {str(manifest.get('commit'))[:8]} · وسم {manifest.get('tag')}")
PY
