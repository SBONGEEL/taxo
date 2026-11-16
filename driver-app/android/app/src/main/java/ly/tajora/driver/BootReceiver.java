package ly.tajora.driver;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

/**
 * <b>بعد إعادة تشغيل الهاتف</b> (SPEC §١٠٣ المرحلة A/6) — <b>إشعارٌ يعيده بلمسةٍ لا اتّصالٌ صامت</b> (انحرافٌ مسبَّبٌ في SPEC).
 *
 * <p><b>العلّةُ مكتوبةٌ في {@code OnlineService}</b>: الاستقبالُ يحتاج مقبسَ التطبيق، والخدمةُ توقف نفسَها حين يموت —
 * «وإبقاؤه كذبٌ مطبوعٌ في شريط الحالة». فخدمةٌ تُبعث بعد الإقلاع بلا التطبيق تقول «تستقبل» ولا شيءَ يستقبل.
 * فإن كان متّصلاً حين انطفأ الهاتف (ولم يفصل ولم يُغلق التطبيق) ومفتاحُه مشتعل: إشعارٌ «المس لتعود متّصلاً» يفتح التطبيقَ
 * بفعل {@code go_online} — والمسارُ القائمُ يفحص ما يفحصه. وفي كلِّ إقلاعٍ يُمحى «متّصل»: لا بلاطةَ تقول ما ليس قائماً.
 */
public class BootReceiver extends BroadcastReceiver {

    private static final String CHANNEL = "taxo_resume";

    @Override
    public void onReceive(Context ctx, Intent intent) {
        String action = intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action) && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) return;
        SharedPreferences prefs = ctx.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        boolean wasOnline = prefs.getBoolean("online", false);
        boolean enabled = prefs.getBoolean("boot", false);
        prefs.edit().putBoolean("online", false).apply();
        LauncherPlugin.wake(ctx);
        if (!wasOnline || !enabled || !Intent.ACTION_BOOT_COMPLETED.equals(action)) return;

        if (Build.VERSION.SDK_INT >= 26) {
            NotificationManager manager = ctx.getSystemService(NotificationManager.class);
            if (manager != null && manager.getNotificationChannel(CHANNEL) == null) {
                manager.createNotificationChannel(
                    new NotificationChannel(CHANNEL, "العودة بعد إعادة التشغيل", NotificationManager.IMPORTANCE_HIGH));
            }
        }
        Intent open = new Intent(ctx, MainActivity.class)
            .putExtra(LauncherPlugin.EXTRA, "go_online")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent tap = PendingIntent.getActivity(ctx, 61, open,
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        NotificationCompat.Builder note = new NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("أُعيد تشغيلُ هاتفك وأنت متّصل")
            .setContentText("المس لتعود متّصلاً وتصلك الطلبات")
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(tap);
        try {
            NotificationManagerCompat.from(ctx).notify(6101, note.build());
        } catch (SecurityException ignored) {
            // الإشعاراتُ مطفأة — مركزُ الأذونات يقول ذلك
        }
    }
}
