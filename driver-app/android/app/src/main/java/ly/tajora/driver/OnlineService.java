package ly.tajora.driver;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;

import androidx.core.app.NotificationCompat;

/**
 * خدمةٌ أماميةٌ تبقي العمليةَ حيّةً ما دام الكبتنُ **مستقبِلاً**.
 *
 * <p><b>العلّةُ مقيسةٌ لا مقدَّرة</b> (S21، 2026-08-21): أُرسل التطبيقُ إلى
 * الخلفية فسقط مفتاحُ الحضور في <b>أقلَّ من ٣٠ ثانية</b> وصار
 * {@code drivers.is_online = false} — إغلاقُ المقبس يشغّل {@code go_offline}،
 * <b>والتوزيعُ لا يعرض على غير الحاضر</b>. فالكبتنُ الذي غادر التطبيق خارجٌ
 * من التوزيع، <b>ولا إشعارَ يوقظه لأن لا عرضَ يُصنع له</b>.
 *
 * <p><b>وحدُّها يُقال قبل أن تُصدَّق</b>: هي تبقي <b>العمليةَ</b> حيّةً —
 * فتعمل والشاشةُ مطفأةٌ والتطبيقُ في الخلفية. <b>ولا تعمل بعد أن يُزيح
 * الكبتنُ التطبيقَ من قائمة المهامّ</b>: المقبسُ يعيش في الـWebView، وإزالةُ
 * المهمّة تقتله. ولذلك {@link #onTaskRemoved} <b>يوقف الخدمة</b> بدل أن يترك
 * إشعاراً يقول «تستقبل» وهو لا يستقبل — <b>وكبتنٌ يظنّ نفسه متصلاً وليس كذلك
 * أخطرُ من كبتنٍ يعرف أنه غيرُ متصل</b>.
 *
 * <p><b>والإشعارُ يقول ما ينفع</b>: «متصل — تستقبل الطلبات»، وضغطُه يفتح
 * التطبيق. وأهميتُه {@code LOW} فلا صوتَ له: إشعارٌ دائمٌ يرنّ يُطفئه صاحبُه،
 * فيُطفئ معه ما يحتاجه.
 */
public class OnlineService extends Service {

    /** يُعلَن هنا لا في الواجهة: النصُّ خاصيّةُ إشعارِ النظام لا خاصيّةُ شاشة. */
    private static final String CHANNEL_ID = "taxo.online";
    private static final int NOTIFICATION_ID = 4201;

    /** «انقطع الاتصال» — يُرسله الجسرُ حين يسقط المقبسُ والكبتنُ يظنّ نفسه متصلاً. */
    public static final String ACTION_DEGRADED = "ly.tajora.driver.DEGRADED";

    /**
     * <b>مهلةُ الصمت</b>: بعدها يُقرأ سكوتُ الويب انقطاعاً لا هدوءاً.
     *
     * <p><b>ورقمُها مقيسٌ لا مقدَّر</b> (S21، 2026-08-21): مفتاحُ الحضور في
     * Redis عمرُه ٦٠ ثانية والتطبيقُ يبثّ أسرعَ منه، فصمتٌ يتجاوز ٩٠ ثانية
     * يعني أن الحضورَ <b>سقط فعلاً</b> لا أنه على وشك. وأقصرُ منها يصيح على
     * تعثّرِ شبكةٍ عابر، وأطولُ يترك الكبتنَ يظنّ نفسه مستقبِلاً دقائق.
     */
    private static final long SILENCE_MS = 90_000L;

    private final Handler watchdog = new Handler(Looper.getMainLooper());
    private long lastPing = 0L;
    private boolean degradedNow = false;

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        boolean degraded = intent != null && ACTION_DEGRADED.equals(intent.getAction());
        // **كلُّ نداءٍ سليمٍ نبضة**: الويبُ ينادي `start` مع كلِّ بثِّ موقعٍ
        // ناجح، فسكوتُه يُقرأ انقطاعاً بلا أن يحتاج رمزاً ولا شبكة
        if (!degraded) {
            lastPing = SystemClock.elapsedRealtime();
            degradedNow = false;
        }
        startForegroundCompat(buildNotification(degraded || degradedNow));
        armWatchdog();
        // **`START_STICKY` لا `START_NOT_STICKY`**: إن قتل النظامُ الخدمةَ
        // لضغطِ ذاكرةٍ أعادها — وهي الحالُ التي يكون فيها الكبتنُ عاملاً ولا
        // يدري أنه خرج. وما لا يغطّيه هذا مكتوبٌ في رأس الملف.
        return START_STICKY;
    }

    /**
     * أُزيل التطبيقُ من قائمة المهامّ — <b>فالمقبسُ مات ولو بقيت الخدمة</b>.
     *
     * <p>فتُوقَف الخدمةُ ويُزال إشعارُها. <b>وإبقاؤه هنا كذبٌ مطبوعٌ في شريط
     * الحالة</b>: يقول «تستقبل الطلبات» بينما لا شيءَ يستقبل.
     */
    @Override
    public void onTaskRemoved(Intent rootIntent) {
        stopSelf();
        super.onTaskRemoved(rootIntent);
    }

    @Override
    public void onDestroy() {
        watchdog.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    /**
     * <b>الحارسُ الذي يمنع أخطرَ الحالين</b>: كبتنٌ يقرأ «تستقبل الطلبات»
     * وهو خارجُ التوزيع.
     *
     * <p>قِيس على S21 أن الخدمةَ تُبقي العمليةَ حيّةً بينما <b>يخنق النظامُ
     * مؤقتاتِ الـWebView</b> بعد دقيقتين تقريباً، فيقف البثُّ ويسقط الحضورُ
     * <b>ويبقى الإشعارُ يقول «متصل»</b>. فصار الصمتُ نفسُه هو الإشارة.
     */
    private void armWatchdog() {
        watchdog.removeCallbacksAndMessages(null);
        watchdog.postDelayed(this::checkSilence, 30_000L);
    }

    private void checkSilence() {
        boolean silent =
            lastPing > 0 && SystemClock.elapsedRealtime() - lastPing > SILENCE_MS;
        if (silent && !degradedNow) {
            degradedNow = true;
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.notify(NOTIFICATION_ID, buildNotification(true));
        }
        armWatchdog();
    }

    private void startForegroundCompat(Notification notification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            // أندرويد 14 يشترط **نوعاً** للخدمة الأمامية، ونوعُنا الموقع:
            // ما تبقيه الخدمةُ حيّاً هو بثُّ موقع الكبتن
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
            );
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    private Notification buildNotification(boolean degraded) {
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && manager != null) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "حالة الاستقبال",
                NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("يظهر ما دمتَ تستقبل الطلبات");
            channel.setShowBadge(false);
            manager.createNotificationChannel(channel);
        }

        Intent open = new Intent(this, MainActivity.class);
        open.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent tap = PendingIntent.getActivity(
            this,
            0,
            open,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        return new NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(degraded ? "انقطع الاتصال" : "متصل — تستقبل الطلبات")
            .setContentText(
                degraded
                    ? "افتح التطبيق لإعادة الاستقبال"
                    : "اضغط لفتح التطبيق"
            )
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(tap)
            .setOngoing(true)
            .setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build();
    }
}
