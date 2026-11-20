package ly.tajora.rider;

import android.animation.ValueAnimator;
import android.app.ActivityManager;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.text.TextPaint;
import android.text.TextUtils;
import android.view.HapticFeedbackConstants;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.animation.DecelerateInterpolator;

import java.util.ArrayList;
import java.util.List;

/**
 * <b>القائمةُ الدائريّة حول الفقاعة</b> (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — <b>نسختان متطابقتان في التطبيقين إلا سطرَ الحزمة</b>.
 *
 * <p><b>آمنةٌ أثناء القيادة</b>: أزرارٌ قطرُها ٦٤dp بأيقونات النمط C وتسمياتٍ قصيرة، <b>نقرةٌ واحدةٌ لكلِّ فعل</b> (وما يحتاج تأكيداً
 * نقرتان على الزرِّ نفسِه: «تأكيد؟»)، بلا كتابة، <b>وتُطوى وحدَها بعد ست ثوانٍ بلا لمس</b> فلا تحجب الطريق. والخلفيّةُ معتمةٌ قليلاً
 * لا سوداء: الطريقُ والخريطةُ تُريان من تحتها. <b>وعلى الهاتف الضعيف</b> (ذاكرةٌ قليلة) تُفتح بلا حركة.
 *
 * <p>نافذةُ تراكبٍ واحدةٌ تُضاف حين تُفتح وتُزال حين تُطوى — <b>لا شيءَ يعمل وهي مغلقة</b>.
 */
public final class RadialMenu {

    /** زرٌّ في القائمة. {@code confirm}: نقرةٌ أولى تقول «تأكيد؟» والثانيةُ تفعل. */
    public static final class Item {
        final String id;
        final String glyph;
        final String label;
        final boolean confirm;
        final boolean danger;

        public Item(String id, String glyph, String label) {
            this(id, glyph, label, false, false);
        }

        public Item(String id, String glyph, String label, boolean confirm, boolean danger) {
            this.id = id;
            this.glyph = glyph;
            this.label = label;
            this.confirm = confirm;
            this.danger = danger;
        }
    }

    public interface Listener {
        void onPick(String id);
    }

    static final long AUTO_CLOSE_MS = 6_000;
    private static View view;
    private static Runnable closer;
    private static Handler mainHandler;

    /**
     * <b>معالجٌ واحدٌ للقائمة كلِّها</b> — {@code removeCallbacks} لا يزيل إلا ما نشره المعالجُ نفسُه، فمعالجٌ جديدٌ لكلِّ نداءٍ ترك
     * مؤقّتَ الطيِّ السابقَ حيّاً يطوي القائمةَ الفرعيّةَ التالية قبل أوانها. <b>وكسولٌ</b> فاختباراتُ JVM لا تلمس {@code Looper}.
     */
    private static Handler main() {
        if (mainHandler == null) mainHandler = new Handler(Looper.getMainLooper());
        return mainHandler;
    }

    private RadialMenu() {}

    public static boolean isOpen() {
        return view != null;
    }

    /** ألوانُ tokens.css — <b>بسِمة النظام</b> لا التطبيق (قد لا يعمل حين تُرسم). نسخةٌ هنا كي يبقى الملفُّ واحداً في التطبيقين. */
    static final class Pal {
        final boolean dark;
        final int sur, brd, tx, mut, acc, dim;

        private Pal(boolean dark) {
            this.dark = dark;
            sur = android.graphics.Color.parseColor(dark ? "#171a1f" : "#ffffff");
            brd = android.graphics.Color.parseColor(dark ? "#2b3038" : "#e0dad0");
            tx = android.graphics.Color.parseColor(dark ? "#f2efe8" : "#14161a");
            mut = android.graphics.Color.parseColor(dark ? "#9097a1" : "#6a6862");
            acc = android.graphics.Color.parseColor(dark ? "#ff6a33" : "#f05a28");
            dim = dark ? android.graphics.Color.argb(153, 0, 0, 0) : android.graphics.Color.argb(115, 20, 22, 26);
        }

