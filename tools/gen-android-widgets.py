# مولِّدُ ودجات TAXO (أمرُ المالك ٢٠/١١ الثامن) — موارد أندرويد المشتركة للتطبيقين: الألوان، والخلفيّات، ورسومُ النمط C متّجهةً،
# والتخطيطُ الواحد، وصورُ السيارات. ويُشغَّل: python3 gen_widgets.py <app-dir> <pkg> <studio-out>
import json, pathlib, re, shutil, sys

APP = pathlib.Path(sys.argv[1])
PKG = sys.argv[2]
OUT = pathlib.Path(sys.argv[3])
RES = APP / "android/app/src/main/res"
GLYPHS_TS = APP / "src/taxo2/glyphsC.ts"
H = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
A = 'xmlns:android="http://schemas.android.com/apk/res/android"'


def write(rel, text):
    p = RES / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


# ── الألوان: نهارٌ وليل
DAY = dict(tw_bg0="#FFFFFFFF", tw_bg1="#FFEEF0F3", tw_glow="#2EF05A28", tw_line="#14101828", tw_hi="#E6FFFFFF",
           tw_tx="#FF15171C", tw_mut="#FF636974", tw_acc="#FFF05A28", tw_acc2="#FFFF8A5C", tw_chip="#0B101828",
           tw_chip2="#14101828", tw_track="#17101828", tw_g_b="#FFF05A28", tw_g_k="#FFFFB595", tw_g_d="#FFB8401A",
           tw_g_c="#FFFFFFFF", tw_g_g="#1F1F2433", tw_on="#FFFFFFFF", tw_ok="#FF1FBF75", tw_women="#FF9C2C6E")
NIGHT = dict(tw_bg0="#FF262931", tw_bg1="#FF101216", tw_glow="#47FF6A33", tw_line="#17FFFFFF", tw_hi="#1FFFFFFF",
             tw_tx="#FFF5F6F8", tw_mut="#FFA5ABB5", tw_acc="#FFFF6A33", tw_acc2="#FFFF8A5C", tw_chip="#12FFFFFF",
             tw_chip2="#21FFFFFF", tw_track="#1FFFFFFF", tw_g_b="#FFF05A28", tw_g_k="#FF8F2F10", tw_g_d="#FFB8401A",
             tw_g_c="#FF1B1E24", tw_g_g="#73000000", tw_on="#FFFFFFFF", tw_ok="#FF3DBE7E", tw_women="#FFF08CC0")
for folder, table in (("values", DAY), ("values-night", NIGHT)):
    rows = "\n".join(f'    <color name="{k}">{v}</color>' for k, v in table.items())
    write(f"{folder}/tw_colors.xml", H + "<!-- **ودجاتُ TAXO** (أمرُ المالك ٢٠/١١ الثامن) — نهارٌ نظيفٌ وليلٌ برتقاليٌّ على داكن. مولَّد. -->\n<resources>\n" + rows + "\n</resources>\n")

