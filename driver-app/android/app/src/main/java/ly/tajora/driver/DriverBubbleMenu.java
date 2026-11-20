package ly.tajora.driver;

import android.annotation.SuppressLint;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.location.Location;
import android.location.LocationManager;
import android.net.Uri;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * <b>قائمةُ فقاعة الكبتن</b> (أمرُ المالك ٢٠/١١ الرابع، البنود ٤٢–٥٣، SPEC §١١٠) — تبني الأزرارَ من المفاتيح والحال وتنفّذ ما يُختار.
 *
 * <p><b>ثلاثةُ طرقٍ لا رابعَ لها</b>:
 * <ul>
 *   <li><b>نداءٌ خفيفٌ من هنا</b> ({@link BubbleNet}) لأبوابٍ قائمة: الاستراحة، «وصلت»، الردُّ السريع، بلاغُ الطريق، الطوارئ.</li>
 *   <li><b>فتحُ التطبيق على فعلٍ</b> ({@code taxo_action}) لما يمرّ بمسار الويب وفحوصه: إيقافُ الاستقبال، «آخر رحلة»، الاتّصال، الدردشة
 *       — <b>فلا بابَ ثانياً</b> يتجاوز فحصَ الاشتراك أو إخفاءَ الأرقام.</li>
 *   <li><b>الملاحةُ</b> بتطبيق الخرائط في الهاتف: وجهةُ الرحلة أو المنطقةُ المزدحمة.</li>
 * </ul>
 * والأرقامُ تُقرأ عند الفتح من أبوابها ({@code /drivers/me/earnings} · {@code /subscriptions/me} · {@code /drivers/me/busy-area}) —
 * <b>لا مؤقّتَ في الخلفيّة</b>، فلا كلفةَ على البطّاريّة والقائمةُ مغلقة.
 */
final class DriverBubbleMenu {

    static final String[] FLAGS = {
        "bubble_radial_menu", "bubble_online_toggle", "bubble_today_card", "driver_break", "bubble_busy_area",
        "bubble_last_ride", "bubble_goal_ring", "bubble_subscription_ring", "bubble_ride_panel", "quick_replies",
        "bubble_wait_counter", "bubble_road_report", "map_road_reports", "bubble_sos",
    };

    private static float lastX;
    private static float lastY;

    private DriverBubbleMenu() {}

