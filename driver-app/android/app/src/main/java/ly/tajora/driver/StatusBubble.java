package ly.tajora.driver;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.animation.Animation;
import android.view.animation.ScaleAnimation;
import android.widget.FrameLayout;
import android.widget.TextView;

/**
 * <b>فقاعةُ الحال العائمة</b> (SPEC §١٠٣ المرحلة A/1، أمرُ المالك ٢٠٢٦-١١-١٦): دائرةٌ صغيرةٌ فوق التطبيقات <b>والكبتنُ متّصلٌ
 * خارجَ التطبيق</b> — تقول «متصل» أو «غير متصل»، <b>وتنبض عند طلبٍ جديد</b>، ولمسةٌ تفتح التطبيق، <b>وسحبُها إلى أسفل الشاشة يخفيها</b>
 * حتى الجلسة القادمة.
 *
 * <p><b>غيرُ فقاعة الطلب</b> ({@link OfferBubble}): تلك تحمل طلباً بعينه وتعيش مهلتَه، <b>وهذه حالٌ لا طلب</b> — فلا قبولَ فيها ولا مبلغ.
 *
 * <p><b>خلف مفتاحها</b> ({@code status_bubble}، يكتبه الويبُ بـ{@code Launcher.setPrefs} كأخواته)، <b>وإذنُ التراكب نفسُه</b>: بلاه لا شيء،
 * ولا يُطلب من هنا — الطلبُ في مركز الأذونات بشاشة شرحه.
 */
public final class StatusBubble {

    /** مفتاحُ السوق كما يكتبه الويب. */
    static final String PREF = "status_bubble";
    /** «أخفاها بالسحب» — يُمحى عند كلِّ اتّصالٍ جديد ({@link #resetDismissed}). */
    static final String DISMISSED = "status_bubble_dismissed";

    /** <b>«منطقةُ طلبٍ عالٍ»</b> (SPEC §١٠٣ C/29) — يكتبه الويبُ من جواب {@code /drivers/me/demand} القائم وحدَه، و{@code null} حين يُطفأ المفتاح. */
    static final String DEMAND = "bubble_demand";

    private static View view;
    private static TextView dot;
    private static TextView label;
    private static GradientDrawable circle;
    private static SharedPreferences.OnSharedPreferenceChangeListener listener;

