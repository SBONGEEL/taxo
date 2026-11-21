# مولِّدُ ودجات TAXO — الجيلُ الثاني (أمرُ المالك ٢٠٢٦-١١-٢١: «التصميمُ بعيدٌ عن صورتي المرجعيّة»).
#
# **مواصفةٌ واحدةٌ تُخرج شيئين**: موارد أندرويد (الألوان، الخلفيّات الزجاجيّة، رسومُ النمط C متّجهةً، تخطيطٌ لكلِّ نوعٍ ولكلِّ حجم،
# وملفّاتُ المزوّدات بمعاينةٍ حيّة `previewLayout`) — **ومعاينةً HTML بالبنية نفسِها** تُصوَّر قبل البناء.
# فما يُرى في المعاينة هو ما يُبنى، **والمعاينةُ في المنتقي هي التخطيطُ نفسُه** لا صورةُ سيارةٍ واحدةٍ للجميع.
#
# التشغيل:  python3 tools/gen-android-widgets.py <app-dir> rider|driver <assets-dir> [<preview-out-dir>]
#   <assets-dir> = design/widgets-hq (السيارات، الرسوم، المشهد، العلامة) — يُحفظ في المستودع ليُعاد التوليدُ بلا شيءٍ خارجه.
#
# **قيودُ RemoteViews محترمة**: FrameLayout/LinearLayout/TextView/ImageView/ProgressBar وحدها، والزجاجُ تدرّجاتٌ وطبقاتٌ **بلا blur**
# (البطاريّة)، ولا رقمَ في نصٍّ افتراضيّ (النصُّ الافتراضيُّ هو ما يراه المنتقي: عناوينُ وأفعالٌ لا بياناتٌ مخترعة).
import html, json, pathlib, re, shutil, sys

APP = pathlib.Path(sys.argv[1])
ROLE_APP = sys.argv[2]  # rider | driver
ASSETS = pathlib.Path(sys.argv[3])
PREVIEW = pathlib.Path(sys.argv[4]) if len(sys.argv) > 4 else None
RES = APP / "android/app/src/main/res"
PKG = "ly.tajora.rider" if ROLE_APP == "rider" else "ly.tajora.driver"
GLYPHS_TS = APP / "src/taxo2/glyphsC.ts"
H = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
A = 'xmlns:android="http://schemas.android.com/apk/res/android"'
GEN = "مولَّدٌ من tools/gen-android-widgets.py — لا يُحرَّر باليد."


def write(rel, text):
    p = RES / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


# ═══════════════════════════ الألوان: نهارٌ نظيف وليلٌ داكنٌ بلمسةٍ برتقاليّة ═══════════════════════════
DAY = dict(
    tw_bg0="#FFFFFFFF", tw_bg1="#FFF4EFEB", tw_glow="#38FF8A5C", tw_line="#12101828", tw_hi="#B3FFFFFF",
    tw_tx="#FF15171C", tw_mut="#FF5F6570", tw_acc="#FFF05A28", tw_acc2="#FFFF8A5C", tw_acc_tx="#FFC2451A",
    tw_glass="#FFF8F3F0", tw_gline="#14101828", tw_glass2="#FFFFFFFF", tw_chipbg="#F2FFFFFF", tw_track="#1A101828",
    tw_g_b="#FFF05A28", tw_g_k="#FFFFC4AA", tw_g_d="#FFB8401A", tw_g_c="#FFFFFFFF", tw_g_g="#1F1F2433",
    tw_on="#FFFFFFFF", tw_ok="#FF1FBF75", tw_star="#FFFFB020", tw_icon="#FF15171C", tw_fade="#FFFAF6F3", tw_fade0="#00FAF6F3",
)
NIGHT = dict(
    tw_bg0="#FF2A2C35", tw_bg1="#FF111217", tw_glow="#59FF6A33", tw_line="#1CFFFFFF", tw_hi="#12FFFFFF",
    tw_tx="#FFF6F7F9", tw_mut="#FFA9AFB9", tw_acc="#FFFF6A33", tw_acc2="#FFFF9466", tw_acc_tx="#FFFF8A5C",
    tw_glass="#14FFFFFF", tw_gline="#1FFFFFFF", tw_glass2="#1FFFFFFF", tw_chipbg="#D9101116", tw_track="#24FFFFFF",
    tw_g_b="#FFFF6A33", tw_g_k="#FF7A2A10", tw_g_d="#FFFFB08A", tw_g_c="#FF1B1E24", tw_g_g="#73000000",
    tw_on="#FFFFFFFF", tw_ok="#FF3DBE7E", tw_star="#FFFFB020", tw_icon="#FFF6F7F9", tw_fade="#FF1D1E24", tw_fade0="#001D1E24",
)
HOT = dict(h_tx="#FFFFFFFF", h_mut="#E6FFFFFF", h_glass="#29FFFFFF", h_line="#40FFFFFF")
for folder, table in (("values", DAY), ("values-night", NIGHT)):
    rows = "\n".join(f'    <color name="{k}">{v}</color>' for k, v in {**table, **HOT}.items())
    write(f"{folder}/tw_colors.xml", H + f"<!-- **ودجاتُ TAXO** — نهارٌ نظيفٌ وليلٌ داكنٌ بلمسةٍ برتقاليّة. {GEN} -->\n<resources>\n" + rows + "\n</resources>\n")

R = 28  # نصفُ قطر البطاقة


def shape(inner, kind="rectangle"):
    return f'<shape android:shape="{kind}">{inner}</shape>'


DRAW = {
    # البطاقة: تدرّجٌ قطريٌّ + توهّجٌ برتقاليٌّ في الزاوية + لمعةٌ علويّة + حدٌّ رفيع — زجاجٌ مقلَّدٌ بالطبقات
    "tw_card": f'''<layer-list {A}>
    <item>{shape(f'<gradient android:angle="300" android:startColor="@color/tw_bg0" android:endColor="@color/tw_bg1" /><corners android:radius="{R}dp" />')}</item>
    <item>{shape(f'<gradient android:type="radial" android:gradientRadius="240dp" android:centerX="0.0" android:centerY="1.0" android:startColor="@color/tw_glow" android:endColor="#00000000" /><corners android:radius="{R}dp" />')}</item>
    <item android:gravity="top" android:height="56dp">{shape(f'<gradient android:angle="270" android:startColor="@color/tw_hi" android:endColor="#00FFFFFF" /><corners android:topLeftRadius="{R}dp" android:topRightRadius="{R}dp" />')}</item>
    <item>{shape(f'<stroke android:width="1dp" android:color="@color/tw_line" /><corners android:radius="{R}dp" />')}</item>
</layer-list>''',
    # البطاقةُ الساخنة (الخصم): برتقاليٌّ في النهار والليل
    "tw_card_hot": f'''<layer-list {A}>
    <item>{shape(f'<gradient android:angle="315" android:startColor="#FFFF9A5E" android:centerColor="#FFF05A28" android:endColor="#FFB93A14" /><corners android:radius="{R}dp" />')}</item>
    <item>{shape(f'<gradient android:type="radial" android:gradientRadius="200dp" android:centerX="1.0" android:centerY="0.0" android:startColor="#40FFFFFF" android:endColor="#00FFFFFF" /><corners android:radius="{R}dp" />')}</item>
    <item>{shape(f'<stroke android:width="1dp" android:color="#33FFFFFF" /><corners android:radius="{R}dp" />')}</item>
</layer-list>''',
    "tw_fade": f'''<layer-list {A}>
    <item>{shape('<gradient android:angle="180" android:startColor="@color/tw_fade" android:centerColor="@color/tw_fade0" android:centerX="0.45" android:endColor="@color/tw_fade0" />')}</item>
    <item>{shape('<gradient android:angle="270" android:startColor="@color/tw_fade" android:centerColor="@color/tw_fade0" android:centerY="0.4" android:endColor="@color/tw_fade0" />')}</item>
    <item>{shape('<gradient android:angle="0" android:startColor="@color/tw_fade" android:centerColor="@color/tw_fade0" android:centerX="0.18" android:endColor="@color/tw_fade0" />')}</item>
</layer-list>''',
    "tw_glass": f'<shape {A} android:shape="rectangle"><solid android:color="@color/tw_glass" /><stroke android:width="1dp" android:color="@color/tw_gline" /><corners android:radius="18dp" /></shape>',
    "tw_glass_hot": f'<shape {A} android:shape="rectangle"><solid android:color="@color/h_glass" /><stroke android:width="1dp" android:color="@color/h_line" /><corners android:radius="18dp" /></shape>',
    "tw_tile": f'<shape {A} android:shape="rectangle"><solid android:color="@color/tw_glass" /><stroke android:width="1dp" android:color="@color/tw_gline" /><corners android:radius="20dp" /></shape>',
    "tw_pill": f'''<layer-list {A}>
    <item>{shape('<gradient android:angle="0" android:startColor="@color/tw_acc" android:endColor="@color/tw_acc2" /><corners android:radius="99dp" />')}</item>
    <item android:gravity="top" android:height="18dp">{shape('<gradient android:angle="270" android:startColor="#33FFFFFF" android:endColor="#00FFFFFF" /><corners android:topLeftRadius="99dp" android:topRightRadius="99dp" />')}</item>
</layer-list>''',
    "tw_pill_light": f'<shape {A} android:shape="rectangle"><solid android:color="#FFFFFFFF" /><corners android:radius="99dp" /></shape>',
    "tw_pill_glass": f'<shape {A} android:shape="rectangle"><solid android:color="@color/tw_glass2" /><stroke android:width="1dp" android:color="@color/tw_gline" /><corners android:radius="99dp" /></shape>',
    "tw_chip": f'<shape {A} android:shape="rectangle"><solid android:color="@color/tw_chipbg" /><stroke android:width="1dp" android:color="@color/tw_gline" /><corners android:radius="99dp" /></shape>',
    "tw_circle": f'''<layer-list {A}>
    <item>{shape('<solid android:color="#2EF05A28" />', "oval")}</item>
    <item android:top="5dp" android:bottom="5dp" android:left="5dp" android:right="5dp">{shape('<gradient android:angle="300" android:startColor="@color/tw_acc2" android:endColor="@color/tw_acc" />', "oval")}</item>
</layer-list>''',
    "tw_circle_glass": f'<shape {A} android:shape="oval"><solid android:color="@color/tw_glass" /><stroke android:width="1dp" android:color="@color/tw_gline" /></shape>',
    "tw_circle_light": f'<shape {A} android:shape="oval"><solid android:color="#FFFFFFFF" /></shape>',
    "tw_photo_ring": f'<shape {A} android:shape="oval"><stroke android:width="2dp" android:color="@color/tw_acc" /></shape>',
    "tw_dot": f'<shape {A} android:shape="oval"><solid android:color="@color/tw_acc" /><size android:width="8dp" android:height="8dp" /></shape>',
    "tw_dot_ok": f'<shape {A} android:shape="oval"><solid android:color="@color/tw_ok" /><size android:width="8dp" android:height="8dp" /></shape>',
    "tw_dot_off": f'<shape {A} android:shape="oval"><solid android:color="@color/tw_mut" /><size android:width="8dp" android:height="8dp" /></shape>',
    "tw_bar": f'''<layer-list {A}>
    <item android:id="@android:id/background">{shape('<solid android:color="@color/tw_track" /><corners android:radius="4dp" />')}</item>
    <item android:id="@android:id/progress"><clip>{shape('<gradient android:angle="0" android:startColor="@color/tw_acc" android:endColor="@color/tw_acc2" /><corners android:radius="4dp" />')}</clip></item>
</layer-list>''',
    "tw_ring": f'''<layer-list {A}>
    <item android:id="@android:id/background"><shape android:shape="ring" android:innerRadiusRatio="2.5" android:thicknessRatio="11" android:useLevel="false"><solid android:color="@color/tw_track" /></shape></item>
    <item android:id="@android:id/progress"><rotate android:fromDegrees="270" android:toDegrees="270" android:pivotX="50%" android:pivotY="50%"><shape android:shape="ring" android:innerRadiusRatio="2.5" android:thicknessRatio="11" android:useLevel="true"><gradient android:type="sweep" android:startColor="@color/tw_acc2" android:endColor="@color/tw_acc" /></shape></rotate></item>
</layer-list>''',
}
for name, body in DRAW.items():
    write(f"drawable/{name}.xml", H + f"<!-- {GEN} -->\n" + body + "\n")

