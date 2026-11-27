#!/usr/bin/env bash
# **الحكمُ على أرقام النسخة** (قرارُ المالك ٢٠٢٦-١١-٢٧، `design/OWNER-2026-11-27-BACKUP.md`).
#
# يقرأ `key=value` من stdin (من `backup_metrics` — على الخادم أو على الحاسوب) ويحكم **بالعتبات نفسِها** التي كانت في البوّابة
# الرابعة («نسخةٌ لم تُفتح ليست نسخة»)، **وزادت خاتمةُ التفريغ**. ويخرج بـ0 حين تخضرّ كلُّها.
#
# **والحكمُ على الحاسوب لا على الخادم**: الخادمُ يقيس أرقاماً، ومن يرفع يحكم — فلا تُخضِّر النسخةُ نفسَها.
set -u

declare -A M
while IFS='=' read -r k v; do
  k="${k%$'\r'}"; v="${v%$'\r'}"
  [ -n "$k" ] && M["$k"]="$v"
done

g() { printf '%s' "${M[$1]:-}"; }
num() { case "$1" in ''|*[!0-9]*) echo 0 ;; *) echo "$1" ;; esac; }
FAIL=0
ok()  { printf '  ✓ %s\n' "$1"; }
bad() { printf '  ✗ %s\n' "$1"; FAIL=1; }

part() { # مفتاح · وصف — يُفتح؟ (والحجمُ يكشف الفراغَ وحدَه، والمحتوى يحكم)
  if [ "$(g "present_$1")" != 1 ]; then bad "$2 — غائب"; return 1; fi
  if [ "$(num "$(g "bytes_$1")")" -eq 0 ]; then bad "$2 — فارغ"; return 1; fi
  if [ "$(g "gzip_$1")" != 1 ]; then bad "$2 — لا يُفتح"; return 1; fi
  return 0
}

if part taxo "القاعدة"; then
  h=$(num "$(g sql_header)"); t=$(num "$(g sql_tables)"); c=$(num "$(g sql_complete)")
  if [ "$h" -ge 1 ] && [ "$t" -ge 20 ] && [ "$c" -ge 1 ]; then
    ok "القاعدة — ترويسة $h · جداول $t · خاتمةُ التفريغ موجودة ($(g bytes_taxo) بايت)"
  else
    bad "القاعدة — ترويسة $h · جداول $t · خاتمةُ التفريغ $c (تفريغٌ بلا خاتمةٍ قُطع في منتصفه)"
  fi
fi

if part env "الأسرار"; then
  e=$(num "$(g env_lines)")
  if [ "$e" -ge 5 ]; then ok "الأسرار — أسطرُ إعدادٍ حقيقية: $e"; else bad "الأسرار — أسطرُ إعدادٍ حقيقية: $e (وصلةٌ بلا هدف؟)"; fi
fi

if [ "$(g present_outside)" = 1 ] && part outside "ما خارج الشجرة"; then
  o=$(num "$(g outside_tunnel)")
  if [ "$o" -ge 2 ]; then ok "ما خارج الشجرة — بيانُ النفق ومعرِّفُه: $o من ٢"; else bad "ما خارج الشجرة — بيانُ النفق ومعرِّفُه: $o من ٢"; fi
fi

if [ "$(g present_untracked)" = 1 ] && part untracked "غيرُ المتتبَّع"; then
  u=$(num "$(g untracked_entries)")
  if [ "$u" -ge 1 ]; then ok "غيرُ المتتبَّع — $u مدخلاً"; else bad "غيرُ المتتبَّع — صفرُ مدخل"; fi
fi

if [ "$(g present_documents)" = 1 ] && part documents "الوثائق"; then
  rows="$(g doc_rows)"; files=$(num "$(g doc_files)")
  # **رأسُ الجدولِ غيرُ مقروءٍ ⇒ لا يُقاس ⇒ لا يُخضَّر**، وصفرٌ في الطرفين حالٌ صحيحة
  case "$rows" in
    ''|*[!0-9]*) bad "الوثائق — صفوفُ driver_documents لم تُقرأ" ;;
    0) ok "الوثائق — صفرُ صفٍّ وصفرُ ملفٍّ مطلوب" ;;
    *) if [ "$files" -ge 1 ]; then ok "الوثائق — $files ملفّاً · $rows صفّاً"; else bad "الوثائق — $rows صفّاً وصفرُ ملفٍّ في الأرشيف"; fi ;;
  esac
fi

if [ "$(g present_wa_auth)" = 1 ]; then
  if part wa_auth "جلسة واتساب"; then
    w=$(num "$(g wa_creds)")
    if [ "$w" -ge 1 ]; then ok "جلسة واتساب — ملفُّ الاعتماد موجود"; else bad "جلسة واتساب — بلا creds.json"; fi
  fi
else
  printf '  ⚠ جلسة واتساب — **لم تُنسخ**: الحاويةُ غيرُ عاملةٍ أو بلا جلسة (لا يُسقط الرفع)\n'
fi

sha="$(g bundle_sha256)"
if [ "$(g bundle_tar_ok)" = 1 ] && [ "$(num "$(g bundle_bytes)")" -gt 0 ] && [[ "$sha" =~ ^[0-9a-f]{64}$ ]]; then
  ok "الحزمة — $(g bundle_bytes) بايت · sha256 ${sha:0:12}…"
else
  bad "الحزمة — لا تُفتح أو بلا ختم"
fi

exit "$FAIL"
