package ly.tajora.driver;

import android.animation.ValueAnimator;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.WindowManager;
import android.view.animation.Animation;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.ScaleAnimation;

import org.json.JSONObject;

/**
 * <b>فقاعةُ الحال العائمة</b> (SPEC §١٠٣ المرحلة A/1، أمرُ المالك ٢٠٢٦-١١-١٦؛ <b>وموسَّعةً بأمر ٢٠/١١ الرابع، SPEC §١١٠</b>): دائرةٌ
 * فوق التطبيقات <b>والكبتنُ متّصلٌ خارجَ التطبيق</b> — تقول «متصل» أو «غير متصل»، <b>وتنبض عند طلبٍ جديد</b>.
 *
 * <p><b>ومنذ ٢٠/١١</b>، كلٌّ خلف مفتاحه:
 * <ul>
 *   <li>لمسةٌ تفتح <b>القائمةَ الدائريّة</b> ({@link DriverBubbleMenu}، {@code bubble_radial_menu}) — ومطفأً تفتح التطبيقَ كما كانت.</li>
 *   <li><b>حلقتان</b> حولها: الهدفُ اليوميّ يمتلئ مع صافي اليوم (٤٧) والاشتراكُ بأيّامه (٤٨).</li>
 *   <li><b>عدّادٌ في وسطها</b>: الانتظارُ بعد «وصلت» (٥١)، وما بقي من الاستراحة (٤٤).</li>
 *   <li><b>ضغطةٌ طويلة = الطوارئ</b> بعدٍّ تنازليٍّ ٣ ثوانٍ تلغيه لمسة (٥٣).</li>
 *   <li><b>إعداداتُها</b> (٥٥): الحجمُ والشفافيّة والالتصاقُ بالحافّة، <b>وسحبُها إلى ✕ أسفل الشاشة يخفيها</b> حتى الاتّصال القادم،
 *       <b>وتختفي والتطبيقُ مفتوح</b> ({@code MainActivity.onResume}).</li>
 * </ul>
 *
 * <p><b>والبطّاريّة</b>: لا مؤقّتَ إلا حين يُعرض عدّاد، وتحديثُ الحال من تغيّر التفضيلات لا من استطلاع.
 * <b>وإذنُ التراكب نفسُه</b>: بلاه لا شيء، ولا يُطلب من هنا — الطلبُ في مركز الأذونات بشاشة شرحه.
 */
public final class StatusBubble {

    /** مفتاحُ السوق كما يكتبه الويب. */
    static final String PREF = "status_bubble";
    /** «أخفاها بالسحب» — يُمحى عند كلِّ اتّصالٍ جديد ({@link #resetDismissed}). */
    static final String DISMISSED = "status_bubble_dismissed";
    /** <b>«منطقةُ طلبٍ عالٍ»</b> (SPEC §١٠٣ C/29) — يكتبه الويبُ من جواب {@code /drivers/me/demand}، و{@code null} حين يُطفأ المفتاح. */
    static final String DEMAND = "bubble_demand";

    static final long SOS_SECONDS = 3;

    private static Face view;
    private static WindowManager.LayoutParams params;
    private static View target;
    private static SharedPreferences.OnSharedPreferenceChangeListener listener;
    private static Handler mainHandler;

    /** <b>كسولٌ لا عند تحميل الصنف</b> — فاختباراتُ JVM للدوالّ الخالصة لا تلمس {@code Looper} (غيرُ مُحاكى هناك). */
    private static Handler main() {
        if (mainHandler == null) mainHandler = new Handler(Looper.getMainLooper());
        return mainHandler;
    }
    private static Runnable ticker;

    private StatusBubble() {}

