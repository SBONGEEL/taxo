#!/usr/bin/env bash
# استعادةُ نسخةٍ احتياطية (`design/BACKUP-AND-RESTORE.md` §٧).
#
# **يُنفَّذ على الخادم**، ويُنادى من خارج الحاويات:
#
#   docker compose stop worker beat backend
#   docker compose run --rm --no-deps backend /app/scripts/restore.sh taxo-20260816-0300
#   docker compose up -d          # **إنشاءٌ لا `restart`** — انظر أدناه
#
# **وإيقافُ `worker` و`beat` أولاً ليس لأن الاستعادة تفشل بدونهم**، بل لأن مهمّةً
# دوريةً تكتب في قاعدةٍ نصفِ مستعادةٍ تُنتج حالاً **لا يوجد في أيِّ نسخة**.
#
# **والحكمُ ليس «لم يظهر خطأ»**: يطبع السكربتُ في آخره ما يُقاس — مجموعُ قيود كلِّ
# محفظةٍ مقابلَ آخر `balance_after`، وعددُ الرحلات والدفعات، وكم صفَّ مستندٍ بلا
# ملفٍّ على القرص. **ونسخةٌ تُستعاد بلا خطأٍ وبدفترٍ لا يُجمع ليست نسخة.**

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: restore.sh <backup-name-or-path> [--into DBNAME]" >&2
  exit 2
fi

SRC="$1"
shift
BACKUP_ROOT="${BACKUP_ROOT:-/app/var/backups}"
STORAGE_ROOT="${STORAGE_ROOT:-/app/var/documents}"
BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-}"
TARGET_DB=""

while [ $# -gt 0 ]; do
  case "$1" in
    --into) TARGET_DB="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[ -d "$SRC" ] || SRC="${BACKUP_ROOT}/${SRC}"
[ -d "$SRC" ] || { echo "لا توجد نسخة بهذا الاسم: $SRC" >&2; exit 1; }

python3 - <<'PY' > /tmp/_pgenv
import os
from urllib.parse import unquote, urlparse

url = urlparse(os.environ["DATABASE_URL"].replace("+asyncpg", ""))
print(f"export PGHOST={url.hostname}")
print(f"export PGPORT={url.port or 5432}")
print(f"export PGUSER={unquote(url.username or '')}")
print(f"export PGPASSWORD={unquote(url.password or '')}")
print(f"export PGDATABASE={(url.path or '/').lstrip('/')}")
PY
# shellcheck disable=SC1091
. /tmp/_pgenv
rm -f /tmp/_pgenv
[ -n "$TARGET_DB" ] && export PGDATABASE="$TARGET_DB"

echo "==> البيان"
python3 - "$SRC" <<'PY'
import hashlib
import json
import pathlib
import sys

target = pathlib.Path(sys.argv[1])
manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
print(f"    أُخذت: {manifest['taken_at']}")
print(f"    ترحيلة: {manifest.get('alembic_revision')}")

# **تُفحص البصماتُ قبل أيِّ كتابة** — لا بعد أن تُمحى القاعدةُ الحالية: نقلٌ
# مبتورٌ يصمت، ونسخةٌ نصفُها لا تُكتشف إلا بعد أن يُحذف ما كان يحلّ محلَّها
for name, meta in manifest["files"].items():
    item = target / name
    if not item.exists():
        sys.exit(f"ملفٌّ مفقود من النسخة: {name}")
    h = hashlib.sha256()
    with item.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != meta["sha256"]:
        sys.exit(f"بصمةٌ لا تطابق البيان: {name} — النسخةُ مبتورة")
print("    البصمات مطابقة")
PY

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

for item in db.dump files.tar.gz; do
  if [ -f "${SRC}/${item}.gpg" ]; then
    [ -n "$BACKUP_PASSPHRASE" ] || {
      echo "النسخة مشفَّرة و BACKUP_PASSPHRASE غير مضبوطة — وفقدُها فقدُ النسخ كلِّها" >&2
      exit 1
    }
    gpg --batch --yes --quiet --passphrase "$BACKUP_PASSPHRASE" \
      -o "${WORK}/${item}" -d "${SRC}/${item}.gpg"
  else
    cp "${SRC}/${item}" "${WORK}/${item}"
  fi
