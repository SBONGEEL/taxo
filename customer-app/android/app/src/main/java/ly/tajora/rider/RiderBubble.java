package ly.tajora.rider;

import android.animation.ValueAnimator;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.view.WindowManager;
import android.view.animation.DecelerateInterpolator;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * <b>فقاعةُ الراكب</b> (أمرُ المالك ٢٠/١١ الرابع، الجزء ٢، SPEC §١١٠) — خلف {@code rider_bubble} <b>واختيارِ الراكب نفسِه</b>
 * ({@code rider_bubble_user})، وإذنِ «الظهور فوق التطبيقات» الذي يُطلب حين يختارها من شاشة الأذونات.
 *
 * <p><b>تظهر أثناء البحث عن كابتن وأثناء الرحلة، وحين يخرج من التطبيق وحدَهما</b> — وتختفي لحظةَ يعود أو تنتهي الرحلة. <b>حلقتُها
 * تمتلئ مع اقتراب الكابتن</b>، ووسطُها وقتُ الوصول أو عدّادُ الانتظار. والقائمةُ: الحالُ والإلغاءُ والاتّصالُ والدردشةُ (الأرقامُ مخفيّة)
 * والردودُ السريعةُ والمشاركةُ وتعديلُ الوجهة إن أُذن، <b>والطوارئُ بضغطةٍ طويلةٍ وعدٍّ تنازليّ</b>. والإعداداتُ كفقاعة الكبتن.
 *
 * <p><b>ما يمرّ بقاعدةٍ أو رسمٍ يفتح التطبيقَ على فعله</b> (الإلغاء، التعديل، الاتّصال، المشاركة) — فلا يتجاوز تأكيدَ السعر ولا رسمَ
 * الإلغاء. <b>ولا رحلةَ تُطلب من هنا أبداً.</b>
 */
public final class RiderBubble {

    static final long SOS_SECONDS = 3;
    private static Handler mainHandler;

    /** <b>كسولٌ لا عند تحميل الصنف</b> — فاختباراتُ JVM للدوالّ الخالصة لا تلمس {@code Looper} (غيرُ مُحاكى هناك). */
    private static Handler main() {
        if (mainHandler == null) mainHandler = new Handler(Looper.getMainLooper());
        return mainHandler;
    }
    private static Face view;
    private static WindowManager.LayoutParams params;
    private static View target;
    private static Runnable ticker;
    private static SharedPreferences.OnSharedPreferenceChangeListener listener;
    private static boolean appHidden;

    private RiderBubble() {}

