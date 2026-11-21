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
import android.os.Build;
import android.os.Bundle;
import android.util.ArrayMap;
import android.util.SizeF;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONObject;

import java.util.Locale;
import java.util.Map;

/**
 * <b>ودجاتُ الكبتن الخمس</b> (أمرُ المالك ٢٠٢٦-١١-٢٠ الثامن؛ وأُعيد تصميمُها ٢١/١١ على صورته المرجعيّة بهويّة TAXO) — متّصلٌ أو غيرُ
 * متّصلٍ مع أرباح اليوم · حلقةُ الهدف اليوميّ · أيّامُ الاشتراك الباقية · أقربُ منطقةٍ مزدحمة و«اذهب إليها» · حالُ الرحلة أثناءها.
 *
 * <p><b>تخطيطٌ لكلِّ نوعٍ ولكلِّ حجم</b> ({@link TwLayouts}، مولَّدٌ من {@code tools/gen-android-widgets.py})، والثلاثةُ معاً على أندرويد ١٢+،
 * <b>والمعاينةُ في المنتقي هي التخطيطُ نفسُه</b>. <b>ونصوصُ التخطيط الافتراضيّةُ هي الحالُ الفارغة</b>: لا رقمَ في المعاينة.
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
            for (int id : ids) manager.updateAppWidget(id, views(ctx, kind, manager.getAppWidgetOptions(id)));
        }
        legacy(ctx, pm, manager, DriverWidget.class);
    }

    /** <b>ودجةٌ قديمةٌ ترسمها ودجةٌ جديدة</b> (٢١/١١): تبقى ما دامت لها نسخةٌ موضوعة، وتُخفى من المنتقي وإلا — فلا تتكرّر فيه. */
    static void legacy(Context ctx, PackageManager pm, AppWidgetManager manager, Class<?> cls) {
        ComponentName name = new ComponentName(ctx, cls);
        int[] ids = new int[0];
        try {
            ids = manager.getAppWidgetIds(name);
        } catch (Exception ignored) {
            // مطفأة — لا نسخ
        }
        int state = ids.length > 0 ? PackageManager.COMPONENT_ENABLED_STATE_DEFAULT : PackageManager.COMPONENT_ENABLED_STATE_DISABLED;
        if (pm.getComponentEnabledSetting(name) != state) pm.setComponentEnabledSetting(name, state, PackageManager.DONT_KILL_APP);
    }

    /** خالصة: {@code 0} صغيرة · {@code 1} متوسّطة · {@code 2} كبيرة (ما قبل أندرويد ١٢). */
    static int sizeClass(int widthDp, int heightDp) {
        if (heightDp >= 170 && widthDp >= 250) return 2;
        if (widthDp >= 230) return 1;
        return 0;
    }

    /** خالصة: «يوم باقٍ» للواحد، و«أيام باقية» من ٢ إلى ١٠، و«يوماً باقياً» فوقها. */
    static String daysUnit(int n) {
        if (n == 1) return "يوم باقٍ";
        if (n >= 2 && n <= 10) return "أيام باقية";
        return "يوماً باقياً";
    }

    /** الثلاثةُ معاً على أندرويد ١٢+ (يختار المشغِّل)، وواحدٌ بالمقاس قبله. */
    static RemoteViews views(Context ctx, String kind, Bundle options) {
        if (Build.VERSION.SDK_INT >= 31) {
            Map<SizeF, RemoteViews> map = new ArrayMap<>();
            map.put(new SizeF(100f, 100f), render(ctx, kind, 0));
            map.put(new SizeF(230f, 100f), render(ctx, kind, 1));
            map.put(new SizeF(230f, 200f), render(ctx, kind, 2));
            return new RemoteViews(map);
        }
        int w = options == null ? 250 : options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 250);
        int h = WidgetSignedOut.heightDp(ctx, options, 110);
        return render(ctx, kind, sizeClass(w, h));
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

    /** أداةُ رسمٍ صغيرة على تخطيط النوع والحجم؛ <b>والمعرّفُ الغائبُ عن تخطيطٍ يُتجاوَز</b>. */
    static final class W {
        final Context ctx;
        final RemoteViews v;
        final String kind;
        final int size;

        W(Context ctx, String kind, int size) {
            this.ctx = ctx;
            this.kind = kind;
            this.size = size;
            v = new RemoteViews(ctx.getPackageName(), TwLayouts.of(kind, size));
        }

        W text(int id, String s) { v.setTextViewText(id, s == null ? "" : s); return this; }
        W show(int id, boolean on) { v.setViewVisibility(id, on ? View.VISIBLE : View.GONE); return this; }
        W img(int id, int res) { v.setImageViewResource(id, res); return this; }
        W click(int id, String action, int slot) { v.setOnClickPendingIntent(id, open(ctx, action, code(kind, slot))); return this; }
        W click(int id, PendingIntent intent) { v.setOnClickPendingIntent(id, intent); return this; }
        W bar(int id, float f) {
            v.setProgressBar(id, 100, Math.round(Math.max(0f, Math.min(1f, f)) * 100), false);
            return this;
        }
        /** زرٌّ بنصّه وفعله — والنصُّ في {@code tw_btn_t} إن كان للزرِّ نصٌّ داخليّ. */
        W button(String label, String action, int slot) {
            return show(R.id.tw_btn, true).text(R.id.tw_btn_t, label).click(R.id.tw_btn, action, slot);
        }
    }

    static RemoteViews render(Context ctx, String kind, int size) {
        SharedPreferences p = ctx.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        boolean plus = p.getBoolean("driver_widgets_plus", false);
        if (!plus || !p.getBoolean("signed_in", false)) {
            RemoteViews v = new RemoteViews(ctx.getPackageName(), R.layout.tw_signed_out);
            WidgetSignedOut.show(ctx, v, size == 1 ? 110 : 170, !plus ? "هذه الودجة غير متاحة الآن" : "حالُك وأرباحُ يومك هنا بعد الدخول",
                    !plus ? "افتح TAXO" : "سجّل الدخول", open(ctx, null, code(kind, 9)));
            v.setOnClickPendingIntent(R.id.tw_root, open(ctx, null, code(kind, 9)));
            return v;
        }
        W c = new W(ctx, kind, size);
        c.click(R.id.tw_root, null, 0);
        boolean online = p.getBoolean("online", false);
        String unit = p.getString("currency_label", "");
        String earned = p.getString("today_earned", null);
        switch (kind) {
            case "status":
                c.text(R.id.tw_title, online ? "متّصل" : "غير متّصل").img(R.id.tw_dot, online ? R.drawable.tw_dot_ok : R.drawable.tw_dot_off);
                if (earned != null) {
                    c.show(R.id.tw_bigrow, true).text(R.id.tw_big, earned).text(R.id.tw_unit, unit).text(R.id.tw_sub, "أرباح اليوم" + rides(p));
                } else {
                    c.show(R.id.tw_bigrow, false).text(R.id.tw_sub, "أرباحُ اليوم تظهر بعد فتح التطبيق");
                }
                c.button(online ? "أوقف الاستقبال" : "اتّصل الآن", online ? "go_offline" : "go_online", 1);
                break;
            case "goal": {
                String goal = p.getString("bubble_goal", null);
                if (goal == null || goal.isEmpty()) {
                    c.text(R.id.tw_big, "").text(R.id.tw_ring_t, "").bar(R.id.tw_ring, 0).text(R.id.tw_sub, "حدّد هدفَك اليوميَّ من إعدادات الفقاعة");
                    break;
                }
                float fraction = BubbleLogic.goalFraction(earned, goal);
                int pct = Math.round(fraction * 100);
                String of = (earned == null ? "0" : earned) + " / " + goal + (unit == null || unit.isEmpty() ? "" : " " + unit);
                c.bar(R.id.tw_ring, fraction).text(R.id.tw_ring_t, pct + "%").text(R.id.tw_big, earned == null ? "0" : earned)
                        .text(R.id.tw_sub, size == 0 ? of : "من هدفك " + goal + (unit == null || unit.isEmpty() ? "" : " " + unit));
                break;
            }
            case "subscription": {
                String days = p.getString("sub_days", null);
                c.click(R.id.tw_root, null, 0);
                if (days == null) {
                    c.show(R.id.tw_bigrow, false).show(R.id.tw_bar, false).show(R.id.tw_btn, false).text(R.id.tw_sub, "يظهر هنا ما بقي من اشتراكك");
                    break;
                }
                int n;
                try {
                    n = Integer.parseInt(days);
                } catch (NumberFormatException ignored) {
                    n = 0;
                }
                c.show(R.id.tw_bigrow, true).text(R.id.tw_big, days).text(R.id.tw_unit, daysUnit(n)).show(R.id.tw_bar, true)
                        .bar(R.id.tw_bar, BubbleLogic.subscriptionFraction(n)).text(R.id.tw_sub, n <= 3 ? "اشتراكك ينتهي قريباً" : "اشتراكك فعّال");
                if (n <= 3) c.button("جدّد الاشتراك", null, 1);
                else c.show(R.id.tw_btn, false);
                break;
            }
            case "busy": {
                JSONObject area = DriverBubbleMenu.busy(p);
                if (!online) {
                    c.text(R.id.tw_sub, "اتّصل لترى أين الطلبُ الآن").button("اتّصل الآن", "go_online", 1);
                } else if (area == null) {
                    c.text(R.id.tw_sub, "لا منطقةَ مزدحمة قريبة الآن").show(R.id.tw_btn, false);
                } else {
                    c.text(R.id.tw_sub, BubbleLogic.busyLine(area.optString("name", null), area.optDouble("distance_km", 0)));
                    Intent nav = new Intent(Intent.ACTION_VIEW, Uri.parse(String.format(Locale.ROOT, "google.navigation:q=%.6f,%.6f",
                            area.optDouble("lat"), area.optDouble("lng"))));
                    c.show(R.id.tw_btn, true).text(R.id.tw_btn_t, "اذهب إليها").click(R.id.tw_btn, PendingIntent.getActivity(ctx, code(kind, 1), nav,
                            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT));
                }
                break;
            }
            default: { // ride
                JSONObject ride = DriverBubbleMenu.ride(p);
                if (ride == null) {
                    c.img(R.id.tw_dot, R.drawable.tw_dot_off).text(R.id.tw_sub, online ? "بانتظار طلبٍ جديد" : "لا رحلة الآن").show(R.id.tw_btn, false);
                    break;
                }
                String status = ride.optString("status", "");
                c.img(R.id.tw_dot, R.drawable.tw_dot_ok).text(R.id.tw_sub, "accepted".equals(status) ? "في الطريق إلى الراكب"
                        : "arrived".equals(status) ? "وصلتَ — بانتظار الراكب" : "في الرحلة إلى الوجهة").button("افتح الرحلة", null, 1);
                break;
            }
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
            for (int id : ids) manager.updateAppWidget(id, views(ctx, kind(), manager.getAppWidgetOptions(id)));
        }

        @Override
        public void onAppWidgetOptionsChanged(Context ctx, AppWidgetManager manager, int id, Bundle options) {
            manager.updateAppWidget(id, views(ctx, kind(), options));
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
