"""الكبتن: `python3 scripts/play_track.py internal <aab> <name> <notes.json> [--apply]` يرفع الحزمةَ إلى **المسار الداخليّ** للتجربة على Note 20،
و`python3 scripts/play_track.py production <versionCode> <name> <notes.json> [--apply]` **يرقّي الرمزَ نفسَه** إلى الإنتاج ١٠٠٪ بلا رفعٍ ثانٍ.
الفحصُ يسبق الرفعَ ويوقفه (كـpa_prod.py)، **والمسارُ المغلقُ لا يُمسّ**. بلا --apply: كلُّ شيءٍ ثمّ حذفُ التعديل بلا commit."""
import json, pathlib, sys, urllib.error, urllib.request, zipfile
sys.path.insert(0, "/home/loly3/prj/TAXO/scripts")
import play_api as pa

PKG = "ly.tajora.driver"
mode, target, name, notes_file = sys.argv[1:5]
apply = "--apply" in sys.argv
notes = json.loads(pathlib.Path(notes_file).read_text(encoding="utf-8"))
t = pa.access_token()


def put(path: str, body: dict) -> dict:
    req = urllib.request.Request(f"{pa.API}/{path}", method="PUT", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": f"{e.code}: {(e.read() or b'')[:300].decode(errors='replace')}"}


def check(aab: str) -> None:
    ok, lines, badge = pa.check_aab(t, aab)
    print("\n".join(lines))
    if badge.get("package") != PKG:
        print(f"  ✗ المعرّف {badge.get('package')} ≠ {PKG}"); ok = False
    z = zipfile.ZipFile(aab)
    if b"debuggable" in z.read("base/manifest/AndroidManifest.xml"):
        print("  ✗ debuggable في البيان"); ok = False
    res = z.read("base/resources.pb") if "base/resources.pb" in z.namelist() else b""
    if not (b"google_app_id" in res and b"gcm_defaultSenderId" in res):
        print("  ✗ Firebase غائب"); ok = False
    if b"taxo_offer_beep" not in res:
        print("  ✗ نغمةُ «بيب بيب» غائبةٌ من الموارد"); ok = False
    for n in z.namelist():
        if n.endswith("capacitor.config.json"):
            c = json.loads(z.read(n))
            url = (c.get("server") or {}).get("url")
            print(f"  · server.url={url!r} appId={c.get('appId')}")
            if c.get("appId") != PKG or (url and "tajora.ly" not in url):
                print("  ✗ إعدادُ Capacitor لا يطابق الإنتاج"); ok = False
    if not ok:
        raise SystemExit("✗ لا رفع — الفحصُ سقط")
    print(f"  ✓ الفحص · {badge.get('version_code')} · {pathlib.Path(aab).stat().st_size} بايت")


eid = pa.call(t, "POST", f"{PKG}/edits")["id"]
try:
    alpha_before = pa.call(t, "GET", f"{PKG}/edits/{eid}/tracks/alpha")
    if mode == "internal":
        check(target)
        req = urllib.request.Request(f"https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/{PKG}/edits/{eid}/bundles?uploadType=media",
                                     method="POST", data=pathlib.Path(target).read_bytes(),
                                     headers={"Authorization": f"Bearer {t}", "Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=900) as r:
            vc = str(json.load(r)["versionCode"])
        print(f"✓ الحزمةُ رُفعت: {vc}")
        mapping = pathlib.Path(target).parents[2] / "mapping" / pathlib.Path(target).parent.name / "mapping.txt"
        if mapping.is_file():
            req = urllib.request.Request(f"https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/{PKG}/edits/{eid}/apks/{vc}/deobfuscationFiles/proguard?uploadType=media",
                                         method="POST", data=mapping.read_bytes(), headers={"Authorization": f"Bearer {t}", "Content-Type": "application/octet-stream"})
            with urllib.request.urlopen(req, timeout=300):
                print(f"✓ ملفُّ R8 ({mapping.stat().st_size} بايت)")
        track = "internal"
    elif mode == "production":
        vc = str(int(target))
        track = "production"
    else:
        raise SystemExit("internal|production")
    body = {"track": track, "releases": [{"name": name, "versionCodes": [vc], "status": "completed",
                                          "releaseNotes": [{"language": k, "text": v} for k, v in notes.items()]}]}
    out = put(f"{PKG}/edits/{eid}/tracks/{track}", body)
    if "_error" in out:
        raise SystemExit(f"✗ {track}: {out['_error']}")
    print(f"✓ {track}:", [(x.get("name"), x.get("versionCodes"), x.get("status"), x.get("userFraction")) for x in out.get("releases", [])])
    alpha_after = pa.call(t, "GET", f"{PKG}/edits/{eid}/tracks/alpha")
    if alpha_before.get("releases") != alpha_after.get("releases"):
        raise SystemExit("✗ المسارُ المغلقُ تغيّر — لا commit")
    print("✓ المغلقُ كما هو")
    if apply:
        res = pa.call(t, "POST", f"{PKG}/edits/{eid}:commit")
        print("COMMIT", json.dumps(res, ensure_ascii=False)[:300])
        eid = None
finally:
    if eid:
        pa.call(t, "DELETE", f"{PKG}/edits/{eid}")
        print("· التعديلُ حُذف بلا commit")