    private static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
    }

    /** <b>أتُرسم الآن؟</b> — المفتاحُ، والاتّصالُ، وإذنُ التراكب، ولم تُخفَ بالسحب. */
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

    /** خالصة: <b>قطرُ الفقاعة</b> بالـdp من اختيار الكبتن (البند ٥٥) — صغيرٌ ٤٨، متوسّطٌ ٥٨ (الافتراض)، كبيرٌ ٧٠. */
    static int sizeDp(String choice) {
        if ("s".equals(choice)) return 48;
        if ("l".equals(choice)) return 70;
        return 58;
    }

    /** خالصة: <b>الشفافيّة</b> ١٠٠ / ٨٠ / ٦٠ — وما سواها كاملة. */
    static float alpha(String choice) {
        if ("80".equals(choice)) return 0.8f;
        if ("60".equals(choice)) return 0.6f;
        return 1f;
    }

    /** خالصة: <b>الالتصاقُ بالحافّة</b> — أقربُ الحافّتين لمركز الفقاعة. */
    static int snapX(int x, int size, int screenWidth, int margin) {
        int center = x + size / 2;
        return center < screenWidth / 2 ? margin : screenWidth - size - margin;
    }

    /** خالصة: <b>أأُفلتت فوق ✕؟</b> — داخلَ دائرةٍ نصفُ قطرها {@code r} حول مركز الهدف. */
    static boolean overTarget(float x, float y, float tx, float ty, float r) {
        float dx = x - tx;
        float dy = y - ty;
        return dx * dx + dy * dy <= r * r;
    }

    /** الخُمسُ الأسفلُ من الشاشة — <b>بقي لما قبل ✕</b> (الفقاعةُ القديمة) ومختبَر. */
    static boolean inDismissZone(float rawY, int screenHeight) {
        return screenHeight > 0 && rawY >= screenHeight * 0.8f;
    }

    /** يُنادى حين يخرج الكبتنُ من التطبيق. */
    public static void showIfWanted(Context context) {
        Context c = context.getApplicationContext();
        if (!wanted(c)) return;
        main().post(() -> attach(c));
    }

    /** يُنادى حين يعود إلى التطبيق، وحين ينفصل. */
    public static void hide(Context context) {
        Context c = context.getApplicationContext();
        main().post(() -> {
            RadialMenu.close(c);
            detach(c);
        });
    }

    /** اتّصالٌ جديد — <b>ما أُخفي بالسحب يعود</b>، فالإخفاءُ لجلسةٍ واحدة. */
    public static void resetDismissed(Context context) {
        prefs(context).edit().remove(DISMISSED).apply();
    }

    /** يعيد قراءةَ الحال ورسمَها — بعد استراحةٍ أو وصول. */
    public static void refresh(Context context) {
        Context c = context.getApplicationContext();
        main().post(() -> restyle(c));
    }

    /** <b>طلبٌ جديد</b> — نبضاتٌ ثلاث إن كانت ظاهرة، ولا شيءَ إن لم تكن. */
    public static void pulse() {
        main().post(() -> {
            if (view == null) return;
            ScaleAnimation beat = new ScaleAnimation(1f, 1.25f, 1f, 1.25f,
                    Animation.RELATIVE_TO_SELF, 0.5f, Animation.RELATIVE_TO_SELF, 0.5f);
            beat.setDuration(260);
            beat.setRepeatCount(5);
            beat.setRepeatMode(Animation.REVERSE);
            view.startAnimation(beat);
        });
    }

    /** <b>بلغ الهدف</b> (البند ٤٧) — وميضُ الحلقة ونبضتان. */
    static void celebrate(Context context) {
        main().post(() -> {
            if (view == null) return;
            ValueAnimator flash = ValueAnimator.ofFloat(0f, 1f, 0f, 1f, 0f);
            flash.setDuration(1400);
            flash.addUpdateListener(a -> {
                if (view == null) return;
                view.glow = (float) a.getAnimatedValue();
                view.invalidate();
            });
            flash.start();
            pulse();
        });
    }

    private static void attach(Context c) {
        if (view != null) return;
        WindowManager manager = c.getSystemService(WindowManager.class);
        if (manager == null) return;
        SharedPreferences shared = prefs(c);
        int size = OfferUi.dp(c, sizeDp(shared.getString("bubble_size", "m")));
        Face face = new Face(c);
        face.setAlpha(alpha(shared.getString("bubble_alpha", "100")));
        params = new WindowManager.LayoutParams(
                size, size,
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                        : WindowManager.LayoutParams.TYPE_PHONE,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP | Gravity.START;
        params.x = shared.getInt("bubble_x", OfferUi.dp(c, 8));
        params.y = shared.getInt("bubble_y", OfferUi.dp(c, 140));
        try {
            manager.addView(face, params);
            view = face;
            restyle(c);
            listener = (p, key) -> {
                if (key == null) return;
                if (DEMAND.equals(key) || "online".equals(key) || key.startsWith("bubble_") || "break_until".equals(key)
                        || "today_earned".equals(key) || "sub_days".equals(key)) {
                    main().post(() -> restyle(c));
                }
            };
            shared.registerOnSharedPreferenceChangeListener(listener);
        } catch (Exception ignored) {
            // إذنٌ سُحب بين السؤال والرسم — لا فقاعة، ولا شيءَ ينكسر
            view = null;
            return;
        }
        touch(c, manager, face);
    }

    /**
     * <b>لمسةٌ وسحبٌ وضغطةٌ طويلة</b>: حركةٌ دون الحدّ لمسة (القائمةُ أو التطبيق، <b>وتلغي عدَّ الطوارئ إن كان جارياً</b>)؛ والسحبُ يُظهر
     * ✕ أسفل الشاشة والإفلاتُ فوقها يخفيها؛ والإفلاتُ في غيرها يلصقها بالحافّة إن اختار الكبتنُ ذلك؛ والضغطةُ الطويلةُ تبدأ الطوارئ.
     */
    private static void touch(Context c, WindowManager manager, Face root) {
        int slop = OfferUi.dp(c, 10);
        long longPress = Math.max(600, ViewConfiguration.getLongPressTimeout());
        root.setOnTouchListener(new View.OnTouchListener() {
            float downX;
            float downY;
            int startX;
            int startY;
            boolean moved;
            boolean held;
            final Runnable hold = () -> {
                held = true;
                startSos(c);
            };

            @Override
            public boolean onTouch(View v, MotionEvent event) {
                switch (event.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        downX = event.getRawX();
                        downY = event.getRawY();
                        startX = params.x;
                        startY = params.y;
                        moved = false;
                        held = false;
                        if (root.sosLeft < 0 && prefs(c).getBoolean("bubble_sos", false)) main().postDelayed(hold, longPress);
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        float dx = event.getRawX() - downX;
                        float dy = event.getRawY() - downY;
                        if (!moved && (Math.abs(dx) > slop || Math.abs(dy) > slop)) {
                            moved = true;
                            main().removeCallbacks(hold);
                            showTarget(c, manager);
                        }
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
                    case MotionEvent.ACTION_CANCEL:
                        main().removeCallbacks(hold);
                        hideTarget(manager);
                        if (event.getActionMasked() == MotionEvent.ACTION_CANCEL || held) return true;
                        if (!moved) {
                            if (root.sosLeft >= 0) {
                                cancelSos(c);
                            } else if (DriverBubbleMenu.enabled(c)) {
                                DriverBubbleMenu.open(c, params.x + root.getWidth() / 2f, params.y + root.getHeight() / 2f);
                            } else {
                                DriverBubbleMenu.openApp(c, null);
                            }
                        } else if (droppedOnTarget(c, event.getRawX(), event.getRawY())) {
                            prefs(c).edit().putBoolean(DISMISSED, true).apply();
                            detach(c);
                        } else {
                            settle(c, manager, root);
                        }
                        return true;
                    default:
                        return false;
                }
            }
        });
    }

    private static boolean droppedOnTarget(Context c, float x, float y) {
        DisplayMetrics m = c.getResources().getDisplayMetrics();
        float tx = m.widthPixels / 2f;
        float ty = m.heightPixels - OfferUi.dp(c, 96);
        return overTarget(x, y, tx, ty, OfferUi.dp(c, 64));
    }

    /** يحفظ الموضع، ويلصقها بالحافّة إن اختار الكبتنُ ذلك (الافتراض: نعم). */
    private static void settle(Context c, WindowManager manager, View root) {
        SharedPreferences shared = prefs(c);
        if (shared.getBoolean("bubble_snap", true)) {
            DisplayMetrics m = c.getResources().getDisplayMetrics();
            int to = snapX(params.x, root.getWidth(), m.widthPixels, OfferUi.dp(c, 6));
            ValueAnimator slide = ValueAnimator.ofInt(params.x, to);
            slide.setDuration(160);
            slide.setInterpolator(new DecelerateInterpolator());
            slide.addUpdateListener(a -> {
                if (view == null) return;
                params.x = (int) a.getAnimatedValue();
                try {
                    manager.updateViewLayout(root, params);
                } catch (Exception ignored) {
                    // طُويت
                }
            });
            slide.start();
            shared.edit().putInt("bubble_x", to).putInt("bubble_y", params.y).apply();
        } else {
            shared.edit().putInt("bubble_x", params.x).putInt("bubble_y", params.y).apply();
        }
    }

    /** ✕ أسفل الشاشة أثناء السحب وحدَه. */
    private static void showTarget(Context c, WindowManager manager) {
        if (target != null) return;
        OfferPalette p = OfferPalette.of(c);
        int s = OfferUi.dp(c, 64);
        android.widget.TextView x = OfferUi.text(c, "✕", 26f, p.inv, true);
        x.setGravity(Gravity.CENTER);
        android.graphics.drawable.GradientDrawable d = new android.graphics.drawable.GradientDrawable();
        d.setShape(android.graphics.drawable.GradientDrawable.OVAL);
        d.setColor(p.tx);
        d.setAlpha(200);
        x.setBackground(d);
        x.setContentDescription("اسحب الفقاعة هنا لإخفائها");
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(s, s,
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                        : WindowManager.LayoutParams.TYPE_PHONE,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL;
        lp.y = OfferUi.dp(c, 64);
        try {
            manager.addView(x, lp);
            target = x;
        } catch (Exception ignored) {
            target = null;
        }
    }

    private static void hideTarget(WindowManager manager) {
        if (target == null) return;
        try {
            manager.removeView(target);
        } catch (Exception ignored) {
            // طُوي
        }
        target = null;
    }

    // ───────────────────────────── الطوارئ بالضغطة الطويلة (٥٣)

    private static void startSos(Context c) {
        if (view == null) return;
        view.sosLeft = SOS_SECONDS;
        DriverBubbleMenu.buzz(c, new long[] {0, 120});
        DriverBubbleMenu.toast(c, "طوارئ بعد 3 ثوانٍ — المس الفقاعة للإلغاء");
        tick(c);
    }

    private static void cancelSos(Context c) {
        if (view == null) return;
        view.sosLeft = -1;
        DriverBubbleMenu.toast(c, "أُلغي تنبيهُ الطوارئ");
        restyle(c);
    }

    // ───────────────────────────── الرسم

    /** يقرأ الحالَ ويرسمها، ويُبقي المؤقّتَ حيّاً ما دام عدّادٌ يُعرض — <b>ويوقفه حين لا عدّاد</b>. */
    private static void restyle(Context c) {
        if (view == null) return;
        SharedPreferences shared = prefs(c);
        Face f = view;
        f.online = shared.getBoolean("online", false);
        f.hot = showsHeat(f.online, shared.getBoolean(DEMAND, false));
        f.goal = shared.getBoolean("bubble_goal_ring", false)
                ? BubbleLogic.goalFraction(shared.getString("today_earned", null), shared.getString("bubble_goal", null)) : -1f;
        float sub = -1f;
        if (shared.getBoolean("bubble_subscription_ring", false)) {
            try {
                sub = BubbleLogic.subscriptionFraction(Integer.parseInt(shared.getString("sub_days", "")));
            } catch (NumberFormatException ignored) {
                sub = -1f;
            }
        }
        f.sub = sub;
        f.setAlpha(alpha(shared.getString("bubble_alpha", "100")));
        tick(c);
    }

    /** نصُّ الوسط الآن: عدُّ الطوارئ، ثمّ الانتظار، ثمّ الاستراحة، ثمّ «TAXO». و{@code true} إن كان عدّاداً يحتاج ثانيةً تالية. */
    private static boolean centerText(Context c) {
        Face f = view;
        SharedPreferences shared = prefs(c);
        long now = System.currentTimeMillis();
        if (f.sosLeft >= 0) {
            f.center = "SOS " + f.sosLeft;
            return true;
        }
        JSONObject ride = DriverBubbleMenu.ride(shared);
        if (ride != null && shared.getBoolean("bubble_wait_counter", false) && "arrived".equals(ride.optString("status"))) {
            long at = BubbleLogic.isoMillis(ride.optString("arrived_at", null));
            if (at > 0) {
                f.center = BubbleLogic.clock((now - at) / 1000);
                return true;
            }
        }
        long until = DriverBubbleMenu.breakUntil(shared);
        if (until > now) {
            f.center = "☕ " + BubbleLogic.clock((until - now) / 1000);
            return true;
        }
        f.center = "TAXO";
        return false;
    }

    private static void tick(Context c) {
        if (ticker != null) main().removeCallbacks(ticker);
        ticker = null;
        if (view == null) return;
        boolean live = centerText(c);
        Face f = view;
        f.setContentDescription(f.hot ? "متصل — منطقة طلب عالٍ — المس للقائمة"
                : f.online ? "متصل — المس للقائمة" : "غير متصل — المس لفتح التطبيق");
        f.invalidate();
        if (!live) return;
        ticker = () -> {
            if (view == null) return;
            if (view.sosLeft > 0) {
                view.sosLeft -= 1;
            } else if (view.sosLeft == 0) {
                view.sosLeft = -1;
                DriverBubbleMenu.emergency(c);
            }
            tick(c);
        };
        main().postDelayed(ticker, 1000);
    }

    private static void detach(Context c) {
        if (ticker != null) main().removeCallbacks(ticker);
        ticker = null;
        if (listener != null) {
            prefs(c).unregisterOnSharedPreferenceChangeListener(listener);
            listener = null;
        }
        WindowManager manager = c.getSystemService(WindowManager.class);
        if (manager != null) hideTarget(manager);
        if (view == null) return;
        try {
            if (manager != null) manager.removeView(view);
        } catch (Exception ignored) {
            // طُويت من قبل
        }
        view = null;
    }

    /** الوجه: دائرةٌ ونقطةُ حال، وحلقتان، ونصٌّ في الوسط — منظرٌ واحدٌ يرسم كلَّ شيء. */
    static final class Face extends View {
        final OfferPalette p;
        final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        final RectF oval = new RectF();
        boolean online;
        boolean hot;
        float goal = -1f;
        float sub = -1f;
        float glow;
        long sosLeft = -1;
        String center = "TAXO";

        Face(Context c) {
            super(c);
            p = OfferPalette.of(c);
            paint.setTextAlign(Paint.Align.CENTER);
        }

        @Override
        protected void onDraw(Canvas canvas) {
            float w = getWidth();
            float h = getHeight();
            float stroke = OfferUi.dp(getContext(), 3);
            float ring = OfferUi.dp(getContext(), 3.5f);
            float r = Math.min(w, h) / 2f - ring - stroke / 2f;
            float cx = w / 2f;
            float cy = h / 2f;
            boolean sos = sosLeft >= 0;
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(sos || hot ? p.acc : p.sur);
            canvas.drawCircle(cx, cy, r, paint);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(stroke);
            paint.setColor(online ? p.acc : p.mut);
            canvas.drawCircle(cx, cy, r, paint);
            // **حلقةُ الهدف** — خارجيّة، البرتقاليّ يمتلئ مع صافي اليوم
            float outer = Math.min(w, h) / 2f - ring / 2f;
            oval.set(cx - outer, cy - outer, cx + outer, cy + outer);
            paint.setStrokeCap(Paint.Cap.ROUND);
            if (goal >= 0f) {
                paint.setStrokeWidth(ring);
                paint.setColor(p.brd);
                canvas.drawArc(oval, 0, 360, false, paint);
                paint.setColor(p.acc);
                paint.setAlpha((int) (255 * (1f - 0.5f * glow)));
                canvas.drawArc(oval, -90, 360 * goal, false, paint);
                paint.setAlpha(255);
            }
            // **حلقةُ الاشتراك** — داخل الحدّ، لونٌ هادئ
            if (sub >= 0f) {
                float inner = r - stroke;
                oval.set(cx - inner, cy - inner, cx + inner, cy + inner);
                paint.setStrokeWidth(OfferUi.dp(getContext(), 2));
                paint.setColor(p.ok);
                paint.setAlpha(170);
                canvas.drawArc(oval, -90, 360 * sub, false, paint);
                paint.setAlpha(255);
            }
            paint.setStrokeCap(Paint.Cap.BUTT);
            // نقطةُ الحال
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(online ? p.ok : p.mut);
            float dot = OfferUi.dp(getContext(), 5.5f);
            canvas.drawCircle(cx + r * 0.72f, cy - r * 0.72f, dot, paint);
            // النصّ
            paint.setColor(sos || hot ? p.inv : p.tx);
            paint.setTypeface(Typeface.DEFAULT_BOLD);
            float size = "TAXO".equals(center) ? r * 0.42f : r * 0.36f;
            paint.setTextSize(size);
            canvas.drawText(center, cx, cy + size * 0.36f, paint);
        }
    }

    /** يُبقي التوقيعَ القديمَ لمن يناديه — يفتح التطبيق. */
    static void open(Context c) {
        Intent intent = new Intent(c, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        try {
            c.startActivity(intent);
        } catch (Exception ignored) {
            // إطلاقٌ منعه النظام
        }
    }
}
