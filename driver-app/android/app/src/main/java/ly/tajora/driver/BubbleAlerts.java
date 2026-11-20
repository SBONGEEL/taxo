package ly.tajora.driver;

import android.app.AlarmManager;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

import androidx.core.app.NotificationCompat;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * <b>تنبيهاتُ الفقاعة</b> (أمرُ المالك ٢٠/١١ الرابع): <b>الاستراحةُ تنتهي بعد دقيقة</b> (البند ٤٤)، <b>وعدتَ إلى العروض</b> عند نهايتها،
 * <b>والاشتراكُ ينتهي غداً</b> (البند ٤٨) مرّةً في اليوم.
 *
 * <p><b>منبّهٌ غيرُ دقيقٍ بنافذة ٣٠ ثانية</b> ({@code setWindow}) لا {@code setExact}: لا يحتاج إذنَ «المنبّهات الدقيقة» ولا تصريحاً في
 * Play، ودقيقةٌ قبل النهاية تحتمل نصفَ دقيقة. <b>والعودةُ إلى العروض لا تنتظر هذا المنبّه</b>: التوزيعُ يقارن بالساعة في الخادم
 * (SPEC §١١٠) — المنبّهُ إخبارٌ لا مفتاح.
 */
public final class BubbleAlerts extends BroadcastReceiver {

    static final String ACTION = "ly.tajora.driver.BREAK_ALERT";
    private static final int SOON = 4401;
    private static final int OVER = 4402;
    private static final int SUB = 4403;

    @Override
    public void onReceive(Context context, Intent intent) {
        boolean over = intent.getBooleanExtra("over", false);
        if (over) {
            context.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE).edit().remove("break_until").apply();
            StatusBubble.refresh(context);
        }
        notify(context, over ? OVER : SOON,
                over ? "انتهت الاستراحة" : "تنتهي استراحتك بعد دقيقة",
                over ? "عدتَ إلى العروض — ستصلك الطلباتُ الآن" : "ثمّ تعود إلى العروض وحدَك");
    }

    private static PendingIntent pending(Context c, boolean over) {
        Intent intent = new Intent(c, BubbleAlerts.class).setAction(ACTION).putExtra("over", over);
        return PendingIntent.getBroadcast(c, over ? OVER : SOON, intent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    static void scheduleBreak(Context context, long until) {
        Context c = context.getApplicationContext();
        if (until <= System.currentTimeMillis()) return;
        AlarmManager am = c.getSystemService(AlarmManager.class);
        if (am == null) return;
        long soon = until - 60_000;
        if (soon > System.currentTimeMillis()) am.setWindow(AlarmManager.RTC_WAKEUP, soon, 30_000, pending(c, false));
        am.setWindow(AlarmManager.RTC_WAKEUP, until, 30_000, pending(c, true));
    }

    static void cancelBreak(Context context) {
        Context c = context.getApplicationContext();
        AlarmManager am = c.getSystemService(AlarmManager.class);
        if (am != null) {
            am.cancel(pending(c, false));
            am.cancel(pending(c, true));
        }
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm != null) nm.cancel(SOON);
    }

    /** <b>«ينتهي اشتراكك غداً»</b> — يومٌ واحدٌ أو أقلّ، مرّةً في اليوم. */
    static void subscriptionEnding(Context context, int days) {
        if (days > 1) return;
        Context c = context.getApplicationContext();
        SharedPreferences p = c.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        String today = new SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).format(new Date());
        if (today.equals(p.getString("sub_alerted", null))) return;
        p.edit().putString("sub_alerted", today).apply();
        notify(c, SUB, days <= 0 ? "انتهى اشتراكك" : "ينتهي اشتراكك غداً", "جدّده من التطبيق لتبقى الطلباتُ تصلك");
    }

    private static void notify(Context c, int id, String title, String text) {
        TaxoChannels.ensure(c);
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (nm == null) return;
        Intent open = new Intent(c, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);
        PendingIntent tap = PendingIntent.getActivity(c, id, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        try {
            nm.notify(id, new NotificationCompat.Builder(c, TaxoChannels.GENERAL)
                    .setSmallIcon(R.drawable.ic_stat_taxo)
                    .setContentTitle(title)
                    .setContentText(text)
                    .setAutoCancel(true)
                    .setContentIntent(tap)
                    .build());
        } catch (SecurityException ignored) {
            // إذنُ الإشعارات مسحوب
        }
    }
}
