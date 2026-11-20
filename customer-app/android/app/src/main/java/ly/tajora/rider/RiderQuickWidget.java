package ly.tajora.rider;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * <b>ودجةُ الراكب الجديدة</b> (أمرُ المالك ٢٠/١١ الرابع، الجزء ٣، SPEC §١١٠) — خلف {@code rider_widgets_plus}.
 *
 * <p>«إلى أين؟» يفتح التطبيقَ جاهزاً للكتابة؛ <b>«البيت» و«العمل» والوجهاتُ الأخيرة تفتح ورقةَ الطلب للتأكيد — لا رحلةَ بلا تأكيدٍ أبداً</b>؛
 * وحالُ الرحلة الحيّ (وقتُ الوصول والسيّارة واللوحة) ممّا كتبه التطبيق. <b>تتحدّث حين يتغيّر الحال</b> لا بمؤقّت، <b>وتقول «سجّل الدخول»</b>
 * لمن خرج. والصغيرةُ «إلى أين؟» وحدَها، والمتوسّطةُ معها البيتُ والعمل، والكبيرةُ معها الأخيرةُ والرحلة.
 */
public class RiderQuickWidget extends AppWidgetProvider {

    @Override
    public void onUpdate(Context ctx, AppWidgetManager manager, int[] ids) {
        for (int id : ids) manager.updateAppWidget(id, render(ctx, manager.getAppWidgetOptions(id)));
    }

    @Override
    public void onAppWidgetOptionsChanged(Context ctx, AppWidgetManager manager, int id, Bundle options) {
        manager.updateAppWidget(id, render(ctx, options));
    }

    @Override
    public void onReceive(Context ctx, Intent intent) {
        super.onReceive(ctx, intent);
        if (LauncherPlugin.CHANGED.equals(intent.getAction())) {
            AppWidgetManager manager = AppWidgetManager.getInstance(ctx);
            onUpdate(ctx, manager, manager.getAppWidgetIds(new ComponentName(ctx, RiderQuickWidget.class)));
        }
    }

    /** خالصة: {@code 0} صغيرة · {@code 1} متوسّطة · {@code 2} كبيرة. */
    static int sizeClass(int minWidthDp, int minHeightDp) {
        if (minHeightDp >= 150) return 2;
        if (minHeightDp >= 100 || minWidthDp >= 250) return 1;
        return 0;
    }

    private static PendingIntent open(Context ctx, String action, int code) {
        Intent intent = new Intent(ctx, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (action != null) intent.putExtra(LauncherPlugin.EXTRA, action);
        return PendingIntent.getActivity(ctx, code, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    static RemoteViews render(Context ctx, Bundle options) {
        SharedPreferences p = ctx.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        RemoteViews v = new RemoteViews(ctx.getPackageName(), R.layout.widget_rider_quick);
        int w = options == null ? 250 : options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 250);
        int h = options == null ? 110 : options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 110);
        int size = sizeClass(w, h);
        boolean enabled = p.getBoolean("rider_widgets_plus", false);
        boolean signedIn = p.getBoolean("signed_in", false);
        int[] recentIds = {R.id.rq_recent0, R.id.rq_recent1, R.id.rq_recent2};
        v.setOnClickPendingIntent(R.id.rq_root, open(ctx, null, 81));
        for (int id : recentIds) v.setViewVisibility(id, View.GONE);
        v.setViewVisibility(R.id.rq_ride, View.GONE);
        if (!enabled || !signedIn) {
            // **بطاقةٌ تملأ الودجة** (٢٠/١١ السادس، البند ٣) — لا سطرٌ في أعلاها وفراغٌ تحته
            v.setViewVisibility(R.id.rq_where, View.GONE);
            v.setViewVisibility(R.id.rq_places, View.GONE);
            WidgetSignedOut.show(ctx, v, h, signedIn ? "رحلتُك التالية بلمسة" : "اطلب رحلتك بلمسةٍ من هنا بعد الدخول",
                    signedIn ? "اطلب رحلة" : "سجّل الدخول", open(ctx, null, 82));
            return v;
        }
        v.setViewVisibility(R.id.wo_root, View.GONE);
        v.setViewVisibility(R.id.rq_where, View.VISIBLE);
        v.setTextViewText(R.id.rq_where, "إلى أين؟");
        v.setOnClickPendingIntent(R.id.rq_where, open(ctx, "where_to", 83));
        JSONObject ride = RiderBubble.ride(p);
        if (ride != null && RiderBubbleLogic.showsFor(ride.optString("phase"))) {
            v.setTextViewText(R.id.rq_ride, String.join("\n", RiderBubble.header(ride)));
            v.setViewVisibility(R.id.rq_ride, View.VISIBLE);
            v.setViewVisibility(R.id.rq_places, View.GONE);
            v.setOnClickPendingIntent(R.id.rq_ride, open(ctx, null, 84));
            return v;
        }
        JSONObject places = null;
        try {
            places = new JSONObject(p.getString("rider_places", "{}"));
        } catch (Exception ignored) {
            // لا أماكن
        }
        boolean home = places != null && places.optBoolean("home", false);
        boolean work = places != null && places.optBoolean("work", false);
        if (size >= 1 && (home || work)) {
            v.setViewVisibility(R.id.rq_places, View.VISIBLE);
            v.setViewVisibility(R.id.rq_home, home ? View.VISIBLE : View.GONE);
            v.setViewVisibility(R.id.rq_work, work ? View.VISIBLE : View.GONE);
            v.setOnClickPendingIntent(R.id.rq_home, open(ctx, "ride_home", 85));
            v.setOnClickPendingIntent(R.id.rq_work, open(ctx, "ride_work", 86));
        } else {
            v.setViewVisibility(R.id.rq_places, View.GONE);
        }
        if (size == 2) {
            try {
                JSONArray recent = new JSONArray(p.getString("rider_recent", "[]"));
                for (int i = 0; i < recent.length() && i < recentIds.length; i++) {
                    v.setTextViewText(recentIds[i], "↺  " + recent.getString(i));
                    v.setViewVisibility(recentIds[i], View.VISIBLE);
                    v.setOnClickPendingIntent(recentIds[i], open(ctx, "recent_" + i, 87 + i));
                }
            } catch (Exception ignored) {
                // لا أخيرة
            }
        }
        return v;
    }
}