        static Pal of(Context c) {
            int mode = c.getResources().getConfiguration().uiMode & android.content.res.Configuration.UI_MODE_NIGHT_MASK;
            return new Pal(mode == android.content.res.Configuration.UI_MODE_NIGHT_YES);
        }
    }

    static int dp(Context c, float v) {
        return Math.round(v * c.getResources().getDisplayMetrics().density);
    }

    // ───────────────────────────── الهندسة — خالصةٌ ومختبَرة

    /**
     * <b>مواضعُ الأزرار</b> حول مركز الفقاعة ({@code cx}, {@code cy}) في شاشةٍ {@code w}×{@code h}: مروحةٌ تتّجه إلى وسط الشاشة، بخطوةٍ
     * تكفي ألّا يتماسّ زرّان (قطرٌ وفجوة)، <b>ونصفُ دائرةٍ على الأكثر في الحلقة الأولى</b> وما زاد في حلقةٍ ثانية أبعد. وكلُّ موضعٍ
     * يُزاح إلى داخل الشاشة بهامش نصف قطر. يُرجع {@code [n][2]}.
     */
    static float[][] positions(int n, float cx, float cy, float w, float h, float r1, float r2, float itemR, float gap) {
        float[][] out = new float[n][2];
        if (n <= 0) return out;
        double base = Math.atan2(h / 2f - cy, w / 2f - cx);
        int first = Math.min(n, capacity(r1, itemR, gap));
        place(out, 0, first, base, cx, cy, r1, itemR, gap);
        if (n > first) place(out, first, n - first, base, cx, cy, r2, itemR, gap);
        float margin = itemR + 4f;
        for (float[] p : out) {
            p[0] = Math.max(margin, Math.min(w - margin, p[0]));
            p[1] = Math.max(margin, Math.min(h - margin, p[1]));
        }
        return out;
    }

    /** كم زرّاً يسع نصفُ دائرةٍ بنصف قطر {@code r} — والزرُّ الواحدُ يُسعه دائماً. */
    static int capacity(float r, float itemR, float gap) {
        double step = (2 * itemR + gap) / r;
        return Math.max(1, (int) Math.floor(Math.PI / step) + 1);
    }

    private static void place(float[][] out, int from, int count, double base, float cx, float cy, float r, float itemR, float gap) {
        double step = (2 * itemR + gap) / r;
        double start = base - step * (count - 1) / 2.0;
        for (int i = 0; i < count; i++) {
            double a = start + step * i;
            out[from + i][0] = cx + (float) (r * Math.cos(a));
            out[from + i][1] = cy + (float) (r * Math.sin(a));
        }
    }

    // ───────────────────────────── الفتح والطيّ

    /**
     * يفتح القائمةَ حول ({@code cx}, {@code cy}) بإحداثيّات الشاشة. {@code header}: سطورُ بطاقةٍ صغيرةٍ في النصف الآخر من الشاشة
     * (أرقامُ اليوم، الراكب، المنطقة) — فارغةً لا بطاقة.
     */
    public static void open(Context context, float cx, float cy, List<String> header, List<Item> items, Listener listener) {
        Context c = context.getApplicationContext();
        main().post(() -> attach(c, cx, cy, header, items, listener));
    }

    /** <b>تحديثُ ما في القائمة وهي مفتوحة</b> — حين تصل أرقامُ اليوم بعد الفتح؛ بلا حركةٍ ثانية. {@code null} يُبقي ما كان. */
    public static void update(List<String> header, List<Item> items) {
        main().post(() -> {
            if (!(view instanceof Face)) return;
            Face face = (Face) view;
            if (header != null) face.header = header;
            if (items != null) {
                face.items = items;
                face.armed = -1;
                face.layoutSpots();
            }
            face.invalidate();
        });
    }

    public static void close(Context context) {
        Context c = context.getApplicationContext();
        main().post(() -> detach(c));
    }

