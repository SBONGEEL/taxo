"""رمزا حسابَي الاختبار (الكابتن والراكب) لصور المتجر — يُحفظان في ملفّين 600 ولا يُطبعان؛ وقراءاتُ GET بهما.

python3 tok.py refresh            — يتحقّق من الرمزين ويجدّد الساقط بدخول الحساب الاختباريّ
python3 tok.py get rider /path …  — GET بحساب الراكب (أو captain)
"""
import json
import pathlib
import sys
import urllib.request

BASE = "https://api.tajora.ly/api/v1"
S = pathlib.Path("/mnt/c/Users/loly3/AppData/Local/Temp/claude/2cccde71cb918853/1be46dcf-43b9-4d7a-8ee2-56b32aaa8a2d/scratchpad")
env = dict(l.split("=", 1) for l in pathlib.Path("/mnt/c/Users/loly3/.taxo-secrets/test-accounts.env").read_text().splitlines() if "=" in l and not l.startswith("#"))
WHO = {"captain": ("CAPTAIN", "driver", S / ".cap_token", "/drivers/me"), "rider": ("RIDER", "rider", S / ".rider_token", "/auth/me")}


def call(method, path, body=None, token=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": "taxo-check", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def token(who):
    key, app, cache, probe = WHO[who]
    t = cache.read_text().strip() if cache.exists() else None
    if t and call("GET", probe, token=t)[0] == 200:
        return t
    st, out = call("POST", "/auth/login", {"phone": env[f"TAXO_TEST_{key}_PHONE"], "password": env[f"TAXO_TEST_{key}_PASSWORD"], "app": app})
    if st != 200:
        sys.exit(f"{who} login {st}")
    t = out["tokens"]["access_token"]
    cache.write_text(t)
    cache.chmod(0o600)
    return t


if sys.argv[1] == "refresh":
    for w in WHO:
        if "force" in sys.argv:
            WHO[w][2].unlink(missing_ok=True)
        token(w)
        print(w, "ok")
elif sys.argv[1] == "get":
    t = token(sys.argv[2])
    for path in sys.argv[3:]:
        st, out = call("GET", path, token=t)
        print(path, st)
        print(json.dumps(out, ensure_ascii=False)[:1800])
elif sys.argv[1] == "dump":
    st, out = call("GET", sys.argv[3], token=token(sys.argv[2]))
    pathlib.Path(sys.argv[4]).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(sys.argv[3], st)
