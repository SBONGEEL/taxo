"""قناعُ الطلاء لكلِّ سيارة TAXO (SPEC §١١١/٤) — `python tools/gen-car-paint-masks.py driver-app/public/cars <مجلّدُ الخرج>`
ثمّ يُنسخ منه ما لسيارات الهيكل الأبيض وحدَها (لا `vip` ولا `women`) إلى `driver-app/public/cars/`."""
# — حيث الهيكلُ الأبيضُ وحدَه (لا الزجاجُ ولا العجلاتُ ولا اللمسةُ البرتقاليّة)
import sys, pathlib, numpy as np
from PIL import Image
src = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
def ss(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
for f in sorted(src.glob("*-34-*-640.webp")):
    im = np.asarray(Image.open(f).convert("RGBA")).astype(np.float32) / 255
    rgb, a = im[..., :3], im[..., 3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    night = "-night-" in f.name
    v_lo, v_hi = (0.22, 0.42) if night else (0.42, 0.62)
    m = a * (1 - ss(s, 0.10, 0.22)) * ss(mx, v_lo, v_hi)
    # **القناعُ في قناة الشفافيّة** — `mask-image` يقرأ الألفا لا السطوع، والأبيضُ تحتها لا يُرى
    alpha = Image.fromarray((m * 255).astype(np.uint8), "L").resize((320, 200), Image.LANCZOS)
    img = Image.new("RGBA", alpha.size, (255, 255, 255, 0)); img.putalpha(alpha)
    name = f.name.replace("-34-", "-paint-").replace("-640.webp", ".webp")
    img.save(out / name, "WEBP", quality=80, alpha_quality=70)
print("masks", len(list(out.glob("*.webp"))))
