#!/usr/bin/env bash
# **بروفةُ صورة الخلفية — قبل أن تُمسّ حاوية** (قرارُ المالك ٢٠٢٦-٠٩-٢٩).
#
# ## الثغرةُ التي سدّها
#
# بروفةُ `deploy.sh` كانت تبني **الواجهاتِ وحدَها**. وصورةُ الخلفية تُبنى في
# `up -d --build` نفسِه **الذي يستبدل الحاويات** — فعطبٌ في الصورة لا يظهر إلا
# والإنتاجُ ساقط. **ووقع قريباً**: القيدُ `sqlalchemy<3.0` حُلَّ إلى 2.1.1 فسقطت
# المجموعةُ كلُّها في CI (١٥١٦ خطأً، التشغيل 36576457431) — **وكان سيُبنى في
# أوّل رفعٍ يكسر خبيئةَ طبقة `pip`**.
#
# ## وسؤالان لا واحد — **والأوّلُ وحدَه لا يمسك ذلك العطب**
#
# 1. `import app.main` — ما يفعله الإقلاع.
# 2. **DDL النماذج كلِّها على محرّك PostgreSQL وهميّ** — بلا قاعدةٍ ولا شبكة.
#
# **قِيس أن الأوّلَ يمرّ على 2.1.1** (`rc=0`)، لأن العطبَ في حدث `before_create`
# من GeoAlchemy2 — **يقع حين يُنشأ جدولٌ لا حين يُستورد**. **والثاني يسقط بنصِّ
# المجموعة نفسِه**: `ColumnCollection is an abstract base class`. فالبروفةُ
# بسؤالٍ واحدٍ كانت ستُخضِّر العطبَ الذي وُجدت له.
#
# ## وما لا تقيسه — يُقال
#
# **لا تقيس الترحيلات ولا قاعدةً حيّة ولا Redis**: الصورةُ تُبنى وتُسأل عن نفسها.
# **وخُضرتُها «الصورةُ تُبنى، والتطبيقُ يُستورد، والنماذجُ تُولِّد DDL»** لا أكثر.
#
#     bash scripts/rehearse-backend.sh [وسم]     # من جذر المستودع، محلياً أو على الخادم
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

TAG="taxo-rehearse-backend:${1:-local}"
fail() { printf '\n✗ بروفةُ الخلفية: %s\n' "$1" >&2; shift; for l in "$@"; do printf '  %s\n' "$l" >&2; done; docker image rm -f "$TAG" >/dev/null 2>&1; exit 1; }

command -v docker >/dev/null 2>&1 || fail "لا docker — **وغيابُ أداة القياس يوقف ولا يُقرأ سلامة**."

echo "→ بروفةُ الخلفية: بناءُ $TAG (بلا لمس أيِّ حاوية)…"
# **الأثرُ يتدفّق لا يُكتم**: قناةُ ssh الصامتةُ دقائقَ تُقطع (درسٌ مسجَّلٌ في deploy.sh)
docker build --progress=plain -t "$TAG" backend || fail "تعذّر بناءُ صورة الخلفية — الأثرُ أعلاه."

# **قيمٌ للاستيراد وحدَه**: الإعدادُ يشترط عنوانَ قاعدة، ولا اتصالَ يقع أصلاً
PROBE='
import sqlalchemy, geoalchemy2
import app.main  # noqa: F401 — الإقلاعُ نفسُه، ويسجّل النماذجَ كلَّها
from sqlalchemy import create_mock_engine
from app.models.base import Base
emitted = []
engine = create_mock_engine("postgresql+asyncpg://", lambda sql, *a, **k: emitted.append(sql))
Base.metadata.create_all(engine, checkfirst=False)
print(f"REHEARSE_OK sqlalchemy={sqlalchemy.__version__} geoalchemy2={geoalchemy2.__version__} "
      f"tables={len(Base.metadata.tables)} ddl={len(emitted)}")
'
out="$(docker run --rm --network none \
  -e PYTHONPATH=/app \
  -e DATABASE_URL=postgresql+asyncpg://rehearse:rehearse@127.0.0.1:1/rehearse \
  -e REDIS_URL=redis://127.0.0.1:1/0 \
  --entrypoint python "$TAG" -c "$PROBE" 2>&1)"
code=$?
printf '%s\n' "$out" | tail -n 12
[ "$code" -eq 0 ] && printf '%s' "$out" | grep -q '^REHEARSE_OK ' \
  || fail "الصورةُ بُنيت ولا يُستورد التطبيقُ أو لا تُولِّد النماذجُ DDL (خرج $code)." \
          "**ولا تُستبدل الحاوياتُ بصورةٍ كهذه** — الأثرُ أعلاه، وآخرُ سطرٍ فيه السبب."

docker image rm -f "$TAG" >/dev/null 2>&1 || true
echo "✓ بروفةُ الخلفية خضراء — الصورةُ تُبنى، والتطبيقُ يُستورد، والنماذجُ تُولِّد DDL."