    static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
    }

    static JSONObject ride(SharedPreferences p) {
        String raw = p.getString("rider_ride", null);
        if (raw == null) return null;
        try {
            return new JSONObject(raw);
        } catch (Exception e) {
            return null;
        }
    }

    static boolean wanted(Context c) {
        SharedPreferences p = prefs(c);
        JSONObject ride = ride(p);
        return p.getBoolean("rider_bubble", false)
                && p.getBoolean("rider_bubble_user", false)
                && ride != null && RiderBubbleLogic.showsFor(ride.optString("phase"))
                && Settings.canDrawOverlays(c);
    }

    /** خرج الراكبُ من التطبيق. */
    public static void onAppHidden(Context context) {
        Context c = context.getApplicationContext();
        appHidden = true;
        watch(c);
        if (wanted(c)) main().post(() -> attach(c));
    }

    /** عاد إليه. */
    public static void onAppShown(Context context) {
        Context c = context.getApplicationContext();
        appHidden = false;
        main().post(() -> {
            RadialMenu.close(c);
            detach(c);
        });
    }

    /** يراقب الحالَ والتطبيقُ خارجاً — رحلةٌ تنتهي تُخفي الفقاعة، وكابتنٌ يُعثر عليه يحدّثها. */
    private static void watch(Context c) {
        if (listener != null) return;
        listener = (p, key) -> {
            if (key == null || !(key.startsWith("rider_") || key.startsWith("bubble_"))) return;
            main().post(() -> {
                if (!appHidden) return;
                if (!wanted(c)) {
                    RadialMenu.close(c);
                    detach(c);
                } else if (view == null) {
                    attach(c);
                } else {
                    tick(c);
                }
            });
        };
        prefs(c).registerOnSharedPreferenceChangeListener(listener);
    }

    private static int sizeDp(String choice) {
        if ("s".equals(choice)) return 48;
        if ("l".equals(choice)) return 70;
        return 58;
    }

    private static float alpha(String choice) {
        if ("80".equals(choice)) return 0.8f;
        if ("60".equals(choice)) return 0.6f;
        return 1f;
    }

    private static void attach(Context c) {
        if (view != null) return;
        WindowManager manager = c.getSystemService(WindowManager.class);
        if (manager == null) return;
        SharedPreferences p = prefs(c);
        int size = RadialMenu.dp(c, sizeDp(p.getString("bubble_size", "m")));
        Face face = new Face(c);
        face.setAlpha(alpha(p.getString("bubble_alpha", "100")));
        params = new WindowManager.LayoutParams(size, size,
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                        : WindowManager.LayoutParams.TYPE_PHONE,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP | Gravity.START;
        params.x = p.getInt("bubble_x", RadialMenu.dp(c, 8));
        params.y = p.getInt("bubble_y", RadialMenu.dp(c, 160));
        try {
            manager.addView(face, params);
            view = face;
        } catch (Exception ignored) {
            view = null;
            return;
        }
        touch(c, manager, face);
        tick(c);
    }

    private static void touch(Context c, WindowManager manager, Face root) {
        int slop = RadialMenu.dp(c, 10);
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
            public boolean onTouch(View v, MotionEvent e) {
                switch (e.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        downX = e.getRawX();
                        downY = e.getRawY();
                        startX = params.x;
                        startY = params.y;
                        moved = false;
                        held = false;
                        if (root.sosLeft < 0 && prefs(c).getBoolean("bubble_sos", false)) main().postDelayed(hold, longPress);
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        float dx = e.getRawX() - downX;
                        float dy = e.getRawY() - downY;
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
                                // طُويت
                            }
                        }
                        return true;
                    case MotionEvent.ACTION_UP:
                    case MotionEvent.ACTION_CANCEL:
                        main().removeCallbacks(hold);
                        hideTarget(manager);
                        if (e.getActionMasked() == MotionEvent.ACTION_CANCEL || held) return true;
                        if (!moved) {
                            if (root.sosLeft >= 0) cancelSos(c);
                            else openMenu(c, params.x + root.getWidth() / 2f, params.y + root.getHeight() / 2f);
                        } else if (overTarget(c, e.getRawX(), e.getRawY())) {
                            // **مخفيّةٌ لهذه الرحلة** — تعود في الطلب القادم
                            JSONObject ride = ride(prefs(c));
                            prefs(c).edit().putString("rider_bubble_hidden", ride == null ? "" : ride.optString("id")).apply();
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

    private static boolean overTarget(Context c, float x, float y) {
        DisplayMetrics m = c.getResources().getDisplayMetrics();
        float dx = x - m.widthPixels / 2f;
        float dy = y - (m.heightPixels - RadialMenu.dp(c, 96));
        float r = RadialMenu.dp(c, 64);
        return dx * dx + dy * dy <= r * r;
    }

    private static void settle(Context c, WindowManager manager, View root) {
        SharedPreferences p = prefs(c);
        if (p.getBoolean("bubble_snap", true)) {
            DisplayMetrics m = c.getResources().getDisplayMetrics();
            int margin = RadialMenu.dp(c, 6);
            int to = params.x + root.getWidth() / 2 < m.widthPixels / 2 ? margin : m.widthPixels - root.getWidth() - margin;
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
            p.edit().putInt("bubble_x", to).putInt("bubble_y", params.y).apply();
        } else {
            p.edit().putInt("bubble_x", params.x).putInt("bubble_y", params.y).apply();
        }
    }

    private static void showTarget(Context c, WindowManager manager) {
        if (target != null) return;
        RadialMenu.Pal pal = RadialMenu.Pal.of(c);
        int s = RadialMenu.dp(c, 64);
        TextView x = new TextView(c);
        x.setText("✕");
        x.setTextSize(26f);
        x.setTextColor(pal.sur);
        x.setGravity(Gravity.CENTER);
        GradientDrawable d = new GradientDrawable();
        d.setShape(GradientDrawable.OVAL);
        d.setColor(pal.tx);
        d.setAlpha(200);
        x.setBackground(d);
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(s, s,
                Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                        ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                        : WindowManager.LayoutParams.TYPE_PHONE,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL;
        lp.y = RadialMenu.dp(c, 64);
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

    // ───────────────────────────── القائمة

    private static float lastX;
    private static float lastY;

    static void openMenu(Context c, float cx, float cy) {
        lastX = cx;
        lastY = cy;
        SharedPreferences p = prefs(c);
        JSONObject ride = ride(p);
        if (ride == null) return;
        String phase = ride.optString("phase");
        RadialMenu.open(c, cx, cy, header(ride), RiderBubbleLogic.items(phase,
                p.getBoolean("quick_replies", false), p.getBoolean("rider_edit_dest", false)), id -> pick(c, id));
        if (p.getBoolean("quick_replies", false) && !"searching".equals(phase)) {
            BubbleNet.get(c, "/quick-replies?side=rider", (code, body) -> {
                if (code != 200 || body == null) return;
                JSONArray texts = body.optJSONArray("texts");
                if (texts != null) p.edit().putString("rider_quick_json", texts.toString()).apply();
            });
        }
    }

    /** سطورُ البطاقة — <b>ما كتبه التطبيقُ بحرفه</b>، فلا وقتَ وصولٍ يُخترع ولا رسمَ يُحسب. */
    static List<String> header(JSONObject ride) {
        List<String> lines = new ArrayList<>();
        String phase = ride.optString("phase");
        if ("searching".equals(phase)) {
            lines.add("نبحث لك عن كابتن…");
            if (ride.optBoolean("free_cancel", false)) lines.add("الإلغاء الآن مجاني");
            return lines;
        }
        String driver = ride.optString("driver", "");
        String car = (ride.optString("car", "") + " " + ride.optString("color", "")).trim();
        String plate = ride.optString("plate", "");
        if ("assigned".equals(phase)) {
            int eta = ride.optInt("eta_min", -1);
            lines.add(eta >= 0 ? (driver.isEmpty() ? "الكابتن" : driver) + " يصل خلال " + eta + " د"
                    : (driver.isEmpty() ? "الكابتن" : driver) + " في الطريق إليك");
        } else if ("arrived".equals(phase)) {
            lines.add((driver.isEmpty() ? "الكابتن" : driver) + " وصل — بانتظارك");
            String note = ride.optString("wait_note", "");
            if (!note.isEmpty()) lines.add(note);
        } else {
            lines.add("في الرحلة مع " + (driver.isEmpty() ? "الكابتن" : driver));
        }
        if (!car.isEmpty() || !plate.isEmpty()) lines.add((car + (plate.isEmpty() ? "" : " · " + plate)).trim());
        return lines;
    }

    private static List<String> replies(SharedPreferences p) {
        List<String> out = new ArrayList<>();
        try {
            JSONArray texts = new JSONArray(p.getString("rider_quick_json", "[]"));
            for (int i = 0; i < texts.length(); i++) out.add(texts.getString(i));
        } catch (Exception ignored) {
            // الافتراض
        }
        if (out.isEmpty()) {
            out.add("أنا قادم");
            out.add("انتظرني دقيقة");
            out.add("أنا عند المدخل");
        }
        return out;
    }

    private static void pick(Context c, String id) {
        SharedPreferences p = prefs(c);
        JSONObject ride = ride(p);
        String rideId = ride == null ? null : ride.optString("id", null);
        switch (id) {
            case "open":
                openApp(c, null);
                return;
            case "quick":
                RadialMenu.open(c, lastX, lastY, null, RiderBubbleLogic.replyItems(replies(p)), next -> pick(c, next));
                return;
            case "back":
                openMenu(c, lastX, lastY);
                return;
            default:
                break;
        }
        if (id.startsWith("reply:")) {
            List<String> texts = replies(p);
            int i = Integer.parseInt(id.substring(6));
            if (rideId == null || i >= texts.size()) return;
            JSONObject body = new JSONObject();
            try {
                body.put("body", texts.get(i));
            } catch (Exception ignored) {
                // لا يقع
            }
            BubbleNet.post(c, "/rides/" + rideId + "/chat", body, (code, answer) -> {
                if (code >= 200 && code < 300) toast(c, "أُرسل: " + texts.get(i));
                else openApp(c, "chat");
            });
            return;
        }
        // **الاتّصالُ والدردشةُ بفعلَي الإشعار القائمَين** (`ride_call:<id>` · `ride_chat:<id>`) — الأرقامُ مخفيّة
        if (("call".equals(id) || "chat".equals(id)) && rideId != null) {
            openApp(c, "ride_" + id + ":" + rideId);
            return;
        }
        // الإلغاءُ والمشاركةُ وتعديلُ الوجهة — بمسار التطبيق وقاعدته
        openApp(c, id);
    }

    // ───────────────────────────── الطوارئ

    private static void startSos(Context c) {
        if (view == null) return;
        view.sosLeft = SOS_SECONDS;
        buzz(c, 120);
        toast(c, "طوارئ بعد 3 ثوانٍ — المس الفقاعة للإلغاء");
        tick(c);
    }

    private static void cancelSos(Context c) {
        if (view == null) return;
        view.sosLeft = -1;
        toast(c, "أُلغي تنبيهُ الطوارئ");
        tick(c);
    }

    private static void emergency(Context c) {
        JSONObject ride = ride(prefs(c));
        JSONObject body = new JSONObject();
        try {
            body.put("app", "rider");
            if (ride != null && ride.has("id")) body.put("ride_id", ride.optString("id"));
        } catch (Exception ignored) {
            // لا يقع
        }
        buzz(c, 400);
        BubbleNet.post(c, "/emergency", body, (code, answer) -> {
            if (code >= 200 && code < 300) toast(c, "أُرسل تنبيهُ الطوارئ إلى فريق TAXO");
            else openApp(c, "emergency");
        });
    }

    // ───────────────────────────── الرسم

    private static void tick(Context c) {
        if (ticker != null) main().removeCallbacks(ticker);
        ticker = null;
        if (view == null) return;
        SharedPreferences p = prefs(c);
        JSONObject ride = ride(p);
        String hidden = p.getString("rider_bubble_hidden", null);
        if (ride != null && hidden != null && hidden.equals(ride.optString("id"))) {
            detach(c);
            return;
        }
        Face f = view;
        boolean live = false;
        if (f.sosLeft >= 0) {
            f.center = "SOS " + f.sosLeft;
            live = true;
        } else if (ride != null) {
            String phase = ride.optString("phase");
            f.ring = RiderBubbleLogic.approach(phase, ride.optInt("eta_min", -1), ride.optInt("eta_first", -1));
            if ("arrived".equals(phase) && ride.optLong("arrived_ms", 0) > 0) {
                f.center = RiderBubbleLogic.clock((System.currentTimeMillis() - ride.optLong("arrived_ms")) / 1000);
                live = true;
            } else if ("assigned".equals(phase) && ride.optInt("eta_min", -1) >= 0) {
                f.center = ride.optInt("eta_min") + "د";
            } else if ("searching".equals(phase)) {
                f.center = "…";
                f.ring = -1f;
            } else {
                f.center = "TAXO";
            }
        }
        f.invalidate();
        if (!live) return;
        ticker = () -> {
            if (view == null) return;
            if (view.sosLeft > 0) {
                view.sosLeft -= 1;
            } else if (view.sosLeft == 0) {
                view.sosLeft = -1;
                emergency(c);
            }
            tick(c);
        };
        main().postDelayed(ticker, 1000);
    }

    private static void detach(Context c) {
        if (ticker != null) main().removeCallbacks(ticker);
        ticker = null;
        WindowManager manager = c.getSystemService(WindowManager.class);
        if (manager != null) hideTarget(manager);
        if (view == null) return;
        try {
            if (manager != null) manager.removeView(view);
        } catch (Exception ignored) {
            // طُويت
        }
        view = null;
    }

    static final class Face extends View {
        final RadialMenu.Pal p;
        final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        final RectF oval = new RectF();
        float ring = -1f;
        long sosLeft = -1;
        String center = "TAXO";

        Face(Context c) {
            super(c);
            p = RadialMenu.Pal.of(c);
            paint.setTextAlign(Paint.Align.CENTER);
            setContentDescription("فقاعة رحلتك — المس للقائمة");
        }

        @Override
        protected void onDraw(Canvas canvas) {
            float w = getWidth();
            float h = getHeight();
            float ringW = RadialMenu.dp(getContext(), 4);
            float r = Math.min(w, h) / 2f - ringW;
            float cx = w / 2f;
            float cy = h / 2f;
            boolean sos = sosLeft >= 0;
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(sos ? p.acc : p.sur);
            canvas.drawCircle(cx, cy, r, paint);
            float outer = Math.min(w, h) / 2f - ringW / 2f;
            oval.set(cx - outer, cy - outer, cx + outer, cy + outer);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(ringW);
            paint.setStrokeCap(Paint.Cap.ROUND);
            paint.setColor(p.brd);
            canvas.drawArc(oval, 0, 360, false, paint);
            if (ring >= 0f) {
                paint.setColor(p.acc);
                canvas.drawArc(oval, -90, 360 * ring, false, paint);
            }
            paint.setStrokeCap(Paint.Cap.BUTT);
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(sos ? p.sur : p.tx);
            paint.setTypeface(Typeface.DEFAULT_BOLD);
            float size = "TAXO".equals(center) ? r * 0.42f : r * 0.4f;
            paint.setTextSize(size);
            canvas.drawText(center, cx, cy + size * 0.36f, paint);
        }
    }

    static void openApp(Context c, String action) {
        Intent intent = new Intent(c, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        if (action != null) intent.putExtra(LauncherPlugin.EXTRA, action);
        try {
            c.startActivity(intent);
        } catch (Exception ignored) {
            // منعه النظام
        }
    }

    private static void toast(Context c, String text) {
        try {
            Toast.makeText(c, text, Toast.LENGTH_SHORT).show();
        } catch (Exception ignored) {
            // لا نافذة
        }
    }

    private static void buzz(Context c, long ms) {
        Vibrator v = c.getSystemService(Vibrator.class);
        if (v == null || !v.hasVibrator()) return;
        try {
            if (Build.VERSION.SDK_INT >= 26) v.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE));
            else v.vibrate(ms);
        } catch (Exception ignored) {
            // لا اهتزاز
        }
    }
}
