"""vault_put.py — يضيف سرّاً إلى خزنة TAXO أو يحدّثه، **ويحفظ القيمةَ القديمة في سجلّ المدخل بتاريخها** (قاعدةُ المالك الدائمة ٢٠٢٦-١١-٢٣، `design/OWNER-2026-11-23-VAULT-BACKUP.md`).

    python3 scripts/vault_put.py --group "البريد" --title "Resend — مفتاحُ الإرسال" --file <ملفُّ القيمة>
        [--username U] [--url URL] [--service S] [--purpose P] [--where W] [--status S]
        [--attach <ملفّ>]      # مرفقٌ (مفتاحٌ خاصّ، JSON حسابِ خدمة، keystore)

**القيمةُ من ملفٍّ لا من سطر الأمر** — سطرُ الأمر يُرى في قائمة العمليّات وسجلِّ الصدفة. ولا يطبع القيمةَ أبداً؛ يطبع سطراً واحداً:
«أضفت إلى الخزنة: <الاسم>» أو «حدّثت في الخزنة: <الاسم> (القديمُ في السجلّ)». والخزنةُ تُفتح من جديد بعد الحفظ وإلا خرج بغير الصفر.

الخزنة: `C:/Users/loly3/OneDrive/Desktop/TAXO-VAULT.kdbx` · كلمتُها: `C:/Users/loly3/.taxo-secrets/vault-master.txt` (خارج OneDrive).
"""
import argparse
import os
import sys
from datetime import datetime, timezone

from pykeepass import PyKeePass

VAULT = os.environ.get("TAXO_VAULT", "/mnt/c/Users/loly3/OneDrive/Desktop/TAXO-VAULT.kdbx")
MASTER = os.environ.get("TAXO_VAULT_MASTER", "/mnt/c/Users/loly3/.taxo-secrets/vault-master.txt")

ap = argparse.ArgumentParser()
ap.add_argument("--group", required=True)
ap.add_argument("--title", required=True)
ap.add_argument("--file", help="ملفٌّ فيه القيمة (سطرٌ واحد)")
ap.add_argument("--username", default=None)
ap.add_argument("--url", default=None)
ap.add_argument("--service", default="")
ap.add_argument("--purpose", default="")
ap.add_argument("--where", default="")
ap.add_argument("--status", default="")
ap.add_argument("--attach", action="append", default=[])
a = ap.parse_args()

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
pw = open(MASTER, encoding="utf-8").read().strip()
kp = PyKeePass(VAULT, password=pw)
value = open(a.file, encoding="utf-8").read().strip() if a.file else None

grp = kp.find_groups(name=a.group, first=True) or kp.add_group(kp.root_group, a.group)
e = kp.find_entries(title=a.title, group=grp, recursive=False, first=True)
created = e is None
if created:
    e = kp.add_entry(grp, a.title, a.username or "", value or "", url=a.url, force_creation=True)
else:
    e.save_history()  # القديمُ إلى السجلّ بتاريخه قبل أيِّ تغيير
    if value is not None:
        e.password = value
    if a.username is not None:
        e.username = a.username
    if a.url is not None:
        e.url = a.url
notes = [l for l in (e.notes or "").splitlines() if not l.startswith("التاريخ (إنشاءٌ أو آخرُ تغيير):")]
for label, val in (("الخدمة", a.service), ("الاستعمال", a.purpose), ("أين يُحفظ أيضاً", a.where), ("الحالة", a.status)):
    if val:
        notes = [l for l in notes if not l.startswith(label + ":")] + [f"{label}: {val}"]
notes.append(f"التاريخ (إنشاءٌ أو آخرُ تغيير): {today}")
e.notes = "\n".join(notes)
for path in a.attach:
    bid = kp.add_binary(open(path, "rb").read())
    e.add_attachment(bid, os.path.basename(path))
e.touch(modify=True)
kp.save()

check = PyKeePass(VAULT, password=pw)
if not check.find_entries(title=a.title, first=True):
    sys.exit("✗ لم يُعثر على المدخل بعد الحفظ")
print(("أضفت إلى الخزنة: " if created else "حدّثت في الخزنة: ") + a.title + ("" if created else " (القديمُ في السجلّ)"))
