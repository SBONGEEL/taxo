"""play_api.py — Google Play Developer API بحساب الخدمة (SPEC §٧٦-ح، §٧٩) — مكتبةُ بايثون القياسيّة و openssl وأدواتُ SDK وحدَها.

    python3 scripts/play_api.py read          # قراءةٌ وحدَها: مساراتُ التطبيقين وبطاقاتُهما ومجموعاتُ مختبِري المسار المغلق — تعديلٌ يُفتح ثمّ يُحذف بلا commit
    python3 scripts/play_api.py signing       # قراءةٌ وحدَها: شهادةُ توقيع Play لكلِّ تطبيق (من آخر رمزٍ رُفع) مقابلَ المسجَّلة هنا، وأعلى رمزٍ في كلِّ مسار
    python3 scripts/play_api.py preflight [<rider.aab> <driver.aab>]
                                              # **فحصُ ما قبل كلِّ رفع** (§٧٩ البند ٣): موقَّعةٌ بمفتاح الرفع · رمزُها أعلى من كلِّ ما على Play ·
                                              # وحزمتا الموقع بتوقيع Play ورمزُهما لا يعلو رمزَ Play (بلا حزمٍ: الموقعُ وحدَه). **ويخرج بغير الصفر إن سقط شيء**
    python3 scripts/play_api.py upload <pkg> <aab> <name> <notes.json>
                                              # **المسارُ المغلقُ (alpha) وحدَه** (§٧٦-ط: روتينٌ يُفعل ثمّ يُبلَّغ) — **ويسبقه فحصُ الحزمة نفسِها
                                              # ولا يُرفع إن سقط**. ولا يمسّ مسارَ الإنتاج ولا البلدانَ ولا المختبِرين
    python3 scripts/play_api.py universal <versionCode> <outdir>
                                              # **حزمتا الموقع من Play نفسِه** (§٧٩ البند ٢): «الحزمةُ الشاملة» التي يولّدها Play ويوقّعها بمفتاحه،
                                              # تُنزَّل وتُقاس شهادتُها ورمزُها ومعرّفُها، ويُكتب معها `manifest.json` بشكل صفحة التحميل

**المفتاحُ لا يُطبع ولا يُكتب في سجلّ**: يُقرأ من ~/.taxo-secrets/play-api/ (ملفٌّ واحد)، ويُكتب المفتاحُ الخاصُّ لحظةَ التوقيع في ملفٍّ
مؤقّتٍ بصلاحيّة 600 داخل المجلّد نفسِه ويُحذف فوراً. **ولا يُطبع الرمزُ (access token) أبداً.**

**ولا يمسّ أيُّ أمرٍ هنا إعداداتِ المفاتيح في Play Console** (شرطُ المالك ٢٠٢٦-١٠-١٨): لا تدويرَ ولا تغييرَ لمفتاح الرفع ولا لمفتاح توقيع
التطبيق — **قراءةُ الشهادة وتنزيلُ ما وقّعه Play قراءتان**.
"""

import base64
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

KEY_DIR = pathlib.Path.home() / ".taxo-secrets" / "play-api"
API = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
APPS = ("ly.tajora.rider", "ly.tajora.driver")
SITE = "https://taxo.tajora.ly"

# **الشهاداتُ الثلاثُ مسجَّلةٌ هنا — بصماتٌ عامّةٌ لا أسرار** (قِيست ٢٠٢٦-١٠-١٨، SPEC §٧٩).
# **مفتاحُ الرفع واحدٌ للتطبيقين** (`taxo` في المخزن)، **ومفتاحُ توقيع Play لكلِّ تطبيقٍ مفتاحُه** — ويولّده Google ولا يُسلَّم.
# **وتُقارَن بما يقوله Play في كلِّ تشغيل**: افتراقُهما خبرٌ عن المفاتيح نفسِها، **فيوقف ولا يُصحَّح هنا** — ولا تُغيَّر هذه الأسطرُ
# إلا بكلمة المالك بعد أن يرى الكونسول.
UPLOAD_CERT = "3B:DC:73:91:8E:2D:C4:C1:B8:7D:BA:85:9E:15:B2:7C:7A:89:0E:21:57:9C:66:5E:21:07:69:CE:0C:5C:E1:9E"
PLAY_CERT = {
    "ly.tajora.rider": "9E:E8:58:36:23:75:93:E7:DC:8B:EA:69:EB:C5:13:B9:94:4E:3F:E6:E0:DE:CD:C9:38:17:3D:F2:C8:29:88:01",
    "ly.tajora.driver": "1E:66:E7:52:C3:34:84:FF:EA:93:2D:61:8E:28:BC:DD:D4:4C:09:0C:B3:CB:ED:15:9D:67:A1:66:8E:98:54:7B",
}
# **اسمُ ملفِّ الموقع ومفتاحُ البيان** — كما تقرؤهما `site/download.html` و`tools/check-apk.mjs`
SITE_FILE = {"ly.tajora.rider": ("rider", "تطبيق الراكب", "taxo-rider.apk"),
             "ly.tajora.driver": ("driver", "تطبيق الكبتن", "taxo-driver.apk")}


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


