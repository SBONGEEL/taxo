/** **أيقوناتُ الفقاعتين بالنمط C** (أمرُ المالك ٢٠/١١ الرابع) — يولّد `BubbleGlyphs.java` للتطبيقين من `set.mjs` نفسِه.
 *  الأدوارُ والألوانُ كما في `renderC`؛ وما لا شكلَ له في المجموعة بعدُ (الإيقاف، اللهب، الطريق، الحادث، الملاحة، الاستراحة، الطوارئ)
 *  مرسومٌ هنا على شبكة ٤٨ بالقواعد نفسِها. تشغيل: `node design/icons-c/bubble-glyphs.mjs` ثمّ يُودَع الناتجُ. */
import { writeFileSync } from "node:fs";
import { GLYPHS, VEHICLES } from "./set.mjs";

const P = (role, d) => ({ role, d });
const EXTRA = {
  power: [P("body", "M14.4 11.4l3.2 3.8a11.6 11.6 0 1 0 12.8 0l3.2-3.8a16.6 16.6 0 1 1-19.2 0z"), P("detail", "M21.5 4.5h5v19h-5z")],
  pause: [P("body", "M12 8h8.5v32H12zM27.5 8H36v32h-8.5z")],
  flame: [P("body", "M24 4c2.4 7.6 11.6 10.8 11.6 22.4a11.6 11.6 0 0 1-23.2 0c0-5.6 2.6-9 5.4-11.2 0 4.4 1.6 6.6 3.8 7.8C20.6 17.6 20 10.6 24 4z"), P("cut", "M24 27c2.4 2.2 4.4 3.6 4.4 6.6a4.4 4.4 0 0 1-8.8 0c0-2.4 1.8-4.4 4.4-6.6z")],
  road_closed: [P("body", "M5 15h38a3 3 0 0 1 3 3v9a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3v-9a3 3 0 0 1 3-3z"), P("cut", "M9 30l9-15h5l-9 15zM21 30l9-15h5l-9 15z"), P("detail", "M8 30h5v12H8zM35 30h5v12h-5z")],
  accident: [P("body", "M24 4.5c1.4 0 2.6.7 3.3 2l16.6 29c1.4 2.5-.4 5.5-3.3 5.5H7.4c-2.9 0-4.7-3-3.3-5.5l16.6-29c.7-1.3 1.9-2 3.3-2z"), P("cut", "M21.6 15h4.8l-.8 13h-3.2zM24 30.6a2.6 2.6 0 1 1 0 5.2 2.6 2.6 0 0 1 0-5.2z")],
  navigate: [P("body", "M24 4l15.5 37.5L24 33.6 8.5 41.5z"), P("detail", "M24 4v29.6l-15.5 7.9z")],
  sos: [P("body", "M24 4.5l16 6v11.4c0 10.4-6.8 18.6-16 21.6-9.2-3-16-11.2-16-21.6V10.5z"), P("cut", "M21.6 13h4.8l-.8 13.4h-3.2zM24 29.2a2.6 2.6 0 1 1 0 5.2 2.6 2.6 0 0 1 0-5.2z")],
  wrench: [P("body", "M30.6 5.2a10 10 0 0 0-11 13.2L6.4 31.6a4.6 4.6 0 0 0 6.5 6.5l13.2-13.2a10 10 0 0 0 13.2-11l-6 6-5.4-1.4-1.4-5.4z"), P("cut", "M10.2 33a2 2 0 1 1 0 4 2 2 0 0 1 0-4z")],
  timer: [P("body", "M24 9.5a16.5 16.5 0 1 1 0 33 16.5 16.5 0 0 1 0-33z"), P("detail", "M19 3.5h10v4H19z"), P("cut", "M22 15h4v11.2l7 4.2-2 3.4-9-5.4z")],
};
const NAMES = ["call", "chat", "location_on", "home", "star", "credit_card", "payments", "share", "close", "settings", "tune", "flag", "check_circle", "schedule", "shield"];
const all = { ...Object.fromEntries(NAMES.map((n) => [n, GLYPHS[n]])), ...EXTRA, jam: VEHICLES?.directions_car ?? GLYPHS.flag };
for (const [k, v] of Object.entries(all)) if (!Array.isArray(v)) throw new Error(`لا شكلَ لـ${k}`);