done

echo "==> pg_restore إلى ${PGDATABASE}"
# **و`postgis` يجب أن تكون منشأةً في القاعدة الهدف**، وإلا فشلت أوّلُ جملةٍ جغرافية
psql -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS postgis' >/dev/null
pg_restore --clean --if-exists --no-owner --no-acl -d "$PGDATABASE" "${WORK}/db.dump"

if [ -z "$TARGET_DB" ]; then
  echo "==> الملفات"
  mkdir -p "$STORAGE_ROOT"
  tar -xzf "${WORK}/files.tar.gz" -C "$STORAGE_ROOT"
else
  echo "==> الملفات: تُتخطّى (استعادةُ اختبارٍ في قاعدةٍ جانبية)"
fi

echo "==> الحكم — الدفترُ لا غيابُ الأخطاء"
psql -v ON_ERROR_STOP=1 -tA <<'SQL'
\echo '    محافظُ لا يوافق مجموعُها أيَّ رصيدٍ مسجَّل فيها:'
-- **ولا يُقارَن بـ«آخر صفّ» بالوقت.** قيدان يُكتبان في معاملةٍ واحدة يحملان
-- `created_at` نفسَه بالضبط (`now()` في بوستجرس وقتُ المعاملة لا وقتُ الجملة) —
-- وهو ما يقع فعلاً حين يُشحن رصيدٌ فيُحصَّل به دَينُ إلغاءٍ في المعاملة نفسِها.
-- وفكُّ التعادل بـ`id` ترتيبٌ عشوائيّ، فتُقرأ محفظةٌ **سليمة** غيرَ متوازنة.
--
-- وقد وقع ذلك في أوّل استعادةِ اختبار: أُبلغ عن محفظةٍ مختلّة ودفترُها صحيح.
-- **وإنذارٌ كاذبٌ في هذا الفحص أخطرُ من غيابه**: يُعلّم قارئَه أن «١» رقمٌ
-- عاديّ، فيمرّ به يومَ يكون حقيقياً.
--
-- فالمقيسُ ما لا يعتمد على ترتيب: **مجموعُ القيود يساوي أحدَ الأرصدة المسجَّلة
-- في المحفظة** — وهو الرصيدُ بعد آخر قيدٍ أيّاً كان ترتيبُها. وصفٌّ ناقصٌ أو
-- مبتورٌ يكسره كما يكسر المقارنةَ الأولى.
WITH sums AS (
  SELECT owner_id, owner_type, SUM(amount) AS total
  FROM wallet_transactions GROUP BY owner_id, owner_type
)
SELECT count(*) FROM sums WHERE NOT EXISTS (
  SELECT 1 FROM wallet_transactions w
  WHERE w.owner_id = sums.owner_id AND w.owner_type = sums.owner_type
    AND w.balance_after = sums.total
);

\echo '    قيودٌ برصيدٍ سالب:'
SELECT count(*) FROM wallet_transactions WHERE balance_after < 0;

\echo '    الرحلات / الدفعات / المستندات:'
SELECT (SELECT count(*) FROM rides), (SELECT count(*) FROM payments),
       (SELECT count(*) FROM driver_documents);
SQL

if [ -z "$TARGET_DB" ]; then
  echo "    صفوفُ مستنداتٍ بلا ملفٍّ على القرص:"
  psql -tA -c 'SELECT file_path FROM driver_documents' | while read -r rel; do
    [ -n "$rel" ] && [ ! -f "${STORAGE_ROOT}/${rel}" ] && echo "      ${rel}"
  done
  echo "    (لا سطرَ فوق = كلُّ صفٍّ له ملفُّه)"
fi

echo
echo "تمّت الاستعادة. **أعد إنشاء الحاويات لا restart**: asyncpg يخزّن أنواع"
echo "الـENUM لكل اتصال، وقاعدةٌ استُبدلت تحته تُنتج cache lookup failed for type."
echo "وإن كان الكودُ أحدثَ من ترحيلة البيان، شغّل: alembic upgrade head"
