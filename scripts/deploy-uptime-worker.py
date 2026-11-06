"""ينشر مراقبَ التوفّر الخارجيّ (`ops/uptime-worker/worker.js`) على حساب Cloudflare القائم — البند ٧، أمرُ المالك ٢٠٢٦-١١-٠٦.

    python scripts/deploy-uptime-worker.py           # ينشر ويضبط المُشغِّل
    python scripts/deploy-uptime-worker.py --status  # يقرأ وحسب

**يقرأ رقمَ الحساب ورمزَه من `~/.taxo-secrets/cloudflare-delicate-block-888e.txt` ولا يطبع أيّاً منهما.** وعنوانُ التنبيه هو العنوانُ
**المُتحقَّقُ منه** في Email Routing بالحساب نفسِه (لا يُكتب في الشيفرة ولا في المستودع). **ولا يمسّ إلا ثلاثة**: الـWorker `taxo-uptime`،
ومُشغِّلَه (كلَّ دقيقة)، ومساحةَ KV `taxo-uptime-state`. لا Route، ولا شيءَ في النطاق — **ونطاقُ workers.dev للحساب (`taxo-ops`) شرطُ
Cloudflare للمُشغِّل وحدَه، والـWorker مطفأٌ عليه.**
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SECRET = Path.home() / ".taxo-secrets" / "cloudflare-delicate-block-888e.txt"
WORKER = Path(__file__).resolve().parent.parent / "ops" / "uptime-worker" / "worker.js"
NAME = "taxo-uptime"
KV_TITLE = "taxo-uptime-state"
CRON = "* * * * *"
API = "https://api.cloudflare.com/client/v4"


def creds() -> tuple[str, str]:
    lines = [line.strip() for line in SECRET.read_text(encoding="utf-8").splitlines()]
    return lines[lines.index("Account ID") + 1], lines[lines.index("Your API Token") + 1]


ACCOUNT, TOKEN = creds()


def call(method: str, path: str, body: bytes | None = None, content_type: str = "application/json") -> dict:
    request = urllib.request.Request(API + path, data=body, method=method,
                                     headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": content_type})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        data = json.load(error)
    if not data.get("success"):
        raise SystemExit(f"✗ {method} {path.split('?')[0]}: {[e.get('message') for e in data.get('errors', [])]}")
    return data


def alert_address() -> str:
    verified = [a["email"] for a in call("GET", f"/accounts/{ACCOUNT}/email/routing/addresses")["result"] if a.get("verified")]
    if len(verified) != 1:
        raise SystemExit(f"✗ يُنتظر عنوانٌ مُتحقَّقٌ واحد في Email Routing، ووُجد {len(verified)}")
    return verified[0]


def kv_namespace() -> str:
    for ns in call("GET", f"/accounts/{ACCOUNT}/storage/kv/namespaces?per_page=100")["result"]:
        if ns["title"] == KV_TITLE:
            return ns["id"]
    return call("POST", f"/accounts/{ACCOUNT}/storage/kv/namespaces", json.dumps({"title": KV_TITLE}).encode())["result"]["id"]


def status() -> None:
    scripts = [s["id"] for s in call("GET", f"/accounts/{ACCOUNT}/workers/scripts")["result"]]
    print("الـWorker:", "منشور" if NAME in scripts else "غيرُ منشور")
    if NAME in scripts:
        schedules = call("GET", f"/accounts/{ACCOUNT}/workers/scripts/{NAME}/schedules")["result"]["schedules"]
        print("المُشغِّل:", [s["cron"] for s in schedules])


def deploy() -> None:
    to = alert_address()
    kv = kv_namespace()
    metadata = {
        "main_module": "worker.js",
        "compatibility_date": "2026-10-01",
        "bindings": [
            {"type": "kv_namespace", "name": "STATE", "namespace_id": kv},
            {"type": "send_email", "name": "ALERT", "destination_address": to},
            {"type": "plain_text", "name": "ALERT_TO", "text": to},
        ],
    }
    boundary = uuid.uuid4().hex
    parts = [
        (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"; filename="metadata.json"\r\n'
         f"Content-Type: application/json\r\n\r\n").encode() + json.dumps(metadata).encode() + b"\r\n",
        (f'--{boundary}\r\nContent-Disposition: form-data; name="worker.js"; filename="worker.js"\r\n'
         f"Content-Type: application/javascript+module\r\n\r\n").encode() + WORKER.read_bytes() + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    call("PUT", f"/accounts/{ACCOUNT}/workers/scripts/{NAME}", b"".join(parts), f"multipart/form-data; boundary={boundary}")
    # **المُشغِّلُ يشترط نطاقَ workers.dev للحساب** (أُنشئ `taxo-ops` لهذا وحدَه ٢٠٢٦-١١-٠٦) — **والـWorker نفسُه بلا عنوانٍ عامّ** عليه
    call("POST", f"/accounts/{ACCOUNT}/workers/scripts/{NAME}/subdomain", json.dumps({"enabled": False}).encode())
    call("PUT", f"/accounts/{ACCOUNT}/workers/scripts/{NAME}/schedules", json.dumps([{"cron": CRON}]).encode())
    print(f"✓ نُشر {NAME} بمُشغِّل «{CRON}» ومساحة KV «{KV_TITLE}» — والتنبيهُ إلى العنوان المُتحقَّق منه في الحساب")
    status()


if __name__ == "__main__":
    status() if "--status" in sys.argv else deploy()
