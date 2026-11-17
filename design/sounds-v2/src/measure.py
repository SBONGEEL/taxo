"""قياسُ الأصوات بلا أذن: النبرةُ الوسطى (F0) وتذبذبُها، والارتفاعُ، والقصّ."""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

D = Path(__file__).parent


def load(mp3: Path) -> np.ndarray:
    wav = mp3.with_suffix('.m.wav')
    lin = '/mnt/c/' + str(wav).replace('\\', '/')[3:]
    src = '/mnt/c/' + str(mp3).replace('\\', '/')[3:]
    subprocess.run(['wsl.exe', '-d', 'Ubuntu-24.04', '--', 'ffmpeg', '-v', 'error', '-y', '-i', src, '-ac', '1', '-ar', '16000', lin],
                   check=True, stdin=subprocess.DEVNULL)
    with wave.open(str(wav)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    wav.unlink()
    return x


def f0(x, sr=16000):
    out = []
    n = 640
    for i in range(0, len(x) - n, 320):
        f = x[i:i + n]
        if np.sqrt(np.mean(f ** 2)) < 0.03:
            continue
        f = f - f.mean()
        ac = np.correlate(f, f, 'full')[n - 1:]
        lo, hi = sr // 400, sr // 80
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.4 * ac[0]:
            out.append(sr / k)
    return np.array(out)


for p in sorted(D.glob(sys.argv[1] if len(sys.argv) > 1 else 'voice/*.mp3')):
    x = load(p)
    p0 = f0(x)
    rms = 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
    print(f"{p.name:28s} dur={len(x)/16000:5.2f}s F0med={np.median(p0) if len(p0) else 0:6.1f}Hz F0iqr={np.subtract(*np.percentile(p0,[75,25])) if len(p0) else 0:5.1f} rms={rms:6.1f}dB peak={np.max(np.abs(x)):.2f}")
