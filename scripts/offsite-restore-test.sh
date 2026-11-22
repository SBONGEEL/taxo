#!/usr/bin/env bash
# **تجربةُ استعادةٍ من نسخةٍ خارج الموقع — على التطوير لا الإنتاج** (أمرُ المالك ٢٠٢٦-١١-٢٢ الثاني، البند ٣).
#
#   offsite-restore-test.sh                 # أحدثُ نسخةٍ على Drive
#   offsite-restore-test.sh <ملفّ .tar.gpg>  # نسخةٌ مشفَّرةٌ محلّيّة (تجربةُ الطريق قبل ربط Drive)
#
# يفكّ التشفير، ويستعيد `taxo.sql.gz` **في حاويةِ Postgres مؤقّتةٍ معزولة** (صورةُ الإنتاج نفسُها `postgis/postgis:16-3.4`،
# بلا منفذٍ منشور، تُحذف عند الانتهاء) — **فلا يمسّ قاعدةَ التطوير ولا الإنتاج**. ثم يعدّ صفوفَ جداول المال والهويّة
# ويقيس أن `.env` في النسخة يحمل قيماً. **ونسخةٌ لم تُستعد ليست نسخة.**
set -Eeuo pipefail
PASS_FILE="$HOME/.taxo-secrets/offsite-backup.passphrase"
REMOTE="${TAXO_OFFSITE_REMOTE:-gdrive-taxo:TAXO-backups}"
WORK="$(mktemp -d)"; CT="taxo-restore-test-$$"
cleanup() { docker rm -f "$CT" >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT

if [ $# -ge 1 ]; then
  SRC="$1"; echo "• المصدر: $SRC (محلّيّ)"
else
  OBJ="$(rclone lsf "$REMOTE" --files-only | grep -E '\.tar\.gpg$' | sed -E 's/^taxo-(daily-)?(.*)\.tar\.gpg$/\2 &/' | sort | tail -1 | awk '{print $2}')"
  [ -n "$OBJ" ] || { echo "✗ لا نسخةَ على $REMOTE"; exit 1; }
  echo "• المصدر: $REMOTE/$OBJ — يُنزَّل…"
  rclone copyto "$REMOTE/$OBJ" "$WORK/$OBJ"; SRC="$WORK/$OBJ"
fi

gpg --batch --pinentry-mode loopback --passphrase-file "$PASS_FILE" -d "$SRC" 2>/dev/null | tar -xf - -C "$WORK"
DIR="$(find "$WORK" -mindepth 1 -maxdepth 1 -type d | head -1)"
[ -s "$DIR/taxo.sql.gz" ] || { echo "✗ لا taxo.sql.gz في النسخة"; exit 1; }
echo "✓ فُكّ التشفير: $(ls "$DIR" | tr '\n' ' ')"
[ "$(tar -xzOf "$DIR/env.tar.gz" .env | grep -c '=')" -ge 3 ] && echo "✓ .env في النسخة يحمل قيماً"

# **والقاعدةُ تُنشأ من `template0` لا من تهيئة الصورة**: صورةُ postgis تُنشئ في `POSTGRES_DB` مخطّطاتِ tiger/topology سلفاً،
# فيصيح التفريغُ «already exists» ثلاثاً على استعادةٍ سليمة (قِيس ٢٢/١١) — وإنذارٌ كاذبٌ يعلّم تجاهلَ الإنذار.
# كلمةُ حاويةٍ مؤقّتةٍ بلا منفذٍ منشور تُحذف بعد دقائق — تُولَّد لا تُكتب، فلا حرفيَّ يصيح عليه ماسحُ الأسرار (قِيس ٢٢/١١)
THROWAWAY="$(openssl rand -hex 12)"
docker run -d --name "$CT" -e POSTGRES_PASSWORD="${THROWAWAY}" -e POSTGRES_USER=taxo -e POSTGRES_DB=postgres postgis/postgis:16-3.4 >/dev/null
# **صورةُ Postgres تُهيّئ ثم تُعيد التشغيل** — و`pg_isready` يجيب «جاهز» أثناء التهيئة، فاستعادةٌ تبدأ هناك تسقط مع الإعادة
# (وقع مقيساً ٢٢/١١). فيُنتظر سطرُ «init process complete» ثم الجاهزيّة.
for _ in $(seq 1 90); do
  docker logs "$CT" 2>&1 | grep -q "init process complete" && docker exec "$CT" pg_isready -U taxo -d postgres >/dev/null 2>&1 && break
  sleep 2
done
docker exec "$CT" pg_isready -U taxo -d postgres >/dev/null || { echo "✗ Postgres المؤقّت لم يجهز"; exit 1; }
docker exec "$CT" createdb -U taxo -T template0 taxo
zcat "$DIR/taxo.sql.gz" | docker exec -i "$CT" psql -q -U taxo -d taxo -v ON_ERROR_STOP=0 >/dev/null 2>"$WORK/restore.err"   || { echo "✗ psql لم يُكمل: $(tail -2 "$WORK/restore.err")"; exit 1; }
ERRS="$(grep -c 'ERROR' "$WORK/restore.err" || true)"
echo "• أخطاءُ الاستعادة: $ERRS $( [ "$ERRS" != 0 ] && head -3 "$WORK/restore.err" | cut -c1-160)"
docker exec "$CT" psql -U taxo -d taxo -tA -F ' = ' -c "
select 'الجداول', count(*) from information_schema.tables where table_schema='public'
union all select 'المستخدمون', count(*) from users
union all select 'قيودُ الدفتر', count(*) from wallet_transactions
union all select 'الرحلات', count(*) from rides
union all select 'الاشتراكات', count(*) from driver_subscriptions"
docker exec "$CT" psql -U taxo -d taxo -tAc "select version_num from alembic_version" | sed 's/^/• الترحيلة: /'
[ "$ERRS" = 0 ] && echo "✓ الاستعادةُ نظيفة" || { echo "✗ الاستعادةُ فيها أخطاء"; exit 1; }
