"""play_api.py — Google Play Developer API بحساب الخدمة (SPEC §٧٦-ح) — مكتبةُ بايثون القياسيّة و openssl وحدَهما.

    python3 scripts/play_api.py read          # قراءةٌ وحدَها: مساراتُ التطبيقين وبطاقاتُهما ومجموعاتُ مختبِري المسار المغلق — تعديلٌ يُفتح ثمّ يُحذف بلا commit

**المفتاحُ لا يُطبع ولا يُكتب في سجلّ**: يُقرأ من ~/.taxo-secrets/play-api/ (ملفٌّ واحد)، ويُكتب المفتاحُ الخاصُّ لحظةَ التوقيع في ملفٍّ
مؤقّتٍ بصلاحيّة 600 داخل المجلّد نفسِه ويُحذف فوراً. **ولا يُطبع الرمزُ (access token) أبداً.**
"""

import base64
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KEY_DIR = pathlib.Path.home() / ".taxo-secrets" / "play-api"
API = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
APPS = ("ly.tajora.rider", "ly.tajora.driver")


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def key_file() -> pathlib.Path:
    files = sorted(p for p in KEY_DIR.glob("*.json") if p.is_file())
    if len(files) != 1:
        raise SystemExit(f"✗ يُنتظر ملفُّ مفتاحٍ واحدٌ في {KEY_DIR} — وُجد {len(files)}")
    return files[0]


def access_token() -> str:
    info = json.loads(key_file().read_text())
    now = int(time.time())
    header = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64(json.dumps({"iss": info["client_email"], "scope": SCOPE, "aud": info["token_uri"],
                             "iat": now, "exp": now + 600}).encode())
    signing_input = f"{header}.{claims}".encode()
    tmp = KEY_DIR / f".sign-{os.getpid()}.pem"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(info["private_key"])
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(tmp)], input=signing_input,
                             capture_output=True, check=True).stdout
    finally:
        tmp.unlink(missing_ok=True)
    assertion = f"{header}.{claims}.{b64(sig)}"
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": assertion}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(info["token_uri"], data=body), timeout=30) as r:
            return json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"✗ تبادلُ الرمز {e.code}: {json.loads(e.read() or b'{}').get('error_description', '')}")


def call(token: str, method: str, path: str) -> dict:
    req = urllib.request.Request(f"{API}/{path}", method=method, headers={"Authorization": f"Bearer {token}"},
                                 data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = json.loads(e.read() or b"{}").get("error", {})
        return {"_error": f"{e.code} {err.get('status', '')}: {err.get('message', '')[:300]}"}


def read() -> int:
    token = access_token()
    print("✓ رمزُ الوصول صدر (لا يُطبع)")
    rc = 0
    for pkg in APPS:
        edit = call(token, "POST", f"{pkg}/edits")
        if "_error" in edit:
            print(f"✗ {pkg}: فتحُ التعديل — {edit['_error']}")
            rc = 1
            continue
        eid = edit["id"]
        try:
            tracks = call(token, "GET", f"{pkg}/edits/{eid}/tracks")
            listings = call(token, "GET", f"{pkg}/edits/{eid}/listings")
            details = call(token, "GET", f"{pkg}/edits/{eid}/details")
            testers = call(token, "GET", f"{pkg}/edits/{eid}/testers/alpha")
        finally:
            gone = call(token, "DELETE", f"{pkg}/edits/{eid}")
        print(f"\n== {pkg}")
        if "_error" in tracks:
            print("  ✗ المسارات —", tracks["_error"])
            rc = 1
        for t in tracks.get("tracks", []):
            rel = [f"{r.get('name', '?')} [{','.join(r.get('versionCodes', []))}] {r.get('status')}" for r in t.get("releases", [])]
            print(f"  مسار {t['track']}: " + (" | ".join(rel) or "—"))
        if "_error" in listings:
            print("  ✗ البطاقات —", listings["_error"])
            rc = 1
        for li in listings.get("listings", []):
            print(f"  بطاقة {li['language']}: «{li.get('title')}» · القصير {len(li.get('shortDescription', ''))} حرفاً")
        if "_error" in testers:
            print("  ✗ مختبِرو alpha —", testers["_error"])
            rc = 1
        else:
            print("  مجموعاتُ مختبِري alpha: " + (", ".join(testers.get("googleGroups", [])) or "—"))
        if "_error" not in details:
            print(f"  اللغةُ التلقائيّة: {details.get('defaultLanguage')}")
        print("  التعديلُ حُذف بلا commit" if "_error" not in gone else f"  ✗ حذفُ التعديل — {gone['_error']}")
    return rc


if __name__ == "__main__":
    if sys.argv[1:] != ["read"]:
        raise SystemExit(__doc__)
    sys.exit(read())