    private static boolean weak(Context c) {
        ActivityManager am = c.getSystemService(ActivityManager.class);
        return am == null || am.isLowRamDevice() || am.getMemoryClass() <= 192;
    }

    private static void attach(Context c, float cx, float cy, List<String> header, List<Item> items, Listener listener) {
        detach(c);
        WindowManager manager = c.getSystemService(WindowManager.class);
        if (manager == null) return;
        Face face = new Face(c, cx, cy, header, items, listener);
        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT,
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                        : WindowManager.LayoutParams.TYPE_PHONE,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        try {
            manager.addView(face, params);
            view = face;
        } catch (Exception ignored) {
            view = null;
            return;
        }
        if (weak(c)) {
            face.progress = 1f;
        } else {
            ValueAnimator grow = ValueAnimator.ofFloat(0f, 1f);
            grow.setDuration(180);
            grow.setInterpolator(new DecelerateInterpolator());
            grow.addUpdateListener(a -> {
                face.progress = (float) a.getAnimatedValue();
                face.invalidate();
            });
            grow.start();
        }
        armCloser(c);
    }

    private static void armCloser(Context c) {
        if (closer != null) main().removeCallbacks(closer);
        closer = () -> detach(c);
        main().postDelayed(closer, AUTO_CLOSE_MS);
    }

    private static void detach(Context c) {
        if (closer != null) {
            main().removeCallbacks(closer);
            closer = null;
        }
        if (view == null) return;
        WindowManager manager = c.getSystemService(WindowManager.class);
        try {
            if (manager != null) manager.removeView(view);
        } catch (Exception ignored) {
            // طُويت من قبل
        }
        view = null;
    }

    /** الرسمُ واللمس — منظرٌ واحدٌ يرسم كلَّ شيء، فلا شجرةَ مناظرَ تُبنى في كلِّ فتح. */
    private static final class Face extends View {
        final float cx;
        final float cy;
        List<String> header;
        List<Item> items;
        final Listener listener;
        final Pal p;
        final boolean dark;
        final float itemR;
        final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
        final Paint glyphPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        final TextPaint label = new TextPaint(Paint.ANTI_ALIAS_FLAG);
        final TextPaint head = new TextPaint(Paint.ANTI_ALIAS_FLAG);
        float progress;
        float[][] spots = new float[0][2];
        int armed = -1;

        Face(Context c, float cx, float cy, List<String> header, List<Item> items, Listener listener) {
            super(c);
            this.cx = cx;
            this.cy = cy;
            this.header = header == null ? new ArrayList<>() : header;
            this.items = items;
            this.listener = listener;
            this.p = Pal.of(c);
            this.dark = p.dark;
            this.itemR = dp(c, 32);
            label.setTextSize(dp(c, 12));
            label.setTypeface(Typeface.DEFAULT_BOLD);
            label.setTextAlign(Paint.Align.CENTER);
            head.setTextSize(dp(c, 14));
            head.setTypeface(Typeface.DEFAULT_BOLD);
            head.setTextAlign(Paint.Align.CENTER);
            setContentDescription("قائمة الفقاعة");
        }

        @Override
        protected void onSizeChanged(int w, int h, int ow, int oh) {
            super.onSizeChanged(w, h, ow, oh);
            layoutSpots();
        }

        void layoutSpots() {
            Context c = getContext();
            if (getWidth() == 0) return;
            spots = positions(items.size(), cx, cy, getWidth(), getHeight(), dp(c, 104), dp(c, 180), itemR, dp(c, 14));
        }

