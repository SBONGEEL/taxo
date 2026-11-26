"""صورُ المتجر على Play عبر الـAPI — أمرُ المالك ٢٠٢٦-١١-٢٦ (design/OWNER-2026-11-26-STORE-IMAGES-NOW.md).

python3 store_images.py read            — قراءةٌ وحدَها: لغاتُ البطاقات وعددُ صور الهاتف والصورة المميّزة في كلٍّ (تعديلٌ يُفتح ثمّ يُحذف)
python3 store_images.py apply [--commit] — يستبدل صورَ الهاتف والمميّزةَ للعربيّة (ar) والفرنسيّة (fr-FR) من مجلّد سطح المكتب؛
                                          بلا --commit يُبنى التعديلُ ويُقرأ ثمّ يُحذف (تجربةٌ جافّة)
لا يُطبع الرمز. يُشغَّل من جذر المستودع (يستورد scripts/play_api.py).
"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "scripts")
import play_api as pa  # noqa: E402

SRC = pathlib.Path("/mnt/c/Users/loly3/OneDrive/Desktop/TAXO-store-images")
APPS = {"ly.tajora.driver": "driver", "ly.tajora.rider": "rider"}
LANGS = {"ar": "ar", "fr-FR": "fr", "en-US": "ar"}  # التطبيقان بالعربيّة والفرنسيّة وحدَهما — فبطاقةُ الإنجليزيّة تُرى بالعربيّة
UP = "https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications"


def files_for(app: str, short: str):
    d = SRC / app
    shots = sorted(d.glob(f"{app}-{short}-0[1-8].png"))
    fg = d / f"{app}-{short}-feature-1024x500.jpg"
    return shots, fg


def upload(token, pkg, eid, lang, kind, path):
    ctype = "image/png" if path.suffix == ".png" else "image/jpeg"
    req = urllib.request.Request(f"{UP}/{pkg}/edits/{eid}/listings/{lang}/{kind}?uploadType=media", method="POST",
                                 data=path.read_bytes(), headers={"Authorization": f"Bearer {token}", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r).get("image", {}).get("id", "?")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"✗ رفع {pkg} {lang} {kind} {path.name} — {e.code} {(e.read() or b'')[:300].decode(errors='replace')}")


def state(token, pkg, eid):
    out = {}
    for lst in pa.call(token, "GET", f"{pkg}/edits/{eid}/listings").get("listings", []):
        lang = lst["language"]
        out[lang] = {k: len(pa.call(token, "GET", f"{pkg}/edits/{eid}/listings/{lang}/{k}").get("images", []))
                     for k in ("phoneScreenshots", "featureGraphic", "sevenInchScreenshots", "tenInchScreenshots")}
    return out


def main():
    mode = sys.argv[1]
    commit = "--commit" in sys.argv
    token = pa.access_token()
    for pkg, app in APPS.items():
        edit = pa.call(token, "POST", f"{pkg}/edits")
        if "_error" in edit:
            raise SystemExit(f"✗ فتحُ التعديل {pkg} — {edit['_error']}")
        eid, committed = edit["id"], False
        try:
            print(pkg, "قبل:", json.dumps(state(token, pkg, eid), ensure_ascii=False))
            if mode != "apply":
                continue
            for lang, short in LANGS.items():
                shots, fg = files_for(app, short)
                if len(shots) != 8 or not fg.is_file():
                    raise SystemExit(f"✗ ملفّاتٌ ناقصة {app} {short}: {len(shots)} صورة، المميّزة {fg.is_file()}")
                for kind in ("phoneScreenshots", "featureGraphic"):
                    r = pa.call(token, "DELETE", f"{pkg}/edits/{eid}/listings/{lang}/{kind}")
                    if "_error" in r:
                        raise SystemExit(f"✗ حذفُ القديمة {pkg} {lang} {kind} — {r['_error']}")
                for p in shots:
                    upload(token, pkg, eid, lang, "phoneScreenshots", p)
                upload(token, pkg, eid, lang, "featureGraphic", fg)
                print(f"  ✓ {lang}: {len(shots)} صور هاتف + المميّزة")
            print(pkg, "بعد:", json.dumps(state(token, pkg, eid), ensure_ascii=False))
            if commit:
                done = pa.call(token, "POST", f"{pkg}/edits/{eid}:commit")
                if "_error" in done:
                    raise SystemExit(f"✗ commit {pkg} — {done['_error']}")
                committed = True
                print(f"✓ commit — {pkg}")
        finally:
            if not committed:
                pa.call(token, "DELETE", f"{pkg}/edits/{eid}")
                print("  التعديلُ حُذف بلا commit")


main()