# ═══════════════════════════ الرسومُ المتّجهة ═══════════════════════════
src = GLYPHS_TS.read_text(encoding="utf-8")
glyphs = {m.group(1): json.loads('"' + m.group(2) + '"') for m in re.finditer(r'^  ([a-z_]+): "((?:[^"\\]|\\.)*)",?$', src, re.M)}
glyphs["work"] = '<path class="g" d="M8 41.2a16 1.8 0 1 0 32 0a16 1.8 0 1 0 -32 0z"/><path class="k" transform="translate(2 2)" d="M12 14h24a5 5 0 0 1 5 5v15a5 5 0 0 1-5 5H12a5 5 0 0 1-5-5V19a5 5 0 0 1 5-5z"/><path class="d" d="M18 15v-4a3 3 0 0 1 3-3h6a3 3 0 0 1 3 3v4h-3v-3.5h-6V15z"/><path class="b" d="M12 14h24a5 5 0 0 1 5 5v15a5 5 0 0 1-5 5H12a5 5 0 0 1-5-5V19a5 5 0 0 1 5-5z"/><path class="c" d="M7 24.5h34v2.6H7z"/><path class="d" d="M21.5 22h5a1.5 1.5 0 0 1 1.5 1.5v4a1.5 1.5 0 0 1-1.5 1.5h-5a1.5 1.5 0 0 1-1.5-1.5v-4a1.5 1.5 0 0 1 1.5-1.5z"/>'
glyphs["flight"] = '<path class="k" transform="translate(2 2)" d="M24 4c1.7 0 3 1.6 3 3.6V19l14 8v4l-14-4.2V36l4 3v3l-7-2-7 2v-3l4-3v-9.2L7 31v-4l14-8V7.6C21 5.6 22.3 4 24 4z"/><path class="b" d="M24 4c1.7 0 3 1.6 3 3.6V19l14 8v4l-14-4.2V36l4 3v3l-7-2-7 2v-3l4-3v-9.2L7 31v-4l14-8V7.6C21 5.6 22.3 4 24 4z"/><path class="c" d="M22.6 9.5h2.8v4h-2.8z"/>'
ROLE = {"b": "@color/tw_g_b", "k": "@color/tw_g_k", "d": "@color/tw_g_d", "c": "@color/tw_g_c", "g": "@color/tw_g_g"}
ON = {"b": "#FFFFFFFF", "k": "#FFFFD2BD", "d": "#FFB8401A", "c": "#FFF05A28", "g": "#00000000"}
WANT = ["home", "work", "flight", "account_balance_wallet", "redeem", "schedule", "sell", "history", "star", "location_on",
        "check_circle", "local_taxi", "person", "search", "tune", "woman", "directions_car", "airport_shuttle", "payments",
        "my_location", "flag", "receipt_long"]


def vector(svg, colors, name):
    parts = []
    for m in re.finditer(r'<path class="([a-z])"( transform="translate\(([-\d.]+) ([-\d.]+)\)")? d="([^"]+)"/>', svg):
        role, tr, tx, ty, d = m.groups()
        p = f'<path android:fillColor="{colors[role]}" android:pathData="{d}" />'
        parts.append(f'<group android:translateX="{tx}" android:translateY="{ty}">{p}</group>' if tr else p)
    assert parts, name
    return H + f'<vector {A} android:width="48dp" android:height="48dp" android:viewportWidth="48" android:viewportHeight="48">\n    ' + "\n    ".join(parts) + "\n</vector>\n"


for name in WANT:
    write(f"drawable/tw_g_{name}.xml", vector(glyphs[name], ROLE, name))
write("drawable/tw_g_local_taxi_on.xml", vector(glyphs["local_taxi"], ON, "local_taxi_on"))

# رموزٌ خطّيّةٌ صغيرة (Material، ٢٤) — السهمُ يشير يساراً: «إلى الأمام» في واجهةٍ عربيّة
MAT = {
    "arrow": "M20,11H7.83l5.59,-5.59L12,4l-8,8 8,8 1.41,-1.41L7.83,13H20v-2z",
    "clock": "M11.99,2C6.47,2 2,6.48 2,12s4.47,10 9.99,10C17.52,22 22,17.52 22,12S17.52,2 11.99,2zM12,20c-4.42,0 -8,-3.58 -8,-8s3.58,-8 8,-8 8,3.58 8,8 -3.58,8 -8,8zM12.5,7H11v6l5.25,3.15 0.75,-1.23 -4.5,-2.67z",
    "plus": "M19,13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
    "chev": "M15.41,7.41L14,6l-6,6 6,6 1.41,-1.41L10.83,12z",
    "star": "M12,17.27L18.18,21l-1.64,-7.03L22,9.24l-7.19,-0.61L12,2 9.19,8.63 2,9.24l5.46,4.73L5.82,21z",
    "bolt": "M7,2v11h3v9l7,-12h-4l4,-8z",
    "person": "M12,12c2.21,0 4,-1.79 4,-4s-1.79,-4 -4,-4 -4,1.79 -4,4 1.79,4 4,4zM12,14c-2.67,0 -8,1.34 -8,4v2h16v-2c0,-2.66 -5.33,-4 -8,-4z",
    "car": "M18.92,6.01C18.72,5.42 18.16,5 17.5,5h-11c-0.66,0 -1.21,0.42 -1.42,1.01L3,12v8c0,0.55 0.45,1 1,1h1c0.55,0 1,-0.45 1,-1v-1h12v1c0,0.55 0.45,1 1,1h1c0.55,0 1,-0.45 1,-1v-8l-2.08,-5.99zM6.5,16c-0.83,0 -1.5,-0.67 -1.5,-1.5S5.67,13 6.5,13s1.5,0.67 1.5,1.5S7.33,16 6.5,16zM17.5,16c-0.83,0 -1.5,-0.67 -1.5,-1.5s0.67,-1.5 1.5,-1.5 1.5,0.67 1.5,1.5 -0.67,1.5 -1.5,1.5zM5,11l1.5,-4.5h11L19,11H5z",
    "power": "M13,3h-2v10h2V3zM17.83,5.17l-1.42,1.42C17.99,7.86 19,9.81 19,12c0,3.87 -3.13,7 -7,7s-7,-3.13 -7,-7c0,-2.19 1.01,-4.14 2.58,-5.42L6.17,5.17C4.23,6.82 3,9.26 3,12c0,4.97 4.03,9 9,9s9,-4.03 9,-9c0,-2.74 -1.23,-5.18 -3.17,-6.83z",
    "nav": "M12,2L4.5,20.29l0.71,0.71L12,18l6.79,3 0.71,-0.71z",
}
MAT_TINT = {"on": "@color/tw_on", "acc": "@color/tw_acc", "tx": "@color/tw_icon", "mut": "@color/tw_mut", "star": "@color/tw_star"}
MAT_USE = [("arrow", "on"), ("arrow", "acc"), ("arrow", "tx"), ("clock", "tx"), ("clock", "on"), ("clock", "acc"), ("plus", "on"), ("chev", "mut"),
           ("star", "star"), ("bolt", "star"), ("person", "mut"), ("car", "on"), ("power", "on"), ("nav", "on"), ("chev", "acc")]
for n, t in MAT_USE:
    write(f"drawable/tw_v_{n}_{t}.xml", H + f'<vector {A} android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24" android:autoMirrored="false"><path android:fillColor="{MAT_TINT[t]}" android:pathData="{MAT[n]}" /></vector>\n')

# ═══════════════════════════ الصور: السيارات والرسومُ والمشهدُ والعلامة ═══════════════════════════
CARS = ["economy", "comfort", "vip", "hatchback", "suv", "family", "van", "city_taxi", "women"]
for folder in ("drawable-nodpi", "drawable-night-nodpi"):
    for old in (RES / folder).glob("tw_car_*.webp") if (RES / folder).exists() else []:
        old.unlink()  # السيارةُ واحدةٌ في النهار والليل الآن — لا نسخةَ ليليّةً قديمةٌ تغلب الجديدة
(RES / "drawable-nodpi").mkdir(parents=True, exist_ok=True)
(RES / "drawable-night-nodpi").mkdir(parents=True, exist_ok=True)
for key in CARS:
    shutil.copy(ASSETS / f"car-{key}.webp", RES / "drawable-nodpi" / f"tw_car_{key}.webp")
for il in ["gift", "wallet", "calendar", "percent", "crown", "pin"]:
    shutil.copy(ASSETS / f"il-{il}.webp", RES / "drawable-nodpi" / f"tw_il_{il}.webp")
shutil.copy(ASSETS / "scene-day.webp", RES / "drawable-nodpi" / "tw_scene.webp")
shutil.copy(ASSETS / "scene-night.webp", RES / "drawable-night-nodpi" / "tw_scene.webp")
shutil.copy(ASSETS / "wm-day.webp", RES / "drawable-nodpi" / "tw_wordmark.webp")
shutil.copy(ASSETS / "wm-night.webp", RES / "drawable-night-nodpi" / "tw_wordmark.webp")
shutil.copy(ASSETS / "wm-white.webp", RES / "drawable-nodpi" / "tw_wordmark_white.webp")
for stale in ("drawable/tw_bg.xml", "drawable/tw_btn.xml", "drawable/tw_btn2.xml", "drawable/w2_bg.xml"):
    pass  # تبقى: تستعملها ودجاتٌ أقدمُ (widget_ride / widget_rider_quick / widget_driver)

# ═══════════════════════════ لغةُ التخطيط: عُقَدٌ تُكتب XML وHTML معاً ═══════════════════════════


class N:
    def __init__(self, tag, kids=(), **a):
        self.tag, self.kids, self.a = tag, [k for k in kids if k is not None], a


def V(*k, **a): return N("V", k, **a)
def Hz(*k, **a): return N("H", k, **a)
def F(*k, **a): return N("F", k, **a)
def T(id_=None, text="", **a): return N("T", (), id=id_, text=text, **a)
def I(id_=None, src=None, **a): return N("I", (), id=id_, src=src, **a)
def Sp(weight=1, **a): return N("S", (), weight=weight, **a)
def Bar(id_="tw_bar", **a): return N("P", (), id=id_, **a)
def Ring(id_="tw_ring", size=100, **a): return N("R", (), id=id_, size=size, **a)


def dim(v):
    return {"m": "match_parent", "w": "wrap_content", None: "wrap_content"}.get(v, f"{v}dp")


