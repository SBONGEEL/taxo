package ly.tajora.driver;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONObject;

import java.util.Locale;

/**
 * <b>ودجةُ الكبتن الجديدة</b> (أمرُ المالك ٢٠/١١ الرابع، الجزء ٣، SPEC §١١٠) — خلف {@code driver_widgets_plus}.
 *
 * <p>صغيرةً: الحالُ وزرُّ الاتّصال/الإيقاف مع صافي اليوم ورحلاته. متوسّطةً: + حلقةُ الهدف وأيّامُ الاشتراك. كبيرةً: + أقربُ منطقةٍ
 * مزدحمة بـ«اذهب إليها»، وأثناء الرحلة حالُها و«اتصال». <b>كلُّ رقمٍ ممّا كتبه التطبيق</b> (الويبُ أو الفقاعة)، ولا حسابَ هنا إلا نسبةَ
 * امتلاء الحلقة للعرض. <b>وتتحدّث حين يتغيّر الحال</b> ({@code LAUNCHER_CHANGED}) لا بمؤقّت، <b>وتقول «سجّل الدخول» لمن خرج</b>.
 *
 * <p><b>والأزرارُ تفتح التطبيقَ على فعلٍ</b> (كالبلاطة): الاتّصالُ يمرّ بفحص الاشتراك والأذونات في الويب، <b>والمكالمةُ بأرقامٍ مخفيّة</b>.
 */
public class DriverWidget extends AppWidgetProvider {

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
            onUpdate(ctx, manager, manager.getAppWidgetIds(new ComponentName(ctx, DriverWidget.class)));
        }
    }

    /** خالصة: <b>حجمُ الودجة</b> من أبعادها بالـdp — {@code 0} صغيرة، {@code 1} متوسّطة، {@code 2} كبيرة. */
    static int sizeClass(int minWidthDp, int minHeightDp) {
        if (minHeightDp >= 150 && minWidthDp >= 250) return 2;
        if (minWidthDp >= 250 || minHeightDp >= 110) return 1;
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
        RemoteViews v = new RemoteViews(ctx.getPackageName(), R.layout.widget_driver);
        int w = options == null ? 250 : options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 250);
        int h = options == null ? 110 : options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, 110);
        int size = sizeClass(w, h);
        boolean enabled = p.getBoolean("driver_widgets_plus", false);
        boolean signedIn = p.getBoolean("signed_in", false);
        boolean online = p.getBoolean("online", false);
        v.setOnClickPendingIntent(R.id.w2_root, open(ctx, null, 71));
        v.setViewVisibility(R.id.w2_busy_row, View.GONE);
        v.setViewVisibility(R.id.w2_ride_row, View.GONE);
        if (!enabled || !signedIn) {
            // **بطاقةٌ تملأ الودجة** (٢٠/١١ السادس، البند ٣) — لا سطرٌ في أعلاها وفراغٌ تحته
            v.setViewVisibility(R.id.w2_head, View.GONE);
            WidgetSignedOut.show(ctx, v, h, signedIn ? "حالُك وأرباحُ يومك في التطبيق" : "حالُك وأرباحُ يومك هنا بعد الدخول",
                    signedIn ? "افتح التطبيق" : "سجّل الدخول", open(ctx, null, 72));
            return v;
        }
        v.setViewVisibility(R.id.wo_root, View.GONE);
        v.setViewVisibility(R.id.w2_head, View.VISIBLE);
        v.setTextViewText(R.id.w2_title, online ? "متّصل" : "غير متّصل");
        String earnings = p.getString("widget_earnings", null);
        String rides = p.getString("widget_rides", null);
        v.setTextViewText(R.id.w2_line, earnings == null ? "أرباح اليوم —" : earnings + (rides == null ? "" : " · " + rides));
        v.setTextViewText(R.id.w2_toggle, online ? "أوقف" : "اتّصل");
        v.setOnClickPendingIntent(R.id.w2_toggle, open(ctx, online ? "go_offline" : "go_online", 73));

        float goal = p.getBoolean("bubble_goal_ring", false)
                ? BubbleLogic.goalFraction(p.getString("today_earned", null), p.getString("bubble_goal", null)) : -1f;
        float sub = -1f;
        String days = p.getString("sub_days", null);
        if (days != null) {
            try {
                sub = BubbleLogic.subscriptionFraction(Integer.parseInt(days));
            } catch (NumberFormatException ignored) {
                sub = -1f;
            }
        }
        v.setImageViewBitmap(R.id.w2_ring, ring(ctx, size >= 1 ? goal : -1f, size >= 1 ? sub : -1f,
                days == null ? "TAXO" : days + "ي"));
        if (size == 0) return v;

        JSONObject ride = DriverBubbleMenu.ride(p);
        if (ride != null) {
            String status = ride.optString("status", "");
            String rider = ride.optString("rider", "الراكب");
            v.setTextViewText(R.id.w2_ride, rider + " · " + ("accepted".equals(status) ? "في الطريق إليه"
                    : "arrived".equals(status) ? "بانتظاره" : "في الرحلة"));
            v.setOnClickPendingIntent(R.id.w2_call, open(ctx, "call", 74));
            v.setViewVisibility(R.id.w2_ride_row, View.VISIBLE);
        } else if (size == 2 && online) {
            JSONObject area = DriverBubbleMenu.busy(p);
            if (area != null) {
                v.setTextViewText(R.id.w2_busy, BubbleLogic.busyLine(area.optString("name", null), area.optDouble("distance_km", 0)));
                Intent nav = new Intent(Intent.ACTION_VIEW, Uri.parse(String.format(Locale.ROOT, "google.navigation:q=%.6f,%.6f",
                        area.optDouble("lat"), area.optDouble("lng"))));
                v.setOnClickPendingIntent(R.id.w2_busy_go, PendingIntent.getActivity(ctx, 75, nav,
                        PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT));
                v.setViewVisibility(R.id.w2_busy_row, View.VISIBLE);
            }
        }
        return v;
    }

    /** الحلقتان صورةً — الهدفُ خارجاً بالبرتقاليّ، والاشتراكُ داخلاً بالأخضر الهادئ، ونصٌّ قصيرٌ في الوسط. */
    static Bitmap ring(Context ctx, float goal, float sub, String center) {
        boolean dark = (ctx.getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        OfferPalette pal = OfferPalette.of(ctx);
        int px = OfferUi.dp(ctx, 52);
        Bitmap bmp = Bitmap.createBitmap(px, px, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bmp);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        float stroke = OfferUi.dp(ctx, 4);
        RectF outer = new RectF(stroke, stroke, px - stroke, px - stroke);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeCap(Paint.Cap.ROUND);
        paint.setStrokeWidth(stroke);
        paint.setColor(pal.brd);
        c.drawArc(outer, 0, 360, false, paint);
        if (goal >= 0f) {
            paint.setColor(pal.acc);
            c.drawArc(outer, -90, 360 * goal, false, paint);
        }
        if (sub >= 0f) {
            float in = stroke * 2.4f;
            RectF inner = new RectF(in, in, px - in, px - in);
            paint.setStrokeWidth(OfferUi.dp(ctx, 2.5f));
            paint.setColor(pal.ok);
            c.drawArc(inner, -90, 360 * sub, false, paint);
        }
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(dark ? Color.parseColor("#f2efe8") : Color.parseColor("#14161a"));
        paint.setTypeface(Typeface.DEFAULT_BOLD);
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTextSize(px * ("TAXO".equals(center) ? 0.22f : 0.26f));
        c.drawText(center, px / 2f, px / 2f + paint.getTextSize() * 0.36f, paint);
        return bmp;
    }
}