    private StatusBubble() {}

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
    }

    /** <b>أتُرسم الآن؟</b> — المفتاحُ، والاتّصالُ، وإذنُ التراكب، ولم تُخفَ بالسحب. خالصٌ إلا من القراءة. */
    static boolean wanted(Context c) {
        SharedPreferences p = prefs(c);
        return p.getBoolean(PREF, false)
                && p.getBoolean("online", false)
                && !p.getBoolean(DISMISSED, false)
                && Settings.canDrawOverlays(c);
    }

    /** خالصة: <b>أتُرسم حرارةُ الطلب؟</b> — متّصلٌ وفي منطقة طلبٍ عالٍ معاً. */
    static boolean showsHeat(boolean online, boolean demand) {
        return online && demand;
    }

    /** يُنادى حين يخرج الكبتنُ من التطبيق. */
    public static void showIfWanted(Context context) {
        Context c = context.getApplicationContext();
        if (!wanted(c)) return;
        new Handler(Looper.getMainLooper()).post(() -> attach(c));
    }

    /** يُنادى حين يعود إلى التطبيق، وحين ينفصل. */
    public static void hide(Context context) {
        Context c = context.getApplicationContext();
        new Handler(Looper.getMainLooper()).post(() -> detach(c));
    }

    /** اتّصالٌ جديد — <b>ما أُخفي بالسحب يعود</b>، فالإخفاءُ لجلسةٍ واحدة. */
    public static void resetDismissed(Context context) {
        prefs(context).edit().remove(DISMISSED).apply();
    }

    /** <b>طلبٌ جديد</b> — نبضاتٌ ثلاث إن كانت ظاهرة، ولا شيءَ إن لم تكن. */
    public static void pulse() {
        new Handler(Looper.getMainLooper()).post(() -> {
            if (view == null) return;
            ScaleAnimation beat = new ScaleAnimation(1f, 1.25f, 1f, 1.25f,
                    Animation.RELATIVE_TO_SELF, 0.5f, Animation.RELATIVE_TO_SELF, 0.5f);
            beat.setDuration(260);
            beat.setRepeatCount(5);
            beat.setRepeatMode(Animation.REVERSE);
            view.startAnimation(beat);
        });
    }

    private static void attach(Context c) {
        if (view != null) return;
        WindowManager manager = c.getSystemService(WindowManager.class);
        if (manager == null) return;
        OfferPalette p = OfferPalette.of(c);
        boolean online = prefs(c).getBoolean("online", false);

        FrameLayout root = new FrameLayout(c);
        int size = OfferUi.dp(c, 58);
        circle = new GradientDrawable();
        circle.setShape(GradientDrawable.OVAL);
        circle.setColor(p.sur);
        circle.setStroke(OfferUi.dp(c, 3), online ? p.acc : p.mut);
        root.setBackground(circle);
        root.setContentDescription(online ? "متصل — المس لفتح التطبيق" : "غير متصل — المس لفتح التطبيق");

        label = OfferUi.text(c, "TAXO", 11f, p.tx, true);
        label.setGravity(Gravity.CENTER);
        root.addView(label, new FrameLayout.LayoutParams(size, size, Gravity.CENTER));

        dot = new TextView(c);
        GradientDrawable d = new GradientDrawable();
        d.setShape(GradientDrawable.OVAL);
        d.setColor(online ? p.acc : p.mut);
        dot.setBackground(d);
        int ds = OfferUi.dp(c, 14);
        FrameLayout.LayoutParams dlp = new FrameLayout.LayoutParams(ds, ds, Gravity.TOP | Gravity.END);
        root.addView(dot, dlp);

        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                size, size,
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                        : WindowManager.LayoutParams.TYPE_PHONE,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP | Gravity.START;
        params.x = OfferUi.dp(c, 8);
        params.y = OfferUi.dp(c, 140);

        try {
            manager.addView(root, params);
            view = root;
            // **حرارةُ الطلب** (§١٠٣ C/29) — تُرسم الآن، وتتبع كلَّ تغيّرٍ ما دامت الفقاعةُ ظاهرة
            restyle(c);
            listener = (shared, key) -> {
                if (DEMAND.equals(key) || "online".equals(key)) new Handler(Looper.getMainLooper()).post(() -> restyle(c));
            };
            prefs(c).registerOnSharedPreferenceChangeListener(listener);
        } catch (Exception ignored) {
            // إذنٌ سُحب بين السؤال والرسم — لا فقاعة، ولا شيءَ ينكسر
            view = null;
            return;
        }
        touch(c, manager, root, params);
    }

    /** <b>سحبٌ ولمسة</b>: حركةٌ دون ١٠dp لمسةٌ تفتح التطبيق؛ وإفلاتٌ في الخُمس الأسفل من الشاشة يخفيها لهذه الجلسة. */
    private static void touch(Context c, WindowManager manager, View root, WindowManager.LayoutParams params) {
        int slop = OfferUi.dp(c, 10);
        root.setOnTouchListener(new View.OnTouchListener() {
            float downX;
            float downY;
            int startX;
            int startY;
            boolean moved;

            @Override
            public boolean onTouch(View v, MotionEvent event) {
                switch (event.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        downX = event.getRawX();
                        downY = event.getRawY();
                        startX = params.x;
                        startY = params.y;
                        moved = false;
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        float dx = event.getRawX() - downX;
                        float dy = event.getRawY() - downY;
                        if (Math.abs(dx) > slop || Math.abs(dy) > slop) moved = true;
                        if (moved) {
                            params.x = startX + (int) dx;
                            params.y = startY + (int) dy;
                            try {
                                manager.updateViewLayout(root, params);
                            } catch (Exception ignored) {
                                // طُويت أثناء السحب
                            }
                        }
                        return true;
                    case MotionEvent.ACTION_UP:
                        if (!moved) {
                            open(c);
                        } else if (inDismissZone(c, event.getRawY())) {
                            prefs(c).edit().putBoolean(DISMISSED, true).apply();
                            detach(c);
                        }
                        return true;
                    default:
                        return false;
                }
            }
        });
    }

    /** الخُمسُ الأسفلُ من الشاشة — خالصٌ ومختبَر. */
    static boolean inDismissZone(float rawY, int screenHeight) {
        return screenHeight > 0 && rawY >= screenHeight * 0.8f;
    }

    private static boolean inDismissZone(Context c, float rawY) {
        DisplayMetrics m = c.getResources().getDisplayMetrics();
        return inDismissZone(rawY, m.heightPixels);
    }

    private static void open(Context c) {
        Intent intent = new Intent(c, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        try {
            c.startActivity(intent);
        } catch (Exception ignored) {
            // إطلاقٌ منعه النظام — الفقاعةُ تبقى، والتطبيقُ من أيقونته
        }
    }

    /** الجمرُ يملأ الدائرةَ في منطقة الطلب العالي، وما فوق الجمر نصُّها — **أدوارُ الهوية لا لونٌ جديد**. */
    private static void restyle(Context c) {
        if (view == null || circle == null || label == null) return;
        OfferPalette p = OfferPalette.of(c);
        SharedPreferences shared = prefs(c);
        boolean online = shared.getBoolean("online", false);
        boolean hot = showsHeat(online, shared.getBoolean(DEMAND, false));
        circle.setColor(hot ? p.acc : p.sur);
        label.setTextColor(hot ? p.inv : p.tx);
        view.setContentDescription(hot
                ? "متصل — منطقة طلب عالٍ — المس لفتح التطبيق"
                : online ? "متصل — المس لفتح التطبيق" : "غير متصل — المس لفتح التطبيق");
    }

    private static void detach(Context c) {
        if (listener != null) {
            prefs(c).unregisterOnSharedPreferenceChangeListener(listener);
            listener = null;
        }
        if (view == null) return;
        WindowManager manager = c.getSystemService(WindowManager.class);
        try {
            if (manager != null) manager.removeView(view);
        } catch (Exception ignored) {
            // طُويت من قبل
        }
        view = null;
        dot = null;
        label = null;
        circle = null;
    }
}