GRAV = {"c": "center", "cv": "center_vertical", "ch": "center_horizontal", "s": "start", "e": "end", "t": "top", "b": "bottom",
        "bl": "bottom|left", "br": "bottom|right", "tl": "top|left", "tr": "top|right", "cl": "center_vertical|left",
        "cr": "center_vertical|right", "bs": "bottom|start", "be": "bottom|end", "ts": "top|start", "te": "top|end", "sv": "start|center_vertical"}


def xml_attrs(n, parent):
    a = n.a
    out = []
    if a.get("id"): out.append(f'android:id="@+id/{a["id"]}"')
    w, h = a.get("w", "m" if n.tag in "VHF" else "w"), a.get("h", "w")
    wt = a.get("weight")
    if wt is not None and parent == "H": w = 0
    if wt is not None and parent == "V": h = 0
    out.append(f'android:layout_width="{dim(w)}"')
    out.append(f'android:layout_height="{dim(h)}"')
    if wt is not None and parent and parent in "HV": out.append(f'android:layout_weight="{wt}"')
    if a.get("lg"): out.append(f'android:layout_gravity="{GRAV[a["lg"]]}"')
    if a.get("g"): out.append(f'android:gravity="{GRAV[a["g"]]}"')
    m = a.get("m")
    if m:
        s, t, e, b = m if isinstance(m, tuple) else (m, m, m, m)
        for k, v in (("Start", s), ("Top", t), ("End", e), ("Bottom", b)):
            if v: out.append(f'android:layout_margin{k}="{v}dp"')
    p = a.get("pad")
    if p:
        s, t, e, b = p if isinstance(p, tuple) else (p, p, p, p)
        out.append(f'android:paddingStart="{s}dp" android:paddingTop="{t}dp" android:paddingEnd="{e}dp" android:paddingBottom="{b}dp"')
    if a.get("bg"): out.append(f'android:background="@drawable/{a["bg"]}"')
    if a.get("gone"): out.append('android:visibility="gone"')
    if a.get("clip"): out.append('android:clipToOutline="true"')
    return out


def color_ref(c):
    return f"@color/{c}" if not c.startswith("#") else c


def to_xml(n, parent=None, depth=1, root=False):
    ind = "    " * depth
    at = xml_attrs(n, parent)
    if root: at = [A] + at + ['android:layoutDirection="rtl"']
    if n.tag in "VHF":
        cls = "FrameLayout" if n.tag == "F" else "LinearLayout"
        if n.tag in "VH": at.append(f'android:orientation="{"vertical" if n.tag == "V" else "horizontal"}"')
        inner = "\n".join(to_xml(k, n.tag, depth + 1) for k in n.kids)
        return f"{ind}<{cls} " + " ".join(at) + (">\n" + inner + f"\n{ind}</{cls}>" if inner else " />")
    if n.tag == "S":
        return f"{ind}<FrameLayout " + " ".join(at) + " />"
    if n.tag == "T":
        a = n.a
        at += [f'android:textColor="{color_ref(a.get("color", "tw_tx"))}"', f'android:textSize="{a.get("size", 13)}sp"', 'android:includeFontPadding="false"']
        if a.get("bold"): at.append('android:textStyle="bold"')
        at.append(f'android:maxLines="{a.get("lines", 1)}"')
        at.append('android:ellipsize="end"')
        if a.get("ltr"): at.append('android:textDirection="ltr"')
        if a.get("center"): at.append('android:gravity="center"')
        if a.get("ls"): at.append(f'android:letterSpacing="{a["ls"]}"')
        if a.get("text"): at.append(f'android:text="{html.escape(a["text"], quote=True)}"')
        return f"{ind}<TextView " + " ".join(at) + " />"
    if n.tag == "I":
        a = n.a
        if a.get("src"): at.append(f'android:src="@drawable/{a["src"]}"')
        at.append(f'android:scaleType="{ {"fit": "fitCenter", "crop": "centerCrop", "fitEnd": "fitEnd", "fitStart": "fitStart", "in": "centerInside", "xy": "fitXY"}[a.get("scale", "fit")] }"')
        if a.get("adjust"): at.append('android:adjustViewBounds="true"')
        if a.get("desc"): at.append(f'android:contentDescription="{html.escape(a["desc"], quote=True)}"')
        else: at.append('android:importantForAccessibility="no"')
        if a.get("ipad"): at.append(f'android:padding="{a["ipad"]}dp"')
        if a.get("alpha"): at.append(f'android:alpha="{a["alpha"]}"')
        return f"{ind}<ImageView " + " ".join(at) + " />"
    if n.tag == "P":
        at += ['style="?android:attr/progressBarStyleHorizontal"', 'android:max="100"', 'android:progress="0"', 'android:progressDrawable="@drawable/tw_bar"']
        return f"{ind}<ProgressBar " + " ".join(at) + " />"
    if n.tag == "R":
        at = [x for x in at if "layout_width" not in x and "layout_height" not in x]
        at += [f'android:layout_width="{n.a["size"]}dp"', f'android:layout_height="{n.a["size"]}dp"', 'style="?android:attr/progressBarStyleHorizontal"',
               'android:max="100"', 'android:progress="0"', 'android:progressDrawable="@drawable/tw_ring"']
        return f"{ind}<ProgressBar " + " ".join(at) + " />"
    raise ValueError(n.tag)


# ─── HTML: البنيةُ نفسُها بـflex — للمعاينة قبل البناء
def hex2css(v):
    v = v.lstrip("#")
    if len(v) == 8:
        a, r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16), int(v[6:8], 16)
        return f"rgba({r},{g},{b},{a / 255:.3f})"
    return "#" + v


def css_bg(name, th):
    c = lambda k: hex2css({**th, **HOT}[k])
    if name == "tw_card":
        return (f"background: linear-gradient(to bottom, {c('tw_hi')} 0, rgba(255,255,255,0) 56px), radial-gradient(240px circle at 0% 100%, {c('tw_glow')}, rgba(0,0,0,0) 100%), "
                f"linear-gradient(150deg, {c('tw_bg0')}, {c('tw_bg1')}); border:1px solid {c('tw_line')}; border-radius:{R}px;")
    if name == "tw_card_hot":
        return f"background: radial-gradient(200px circle at 100% 0%, rgba(255,255,255,.25), rgba(255,255,255,0)), linear-gradient(135deg,#FF9A5E,#F05A28 50%,#B93A14); border:1px solid rgba(255,255,255,.2); border-radius:{R}px;"
    if name in ("tw_glass", "tw_tile"):
        return f"background:{c('tw_glass')}; border:1px solid {c('tw_gline')}; border-radius:{18 if name == 'tw_glass' else 20}px;"
    if name == "tw_glass_hot":
        return f"background:{c('h_glass')}; border:1px solid {c('h_line')}; border-radius:18px;"
    if name == "tw_pill":
        return f"background: linear-gradient(to bottom, rgba(255,255,255,.2), rgba(255,255,255,0) 50%), linear-gradient(90deg,{c('tw_acc2')},{c('tw_acc')}); border-radius:99px;"
    if name == "tw_pill_light": return "background:#fff; border-radius:99px;"
    if name == "tw_pill_glass": return f"background:{c('tw_glass2')}; border:1px solid {c('tw_gline')}; border-radius:99px;"
    if name == "tw_chip": return f"background:{c('tw_chipbg')}; border:1px solid {c('tw_gline')}; border-radius:99px;"
    if name == "tw_circle": return f"background: linear-gradient(150deg,{c('tw_acc2')},{c('tw_acc')}); border-radius:50%; box-shadow:0 0 0 5px rgba(240,90,40,.18);"
    if name == "tw_circle_glass": return f"background:{c('tw_glass')}; border:1px solid {c('tw_gline')}; border-radius:50%;"
    if name == "tw_circle_light": return "background:#fff; border-radius:50%;"
    if name == "tw_photo_ring": return f"border:2px solid {c('tw_acc')}; border-radius:50%;"
    return ""


HGRAV = {"c": ("center", "center"), "cv": (None, "center"), "ch": ("center", None), "s": ("flex-start", None), "e": ("flex-end", None),
         "t": (None, "flex-start"), "b": (None, "flex-end"), "sv": ("flex-start", "center")}