# ═══ أدواتُ القياس — **من داخل الملفّ لا من اسمه** ═══

def sdk_tool(name: str) -> str:
    """`apksigner`/`aapt2` من أحدث `build-tools` — **وغيابُها يوقف ولا يُقرأ سلامة** (القاعدةُ الخامسة في فهرس الحرّاس)."""
    roots = [os.environ.get("ANDROID_SDK_ROOT"), os.environ.get("ANDROID_HOME"), str(pathlib.Path.home() / "Android" / "Sdk")]
    for root in filter(None, roots):
        bt = pathlib.Path(root) / "build-tools"
        if bt.is_dir():
            for d in sorted(bt.iterdir(), reverse=True):
                if (d / name).exists():
                    return str(d / name)
    raise SystemExit(f"✗ لا {name} — أدواتُ البناء غيرُ موجودة، **فلا يُقاس التوقيع** (صرّح ANDROID_SDK_ROOT)")


def apk_cert(path: str) -> str:
    """شهادةُ الموقِّع الأوّل من داخل الـAPK (`apksigner`) — بصيغة `AA:BB:…` الكبيرة."""
    out = subprocess.run([sdk_tool("apksigner"), "verify", "--print-certs", path], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"✗ apksigner لم يتحقّق من {path}: {out.stderr.strip()[:200]}")
    m = re.search(r"Signer #1 certificate SHA-256 digest: ([0-9a-f]{64})", out.stdout)
    if not m:
        raise SystemExit(f"✗ لا شهادةَ مقروءةً في {path}")
    return ":".join(m.group(1)[i:i + 2] for i in range(0, 64, 2)).upper()


def apk_badging(path: str) -> dict:
    out = subprocess.run([sdk_tool("aapt2"), "dump", "badging", path], capture_output=True, text=True, check=True).stdout
    line = next((l for l in out.splitlines() if l.startswith("package:")), "")
    get = lambda k: (re.search(rf"{k}='([^']*)'", line) or [None, None])[1]
    return {"package": get("name"), "version_code": get("versionCode"), "version_name": get("versionName")}


def aab_cert(path: str) -> str:
    """توقيعُ حزمة AAB (توقيعُ JAR) — `keytool -printcert -jarfile`، والبصمةُ وحدَها تُقرأ."""
    out = subprocess.run(["keytool", "-printcert", "-jarfile", path], capture_output=True, text=True).stdout
    m = re.search(r"SHA256:\s*([0-9A-F:]{95})", out)
    if not m:
        raise SystemExit(f"✗ لا توقيعَ مقروءاً في {path} — **حزمةٌ غيرُ موقَّعةٍ لا تُرفع**")
    return m.group(1)


def _varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        c = b[i]
        i += 1
        r |= (c & 0x7F) << s
        s += 7
        if c < 0x80:
            return r, i


def _proto_fields(b: bytes) -> list:
    i, out = 0, []
    while i < len(b):
        key, i = _varint(b, i)
        f, w = key >> 3, key & 7
        if w == 0:
            v, i = _varint(b, i)
        elif w == 2:
            n, i = _varint(b, i)
            v = b[i:i + n]
            i += n
        elif w == 5:
            v, i = b[i:i + 4], i + 4
        elif w == 1:
            v, i = b[i:i + 8], i + 8
        else:
            raise ValueError(w)
        out.append((f, w, v))
    return out


