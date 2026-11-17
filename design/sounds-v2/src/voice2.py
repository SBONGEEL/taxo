"""المجموعةُ الثانية: صوتٌ أنثويٌّ إنجليزيٌّ **مصمَّمٌ من وصفٍ نصّيّ** (ElevenLabs Voice Design) — لا استنساخَ ولا تقليدَ لأحد.
المفتاحُ يُقرأ من ~/.taxo-secrets ولا يُطبع. الخطوة: previews | save <generated_id> <name> | say <voice_id> <tag>"""
import base64
import json
import sys
import urllib.request
from pathlib import Path

KEY = (Path.home() / ".taxo-secrets/elevenlabs/api-key.txt").read_text().strip()
API = "https://api.elevenlabs.io"
OUT = Path(__file__).parent / "voice"
OUT.mkdir(exist_ok=True)

DESIGNS = {
    "warm": "A warm, friendly, modern young adult woman with a clear neutral international English accent. Smooth, confident, smiling tone, studio quality, close microphone, no background noise.",
    "bright": "A bright, upbeat, energetic young woman with a clear neutral American English accent. Crisp, cheerful and modern, like a premium tech brand announcer, studio quality, no background noise.",
}
PREVIEW_TEXT = ("Taxo! Your ride is here. Taxo. Welcome aboard, it is a pleasure to have you with us today. "
                "Taxo! Your captain has arrived and is waiting for you at the door.")


def call(path, body=None, raw=False):
    req = urllib.request.Request(API + path, headers={"xi-api-key": KEY, "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    return data if raw else json.loads(data)


step = sys.argv[1]
if step == "previews":
    s = call("/v1/user/subscription")
    print("credits used", s.get("character_count"), "of", s.get("character_limit"))
    for name, desc in DESIGNS.items():
        out = call("/v1/text-to-voice/create-previews", {"voice_description": desc, "text": PREVIEW_TEXT})
        for i, p in enumerate(out.get("previews", [])):
            f = OUT / f"preview_{name}_{i}.mp3"
            f.write_bytes(base64.b64decode(p["audio_base_64"]))
            print("PREVIEW", f.name, p["generated_voice_id"])
elif step == "save":
    gid, name = sys.argv[2], sys.argv[3]
    out = call("/v1/text-to-voice/create-voice-from-preview",
               {"voice_name": f"TAXO {name}", "voice_description": DESIGNS[name.split('-')[0]], "generated_voice_id": gid})
    print("SAVED", out.get("voice_id"))
elif step == "say":
    vid, tag = sys.argv[2], sys.argv[3]
    takes = [("a", "Taxo!"), ("b", "[warmly] Taxo."), ("c", "[cheerfully] Taxo!"), ("d", "Tax-oh!")]
    for k, text in takes:
        audio = call(f"/v1/text-to-speech/{vid}?output_format=mp3_44100_128",
                     {"text": text, "model_id": "eleven_v3", "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}, raw=True)
        f = OUT / f"taxo_{tag}_{k}.mp3"
        f.write_bytes(audio)
        print("WROTE", f.name, len(audio))
