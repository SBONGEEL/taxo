#!/usr/bin/env bash
# يقيس **بيئةً حيّةً** بما تشحنه الشجرة — والمرجعُ يُقرأ من الوحدة التي تشحنه
# (`scripts/seed.py::FEATURE_DEFAULTS`) لا بتحليل نصِّها، فلا يفترق الحارسُ
# عمّا يُشحن فعلاً. الاستعمال: bash scripts/check-markets.sh https://stg-api.tajora.ly
set -euo pipefail
BASE="${1:-}"
[ -z "$BASE" ] && { echo "الاستعمال: bash scripts/check-markets.sh <أساسُ البيئة>"; exit 2; }

TMP="$(mktemp -t taxo-shipped-XXXXXX.json)"
trap 'rm -f "$TMP"' EXIT

docker compose run --rm --no-deps -T backend python -c "
import json
from scripts.seed import FEATURE_DEFAULTS
print(json.dumps({c.value: {k.value: v for k, v in d.items()} for c, d in FEATURE_DEFAULTS.items()}))
" | tr -d '\r' | tail -1 > "$TMP"

node tools/check-markets.mjs "$BASE" "$TMP"