def to_html(n, th, imgs, data, parent=None):
    a = n.a
    st = []
    w, h = a.get("w", "m" if n.tag in "VHF" else "w"), a.get("h", "w")
    wt = a.get("weight")
    if parent and parent in "HV":
        if wt is not None:
            st.append(f"flex:{wt} 1 0; min-{'width' if parent == 'H' else 'height'}:0;")
            if parent == "H": w = None
            else: h = None
        cross_w = parent == "V"
        if cross_w and w == "m": st.append("align-self:stretch;"); w = None
        if not cross_w and h == "m": st.append("align-self:stretch;"); h = None
    if isinstance(w, int): st.append(f"width:{w}px; flex-shrink:0;")
    elif w == "m": st.append("width:100%;")
    if isinstance(h, int): st.append(f"height:{h}px; flex-shrink:0;")
    elif h == "m": st.append("height:100%;")
    if parent == "F":
        st.append("position:absolute;")
        lg = a.get("lg", "")
        g = GRAV.get(lg, "")
        if w == "m" or "left" in g or "start" in g or g in ("", "top", "bottom"):
            pass
        horiz = "left:0;" if "left" in g else "right:0;" if "right" in g else ""
        if "start" in g: horiz = "right:0;"
        if "end" in g: horiz = "left:0;"
        vert = "top:0;" if "top" in g else "bottom:0;" if "bottom" in g else ""
        if g in ("center",):
            st.append("left:0;right:0;top:0;bottom:0;margin:auto;")
        elif g == "center_vertical|left" or g == "center_vertical|right":
            st.append(horiz + "top:0;bottom:0;margin-top:auto;margin-bottom:auto;")
        else:
            st.append((horiz or ("right:0;" if w != "m" else "left:0;right:0;")) + (vert or "top:0;"))
        mm = a.get("m") or 0
        ms, mt, me, mb = mm if isinstance(mm, tuple) else (mm, mm, mm, mm)
        if w == "m": st.append(f"left:{me}px;right:{ms}px;width:calc(100% - {ms + me}px);")
        if h == "m": st.append(f"top:{mt}px;bottom:{mb}px;height:calc(100% - {mt + mb}px);")
        if w == "m" or h == "m": a = dict(a, m=None)
    m = a.get("m")
    if m and not (parent == "F" and (w == "m" or h == "m")):
        s, t, e, b = m if isinstance(m, tuple) else (m, m, m, m)
        st.append(f"margin-right:{s}px; margin-top:{t}px; margin-left:{e}px; margin-bottom:{b}px;")
    p = a.get("pad")
    if p:
        s, t, e, b = p if isinstance(p, tuple) else (p, p, p, p)
        st.append(f"padding:{t}px {e}px {b}px {s}px;")
    if a.get("bg"): st.append(css_bg(a["bg"], th))
    idn = a.get("id")
    hidden = data.get("__gone__", set())
    is_hidden = (a.get("gone") and idn not in data.get("__show__", set())) or idn in hidden
    st.append("box-sizing:border-box;")
    if n.tag in "VHF":
        if n.tag == "F":
            st.append("position:relative;" if parent != "F" else "")
            if a.get("clip") or parent is None: st.append("overflow:hidden;")
        else:
            st.append(f"display:flex; flex-direction:{'column' if n.tag == 'V' else 'row'};")
            g = a.get("g")
            if g:
                main, cross = HGRAV.get(g, (None, None))
                if n.tag == "V": main, cross = (cross, main) if g in ("cv", "ch") else (main, cross)
                if g == "cv": st.append("align-items:center;" if n.tag == "H" else "justify-content:center;")
                elif g == "ch": st.append("justify-content:center;" if n.tag == "H" else "align-items:center;")
                elif g == "c": st.append("justify-content:center; align-items:center;")
                elif g == "s": st.append("justify-content:flex-start;" if n.tag == "H" else "align-items:flex-start;")
                elif g == "e": st.append("justify-content:flex-end;" if n.tag == "H" else "align-items:flex-end;")
                elif g == "sv": st.append("align-items:center; justify-content:flex-start;")
                elif g == "b": st.append("align-items:flex-end;" if n.tag == "H" else "justify-content:flex-end;")
            elif n.tag == "V": st.append("align-items:flex-start;")
        if parent is None: st.append("direction:rtl;")
        if is_hidden: st.append("display:none !important;")
        inner = "".join(to_html(k, th, imgs, data, n.tag) for k in n.kids)
        return f'<div style="{" ".join(st)}">{inner}</div>'
    if n.tag == "S":
        if wt is None: return f'<div style="{" ".join(st)}"></div>'
        return f'<div style="{" ".join(st)}"></div>'
    if is_hidden: return ""
    if n.tag == "T":
        col = {**th, **HOT}.get(a.get("color", "tw_tx"), a.get("color", "#000"))
        txt = data.get(idn, a.get("text", "")) if idn else a.get("text", "")
        lines = a.get("lines", 1)
        st.append(f"color:{hex2css(col)}; font-size:{a.get('size', 13)}px; line-height:1.18; font-weight:{700 if a.get('bold') else 400};"
                  f" display:-webkit-box; -webkit-line-clamp:{lines}; -webkit-box-orient:vertical; overflow:hidden; white-space:{'normal' if lines > 1 else 'nowrap'}; text-overflow:ellipsis;")
        if a.get("ltr"): st.append("direction:ltr; unicode-bidi:plaintext;")
        if a.get("center"): st.append("text-align:center;")
        if a.get("ls"): st.append(f"letter-spacing:{a['ls']}em;")
        return f'<div style="{" ".join(st)}">{html.escape(str(txt))}</div>'
    if n.tag == "I":
        srcn = data.get(idn, a.get("src")) if idn else a.get("src")
        if srcn is None: return f'<div style="{" ".join(st)}"></div>'
        fit = {"fit": "contain", "crop": "cover", "fitEnd": "contain", "fitStart": "contain", "in": "scale-down", "xy": "fill"}[a.get("scale", "fit")]
        if a.get("alpha"): st.append(f"opacity:{a['alpha']};")
        pos = {"fitEnd": "left bottom", "fitStart": "right top"}.get(a.get("scale"), "center")
        if a.get("ipad"): st.append(f"padding:{a['ipad']}px;")
        if a.get("adjust") and w in ("w", None): st.append("width:auto;")
        return f'<img src="{imgs(srcn)}" style="{" ".join(st)} object-fit:{fit}; object-position:{pos}; display:block;">'
    if n.tag == "P":
        v = data.get(idn, 0)
        tr = hex2css(th["tw_track"])
        return f'<div style="{" ".join(st)} height:6px; background:{tr}; border-radius:4px; overflow:hidden;"><div style="width:{v * 100:.0f}%; height:100%; margin-right:auto; margin-left:0; background:linear-gradient(90deg,{hex2css(th["tw_acc"])},{hex2css(th["tw_acc2"])}); float:right;"></div></div>'
    if n.tag == "R":
        v = data.get(idn, 0)
        s = n.a["size"]
        tr, ac = hex2css(th["tw_track"]), hex2css(th["tw_acc"])
        th_ = s / 11
        return (f'<div style="{" ".join(st)} width:{s}px;height:{s}px;border-radius:50%;background:conic-gradient({ac} {v * 360:.0f}deg,{tr} 0);'
                f'-webkit-mask:radial-gradient(circle,transparent {s / 2 - th_:.1f}px,#000 {s / 2 - th_ + .5:.1f}px);"></div>')
    raise ValueError(n.tag)


# ═══════════════════════════ القطعُ المشتركة ═══════════════════════════
def header(title, glyph=None, tid="tw_title", size=14.5, dot=None, color="tw_tx", m=None):
    kids = []
    if dot: kids.append(I("tw_dot", dot, w=8, h=8, m=(0, 0, 7, 0)))
    if glyph: kids.append(I(None, glyph, w=20, h=20, m=(0, 0, 7, 0)))
    kids.append(T(tid, title, size=size, bold=True, color=color, weight=1))
    return Hz(*kids, w="m", g="cv", m=m)


def pill(text, id_="tw_btn", style="tw_pill", arrow=True, icon=None, h=38, size=14, full=False, m=None, gone=False, tid=None):
    col = {"tw_pill": "tw_on", "tw_pill_light": "tw_acc_tx", "tw_pill_glass": "tw_tx"}[style]
    arr = {"tw_pill": "tw_v_arrow_on", "tw_pill_light": "tw_v_arrow_acc", "tw_pill_glass": "tw_v_arrow_tx"}[style]
    kids = []
    if icon: kids.append(I(None, icon, w=18, h=18, m=(0, 0, 6, 0)))
    kids.append(T(tid or (id_ + "_t"), text, size=size, bold=True, color=col))
    if arrow: kids.append(I(None, arr, w=17, h=17, m=(8, 0, 0, 0)))
    return Hz(*kids, id=id_, w="m" if full else "w", h=h, g="c", pad=(16, 0, 14, 0), bg=style, m=m, gone=gone)


def tile(i, glyph, label, big=False, gone=False):
    return V(I(f"tw_t{i}i", glyph, w=34 if big else 28, h=34 if big else 28),
             T(f"tw_t{i}l", label, size=12.5 if big else 11.5, bold=True, m=(0, 6, 0, 0), center=True),
             id=f"tw_t{i}", weight=1, h="m", g="c", bg="tw_tile", m=(0 if i == 0 else 7, 0, 0, 0), pad=(4, 6, 4, 6), gone=gone)


def art(id_, src, **a):
    return I(id_, src, **a)


def scene_car(car="tw_car_economy", scene=True, car_m=(0, 0, 0, 0)):
    kids = []
    if scene:
        kids.append(I("tw_scene", "tw_scene", w="m", h="m", scale="fitEnd", alpha=0.8))
    kids.append(I("tw_car", car, w="m", h="m", scale="fitEnd", m=car_m))
    return kids


def card(*kids, hot=False, **a):
    a.setdefault("bg", "tw_card_hot" if hot else "tw_card")
    return F(*kids, id="tw_root", w="m", h="m", clip=True, **a)


def places_row(m=(12, 0, 12, 12), h=74):
    return Hz(tile(0, "tw_g_home", "المنزل"), tile(1, "tw_g_work", "العمل"), tile(2, "tw_g_flight", "المطار", gone=True),
              w="m", h=h, m=m)


