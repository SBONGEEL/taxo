package ly.tajora.driver;

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
 * <b>أداةُ الشاشة الرئيسيّة</b> (SPEC §١٠٣ المرحلة A/5): أرباحُ اليوم ورحلاتُه وزرُّ الاتّصال.
 *
 * <p><b>لا حسابَ هنا ولا نداء</b>: النصّان كما صاغهما الويبُ من {@code /drivers/me/earnings} (§14 — المالُ يُحسب في الخلفيّة)،
 * ويُكتبان عبر {@code Launcher.setPrefs} حين تتغيّر. وزرُّ الاتّصال <b>يفتح التطبيقَ بفعله</b> كالبلاطة.
 * ومطفأةً لدولته ({@code widget=false}) تعرض «افتح التطبيق» وحدَه — لا أرقامَ قديمةً تُقرأ خبراً.
 *
 * <p><b>على تصميم ودجات TAXO</b> (أمرُ المالك ٢١/١١) — شريطٌ 4×1 من المولِّد ({@code tw_bar_earn}): الحالُ بنقطته، والمبلغُ كما
 * كتبه الويب، وسيارةُ TAXO، وزرٌّ مستدير؛ <b>وما لم يُكتب بعدُ سطرٌ يقول أين يُرى</b> لا شَرطةٌ تُقرأ رقماً. والمكوّنُ هو هو.
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
        RemoteViews views = new RemoteViews(ctx.getPackageName(), R.layout.tw_bar_earn);
        boolean enabled = prefs.getBoolean("widget", false);
        boolean online = enabled && prefs.getBoolean("online", false);
        String earnings = enabled ? prefs.getString("widget_earnings", null) : null;
        String rides = enabled ? prefs.getString("widget_rides", null) : null;
        views.setImageViewResource(R.id.tw_dot, online ? R.drawable.tw_dot_ok : R.drawable.tw_dot_off);
        views.setTextViewText(R.id.tw_title, !enabled ? "افتح التطبيق" : online ? "متّصل" : "غير متّصل");
        boolean amount = earnings != null && !earnings.isEmpty();
        views.setViewVisibility(R.id.tw_bigrow, amount ? View.VISIBLE : View.GONE);
        views.setViewVisibility(R.id.tw_sub, amount ? View.GONE : View.VISIBLE);
        if (amount) {
            views.setTextViewText(R.id.tw_big, earnings);
            views.setTextViewText(R.id.tw_unit, rides == null ? "" : rides);
        }
        if (enabled) {
            views.setTextViewText(R.id.tw_btn_t, online ? "افصل" : "اتّصل");
            views.setOnClickPendingIntent(R.id.tw_btn, open(ctx, online ? "go_offline" : "go_online", 51));
        } else {
            views.setTextViewText(R.id.tw_btn_t, "افتح");
            views.setOnClickPendingIntent(R.id.tw_btn, open(ctx, "home", 52));
        }
        views.setOnClickPendingIntent(R.id.tw_root, open(ctx, enabled ? "earnings" : "home", 53));
        return views;
    }
}
