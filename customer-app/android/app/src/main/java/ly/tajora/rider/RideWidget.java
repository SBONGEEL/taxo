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
 * <b>أداةُ «اطلب رحلة»</b> (SPEC §١٠٣ B/20) — زرّا «المنزل» و«العمل» يفتحان التطبيقَ بفعلهما، <b>والويبُ يطلب إلى المكان المحفوظ</b>
 * ({@code ride_home} · {@code ride_work})، أو يفتح «أماكني» إن لم يُحفظ بعد. <b>لا عنوانَ ولا إحداثيّاتٍ هنا</b>: الأداةُ على الشاشة
 * الرئيسيّة يراها من يمسك الهاتف. ومطفأةً لدولته ({@code ride_widget=false}) تعرض «افتح التطبيق» وحدَه.
 *
 * <p><b>على تصميم ودجات TAXO</b> (أمرُ المالك ٢١/١١: «كلُّ الودجات» على صورته المرجعيّة) — شريطٌ 4×1 من المولِّد
 * ({@code tw_bar_ride}): عنوانٌ وعلامة، زرّان مستديران، سيارةُ TAXO؛ <b>والمكوّنُ هو هو</b> فلا تنكسر أداةٌ وضعها أحدٌ على شاشته.
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
        RemoteViews views = new RemoteViews(ctx.getPackageName(), R.layout.tw_bar_ride);
        boolean enabled = prefs.getBoolean("ride_widget", false);
        int buttons = enabled ? View.VISIBLE : View.GONE;
        views.setViewVisibility(R.id.tw_t0, buttons);
        views.setViewVisibility(R.id.tw_t1, buttons);
        views.setTextViewText(R.id.tw_title, enabled ? "اطلب رحلة" : "افتح التطبيق");
        if (enabled) {
            views.setOnClickPendingIntent(R.id.tw_t0, open(ctx, "ride_home", 61));
            views.setOnClickPendingIntent(R.id.tw_t1, open(ctx, "ride_work", 62));
        }
        views.setOnClickPendingIntent(R.id.tw_root, open(ctx, null, 63));
        return views;
    }
}