# ═══════════════════════════ ودجاتُ الراكب ═══════════════════════════
def rider_layouts():
    L = {}
    # ── اطلب مشوارك
    hero_text = lambda big: V(I(None, "tw_wordmark", w="w", h=16 if big else 14, adjust=True, scale="fitStart"),
                              T("tw_title", "اطلب مشوارك الآن", size=19 if big else 17, bold=True, lines=2, m=(0, 10, 0, 0)),
                              T("tw_sub", "بكل سهولة وأمان", size=12.5, color="tw_mut", m=(0, 5, 0, 0)),
                              Sp(), pill("إلى أين؟", m=(0, 8, 0, 0)), weight=1, h="m", pad=(16, 16, 4, 16))
    L["request_s"] = card(*scene_car(car_m=(6, 0, 6, 8)),
                          V(I(None, "tw_wordmark", w="w", h=13, adjust=True, scale="fitStart"), T("tw_title", "اطلب مشوارك", size=15, bold=True, m=(0, 7, 0, 0)),
                            T("tw_sub", "بكل سهولة وأمان", size=11, color="tw_mut", m=(0, 3, 0, 0)), pad=(14, 14, 14, 0)))
    L["request_m"] = card(Hz(hero_text(False), F(*scene_car(car_m=(0, 10, 6, 10)), weight=1.15, h="m"), w="m", h="m"))
    L["request_l"] = card(V(Hz(hero_text(True), F(*scene_car(car_m=(0, 12, 8, 6)), weight=1.15, h="m"), w="m", weight=1), places_row(), w="m", h="m"))

    # ── السائق في الطريق (حيّ / فارغ)
    def eta_chip(id_="tw_chip"):
        return Hz(I(None, "tw_v_clock_acc", w=17, h=17, m=(0, 0, 6, 0)), T("tw_big", "", size=15, bold=True, ltr=True),
                  T("tw_unit", "دقائق", size=12.5, color="tw_mut", m=(5, 0, 0, 0)), id=id_, w="w", h=34, g="cv", pad=(12, 0, 12, 0), bg="tw_chip")

    def driver_row(photo=44, big=False):
        return Hz(F(I("tw_photo", "tw_v_person_mut", w=photo, h=photo, scale="crop", ipad=0), I(None, "tw_photo_ring", w=photo, h=photo), w=photo, h=photo),
                  V(T("tw_title", "السائق في الطريق", size=15 if big else 14, bold=True),
                    Hz(I(None, "tw_v_star_star", w=14, h=14, m=(0, 0, 4, 0)), T("tw_sub", "", size=12, color="tw_mut", ltr=False), g="cv", m=(0, 4, 0, 0)),
                    weight=1, m=(10, 0, 0, 0)),
                  w="m", g="cv", pad=(10, 9, 12, 9), bg="tw_glass")

    def empty(title, sub, s=False):
        return V(T("tw_e_title", title, size=15 if not s else 14, bold=True), T("tw_e_sub", sub, size=12, color="tw_mut", lines=2, m=(0, 4, 0, 0)),
                 F(*scene_car(scene=False), weight=1, w="m"), pill("اطلب رحلة", id_="tw_e_btn", h=34, size=13), id="tw_empty", w="m", h="m", pad=(14, 14, 14, 14))

    L["on_the_way_s"] = card(I("tw_map", None, w="m", h="m", scale="crop", gone=True),
                             V(eta_chip(), Sp(), F(I("tw_photo", "tw_v_person_mut", w=52, h=52, scale="crop"), I(None, "tw_photo_ring", w=52, h=52), w=52, h=52),
                               T("tw_title", "السائق في الطريق", size=13.5, bold=True, m=(0, 6, 0, 0)), T("tw_sub", "", size=11.5, color="tw_mut", m=(0, 2, 0, 0)),
                               id="tw_live", gone=True, w="m", h="m", pad=(12, 12, 12, 12)),
                             empty("السائق في الطريق", "يظهر سائقك هنا حين تطلب رحلة", True))
    L["on_the_way_m"] = card(Hz(V(eta_chip(), Sp(), driver_row(40), weight=1.35, h="m"),
                                F(I("tw_map", None, w="m", h="m", scale="crop", gone=True), F(*scene_car(scene=False), id="tw_carbox", w="m", h="m", gone=True),
                                  weight=1, h="m", m=(10, 0, 0, 0), bg="tw_glass", clip=True),
                                id="tw_live", gone=True, w="m", h="m", pad=(12, 12, 12, 12)),
                             empty("السائق في الطريق", "يظهر سائقك هنا حين تطلب رحلة"))
    L["on_the_way_l"] = card(I("tw_map", None, w="m", h="m", scale="crop", gone=True),
                             F(*scene_car(scene=False, car_m=(14, 56, 14, 124)), id="tw_carbox", w="m", h="m", gone=True),
                             V(eta_chip(), Sp(), driver_row(52, True), Bar(w="m", h=6, m=(4, 10, 4, 0)), id="tw_live", gone=True, w="m", h="m", pad=(14, 14, 14, 14)),
                             empty("السائق في الطريق", "يظهر سائقك هنا حين تطلب رحلة"))

    # ── طلبٌ سريع
    circle = lambda s: I("tw_qbtn", "tw_v_car_on", w=s, h=s, ipad=int(s * 0.27), bg="tw_circle", desc="اطلب رحلة")
    L["quick_s"] = card(V(I(None, "tw_wordmark", w="w", h=13, adjust=True), T("tw_title", "طلب سريع", size=15, bold=True, m=(0, 6, 0, 0)),
                          F(circle(72), weight=1, w="m", g="c"), w="m", h="m", g="ch", pad=(12, 14, 12, 12)))
    L["quick_m"] = card(Hz(V(I(None, "tw_wordmark", w="w", h=15, adjust=True, scale="fitStart"), T("tw_title", "طلب سريع", size=19, bold=True, m=(0, 8, 0, 0)),
                             T("tw_sub", "رحلتك بلمسةٍ واحدة", size=12.5, color="tw_mut", m=(0, 4, 0, 0)), weight=1),
                           circle(80), w="m", h="m", g="cv", pad=(18, 14, 16, 14)))
    L["quick_l"] = card(V(Hz(V(I(None, "tw_wordmark", w="w", h=16, adjust=True, scale="fitStart"), T("tw_title", "طلب سريع", size=20, bold=True, m=(0, 8, 0, 0)),
                               T("tw_sub", "رحلتك بلمسةٍ واحدة", size=13, color="tw_mut", m=(0, 4, 0, 0)), weight=1),
                             circle(80), w="m", g="cv", pad=(18, 16, 16, 0)),
                          F(*scene_car(car_m=(14, 4, 14, 4)), w="m", weight=1), places_row(), w="m", h="m"))

    # ── وجهاتك المفضّلة
    fav_head = lambda s=14.5: header("وجهاتك المفضلة", "tw_v_star_star", size=s)
    L["favorites_s"] = card(V(fav_head(13), Hz(tile(0, "tw_g_home", "المنزل"), tile(1, "tw_g_work", "العمل"), w="m", weight=1, m=(0, 8, 0, 0)),
                              Hz(tile(2, "tw_g_flight", "المطار", gone=True), tile(3, "tw_g_location_on", "الكل"), w="m", weight=1, m=(0, 7, 0, 0)),
                              w="m", h="m", pad=(12, 12, 12, 12)))
    L["favorites_m"] = card(V(fav_head(), Hz(tile(0, "tw_g_home", "المنزل"), tile(1, "tw_g_work", "العمل"), tile(2, "tw_g_flight", "المطار", gone=True),
                                             w="m", weight=1, m=(0, 10, 0, 8)),
                              pill("عرض الكل", id_="tw_btn", style="tw_pill_glass", h=32, size=12.5, full=True), w="m", h="m", pad=(14, 13, 14, 12)))
    L["favorites_l"] = card(V(fav_head(16), Hz(tile(0, "tw_g_home", "المنزل", big=True), tile(1, "tw_g_work", "العمل", big=True),
                                               tile(2, "tw_g_flight", "المطار", big=True, gone=True), w="m", h=96, m=(0, 12, 0, 6)),
                              F(*scene_car(car_m=(12, 0, 12, 0)), w="m", weight=1, m=(0, 0, 0, 8)),
                              pill("عرض كلِّ أماكني", id_="tw_btn", style="tw_pill_glass", h=38, size=13.5, full=True), w="m", h="m", pad=(16, 16, 16, 14)))

    # ── محفظتي
    amount = lambda s: Hz(T("tw_big", "", size=s, bold=True, ltr=True), T("tw_unit", "", size=13, color="tw_mut", m=(6, 0, 0, 2)), id="tw_bigrow", g="b")
    L["wallet_s"] = card(I("tw_art", "tw_il_wallet", w=64, h=64, lg="tl", m=(0, 6, 4, 0)),
                         V(header("محفظتي", None, size=13.5), Sp(), amount(24), T("tw_sub", "افتح التطبيق لترى رصيدك", size=10.5, color="tw_mut", lines=2, m=(0, 2, 0, 6)),
                           pill("شحن", icon="tw_v_plus_on", arrow=False, h=32, size=12.5, full=True), w="m", h="m", pad=(12, 12, 12, 12)))
    L["wallet_m"] = card(Hz(V(header("محفظتي", "tw_g_account_balance_wallet"), Sp(), amount(30),
                              T("tw_sub", "افتح التطبيق لترى رصيدك", size=11, color="tw_mut", m=(0, 3, 0, 0)), Sp(),
                              pill("شحن الرصيد", icon="tw_v_plus_on", arrow=False, h=36, size=13), weight=1.25, h="m"),
                            I("tw_art", "tw_il_wallet", weight=0.9, h="m", m=(4, 4, 0, 4)), w="m", h="m", pad=(14, 13, 10, 13)))
    L["wallet_l"] = card(V(header("محفظتي", "tw_g_account_balance_wallet", size=16), I("tw_art", "tw_il_wallet", w="m", weight=1, m=(0, 8, 0, 8)),
                           amount(34), T("tw_sub", "افتح التطبيق لترى رصيدك", size=11.5, color="tw_mut", m=(0, 3, 0, 10)),
                           Hz(pill("شحن الرصيد", icon="tw_v_plus_on", arrow=False, h=40, size=13.5, full=True, weight=1) if False else
                              pill("شحن الرصيد", icon="tw_v_plus_on", arrow=False, h=40, size=13.5, full=True),
                              w="m"), w="m", h="m", pad=(16, 16, 16, 16)))

    # ── خصمٌ خاص (البطاقةُ الساخنة)
    disc_txt = lambda big, s: V(T("tw_title", "خصم خاص", size=15 if big else 14, bold=True, color="h_tx"), Sp(),
                                T("tw_big", "", size=s, bold=True, color="h_tx", ltr=True), T("tw_sub", "عروضٌ تصلك هنا", size=12, color="h_mut", lines=2, m=(0, 3, 0, 0)),
                                Sp(), pill("استفد الآن", style="tw_pill_light", h=34, size=13), weight=1.2, h="m")
    L["discount_s"] = card(I("tw_art", "tw_il_gift", w=70, h=70, lg="tl", m=(0, 4, 2, 0)),
                           V(T("tw_title", "خصم خاص", size=13.5, bold=True, color="h_tx"), Sp(), T("tw_big", "", size=28, bold=True, color="h_tx", ltr=True),
                             T("tw_sub", "عروضٌ تصلك هنا", size=11, color="h_mut", lines=2, m=(0, 2, 0, 0)), w="m", h="m", pad=(13, 13, 13, 13)), hot=True)
    L["discount_m"] = card(Hz(disc_txt(False, 34), I("tw_art", "tw_il_gift", weight=0.9, h="m", m=(4, 2, 0, 2)), w="m", h="m", pad=(15, 14, 10, 14)), hot=True)
    L["discount_l"] = card(V(I("tw_art", "tw_il_gift", w="m", weight=1, m=(0, 0, 0, 8)), T("tw_title", "خصم خاص", size=16, bold=True, color="h_tx"),
                             T("tw_big", "", size=40, bold=True, color="h_tx", ltr=True, m=(0, 4, 0, 0)),
                             T("tw_sub", "عروضٌ تصلك هنا", size=12.5, color="h_mut", lines=2, m=(0, 4, 0, 12)),
                             pill("استفد الآن", style="tw_pill_light", h=40, size=14, full=True), w="m", h="m", pad=(16, 16, 16, 16)), hot=True)

    # ── حجزٌ مسبق
    sched_txt = lambda s: V(header("حجز مسبق", "tw_g_schedule", size=s), T("tw_big", "", size=17, bold=True, m=(0, 8, 0, 0), gone=True),
                            T("tw_sub", "رحلتك في موعدٍ لاحق", size=12, color="tw_mut", lines=2, m=(0, 6, 0, 0)), Sp(),
                            pill("احجز الآن", icon="tw_v_clock_on", arrow=False, h=36, size=13), weight=1.2, h="m")
    L["schedule_s"] = card(V(header("حجز مسبق", None, size=13.5), I("tw_art", "tw_il_calendar", w="m", weight=1, m=(0, 4, 0, 4)),
                             T("tw_big", "", size=13, bold=True, center=True, w="m", gone=True),
                             pill("احجز", icon="tw_v_clock_on", arrow=False, h=32, size=12.5, full=True, m=(0, 4, 0, 0)), w="m", h="m", pad=(12, 12, 12, 12)))
    L["schedule_m"] = card(Hz(sched_txt(14.5), I("tw_art", "tw_il_calendar", weight=0.9, h="m", m=(4, 4, 0, 4)), w="m", h="m", pad=(14, 13, 10, 13)))
    L["schedule_l"] = card(V(header("حجز مسبق", "tw_g_schedule", size=16), I("tw_art", "tw_il_calendar", w="m", weight=1, m=(0, 8, 0, 8)),
                             T("tw_big", "", size=19, bold=True, gone=True), T("tw_sub", "رحلتك في موعدٍ لاحق", size=12.5, color="tw_mut", lines=2, m=(0, 4, 0, 12)),
                             pill("احجز الآن", icon="tw_v_clock_on", arrow=False, h=40, size=14, full=True), w="m", h="m", pad=(16, 16, 16, 16)))

    # ── خدمات التنقّل السريع
    svc_head = lambda s=14.5: header("خدمات التنقّل السريع", "tw_v_bolt_star", size=s)
    SVC = [("tw_g_directions_car", "بين المدن"), ("tw_g_schedule", "حجز مسبق"), ("tw_g_history", "التنقّل اليوميّ"), ("tw_g_account_balance_wallet", "المحفظة")]
    L["services_s"] = card(V(svc_head(13), Hz(tile(0, *SVC[0]), tile(1, *SVC[1]), w="m", weight=1, m=(0, 8, 0, 0)),
                             Hz(tile(2, *SVC[2]), tile(3, *SVC[3]), w="m", weight=1, m=(0, 7, 0, 0)), w="m", h="m", pad=(12, 12, 12, 12)))
    L["services_m"] = card(V(svc_head(), Hz(*[tile(i, *SVC[i]) for i in range(4)], w="m", weight=1, m=(0, 10, 0, 0)),
                             T("tw_sub", "", size=12, color="tw_mut", gone=True), w="m", h="m", pad=(14, 13, 14, 13)))
    L["services_l"] = card(V(svc_head(16), Hz(tile(0, *SVC[0], big=True), tile(1, *SVC[1], big=True), w="m", weight=1, m=(0, 12, 0, 0)),
                             Hz(tile(2, *SVC[2], big=True), tile(3, *SVC[3], big=True), w="m", weight=1, m=(0, 8, 0, 0)),
                             T("tw_sub", "", size=12, color="tw_mut", gone=True), w="m", h="m", pad=(16, 16, 16, 16)))

    # ── رحلتي الحالية (حيّ / فارغ)
    def status_chip(big):
        return V(T("tw_chip_t", "الوصول خلال", size=11.5, color="tw_mut"),
                 Hz(T("tw_big", "", size=26 if big else 22, bold=True, ltr=True), T("tw_unit", "", size=12.5, color="tw_mut", m=(5, 0, 0, 2)), id="tw_bigrow", g="b", m=(0, 4, 0, 0)),
                 id="tw_chip", w="w", pad=(14, 10, 14, 10), bg="tw_glass")
    head_cur = lambda s: header("رحلتي الحالية", None, size=s, dot="tw_dot_ok")
    L["current_s"] = card(V(V(head_cur(13), T("tw_chip_t", "الوصول خلال", size=11, color="tw_mut", m=(0, 8, 0, 0)),
                              Hz(T("tw_big", "", size=24, bold=True, ltr=True), T("tw_unit", "", size=12, color="tw_mut", m=(5, 0, 0, 2)), id="tw_bigrow", g="b"),
                              F(I("tw_car", "tw_car_economy", w="m", h="m", scale="fitEnd"), w="m", weight=1), Bar(w="m", h=6, m=(0, 6, 0, 0)),
                              id="tw_live", gone=True, w="m", h="m", pad=(12, 12, 12, 12)), w="m", h="m"),
                          empty("رحلتي الحالية", "لا رحلة الآن", True))
    L["current_m"] = card(V(head_cur(14.5), Hz(status_chip(False), F(I("tw_map", None, w="m", h="m", scale="crop", gone=True),
                                                                     I("tw_car", "tw_car_economy", w="m", h="m", scale="fit"), weight=1, h="m", m=(10, 0, 0, 0)),
                                               w="m", weight=1, g="cv", m=(0, 8, 0, 8)), Bar(w="m", h=6), id="tw_live", gone=True, w="m", h="m", pad=(14, 13, 14, 13)),
                          empty("رحلتي الحالية", "لا رحلة الآن"))
    L["current_l"] = card(V(head_cur(16), F(I("tw_map", None, w="m", h="m", scale="crop", gone=True),
                                            I("tw_car", "tw_car_economy", w="m", h="m", scale="fit"), w="m", weight=1, m=(0, 10, 0, 10), bg="tw_glass"),
                            Hz(status_chip(True), Sp(), w="m"), Bar(w="m", h=6, m=(0, 10, 0, 0)), id="tw_live", gone=True, w="m", h="m", pad=(16, 16, 16, 16)),
                          empty("رحلتي الحالية", "لا رحلة الآن"))

    # ── المنزل / العمل
    for kind, glyph, name in (("home", "tw_g_home", "المنزل"), ("work", "tw_g_work", "العمل")):
        circ = lambda s: F(I("tw_icon", glyph, w=int(s * 0.56), h=int(s * 0.56), lg="c"), w=s, h=s, bg="tw_circle_glass")
        L[f"{kind}_s"] = card(V(circ(70), T("tw_title", name, size=17, bold=True, m=(0, 9, 0, 0)), T("tw_sub", "اطلب رحلة", size=11.5, color="tw_mut", m=(0, 3, 0, 0)),
                                w="m", h="m", g="c", pad=(10, 10, 10, 10)))
        L[f"{kind}_m"] = card(Hz(circ(76), V(T("tw_title", name, size=20, bold=True), T("tw_sub", "اطلب رحلة", size=12.5, color="tw_mut", m=(0, 4, 0, 10)),
                                             pill("اطلب رحلة", h=34, size=13), weight=1, m=(14, 0, 0, 0)), w="m", h="m", g="cv", pad=(18, 14, 16, 14)))
        L[f"{kind}_l"] = card(V(F(*scene_car(car_m=(10, 0, 10, 0)), w="m", weight=1),
                                Hz(circ(56), V(T("tw_title", name, size=19, bold=True), T("tw_sub", "اطلب رحلة", size=12.5, color="tw_mut", m=(0, 3, 0, 0)), weight=1, m=(12, 0, 0, 0)),
                                   w="m", g="cv", m=(0, 10, 0, 12)), pill("اطلب رحلة", h=40, size=14, full=True), w="m", h="m", pad=(16, 12, 16, 16)))

    # ── نقاطي
    L["points_s"] = card(V(I("tw_art", "tw_il_crown", w=50, h=44), T("tw_title", "نقاطي", size=13, color="tw_mut", bold=True, m=(0, 6, 0, 0)),
                           Hz(T("tw_big", "", size=26, bold=True, ltr=True), I(None, "tw_v_star_star", w=20, h=20, m=(6, 0, 0, 0)), g="cv", m=(0, 2, 0, 0)),
                           T("tw_sub", "", size=11, color="tw_mut", m=(0, 3, 0, 0)), w="m", h="m", g="c", pad=(10, 10, 10, 10)))
    ring_box = lambda s, inner: F(Ring(size=s, lg="c"), V(*inner, w="w", lg="c", g="ch"), w=s, h=s)
    L["points_m"] = card(Hz(ring_box(110, [I(None, "tw_il_crown", w=34, h=30), T("tw_ring_t", "", size=15, bold=True, ltr=True, m=(0, 2, 0, 0))]),
                            V(header("نقاطي", "tw_v_star_star"), Hz(T("tw_big", "", size=30, bold=True, ltr=True), g="b", m=(0, 6, 0, 0)),
                              T("tw_sub", "", size=12, color="tw_mut", lines=2, m=(0, 3, 0, 0)), Sp(),
                              pill("نقاطي ومكافآتي", style="tw_pill_glass", h=32, size=12.5), weight=1, h="m", m=(14, 0, 0, 0)),
                            w="m", h="m", g="cv", pad=(16, 14, 14, 14)))
    L["points_l"] = card(V(header("نقاطي", "tw_v_star_star", size=16), F(ring_box(150, [I(None, "tw_il_crown", w=48, h=42), T("tw_big", "", size=30, bold=True, ltr=True, m=(0, 2, 0, 0)),
                                                                                       T("tw_ring_t", "", size=12, color="tw_mut")]), w="m", weight=1, g="c"),
                           T("tw_sub", "", size=12.5, color="tw_mut", lines=2, center=True, w="m", m=(0, 0, 0, 10)),
                           pill("نقاطي ومكافآتي", style="tw_pill_glass", h=38, size=13.5, full=True), w="m", h="m", pad=(16, 16, 16, 16)))

    # ── آخر رحلاتي
    def last_row(big):
        return Hz(I("tw_car", "tw_car_economy", w=96 if big else 76, h=60 if big else 46, scale="fit"),
                  V(T("tw_sub", "", size=13.5 if big else 13, bold=True), T("tw_sub2", "", size=12, color="tw_mut", m=(0, 4, 0, 0)), weight=1, m=(10, 0, 6, 0)),
                  I(None, "tw_v_chev_mut", w=18, h=18), id="tw_row", w="m", g="cv", pad=(8, 8, 10, 8), bg="tw_glass", gone=True)
    def rec_empty():
        return V(T("tw_e_sub", "لا رحلات بعد — رحلتك الأولى تظهر هنا", size=12, color="tw_mut", lines=2, m=(0, 6, 0, 0)), F(*scene_car(scene=False), w="m", weight=1),
                 pill("اطلب رحلة", id_="tw_e_btn", h=34, size=13), id="tw_empty", w="m", weight=1)
    rh = lambda s: header("آخر رحلاتي", "tw_g_history", size=s)
    L["recent_s"] = card(V(rh(13), V(T("tw_sub", "", size=13, bold=True, lines=2), T("tw_sub2", "", size=11, color="tw_mut", m=(0, 4, 0, 0)),
                                     id="tw_row", w="m", weight=1, pad=(10, 10, 10, 10), bg="tw_glass", m=(0, 8, 0, 8), gone=True),
                           pill("مرة أخرى", h=32, size=12.5, full=True, gone=True), rec_empty(), w="m", h="m", pad=(12, 12, 12, 12)))
    L["recent_m"] = card(V(rh(14.5), F(last_row(False), w="m", m=(0, 8, 0, 8)),
                           Hz(pill("اطلبها مرة أخرى", h=34, size=12.5), pill("كل الرحلات", id_="tw_btn2", style="tw_pill_glass", arrow=False, h=34, size=12.5, m=(8, 0, 0, 0)), w="m", id="tw_btns", gone=True),
                           rec_empty(), w="m", h="m", pad=(14, 13, 14, 13)))
    rec_dest = lambda i: Hz(I(None, "tw_g_location_on", w=20, h=20), T(f"tw_r{i}l", "", size=12.5, bold=True, weight=1, m=(8, 0, 0, 0)), I(None, "tw_v_chev_mut", w=16, h=16),
                            id=f"tw_r{i}", w="m", h=36, g="cv", pad=(10, 0, 10, 0), bg="tw_glass", m=(0, 6, 0, 0), gone=True)
    L["recent_l"] = card(V(rh(16), last_row(True), Sp(), rec_dest(0), rec_dest(1), rec_dest(2), Sp(),
                           Hz(pill("اطلبها مرة أخرى", h=38, size=13), pill("كل الرحلات", id_="tw_btn2", style="tw_pill_glass", arrow=False, h=38, size=13, m=(8, 0, 0, 0)), w="m", id="tw_btns", m=(0, 10, 0, 0), gone=True),
                           rec_empty(), w="m", h="m", pad=(16, 16, 16, 16)))

    # ── العروض والخصومات
    off_txt = lambda s: V(T("tw_title", "العروض والخصومات", size=s, bold=True, lines=2), T("tw_sub", "عروضٌ مميّزة لك", size=12, color="tw_mut", lines=2, m=(0, 5, 0, 0)),
                          Sp(), pill("مشاهدة العروض", style="tw_pill_glass", h=34, size=12.5), weight=1.25, h="m")
    L["offers_s"] = card(I("tw_art", "tw_il_percent", w=64, h=64, lg="tl", m=(0, 6, 4, 0)),
                         V(Sp(), T("tw_big", "", size=26, bold=True, ltr=True, gone=True), T("tw_title", "العروض والخصومات", size=13.5, bold=True, lines=2),
                           T("tw_sub", "عروضٌ مميّزة لك", size=11, color="tw_mut", lines=2, m=(0, 3, 0, 0)), w="m", h="m", pad=(12, 12, 12, 12)))
    L["offers_m"] = card(Hz(off_txt(15), I("tw_art", "tw_il_percent", weight=0.85, h="m", m=(4, 4, 0, 4)), w="m", h="m", pad=(15, 14, 10, 14)))
    L["offers_l"] = card(V(I("tw_art", "tw_il_percent", w="m", weight=1, m=(0, 0, 0, 8)), T("tw_title", "العروض والخصومات", size=17, bold=True),
                           T("tw_big", "", size=32, bold=True, ltr=True, gone=True, m=(0, 4, 0, 0)), T("tw_sub", "عروضٌ مميّزة لك", size=12.5, color="tw_mut", lines=2, m=(0, 4, 0, 12)),
                           pill("مشاهدة العروض", h=40, size=14, full=True), w="m", h="m", pad=(16, 16, 16, 16)))

    # ── أقرب سائق متاح
    arrow_btn = lambda s: I("tw_btn", "tw_v_arrow_on", w=s, h=s, ipad=int(s * 0.28), bg="tw_circle", desc="اطلب الآن")
    near_txt = lambda big: V(T("tw_title", "أقرب سائق متاح", size=17 if big else 16, bold=True, lines=2),
                             Hz(T("tw_big", "", size=15, bold=True, ltr=True), T("tw_unit", "", size=12.5, color="tw_mut", m=(4, 0, 0, 0)), id="tw_bigrow", g="b", m=(0, 6, 0, 0), gone=True),
                             T("tw_sub", "افتح التطبيق لنعرف أقربَ سائقٍ إليك", size=12, color="tw_mut", lines=2, m=(0, 5, 0, 0)), Sp(), arrow_btn(42), weight=1, h="m", pad=(16, 15, 4, 14))
    L["nearest_s"] = card(*scene_car(car_m=(4, 0, 4, 6)),
                          V(T("tw_title", "أقرب سائق متاح", size=14, bold=True, lines=2), Hz(T("tw_big", "", size=20, bold=True, ltr=True),
                                                                                             T("tw_unit", "", size=11.5, color="tw_mut", m=(4, 0, 0, 0)), id="tw_bigrow", g="b", m=(0, 4, 0, 0), gone=True),
                            T("tw_sub", "افتح التطبيق لنعرف", size=11, color="tw_mut", lines=2, m=(0, 3, 0, 0)), pad=(13, 13, 13, 0)))
    L["nearest_m"] = card(Hz(near_txt(False), F(*scene_car(car_m=(0, 10, 6, 8)), weight=1.15, h="m"), w="m", h="m"))
    L["nearest_l"] = card(V(F(*scene_car(car_m=(10, 6, 10, 0)), w="m", weight=1),
                            V(T("tw_title", "أقرب سائق متاح", size=18, bold=True), Hz(T("tw_big", "", size=17, bold=True, ltr=True), T("tw_unit", "", size=13, color="tw_mut", m=(4, 0, 0, 0)),
                                                                                       id="tw_bigrow", g="b", m=(0, 6, 0, 0), gone=True),
                              T("tw_sub", "افتح التطبيق لنعرف أقربَ سائقٍ إليك", size=12.5, color="tw_mut", lines=2, m=(0, 5, 0, 12)),
                              pill("اطلب الآن", h=40, size=14, full=True), w="m", pad=(16, 4, 16, 16)), w="m", h="m"))
    return L


