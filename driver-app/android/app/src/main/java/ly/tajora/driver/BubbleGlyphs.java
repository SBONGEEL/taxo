package ly.tajora.driver;

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
        put("call", new String[][] {
            {"body", "M14.6 7.6c2.2-.9 3.5-.2 4.3 1.6l3 6.3c.9 1.9.4 3.3-1.2 4.6l-2.2 1.8c2.2 4.6 5.4 7.8 10 10l1.8-2.2c1.3-1.6 2.7-2.1 4.6-1.2l6.3 3c1.8.8 2.5 2.1 1.6 4.3l-1.1 2.7C40.8 40.6 39 41.6 36.4 41.4 21.6 40.2 7.8 26.4 6.6 11.6 6.4 9 7.4 7.2 9.4 6.4z"},
            {"detail", "M29.5 5.5a14 14 0 0 1 13 13l-3.2.2a10.8 10.8 0 0 0-10-10zM28.6 11.4a8.2 8.2 0 0 1 8 8l-3.2.1a5 5 0 0 0-4.9-4.9z"},
        });
        put("chat", new String[][] {
            {"body", "M11 7h26a5 5 0 0 1 5 5v16a5 5 0 0 1-5 5H20.5L12 40.5V33h-1a5 5 0 0 1-5-5V12a5 5 0 0 1 5-5z"},
            {"cut", "M14 20a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0 -5 0z"},
            {"cut", "M21.5 20a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0 -5 0z"},
            {"cut", "M29 20a2.5 2.5 0 1 0 5 0a2.5 2.5 0 1 0 -5 0z"},
        });
        put("location_on", new String[][] {
            {"ground", "M15.5 43.2a8.5 2 0 1 0 17 0a8.5 2 0 1 0 -17 0z"},
            {"body", "M24 42S10 30.4 10 19.6a14 14 0 0 1 28 0C38 30.4 24 42 24 42z"},
            {"cut", "M18.4 19.6a5.6 5.6 0 1 0 11.2 0a5.6 5.6 0 1 0 -11.2 0z"},
        });
        put("home", new String[][] {
            {"detail", "M32.4 9.5h2.6000000000000005a1.4 1.4 0 0 1 1.4 1.4v6.2a1.4 1.4 0 0 1 -1.4 1.4h-2.6000000000000005a1.4 1.4 0 0 1 -1.4 -1.4v-6.2a1.4 1.4 0 0 1 1.4 -1.4z"},
            {"body", "M7.5 23.1L22.1 10.2a2.9 2.9 0 0 1 3.8 0L40.5 23.1V38a3.5 3.5 0 0 1-3.5 3.5H11A3.5 3.5 0 0 1 7.5 38z"},
            {"cut", "M19.5 41.5V31a4 4 0 0 1 4-4h1a4 4 0 0 1 4 4v10.5z"},
        });
        put("star", new String[][] {
            {"body", "M24 6L29.05 18.04L42.07 19.13L32.18 27.66L35.17 40.37L24 33.6L12.83 40.37L15.82 27.66L5.93 19.13L18.95 18.04z"},
            {"cut", "M24 20.2L25.53 23.5L29.14 23.93L26.47 26.4L27.17 29.97L24 28.2L20.83 29.97L21.53 26.4L18.86 23.93L22.47 23.5z"},
        });
        put("credit_card", new String[][] {
            {"body", "M10.5 10.5h27a5 5 0 0 1 5 5v17a5 5 0 0 1 -5 5h-27a5 5 0 0 1 -5 -5v-17a5 5 0 0 1 5 -5z"},
            {"detail", "M5.5 16h37v5.2h-37z"},
            {"cut", "M12.1 26h5.8a1.6 1.6 0 0 1 1.6 1.6v3.2a1.6 1.6 0 0 1 -1.6 1.6h-5.8a1.6 1.6 0 0 1 -1.6 -1.6v-3.2a1.6 1.6 0 0 1 1.6 -1.6z"},
            {"cut", "M26.3 28.2h9.9a1.3 1.3 0 0 1 1.3 1.3v0a1.3 1.3 0 0 1 -1.3 1.3h-9.9a1.3 1.3 0 0 1 -1.3 -1.3v0a1.3 1.3 0 0 1 1.3 -1.3z"},
        });
        put("payments", new String[][] {
            {"back", "M15 8.5h23a4 4 0 0 1 4 4v12a4 4 0 0 1 -4 4h-23a4 4 0 0 1 -4 -4v-12a4 4 0 0 1 4 -4z"},
            {"body", "M10 15.5h23a4 4 0 0 1 4 4v13.5a4 4 0 0 1 -4 4h-23a4 4 0 0 1 -4 -4v-13.5a4 4 0 0 1 4 -4z"},
            {"cut", "M16.5 26.2a5 5 0 1 0 10 0a5 5 0 1 0 -10 0z"},
            {"detail", "M19.5 26.2a2 2 0 1 0 4 0a2 2 0 1 0 -4 0z"},
            {"cut", "M9.4 20.5a1.6 1.6 0 1 0 3.2 0a1.6 1.6 0 1 0 -3.2 0z"},
            {"cut", "M30.4 32a1.6 1.6 0 1 0 3.2 0a1.6 1.6 0 1 0 -3.2 0z"},
        });
        put("share", new String[][] {
            {"detail", "M16.4 21.4l13.4-7.1 1.7 3.2-13.4 7.1zM18.1 23.3l13.4 7.1-1.7 3.2-13.4-7.1z"},
            {"body", "M28.1 13a6.4 6.4 0 1 0 12.8 0a6.4 6.4 0 1 0 -12.8 0z"},
            {"body", "M7.1 24a6.4 6.4 0 1 0 12.8 0a6.4 6.4 0 1 0 -12.8 0z"},
            {"body", "M28.1 35a6.4 6.4 0 1 0 12.8 0a6.4 6.4 0 1 0 -12.8 0z"},
        });
        put("close", new String[][] {
            {"body", "M6 24a18 18 0 1 0 36 0a18 18 0 1 0 -36 0z"},
            {"cut", "M17.6 15.4L24 21.8l6.4-6.4 2.2 2.2L26.2 24l6.4 6.4-2.2 2.2L24 26.2l-6.4 6.4-2.2-2.2 6.4-6.4-6.4-6.4z"},
        });
        put("settings", new String[][] {
            {"body", "M18.7 10.61L19.97 5.43L28.03 5.43L29.3 10.61L29.72 10.78L34.28 8.02L39.98 13.72L37.22 18.28L37.39 18.7L42.57 19.97L42.57 28.03L37.39 29.3L37.22 29.72L39.98 34.28L34.28 39.98L29.72 37.22L29.3 37.39L28.03 42.57L19.97 42.57L18.7 37.39L18.28 37.22L13.72 39.98L8.02 34.28L10.78 29.72L10.61 29.3L5.43 28.03L5.43 19.97L10.61 18.7L10.78 18.28L8.02 13.72L13.72 8.02L18.28 10.78z"},
            {"cut", "M17.6 24a6.4 6.4 0 1 0 12.8 0a6.4 6.4 0 1 0 -12.8 0z"},
        });
        put("tune", new String[][] {
            {"detail", "M8.2 11h31.6a2.2 2.2 0 0 1 2.2 2.2v0a2.2 2.2 0 0 1 -2.2 2.2h-31.6a2.2 2.2 0 0 1 -2.2 -2.2v0a2.2 2.2 0 0 1 2.2 -2.2z"},
            {"detail", "M8.2 21.8h31.6a2.2 2.2 0 0 1 2.2 2.2v0a2.2 2.2 0 0 1 -2.2 2.2h-31.6a2.2 2.2 0 0 1 -2.2 -2.2v0a2.2 2.2 0 0 1 2.2 -2.2z"},
            {"detail", "M8.2 32.6h31.6a2.2 2.2 0 0 1 2.2 2.2v0a2.2 2.2 0 0 1 -2.2 2.2h-31.6a2.2 2.2 0 0 1 -2.2 -2.2v0a2.2 2.2 0 0 1 2.2 -2.2z"},
            {"body", "M24.4 13.2a5.6 5.6 0 1 0 11.2 0a5.6 5.6 0 1 0 -11.2 0z"},
            {"cut", "M28 13.2a2 2 0 1 0 4 0a2 2 0 1 0 -4 0z"},
            {"body", "M10.9 24a5.6 5.6 0 1 0 11.2 0a5.6 5.6 0 1 0 -11.2 0z"},
            {"cut", "M14.5 24a2 2 0 1 0 4 0a2 2 0 1 0 -4 0z"},
            {"body", "M27.4 34.8a5.6 5.6 0 1 0 11.2 0a5.6 5.6 0 1 0 -11.2 0z"},
            {"cut", "M31 34.8a2 2 0 1 0 4 0a2 2 0 1 0 -4 0z"},
        });
        put("flag", new String[][] {
            {"detail", "M10.8 5.5h0a1.8 1.8 0 0 1 1.8 1.8v33.4a1.8 1.8 0 0 1 -1.8 1.8h0a1.8 1.8 0 0 1 -1.8 -1.8v-33.4a1.8 1.8 0 0 1 1.8 -1.8z"},
            {"body", "M12.6 8h23.6c1.9 0 2.9 2 1.9 3.6L34.6 17l3.5 5.4c1 1.6 0 3.6-1.9 3.6H12.6z"},
            {"cut", "M18 13h3a1 1 0 0 1 1 1v1.6a1 1 0 0 1 -1 1h-3a1 1 0 0 1 -1 -1v-1.6a1 1 0 0 1 1 -1z"},
            {"cut", "M23 16.6h3a1 1 0 0 1 1 1v1.6a1 1 0 0 1 -1 1h-3a1 1 0 0 1 -1 -1v-1.6a1 1 0 0 1 1 -1z"},
            {"cut", "M18 20.2h3a1 1 0 0 1 1 1v1.6a1 1 0 0 1 -1 1h-3a1 1 0 0 1 -1 -1v-1.6a1 1 0 0 1 1 -1z"},
        });
        put("check_circle", new String[][] {
            {"body", "M6 24a18 18 0 1 0 36 0a18 18 0 1 0 -36 0z"},
            {"cut", "M15 24.4l2.6-2.6 4 4 9-9 2.6 2.6L21.6 31z"},
        });
        put("schedule", new String[][] {
            {"body", "M6 24a18 18 0 1 0 36 0a18 18 0 1 0 -36 0z"},
            {"cut", "M24 12h0a1.6 1.6 0 0 1 1.6 1.6v9.8a1.6 1.6 0 0 1 -1.6 1.6h0a1.6 1.6 0 0 1 -1.6 -1.6v-9.8a1.6 1.6 0 0 1 1.6 -1.6z"},
            {"cut", "M23 23.2l8.6 5-1.6 2.8-8.6-5z"},
            {"detail", "M21.6 24a2.4 2.4 0 1 0 4.8 0a2.4 2.4 0 1 0 -4.8 0z"},
        });
        put("shield", new String[][] {
            {"body", "M24 4.5l15 6v10.6c0 9.6-6.3 17.6-15 21.4C15.3 38.7 9 30.7 9 21.1V10.5z"},
            {"cut", "M16.6 23.5l2.7-2.7 3.4 3.4 6.8-6.8 2.7 2.7-9.5 9.5z"},
        });
        put("power", new String[][] {
            {"body", "M14.4 11.4l3.2 3.8a11.6 11.6 0 1 0 12.8 0l3.2-3.8a16.6 16.6 0 1 1-19.2 0z"},
            {"detail", "M21.5 4.5h5v19h-5z"},
        });
        put("pause", new String[][] {
            {"body", "M12 8h8.5v32H12zM27.5 8H36v32h-8.5z"},
        });
        put("flame", new String[][] {
            {"body", "M24 4c2.4 7.6 11.6 10.8 11.6 22.4a11.6 11.6 0 0 1-23.2 0c0-5.6 2.6-9 5.4-11.2 0 4.4 1.6 6.6 3.8 7.8C20.6 17.6 20 10.6 24 4z"},
            {"cut", "M24 27c2.4 2.2 4.4 3.6 4.4 6.6a4.4 4.4 0 0 1-8.8 0c0-2.4 1.8-4.4 4.4-6.6z"},
        });
        put("road_closed", new String[][] {
            {"body", "M5 15h38a3 3 0 0 1 3 3v9a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3v-9a3 3 0 0 1 3-3z"},
            {"cut", "M9 30l9-15h5l-9 15zM21 30l9-15h5l-9 15z"},
            {"detail", "M8 30h5v12H8zM35 30h5v12h-5z"},
        });
        put("accident", new String[][] {
            {"body", "M24 4.5c1.4 0 2.6.7 3.3 2l16.6 29c1.4 2.5-.4 5.5-3.3 5.5H7.4c-2.9 0-4.7-3-3.3-5.5l16.6-29c.7-1.3 1.9-2 3.3-2z"},
            {"cut", "M21.6 15h4.8l-.8 13h-3.2zM24 30.6a2.6 2.6 0 1 1 0 5.2 2.6 2.6 0 0 1 0-5.2z"},
        });
        put("navigate", new String[][] {
            {"body", "M24 4l15.5 37.5L24 33.6 8.5 41.5z"},
            {"detail", "M24 4v29.6l-15.5 7.9z"},
        });
        put("sos", new String[][] {
            {"body", "M24 4.5l16 6v11.4c0 10.4-6.8 18.6-16 21.6-9.2-3-16-11.2-16-21.6V10.5z"},
            {"cut", "M21.6 13h4.8l-.8 13.4h-3.2zM24 29.2a2.6 2.6 0 1 1 0 5.2 2.6 2.6 0 0 1 0-5.2z"},
        });
        put("wrench", new String[][] {
            {"body", "M30.6 5.2a10 10 0 0 0-11 13.2L6.4 31.6a4.6 4.6 0 0 0 6.5 6.5l13.2-13.2a10 10 0 0 0 13.2-11l-6 6-5.4-1.4-1.4-5.4z"},
            {"cut", "M10.2 33a2 2 0 1 1 0 4 2 2 0 0 1 0-4z"},
        });
        put("timer", new String[][] {
            {"body", "M24 9.5a16.5 16.5 0 1 1 0 33 16.5 16.5 0 0 1 0-33z"},
            {"detail", "M19 3.5h10v4H19z"},
            {"cut", "M22 15h4v11.2l7 4.2-2 3.4-9-5.4z"},
        });
        put("jam", new String[][] {
            {"ground", "M2 39.6a21.5 2.1 0 1 0 43 0a21.5 2.1 0 1 0 -43 0z"},
            {"detail", "M39.1 34.6a2.1 3.4 0 1 0 4.2 0a2.1 3.4 0 1 0 -4.2 0z"},
            {"body", "M2.5 33v-5.8c0-1.6 1.1-2.6 2.6-2.8l6.6-.9 4.6-6.6c.8-1.1 1.9-1.6 3.2-1.6h9c1.3 0 2.4.6 3.1 1.6l3.5 5.3 1.2.3V33z"},
            {"back", "M19.5 15.3l3.1-1.6h11l-1.8 3.2c-.7-1-1.8-1.6-3.1-1.6z"},
            {"detail", "M36.3 22.5l6 1.9c1.3.4 2.1 1.4 2.1 2.7V33.7l-8.1.4z"},
            {"cut", "M31.8 16.9l1.8-3.2 4.6 3 3.6 7.7-5.5-1.9z"},
            {"cut", "M17.8 17.4c.5-.6 1.1-.9 1.9-.9h3.5v5.9h-8.9z"},
            {"cut", "M25.2 16.5h3.4c.9 0 1.6.4 2.1 1.1l3.1 4.8h-8.6z"},
            {"cut", "M39 27.3l4.4 1.2v1.8L39 29.1z"},
            {"detail", "M4.4 26.6h2.9999999999999996a0.8 0.8 0 0 1 0.8 0.8v0a0.8 0.8 0 0 1 -0.8 0.8h-2.9999999999999996a0.8 0.8 0 0 1 -0.8 -0.8v0a0.8 0.8 0 0 1 0.8 -0.8z"},
            {"detail", "M6.7 33.6a4.3 4.3 0 1 0 8.6 0a4.3 4.3 0 1 0 -8.6 0z"},
            {"cut", "M9.3 33.6a1.7 1.7 0 1 0 3.4 0a1.7 1.7 0 1 0 -3.4 0z"},
            {"detail", "M26.099999999999998 33.6a4.3 4.3 0 1 0 8.6 0a4.3 4.3 0 1 0 -8.6 0z"},
            {"cut", "M28.7 33.6a1.7 1.7 0 1 0 3.4 0a1.7 1.7 0 1 0 -3.4 0z"},
            {"detail", "M41.5 5.1L42.62 7.96L45.68 8.14L43.31 10.09L44.09 13.06L41.5 11.4L38.91 13.06L39.69 10.09L37.32 8.14L40.38 7.96z"},
        });
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