const q = (s) => JSON.stringify(s);
const body = Object.entries(all)
  .map(([k, parts]) => `        put(${q(k)}, new String[][] {\n${parts.map((p) => `            {${q(p.role)}, ${q(p.d)}},`).join("\n")}\n        });`)
  .join("\n");

for (const [app, pkg] of [["driver-app", "ly.tajora.driver"], ["customer-app", process.argv[2] || "ly.tajora.rider"]]) {
  const java = `package ${pkg};

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;

import androidx.core.graphics.PathParser;

import java.util.HashMap;
import java.util.Map;

/**
 * <b>أيقوناتُ الفقاعتين بالنمط C</b> (أمرُ المالك ٢٠/١١ الرابع) — <b>مولَّدٌ</b> من {@code design/icons-c/set.mjs} بـ
 * {@code design/icons-c/bubble-glyphs.mjs}، ولا يُحرَّر بيد. شبكةُ ٤٨، والأدوارُ كما في {@code renderC}: البرتقاليُّ ممتلئ، وظلٌّ مزاحٌ
 * بالدرجة الثانية، والتفاصيلُ بالبرتقاليّ الداكن، والثقوبُ بلون السطح. <b>نسختان في التطبيقين</b> إلا سطرَ الحزمة.
 */
public final class BubbleGlyphs {

    static final int ORANGE = Color.parseColor("#f05a28");
    static final int ORANGE_DEEP = Color.parseColor("#b8401a");

    private static final Map<String, String[][]> DATA = new HashMap<>();
    private static final Map<String, Path> CACHE = new HashMap<>();

    private static void put(String name, String[][] parts) {
        DATA.put(name, parts);
    }

    static {
${body}
    }

    private BubbleGlyphs() {}

    static boolean has(String name) {
        return DATA.containsKey(name);
    }

    private static Path path(String d) {
        Path cached = CACHE.get(d);
        if (cached == null) {
            cached = PathParser.createPathFromPathData(d);
            CACHE.put(d, cached);
        }
        return cached;
    }

    /** يرسم الأيقونةَ في مربّعٍ ضلعُه {@code size} أعلاه-يساره ({@code x}, {@code y}). {@code cut} لونُ السطح تحتها. */
    static void draw(Canvas canvas, String name, float x, float y, float size, boolean dark, int cut, Paint paint) {
        String[][] parts = DATA.get(name);
        if (parts == null) return;
        int second = dark ? Color.parseColor("#8f2f10") : Color.parseColor("#ffb595");
        int ground = dark ? Color.BLACK : Color.parseColor("#1f2433");
        float scale = size / 48f;
        canvas.save();
        canvas.translate(x, y);
        canvas.scale(scale, scale);
        paint.setStyle(Paint.Style.FILL);
        paint.setAntiAlias(true);
        for (String[] part : parts) {
            if (!"body".equals(part[0])) continue;
            canvas.save();
            canvas.translate(2f, 2f);
            paint.setColor(second);
            canvas.drawPath(path(part[1]), paint);
            canvas.restore();
        }
        for (String[] part : parts) {
            switch (part[0]) {
                case "body": paint.setColor(ORANGE); break;
                case "back": paint.setColor(second); break;
                case "detail": paint.setColor(ORANGE_DEEP); break;
                case "ground": paint.setColor(ground); paint.setAlpha(60); break;
                default: paint.setColor(cut); break;
            }
            canvas.drawPath(path(part[1]), paint);
            paint.setAlpha(255);
        }
        canvas.restore();
    }
}
`;
  const dir = app === "driver-app" ? "ly/tajora/driver" : pkg.replace(/\./g, "/");
  writeFileSync(new URL(`../../${app}/android/app/src/main/java/${dir}/BubbleGlyphs.java`, import.meta.url), java);
}
console.log("ok", Object.keys(all).length);