def aab_badging(path: str) -> dict:
    """**المعرّفُ والرمزُ من بيان الحزمة نفسِها** — `aapt2` لا يقرأ AAB، وبيانُها بصيغة protobuf (`XmlNode`)، فيُقرأ هنا
    بلا مكتبة: كلُّ `XmlAttribute` اسمُه (الحقل ٢) وقيمتُه النصّيّة (الحقل ٣). **وقِيس على حزمتَي ٩١٨** فأعاد ما قاله Play."""
    hits: dict[str, str] = {}

    def walk(b: bytes, depth: int) -> None:
        try:
            fs = _proto_fields(b)
        except (ValueError, IndexError):
            return
        by: dict[int, list] = {}
        for f, _, v in fs:
            by.setdefault(f, []).append(v)
        name = by.get(2, [None])[0]
        if name in (b"package", b"versionCode", b"versionName") and by.get(3) and isinstance(by[3][0], bytes):
            hits.setdefault(name.decode(), by[3][0].decode(errors="replace"))
        if depth < 12:
            for _, w, v in fs:
                if w == 2 and len(v) > 1:
                    walk(v, depth + 1)

    walk(zipfile.ZipFile(path).read("base/manifest/AndroidManifest.xml"), 0)
    return {"package": hits.get("package"), "version_code": hits.get("versionCode"), "version_name": hits.get("versionName")}


# ═══ ما يقوله Play ═══

def play_state(token: str, pkg: str) -> dict:
    """أعلى رمزٍ في كلِّ مسار — **من تعديلٍ يُفتح ويُحذف بلا commit**."""
    edit = call(token, "POST", f"{pkg}/edits")
    if "_error" in edit:
        raise SystemExit(f"✗ {pkg}: فتحُ التعديل — {edit['_error']}")
    try:
        tracks = call(token, "GET", f"{pkg}/edits/{edit['id']}/tracks")
    finally:
        call(token, "DELETE", f"{pkg}/edits/{edit['id']}")
    if "_error" in tracks:
        raise SystemExit(f"✗ {pkg}: المسارات — {tracks['_error']}")
    per_track = {}
    for t in tracks.get("tracks", []):
        codes = [int(v) for r in t.get("releases", []) for v in r.get("versionCodes", [])]
        if codes:
            per_track[t["track"]] = max(codes)
    return {"tracks": per_track, "max": max(per_track.values(), default=0)}


def play_signing_cert(token: str, pkg: str, version_code: int) -> tuple[str | None, str | None]:
    """شهادةُ ما يولّده Play لهذا الرمز، ومعرّفُ تنزيل «الحزمة الشاملة» — `generatedapks.list`."""
    g = call(token, "GET", f"{pkg}/generatedApks/{version_code}")
    if "_error" in g:
        raise SystemExit(f"✗ {pkg} {version_code}: generatedApks — {g['_error']}")
    for per in g.get("generatedApks", []):
        cert = (per.get("certificateSha256Hash") or "").upper()
        if cert == PLAY_CERT[pkg]:
            return cert, (per.get("generatedUniversalApk") or {}).get("downloadId")
    seen = [(per.get("certificateSha256Hash") or "?")[:23] for per in g.get("generatedApks", [])]
    raise SystemExit(f"✗ {pkg} {version_code}: لا مجموعةَ حزمٍ بشهادة Play المسجَّلة — قال Play: {seen}. **مفاتيحُ تغيّرت؟ يوقف ويُسأل المالك**")


# ═══ الأوامر ═══

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


def signing() -> int:
    token = access_token()
    print(f"مفتاحُ الرفع (المسجَّل، للتطبيقين): {UPLOAD_CERT}")
    for pkg in APPS:
        state = play_state(token, pkg)
        cert, uni = play_signing_cert(token, pkg, state["max"])
        print(f"\n== {pkg}")
        print("  المسارات: " + " · ".join(f"{t} {v}" for t, v in sorted(state["tracks"].items())))
        print(f"  توقيعُ Play (من {state['max']}): {cert}  ✓ = المسجَّل")
        print(f"  الحزمةُ الشاملةُ متاحة: {'نعم' if uni else 'لا'}")
    return 0


