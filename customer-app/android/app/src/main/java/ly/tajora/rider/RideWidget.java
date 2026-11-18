package ly.tajora.rider;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.view.View;
import android.widget.RemoteViews;

/**
 * <b>أداةُ «اطلب رحلة»</b> (SPEC §١٠٣ B/20) — زرّا «البيت» و«العمل» يفتحان التطبيقَ بفعلهما، <b>والويبُ يطلب إلى المكان المحفوظ</b>
 * ({@code ride_home} · {@code ride_work})، أو يفتح «أماكني» إن لم يُحفظ بعد. <b>لا عنوانَ ولا إحداثيّاتٍ هنا</b>: الأداةُ على الشاشة
 * الرئيسيّة يراها من يمسك الهاتف. ومطفأةً لدولته ({@code ride_widget=false}) تعرض «افتح التطبيق» وحدَه.
 */
public class RideWidget extends AppWidgetProvider {

    @Override
    public void onUpdate(Context ctx, AppWidgetManager manager, int[] ids) {
        for (int id : ids) manager.updateAppWidget(id, render(ctx));
    }

    @Override
    public void onReceive(Context ctx, Intent intent) {
        super.onReceive(ctx, intent);
        if (LauncherPlugin.CHANGED.equals(intent.getAction())) {
            AppWidgetManager manager = AppWidgetManager.getInstance(ctx);
            int[] ids = manager.getAppWidgetIds(new ComponentName(ctx, RideWidget.class));
            onUpdate(ctx, manager, ids);
        }
    }

    private static PendingIntent open(Context ctx, String action, int code) {
        Intent intent = new Intent(ctx, MainActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (action != null) intent.putExtra(LauncherPlugin.EXTRA, action);
        return PendingIntent.getActivity(ctx, code, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    static RemoteViews render(Context ctx) {
        SharedPreferences prefs = ctx.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        RemoteViews views = new RemoteViews(ctx.getPackageName(), R.layout.widget_ride);
        boolean enabled = prefs.getBoolean("ride_widget", false);
        int buttons = enabled ? View.VISIBLE : View.GONE;
        views.setViewVisibility(R.id.ride_widget_home, buttons);
        views.setViewVisibility(R.id.ride_widget_work, buttons);
        views.setTextViewText(R.id.ride_widget_title, enabled ? "اطلب رحلة" : "افتح التطبيق");
        if (enabled) {
            views.setOnClickPendingIntent(R.id.ride_widget_home, open(ctx, "ride_home", 61));
            views.setOnClickPendingIntent(R.id.ride_widget_work, open(ctx, "ride_work", 62));
        }
        views.setOnClickPendingIntent(R.id.ride_widget_root, open(ctx, null, 63));
        return views;
    }
}
