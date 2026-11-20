package ly.tajora.driver;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONObject;

import java.util.Locale;

/**
 * <b>ودجاتُ الكبتن الخمس</b> (أمرُ المالك ٢٠٢٦-١١-٢٠ الثامن) — بأسلوب ودجات الراكب: متّصلٌ أو غيرُ متّصلٍ مع أرباح اليوم · حلقةُ
 * الهدف اليوميّ · أيّامُ الاشتراك الباقية · أقربُ منطقةٍ مزدحمة و«اذهب إليها» · حالُ الرحلة أثناءها.
 *
 * <p><b>ترسم ما تقرؤه الفقاعةُ نفسُها من أبوابها</b> ({@code today_earned} و{@code sub_days} و{@code busy_json} يكتبها
 * {@link DriverBubbleMenu#refresh} من الخادم، و{@code bubble_ride} الويب) — <b>لا رقمَ مخترَع</b>، وما لا قيمةَ له حالٌ فارغةٌ تقول ذلك.
 * <b>ولا اسمَ راكبٍ ولا هاتف</b>. والمزوّداتُ مطفأةٌ في البيان، و{@link #sync} يُظهرها في المنتقي حين يشتعل {@code driver_widgets_plus}
 * ومفتاحُ بياناتها لبلد الكبتن، <b>ولا يُخفي ما وضعه على شاشته</b>.
 */
public final class TaxoWidgets {
    private TaxoWidgets() {}

    static final String[] KINDS = {"status", "goal", "subscription", "busy", "ride"};

    static Class<?> provider(String kind) {
        switch (kind) {
            case "status": return Status.class;
            case "goal": return Goal.class;
            case "subscription": return Subscription.class;
            case "busy": return Busy.class;
            default: return Ride.class;
        }
    }

    /** خالصة: <b>أيُعرض النوعُ في المنتقي؟</b> — المفتاحُ العامُّ ومفتاحُ البيانات التي يعرضها (البلدُ يملكهما). */
    static boolean listed(String kind, boolean plus, boolean goalRing, boolean subRing, boolean busyArea) {
        if (!plus) return false;
        switch (kind) {
            case "goal": return goalRing;
            case "subscription": return subRing;
            case "busy": return busyArea;
            default: return true;
        }
    }

    /** ما يظهر في المنتقي — <b>وما له ودجةٌ قائمةٌ يبقى</b> — ثم رسمُ كلِّ ما على الشاشة. */
    public static void sync(Context ctx) {
        SharedPreferences p = ctx.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        boolean plus = p.getBoolean("driver_widgets_plus", false);
        PackageManager pm = ctx.getPackageManager();
        AppWidgetManager manager = AppWidgetManager.getInstance(ctx);
        for (String kind : KINDS) {
            ComponentName name = new ComponentName(ctx, provider(kind));
            int[] ids = new int[0];
            try {
                ids = manager.getAppWidgetIds(name);
            } catch (Exception ignored) {
                // المزوّدُ مطفأ — لا ودجاتٍ له
            }
            boolean want = listed(kind, plus, p.getBoolean("bubble_goal_ring", false), p.getBoolean("bubble_subscription_ring", false),
                    p.getBoolean("bubble_busy_area", false)) || ids.length > 0;
            int state = want ? PackageManager.COMPONENT_ENABLED_STATE_ENABLED : PackageManager.COMPONENT_ENABLED_STATE_DEFAULT;
            if (pm.getComponentEnabledSetting(name) != state) pm.setComponentEnabledSetting(name, state, PackageManager.DONT_KILL_APP);
            for (int id : ids) manager.updateAppWidget(id, render(ctx, kind, manager.getAppWidgetOptions(id)));
        }
    }

    /** خالصة: {@code 0} صغيرة · {@code 1} متوسّطة · {@code 2} كبيرة. */
    static int sizeClass(int widthDp, int heightDp) {
        if (heightDp >= 170 && widthDp >= 250) return 2;
        if (widthDp >= 230) return 1;
        return 0;
    }

