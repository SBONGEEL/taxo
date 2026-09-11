"""يملأ CSV أمان البيانات لتطبيق الكبتن — من الشيفرة لا من الراكب.

    python3 tools/play-data-safety.py <export.csv> <out.csv>

ولا يخترع سؤالاً: يقرأ صفوف التصدير كما هي ويكتب `Response value` وحدَه،
ويسقط إن ذُكر معرِّفٌ ليس في الملف — فالخطأُ يُصاح به ولا يُبتلع.
"""

import csv
import io
import sys

TOP = {
    ("PSL_DATA_COLLECTION_COLLECTS_PERSONAL_DATA", ""): "true",
    ("PSL_DATA_COLLECTION_ENCRYPTED_IN_TRANSIT", ""): "true",
    ("PSL_SUPPORTED_ACCOUNT_CREATION_METHODS", "PSL_ACM_USER_ID_PASSWORD_OTHER_AUTH"): "true",
    ("PSL_ACCOUNT_DELETION_URL", ""): "https://taxo.tajora.ly/delete-account",
    ("PSL_SUPPORT_DATA_DELETION_BY_USER", "DATA_DELETION_NO"): "true",
    # **نُزع بنصّ رفضه**: «لا يمكنك الإجابة عن السؤال PSL_HAS_OUTSIDE_APP_ACCOUNTS.»
    # — سؤالٌ غيرُ منطبقٍ على هذا التطبيق، ووقع الرفضُ نفسُه للراكب.
}

# نوعُ البيانات → (مجموعتُه، الضرورة، أغراضُ الجمع)
REQ = "PSL_DATA_USAGE_USER_CONTROL_REQUIRED"
OPT = "PSL_DATA_USAGE_USER_CONTROL_OPTIONAL"
FUNC = "PSL_APP_FUNCTIONALITY"
ACCT = "PSL_ACCOUNT_MANAGEMENT"
FRAUD = "PSL_FRAUD_PREVENTION_SECURITY"

TYPES = {
    "PSL_NAME": ("PSL_DATA_TYPES_PERSONAL", REQ, [FUNC, ACCT]),
    "PSL_USER_ACCOUNT": ("PSL_DATA_TYPES_PERSONAL", REQ, [FUNC, ACCT]),
    "PSL_PHONE": ("PSL_DATA_TYPES_PERSONAL", REQ, [FUNC, FRAUD, ACCT]),
    "PSL_OTHER_PERSONAL": ("PSL_DATA_TYPES_PERSONAL", REQ, [FUNC, FRAUD, ACCT]),
    "PSL_CREDIT_DEBIT_BANK_ACCOUNT_NUMBER": ("PSL_DATA_TYPES_FINANCIAL", OPT, [FUNC]),
    "PSL_PURCHASE_HISTORY": ("PSL_DATA_TYPES_FINANCIAL", REQ, [FUNC, ACCT]),
    "PSL_OTHER": ("PSL_DATA_TYPES_FINANCIAL", REQ, [FUNC, ACCT]),
    "PSL_APPROX_LOCATION": ("PSL_DATA_TYPES_LOCATION", REQ, [FUNC]),
    "PSL_PRECISE_LOCATION": ("PSL_DATA_TYPES_LOCATION", REQ, [FUNC]),
    "PSL_PHOTOS": ("PSL_DATA_TYPES_PHOTOS_AND_VIDEOS", REQ, [FUNC, ACCT]),
    "PSL_FILES_AND_DOCS": ("PSL_DATA_TYPES_FILES_AND_DOCS", REQ, [FUNC, ACCT]),
    "PSL_USER_GENERATED_CONTENT": ("PSL_DATA_TYPES_APP_ACTIVITY", OPT, [FUNC]),
    "PSL_DEVICE_ID": ("PSL_DATA_TYPES_IDENTIFIERS", OPT, [FUNC]),
}

src, dst = sys.argv[1], sys.argv[2]
rows = list(csv.reader(io.open(src, encoding="utf-8")))
head, body = rows[0], rows[1:]

want = dict(TOP)
for t, (group, control, purposes) in TYPES.items():
    want[(group, t)] = "true"
    want[(f"PSL_DATA_USAGE_RESPONSES:{t}:PSL_DATA_USAGE_COLLECTION_AND_SHARING",
          "PSL_DATA_USAGE_ONLY_COLLECTED")] = "true"
    want[(f"PSL_DATA_USAGE_RESPONSES:{t}:PSL_DATA_USAGE_EPHEMERAL", "")] = "false"
    want[(f"PSL_DATA_USAGE_RESPONSES:{t}:DATA_USAGE_USER_CONTROL", control)] = "true"
    for p in purposes:
        want[(f"PSL_DATA_USAGE_RESPONSES:{t}:DATA_USAGE_COLLECTION_PURPOSE", p)] = "true"

present = {(r[0], r[1]) for r in body}
missing = sorted(k for k in want if k not in present)
if missing:
    raise SystemExit("✗ معرِّفاتٌ ليست في التصدير:\n  " + "\n  ".join(map(str, missing)))

filled = 0
for r in body:
    v = want.get((r[0], r[1]))
    if v is not None:
        r[2] = v
        filled += 1

with io.open(dst, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\r\n")
    w.writerow(head)
    w.writerows(body)

print(f"  ✓ {dst}")
print(f"    صفوفٌ مُلئت: {filled} / {len(body)}   ·   أنواعُ بيانات: {len(TYPES)}")
