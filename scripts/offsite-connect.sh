#!/usr/bin/env bash
# **خطوةُ المالك الوحيدة** لربط Google Drive بالنسخ خارج الموقع (أمرُ المالك ٢٠٢٦-١١-٢٢ الثاني، البند ٣).
#
# يُشغَّل مرّةً من PowerShell:   wsl -- bash ~/prj/TAXO/scripts/offsite-connect.sh
# فيطبع رابطاً يُفتح في المتصفّح: يختار المالكُ حسابَه في Google ويضغط «سماح». **لا كلمةَ مرورٍ تُكتب هنا ولا في أيِّ محادثة.**
#
# **والنطاقُ `drive.file`**: يرى rclone **ما أنشأه هو وحدَه** — المجلّدَ «TAXO-backups» وما فيه — ولا يرى بقيّةَ Drive المالك
# ولا يقرؤها. (Google لا تعرض صلاحيةَ «مجلّدٍ بعينه»؛ وهذا أضيقُ ما تعرضه، وهو يساوي المجلّدَ الواحد عملاً.)
set -euo pipefail
NAME="gdrive-taxo"
if rclone listremotes | grep -qx "$NAME:"; then
  echo "• الربطُ قائمٌ سلفاً ($NAME) — يُجدَّد الإذن فقط"
  rclone config reconnect "$NAME:" --auto-confirm
else
  echo "• افتح الرابطَ الذي سيظهر الآن في المتصفّح، واختر حسابَ Google، ثم «سماح»."
  rclone config create "$NAME" drive scope=drive.file
fi
rclone mkdir "$NAME:TAXO-backups"
rclone lsd "$NAME:" | grep -q "TAXO-backups" && echo "✓ تمّ: المجلّد «TAXO-backups» جاهز، والنسخُ اليوميّةُ ستُرفع إليه مشفَّرةً تلقائيّاً."
