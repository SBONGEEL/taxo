#!/usr/bin/env bash
# **القاعدةُ وRedis في CI** — و`suite.sh` يمرّ بـ`--no-deps` عمداً فلا يُقيمهما (لئلّا يُعيد تشغيلَ خدمةٍ صحيحةٍ على جهاز المطوّر).
# **ولم تكن هذه الخطوةُ موجودةً قطّ** يوماً، فكانت المجموعةُ تعمل **بلا قاعدة**: ١١٧٦ خطأَ تهيئةٍ في التشغيل ٤١.
# **والاسمُ يُصرَّح** (`TAXO_ENV_FILE`): `ps` يتحقّق من الملفِّ كلِّه فيطلب `env_file` الخلفية (عطبٌ مقيسٌ في التشغيل ٤٢).
set -euo pipefail
: "${TAXO_ENV_FILE:?TAXO_ENV_FILE مطلوب}"
docker compose --env-file .env up -d db redis
for i in $(seq 1 90); do
  ok=0
  for svc in db redis; do
    cid=$(docker compose --env-file .env ps -q "$svc")
    [ -n "$cid" ] || continue
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$cid")" = healthy ] && ok=$((ok+1))
  done
  [ "$ok" = 2 ] && { echo "✓ القاعدةُ وRedis سليمتان بعد ${i}ث"; exit 0; }
  sleep 1
done
echo "✗ لم تصحّا في ٩٠ث"; docker compose --env-file .env ps; exit 1