# ═══════════════════════════ ودجاتُ الكبتن ═══════════════════════════
def driver_layouts():
    L = {}
    amount = lambda s, color="tw_tx": Hz(T("tw_big", "", size=s, bold=True, ltr=True, color=color), T("tw_unit", "", size=13, color="tw_mut", m=(6, 0, 0, 2)), id="tw_bigrow", g="b")
    status_head = lambda s: header("غير متّصل", None, size=s, dot="tw_dot_off")
    power = lambda s: I("tw_btn", "tw_v_power_on", w=s, h=s, ipad=int(s * 0.27), bg="tw_circle", desc="الاتّصال")
    L["status_s"] = card(V(status_head(15), T("tw_sub", "أرباحُ اليوم تظهر بعد فتح التطبيق", size=11, color="tw_mut", lines=2, m=(0, 5, 0, 0)), amount(22),
                           F(power(64), w="m", weight=1, g="c"), w="m", h="m", pad=(12, 12, 12, 12)))
    L["status_m"] = card(Hz(V(status_head(17), Sp(), amount(28), T("tw_sub", "أرباحُ اليوم تظهر بعد فتح التطبيق", size=11.5, color="tw_mut", lines=2, m=(0, 4, 0, 0)), Sp(),
                              pill("اتّصل الآن", h=36, size=13), weight=1.2, h="m"),
                            F(*scene_car(car_m=(0, 0, 0, 0)), weight=1, h="m"), w="m", h="m", pad=(15, 14, 8, 14)))
    L["status_l"] = card(V(status_head(18), F(*scene_car(car_m=(10, 6, 10, 6)), w="m", weight=1, m=(0, 10, 0, 10)), amount(32),
                           T("tw_sub", "أرباحُ اليوم تظهر بعد فتح التطبيق", size=12, color="tw_mut", lines=2, m=(0, 4, 0, 12)),
                           pill("اتّصل الآن", h=40, size=14, full=True), w="m", h="m", pad=(16, 16, 16, 16)))
    ring_box = lambda s, big: F(Ring(size=s, lg="c"), V(I(None, "tw_g_flag", w=22 if not big else 28, h=22 if not big else 28),
                                                        T("tw_ring_t", "", size=18 if not big else 26, bold=True, ltr=True, m=(0, 2, 0, 0)), w="w", lg="c", g="ch"), w=s, h=s)
    gh = lambda s: header("هدفي اليوميّ", "tw_g_flag", size=s)
    L["goal_s"] = card(V(gh(13), F(ring_box(104, False), w="m", weight=1, g="c"), T("tw_sub", "حدّد هدفَك من إعدادات الفقاعة", size=11, color="tw_mut", lines=2, center=True, w="m"),
                         w="m", h="m", pad=(12, 12, 12, 12)))
    L["goal_m"] = card(Hz(ring_box(112, False), V(gh(15), Sp(), T("tw_big", "", size=22, bold=True, ltr=True),
                                                  T("tw_sub", "حدّد هدفَك اليوميَّ من إعدادات الفقاعة", size=12, color="tw_mut", lines=2, m=(0, 4, 0, 0)), Sp(), weight=1, h="m", m=(14, 0, 0, 0)),
                          w="m", h="m", g="cv", pad=(16, 14, 14, 14)))
    L["goal_l"] = card(V(gh(16), F(ring_box(160, True), w="m", weight=1, g="c"), T("tw_big", "", size=22, bold=True, ltr=True, center=True, w="m"),
                         T("tw_sub", "حدّد هدفَك اليوميَّ من إعدادات الفقاعة", size=12.5, color="tw_mut", lines=2, center=True, w="m", m=(0, 4, 0, 0)), w="m", h="m", pad=(16, 16, 16, 16)))
    sh = lambda s: header("اشتراكي", "tw_g_receipt_long", size=s)
    days = lambda s: Hz(T("tw_big", "", size=s, bold=True, ltr=True), T("tw_unit", "", size=13, color="tw_mut", m=(6, 0, 0, 2)), id="tw_bigrow", g="b")
    L["subscription_s"] = card(I("tw_art", "tw_il_calendar", w=60, h=60, lg="tl", m=(0, 6, 4, 0)),
                               V(sh(13.5), Sp(), days(28), T("tw_sub", "يظهر هنا ما بقي من اشتراكك", size=11, color="tw_mut", lines=2, m=(0, 2, 0, 0)),
                                 Bar(w="m", h=6, m=(0, 8, 0, 0)), w="m", h="m", pad=(12, 12, 12, 12)))
    L["subscription_m"] = card(Hz(V(sh(14.5), Sp(), days(32), T("tw_sub", "يظهر هنا ما بقي من اشتراكك", size=11.5, color="tw_mut", lines=2, m=(0, 3, 0, 0)),
                                    Bar(w="m", h=6, m=(0, 8, 0, 0)), pill("جدّد الاشتراك", h=34, size=12.5, m=(0, 10, 0, 0), gone=True), weight=1.25, h="m"),
                                  I("tw_art", "tw_il_calendar", weight=0.9, h="m", m=(4, 4, 0, 4)), w="m", h="m", pad=(14, 13, 10, 13)))
    L["subscription_l"] = card(V(sh(16), I("tw_art", "tw_il_calendar", w="m", weight=1, m=(0, 8, 0, 8)), days(36),
                                 T("tw_sub", "يظهر هنا ما بقي من اشتراكك", size=12, color="tw_mut", lines=2, m=(0, 3, 0, 0)), Bar(w="m", h=6, m=(0, 10, 0, 0)),
                                 pill("جدّد الاشتراك", h=40, size=14, full=True, m=(0, 12, 0, 0), gone=True), w="m", h="m", pad=(16, 16, 16, 16)))
    bh = lambda s: header("أقرب منطقة مزدحمة", "tw_g_my_location", size=s)
    L["busy_s"] = card(I("tw_art", "tw_il_pin", w=58, h=58, lg="tl", m=(0, 6, 4, 0)),
                       V(T("tw_title", "أقرب منطقة مزدحمة", size=13.5, bold=True, lines=2, m=(0, 0, 54, 0)), Sp(), T("tw_sub", "اتّصل لترى أين الطلبُ الآن", size=11.5, color="tw_mut", lines=3),
                         pill("اذهب", h=32, size=12.5, full=True, m=(0, 8, 0, 0)), w="m", h="m", pad=(12, 12, 12, 12)))
    L["busy_m"] = card(Hz(V(bh(14.5), T("tw_sub", "اتّصل لترى أين الطلبُ الآن", size=12.5, color="tw_mut", lines=3, m=(0, 8, 0, 0)), Sp(),
                            pill("اذهب إليها", icon="tw_v_nav_on", arrow=False, h=36, size=13), weight=1.25, h="m"),
                          I("tw_art", "tw_il_pin", weight=0.8, h="m", m=(4, 6, 0, 6)), w="m", h="m", pad=(14, 13, 10, 13)))
    L["busy_l"] = card(V(bh(16), I("tw_art", "tw_il_pin", w="m", weight=1, m=(0, 8, 0, 8)), T("tw_sub", "اتّصل لترى أين الطلبُ الآن", size=13, color="tw_mut", lines=3, m=(0, 0, 0, 12)),
                         pill("اذهب إليها", icon="tw_v_nav_on", arrow=False, h=40, size=14, full=True), w="m", h="m", pad=(16, 16, 16, 16)))
    rh = lambda s: header("رحلتي الحالية", None, size=s, dot="tw_dot_ok")
    L["ride_s"] = card(V(rh(13.5), T("tw_sub", "لا رحلة الآن", size=12, color="tw_mut", lines=2, m=(0, 6, 0, 0)), F(I("tw_car", "tw_car_economy", w="m", h="m", scale="fitEnd"), w="m", weight=1),
                         pill("افتح الرحلة", h=32, size=12.5, full=True, m=(0, 6, 0, 0), gone=True), w="m", h="m", pad=(12, 12, 12, 12)))
    L["ride_m"] = card(Hz(V(rh(15), T("tw_sub", "لا رحلة الآن", size=12.5, color="tw_mut", lines=2, m=(0, 8, 0, 0)), Sp(), pill("افتح الرحلة", h=36, size=13, gone=True), weight=1.2, h="m"),
                          F(*scene_car(car_m=(0, 0, 0, 0)), weight=1, h="m"), w="m", h="m", pad=(15, 14, 8, 14)))
    L["ride_l"] = card(V(rh(16), F(*scene_car(car_m=(10, 6, 10, 6)), w="m", weight=1, m=(0, 10, 0, 10)), T("tw_sub", "لا رحلة الآن", size=13, color="tw_mut", lines=2, m=(0, 0, 0, 12)),
                         pill("افتح الرحلة", h=40, size=14, full=True, gone=True), w="m", h="m", pad=(16, 16, 16, 16)))
    return L