        @Override
        protected void onDraw(Canvas canvas) {
            int w = getWidth();
            int h = getHeight();
            // الخلفيّةُ معتمةٌ قليلاً — الطريقُ يُرى من تحتها
            fill.setColor(p.dim);
            fill.setAlpha((int) (110 * progress));
            canvas.drawRect(0, 0, w, h, fill);
            fill.setAlpha(255);
            drawHeader(canvas, w, h);
            for (int i = 0; i < items.size() && i < spots.length; i++) {
                Item item = items.get(i);
                float x = cx + (spots[i][0] - cx) * progress;
                float y = cy + (spots[i][1] - cy) * progress;
                float r = itemR * (0.6f + 0.4f * progress);
                fill.setColor(item.danger ? p.acc : p.sur);
                canvas.drawCircle(x, y, r, fill);
                fill.setStyle(Paint.Style.STROKE);
                fill.setStrokeWidth(dp(getContext(), 1.5f));
                fill.setColor(i == armed ? p.acc : p.brd);
                canvas.drawCircle(x, y, r, fill);
                fill.setStyle(Paint.Style.FILL);
                float g = r * 1.05f;
                BubbleGlyphs.draw(canvas, item.glyph, x - g / 2f, y - g / 2f, g, dark, item.danger ? p.acc : p.sur, glyphPaint);
                String text = i == armed ? "تأكيد؟" : item.label;
                float pillW = Math.min(label.measureText(text) + dp(getContext(), 12), dp(getContext(), 120));
                float top = y + r + dp(getContext(), 4);
                RectF pill = new RectF(x - pillW / 2f, top, x + pillW / 2f, top + dp(getContext(), 20));
                fill.setColor(p.sur);
                fill.setAlpha((int) (235 * progress));
                canvas.drawRoundRect(pill, dp(getContext(), 10), dp(getContext(), 10), fill);
                fill.setAlpha(255);
                label.setColor(i == armed ? p.acc : p.tx);
                label.setAlpha((int) (255 * progress));
                CharSequence shown = TextUtils.ellipsize(text, label, dp(getContext(), 112), TextUtils.TruncateAt.END);
                canvas.drawText(shown, 0, shown.length(), x, top + dp(getContext(), 14.5f), label);
            }
        }

        /** البطاقةُ في النصف الآخر من الشاشة — لا تقع تحت الأزرار. */
        private void drawHeader(Canvas canvas, int w, int h) {
            if (header.isEmpty()) return;
            Context c = getContext();
            float lineH = dp(c, 22);
            float cardW = Math.min(w - dp(c, 32), dp(c, 320));
            float cardH = lineH * header.size() + dp(c, 18);
            float top = cy > h / 2f ? dp(c, 56) : h - cardH - dp(c, 56);
            RectF card = new RectF((w - cardW) / 2f, top, (w + cardW) / 2f, top + cardH);
            fill.setColor(p.sur);
            fill.setAlpha((int) (245 * progress));
            canvas.drawRoundRect(card, dp(c, 16), dp(c, 16), fill);
            fill.setAlpha(255);
            for (int i = 0; i < header.size(); i++) {
                head.setColor(i == 0 ? p.tx : p.mut);
                head.setAlpha((int) (255 * progress));
                CharSequence line = TextUtils.ellipsize(header.get(i), head, cardW - dp(c, 24), TextUtils.TruncateAt.END);
                canvas.drawText(line, 0, line.length(), w / 2f, top + dp(c, 9) + lineH * (i + 0.72f), head);
            }
        }

        @Override
        public boolean onTouchEvent(MotionEvent event) {
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                armCloser(getContext());
                return true;
            }
            if (event.getActionMasked() != MotionEvent.ACTION_UP) return true;
            int hit = -1;
            float slop = itemR + dp(getContext(), 8);
            for (int i = 0; i < spots.length; i++) {
                float dx = event.getX() - spots[i][0];
                float dy = event.getY() - spots[i][1];
                if (dx * dx + dy * dy <= slop * slop) {
                    hit = i;
                    break;
                }
            }
            if (hit < 0) {
                detach(getContext());
                return true;
            }
            Item item = items.get(hit);
            performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);
            if (item.confirm && armed != hit) {
                armed = hit;
                invalidate();
                return true;
            }
            detach(getContext());
            if (listener != null) listener.onPick(item.id);
            return true;
        }
    }
}
