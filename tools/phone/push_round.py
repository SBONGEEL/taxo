#!/usr/bin/env python3
"""جولةُ الإشعارات على الهاتف — **قراءةٌ فقط** (SPEC §٦١-ل/٣ · `design/PUSH-PHONE-ROUND.md`).

**لا يضغط شيئاً على الهاتف، ولا يغيّر إعداداً، ولا يثبّت حزمة، ولا يمسح سجلّاً**: `dumpsys` و`appops get` و
`getprop` و`logcat -T 1` (من الآن، بلا مسح) قراءةٌ كلُّها. **والمخرجاتُ خارج المستودع** (`--out`): قد تحمل نصوصَ
إشعاراتٍ حقيقية. **والرموزُ تُحجب قبل أن تُكتب** — رمزُ الدخول في عنوان المقبس، ورموزُ FCM الطويلة.

    python push_round.py snapshot --out DIR --label قبل     # لقطة: الإصداراتُ والأذوناتُ والقنواتُ والمنشورُ والصوت
    python push_round.py watch    --out DIR [--minutes 45]  # مراقبةٌ حتى يوجد DIR/STOP أو تنقضي المدّة
    python push_round.py selftest                           # يقيس المحلِّلات على نصٍّ مصنوعٍ — بلا هاتف

**وما يُقرأ ولماذا**: القنواتُ ومعها صوتُها ومجراه (`usage=`) — **أهي على المنبّه أم الإشعار**؛ والمنشورُ كلَّ ثانيةٍ
بقناته — **أيُّ قناةٍ رسمته فعلاً**؛ وأحداثُ مشغّلات الصوت في `dumpsys audio` — **أيُّ صوتٍ بدأ، ومن أيِّ تطبيق، وعلى
أيِّ مجرى** (فنغمةُ الويب تُرى مشغّلاً من التطبيق على مجرى الوسائط، وصوتُ الإشعار من النظام)؛ والسجلُّ مصفّىً على
Firebase وCapacitor ورسائلِ الويب — **ففيه «القناةُ لم تُنشأ» من FCM، وسببُ غياب الرمز عند الراكب**.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ADB = os.environ.get("ADB") or str(
    Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
)
PACKAGES = ("ly.tajora.driver", "ly.tajora.rider")
#: **نسختا التجربة** (`.test`) — تُحمِّلان شاشاتهما من مكدّس التطوير عبر `dev-*` (`channels.json`)
TRIAL_PACKAGES = ("ly.tajora.driver.test", "ly.tajora.rider.test")

_REDACTIONS = (
    (re.compile(r"(token=)[^&\s\"']+"), r"\1<محجوب>"),
    (re.compile(r"eyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}"), "<jwt محجوب>"),
    (re.compile(r"[A-Za-z0-9_:\-]{100,}"), "<رمزٌ طويلٌ محجوب>"),
)


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def adb(*args: str, timeout: float = 40) -> str:
    result = subprocess.run([ADB, *args], capture_output=True, timeout=timeout)
    return result.stdout.decode("utf-8", "replace")


def device() -> str:
    """الجهازُ الموصول — **واحدٌ مأذونٌ لا غير**، وإلا يقف بنصِّ السبب."""
    if not Path(ADB).exists():
        sys.exit(f"✗ adb غيرُ موجود في {ADB}")
    rows = [line.split() for line in adb("devices").splitlines()[1:] if line.strip()]
    ready = [row[0] for row in rows if len(row) >= 2 and row[1] == "device"]
    if any(len(row) >= 2 and row[1] == "unauthorized" for row in rows):
        sys.exit("✗ الهاتفُ موصولٌ ولم يُؤذن بعد — اقبل «السماح بتصحيح USB» على شاشته")
    if len(ready) != 1:
        sys.exit(f"✗ المطلوبُ هاتفٌ واحدٌ موصول، والموجود {len(ready)}")
    return ready[0]


# ------------------------------------------------------------------ المحلِّلات


_APP = re.compile(r"^\s*AppSettings: (\S+) \((\d+)\)")
_FIELD = {
    "id": re.compile(r"mId='([^']*)'"),
    "name": re.compile(r"mName=(.*?), m(?:Description|Importance)="),
    "importance": re.compile(r"mImportance=(-?\d+)"),
    "sound": re.compile(r"mSound=([^,]*),"),
    "usage": re.compile(r"usage=(\w+)"),
    "deleted": re.compile(r"mDeleted=(\w+)"),
}


def _fields(line: str, fields: dict[str, re.Pattern[str]]) -> dict[str, str]:
    found = {}
    for name, pattern in fields.items():
        match = pattern.search(line)
        if match:
            found[name] = match.group(1).strip()
    return found


def channels(dump: str) -> dict[str, list[dict[str, str]]]:
    """قنواتُ كلِّ تطبيقٍ كما يحفظها النظام — بصوتها ومجراه."""
    result: dict[str, dict[str, dict[str, str]]] = {package: {} for package in PACKAGES}
    current: str | None = None
    for line in dump.splitlines():
        app = _APP.match(line)
        if app:
            current = app.group(1) if app.group(1) in PACKAGES else None
            continue
        if current and "NotificationChannel{" in line:
            fields = _fields(line, _FIELD)
            if "id" in fields:
                result[current][fields["id"]] = fields
    return {package: list(found.values()) for package, found in result.items()}


_RECORD = re.compile(r"NotificationRecord\(0x[0-9a-f]+: pkg=(\S+) .*?key=(\S+?): Notification\(channel=(\S+)")


def _extra(block: list[str], name: str) -> str:
    for line in block:
        stripped = line.strip()
        if stripped.startswith(f"{name}="):
            value = stripped.split("=", 1)[1]
            opening = value.find("(")
            return value[opening + 1 : value.rfind(")")] if opening >= 0 else value
    return ""


def posted(dump: str) -> list[dict[str, str]]:
    """ما هو منشورٌ الآن من التطبيقين — **بقناته التي رسمته**."""
    lines = dump.splitlines()
    found: dict[str, dict[str, str]] = {}
    for index, line in enumerate(lines):
        match = _RECORD.search(line)
        if not match or match.group(1) not in PACKAGES:
            continue
        block = lines[index + 1 : index + 160]
        end = next((j for j, row in enumerate(block) if "NotificationRecord(" in row), len(block))
        block = block[:end]
        flags = next((row.strip() for row in block if row.strip().startswith("flags=")), "")
        found[match.group(2)] = {
            "pkg": match.group(1),
            "key": match.group(2),
            "channel": match.group(3),
            "title": _extra(block, "android.title"),
            "text": _extra(block, "android.text"),
            "flags": flags,
        }
    return list(found.values())


_AUDIO = re.compile(r"^\s*(\d\d-\d\d \d\d:\d\d:\d\d[:.]\d+)\s+(.*piid:\s*\d+.*)$")


def audio_events(dump: str) -> list[str]:
    """أحداثُ مشغّلات الصوت — **من بدأ صوتاً، وبأيِّ مجرى** (`usage=`)."""
    keep = ("new player", "state:", "event:", "started", "usage=")
    return [
        f"{match.group(1)} {match.group(2).strip()}"
        for line in dump.splitlines()
        if (match := _AUDIO.match(line)) and any(word in line for word in keep)
    ]


def uids() -> dict[str, str]:
    found = {}
    for package in PACKAGES:
        match = re.search(r"userId=(\d+)", adb("shell", "dumpsys", "package", package))
        if match:
            found[package] = match.group(1)
    return found


# ------------------------------------------------------------------ اللقطة


def snapshot(out: Path, label: str) -> None:
    serial = device()
    folder = out / label
    folder.mkdir(parents=True, exist_ok=True)
    notification = adb("shell", "dumpsys", "notification", "--noredact")
    audio = adb("shell", "dumpsys", "audio")
    (folder / "notification.txt").write_text(redact(notification), encoding="utf-8")
    (folder / "audio.txt").write_text(redact(audio), encoding="utf-8")

    summary: dict[str, object] = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "serial_tail": serial[-4:],
        "model": adb("shell", "getprop", "ro.product.model").strip(),
        "android": adb("shell", "getprop", "ro.build.version.release").strip(),
        "zen_mode": adb("shell", "settings", "get", "global", "zen_mode").strip(),
        "ringer": sorted({row.strip() for row in audio.splitlines() if "ringer mode" in row.lower()})[:4],
        "uids": uids(),
        "apps": {},
        "channels": channels(notification),
        "posted": posted(notification),
    }
    for package in PACKAGES:
        info = adb("shell", "dumpsys", "package", package)
        (folder / f"package-{package}.txt").write_text(redact(info), encoding="utf-8")
        wanted = ("versionName=", "versionCode=", "lastUpdateTime=", "POST_NOTIFICATIONS",
                  "USE_FULL_SCREEN_INTENT", "ACCESS_FINE_LOCATION", "ACCESS_BACKGROUND_LOCATION")
        summary["apps"][package] = {  # type: ignore[index]
            "installed": "versionCode=" in info,
            "facts": sorted({row.strip() for row in info.splitlines() if any(w in row for w in wanted)})[:14],
            "overlay": adb("shell", "appops", "get", package, "SYSTEM_ALERT_WINDOW").strip(),
            "full_screen": adb("shell", "appops", "get", package, "USE_FULL_SCREEN_INTENT").strip(),
        }
    (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


# ------------------------------------------------------------------ المراقبة


_LOGCAT_KEEP = re.compile(r"FirebaseMessaging|FCM|Capacitor|chromium|PushNotification|ly\.tajora|taxo\.")


def watch(out: Path, minutes: float) -> None:
    device()
    folder = out / "watch"
    folder.mkdir(parents=True, exist_ok=True)
    stop_file = out / "STOP"
    events = (folder / "events.log").open("a", encoding="utf-8")
    logcat_file = (folder / "logcat.log").open("a", encoding="utf-8")
    app_uids = uids()

    def note(line: str) -> None:
        events.write(f"{datetime.now().strftime('%H:%M:%S')} {line}\n")
        events.flush()

    # **من الآن لا من أوّل السجلّ، وبلا مسح** — `-T 1` يبدأ من آخر سطر
    logcat = subprocess.Popen([ADB, "logcat", "-v", "time", "-T", "1"], stdout=subprocess.PIPE)

    def pump() -> None:
        assert logcat.stdout is not None
        for raw in logcat.stdout:
            line = raw.decode("utf-8", "replace").rstrip()
            if _LOGCAT_KEEP.search(line):
                logcat_file.write(redact(line) + "\n")
                logcat_file.flush()

    threading.Thread(target=pump, daemon=True).start()
    note(f"بدأت المراقبة — uids {app_uids}")

    seen: dict[str, dict[str, str]] = {}
    heard: set[str] = set(audio_events(adb("shell", "dumpsys", "audio")))
    deadline = time.monotonic() + minutes * 60
    tick = 0
    try:
        while time.monotonic() < deadline and not stop_file.exists():
            now = {row["key"]: row for row in posted(adb("shell", "dumpsys", "notification", "--noredact"))}
            for key, row in now.items():
                if key not in seen:
                    note(redact(f"+ {row['pkg']} [{row['channel']}] {row['title']} — {row['text']} {{{row['flags']}}}"))
            for key, row in seen.items():
                if key not in now:
                    note(redact(f"- {row['pkg']} [{row['channel']}] {row['title']}"))
            seen = now
            if tick % 3 == 0:
                for line in audio_events(adb("shell", "dumpsys", "audio")):
                    if line not in heard:
                        heard.add(line)
                        owner = next((p for p, uid in app_uids.items() if f"/{uid}/" in line or f":{uid}/" in line), "")
                        note(redact(f"♪ {owner or '—'} {line}"))
            tick += 1
            time.sleep(1)
    finally:
        logcat.terminate()
        note("انتهت المراقبة")
        events.close()
        logcat_file.close()


# ------------------------------------------------------------------ قياسُ المحلِّلات


_SAMPLE_NOTIFICATION = """\
  AppSettings: ly.tajora.driver (10234) importance=DEFAULT userSet=false
    NotificationChannel{mId='taxo.offer', mName=طلبات الرحلات, mDescription=بطاقة, mImportance=4, mBypassDnd=false, mSound=content://settings/system/alarm_alert, mLights=true, mAudioAttributes=AudioAttributes: usage=USAGE_ALARM content=CONTENT_TYPE_SONIFICATION flags=0x800 tags= bundle=null, mDeleted=false}
    NotificationChannel{mId='fcm_fallback_notification_channel', mName=Miscellaneous, mImportance=3, mSound=content://settings/system/notification_sound, mAudioAttributes=AudioAttributes: usage=USAGE_NOTIFICATION content=CONTENT_TYPE_SONIFICATION flags=0x800 tags= bundle=null, mDeleted=false}
  AppSettings: com.other.app (10111) importance=DEFAULT userSet=false
    NotificationChannel{mId='x', mName=X, mImportance=3, mSound=null, mAudioAttributes=AudioAttributes: usage=USAGE_NOTIFICATION, mDeleted=false}
  Notification List:
    NotificationRecord(0x0e3d3b7e: pkg=ly.tajora.driver user=UserHandle{0} id=4202 tag=null importance=4 key=0|ly.tajora.driver|4202|null|10234: Notification(channel=taxo.offer shortcut=null contentView=null vibrate=null sound=null defaults=0x0 flags=0x14 color=0x00000000 vis=PRIVATE))
      uid=10234 userId=0
      flags=0x14
      extras={
        android.title=String (طلب رحلة جديد)
        android.text=String (2.500 د.أ · 1.2 كم · 20 ث)
      }
    NotificationRecord(0x0aaaaaaa: pkg=com.other.app user=UserHandle{0} id=1 tag=null importance=3 key=0|com.other.app|1|null|10111: Notification(channel=x))
"""

_SAMPLE_AUDIO = """\
  10-05 14:00:01:123 new player piid:4071 uid/pid:10234/12345 type:android.media.MediaPlayer attr:AudioAttributes: usage=USAGE_ALARM content=CONTENT_TYPE_SONIFICATION flags=0x800
  10-05 14:00:01:130 player piid:4071 event:started
  10-05 14:00:02:000 unrelated line without piid
"""


def selftest() -> None:
    found = channels(_SAMPLE_NOTIFICATION)
    assert [c["id"] for c in found["ly.tajora.driver"]] == ["taxo.offer", "fcm_fallback_notification_channel"], found
    assert found["ly.tajora.driver"][0]["usage"] == "USAGE_ALARM"
    assert found["ly.tajora.driver"][0]["name"] == "طلبات الرحلات"
    assert found["ly.tajora.rider"] == []
    rows = posted(_SAMPLE_NOTIFICATION)
    assert len(rows) == 1 and rows[0]["channel"] == "taxo.offer" and rows[0]["title"] == "طلب رحلة جديد", rows
    assert rows[0]["text"] == "2.500 د.أ · 1.2 كم · 20 ث"
    events = audio_events(_SAMPLE_AUDIO)
    assert len(events) == 2 and "usage=USAGE_ALARM" in events[0], events
    assert redact("wss://x/ws/driver?token=abc.def&device_id=1") == "wss://x/ws/driver?token=<محجوب>&device_id=1"
    assert "<رمزٌ طويلٌ محجوب>" in redact("t " + "a" * 142)
    print("✓ المحلِّلاتُ تقرأ النصَّ المصنوع: قناتان · إشعارٌ واحدٌ بقناته وعنوانه · حدثا صوت · والحجبُ يعمل")


def main() -> None:
    parser = argparse.ArgumentParser(description="جولةُ الإشعارات — قراءةٌ فقط")
    sub = parser.add_subparsers(dest="command", required=True)
    shot = sub.add_parser("snapshot")
    shot.add_argument("--out", type=Path, required=True)
    shot.add_argument("--label", required=True)
    live = sub.add_parser("watch")
    live.add_argument("--out", type=Path, required=True)
    live.add_argument("--minutes", type=float, default=45)
    sub.add_parser("selftest")
    parser.add_argument(
        "--trial", action="store_true", help="نسختا التجربة (.test) بدل المنشورتين"
    )
    args = parser.parse_args()
    if args.trial and args.command != "selftest":
        # **المحلِّلاتُ تقرأ `PACKAGES` عند كلِّ نداء** — فاستبدالُه هنا يكفيها كلَّها.
        # والقياسُ الذاتيُّ على نصِّه المصنوع بالأسماء المنشورة، فلا يمسّه
        globals()["PACKAGES"] = TRIAL_PACKAGES
    if args.command == "snapshot":
        snapshot(args.out, args.label)
    elif args.command == "watch":
        watch(args.out, args.minutes)
    else:
        selftest()


if __name__ == "__main__":
    main()