LAYOUTS = rider_layouts() if ROLE_APP == "rider" else driver_layouts()
for old in (RES / "layout").glob("tw_*.xml"):
    if old.name not in ("tw_signed_out.xml",):
        old.unlink()
# رسومُ النسخة الأولى (٢٠/١١) — لا يقرؤها شيء، وبعضُها يشير إلى لونٍ لم يعد موجوداً فيُسقط البناء
for legacy in ("tw_bg", "tw_btn", "tw_btn2"):
    (RES / "drawable" / f"{legacy}.xml").unlink(missing_ok=True)
for name, node in LAYOUTS.items():
    write(f"layout/tw_{name}.xml", H + f"<!-- **ودجةُ TAXO «{name}»** — {GEN} -->\n" + to_xml(node, depth=0, root=True) + "\n")

# بطاقةُ «قبل الدخول/المفتاح مطفأ» — بالأسلوب الجديد، والمعرّفاتُ نفسُها التي يملؤها `WidgetSignedOut`
def tvx(id_, size, color="@color/tw_tx", bold=False, extra=""):
    return (f'<TextView android:id="@+id/{id_}" android:layout_width="wrap_content" android:layout_height="wrap_content" '
            f'android:textColor="{color}" android:textSize="{size}sp"{" android:textStyle=\"bold\"" if bold else ""} android:includeFontPadding="false" {extra}/>')