    private static PendingIntent open(Context ctx, String action, int code) {
        Intent intent = new Intent(ctx, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (action != null) intent.putExtra(LauncherPlugin.EXTRA, action);
        return PendingIntent.getActivity(ctx, code, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    private static int code(String kind, int slot) {
        for (int i = 0; i < KINDS.length; i++) if (KINDS[i].equals(kind)) return 3300 + i * 10 + slot;
        return 3299;
    }

    /** أداةُ رسمٍ صغيرة: تُظهر ما يُكتب فيه وتُخفي ما سواه. */
    static final class Card {
        final Context ctx;
        final RemoteViews v;
        final String kind;

        Card(Context ctx, String kind) {
            this.ctx = ctx;
            this.kind = kind;
            v = new RemoteViews(ctx.getPackageName(), R.layout.tw_widget);
            int[] hidden = {R.id.tw_car, R.id.tw_car_s, R.id.tw_art, R.id.tw_dot, R.id.tw_mark, R.id.tw_icon, R.id.tw_bigrow, R.id.tw_sub,
                    R.id.tw_tiles, R.id.tw_actions, R.id.tw_btn, R.id.tw_btn2, R.id.tw_bar, R.id.tw_ringbox, R.id.tw_quick, R.id.tw_place,
                    R.id.wo_root};
            for (int id : hidden) v.setViewVisibility(id, View.GONE);
            v.setViewVisibility(R.id.tw_body, View.VISIBLE);
            v.setViewVisibility(R.id.tw_fill, View.VISIBLE);
            v.setTextViewText(R.id.tw_title, "");
        }

        Card title(String text) { v.setTextViewText(R.id.tw_title, text); return this; }
        Card dot(boolean live) {
            v.setViewVisibility(R.id.tw_dot, View.VISIBLE);
            v.setImageViewResource(R.id.tw_dot, live ? R.drawable.tw_dot_ok : R.drawable.tw_dot);
            return this;
        }
        Card icon(int res) { v.setViewVisibility(R.id.tw_icon, View.VISIBLE); v.setImageViewResource(R.id.tw_icon, res); return this; }
        Card big(String value, String unit) {
            v.setViewVisibility(R.id.tw_bigrow, View.VISIBLE);
            v.setTextViewText(R.id.tw_big, value);
            v.setTextViewText(R.id.tw_unit, unit == null ? "" : unit);
            return this;
        }
        Card sub(String text) {
            if (text == null || text.isEmpty()) return this;
            v.setViewVisibility(R.id.tw_sub, View.VISIBLE);
            v.setTextViewText(R.id.tw_sub, text);
            return this;
        }
        Card car() {
            v.setViewVisibility(R.id.tw_car_s, View.VISIBLE);
            v.setImageViewResource(R.id.tw_car_s, R.drawable.tw_car_economy);
            return this;
        }
        Card button(String text, String action, int slot) {
            return button(text, open(ctx, action, code(kind, slot)));
        }
        Card button(String text, PendingIntent intent) {
            v.setViewVisibility(R.id.tw_actions, View.VISIBLE);
            v.setViewVisibility(R.id.tw_btn, View.VISIBLE);
            v.setTextViewText(R.id.tw_btn, text);
            v.setOnClickPendingIntent(R.id.tw_btn, intent);
            return this;
        }
        Card bar(float value) {
            v.setViewVisibility(R.id.tw_bar, View.VISIBLE);
            v.setProgressBar(R.id.tw_bar, 100, Math.round(Math.max(0f, Math.min(1f, value)) * 100), false);
            return this;
        }
        Card tap(String action) { v.setOnClickPendingIntent(R.id.tw_root, open(ctx, action, code(kind, 0))); return this; }
    }

    static RemoteViews render(Context ctx, String kind, Bundle options) {
        SharedPreferences p = ctx.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        int w = options == null ? 250 : options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 250);
        int h = WidgetSignedOut.heightDp(ctx, options, 110);
        int size = sizeClass(w, h);
        Card c = new Card(ctx, kind);
        c.tap(null);
        boolean plus = p.getBoolean("driver_widgets_plus", false);
        boolean signedIn = p.getBoolean("signed_in", false);
        if (!plus || !signedIn) {
            c.v.setViewVisibility(R.id.tw_body, View.GONE);
            c.v.setViewVisibility(R.id.wo_root, View.VISIBLE);
            WidgetSignedOut.show(ctx, c.v, h, !plus ? "هذه الودجة غير متاحة الآن" : "حالُك وأرباحُ يومك هنا بعد الدخول",
                    !plus ? "افتح TAXO" : "سجّل الدخول", open(ctx, null, code(kind, 9)));
            return c.v;
        }
        boolean online = p.getBoolean("online", false);
        String unit = p.getString("currency_label", "");
        String earned = p.getString("today_earned", null);
        JSONObject ride = DriverBubbleMenu.ride(p);
        switch (kind) {
            case "status":
                c.dot(online).title(online ? "متّصل" : "غير متّصل");
                if (earned != null) c.big(earned, unit).sub("أرباح اليوم" + rides(p));
                else c.sub("أرباحُ اليوم تظهر بعد فتح التطبيق");
                c.button(online ? "أوقف الاستقبال" : "اتّصل الآن", online ? "go_offline" : "go_online", 1);
                if (size > 0) c.car();
                break;
            case "goal": {
                String goal = p.getString("bubble_goal", null);
                if (goal == null || goal.isEmpty()) {
                    c.title("هدفي اليوميّ").icon(R.drawable.tw_g_flag).sub("حدّد هدفَك اليوميَّ من إعدادات الفقاعة");
                    break;
                }
                float fraction = BubbleLogic.goalFraction(earned, goal);
                c.v.setViewVisibility(R.id.tw_body, View.GONE);
                c.v.setViewVisibility(R.id.tw_ringbox, View.VISIBLE);
                c.v.setImageViewResource(R.id.tw_ring_icon, R.drawable.tw_g_flag);
                c.v.setProgressBar(R.id.tw_ring, 100, Math.round(fraction * 100), false);
                c.v.setTextViewText(R.id.tw_ring_big, Math.round(fraction * 100) + "%");
                c.v.setTextViewText(R.id.tw_ring_sub, (earned == null ? "0" : earned) + " / " + goal + (unit == null || unit.isEmpty() ? "" : " " + unit));
                break;
            }
            case "subscription": {
                String days = p.getString("sub_days", null);
                c.title("اشتراكي").icon(R.drawable.tw_g_receipt_long);
                if (days == null) {
                    c.sub("يظهر هنا ما بقي من اشتراكك");
                    break;
                }
                int n;
                try {
                    n = Integer.parseInt(days);
                } catch (NumberFormatException ignored) {
                    n = 0;
                }
                c.big(days, "1".equals(days) ? "يوم باقٍ" : "أيام باقية").bar(BubbleLogic.subscriptionFraction(n));
                if (n <= 3) c.button("جدّد الاشتراك", null, 1);
                break;
            }
            case "busy": {
                JSONObject area = DriverBubbleMenu.busy(p);
                c.title("أقرب منطقة مزدحمة").icon(R.drawable.tw_g_my_location);
                if (!online) {
                    c.sub("اتّصل لترى أين الطلبُ الآن").button("اتّصل الآن", "go_online", 1);
                } else if (area == null) {
                    c.sub("لا منطقةَ مزدحمة قريبة الآن");
                } else {
                    c.sub(BubbleLogic.busyLine(area.optString("name", null), area.optDouble("distance_km", 0)));
                    Intent nav = new Intent(Intent.ACTION_VIEW, Uri.parse(String.format(Locale.ROOT, "google.navigation:q=%.6f,%.6f",
                            area.optDouble("lat"), area.optDouble("lng"))));
                    c.button("اذهب إليها", PendingIntent.getActivity(ctx, code(kind, 1), nav,
                            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT));
                }
                break;
            }
            default: // ride
                c.title("رحلتي الحالية");
                if (ride == null) {
                    c.sub(online ? "بانتظار طلبٍ جديد" : "لا رحلة الآن");
                    break;
                }
                String status = ride.optString("status", "");
                c.dot(true).sub("accepted".equals(status) ? "في الطريق إلى الراكب"
                        : "arrived".equals(status) ? "وصلتَ — بانتظار الراكب" : "في الرحلة إلى الوجهة").button("افتح الرحلة", null, 1);
                if (size > 0) c.car();
                break;
        }
        return c.v;
    }

    static String rides(SharedPreferences p) {
        String n = p.getString("today_rides", null);
        return n == null ? "" : " · " + n + " " + ("1".equals(n) ? "رحلة" : "رحلات");
    }

    /** الأصلُ المشترك: يرسم كلَّ ودجةٍ من نوعه، ويستيقظ على {@code LAUNCHER_CHANGED}. */
    public abstract static class Base extends AppWidgetProvider {
        abstract String kind();

        @Override
        public void onUpdate(Context ctx, AppWidgetManager manager, int[] ids) {
            for (int id : ids) manager.updateAppWidget(id, render(ctx, kind(), manager.getAppWidgetOptions(id)));
        }

        @Override
        public void onAppWidgetOptionsChanged(Context ctx, AppWidgetManager manager, int id, Bundle options) {
            manager.updateAppWidget(id, render(ctx, kind(), options));
        }

        @Override
        public void onReceive(Context ctx, Intent intent) {
            super.onReceive(ctx, intent);
            if (LauncherPlugin.CHANGED.equals(intent.getAction())) {
                AppWidgetManager manager = AppWidgetManager.getInstance(ctx);
                onUpdate(ctx, manager, manager.getAppWidgetIds(new ComponentName(ctx, getClass())));
            }
        }
    }

    public static final class Status extends Base { String kind() { return "status"; } }
    public static final class Goal extends Base { String kind() { return "goal"; } }
    public static final class Subscription extends Base { String kind() { return "subscription"; } }
    public static final class Busy extends Base { String kind() { return "busy"; } }
    public static final class Ride extends Base { String kind() { return "ride"; } }
}
