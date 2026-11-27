# shellcheck shell=bash
# **أرقامُ النسخة — تُقاس ولا يُحكم بها هنا** (قرارُ المالك ٢٠٢٦-١١-٢٧، `design/OWNER-2026-11-27-BACKUP.md`).
#
# يُستعمل في موضعين **بالدالّة نفسِها**: على الخادم بعد بناء الأجزاء (`backup-on-server.sh` — يُرفع ملتصقاً بها)،
# وعلى الحاسوب بعد التنزيل (`backup-fetch.sh`). **فما قِيس هناك يُعاد قياسُه هنا بالسطر نفسِه** — لا قياسان يفترقان.
#
# يطبع `key=value` وحدَها، **ولا يطبع من محتوى الأسرار إلا عددَ أسطرها**. والحكمُ في `backup-judge.sh`.

_bm_count() { # عدُّ ما يطابق — و`grep -c` يقرأ إلى الآخر فلا SIGPIPE تحت pipefail
  grep -c "$@" 2>/dev/null || true
}

backup_metrics() {
  local d="$1" f key
  for f in taxo.sql.gz env.tar.gz outside.tar.gz untracked.tar.gz documents.tar.gz wa_auth.tar.gz; do
    key="${f%%.*}"
    if [ -f "$d/$f" ]; then
      echo "present_$key=1"
      echo "bytes_$key=$(stat -c %s "$d/$f" 2>/dev/null || echo 0)"
      if gzip -t "$d/$f" 2>/dev/null; then echo "gzip_$key=1"; else echo "gzip_$key=0"; fi
    else
      echo "present_$key=0"
    fi
  done
  if [ -f "$d/taxo.sql.gz" ]; then
    echo "sql_header=$(gzip -dc "$d/taxo.sql.gz" 2>/dev/null | _bm_count 'PostgreSQL database dump')"
    echo "sql_tables=$(gzip -dc "$d/taxo.sql.gz" 2>/dev/null | _bm_count '^CREATE TABLE')"
    # **قابليّةُ الاستعادة لتفريغٍ نصّيّ**: `pg_dump` لا يكتب خاتمتَه إلا إن أتمّ — وتفريغٌ قُطع في منتصفه بلا خاتمة.
    # (`pg_restore --list` لصيغة `-Fc` وحدَها، وتفريغُنا نصّيٌّ يُستعاد بـ`psql`.)
    echo "sql_complete=$(gzip -dc "$d/taxo.sql.gz" 2>/dev/null | tail -n 20 | _bm_count 'PostgreSQL database dump complete')"
  fi
  [ -f "$d/env.tar.gz" ] && echo "env_lines=$(gzip -dc "$d/env.tar.gz" 2>/dev/null | tar -xO 2>/dev/null | _bm_count -E '^[A-Z][A-Z0-9_]+=.')"
  [ -f "$d/outside.tar.gz" ] && echo "outside_tunnel=$(tar -tzf "$d/outside.tar.gz" 2>/dev/null | _bm_count -E 'cloudflared/.*\.json$|tunnel-id$')"
  [ -f "$d/untracked.tar.gz" ] && echo "untracked_entries=$(tar -tzf "$d/untracked.tar.gz" 2>/dev/null | _bm_count .)"
  if [ -f "$d/documents.tar.gz" ]; then
    echo "doc_files=$(tar -tzf "$d/documents.tar.gz" 2>/dev/null | _bm_count -v '/$')"
    echo "doc_rows=$(tr -d ' \r\n' < "$d/docs.rows" 2>/dev/null)"
  fi
  if [ -f "$d/wa_auth.tar.gz" ]; then
    echo "wa_creds=$(tar -tzf "$d/wa_auth.tar.gz" 2>/dev/null | _bm_count 'creds\.json$')"
    echo "wa_entries=$(tar -tzf "$d/wa_auth.tar.gz" 2>/dev/null | _bm_count -v '/$')"
  fi
  echo "raw_count=$(tr -d ' \r\n' < "$d/raw.count" 2>/dev/null)"
  echo "untracked_count=$(tr -d ' \r\n' < "$d/untracked.count" 2>/dev/null)"
  echo "outside_list=$(tr '\n' ' ' < "$d/outside.list" 2>/dev/null)"
}
