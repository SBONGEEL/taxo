package ly.tajora.driver;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
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

    /** <b>فاصلُ البثّ الفعّال</b> (SPEC §١٠٣ المرحلة A/3): {@link #BROADCAST_MS} افتراضاً، <b>وفاصلُ «المتاح» من لوحة البثّ</b> حين
     *  يشتعل {@code native_location} — يصل من الويب مع كلِّ نبضة ({@code interval_ms})، فتغييرُ اللوحة أو طورُها المتكيّف يبلغ الخدمة. */
    private long intervalMs = BROADCAST_MS;
    /** <b>أدنى ما يُقبل وأعلاه</b> — حدّا حمايةٍ لا قيمتان تُضبطان: اللوحةُ تكتب ما بينهما، وخارجهما خطأُ إدخالٍ لا يُطاع. */
    static final long MIN_INTERVAL_MS = 5_000L;
    static final long MAX_INTERVAL_MS = 60_000L;
    private LocationManager tracker = null;
    private LocationListener listener = null;
    private boolean started = false;
    /** <b>القيادةُ والوقوف</b> (§١٠٣ B/15): نبضةُ اللوحة ومسافةُ الحركة — يصلان مع الفاصل، وبلاهما لا يتغيّر شيء */
    private long heartbeatMs = 0L;
    private int moveMeters = 30;
    private Location lastSent = null;
    private long lastSentAt = 0L;

    /** <b>إشعارُ الرحلة الحيّ</b> (SPEC §١٠٣ B/18): سطرُ الحال يتبدّل في الإشعار القائم نفسِه — لا إشعارٌ ثانٍ ولا قناةٌ جديدة */
    static final String RIDE_FEATURE = "ride_live_notification";
    static final String RIDE_LINE = "ride_line";
    private final SharedPreferences.OnSharedPreferenceChangeListener rideLineWatch = (prefs, key) -> {
        if (RIDE_LINE.equals(key) || RIDE_FEATURE.equals(key)) refreshNotification();
    };

    /** <b>عنوانُ الإشعار أثناء الرحلة</b> — خالصٌ ومختبَر: مطفأً أو بلا سطرٍ أو والاتصالُ منقطع ⇐ {@code null} فيبقى ما كان حرفاً. */
    static String rideTitle(boolean feature, String line, boolean degraded) {
        if (!feature || degraded || line == null || line.trim().isEmpty()) return null;
        return line.trim();
    }

    /**
     * <b>أيُرسَل هذا الموقع؟</b> (SPEC §١٠٣ B/15) — خالصٌ ومختبَر. <b>واقفٌ لا يُرسل إلا نبضةَ اللوحة</b>: لم يتحرّك مسافةَ اللوحة منذ آخر
     * إرسال، ولم تمضِ نبضتُها ⇐ لا يُرسل. <b>ولا أقلَّ ممّا تسمح به اللوحة</b> — النبضةُ حدٌّ لا يُتجاوز، فمهلةُ الحضور لا تسقطه من
     * التوزيع؛ <b>ولا تقليلَ أثناء رحلة</b> ولا والمفتاحُ مطفأ ولا بلا نبضةٍ معروفة.
     */
    static boolean shouldSend(boolean motionAware, boolean rideActive, float movedMeters, long sinceLastMs,
                              long heartbeatMs, int moveMeters) {
        if (!motionAware || rideActive || heartbeatMs <= 0) return true;
        if (movedMeters < 0) return true;
        if (movedMeters >= moveMeters) return true;
        return sinceLastMs >= heartbeatMs;
    }

    /** <b>الفاصلُ من اللوحة</b> — مطفأً أو بلا قيمةٍ صالحة: الافتراضيّ كما كان حرفاً. خالصٌ ومختبَر. */
    static long effectiveInterval(boolean nativeLocation, long fromPanelMs) {
        if (!nativeLocation || fromPanelMs <= 0) return BROADCAST_MS;
        return Math.max(MIN_INTERVAL_MS, Math.min(MAX_INTERVAL_MS, fromPanelMs));
    }

    private boolean nativeLocation() {
        return getSharedPreferences(LauncherPlugin.PREFS, MODE_PRIVATE).getBoolean("native_location", false);
    }

    /** <b>موقعٌ حيٌّ والشاشةُ مطفأة</b>: بلا طلبِ تحديثاتٍ يبقى «آخرُ موقعٍ معروف» ما تركه الويبُ قبل أن يُخنق — قديماً.
     *  فحين يشتعل المفتاحُ تطلب الخدمةُ نفسُها تحديثاتِ GPS والشبكة بالفاصل الفعّال، <b>وتحت إذن «الموقع في الخلفية» الممنوح</b> لا غيره. */
    private void startTracking() {
        stopTracking();
        if (!nativeLocation()) return;
        LocationManager manager = getSystemService(LocationManager.class);
        if (manager == null) return;
        LocationListener l = fix -> { };
        try {
            for (String provider : new String[] {LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER}) {
                if (manager.isProviderEnabled(provider)) {
                    manager.requestLocationUpdates(provider, intervalMs, 0f, l, Looper.getMainLooper());
                }
            }
            tracker = manager;
            listener = l;
        } catch (SecurityException | IllegalArgumentException ignored) {
            // لا إذنَ أو لا مزوّد — يبقى «آخرُ موقعٍ معروف» كما كان
        }
    }

    private void stopTracking() {
        if (tracker != null && listener != null) {
            try {
                tracker.removeUpdates(listener);
            } catch (Exception ignored) {
                // أُزيلت من قبل
            }
        }
        tracker = null;
        listener = null;
    }

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
            if (intent.hasExtra("heartbeat_ms")) heartbeatMs = intent.getLongExtra("heartbeat_ms", 0L);
            if (intent.hasExtra("move_meters")) moveMeters = intent.getIntExtra("move_meters", 30);
            if (intent.hasExtra("interval_ms")) {
                long next = effectiveInterval(nativeLocation(), intent.getLongExtra("interval_ms", 0L));
                if (next != intervalMs || tracker == null) {
                    intervalMs = next;
                    startTracking();
                }
            }
        }
        if (!started) {
            started = true;
            getSharedPreferences(LauncherPlugin.PREFS, MODE_PRIVATE).registerOnSharedPreferenceChangeListener(rideLineWatch);
            // **اتّصالٌ جديد**: فقاعةُ الحال المُخفاةُ بالسحب تعود (§١٠٣ A/1) — الإخفاءُ لجلسةٍ واحدة
            StatusBubble.resetDismissed(this);
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
        // **«متّصل» يموت مع الخدمة** (SPEC §١٠٣/4–6): البلاطةُ والأداةُ تقرآنه — ولا تقولان ما ليس قائماً
        getSharedPreferences(LauncherPlugin.PREFS, MODE_PRIVATE).edit().putBoolean("online", false).apply();
        LauncherPlugin.wake(this);
        getSharedPreferences(LauncherPlugin.PREFS, MODE_PRIVATE).unregisterOnSharedPreferenceChangeListener(rideLineWatch);
        stopTracking();
        StatusBubble.hide(this);
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
    private boolean wantsToSend(Location fix) {
        android.content.SharedPreferences prefs = getSharedPreferences(LauncherPlugin.PREFS, MODE_PRIVATE);
        float moved = lastSent == null ? -1f : fix.distanceTo(lastSent);
        return shouldSend(prefs.getBoolean("motion_aware_location", false), prefs.getBoolean("ride_active", false),
                moved, SystemClock.elapsedRealtime() - lastSentAt, heartbeatMs, moveMeters);
    }

    private void armBeacon() {
        beacon.removeCallbacksAndMessages(null);
        beacon.postDelayed(this::broadcast, intervalMs);
    }

    private void broadcast() {
        try {
            if (endpoint != null && token != null) {
                Location fix = lastKnownFix();
                if (fix != null && wantsToSend(fix)) {
                    lastSent = fix;
                    lastSentAt = SystemClock.elapsedRealtime();
                    post(fix);
                }
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

    private void refreshNotification() {
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null && started) manager.notify(NOTIFICATION_ID, buildNotification(degradedNow));
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

        SharedPreferences prefs = getSharedPreferences(LauncherPlugin.PREFS, MODE_PRIVATE);
        String ride = rideTitle(prefs.getBoolean(RIDE_FEATURE, false), prefs.getString(RIDE_LINE, null), degraded);
        return new NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(ride != null ? ride : degraded ? "انقطع الاتصال" : "متصل — تستقبل الطلبات")
            .setContentText(
                ride != null
                    ? "اضغط للعودة إلى الرحلة"
                    : degraded
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
