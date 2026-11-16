package ly.tajora.driver;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.widget.RemoteViews;

/**
 * <b>أداةُ الشاشة الرئيسيّة</b> (SPEC §١٠٣ المرحلة A/5): أرباحُ اليوم ورحلاتُه وزرُّ الاتّصال.
 *
 * <p><b>لا حسابَ هنا ولا نداء</b>: النصّان كما صاغهما الويبُ من {@code /drivers/me/earnings} (§14 — المالُ يُحسب في الخلفيّة)،
 * ويُكتبان عبر {@code Launcher.setPrefs} حين تتغيّر. وزرُّ الاتّصال <b>يفتح التطبيقَ بفعله</b> كالبلاطة.
 * ومطفأةً لدولته ({@code widget=false}) تعرض «افتح التطبيق» وحدَه — لا أرقامَ قديمةً تُقرأ خبراً.
 */
public class EarningsWidget extends AppWidgetProvider {

    @Override
    public void onUpdate(Context ctx, AppWidgetManager manager, int[] ids) {
        for (int id : ids) manager.updateAppWidget(id, render(ctx));
    }

    @Override
    public void onReceive(Context ctx, Intent intent) {
        super.onReceive(ctx, intent);
        if (LauncherPlugin.CHANGED.equals(intent.getAction())) {
            AppWidgetManager manager = AppWidgetManager.getInstance(ctx);
            int[] ids = manager.getAppWidgetIds(new ComponentName(ctx, EarningsWidget.class));
            onUpdate(ctx, manager, ids);
        }
    }

    private static PendingIntent open(Context ctx, String action, int code) {
        Intent intent = new Intent(ctx, MainActivity.class)
            .putExtra(LauncherPlugin.EXTRA, action)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(ctx, code, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    static RemoteViews render(Context ctx) {
        SharedPreferences prefs = ctx.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        RemoteViews views = new RemoteViews(ctx.getPackageName(), R.layout.widget_earnings);
        boolean enabled = prefs.getBoolean("widget", false);
        boolean online = prefs.getBoolean("online", false);
        if (enabled) {
            views.setTextViewText(R.id.widget_earnings, prefs.getString("widget_earnings", "—"));
            views.setTextViewText(R.id.widget_rides, prefs.getString("widget_rides", "—"));
            views.setTextViewText(R.id.widget_toggle, online ? "افصل" : "اتّصل");
            views.setOnClickPendingIntent(R.id.widget_toggle, open(ctx, online ? "go_offline" : "go_online", 51));
        } else {
            views.setTextViewText(R.id.widget_earnings, "—");
            views.setTextViewText(R.id.widget_rides, "افتح التطبيق");
            views.setTextViewText(R.id.widget_toggle, "افتح");
            views.setOnClickPendingIntent(R.id.widget_toggle, open(ctx, "home", 52));
        }
        views.setOnClickPendingIntent(R.id.widget_root, open(ctx, enabled ? "earnings" : "home", 53));
        return views;
    }
}
