#!/usr/bin/env bash
# **البند ١٠: حاويةٌ تبدو أنها فعلت ما طُلب** — وما بقي من العائلة بعد
# `suite.sh`.
#
# **العائلةُ ثلاثة، وكلُّها بلا رسالة خطأ**: `restart` يُبقي الصورةَ القديمة
# فتغيب تبعيةٌ أُعلنت؛ ومِرآةٌ لا يعبرها inotify فيخدم Vite ما قرأه عند
# الإقلاع؛ وتشغيلٌ شاردٌ يمسك قاعدةَ الاختبار (وهذا يحرسه `scripts/suite.sh`).
#
# **وما يفحصه هنا اثنان مقيسان:**
#
# ١) **`requirements.txt` أحدثُ من صورة الخلفية** ⇒ تبعيةٌ أُعلنت ولم تُبنَ.
#    وقد شُحن هذا مرةً: المرحلةُ ٩-ب أضافت `python-multipart`، **والمجموعةُ
#    خضراء** (لأن `docker compose run` يبني حاويةً من الصورة في كلِّ مرة)
#    والخدمةُ الحيّةُ تردّ على كلِّ طلبٍ بـ`RuntimeError` حتى أُعيد إنشاؤها.
#
# ٢) **الخلفيةُ تعمل بلا `CORS_ORIGINS`** ⇒ رُفعت بلا طبقة النفق، فيقف الهاتفان
#    على «الشبكة ضعيفة» **بينما `curl` يجيب ٢٠٠ من الجهاز**. وقع مقيساً مرتين،
#    آخرُهما 2026-08-20.
#
# **ولا يفحص الثالث** (المِرآة وinotify): لا أثرَ له يُقرأ من خارج العملية —
# يبقى شرطاً مكتوباً. **ويُقال هنا كي لا يُقرأ سكوتُه تغطية.**
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

problems=0
note() { printf '  %s\n' "$1"; }

# ── ١) صورةٌ أقدمُ من تبعياتها ──────────────────────────────────────────────
image_created=$(docker inspect taxo-app-backend --format '{{.Created}}' 2>/dev/null)
if [ -z "$image_created" ]; then
  note "· صورةُ الخلفية غيرُ مبنيّةٍ بعد — لا شيءَ يُقارَن."
else
  req_epoch=$(date -r backend/requirements.txt +%s 2>/dev/null || echo 0)
  img_epoch=$(date -d "$image_created" +%s 2>/dev/null || echo 0)
  if [ "$req_epoch" -gt "$img_epoch" ] && [ "$img_epoch" -gt 0 ]; then
    printf '\n✗ `backend/requirements.txt` أحدثُ من صورة الخلفية.\n' >&2
    note "تبعيةٌ أُعلنت ولم تدخل الصورة. **و\`restart\` لا يكفي** — يبدأ الحاويةَ"
    note "نفسَها من الصورة نفسِها، فالحزمةُ الجديدةُ غائبةٌ ببساطة."
    note "والمجموعةُ **لن تكشفه**: \`docker compose run\` يبني من الصورة كلَّ مرة."
    note ""
    note "  docker compose --env-file .env.local build backend"
    note "  docker compose --env-file .env.local up -d backend worker beat"
    problems=$((problems + 1))
  else
    note "✓ صورةُ الخلفية أحدثُ من \`requirements.txt\`."
  fi
fi

# ── ٢) خلفيةٌ حيّةٌ بلا نطاقات النفق ────────────────────────────────────────
if docker ps --format '{{.Names}}' | grep -q '^taxo-backend$'; then
  if docker inspect taxo-backend --format '{{range .Config.Env}}{{println .}}{{end}}' \
       | grep -q '^CORS_ORIGINS='; then
    note "✓ الخلفيةُ تحمل \`CORS_ORIGINS\` — طبقةُ النفق مرفوعةٌ معها."
  else
    printf '\n✗ الخلفيةُ تعمل بلا `CORS_ORIGINS`.\n' >&2
    note "رُفعت بلا \`docker-compose.tunnel.yml\`، فالهاتفان يقفان على «الشبكة"
    note "ضعيفة» **بينما \`curl\` من الجهاز يجيب ٢٠٠** — والشبكةُ سليمةٌ تماماً."
    note ""
    note "  docker compose --env-file .env.local \\"
    note "    -f docker-compose.yml -f docker-compose.tunnel.yml up -d backend"
    problems=$((problems + 1))
  fi
else
  note "· الخلفيةُ غيرُ عاملة — لا شيءَ يُقاس."
fi

if [ "$problems" -gt 0 ]; then
  printf '\n✗ %s من فخاخ الحاويات قائم.\n' "$problems" >&2
  exit 1
fi
printf '\n✓ لا فخَّ حاويةٍ قائماً — **والمِرآةُ/inotify خارج هذا القياس**، تبقى شرطاً.\n'