write("layout/tw_signed_out.xml", H + f'''<!-- **قبل الدخول** في ودجات TAXO — يملؤها `WidgetSignedOut` (العلامة وسطرٌ وزرّ). {GEN} -->
<FrameLayout {A} android:id="@+id/tw_root" android:layout_width="match_parent" android:layout_height="match_parent" android:layoutDirection="rtl" android:background="@drawable/tw_card" android:clipToOutline="true">
<LinearLayout
    android:id="@+id/wo_root" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical"
    android:gravity="center" android:padding="12dp">
    <LinearLayout android:id="@+id/wo_col" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:gravity="center_horizontal">
        <ImageView android:layout_width="wrap_content" android:layout_height="22dp" android:adjustViewBounds="true" android:src="@drawable/tw_wordmark" android:contentDescription="TAXO" />
        {tvx("wo_mark", 1, extra='android:visibility="gone"')}
        {tvx("wo_line", 13, "@color/tw_mut", extra='android:layout_marginTop="8dp" android:gravity="center" android:maxLines="2" android:ellipsize="end"')}
        {tvx("wo_btn", 14, "@color/tw_on", True, 'android:layout_marginTop="12dp" android:minWidth="150dp" android:minHeight="38dp" android:gravity="center" android:paddingStart="20dp" android:paddingEnd="20dp" android:background="@drawable/tw_pill"')}
    </LinearLayout>
    <LinearLayout android:id="@+id/wo_row" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:gravity="center_vertical">
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:orientation="vertical">
            <ImageView android:layout_width="wrap_content" android:layout_height="16dp" android:adjustViewBounds="true" android:src="@drawable/tw_wordmark" android:contentDescription="TAXO" />
            {tvx("wo_mark2", 1, extra='android:visibility="gone"')}
            {tvx("wo_line2", 12, "@color/tw_mut", extra='android:layout_marginTop="5dp" android:maxLines="2" android:ellipsize="end"')}
        </LinearLayout>
        {tvx("wo_btn2", 13.5, "@color/tw_on", True, 'android:minHeight="36dp" android:gravity="center" android:paddingStart="14dp" android:paddingEnd="14dp" android:background="@drawable/tw_pill"')}
    </LinearLayout>
</LinearLayout>
</FrameLayout>
''')

# ═══════════════════════════ ملفّاتُ المزوّدات: معاينةٌ حيّةٌ هي التخطيطُ نفسُه ═══════════════════════════
KINDS = ([("request", 4, 2), ("on_the_way", 4, 2), ("quick", 2, 2), ("favorites", 4, 2), ("wallet", 4, 2), ("discount", 4, 2), ("schedule", 4, 2),
          ("services", 4, 2), ("current", 4, 2), ("home", 2, 2), ("work", 2, 2), ("points", 2, 2), ("recent", 4, 2), ("offers", 4, 2), ("nearest", 4, 2)]
         if ROLE_APP == "rider" else [("status", 4, 2), ("goal", 2, 2), ("subscription", 4, 2), ("busy", 4, 2), ("ride", 4, 2)])
for kind, cw, ch in KINDS:
    info = APP / f"android/app/src/main/res/xml/tw_info_{kind}.xml"
    old = info.read_text(encoding="utf-8")
    desc = re.search(r'android:description="([^"]+)"', old).group(1)
    size = "m" if cw == 4 else "s"
    write(f"xml/tw_info_{kind}.xml", H + f'''<!-- **ودجةُ «{kind}»** — المعاينةُ في المنتقي هي التخطيطُ نفسُه (`previewLayout`، أندرويد ١٢+)، والصورةُ لما قبله. {GEN} -->
<appwidget-provider xmlns:android="http://schemas.android.com/apk/res/android"
    android:minWidth="{110 if cw == 2 else 250}dp"
    android:minHeight="110dp"
    android:minResizeWidth="110dp"
    android:minResizeHeight="110dp"
    android:maxResizeWidth="530dp"
    android:maxResizeHeight="530dp"
    android:targetCellWidth="{cw}"
    android:targetCellHeight="{ch}"
    android:updatePeriodMillis="0"
    android:initialLayout="@layout/tw_{kind}_{size}"
    android:previewLayout="@layout/tw_{kind}_{size}"
    android:previewImage="@drawable/tw_prev_{kind}"
    android:resizeMode="horizontal|vertical"
    android:widgetCategory="home_screen"
    android:description="{desc}" />
''')

# جدولُ التخطيطات لجافا — النوعُ والحجمُ إلى مورد
cls = "\n".join(f'            case "{k}": return size == 2 ? R.layout.tw_{k}_l : size == 1 ? R.layout.tw_{k}_m : R.layout.tw_{k}_s;' for k, _, _ in KINDS)
(APP / f"android/app/src/main/java/{PKG.replace('.', '/')}/TwLayouts.java").write_text(f'''package {PKG};

/** تخطيطُ كلِّ ودجةٍ بحجمها — {GEN} */
final class TwLayouts {{
    private TwLayouts() {{}}

    static int of(String kind, int size) {{
        switch (kind) {{
{cls}
            default: return R.layout.tw_signed_out;
        }}
    }}
}}
''', encoding="utf-8", newline="\n")

# ═══════════════════════════ المعاينةُ HTML ═══════════════════════════
if PREVIEW:
    import base64
    PREVIEW.mkdir(parents=True, exist_ok=True)
    cache = {}

    def img_uri(theme):
        def f(name):
            key = (name, theme)
            if key in cache: return cache[key]
            p = None
            for folder in ((f"drawable-night-nodpi", "drawable-nodpi") if theme == "night" else ("drawable-nodpi",)):
                for ext in ("webp", "png"):
                    q = RES / folder / f"{name}.{ext}"
                    if q.exists() and p is None: p = q
            if p is None and name.startswith("data:"): return name
            if name == "tw_fade":
                th = NIGHT if theme == "night" else DAY
                c1 = hex2css((NIGHT if theme == "night" else DAY)["tw_fade"])
                svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="none"><defs>'
                       f'<linearGradient id="a" x1="1" x2="0"><stop offset="0" stop-color="{c1}"/><stop offset=".45" stop-color="{c1}" stop-opacity="0"/></linearGradient>'
                       f'<linearGradient id="b" y1="0" y2="1" x1="0" x2="0"><stop offset="0" stop-color="{c1}"/><stop offset=".4" stop-color="{c1}" stop-opacity="0"/></linearGradient>'
                       f'<linearGradient id="c" x1="0" x2="1"><stop offset="0" stop-color="{c1}"/><stop offset=".18" stop-color="{c1}" stop-opacity="0"/></linearGradient></defs>'
                       f'<rect width="100" height="100" fill="url(#a)"/><rect width="100" height="100" fill="url(#b)"/><rect width="100" height="100" fill="url(#c)"/></svg>')
                cache[key] = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
                return cache[key]
            if p is not None:
                cache[key] = f"data:image/{p.suffix[1:]};base64," + base64.b64encode(p.read_bytes()).decode()
                return cache[key]
            vx = RES / "drawable" / f"{name}.xml"
            if vx.exists():
                t = vx.read_text(encoding="utf-8")
                th = NIGHT if theme == "night" else DAY
                th = NIGHT if theme == "night" else DAY
                if "<vector" not in t:  # شكلٌ بيضيٌّ (نقطة الحال أو إطارُ الصورة)
                    colm = re.search(r'android:color="@color/([a-z_0-9]+)"', t)
                    col = hex2css(th[colm.group(1)]) if colm else "#000"
                    body = (f'<circle cx="12" cy="12" r="11" fill="none" stroke="{col}" stroke-width="1.6"/>' if "stroke" in t else f'<circle cx="12" cy="12" r="12" fill="{col}"/>')
                    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{body}</svg>'
                    cache[key] = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
                    return cache[key]
                vb = re.search(r'viewportWidth="([\d.]+)"', t).group(1)
                paths = []
                for g in re.finditer(r'(<group android:translateX="([-\d.]+)" android:translateY="([-\d.]+)">)?<path android:fillColor="([^"]+)" android:pathData="([^"]+)" />', t):
                    col = g.group(4)
                    if col.startswith("@color/"): col = th[col[7:]]
                    css = hex2css(col)
                    pth = f'<path fill="{css}" d="{g.group(5)}"/>'
                    if g.group(1): pth = f'<g transform="translate({g.group(2)} {g.group(3)})">{pth}</g>'
                    paths.append(pth)
                svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb} {vb}">' + "".join(paths) + "</svg>"
                cache[key] = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
                return cache[key]
            return ""
        return f

    SIZES = {"s": (165, 165), "m": (345, 165), "l": (345, 330)}
    SAMPLE = json.loads((ASSETS / f"preview-{ROLE_APP}.json").read_text(encoding="utf-8")) if (ASSETS / f"preview-{ROLE_APP}.json").exists() else {}
    # «-plain»: بلا قيمِ المعاينة — نصوصُ التخطيط الافتراضيّةُ نفسُها، ومنها تُصوَّر صورُ المنتقي لما قبل أندرويد ١٢ (tw_prev_*)
    for (suffix, sample), theme in [(x, t) for x in (("", SAMPLE), ("-plain", {})) for t in ("day", "night")]:
        th = NIGHT if theme == "night" else DAY
        bg = "#E9E6E3" if theme == "day" else "#08090B"
        cells = []
        for kind, _, _ in KINDS:
            row = []
            for sz in ("s", "m", "l"):
                node = LAYOUTS[f"{kind}_{sz}"]
                d = dict(sample.get(kind, {}))
                d["__gone__"] = set(d.pop("gone", []))
                d["__show__"] = set(d.pop("show", []))
                for k in list(d):
                    if isinstance(d[k], str) and d[k].startswith("@"): d[k] = d[k][1:]
                w, h = SIZES[sz]
                row.append(f'<div style="width:{w}px;height:{h}px;position:relative;flex-shrink:0">{to_html(node, th, img_uri(theme), d)}</div>')
            cells.append(f'<div class="k" data-kind="{kind}"><div class="n">{kind}</div><div class="r">{"".join(row)}</div></div>')
        page = f'''<!doctype html><html><head><meta charset="utf-8"><style>body{{margin:0;padding:24px;background:{bg};font-family:"Segoe UI","Noto Sans Arabic",Tahoma,sans-serif}}
.k{{margin-bottom:18px}}.n{{font:12px monospace;color:#888;margin-bottom:6px}}.r{{display:flex;gap:16px;align-items:flex-start}}</style></head><body>{"".join(cells)}</body></html>'''
        (PREVIEW / f"{ROLE_APP}{suffix}-{theme}.html").write_text(page, encoding="utf-8")
print("widgets v2 ok", ROLE_APP, len(LAYOUTS), "layouts")