# ── الخلفيّات: زجاجٌ مقلَّدٌ بالتدرّجات والطبقات — **بلا blur** (البطارية وNote 20)
write("drawable/tw_bg.xml", H + f'''<layer-list {A}>
    <item><shape android:shape="rectangle"><gradient android:angle="315" android:startColor="@color/tw_bg0" android:endColor="@color/tw_bg1" /><corners android:radius="26dp" /></shape></item>
    <item><shape android:shape="rectangle"><gradient android:type="radial" android:gradientRadius="220dp" android:centerX="1.0" android:centerY="0.0" android:startColor="@color/tw_glow" android:endColor="#00000000" /><corners android:radius="26dp" /></shape></item>
    <item android:gravity="top" android:height="44dp"><shape android:shape="rectangle"><gradient android:angle="270" android:startColor="@color/tw_hi" android:endColor="#00FFFFFF" /><corners android:topLeftRadius="26dp" android:topRightRadius="26dp" /></shape></item>
    <item><shape android:shape="rectangle"><stroke android:width="1dp" android:color="@color/tw_line" /><corners android:radius="26dp" /></shape></item>
</layer-list>
''')
write("drawable/tw_btn.xml", H + f'<shape {A} android:shape="rectangle"><gradient android:angle="270" android:startColor="@color/tw_acc2" android:endColor="@color/tw_acc" /><corners android:radius="99dp" /></shape>\n')
write("drawable/tw_btn2.xml", H + f'<shape {A} android:shape="rectangle"><solid android:color="@color/tw_chip2" /><corners android:radius="99dp" /></shape>\n')
write("drawable/tw_chip.xml", H + f'<shape {A} android:shape="rectangle"><solid android:color="@color/tw_chip" /><stroke android:width="1dp" android:color="@color/tw_line" /><corners android:radius="16dp" /></shape>\n')
write("drawable/tw_circle.xml", H + f'<shape {A} android:shape="oval"><gradient android:angle="270" android:startColor="@color/tw_acc2" android:endColor="@color/tw_acc" /></shape>\n')
write("drawable/tw_dot.xml", H + f'<shape {A} android:shape="oval"><solid android:color="@color/tw_acc" /><size android:width="8dp" android:height="8dp" /></shape>\n')
write("drawable/tw_dot_ok.xml", H + f'<shape {A} android:shape="oval"><solid android:color="@color/tw_ok" /><size android:width="8dp" android:height="8dp" /></shape>\n')
write("drawable/tw_bar.xml", H + f'''<layer-list {A}>
    <item android:id="@android:id/background"><shape android:shape="rectangle"><solid android:color="@color/tw_track" /><corners android:radius="4dp" /></shape></item>
    <item android:id="@android:id/progress"><clip><shape android:shape="rectangle"><gradient android:angle="0" android:startColor="@color/tw_acc" android:endColor="@color/tw_acc2" /><corners android:radius="4dp" /></shape></clip></item>
</layer-list>
''')
write("drawable/tw_ring.xml", H + f'''<layer-list {A}>
    <item android:id="@android:id/background"><shape android:shape="ring" android:innerRadiusRatio="2.6" android:thicknessRatio="13" android:useLevel="false"><solid android:color="@color/tw_track" /></shape></item>
    <item android:id="@android:id/progress"><rotate android:fromDegrees="270" android:toDegrees="270" android:pivotX="50%" android:pivotY="50%"><shape android:shape="ring" android:innerRadiusRatio="2.6" android:thicknessRatio="13" android:useLevel="true"><gradient android:type="sweep" android:startColor="@color/tw_acc2" android:endColor="@color/tw_acc" /></shape></rotate></item>
</layer-list>
''')

# ── رسومُ النمط C متّجهةً — من `glyphsC.ts` نفسِه (المصدرُ الواحد)، ومعها الحقيبةُ والطائرة
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

# ── صورُ السيارات: نهارٌ وليلٌ بالاسم نفسِه (`drawable-nodpi` و`drawable-night-nodpi`)
for key in ["economy", "comfort", "vip", "hatchback", "suv", "family", "van", "city_taxi", "women"]:
    for folder, theme in (("drawable-nodpi", "day"), ("drawable-night-nodpi", "night")):
        (RES / folder).mkdir(parents=True, exist_ok=True)
        shutil.copy(OUT / f"{key}-34-{theme}-320.webp", RES / folder / f"tw_car_{key}.webp")

# ── التخطيطُ الواحدُ لكلِّ الودجات — الأنواعُ تُظهر وتُخفي ما تحتاج (`TaxoWidgets.java`)
def tv(id_, size, color="@color/tw_tx", bold=False, extra=""):
    return (f'<TextView android:id="@+id/{id_}" android:layout_width="wrap_content" android:layout_height="wrap_content" '
            f'android:textColor="{color}" android:textSize="{size}sp"{" android:textStyle=\"bold\"" if bold else ""} android:includeFontPadding="false" {extra}/>')


tiles = "\n".join(f'''            <LinearLayout android:id="@+id/tw_t{i}" android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1" {'android:layout_marginStart="6dp" ' if i else ''}android:orientation="vertical" android:gravity="center" android:background="@drawable/tw_chip" android:visibility="gone">
                <ImageView android:id="@+id/tw_t{i}i" android:layout_width="28dp" android:layout_height="28dp" android:importantForAccessibility="no" />
                {tv(f"tw_t{i}l", 12, bold=True, extra='android:layout_marginTop="4dp" android:maxLines="1" android:ellipsize="end"')}
            </LinearLayout>''' for i in range(4))

