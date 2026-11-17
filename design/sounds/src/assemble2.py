"""النمط ٢: «بيب بيب» + «تاكسو» بصوت — يُجمَع من بيبات المُركِّب وصوتٍ مقصوص."""
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from synth import SR, G6, C7, beep, bell, finish, place, write  # noqa: E402

RAW = Path(__file__).parent / "raw"


def read(name: str) -> np.ndarray:
    with wave.open(str(RAW / f"{name}.wav")) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32768


voice = read("taxo_voice_bandar")
voice = voice / (np.max(np.abs(voice)) or 1)

drv = np.zeros(int(2.8 * SR))
place(drv, read("opt2_beeps_driver"), 0.0, 0.9)
place(drv, voice, 1.0, 1.0)
write("opt2_driver_cycle", finish(drv))

rid = np.zeros(int(1.35 * SR))
place(rid, read("opt2_beeps_rider"), 0.0, 0.85)
place(rid, voice, 0.42, 1.0)
write("opt2_rider", finish(rid))

upd = np.zeros(int(0.7 * SR))
place(upd, beep(G6, 0.08, bright=0.1), 0.0, 0.5)
place(upd, bell(C7, 0.5, decay=0.15, index=0.5), 0.12, 0.5)
write("opt2_update", finish(upd, -6.0))
