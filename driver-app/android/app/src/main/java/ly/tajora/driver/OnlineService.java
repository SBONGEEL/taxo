package ly.tajora.driver;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;

import androidx.core.app.NotificationCompat;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

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

    /** فاصلُ البثِّ من الخدمة — **أوسعُ من فاصل الويب عمداً**.
     *
     * <p>الويبُ يبثّ كلَّ ٣ ثوانٍ ليرسم سيارتَه على خريطة الراكب بسلاسة.
     * <b>والخدمةُ لا ترسم شيئاً</b>: عملُها أن يبقى مفتاحُ الحضور حيّاً،
     * وعمرُه ٦٠ ثانية. فعشرون ثانيةً تُبقيه بثلاثة أضعافِ هامشٍ
     * <b>وتوفّر بطاريةَ كبتنٍ يعمل ساعات</b> — والبطاريةُ هنا ثمنٌ يُدفع من
     * جيبه لا رقمٌ في تقرير.
     */
    private static final long BROADCAST_MS = 20_000L;

    private final Handler watchdog = new Handler(Looper.getMainLooper());
    private final Handler beacon = new Handler(Looper.getMainLooper());
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private long lastPing = 0L;
    private boolean degradedNow = false;

    /** ما تحتاجه الخدمةُ لتبثّ بنفسها — **يُسلَّم من الويب ولا يُخزَّن على قرص**.
     *
     * <p><b>ولا رمزَ تجديدٍ هنا</b>: تجديدُ الجلسة <b>مُدوَّرٌ ذو استعمالٍ
     * واحد</b> (المواصفة §23)، وحاملان له يُبطل أحدُهما الآخر فيخرج الكبتنُ
     * من حسابه. فالخدمةُ تحمل <b>رمزَ وصولٍ قصيرَ العمر</b> يجدّده الويبُ ما
     * دام حيّاً — <b>وحدُّ ذلك مكتوبٌ في المواصفة §27.11-أ</b>.
     */
    private String endpoint = null;
    private String token = null;

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
        if (intent != null) {
            String url = intent.getStringExtra("endpoint");
            String bearer = intent.getStringExtra("token");
            if (url != null) endpoint = url;
            if (bearer != null) token = bearer;
        }
        startForegroundCompat(buildNotification(degraded || degradedNow));
        armWatchdog();
        armBeacon();
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
        beacon.removeCallbacksAndMessages(null);
        network.shutdownNow();
        super.onDestroy();
    }

    /**
     * <b>البثُّ من الخدمة نفسِها</b> — وهو ما يجعل «يستقبل والشاشةُ مطفأة»
     * يقع بدل أن يُوعَد به.
     *
     * <p><b>والعلّةُ مقيسةٌ</b> (S21، 2026-08-21): الخدمةُ وحدَها رفعت بقاءَ
     * الحضور من أقلَّ من ٣٠ ثانية إلى ≈١٢٠ <b>ثم سقط</b> — النظامُ يخنق
     * مؤقتاتِ الـWebView، فيقف بثُّه وتبقى العمليةُ حيّة. <b>وأخطرُ ما في
     * ذلك أن `is_online` بقي `true` بلا حضور.</b>
     *
     * <p><b>ولا عقدَ جديداً</b>: تنادي <b>البابَ نفسَه</b> الذي ينادي الويبُ
     * حين يسقط مقبسُه (`POST /drivers/me/location`) — فليست كاتباً ثانياً
     * لحقيقةٍ لها كاتب.
     */
    private void armBeacon() {
        beacon.removeCallbacksAndMessages(null);
        beacon.postDelayed(this::broadcast, BROADCAST_MS);
    }

    private void broadcast() {
        try {
            if (endpoint != null && token != null) {
                Location fix = lastKnownFix();
                if (fix != null) post(fix);
            }
        } catch (SecurityException ignored) {
            // إذنُ الموقع سُحب من الإعدادات أثناء العمل — والشاشةُ تقولها،
            // ولا يُسقط ذلك الخدمةَ ولا يُكتب في سجلٍّ كلَّ عشرين ثانية
        } finally {
            armBeacon();
        }
    }

    /**
     * <b>آخرُ تثبيتٍ معروفٍ لا اشتراكٌ في التدفق</b>، والفرقُ بطارية:
     * الاشتراكُ يوقظ الـGPS باستمرار، وهذا يقرأ ما قرأه النظامُ لغيرنا.
     * ونطلب تحديثاً واحداً بجانبه ليبقى المخزونُ حديثاً.
     */
    private Location lastKnownFix() {
        LocationManager manager = getSystemService(LocationManager.class);
        if (manager == null) return null;
        Location best = null;
        for (String provider : new String[] {
            LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER
        }) {
            try {
                Location fix = manager.getLastKnownLocation(provider);
                if (fix == null) continue;
                if (best == null || fix.getTime() > best.getTime()) best = fix;
            } catch (SecurityException | IllegalArgumentException ignored) {
                // مزوّدٌ غيرُ موجودٍ على هذا الجهاز، أو إذنٌ سُحب
            }
        }
        return best;
    }

    private void post(Location fix) {
        final String body =
            "{\"lat\":" + fix.getLatitude()
            + ",\"lng\":" + fix.getLongitude()
            + ",\"heading\":" + (fix.hasBearing() ? String.valueOf(fix.getBearing()) : "null")
            + "}";
        final String url = endpoint;
        final String bearer = token;
        network.execute(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(url).openConnection();
                connection.setRequestMethod("POST");
                connection.setConnectTimeout(10_000);
                connection.setReadTimeout(10_000);
                connection.setRequestProperty("Content-Type", "application/json");
                // **ترويسةٌ مستقلّةٌ لا `Authorization`** (§23.4): بهذا لا
                // يمرّ رمزُ الحضور بحارس الجلسة أصلاً، فلا يُقرأ جلسةً يوماً
                connection.setRequestProperty("X-Presence-Token", bearer);
                connection.setDoOutput(true);
                try (OutputStream out = connection.getOutputStream()) {
                    out.write(body.getBytes("UTF-8"));
                }
                int code = connection.getResponseCode();
                // **٢٠٤ وحدَها نبضة**: رمزٌ منتهٍ يردّ ٤٠١، وعدُّه نبضةً
                // يجعل الإشعارَ يقول «متصل» بينما لا حضورَ في Redis — وهو
                // الشكلُ السادس: معيارُ نجاحٍ يقيس غيرَ ما يدّعي
                if (code >= 200 && code < 300) {
                    lastPing = SystemClock.elapsedRealtime();
                }
            } catch (Exception ignored) {
                // شبكةٌ ساقطة — والصمتُ نفسُه هو ما يقلب الإشعار بعد ٩٠ ثانية
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
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