    static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
    }

    static boolean enabled(Context c) {
        return prefs(c).getBoolean("bubble_radial_menu", false);
    }

    static Map<String, Boolean> flags(SharedPreferences p) {
        Map<String, Boolean> on = new HashMap<>();
        for (String key : FLAGS) on.put(key, p.getBoolean(key, false));
        return on;
    }

    static JSONObject ride(SharedPreferences p) {
        String raw = p.getString("bubble_ride", null);
        if (raw == null) return null;
        try {
            return new JSONObject(raw);
        } catch (Exception e) {
            return null;
        }
    }

    static long breakUntil(SharedPreferences p) {
        return BubbleLogic.isoMillis(p.getString("break_until", null));
    }

    static JSONObject busy(SharedPreferences p) {
        String raw = p.getString("busy_json", null);
        if (raw == null) return null;
        try {
            JSONObject area = new JSONObject(raw);
            return area.has("lat") ? area : null;
        } catch (Exception e) {
            return null;
        }
    }

    // ───────────────────────────── الفتح

    static void open(Context context, float cx, float cy) {
        Context c = context.getApplicationContext();
        lastX = cx;
        lastY = cy;
        RadialMenu.open(c, cx, cy, header(c), main(c), id -> pick(c, id));
        refresh(c);
    }

    private static List<RadialMenu.Item> main(Context c) {
        SharedPreferences p = prefs(c);
        JSONObject ride = ride(p);
        String status = ride == null ? null : ride.optString("status", null);
        boolean onBreak = breakUntil(p) > System.currentTimeMillis();
        return BubbleLogic.driverItems(flags(p), p.getBoolean("online", false), status, onBreak, busy(p) != null);
    }

    /** سطورُ البطاقة — <b>ما يُعرف وحدَه</b>: سطرٌ لم تصل أرقامُه لا يُرسم. */
    static List<String> header(Context c) {
        SharedPreferences p = prefs(c);
        Map<String, Boolean> on = flags(p);
        String currency = p.getString("currency_label", "");
        List<String> lines = new ArrayList<>();
        JSONObject ride = ride(p);
        if (ride != null && Boolean.TRUE.equals(on.get("bubble_ride_panel"))) {
            String rider = ride.optString("rider", "");
            String status = ride.optString("status", "");
            String phase = "accepted".equals(status) ? "في الطريق إليه" : "arrived".equals(status) ? "وصلتَ — بانتظاره" : "في الرحلة";
            lines.add((rider.isEmpty() ? "الراكب" : rider) + " · " + phase);
        }
        long until = breakUntil(p);
        if (until > System.currentTimeMillis()) {
            lines.add("استراحة — باقٍ " + BubbleLogic.clock((until - System.currentTimeMillis()) / 1000));
        }
        String earned = p.getString("today_earned", null);
        if (Boolean.TRUE.equals(on.get("bubble_today_card")) && earned != null) {
            String rides = p.getString("today_rides", "—");
            Integer minutes = null;
            try {
                minutes = Integer.valueOf(p.getString("today_minutes", ""));
            } catch (NumberFormatException ignored) {
                // «لم يُقَس» — شرطة
            }
            lines.add(String.format(Locale.ROOT, "اليوم %s %s · %s رحلات · %s", earned, currency, rides, BubbleLogic.workTime(minutes)));
        }
        String goal = p.getString("bubble_goal", null);
        if (Boolean.TRUE.equals(on.get("bubble_goal_ring")) && goal != null && earned != null) {
            lines.add(BubbleLogic.goalReached(earned, goal)
                    ? "🎉 بلغتَ هدفَ اليوم " + goal + " " + currency
                    : "الهدف: " + earned + " من " + goal + " " + currency);
        }
        String days = p.getString("sub_days", null);
        if (Boolean.TRUE.equals(on.get("bubble_subscription_ring")) && days != null) {
            lines.add("الاشتراك: باقٍ " + days + " " + ("1".equals(days) ? "يوم" : "أيام"));
        }
        JSONObject area = busy(p);
        if (Boolean.TRUE.equals(on.get("bubble_busy_area")) && ride == null && p.getBoolean("online", false)) {
            lines.add(area == null ? "لا منطقةَ مزدحمة قريبة الآن"
                    : "الأكثر طلباً: " + BubbleLogic.busyLine(area.optString("name", null), area.optDouble("distance_km", 0)));
        }
        return lines;
    }

    /** يقرأ الأرقامَ من أبوابها ويحدّث القائمةَ إن بقيت مفتوحة — <b>ولا يكتب شيئاً في الخادم</b>. */
    static void refresh(Context c) {
        SharedPreferences p = prefs(c);
        Map<String, Boolean> on = flags(p);
        if (Boolean.TRUE.equals(on.get("bubble_today_card")) || Boolean.TRUE.equals(on.get("bubble_goal_ring"))) {
            BubbleNet.get(c, "/drivers/me/earnings?period=today", (code, body) -> {
                if (code != 200 || body == null) return;
                SharedPreferences.Editor e = p.edit()
                        .putString("today_earned", body.optString("earned", null))
                        .putString("today_rides", String.valueOf(body.optInt("completed_rides", 0)));
                if (body.isNull("online_minutes")) e.remove("today_minutes");
                else e.putString("today_minutes", String.valueOf(body.optInt("online_minutes")));
                e.apply();
                celebrateIfReached(c);
                afterRefresh(c);
            });
        }
        if (Boolean.TRUE.equals(on.get("bubble_subscription_ring"))) {
            BubbleNet.get(c, "/subscriptions/me", (code, body) -> {
                if (code != 200 || body == null || !body.has("days_remaining")) return;
                p.edit().putString("sub_days", String.valueOf(body.optInt("days_remaining"))).apply();
                BubbleAlerts.subscriptionEnding(c, body.optInt("days_remaining"));
                afterRefresh(c);
            });
        }
        if (Boolean.TRUE.equals(on.get("bubble_busy_area")) && p.getBoolean("online", false)) {
            BubbleNet.get(c, "/drivers/me/busy-area", (code, body) -> {
                if (code != 200 || body == null) return;
                JSONObject area = body.optJSONObject("area");
                if (area == null) p.edit().remove("busy_json").apply();
                else p.edit().putString("busy_json", area.toString()).apply();
                afterRefresh(c);
            });
        }
        if (Boolean.TRUE.equals(on.get("quick_replies")) && ride(p) != null) {
            BubbleNet.get(c, "/quick-replies?side=driver", (code, body) -> {
                if (code != 200 || body == null) return;
                JSONArray texts = body.optJSONArray("texts");
                if (texts != null) p.edit().putString("quick_json", texts.toString()).apply();
            });
        }
    }

    private static void afterRefresh(Context c) {
        LauncherPlugin.wake(c);
        if (RadialMenu.isOpen()) RadialMenu.update(header(c), null);
    }

    /** <b>احتفالٌ صغيرٌ مرّةً في اليوم</b> حين يبلغ صافي اليوم الهدف (البند ٤٧) — نبضةُ الفقاعة واهتزازٌ قصير. */
    static void celebrateIfReached(Context c) {
        SharedPreferences p = prefs(c);
        if (!p.getBoolean("bubble_goal_ring", false)) return;
        String goal = p.getString("bubble_goal", null);
        String earned = p.getString("today_earned", null);
        if (!BubbleLogic.goalReached(earned, goal)) return;
        String today = new java.text.SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(new java.util.Date());
        if (today.equals(p.getString("goal_celebrated", null))) return;
        p.edit().putString("goal_celebrated", today).apply();
        StatusBubble.celebrate(c);
        buzz(c, new long[] {0, 60, 80, 60, 80, 120});
    }

    // ───────────────────────────── الاختيار

    private static void pick(Context c, String id) {
        SharedPreferences p = prefs(c);
        JSONObject ride = ride(p);
        String rideId = ride == null ? null : ride.optString("id", null);
        switch (id) {
            case "open":
                openApp(c, null);
                return;
            case "call":
            case "chat":
            case "last_ride":
                openApp(c, id);
                return;
            case "offline":
                openApp(c, "go_offline");
                return;
            case "navigate":
                if (ride != null && ride.has("nav_lat")) navigate(c, ride.optDouble("nav_lat"), ride.optDouble("nav_lng"));
                else openApp(c, null);
                return;
            case "busy": {
                JSONObject area = busy(p);
                if (area != null) navigate(c, area.optDouble("lat"), area.optDouble("lng"));
                return;
            }
            case "arrived":
                if (rideId == null) return;
                BubbleNet.post(c, "/rides/" + rideId + "/arrive", null, (code, body) -> done(c, code, "سُجّل وصولك", null));
                return;
            case "break_15":
            case "break_30": {
                int minutes = "break_15".equals(id) ? 15 : 30;
                JSONObject body = new JSONObject();
                try {
                    body.put("minutes", minutes);
                } catch (Exception ignored) {
                    // لا يقع
                }
                BubbleNet.post(c, "/drivers/me/break", body, (code, answer) -> {
                    if (code == 200 && answer != null && !answer.isNull("break_until")) {
                        String until = answer.optString("break_until");
                        p.edit().putString("break_until", until).apply();
                        BubbleAlerts.scheduleBreak(c, BubbleLogic.isoMillis(until));
                        StatusBubble.refresh(c);
                    }
                    done(c, code, "استراحة " + minutes + " دقيقة — لا عروضَ حتى تنتهي", null);
                });
                return;
            }
            case "break_end":
                BubbleNet.delete(c, "/drivers/me/break", (code, answer) -> {
                    if (code == 200) {
                        p.edit().remove("break_until").apply();
                        BubbleAlerts.cancelBreak(c);
                        StatusBubble.refresh(c);
                    }
                    done(c, code, "عدتَ إلى العروض", null);
                });
                return;
            case "road":
                RadialMenu.open(c, lastX, lastY, null, BubbleLogic.roadItems(), next -> pick(c, next));
                return;
            case "quick":
                RadialMenu.open(c, lastX, lastY, null, BubbleLogic.replyItems(replies(p)), next -> pick(c, next));
                return;
            case "back":
                open(c, lastX, lastY);
                return;
            default:
                break;
        }
        if (id.startsWith("road:")) {
            report(c, id.substring(5));
        } else if (id.startsWith("reply:") && rideId != null) {
            List<String> texts = replies(p);
            int i = Integer.parseInt(id.substring(6));
            if (i >= texts.size()) return;
            JSONObject body = new JSONObject();
            try {
                body.put("body", texts.get(i));
            } catch (Exception ignored) {
                // لا يقع
            }
            BubbleNet.post(c, "/rides/" + rideId + "/chat", body, (code, answer) -> done(c, code, "أُرسل: " + texts.get(i), "chat"));
        }
    }

    /** نصوصُ اللوحة إن وصلت، وإلا نصُّ الأمر حرفاً (الخلفيّةُ تعيده نفسَه حين لا صفّ). */
    static List<String> replies(SharedPreferences p) {
        List<String> out = new ArrayList<>();
        try {
            JSONArray texts = new JSONArray(p.getString("quick_json", "[]"));
            for (int i = 0; i < texts.length(); i++) out.add(texts.getString(i));
        } catch (Exception ignored) {
            // يبقى الافتراض
        }
        if (out.isEmpty()) {
            out.add("أنا في الطريق");
            out.add("وصلت");
            out.add("دقيقتين");
        }
        return out;
    }

    @SuppressLint("MissingPermission")
    static Location lastLocation(Context c) {
        LocationManager lm = c.getSystemService(LocationManager.class);
        if (lm == null) return null;
        Location best = null;
        for (String provider : new String[] {LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER, LocationManager.PASSIVE_PROVIDER}) {
            try {
                Location l = lm.getLastKnownLocation(provider);
                if (l != null && (best == null || l.getTime() > best.getTime())) best = l;
            } catch (Exception ignored) {
                // مزوّدٌ غائبٌ أو إذنٌ سُحب
            }
        }
        // **موضعٌ أقدمُ من دقيقتين لا يُبلَّغ به** — بلاغٌ في غير موضعه أسوأُ من لا بلاغ
        if (best != null && System.currentTimeMillis() - best.getTime() > 120_000) return null;
        return best;
    }

    private static void report(Context c, String kind) {
        Location here = lastLocation(c);
        if (here == null) {
            toast(c, "لا موقعَ حديثٌ للبلاغ — جرّب بعد لحظة");
            return;
        }
        JSONObject body = new JSONObject();
        try {
            body.put("kind", kind).put("lat", here.getLatitude()).put("lng", here.getLongitude());
        } catch (Exception ignored) {
            // لا يقع
        }
        BubbleNet.post(c, "/road-reports", body, (code, answer) -> done(c, code, "شكراً — وصل البلاغ", null));
    }

    /** <b>الطوارئ</b> (البند ٥٣) بعد العدّ التنازليّ — بباب الطوارئ القائم، ومعه الرحلةُ والموقعُ إن عُرفا. */
    static void emergency(Context context) {
        Context c = context.getApplicationContext();
        JSONObject ride = ride(prefs(c));
        JSONObject body = new JSONObject();
        try {
            body.put("app", "driver");
            if (ride != null && ride.has("id")) body.put("ride_id", ride.optString("id"));
            Location here = lastLocation(c);
            if (here != null) body.put("lat", here.getLatitude()).put("lng", here.getLongitude());
        } catch (Exception ignored) {
            // لا يقع
        }
        buzz(c, new long[] {0, 400});
        BubbleNet.post(c, "/emergency", body, (code, answer) -> {
            if (code >= 200 && code < 300) toast(c, "أُرسل تنبيهُ الطوارئ إلى فريق TAXO");
            else openApp(c, "emergency");
        });
    }

    private static void done(Context c, int code, String ok, String fallbackAction) {
        if (code >= 200 && code < 300) {
            toast(c, ok);
            buzz(c, new long[] {0, 40});
        } else if (code == 0 || code == 401) {
            openApp(c, fallbackAction);
        } else {
            toast(c, "تعذّر الآن — افتح التطبيق");
        }
    }

    static void openApp(Context c, String action) {
        Intent intent = new Intent(c, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        if (action != null) intent.putExtra(LauncherPlugin.EXTRA, action);
        try {
            c.startActivity(intent);
        } catch (Exception ignored) {
            // إطلاقٌ منعه النظام — الفقاعةُ تبقى
        }
    }

    static void navigate(Context c, double lat, double lng) {
        Intent nav = new Intent(Intent.ACTION_VIEW, Uri.parse(String.format(Locale.ROOT, "google.navigation:q=%.6f,%.6f", lat, lng)))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            c.startActivity(nav);
        } catch (Exception e) {
            try {
                c.startActivity(new Intent(Intent.ACTION_VIEW,
                        Uri.parse(String.format(Locale.ROOT, "geo:%.6f,%.6f?q=%.6f,%.6f", lat, lng, lat, lng)))
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } catch (Exception ignored) {
                toast(c, "لا تطبيقَ خرائط في الهاتف");
            }
        }
    }

    static void toast(Context c, String text) {
        try {
            Toast.makeText(c, text, Toast.LENGTH_SHORT).show();
        } catch (Exception ignored) {
            // لا نافذة
        }
    }

    static void buzz(Context c, long[] pattern) {
        Vibrator v = c.getSystemService(Vibrator.class);
        if (v == null || !v.hasVibrator()) return;
        try {
            if (android.os.Build.VERSION.SDK_INT >= 26) v.vibrate(VibrationEffect.createWaveform(pattern, -1));
            else v.vibrate(pattern, -1);
        } catch (Exception ignored) {
            // لا اهتزاز
        }
    }
}