def check_aab(token: str, aab: str, play: dict | None = None) -> tuple[bool, list[str], dict]:
    """**موقَّعةٌ بمفتاح الرفع، ورمزُها أعلى من كلِّ ما على Play** — والمعرّفُ أحدُ التطبيقين."""
    lines, ok = [], True
    badge = aab_badging(aab)
    pkg = badge["package"]
    if pkg not in APPS:
        return False, [f"  ✗ معرّفُ الحزمة {pkg} — ليس أحدَ تطبيقَي Play"], badge
    cert = aab_cert(aab)
    if cert == UPLOAD_CERT:
        lines.append(f"  ✓ موقَّعةٌ بمفتاح الرفع ({cert[:23]}…)")
    else:
        ok = False
        lines.append(f"  ✗ **ليست موقَّعةً بمفتاح الرفع**: {cert[:23]}… ≠ {UPLOAD_CERT[:23]}… — Play يرفضها، ولا تُرفع")
    play = play or play_state(token, pkg)
    vc = int(badge["version_code"] or 0)
    if vc > play["max"]:
        lines.append(f"  ✓ رمزُها {vc} أعلى من أعلى رمزٍ على Play ({play['max']})")
    else:
        ok = False
        lines.append(f"  ✗ **رمزُها {vc} لا يعلو أعلى رمزٍ على Play ({play['max']})** — لا يُرفع")
    return ok, lines, badge


def _site_req(name: str) -> urllib.request.Request:
    """**باسم وكيلٍ لا باسم بايثون**: الحافّةُ تردّ `Python-urllib` بـ403 (قِيس ٢٠٢٦-١٠-١٨) — ولا يُقرأ ذلك «الموقعُ سليم»."""
    return urllib.request.Request(f"{SITE}/downloads/{name}", headers={"User-Agent": "taxo-preflight/1 (+play_api.py)",
                                                                         "Cache-Control": "no-cache"})


def check_site(token: str, plays: dict) -> tuple[bool, list[str]]:
    """**حزمتا الموقع بتوقيع Play، ورمزُهما لا يعلو رمزَ Play** — تُنزَّلان من الصفحة نفسِها وتُقاسان من داخلهما."""
    lines, ok = [], True
    try:
        with urllib.request.urlopen(_site_req("manifest.json"), timeout=30) as r:
            manifest = json.load(r)
    except Exception as e:  # noqa: BLE001 — **لم يُقس ليس سليماً**
        return False, [f"  ✗ بيانُ الموقع لم يُقرأ ({str(e)[:60]}) — **لم يُقس، فلا يُقرأ سليماً**"]
    tmp = pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / f"site-apk-{os.getpid()}"
    tmp.mkdir(exist_ok=True)
    try:
        for pkg in APPS:
            key, label, name = SITE_FILE[pkg]
            path = tmp / name
            with urllib.request.urlopen(_site_req(name), timeout=300) as r:
                path.write_bytes(r.read())
            cert, badge = apk_cert(str(path)), apk_badging(str(path))
            vc = int(badge["version_code"] or 0)
            if cert == PLAY_CERT[pkg]:
                lines.append(f"  ✓ {name}: بتوقيع Play ({cert[:23]}…)")
            else:
                ok = False
                who = "مفتاح الرفع" if cert == UPLOAD_CERT else "مفتاحٍ مجهول"
                lines.append(f"  ✗ **{name}: بتوقيع {who}** ({cert[:23]}…) لا بتوقيع Play — من ثبّته لا يحدّثه Play")
            if vc <= plays[pkg]["max"]:
                lines.append(f"  ✓ {name}: رمزُه {vc} لا يعلو Play ({plays[pkg]['max']})")
            else:
                ok = False
                lines.append(f"  ✗ **{name}: رمزُه {vc} أعلى من Play ({plays[pkg]['max']})** — يحجب تحديثَ Play")
    finally:
        for f in tmp.glob("*"):
            f.unlink()
        tmp.rmdir()
    return ok, lines


