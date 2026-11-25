#!/usr/bin/env bash
# حزمتا Play من تشغيل CI لوسمٍ بعينه — `bash fetch_pb.sh <tag> <outdir>`؛ الرمزُ يُقرأ من ملفّه ولا يُطبع
set -euo pipefail
TAG="$1"; OUT="$2"
TOKEN="$(tr -d '\r\n' < "$HOME/.taxo-secrets/github-taxo.token")"
API=https://api.github.com/repos/SBONGEEL/taxo
H=(-H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json")
RUN=$(curl -fsS "${H[@]}" "$API/actions/workflows/ci.yml/runs?branch=$TAG&per_page=5" | python3 -c '
import json,sys
runs=json.load(sys.stdin)["workflow_runs"]
print(" ".join(f"{r[\"id\"]}:{r[\"status\"]}:{r[\"conclusion\"]}" for r in runs))')
echo "runs: $RUN"
ID=$(echo "$RUN" | tr " " "\n" | grep ":completed:success" | head -1 | cut -d: -f1 || true)
[ -n "$ID" ] || { echo "✗ لا تشغيلَ ناجحٌ بعد للوسم $TAG"; exit 2; }
URL=$(curl -fsS "${H[@]}" "$API/actions/runs/$ID/artifacts" | python3 -c '
import json,sys
a=[x for x in json.load(sys.stdin)["artifacts"] if x["name"]=="play-bundles"]
print(a[0]["archive_download_url"] if a else "")')
[ -n "$URL" ] || { echo "✗ لا play-bundles في $ID"; exit 3; }
mkdir -p "$OUT"
curl -fsSL "${H[@]}" -o "$OUT/pb.zip" "$URL"
cd "$OUT" && unzip -oq pb.zip && rm pb.zip
find . -name "*.aab" -o -name "mapping.txt" | sort
echo "✓ من التشغيل $ID"