write("layout/tw_widget.xml", H + f'''<!-- **ودجاتُ TAXO** (أمرُ المالك ٢٠/١١ الثامن) — تخطيطٌ واحدٌ لكلِّ الأنواع، والنوعُ يُظهر ما يحتاجه. **لا رحلةَ من الودجة**:
     كلُّ زرٍّ يفتح التطبيق، والراكبُ يؤكّد في ورقة الطلب. نهارٌ وليلٌ من values/values-night، **وزجاجٌ بالتدرّجات بلا blur**. مولَّد. -->
<FrameLayout {A}
    android:id="@+id/tw_root"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:layoutDirection="rtl"
    android:background="@drawable/tw_bg">

    <ImageView android:id="@+id/tw_car" android:layout_width="176dp" android:layout_height="110dp" android:layout_gravity="bottom|left"
        android:layout_marginLeft="-6dp" android:scaleType="fitCenter" android:visibility="gone" android:importantForAccessibility="no" />
    <ImageView android:id="@+id/tw_car_s" android:layout_width="124dp" android:layout_height="78dp" android:layout_gravity="bottom|left"
        android:layout_marginLeft="4dp" android:layout_marginBottom="26dp" android:scaleType="fitCenter" android:visibility="gone" android:importantForAccessibility="no" />
    <ImageView android:id="@+id/tw_art" android:layout_width="92dp" android:layout_height="92dp" android:layout_gravity="center_vertical|left"
        android:layout_marginLeft="22dp" android:visibility="gone" android:importantForAccessibility="no" />

    <LinearLayout android:id="@+id/tw_body" android:layout_width="match_parent" android:layout_height="match_parent"
        android:orientation="vertical" android:paddingStart="16dp" android:paddingEnd="16dp" android:paddingTop="14dp" android:paddingBottom="14dp">
        <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:gravity="center_vertical">
            <ImageView android:id="@+id/tw_dot" android:layout_width="8dp" android:layout_height="8dp" android:layout_marginEnd="7dp" android:src="@drawable/tw_dot" android:visibility="gone" android:importantForAccessibility="no" />
            {tv("tw_mark", 17, bold=True, extra='android:letterSpacing="0.06" android:visibility="gone" android:text="TAXO"')}
            {tv("tw_title", 15, bold=True, extra='android:maxLines="1" android:ellipsize="end"')}
            <FrameLayout android:layout_width="0dp" android:layout_height="1dp" android:layout_weight="1" />
            <ImageView android:id="@+id/tw_icon" android:layout_width="22dp" android:layout_height="22dp" android:visibility="gone" android:importantForAccessibility="no" />
        </LinearLayout>
        <LinearLayout android:id="@+id/tw_bigrow" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="8dp"
            android:orientation="horizontal" android:gravity="bottom" android:visibility="gone">
            {tv("tw_big", 32, bold=True, extra='android:textDirection="ltr"')}
            {tv("tw_unit", 13, "@color/tw_mut", extra='android:layout_marginStart="6dp" android:layout_marginBottom="3dp"')}
        </LinearLayout>
        {tv("tw_sub", 12.5, "@color/tw_mut", extra='android:layout_marginTop="4dp" android:maxLines="2" android:ellipsize="end" android:visibility="gone"')}
        <LinearLayout android:id="@+id/tw_tiles" android:layout_width="match_parent" android:layout_height="0dp" android:layout_weight="1"
            android:layout_marginTop="10dp" android:orientation="horizontal" android:visibility="gone">
{tiles}
        </LinearLayout>
        <FrameLayout android:id="@+id/tw_fill" android:layout_width="1dp" android:layout_height="0dp" android:layout_weight="1" />
        <LinearLayout android:id="@+id/tw_actions" android:layout_width="wrap_content" android:layout_height="wrap_content" android:orientation="horizontal" android:visibility="gone">
            {tv("tw_btn", 14, "@color/tw_on", True, 'android:minHeight="36dp" android:gravity="center" android:paddingStart="16dp" android:paddingEnd="16dp" android:background="@drawable/tw_btn" android:visibility="gone"')}
            {tv("tw_btn2", 13.5, "@color/tw_tx", True, 'android:minHeight="34dp" android:gravity="center" android:paddingStart="14dp" android:paddingEnd="14dp" android:layout_marginStart="8dp" android:background="@drawable/tw_btn2" android:visibility="gone"')}
        </LinearLayout>
        <ProgressBar android:id="@+id/tw_bar" style="?android:attr/progressBarStyleHorizontal" android:layout_width="match_parent" android:layout_height="6dp"
            android:layout_marginTop="10dp" android:max="100" android:progressDrawable="@drawable/tw_bar" android:visibility="gone" />
    </LinearLayout>

    <FrameLayout android:id="@+id/tw_ringbox" android:layout_width="132dp" android:layout_height="132dp" android:layout_gravity="center" android:visibility="gone">
        <ProgressBar android:id="@+id/tw_ring" style="?android:attr/progressBarStyleHorizontal" android:layout_width="match_parent" android:layout_height="match_parent"
            android:max="100" android:progressDrawable="@drawable/tw_ring" />
        <LinearLayout android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_gravity="center" android:orientation="vertical" android:gravity="center_horizontal">
            <ImageView android:id="@+id/tw_ring_icon" android:layout_width="20dp" android:layout_height="20dp" android:src="@drawable/tw_g_star" android:importantForAccessibility="no" />
            {tv("tw_ring_big", 26, bold=True, extra='android:textDirection="ltr"')}
            {tv("tw_ring_sub", 11, "@color/tw_mut")}
        </LinearLayout>
    </FrameLayout>

    <LinearLayout android:id="@+id/tw_quick" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical"
        android:gravity="center_horizontal" android:paddingTop="14dp" android:visibility="gone">
        {tv("tw_qmark", 17, bold=True, extra='android:letterSpacing="0.06" android:text="TAXO"')}
        {tv("tw_qtitle", 14, bold=True, extra='android:layout_marginTop="4dp" android:text="طلب سريع"')}
        <ImageView android:id="@+id/tw_qbtn" android:layout_width="76dp" android:layout_height="76dp" android:layout_marginTop="10dp" android:padding="14dp"
            android:background="@drawable/tw_circle" android:src="@drawable/tw_g_local_taxi_on" android:contentDescription="اطلب رحلة" />
    </LinearLayout>

    <LinearLayout android:id="@+id/tw_place" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical"
        android:gravity="center" android:visibility="gone">
        <ImageView android:id="@+id/tw_place_icon" android:layout_width="64dp" android:layout_height="64dp" android:importantForAccessibility="no" />
        {tv("tw_place_name", 18, bold=True, extra='android:layout_marginTop="8dp"')}
        {tv("tw_place_sub", 12, "@color/tw_mut", extra='android:layout_marginTop="2dp"')}
    </LinearLayout>

    <include layout="@layout/tw_signed_out" />
</FrameLayout>
''')