def preflight(*aabs: str) -> int:
    token = access_token()
    plays = {pkg: play_state(token, pkg) for pkg in APPS}
    rc = 0
    for aab in aabs:
        ok, lines, badge = check_aab(token, aab, None)
        print(f"\n== {badge.get('package')} · {pathlib.Path(aab).name}")
        print("\n".join(lines))
        rc |= 0 if ok else 1
    ok, lines = check_site(token, plays)
    print(f"\n== حزمتا الموقع ({SITE}/download)")
    print("\n".join(lines))
    rc |= 0 if ok else 1
    print("\n" + ("✓ الفحصُ أخضر" if rc == 0 else "✗ الفحصُ سقط — أعلاه ما سقط"))
    return rc


def upload(pkg: str, aab: str, name: str, notes_file: str) -> int:
    """**alpha وحدَه** — `TRACK` ثابتٌ هنا لا وسيط: لا يُرفع إلى الإنتاج بخطأ في سطر أمر."""
    TRACK = "alpha"
    if pkg not in APPS:
        raise SystemExit(f"✗ حزمةٌ غيرُ معروفة: {pkg}")
    notes = json.loads(pathlib.Path(notes_file).read_text(encoding="utf-8"))
    token = access_token()
    # **الفحصُ يسبق الرفعَ ويوقفه** (§٧٩ البند ٣): التوقيعُ والرمز. **وحزمتا الموقع تُقالان ولا توقفان** — تُنشران من Play **بعد**
    # الرفع (`universal`)، فلحظةَ الرفع هما من الإصدار السابق بحقّ؛ ويُقاسان كاملين بـ`preflight`.
    ok, lines, badge = check_aab(token, aab)
    print("\n".join(lines))
    if badge.get("package") != pkg:
        print(f"  ✗ معرّفُ الحزمة {badge.get('package')} ≠ {pkg}")
        ok = False
    if not ok:
        print("✗ لا رفع — الفحصُ سقط")
        return 1
    edit = call(token, "POST", f"{pkg}/edits")
    if "_error" in edit:
        print("✗ فتحُ التعديل —", edit["_error"])
        return 1
    eid = edit["id"]
    committed = False
    try:
        data = pathlib.Path(aab).read_bytes()
        req = urllib.request.Request(
            f"https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/{pkg}/edits/{eid}/bundles?uploadType=media",
            method="POST", data=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                bundle = json.load(r)
        except urllib.error.HTTPError as e:
            print("✗ رفعُ الحزمة —", e.code, (e.read() or b"")[:400].decode(errors="replace"))
            return 1
        vc = str(bundle["versionCode"])
        print(f"✓ الحزمةُ رُفعت: versionCode {vc} · {len(data)} بايت")
        # **ملفُّ R8 في التعديل نفسِه** (قِيس ٢٠٢٦-١٠-٢٩): Play يرفضه بعد أن يُثبَّت الرمز («the Deobfuscation File can't be
        # modified») — فإن لم يُرفع هنا بقيت أسطرُ أعطال هذا الإصدار مخفيّةَ الأسماء إلى الأبد. ومكانُه بجانب الحزمة في مخرجات gradle
        mapping = pathlib.Path(aab).parents[2] / "mapping" / pathlib.Path(aab).parent.name / "mapping.txt"
        if mapping.is_file():
            req = urllib.request.Request(
                f"https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/{pkg}/edits/{eid}/apks/{vc}/deobfuscationFiles/proguard?uploadType=media",
                method="POST", data=mapping.read_bytes(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
            )
            try:
                with urllib.request.urlopen(req, timeout=300):
                    print(f"✓ ملفُّ R8 رُفع: {mapping.stat().st_size} بايت")
            except urllib.error.HTTPError as e:
                print("✗ ملفُّ R8 —", e.code, (e.read() or b"")[:400].decode(errors="replace"))
                return 1
        else:
            print("  · لا ملفَّ R8 بجانب الحزمة — أسطرُ الأعطال تبقى مخفيّةَ الأسماء")
        body = json.dumps({"track": TRACK, "releases": [{"name": name, "versionCodes": [vc], "status": "completed",
                                                          "releaseNotes": [{"language": k, "text": v} for k, v in notes.items()]}]}).encode()
        req = urllib.request.Request(f"{API}/{pkg}/edits/{eid}/tracks/{TRACK}", method="PUT", data=body,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                track = json.load(r)
        except urllib.error.HTTPError as e:
            print("✗ تحديثُ المسار —", e.code, (e.read() or b"")[:400].decode(errors="replace"))
            return 1
        print("✓ المسار:", [(rel.get("name"), rel.get("versionCodes"), rel.get("status")) for rel in track.get("releases", [])])
        done = call(token, "POST", f"{pkg}/edits/{eid}:commit")
        if "_error" in done:
            print("✗ commit —", done["_error"])
            return 1
        committed = True
        print(f"✓ commit — {pkg} {TRACK} {name} ({vc})")
        return 0
    finally:
        if not committed:
            call(token, "DELETE", f"{pkg}/edits/{eid}")
            print("  التعديلُ حُذف بلا commit")


def universal(version_code: str, outdir: str) -> int:
    """**حزمتا صفحة التحميل = ما يوقّعه Play** (§٧٩ البند ٢) — تُنزَّلان من Play وتُقاس كلٌّ: الشهادةُ = شهادةُ Play المسجَّلة،
    والمعرّفُ والرمزُ = المطلوب. **ثمّ يُكتب البيانُ بالشكل الذي تقرؤه الصفحةُ و`check-apk`** ومعه من وقّع."""
    vc = int(version_code)
    out = pathlib.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    token = access_token()
    entries = []
    for pkg in APPS:
        key, label, name = SITE_FILE[pkg]
        state = play_state(token, pkg)
        if vc not in state["tracks"].values() and vc > state["max"]:
            raise SystemExit(f"✗ {pkg}: الرمزُ {vc} ليس على Play (أعلاه {state['max']})")
        cert, download_id = play_signing_cert(token, pkg, vc)
        if not download_id:
            raise SystemExit(f"✗ {pkg} {vc}: لا «حزمةَ شاملة» يولّدها Play لهذا الرمز")
        req = urllib.request.Request(
            f"{API}/{pkg}/generatedApks/{vc}/downloads/{urllib.parse.quote(download_id, safe='')}:download?alt=media",
            headers={"Authorization": f"Bearer {token}"})
        part = out / f"{name}.part"
        with urllib.request.urlopen(req, timeout=600) as r, open(part, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        # **يُقاس ما نزل قبل أن يُسمّى** — الملفُّ لا يأخذ اسمَه حتى تطابق شهادتُه ومعرّفُه ورمزُه
        got_cert, badge = apk_cert(str(part)), apk_badging(str(part))
        if got_cert != PLAY_CERT[pkg] or badge["package"] != pkg or int(badge["version_code"] or 0) != vc:
            part.unlink()
            raise SystemExit(f"✗ {pkg}: ما نزل لا يطابق — شهادة {got_cert[:23]}… · {badge}")
        part.replace(out / name)
        data = (out / name).read_bytes()
        print(f"✓ {name}: {pkg} {vc} · بتوقيع Play {got_cert[:23]}… · {len(data)} بايت")
        entries.append({
            "key": key, "label": label, "file": name, "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "built_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "package": pkg, "version_name": badge["version_name"], "version_code": str(vc),
            "signed_by": "google-play", "signer_sha256": got_cert,
        })
    # **النسبُ إيداعٌ ووسم** كما في `tools/apk-manifest.mjs`: الإيداعُ الذي عددُ إيداعاته = الرمز (هكذا يُشتقّ الرمز)، والوسمُ من البيئة
    commit = None
    try:
        revs = subprocess.run(["git", "rev-list", "--reverse", "HEAD"], capture_output=True, text=True, check=True).stdout.split()
        commit = revs[vc - 1] if len(revs) >= vc else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    manifest = {"generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "commit": commit, "tag": os.environ.get("TAXO_RELEASE_TAG") or None, "dirty": False,
                "source": "google-play", "apps": entries}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ manifest.json — إيداع {str(commit)[:8]} · وسم {manifest['tag']}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["read"]:
        sys.exit(read())
    if args == ["signing"]:
        sys.exit(signing())
    if len(args) >= 1 and args[0] == "preflight":
        sys.exit(preflight(*args[1:]))
    if len(args) == 5 and args[0] == "upload":
        sys.exit(upload(*args[1:]))
    if len(args) == 3 and args[0] == "universal":
        sys.exit(universal(*args[1:]))
    raise SystemExit(__doc__)
