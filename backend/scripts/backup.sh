#!/usr/bin/env bash
# نسخةٌ احتياطيةٌ واحدة (`design/BACKUP-AND-RESTORE.md`).
#
# **يُنفَّذ داخل حاوية الخلفية** — فيها `pg_dump 16` و`gpg`، ومنها يُرى مجلدُ
# المستندات. وتناديه المهمّةُ الدورية بـsubprocess، ويناديه المالكُ عبر SSH بـ
# `docker compose exec -T backend /app/scripts/backup.sh` — **ولا مسارَ ثانٍ
# يُنتج نسخةً بشكلٍ مختلف** (وهو شرطُ `pull-backup.ps1 -Now`).
#
# **والقاعدةُ أولاً ثم الملفات، وهو ليس تفصيلاً**: `core/storage.py` يكتب الملفَّ
# **قبل** صفِّه، فمستندٌ يُرفع بين اللحظتين يترك ملفاً بلا صفّ — **نفاية**، لا
# يراها أحدٌ ولا تكسر شيئاً. والعكسُ يترك **صفّاً يشير إلى ملفٍ ليس في الأرشيف**:
# عطبٌ ظاهرٌ في شاشة المراجعة، ومستندُ كبتنٍ ضاع.
#
# **ولا يقرأ `.env.local` ولا ينسخه** (قرارُ المالك ١): أرشيفٌ يحمل البياناتِ
# ومفتاحَها معاً خزنةٌ مفتاحُها ملصقٌ عليها. ومفتاحُ Fernet يُحفظ عند المالك،
# **واستعادةٌ بلا مفتاح تُنتج نظاماً يعمل بعقودٍ ميّتة** — تُدخَل من جديد.
#
# **ولا يوقف التطبيق**: `pg_dump` يقرأ لقطةً متسقة (MVCC).

set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/app/var/backups}"
STORAGE_ROOT="${STORAGE_ROOT:-/app/var/documents}"
# عبارةُ تشفير الأرشيف — **تسكن حيث يسكن مفتاحُ Fernet** (قرارُ المالك ٤):
# مكانٌ واحدٌ يعرفه المالك، فإن ضاع ضاع كلُّ شيءٍ معاً وإن حُفظ حُفظ معاً.
# **ونصفُ حفظٍ أسوأُ من لا شيء**: نسخٌ تُنقل ولا تُفتح.
BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-}"

# `DATABASE_URL` صيغتُها SQLAlchemy، و`pg_dump` لا يفهمها — فتُفكّ هنا.
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

# **بالثواني لا بالدقائق.** نسختان في الدقيقة نفسِها — وهو ما يقع حين يضغط
# المالكُ «الآن» بعد نسخةٍ مجدولة — كانتا تحملان الاسمَ نفسَه، فـ`mv` ينقل
# الثانيةَ **داخل** الأولى: مجلدٌ يحمل بياناً لا يصفه، ونسخةٌ تُقرأ صالحةً حتى
# يومِ الاستعادة. وجدَه ثاني تشغيلٍ للسكربت، لا مراجعةٌ ولا اختبار.
STAMP="$(date -u +%Y%m%d-%H%M%S)"
NAME="taxo-${STAMP}"
DEST="${BACKUP_ROOT}/${NAME}"

# **وحارسٌ صريحٌ فوق ذلك**: الثواني تجعل الاصطدامَ بعيداً لا مستحيلاً، و`mv`
# فوق مجلدٍ قائمٍ لا يفشل بل **يُعشِّش** — وهو الشكلُ الذي لا يُكتشف
if [ -e "$DEST" ]; then
  echo "نسخةٌ بهذا الاسم موجودةٌ سلفاً: ${DEST}" >&2
  exit 1
fi

# **ويُبنى في مجلدٍ مؤقّتٍ ثم يُنقل**: نسخةٌ نصفُ مكتملةٍ تحمل اسماً نهائياً
# تُقرأ نسخةً صالحة — من اللوحة ومن `pull-backup` معاً — حتى يومِ الاستعادة.
TMP="${BACKUP_ROOT}/.${NAME}.partial"
rm -rf "$TMP"
mkdir -p "$TMP"

cleanup() {
  # فشلٌ يترك المؤقّتَ فيُحذف — ولا يترك اسماً نهائياً أبداً
  [ -d "$TMP" ] && rm -rf "$TMP"
}
trap cleanup EXIT

echo "==> pg_dump"
pg_dump -Fc --no-owner --no-acl -f "${TMP}/db.dump"

echo "==> files"
if [ -d "$STORAGE_ROOT" ]; then
  tar -czf "${TMP}/files.tar.gz" -C "$STORAGE_ROOT" .
else
  # **مجلدٌ غيرُ موجودٍ ليس خطأً**: تثبيتٌ لم يُرفع فيه مستندٌ بعد
  tar -czf "${TMP}/files.tar.gz" -T /dev/null
fi

REVISION="$(psql -tAc 'SELECT version_num FROM alembic_version LIMIT 1' 2>/dev/null || echo '')"

if [ -n "$BACKUP_PASSPHRASE" ]; then
  echo "==> gpg"
  # **يُشفَّر قبل أن يغادر الخادم** (قرارُ المالك ٤): يعبر الشبكةَ ويحمل بياناتِ
  # المستخدمين ودفترَ المحافظ.
  #
  # **والتشفيرُ قبل البيان لا بعده**: البصمةُ يجب أن تكون بصمةَ **ما يُنقل
  # فعلاً**، وإلا رفض `pull-backup` كلَّ نسخةٍ مشفَّرةٍ — أو تحقّق منها بفكِّ
  # تشفيرٍ يحتاج العبارةَ على جهاز السحب، وهو ما يُبطل نقلَ العبارة عن الشبكة.
  for item in db.dump files.tar.gz; do
    gpg --batch --yes --symmetric --cipher-algo AES256 \
      --passphrase "$BACKUP_PASSPHRASE" \
      -o "${TMP}/${item}.gpg" "${TMP}/${item}"
    rm -f "${TMP}/${item}"
  done
fi

echo "==> manifest"
python3 - "$TMP" "$REVISION" <<'PY'
import hashlib
import json
import pathlib
import sys
from datetime import UTC, datetime

target = pathlib.Path(sys.argv[1])
revision = sys.argv[2].strip() or None


def digest(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# **يمرّ على ما وُجد فعلاً** لا على قائمةٍ ثابتة: مشفَّراً كانت الأسماءُ
# `*.gpg`، وقائمةٌ ثابتةٌ كانت ستنهار على ملفٍ غير موجود — أو أسوأ، تكتب بياناً
# لا يصف الأرشيف
files = {}
for item in sorted(target.iterdir()):
    if item.name == "manifest.json" or not item.is_file():
        continue
    files[item.name] = {"bytes": item.stat().st_size, "sha256": digest(item)}

# **ورقمُ الترحيلة في البيان**: به وحدَه يُعرف أن النسخةَ **أقدمُ من الكود**
# قبل محاولة استعادتها — لا بعد أن تُستعاد وتُصادف أعمدةً لا وجودَ لها
(target / "manifest.json").write_text(
    json.dumps(
        {
            "taken_at": datetime.now(UTC).isoformat(),
            "alembic_revision": revision,
            "encrypted": any(name.endswith(".gpg") for name in files),
            "files": files,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
PY

mv "$TMP" "$DEST"
trap - EXIT
echo "OK ${DEST}"