# بطاقةُ «قبل الدخول» — المعرّفاتُ نفسُها التي يملؤها `WidgetSignedOut`
so = (APP / "android/app/src/main/res/layout/widget_rider_quick.xml") if PKG.endswith("rider") else None
write("layout/tw_signed_out.xml", H + f'''<!-- **قبل الدخول** في ودجات الأمر الثامن — البطاقةُ نفسُها التي يملؤها `WidgetSignedOut` (الشعار وسطرٌ وزرّ). مولَّد. -->
<LinearLayout {A}
    android:id="@+id/wo_root" android:layout_width="match_parent" android:layout_height="match_parent" android:orientation="vertical"
    android:gravity="center" android:padding="12dp" android:background="@drawable/tw_bg" android:visibility="gone">
    <LinearLayout android:id="@+id/wo_col" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:gravity="center_horizontal">
        <ImageView android:layout_width="44dp" android:layout_height="44dp" android:src="@mipmap/ic_launcher_round" android:contentDescription="TAXO" />
        {tv("wo_mark", 19, bold=True, extra='android:layout_marginTop="6dp" android:letterSpacing="0.08" android:text="TAXO"')}
        {tv("wo_line", 13, "@color/tw_mut", extra='android:layout_marginTop="2dp" android:gravity="center" android:maxLines="2" android:ellipsize="end"')}
        {tv("wo_btn", 15, "@color/tw_on", True, 'android:layout_marginTop="10dp" android:minWidth="160dp" android:minHeight="40dp" android:gravity="center" android:paddingStart="20dp" android:paddingEnd="20dp" android:background="@drawable/tw_btn"')}
    </LinearLayout>
    <LinearLayout android:id="@+id/wo_row" android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="horizontal" android:gravity="center_vertical">
        <ImageView android:layout_width="38dp" android:layout_height="38dp" android:src="@mipmap/ic_launcher_round" android:contentDescription="TAXO" />
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:layout_marginStart="10dp" android:orientation="vertical">
            {tv("wo_mark2", 16, bold=True, extra='android:letterSpacing="0.08" android:text="TAXO"')}
            {tv("wo_line2", 12, "@color/tw_mut", extra='android:maxLines="2" android:ellipsize="end"')}
        </LinearLayout>
        {tv("wo_btn2", 14, "@color/tw_on", True, 'android:minHeight="36dp" android:gravity="center" android:paddingStart="14dp" android:paddingEnd="14dp" android:background="@drawable/tw_btn"')}
    </LinearLayout>
</LinearLayout>
''')
print("resources ok", len(glyphs))
